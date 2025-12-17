# Per-Company Presentation Metadata Database

A comprehensive specification for building company-specific presentation metadata covering ~13,000 ticker companies. This guide is designed as a standalone document for downstream implementation.

## Executive Summary

| Aspect | Details |
|--------|---------|
| **Goal** | Store presentation trees for all ~13K SEC-registered companies with tickers |
| **Use Case** | Render financial statements with full company-specific structure (no concept loss) |
| **Storage** | 100-200 MB compressed (Parquet with zstd) |
| **Build Time** | 10-20 hours at ~5 seconds per company |
| **Source** | EdgarTools XBRL parsing + SEC submissions |

## Background: Why Per-Company Metadata?

### The Canonical Gap Problem

When using canonical (common) concepts only, we lose company-specific data:

| Metric | Value |
|--------|-------|
| Total unique concepts (10 companies) | 486 |
| Canonical concepts (≥30% occurrence) | 198 (40.7%) |
| Non-canonical concepts lost | 288 (59.3%) |
| Per-company loss (e.g., AAPL) | ~33% of concepts |

**Key insight**: A company like Apple has ~133 concepts, of which ~82 don't appear in the canonical set. To render their statements perfectly, we need company-specific metadata.

## Architecture

### Data Flow

```
SEC Filings → EdgarTools → XBRL Parsing → Presentation Trees → Parquet Storage
     ↓                                           ↓
  13K ticker    filing.xbrl().presentation_trees   Per-company records
  companies
```

### Storage Schema

```
presentations.parquet
├── cik: string (primary key)
├── ticker: string
├── name: string
├── form_type: string (10-K, 10-Q)
├── filing_date: date
├── presentations: binary (JSON blob or nested structure)
├── statement_types: list<string>
├── concept_count: int32
├── extracted_at: timestamp
```

**Alternative: Normalized Schema** (for query flexibility)

```
Tables:
├── companies (cik, ticker, name)
├── filings (cik, form_type, filing_date, accession_number)
├── presentations (filing_id, role_uri, definition, root_element)
├── presentation_nodes (presentation_id, element_id, parent_id, depth, order, label)
```

### Storage Estimates

| Companies | Avg Size/Company | Raw Size | Compressed (zstd) |
|-----------|-----------------|----------|-------------------|
| 13,000    | 20-50 KB        | 260-650 MB | 100-200 MB |

**Note**: Most companies have 3-5 statements with standard hierarchies. Complex filers (financial institutions) may have 10+ roles.

## Implementation

### Phase 1: Data Extraction Pipeline

#### 1.1 Company Enumeration

```python
"""
Get all SEC-registered companies with tickers (~13K).
Uses EdgarTools company dataset infrastructure.
"""
from edgar.reference.company_subsets import get_all_companies

def get_ticker_companies() -> list[dict]:
    """
    Get all companies with active tickers.

    Returns ~13,000 companies with columns:
    - cik: SEC Central Index Key
    - ticker: Stock ticker symbol
    - name: Company name
    - exchange: Trading exchange (NYSE, NASDAQ, etc.)
    """
    df = get_all_companies(use_comprehensive=False)

    # Filter to companies with tickers
    df = df[df['ticker'].notna() & (df['ticker'] != '')]

    return df.to_dict('records')
```

#### 1.2 Presentation Extraction

