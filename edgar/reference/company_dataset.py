"""
Company Dataset Builder for EdgarTools

Builds high-performance company datasets from SEC submissions data with two output formats:
1. PyArrow Parquet (5-20 MB) - Fast filtering with PyArrow compute API
2. DuckDB (287 MB) - Optional SQL interface for power users

Performance:
- Build time: ~30 seconds (optimized with orjson + company filtering)
- Records: ~562,413 companies (40% individual filers filtered)
- Query speed: <1ms (DuckDB) or <100ms (Parquet)

Example:
    >>> from edgar.reference import get_company_dataset
    >>> import pyarrow.compute as pc
    >>>
    >>> # Load dataset (builds on first use)
    >>> companies = get_company_dataset()
    >>>
    >>> # Filter pharmaceutical companies
    >>> pharma = companies.filter(pc.field('sic').between(2834, 2836))
    >>> print(f"Found {len(pharma)} pharma companies")
"""

from pathlib import Path
from typing import Optional, Union
import logging

import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

from edgar.core import get_edgar_data_directory, log

# Try to import orjson for performance, fall back to stdlib json
try:
    import orjson

    def load_json(path: Path) -> dict:
        """Load JSON file using orjson (1.55x faster)"""
        return orjson.loads(path.read_bytes())

    JSON_PARSER = "orjson"
except ImportError:
    import json

    def load_json(path: Path) -> dict:
        """Load JSON file using stdlib json"""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    JSON_PARSER = "json (stdlib)"


# Company dataset schema
COMPANY_SCHEMA = pa.schema([
    ('cik', pa.string()),  # Keep as string to preserve leading zeros
    ('name', pa.string()),
    ('sic', pa.int32()),  # Nullable - some companies have no SIC
    ('sic_description', pa.string()),
    ('tickers', pa.string()),  # Pipe-delimited (e.g., "AAPL|APPLE")
    ('exchanges', pa.string()),  # Pipe-delimited (e.g., "Nasdaq|NYSE")
    ('state_of_incorporation', pa.string()),
    ('state_of_incorporation_description', pa.string()),
    ('fiscal_year_end', pa.string()),  # MMDD format
    ('entity_type', pa.string()),
    ('ein', pa.string()),
])


def is_individual_from_json(data: dict) -> bool:
    """
    Determine if entity is an individual filer vs a company.

    Uses the same logic as edgar.entity.data:478 (is_individual property).

    Companies typically have:
    - Tickers or exchanges
    - State of incorporation
    - Entity type other than '' or 'other'
    - Company-specific filings (10-K, 10-Q, 8-K, etc.)

    Args:
        data: Parsed JSON submission data

    Returns:
        True if individual filer, False if company

    Example:
        >>> data = {'cik': '0001318605', 'tickers': ['TSLA']}
        >>> is_individual_from_json(data)
        False

        >>> data = {'cik': '0001078519', 'name': 'JOHN DOE'}
        >>> is_individual_from_json(data)
        True
    """
    # Has ticker or exchange → company
    if data.get('tickers') or data.get('exchanges'):
        return False

    # Has state of incorporation → company (with exceptions)
    state = data.get('stateOfIncorporation', '')
    if state and state != '':
        # Reed Hastings exception (individual with state of incorporation)
        if data.get('cik') == '0001033331':
            return True
        return False

    # Has entity type (not '' or 'other') → company
    entity_type = data.get('entityType', '')
    if entity_type and entity_type not in ['', 'other']:
        return False

    # Files company forms (10-K, 10-Q, etc.) → company
    filings = data.get('filings', {})
    if filings:
        recent = filings.get('recent', {})
        forms = recent.get('form', [])
        company_forms = {'10-K', '10-Q', '8-K', '10-K/A', '10-Q/A', '20-F', 'S-1'}
        if any(form in company_forms for form in forms):
            return False

    # Default: individual
    return True