```python
"""
Extract presentation trees from a company's latest 10-K filing.
"""
from edgar import Company
from typing import Optional

def extract_company_presentations(cik: str, form_type: str = "10-K") -> Optional[dict]:
    """
    Extract presentation metadata from a company's latest filing.

    Args:
        cik: SEC Central Index Key
        form_type: Filing type (10-K or 10-Q)

    Returns:
        Dictionary with presentation metadata or None if extraction fails

    Structure:
        {
            'cik': '0000320193',
            'ticker': 'AAPL',
            'name': 'Apple Inc.',
            'form_type': '10-K',
            'filing_date': '2024-11-01',
            'accession_number': '0000320193-24-000123',
            'presentations': {
                'role_uri': {
                    'definition': 'Consolidated Statements of Operations',
                    'root_element': 'IncomeStatementAbstract',
                    'nodes': {
                        'element_id': {
                            'parent': 'parent_id',
                            'children': ['child1', 'child2'],
                            'depth': 1,
                            'order': 1.0,
                            'label': 'Net Sales',
                            'is_abstract': False
                        }
                    }
                }
            },
            'statement_types': ['IncomeStatement', 'BalanceSheet', 'CashFlowStatement'],
            'concept_count': 133,
            'extracted_at': '2024-12-17T10:00:00'
        }
    """
    try:
        company = Company(cik)
        filings = company.get_filings(form=form_type)

        if len(filings) == 0:
            return None

        filing = filings.latest()
        xbrl = filing.xbrl()

        if xbrl is None:
            return None

        # Extract presentation trees
        presentations = {}
        for role_uri, tree in xbrl.presentation_trees.items():
            presentations[role_uri] = tree_to_dict(tree)

        return {
            'cik': cik,
            'ticker': company.tickers[0] if company.tickers else None,
            'name': company.name,
            'form_type': form_type,
            'filing_date': str(filing.filing_date),
            'accession_number': filing.accession_number,
            'presentations': presentations,
            'statement_types': list(set(identify_statement_type(role) for role in presentations.keys())),
            'concept_count': count_unique_concepts(presentations),
            'extracted_at': datetime.now().isoformat()
        }

    except Exception as e:
        log.warning(f"Failed to extract presentations for {cik}: {e}")
        return None


def tree_to_dict(tree) -> dict:
    """Convert PresentationTree to serializable dictionary."""
    return {
        'definition': tree.definition,
        'root_element': tree.root_element_id,
        'nodes': {
            node_id: {
                'parent': node.parent,
                'children': node.children,
                'depth': node.depth,
                'order': getattr(node, 'order', 0),
                'label': getattr(node, 'standard_label', node_id),
                'is_abstract': getattr(node, 'is_abstract', False),
                'preferred_label': getattr(node, 'preferred_label', None)
            }
            for node_id, node in tree.all_nodes.items()
        }
    }


def identify_statement_type(role_uri: str) -> str:
    """Identify statement type from role URI."""
    role_lower = role_uri.lower()

    if 'balance' in role_lower or 'financialposition' in role_lower:
        return 'BalanceSheet'
    elif 'income' in role_lower or 'operations' in role_lower or 'earnings' in role_lower:
        return 'IncomeStatement'
    elif 'cashflow' in role_lower or 'cash_flow' in role_lower:
        return 'CashFlowStatement'
    elif 'equity' in role_lower or 'stockholder' in role_lower:
        return 'StatementOfEquity'
    elif 'comprehensive' in role_lower:
        return 'ComprehensiveIncome'
    else:
        return 'Other'


def count_unique_concepts(presentations: dict) -> int:
    """Count unique concepts across all presentations."""
    concepts = set()
    for role_data in presentations.values():
        concepts.update(role_data.get('nodes', {}).keys())
    return len(concepts)
```

#### 1.3 Batch Processing

```python
"""
Batch extraction with rate limiting and error handling.
"""
import time
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

def batch_extract_presentations(
    companies: list[dict],
    output_dir: Path,
    rate_limit: float = 0.1,  # 10 req/sec
    checkpoint_every: int = 100,
    form_type: str = "10-K"
) -> dict:
    """
    Extract presentations for multiple companies with checkpointing.

    Args:
        companies: List of company dicts with 'cik', 'ticker', 'name'
        output_dir: Directory for outputs and checkpoints
        rate_limit: Seconds between requests (0.1 = 10 req/sec)
        checkpoint_every: Save checkpoint every N companies
        form_type: Filing type to extract

    Returns:
        Summary statistics
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load checkpoint if exists
    checkpoint_file = output_dir / 'checkpoint.json'
    results_file = output_dir / 'presentations_partial.jsonl'

    processed_ciks = set()
    if checkpoint_file.exists():
        checkpoint = json.loads(checkpoint_file.read_text())
        processed_ciks = set(checkpoint.get('processed_ciks', []))
        print(f"Resuming from checkpoint: {len(processed_ciks)} already processed")

    # Filter to unprocessed companies
    remaining = [c for c in companies if c['cik'] not in processed_ciks]

    stats = {
        'total': len(companies),
        'already_processed': len(processed_ciks),
        'remaining': len(remaining),
        'success': 0,
        'failed': 0,
        'no_xbrl': 0,
        'errors': []
    }

    # Process companies with progress bar
    with open(results_file, 'a') as f:
        for i, company in enumerate(tqdm(remaining, desc="Extracting presentations")):
            cik = company['cik']

            try:
                result = extract_company_presentations(cik, form_type)

                if result:
                    f.write(json.dumps(result) + '\n')
                    stats['success'] += 1
                else:
                    stats['no_xbrl'] += 1

            except Exception as e:
                stats['failed'] += 1
                stats['errors'].append({'cik': cik, 'error': str(e)})

            processed_ciks.add(cik)

            # Checkpoint
            if (i + 1) % checkpoint_every == 0:
                checkpoint_file.write_text(json.dumps({
                    'processed_ciks': list(processed_ciks),
                    'timestamp': datetime.now().isoformat(),
                    'stats': stats
                }))

            # Rate limiting
            time.sleep(rate_limit)

    # Final checkpoint
    checkpoint_file.write_text(json.dumps({
        'processed_ciks': list(processed_ciks),
        'completed': True,
        'timestamp': datetime.now().isoformat(),
        'stats': stats
    }))

    return stats
```

### Phase 2: Storage Layer

#### 2.1 Parquet Storage (Recommended)

```python
"""
Build Parquet file from extracted presentations.
Follows the pattern from edgar/reference/company_dataset.py.
"""
import pyarrow as pa
import pyarrow.parquet as pq
import json
from pathlib import Path

# Schema definition
PRESENTATION_SCHEMA = pa.schema([
    ('cik', pa.string()),
    ('ticker', pa.string()),
    ('name', pa.string()),
    ('form_type', pa.string()),
    ('filing_date', pa.date32()),
    ('accession_number', pa.string()),
    ('presentations_json', pa.large_string()),  # JSON blob
    ('statement_types', pa.list_(pa.string())),
    ('concept_count', pa.int32()),
    ('extracted_at', pa.timestamp('us'))
])


def build_presentations_parquet(
    jsonl_path: Path,
    output_path: Path,
    compression: str = 'zstd',
    compression_level: int = 9
) -> pa.Table:
    """
    Build Parquet file from JSONL extraction results.

    Args:
        jsonl_path: Path to JSONL file from batch extraction
        output_path: Where to save Parquet file
        compression: Compression algorithm (zstd recommended)
        compression_level: Compression level (1-22 for zstd)

    Returns:
        PyArrow Table
    """
    records = []

    with open(jsonl_path) as f:
        for line in f:
            data = json.loads(line)

            records.append({
                'cik': data['cik'],
                'ticker': data['ticker'],
                'name': data['name'],
                'form_type': data['form_type'],
                'filing_date': data['filing_date'],
                'accession_number': data['accession_number'],
                'presentations_json': json.dumps(data['presentations']),
                'statement_types': data['statement_types'],
                'concept_count': data['concept_count'],
                'extracted_at': data['extracted_at']
            })

    # Create table
    table = pa.Table.from_pylist(records, schema=PRESENTATION_SCHEMA)

    # Write with compression
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        table,
        output_path,
        compression=compression,
        compression_level=compression_level,
        use_dictionary=True
    )

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Saved: {output_path} ({size_mb:.1f} MB, {len(records)} companies)")

    return table
```

#### 2.2 Query API

```python
"""
Query API for presentation metadata.
"""
import pyarrow.parquet as pq
import pyarrow.compute as pc
import json
from typing import Optional
from functools import lru_cache

# Cache for loaded table
_PRESENTATIONS_CACHE = {}


def get_presentations_table(
    parquet_path: Path = Path.home() / '.edgar' / 'presentations.pq'
) -> pa.Table:
    """Load presentations table with caching."""
    if str(parquet_path) not in _PRESENTATIONS_CACHE:
        _PRESENTATIONS_CACHE[str(parquet_path)] = pq.read_table(parquet_path)
    return _PRESENTATIONS_CACHE[str(parquet_path)]


def get_company_presentations(
    cik: str,
    parquet_path: Optional[Path] = None
) -> Optional[dict]:
    """
    Get presentation metadata for a specific company.

    Args:
        cik: SEC Central Index Key
        parquet_path: Optional custom path to Parquet file

    Returns:
        Dictionary with presentation metadata or None if not found
    """
    table = get_presentations_table(parquet_path) if parquet_path else get_presentations_table()

    # Filter by CIK
    filtered = table.filter(pc.equal(pc.field('cik'), cik))

    if len(filtered) == 0:
        return None

    # Get first row (should be only one per company)
    row = filtered.to_pydict()

    return {
        'cik': row['cik'][0],
        'ticker': row['ticker'][0],
        'name': row['name'][0],
        'form_type': row['form_type'][0],
        'filing_date': row['filing_date'][0],
        'accession_number': row['accession_number'][0],
        'presentations': json.loads(row['presentations_json'][0]),
        'statement_types': row['statement_types'][0],
        'concept_count': row['concept_count'][0]
    }


def get_concepts_for_statement(
    cik: str,
    statement_type: str
) -> list[dict]:
    """
    Get all concepts for a specific statement type.

    Args:
        cik: Company CIK
        statement_type: Statement type (IncomeStatement, BalanceSheet, etc.)

    Returns:
        List of concept dictionaries with hierarchy info
    """
    data = get_company_presentations(cik)
    if not data:
        return []

    concepts = []
    for role_uri, presentation in data['presentations'].items():
        if identify_statement_type(role_uri) == statement_type:
            for concept_id, node in presentation['nodes'].items():
                concepts.append({
                    'concept': concept_id,
                    'label': node.get('label', concept_id),
                    'parent': node.get('parent'),
                    'depth': node.get('depth', 0),
                    'order': node.get('order', 0),
                    'is_abstract': node.get('is_abstract', False)
                })

    return sorted(concepts, key=lambda x: (x['depth'], x['order']))


def search_companies_by_concept(
    concept_name: str,
    parquet_path: Optional[Path] = None
) -> list[dict]:
    """
    Find all companies that use a specific concept.

    Args:
        concept_name: XBRL concept name (partial match)

    Returns:
        List of companies using this concept
    """
    table = get_presentations_table(parquet_path) if parquet_path else get_presentations_table()

    results = []
    for row in table.to_pydict():
        presentations = json.loads(row['presentations_json'][0])

        for role_uri, presentation in presentations.items():
            if any(concept_name.lower() in node_id.lower()
                   for node_id in presentation.get('nodes', {}).keys()):
                results.append({
                    'cik': row['cik'][0],
                    'ticker': row['ticker'][0],
                    'name': row['name'][0]
                })
                break

    return results
```