def build_company_dataset_parquet(
    submissions_dir: Path,
    output_path: Path,
    filter_individuals: bool = True,
    show_progress: bool = True
) -> pa.Table:
    """
    Build PyArrow Parquet dataset from submissions directory (companies only).

    This function processes all CIK*.json files in the submissions directory,
    filters out individual filers (optional), and creates a compressed Parquet file.

    Performance:
        - ~30 seconds for 562,413 companies (with orjson + filtering)
        - Output size: ~5-20 MB (zstd compressed)
        - Memory usage: ~100-200 MB during build

    Args:
        submissions_dir: Directory containing CIK*.json files
        output_path: Where to save the .pq file
        filter_individuals: Skip individual filers (default: True)
        show_progress: Show progress bar (default: True)

    Returns:
        PyArrow Table with company data

    Raises:
        FileNotFoundError: If submissions_dir doesn't exist

    Example:
        >>> from pathlib import Path
        >>> submissions_dir = Path.home() / '.edgar' / 'submissions'
        >>> output_path = Path.home() / '.edgar' / 'companies.pq'
        >>> table = build_company_dataset_parquet(submissions_dir, output_path)
        >>> print(f"Built dataset: {len(table):,} companies")
    """
    if not submissions_dir.exists():
        raise FileNotFoundError(
            f"Submissions directory not found: {submissions_dir}\n\n"
            "Please download submissions data first:\n"
            "  from edgar.storage import download_submissions\n"
            "  download_submissions()\n"
        )

    # Get all submission JSON files
    json_files = list(submissions_dir.glob("CIK*.json"))
    if len(json_files) == 0:
        raise FileNotFoundError(
            f"No submission files found in: {submissions_dir}\n"
            "Expected CIK*.json files"
        )

    log.info(f"Building company dataset from {len(json_files):,} submission files")
    log.info(f"Using JSON parser: {JSON_PARSER}")

    companies = []
    errors = 0
    individuals_skipped = 0

    # Process each file with progress bar
    iterator = tqdm(json_files, desc="Processing submissions", disable=not show_progress)

    for json_file in iterator:
        try:
            data = load_json(json_file)

            # Skip individuals if filtering enabled
            if filter_individuals and is_individual_from_json(data):
                individuals_skipped += 1
                continue

            # Extract SIC (handle empty strings)
            sic = data.get('sic')
            sic_int = int(sic) if sic and sic != '' else None

            # Extract tickers and exchanges (filter None values)
            tickers = data.get('tickers', [])
            exchanges = data.get('exchanges', [])

            companies.append({
                'cik': data.get('cik'),
                'name': data.get('name'),
                'sic': sic_int,
                'sic_description': data.get('sicDescription'),
                'tickers': '|'.join(filter(None, tickers)) if tickers else None,
                'exchanges': '|'.join(filter(None, exchanges)) if exchanges else None,
                'state_of_incorporation': data.get('stateOfIncorporation'),
                'state_of_incorporation_description': data.get('stateOfIncorporationDescription'),
                'fiscal_year_end': data.get('fiscalYearEnd'),
                'entity_type': data.get('entityType'),
                'ein': data.get('ein'),
            })

        except Exception as e:
            errors += 1
            log.debug(f"Error processing {json_file.name}: {e}")
            continue

    # Log statistics
    log.info(f"Processed {len(json_files):,} files:")
    log.info(f"  - Companies: {len(companies):,}")
    if filter_individuals:
        log.info(f"  - Individuals skipped: {individuals_skipped:,}")
    if errors > 0:
        log.warning(f"  - Errors: {errors:,}")

    # Create PyArrow Table
    table = pa.Table.from_pylist(companies, schema=COMPANY_SCHEMA)

    # Write to Parquet with compression
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        table,
        output_path,
        compression='zstd',
        compression_level=9,
        use_dictionary=True
    )

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    log.info(f"Saved Parquet file: {output_path} ({file_size_mb:.1f} MB)")

    return table