### Phase 3: Incremental Updates

```python
"""
Incremental update strategy for new filings.
"""
from datetime import date, timedelta

def get_new_filings_since(
    last_update: date,
    form_types: list[str] = ['10-K', '10-Q']
) -> list[dict]:
    """
    Get new filings since last update.

    Args:
        last_update: Date of last database update
        form_types: Filing types to check

    Returns:
        List of new filings to process
    """
    from edgar import get_filings

    new_filings = []

    for form_type in form_types:
        filings = get_filings(form=form_type)
        recent = [f for f in filings if f.filing_date > last_update]
        new_filings.extend(recent)

    return new_filings


def update_presentations_database(
    parquet_path: Path,
    new_filings: list
) -> dict:
    """
    Update database with new filings.

    Returns updated statistics.
    """
    # Load existing
    table = pq.read_table(parquet_path)
    existing_ciks = set(table.column('cik').to_pylist())

    # Extract new presentations
    updates = []
    for filing in new_filings:
        if filing.company.cik not in existing_ciks:
            result = extract_company_presentations(filing.company.cik)
            if result:
                updates.append(result)

    if not updates:
        return {'updated': 0, 'total': len(table)}

    # Merge and rewrite
    # (In practice, you'd use append or merge logic)
    all_records = table.to_pylist() + updates
    new_table = pa.Table.from_pylist(all_records, schema=PRESENTATION_SCHEMA)

    pq.write_table(new_table, parquet_path, compression='zstd')

    return {
        'updated': len(updates),
        'total': len(new_table)
    }
```

## EdgarTools Infrastructure Reference

### Reusable Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `company_dataset.py` | `edgar/reference/` | Parquet building pattern (30s for 562K records) |
| `PresentationParser` | `edgar/xbrl/parsers/presentation.py` | XBRL presentation linkbase parsing |
| `CompanySubset` | `edgar/reference/company_subsets.py` | Flexible company enumeration |
| `get_all_companies()` | `edgar/reference/company_subsets.py` | Get all companies with tickers |
| `PresentationTree` | `edgar/xbrl/models.py` | Presentation tree data model |

### Key Patterns from EdgarTools

**1. Parquet with Compression** (`company_dataset.py:240-248`)
```python
pq.write_table(
    table,
    output_path,
    compression='zstd',
    compression_level=9,
    use_dictionary=True
)
```

**2. In-Memory Caching** (`company_dataset.py:522-527`)
```python
_CACHE = {}

def get_data(rebuild=False):
    if not rebuild and 'key' in _CACHE:
        return _CACHE['key']
    # ... load data ...
    _CACHE['key'] = data
    return data
```

**3. Progress Tracking** (`company_dataset.py:187`)
```python
from tqdm import tqdm
iterator = tqdm(items, desc="Processing")
for item in iterator:
    # process
```

## Cost Estimates

| Factor | Estimate | Notes |
|--------|----------|-------|
| **Companies** | ~13,000 | Companies with active tickers |
| **Build time** | 10-20 hours | 5 seconds/company average |
| **API requests** | ~13,000 | One filing per company |
| **Raw data size** | 260-650 MB | Before compression |
| **Compressed size** | 100-200 MB | zstd level 9 |
| **Daily updates** | ~50-100 | New 10-K/10-Q filings per day |
| **Update time** | ~5 minutes | Per daily update |

### Parallelization Options

```python
# With ThreadPoolExecutor (respects rate limits)
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def parallel_extract(companies, max_workers=5, rate_limit=0.5):
    """
    Parallel extraction with rate limiting.

    Note: SEC has implicit rate limits (~10 req/sec per user agent).
    Be conservative with max_workers to avoid blocks.
    """
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}

        for company in companies:
            future = executor.submit(extract_company_presentations, company['cik'])
            futures[future] = company
            time.sleep(rate_limit / max_workers)  # Distribute rate limit

        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    return results
```

## Challenges & Mitigations

| Challenge | Impact | Mitigation |
|-----------|--------|-----------|
| **SEC Rate Limiting** | Blocked requests | Conservative rate limit (10 req/sec), exponential backoff |
| **XBRL Parsing Failures** | ~5-10% of filings | Robust error handling, skip and log failures |
| **Varied Taxonomies** | Different concept names | Store raw concept IDs, build mapping layer separately |
| **Historical Gaps** | Pre-2009 no XBRL | Start with recent filings, add historical as needed |
| **Storage Growth** | New filings daily | Incremental update pipeline, periodic compaction |
| **Memory Pressure** | Large presentations | Stream processing, batch writes |

## Quality Validation

```python
def validate_presentations_database(parquet_path: Path) -> dict:
    """
    Validate the presentations database.

    Returns validation report.
    """
    table = pq.read_table(parquet_path)

    # Basic statistics
    total = len(table)
    unique_ciks = len(set(table.column('cik').to_pylist()))

    # Check for completeness
    missing_tickers = sum(1 for t in table.column('ticker').to_pylist() if not t)
    empty_presentations = sum(
        1 for p in table.column('presentations_json').to_pylist()
        if not json.loads(p)
    )

    # Check concept counts
    concept_counts = table.column('concept_count').to_pylist()
    avg_concepts = sum(concept_counts) / len(concept_counts) if concept_counts else 0

    return {
        'total_records': total,
        'unique_companies': unique_ciks,
        'missing_tickers': missing_tickers,
        'empty_presentations': empty_presentations,
        'avg_concepts_per_company': round(avg_concepts, 1),
        'min_concepts': min(concept_counts) if concept_counts else 0,
        'max_concepts': max(concept_counts) if concept_counts else 0,
        'file_size_mb': parquet_path.stat().st_size / (1024 * 1024)
    }
```

## Usage Example: Complete Pipeline

```python
"""
Complete pipeline to build per-company presentations database.
"""
from pathlib import Path

# Configuration
OUTPUT_DIR = Path('./presentations_output')
PARQUET_PATH = OUTPUT_DIR / 'presentations.pq'

# Step 1: Get companies
print("Getting ticker companies...")
companies = get_ticker_companies()
print(f"Found {len(companies)} companies with tickers")

# Step 2: Extract presentations (with checkpointing)
print("Extracting presentations...")
stats = batch_extract_presentations(
    companies=companies,
    output_dir=OUTPUT_DIR,
    rate_limit=0.1,  # 10 req/sec
    checkpoint_every=100
)
print(f"Extraction complete: {stats['success']} succeeded, {stats['failed']} failed")

# Step 3: Build Parquet file
print("Building Parquet file...")
jsonl_path = OUTPUT_DIR / 'presentations_partial.jsonl'
table = build_presentations_parquet(jsonl_path, PARQUET_PATH)

# Step 4: Validate
print("Validating database...")
validation = validate_presentations_database(PARQUET_PATH)
print(f"Validation: {validation}")

# Done!
print(f"\nDatabase ready: {PARQUET_PATH}")
print(f"Companies: {validation['total_records']}")
print(f"Size: {validation['file_size_mb']:.1f} MB")
```

## Related Documentation

- [EdgarTools Training Guide](./GUIDE.md) - Canonical concept learning
- [Company Dataset Builder](../../reference/company_dataset.py) - Parquet pattern reference
- [XBRL Presentation Parser](../../xbrl/parsers/presentation.py) - Parser implementation
- [Company Subsets](../../reference/company_subsets.py) - Company enumeration