def build_company_dataset_duckdb(
    submissions_dir: Path,
    output_path: Path,
    filter_individuals: bool = True,
    create_indexes: bool = True,
    show_progress: bool = True
) -> None:
    """
    Build DuckDB database from submissions directory (companies only).

    This function creates a DuckDB database with a 'companies' table and
    optional indexes on key columns for fast querying.

    Performance:
        - ~30 seconds for 562,413 companies (with orjson + filtering)
        - Output size: ~287 MB
        - Query speed: <1ms with indexes

    Args:
        submissions_dir: Directory containing CIK*.json files
        output_path: Where to save the .duckdb file
        filter_individuals: Skip individual filers (default: True)
        create_indexes: Create indexes on cik, sic, name (default: True)
        show_progress: Show progress bar (default: True)

    Raises:
        FileNotFoundError: If submissions_dir doesn't exist
        ImportError: If duckdb package not installed

    Example:
        >>> from pathlib import Path
        >>> submissions_dir = Path.home() / '.edgar' / 'submissions'
        >>> output_path = Path.home() / '.edgar' / 'companies.duckdb'
        >>> build_company_dataset_duckdb(submissions_dir, output_path)
        >>>
        >>> import duckdb
        >>> con = duckdb.connect(str(output_path))
        >>> result = con.execute("SELECT COUNT(*) FROM companies").fetchone()
        >>> print(f"Companies: {result[0]:,}")
    """
    try:
        import duckdb
    except ImportError:
        raise ImportError(
            "DuckDB export requires duckdb package.\n"
            "Install with: pip install duckdb"
        )

    if not submissions_dir.exists():
        raise FileNotFoundError(
            f"Submissions directory not found: {submissions_dir}\n\n"
            "Please download submissions data first:\n"
            "  from edgar.storage import download_submissions\n"
            "  download_submissions()\n"
        )

    # Get all submission JSON files
    json_files = list(submissions_dir.glob("CIK*.json"))
    if len(json_files) == 0:
        raise FileNotFoundError(
            f"No submission files found in: {submissions_dir}\n"
            "Expected CIK*.json files"
        )

    log.info(f"Building DuckDB database from {len(json_files):,} submission files")
    log.info(f"Using JSON parser: {JSON_PARSER}")

    companies = []
    errors = 0
    individuals_skipped = 0

    # Process each file with progress bar
    iterator = tqdm(json_files, desc="Processing submissions", disable=not show_progress)

    for json_file in iterator:
        try:
            data = load_json(json_file)

            # Skip individuals if filtering enabled
            if filter_individuals and is_individual_from_json(data):
                individuals_skipped += 1
                continue

            # Extract SIC (handle empty strings)
            sic = data.get('sic')
            sic_int = int(sic) if sic and sic != '' else None

            # Extract tickers and exchanges (filter None values)
            tickers = data.get('tickers', [])
            exchanges = data.get('exchanges', [])

            companies.append({
                'cik': data.get('cik'),
                'name': data.get('name'),
                'sic': sic_int,
                'sic_description': data.get('sicDescription'),
                'tickers': '|'.join(filter(None, tickers)) if tickers else None,
                'exchanges': '|'.join(filter(None, exchanges)) if exchanges else None,
                'state_of_incorporation': data.get('stateOfIncorporation'),
                'state_of_incorporation_description': data.get('stateOfIncorporationDescription'),
                'fiscal_year_end': data.get('fiscalYearEnd'),
                'entity_type': data.get('entityType'),
                'ein': data.get('ein'),
            })

        except Exception as e:
            errors += 1
            log.debug(f"Error processing {json_file.name}: {e}")
            continue

    # Log statistics
    log.info(f"Processed {len(json_files):,} files:")
    log.info(f"  - Companies: {len(companies):,}")
    if filter_individuals:
        log.info(f"  - Individuals skipped: {individuals_skipped:,}")
    if errors > 0:
        log.warning(f"  - Errors: {errors:,}")

    # Create DuckDB database
    import pandas as pd

    output_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(output_path))

    # Create table from DataFrame
    df = pd.DataFrame(companies)
    con.execute("CREATE TABLE companies AS SELECT * FROM df")

    # Create indexes
    if create_indexes:
        log.info("Creating indexes...")
        con.execute("CREATE INDEX idx_cik ON companies(cik)")
        con.execute("CREATE INDEX idx_sic ON companies(sic)")
        con.execute("CREATE INDEX idx_name ON companies(name)")

    # Add metadata table
    con.execute("""
        CREATE TABLE metadata AS
        SELECT
            CURRENT_TIMESTAMP as created_at,
            COUNT(*) as total_companies,
            COUNT(DISTINCT sic) as unique_sic_codes,
            COUNT(DISTINCT CASE WHEN tickers IS NOT NULL THEN 1 END) as companies_with_tickers,
            COUNT(DISTINCT CASE WHEN exchanges IS NOT NULL THEN 1 END) as companies_with_exchanges
        FROM companies
    """)

    con.close()

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    log.info(f"Saved DuckDB database: {output_path} ({file_size_mb:.1f} MB)")


def load_company_dataset_parquet(parquet_path: Path) -> pa.Table:
    """
    Load company dataset from Parquet file.

    This is a simple wrapper around pyarrow.parquet.read_table() with
    logging for consistency.

    Performance: <100ms for typical dataset

    Args:
        parquet_path: Path to .pq file

    Returns:
        PyArrow Table with company data

    Example:
        >>> from pathlib import Path
        >>> path = Path.home() / '.edgar' / 'companies.pq'
        >>> companies = load_company_dataset_parquet(path)
        >>> print(f"Loaded {len(companies):,} companies")
    """
    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

    table = pq.read_table(parquet_path)
    log.debug(f"Loaded {len(table):,} companies from {parquet_path}")

    return table


def to_duckdb(
    parquet_path: Path,
    duckdb_path: Path,
    create_indexes: bool = True
) -> None:
    """
    Convert Parquet dataset to DuckDB database.

    This provides an easy way to export the Parquet dataset to DuckDB
    for users who want SQL query capabilities.

    Performance: <5 seconds for typical dataset

    Args:
        parquet_path: Path to source .pq file
        duckdb_path: Path to output .duckdb file
        create_indexes: Create indexes on key columns (default: True)

    Example:
        >>> from pathlib import Path
        >>> parquet_path = Path.home() / '.edgar' / 'companies.pq'
        >>> duckdb_path = Path.home() / '.edgar' / 'companies.duckdb'
        >>> to_duckdb(parquet_path, duckdb_path)
        >>>
        >>> import duckdb
        >>> con = duckdb.connect(str(duckdb_path))
        >>> result = con.execute(
        ...     "SELECT * FROM companies WHERE sic = 2834"
        ... ).fetchdf()
    """
    try:
        import duckdb
    except ImportError:
        raise ImportError(
            "DuckDB export requires duckdb package.\n"
            "Install with: pip install duckdb"
        )

    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

    log.info(f"Converting Parquet to DuckDB: {parquet_path} -> {duckdb_path}")

    # Read Parquet file and convert to pandas
    table = pq.read_table(parquet_path)
    import pandas as pd
    df = table.to_pandas()

    # Create DuckDB database
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(duckdb_path))

    # Create table from DataFrame
    con.execute("CREATE TABLE companies AS SELECT * FROM df")

    # Create indexes
    if create_indexes:
        log.info("Creating indexes...")
        con.execute("CREATE INDEX idx_cik ON companies(cik)")
        con.execute("CREATE INDEX idx_sic ON companies(sic)")
        con.execute("CREATE INDEX idx_name ON companies(name)")

    # Add metadata
    con.execute("""
        CREATE TABLE metadata AS
        SELECT
            CURRENT_TIMESTAMP as created_at,
            COUNT(*) as total_companies,
            COUNT(DISTINCT sic) as unique_sic_codes,
            COUNT(DISTINCT CASE WHEN tickers IS NOT NULL THEN 1 END) as companies_with_tickers,
            COUNT(DISTINCT CASE WHEN exchanges IS NOT NULL THEN 1 END) as companies_with_exchanges
        FROM companies
    """)

    con.close()

    file_size_mb = duckdb_path.stat().st_size / (1024 * 1024)
    log.info(f"Exported to DuckDB: {duckdb_path} ({file_size_mb:.1f} MB)")


# In-memory cache for dataset
_CACHE = {}


def get_company_dataset(rebuild: bool = False) -> pa.Table:
    """
    Get company dataset, building from submissions if needed.

    This function checks for a cached dataset at ~/.edgar/companies.pq.
    If not found, it automatically builds the dataset from submissions data.

    On first use, this will take ~30 seconds to build the dataset. Subsequent
    calls load from cache in <100ms.

    Args:
        rebuild: Force rebuild even if cache exists (default: False)

    Returns:
        PyArrow Table with company data (~562,413 companies)

    Raises:
        FileNotFoundError: If submissions directory not found or incomplete

    Performance:
        - First use: ~30 seconds (builds dataset)
        - Cached: <100ms (loads from disk)
        - Memory: ~20-50 MB

    Example:
        >>> from edgar.reference import get_company_dataset
        >>> import pyarrow.compute as pc
        >>>
        >>> # First call builds dataset (takes ~30s)
        >>> companies = get_company_dataset()
        >>> print(f"Loaded {len(companies):,} companies")
        >>>
        >>> # Subsequent calls are fast (<100ms)
        >>> companies = get_company_dataset()
        >>>
        >>> # Filter pharmaceutical companies (SIC 2834-2836)
        >>> pharma = companies.filter(
        ...     pc.field('sic').between(2834, 2836)
        ... )
        >>> print(f"Found {len(pharma)} pharma companies")
        >>>
        >>> # Filter by exchange
        >>> nasdaq = companies.filter(
        ...     pc.field('exchanges').contains('Nasdaq')
        ... )
        >>>
        >>> # Force rebuild with latest data
        >>> companies = get_company_dataset(rebuild=True)
    """
    # Check in-memory cache first
    if not rebuild and 'companies' in _CACHE:
        return _CACHE['companies']

    # Check disk cache
    cache_path = get_edgar_data_directory() / 'companies.pq'

    if cache_path.exists() and not rebuild:
        # Load from cache
        log.info(f"Loading company dataset from cache: {cache_path}")
        table = load_company_dataset_parquet(cache_path)
        _CACHE['companies'] = table
        return table

    # Need to build dataset
    log.info("Building company dataset from submissions (this may take ~30 seconds)...")

    submissions_dir = get_edgar_data_directory() / 'submissions'
    if not submissions_dir.exists() or len(list(submissions_dir.glob('CIK*.json'))) < 100000:
        raise FileNotFoundError(
            f"Submissions directory not found or incomplete: {submissions_dir}\n\n"
            "Please download submissions data first:\n"
            "  from edgar.storage import download_submissions\n"
            "  download_submissions()\n\n"
            "This is a one-time download (~500 MB compressed)."
        )

    # Build dataset
    table = build_company_dataset_parquet(
        submissions_dir,
        cache_path,
        filter_individuals=True
    )

    log.info(f"✅ Built dataset: {len(table):,} companies, cached at {cache_path}")

    _CACHE['companies'] = table
    return table
