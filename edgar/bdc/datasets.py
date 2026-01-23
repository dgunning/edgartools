"""
SEC BDC Data Sets from DERA (Division of Economic and Risk Analysis).

This module provides access to the SEC's pre-extracted BDC data sets,
which contain quarterly snapshots of XBRL data from BDC filings.

Data source: https://www.sec.gov/data-research/sec-markets-data/bdc-data-sets

The data sets include:
- sub.txt: Submission metadata (adsh, cik, name, form, filed, etc.)
- num.txt: Numeric XBRL facts (adsh, tag, value, uom, etc.)
- pre.txt: Presentation linkbase data (adsh, stmt, line, tag, etc.)
- soi.txt: Schedule of Investments data (adsh, company, industry, fair_value, etc.)

Example usage:
    >>> from edgar.bdc import fetch_bdc_dataset, get_available_quarters
    >>>
    >>> # List available quarters
    >>> quarters = get_available_quarters()
    >>> print(quarters)
    [(2024, 3), (2024, 2), (2024, 1), ...]
    >>>
    >>> # Fetch a specific quarter
    >>> dataset = fetch_bdc_dataset(2024, 3)
    >>> print(dataset)
    BDCDataset(2024Q3): 45 submissions, 12,450 facts, 3,200 SOI entries
    >>>
    >>> # Access individual DataFrames
    >>> dataset.submissions  # Submission metadata
    >>> dataset.numbers      # Numeric facts
    >>> dataset.soi          # Schedule of Investments
    >>>
    >>> # Bulk analysis
    >>> soi_df = dataset.soi
    >>> soi_df.groupby('industry')['fair_value'].sum()
"""
import io
import zipfile
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from edgar.bdc.reference import BDCEntity

import pandas as pd
from rich import box
from rich.panel import Panel
from rich.table import Table

from edgar.httprequests import get_with_retry
from edgar.richtools import repr_rich

__all__ = [
    'BDCDataset',
    'ScheduleOfInvestmentsData',
    'fetch_bdc_dataset',
    'fetch_bdc_dataset_monthly',
    'get_available_quarters',
    'list_bdc_datasets',
]

# Base URL for SEC BDC Data Sets
BDC_DATASET_BASE_URL = "https://www.sec.gov/files/structureddata/data/business-development-company-bdc-data-sets"

# Column name mappings for cleaner output
_COLUMN_RENAMES = {
    # Axis columns - remove "Axis" suffix and simplify
    'Industry Sector Axis': 'industry',
    'Investment, Identifier Axis': 'investment_id',
    'Investment, Issuer Affiliation Axis': 'affiliation',
    'Investment Type Axis': 'investment_type',
    'Investment, Issuer Name Axis': 'company',
    'Investment, Name Axis': 'investment_name',
    'Fair Value Hierarchy and NAV Axis': 'fair_value_level',
    'Financial Instrument Axis': 'instrument_type',
    'Valuation Approach and Technique Axis': 'valuation_method',
    'Segments Axis': 'segment',
    'Consolidation Items Axis': 'consolidation',
    'Investment Company, Nonconsolidated Subsidiary Axis': 'subsidiary',
    'Lien Category Axis': 'lien_category',
    'Asset Class Axis': 'asset_class',
    # Value columns - simplify names
    'Investment Interest Rate': 'interest_rate',
    'Investment, Basis Spread, Variable Rate': 'spread',
    'Investment Maturity Date': 'maturity_date',
    'Investment Owned, Balance, Principal Amount': 'principal',
    'Investment Owned, Cost': 'cost',
    'Investment Owned, Fair Value': 'fair_value',
    'Investment Owned, Net Assets, Percentage': 'pct_net_assets',
    'Investment Owned, Balance, Shares': 'shares',
    'Investment, Interest Rate, Paid in Kind': 'pik_rate',
    'Investment, Acquisition Date': 'acquisition_date',
    # Metadata
    'ddate': 'data_date',
    'inlineurl': 'filing_url',
}


def _clean_soi_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean up SOI DataFrame column names and values.

    - Renames columns to simpler names
    - Removes "[Member]" suffix from axis values
    - Removes " Axis" suffix from any unmapped axis columns
    """
    if df.empty:
        return df

    # Rename known columns
    df = df.rename(columns=_COLUMN_RENAMES)

    # For any remaining Axis columns, strip the " Axis" suffix
    new_cols = {}
    for col in df.columns:
        if col.endswith(' Axis'):
            # Convert "Some Thing Axis" to "some_thing"
            new_name = col.replace(' Axis', '').lower().replace(', ', '_').replace(' ', '_')
            new_cols[col] = new_name
    if new_cols:
        df = df.rename(columns=new_cols)

    # Clean up values in object/string columns - remove "[Member]" suffix
    # Use pd.api.types for pandas 2.x/3.x compatibility
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            df[col] = df[col].apply(
                lambda x: x.replace(' [Member]', '').strip() if isinstance(x, str) and '[Member]' in x else x
            )

    return df


class ScheduleOfInvestmentsData:
    """
    Wrapper for Schedule of Investments data from SEC DERA BDC Data Sets.

    Provides convenient access to SOI data with subsetting by CIK.

    Example:
        >>> dataset = fetch_bdc_dataset(2024, 4)
        >>> soi = dataset.schedule_of_investments
        >>>
        >>> # Get all data
        >>> len(soi)
        113124
        >>>
        >>> # Subset by CIK
        >>> arcc_soi = soi[1287750]
        >>> len(arcc_soi)
        1256
        >>>
        >>> # Get unique companies
        >>> soi.ciks
        [1287750, 1396440, ...]
        >>>
        >>> # Convert to DataFrame
        >>> df = soi.to_dataframe()
    """

    def __init__(self, data: pd.DataFrame, drop_empty: bool = True):
        if drop_empty and not data.empty:
            # Drop columns that are entirely empty (all NaN/None)
            self._data = data.dropna(axis=1, how='all')
        else:
            self._data = data

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, key: Union[int, 'BDCEntity']) -> 'ScheduleOfInvestmentsData':
        """
        Get SOI entries for a specific CIK or BDCEntity.

        Args:
            key: Either a CIK number (int) or a BDCEntity instance

        Returns:
            ScheduleOfInvestmentsData filtered to that CIK

        Example:
            >>> soi = dataset.schedule_of_investments
            >>> arcc_soi = soi[1287750]  # Get by CIK
            >>>
            >>> # Or use BDCEntity
            >>> arcc = get_bdc_list().get_by_ticker("ARCC")
            >>> arcc_soi = soi[arcc]  # Get by BDCEntity
        """
        # Handle BDCEntity by extracting its CIK
        if hasattr(key, 'cik'):
            cik = key.cik
        else:
            cik = key

        if 'cik' not in self._data.columns:
            return ScheduleOfInvestmentsData(pd.DataFrame())
        filtered = self._data[self._data['cik'] == cik].copy()
        return ScheduleOfInvestmentsData(filtered)

    def __iter__(self):
        return iter(self._data.itertuples(index=False))

    @property
    def empty(self) -> bool:
        """Check if the data is empty."""
        return self._data.empty

    @property
    def ciks(self) -> list[int]:
        """Get list of unique CIKs in the data."""
        if 'cik' not in self._data.columns or self._data.empty:
            return []
        return sorted(self._data['cik'].unique().tolist())

    @property
    def num_companies(self) -> int:
        """Number of unique companies in the data."""
        return len(self.ciks)

    @property
    def columns(self) -> list[str]:
        """Get column names."""
        return list(self._data.columns)

    def to_dataframe(self, clean: bool = False) -> pd.DataFrame:
        """
        Return the underlying DataFrame.

        Args:
            clean: If True, clean up column names and values for easier use.
                   Removes "Axis" suffix, "[Member]" suffix, and simplifies names.

        Returns:
            DataFrame with SOI data
        """
        if not clean:
            return self._data.copy()
        return _clean_soi_dataframe(self._data.copy())

    def filter(self, **kwargs) -> 'ScheduleOfInvestmentsData':
        """
        Filter SOI data by column values.

        Args:
            **kwargs: Column name and value pairs to filter by

        Returns:
            Filtered ScheduleOfInvestmentsData

        Example:
            >>> soi.filter(form='10-K')
            >>> soi.filter(cik=1287750, form='10-K')
        """
        filtered = self._data.copy()
        for col, value in kwargs.items():
            if col in filtered.columns:
                filtered = filtered[filtered[col] == value]
        return ScheduleOfInvestmentsData(filtered)

    def head(self, n: int = 5) -> pd.DataFrame:
        """Return first n rows as DataFrame."""
        return self._data.head(n)

    def _get_company_column(self) -> Optional[str]:
        """Find the column containing portfolio company names."""
        for col in ['company', 'Investment, Issuer Name Axis']:
            if col in self._data.columns:
                return col
        return None

    def _get_fair_value_column(self) -> Optional[str]:
        """Find the column containing fair value."""
        for col in ['fair_value', 'Investment Owned, Fair Value']:
            if col in self._data.columns:
                return col
        return None

    def search(self, query: str, top_n: int = 20) -> pd.DataFrame:
        """
        Search for portfolio companies across all BDCs.

        Find which BDCs hold investments matching the search query.
        This enables cross-BDC analysis like "Which BDCs hold Ivy Hill?"

        Args:
            query: Search string to match against company names (case-insensitive)
            top_n: Maximum number of results to return (default: 20)

        Returns:
            DataFrame with columns: company, bdc_name, bdc_cik, fair_value, form

        Example:
            >>> dataset = fetch_bdc_dataset(2024, 3)
            >>> soi = dataset.schedule_of_investments
            >>>
            >>> # Find all BDCs holding "Ivy Hill"
            >>> soi.search("Ivy Hill")
                                    company           bdc_name   bdc_cik    fair_value
            0  Ivy Hill Asset Management, L.P.  ARES CAPITAL CORP  1287750  1915300000.0
            >>>
            >>> # Search for software companies
            >>> soi.search("software")
        """
        if self._data.empty:
            return pd.DataFrame()

        company_col = self._get_company_column()
        if company_col is None:
            return pd.DataFrame()

        # Filter by query
        mask = self._data[company_col].str.contains(query, case=False, na=False)
        matches = self._data[mask].copy()

        if matches.empty:
            return pd.DataFrame()

        # Build result DataFrame
        fair_value_col = self._get_fair_value_column()

        result_data = []
        for _, row in matches.iterrows():
            company_name = row[company_col]
            # Clean up [Member] suffix
            if isinstance(company_name, str) and '[Member]' in company_name:
                company_name = company_name.replace(' [Member]', '').strip()

            entry = {
                'company': company_name,
                'bdc_name': row.get('name', ''),
                'bdc_cik': row.get('cik', 0),
                'form': row.get('form', ''),
            }
            if fair_value_col:
                entry['fair_value'] = row.get(fair_value_col, 0)

            result_data.append(entry)

        result = pd.DataFrame(result_data)

        # Sort by fair value if available, otherwise by company name
        if 'fair_value' in result.columns:
            result = result.sort_values('fair_value', ascending=False)
        else:
            result = result.sort_values('company')

        return result.head(top_n).reset_index(drop=True)

    def top_companies(self, n: int = 25) -> pd.DataFrame:
        """
        Get the most commonly held portfolio companies across all BDCs.

        Aggregates holdings across all BDCs to find companies that appear
        in multiple BDC portfolios, indicating broad private credit exposure.

        Args:
            n: Number of top companies to return (default: 25)

        Returns:
            DataFrame with columns: company, num_bdcs, total_fair_value, bdc_names

        Example:
            >>> dataset = fetch_bdc_dataset(2024, 3)
            >>> soi = dataset.schedule_of_investments
            >>>
            >>> # Most commonly held private companies
            >>> soi.top_companies(10)
                                 company  num_bdcs  total_fair_value                    bdc_names
            0       Ivy Hill Asset Mgmt         1      1915300000.0           ARES CAPITAL CORP
            1          ABC Software LLC         3       850000000.0  ARES CAPITAL, MAIN STREET...
        """
        if self._data.empty:
            return pd.DataFrame()

        company_col = self._get_company_column()
        if company_col is None:
            return pd.DataFrame()

        fair_value_col = self._get_fair_value_column()

        # Group by company
        grouped_data = []
        for company, group in self._data.groupby(company_col):
            if pd.isna(company):
                continue

            # Clean company name
            company_name = company
            if isinstance(company_name, str) and '[Member]' in company_name:
                company_name = company_name.replace(' [Member]', '').strip()

            # Get unique BDCs holding this company
            bdc_names = group['name'].dropna().unique().tolist() if 'name' in group.columns else []

            entry = {
                'company': company_name,
                'num_bdcs': len(bdc_names),
                'bdc_names': ', '.join(sorted(bdc_names)[:3]) + ('...' if len(bdc_names) > 3 else ''),
            }

            if fair_value_col and fair_value_col in group.columns:
                entry['total_fair_value'] = group[fair_value_col].sum()

            grouped_data.append(entry)

        if not grouped_data:
            return pd.DataFrame()

        result = pd.DataFrame(grouped_data)

        # Sort by number of BDCs holding, then by total fair value
        sort_cols = ['num_bdcs']
        if 'total_fair_value' in result.columns:
            sort_cols.append('total_fair_value')
        result = result.sort_values(sort_cols, ascending=False)

        return result.head(n).reset_index(drop=True)

    def __rich__(self):
        """Rich display for the SOI data."""
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Entries", f"{len(self):,}")
        table.add_row("Companies", f"{self.num_companies:,}")

        if not self._data.empty:
            table.add_row("", "")
            table.add_row("Columns", ", ".join(self.columns[:5]))
            if len(self.columns) > 5:
                table.add_row("", f"  ... +{len(self.columns) - 5} more")

        return Panel(
            table,
            title="[bold]Schedule of Investments Data[/bold]",
            border_style="cyan",
            width=55
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


@dataclass
class BDCDataset:
    """
    A quarterly BDC data set from SEC DERA.

    Contains pre-extracted XBRL data from all BDC filings for a given quarter.

    Attributes:
        year: The year of the data set
        quarter: The quarter (1-4)
        submissions: DataFrame of filing submissions (sub.txt)
        numbers: DataFrame of numeric facts (num.txt)
        presentation: DataFrame of presentation data (pre.txt)
        soi: DataFrame of Schedule of Investments data (soi.txt)
    """
    year: int
    quarter: int
    submissions: pd.DataFrame
    numbers: pd.DataFrame
    presentation: pd.DataFrame
    soi: pd.DataFrame

    @property
    def period(self) -> str:
        """Return period string like '2024Q3'."""
        return f"{self.year}Q{self.quarter}"

    @property
    def num_submissions(self) -> int:
        """Number of unique submissions in the dataset."""
        return self.submissions['adsh'].nunique() if not self.submissions.empty else 0

    @property
    def num_facts(self) -> int:
        """Number of numeric facts in the dataset."""
        return len(self.numbers)

    @property
    def num_soi_entries(self) -> int:
        """Number of Schedule of Investments entries."""
        return len(self.soi)

    @property
    def num_companies(self) -> int:
        """Number of unique BDC companies in the dataset."""
        return self.submissions['cik'].nunique() if not self.submissions.empty else 0

    @property
    def schedule_of_investments(self) -> ScheduleOfInvestmentsData:
        """
        Get Schedule of Investments data as a wrapped object.

        Returns a ScheduleOfInvestmentsData object that provides convenient
        access to SOI data with subsetting by CIK.

        Returns:
            ScheduleOfInvestmentsData wrapper

        Example:
            >>> dataset = fetch_bdc_dataset(2024, 4)
            >>> soi = dataset.schedule_of_investments
            >>> len(soi)
            113124
            >>>
            >>> # Get ARCC's SOI entries
            >>> arcc_soi = soi[1287750]
            >>> len(arcc_soi)
            1256
        """
        return ScheduleOfInvestmentsData(self.soi)

    def get_submission(self, adsh: str) -> Optional[pd.Series]:
        """
        Get submission metadata for a specific accession number.

        Args:
            adsh: The accession number (e.g., '0001193125-24-123456')

        Returns:
            Series with submission metadata, or None if not found
        """
        matches = self.submissions[self.submissions['adsh'] == adsh]
        if len(matches) > 0:
            return matches.iloc[0]
        return None

    def get_facts_for_submission(self, adsh: str) -> pd.DataFrame:
        """
        Get all numeric facts for a specific submission.

        Args:
            adsh: The accession number

        Returns:
            DataFrame of numeric facts for the submission
        """
        return self.numbers[self.numbers['adsh'] == adsh].copy()

    def get_soi_for_submission(self, adsh: str) -> pd.DataFrame:
        """
        Get Schedule of Investments entries for a specific submission.

        Args:
            adsh: The accession number

        Returns:
            DataFrame of SOI entries for the submission
        """
        return self.soi[self.soi['adsh'] == adsh].copy()

    def get_soi_for_cik(self, cik: int) -> pd.DataFrame:
        """
        Get Schedule of Investments entries for a specific company (CIK).

        Args:
            cik: The company CIK number

        Returns:
            DataFrame of SOI entries for all filings by that company
        """
        # Get all adsh values for this CIK
        adsh_values = self.submissions[self.submissions['cik'] == cik]['adsh'].tolist()
        return self.soi[self.soi['adsh'].isin(adsh_values)].copy()

    def get_facts_by_tag(self, tag: str) -> pd.DataFrame:
        """
        Get all facts for a specific XBRL tag across all submissions.

        Args:
            tag: The XBRL tag name (e.g., 'InvestmentOwnedAtFairValue')

        Returns:
            DataFrame of facts with that tag
        """
        return self.numbers[self.numbers['tag'] == tag].copy()

    def summary_by_company(self) -> pd.DataFrame:
        """
        Get a summary of SOI data aggregated by company.

        Returns:
            DataFrame with columns: cik, name, form, filed, num_investments
        """
        if self.soi.empty:
            return pd.DataFrame()

        # SOI data already contains cik, name, form, filed columns
        required_cols = ['cik', 'name', 'form', 'filed', 'adsh']
        if not all(col in self.soi.columns for col in required_cols):
            return pd.DataFrame()

        # Aggregate by company
        summary = self.soi.groupby(['cik', 'name']).agg({
            'form': 'first',
            'filed': 'max',
            'adsh': 'count',  # Count of SOI entries
        }).reset_index()

        summary.columns = ['cik', 'name', 'form', 'filed', 'num_investments']
        return summary.sort_values('num_investments', ascending=False)

    def summary_by_industry(self) -> pd.DataFrame:
        """
        Get a summary of SOI data aggregated by industry.

        Returns:
            DataFrame with industry-level aggregations
        """
        if self.soi.empty:
            return pd.DataFrame()

        # Find the industry column (may be named differently)
        industry_col = None
        for col in ['industry', 'Industry Sector Axis']:
            if col in self.soi.columns:
                industry_col = col
                break

        if industry_col is None:
            return pd.DataFrame()

        # Find the fair value column
        fair_value_col = None
        for col in ['fair_value', 'Investment Owned, Fair Value']:
            if col in self.soi.columns:
                fair_value_col = col
                break

        if fair_value_col:
            result = self.soi.groupby(industry_col).agg({
                'adsh': 'count',
                fair_value_col: 'sum'
            }).reset_index().rename(columns={
                industry_col: 'industry',
                'adsh': 'num_investments',
                fair_value_col: 'total_fair_value'
            }).sort_values('total_fair_value', ascending=False)
            return result
        else:
            result = self.soi.groupby(industry_col).size().reset_index(name='num_investments')
            result = result.rename(columns={industry_col: 'industry'})
            return result

    def __rich__(self):
        """Rich display for the dataset."""
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Period", self.period)
        table.add_row("Companies", f"{self.num_companies:,}")
        table.add_row("Submissions", f"{self.num_submissions:,}")
        table.add_row("Numeric Facts", f"{self.num_facts:,}")
        table.add_row("SOI Entries", f"{self.num_soi_entries:,}")

        # Show available columns in SOI
        if not self.soi.empty:
            table.add_row("", "")
            table.add_row("SOI Columns", ", ".join(self.soi.columns[:5]))
            if len(self.soi.columns) > 5:
                table.add_row("", f"  ... +{len(self.soi.columns) - 5} more")

        return Panel(
            table,
            title=f"[bold]BDC Dataset {self.period}[/bold]",
            border_style="blue",
            width=60
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


def _build_quarterly_url(year: int, quarter: int) -> str:
    """Build the URL for a quarterly BDC dataset ZIP file."""
    return f"{BDC_DATASET_BASE_URL}/{year}q{quarter}_bdc.zip"


def _build_monthly_url(year: int, month: int) -> str:
    """Build the URL for a monthly BDC dataset ZIP file."""
    return f"{BDC_DATASET_BASE_URL}/{year}_{month:02d}_bdc.zip"


def _parse_tsv_from_zip(zip_content: bytes, filename: str) -> pd.DataFrame:
    """
    Parse a TSV file from a ZIP archive.

    Args:
        zip_content: The raw ZIP file content
        filename: The name of the file to extract (e.g., 'sub.tsv' or 'soi.tsv')

    Returns:
        DataFrame with the parsed data, or empty DataFrame if file not found
    """
    try:
        with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
            # Files may be in 'datasets/' subdirectory or at root
            # Try multiple possible paths
            possible_paths = [
                filename,
                f"datasets/{filename}",
                f"datasets\\{filename}",  # Windows-style path
            ]

            for path in possible_paths:
                if path in z.namelist():
                    with z.open(path) as f:
                        # Read as TSV (tab-separated values)
                        df = pd.read_csv(f, sep='\t', low_memory=False)
                        return df

            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def fetch_bdc_dataset(year: int, quarter: int) -> BDCDataset:
    """
    Fetch a BDC data set from SEC DERA.

    Downloads and parses the quarterly BDC data set containing:
    - Submission metadata (sub.txt)
    - Numeric XBRL facts (num.txt)
    - Presentation data (pre.txt)
    - Schedule of Investments (soi.txt)

    Args:
        year: The year (e.g., 2024)
        quarter: The quarter (1, 2, 3, or 4)

    Returns:
        BDCDataset containing all parsed data

    Raises:
        ValueError: If the quarter is invalid
        httpx.HTTPError: If the download fails

    Example:
        >>> dataset = fetch_bdc_dataset(2024, 3)
        >>> print(f"Found {dataset.num_submissions} submissions")
        Found 45 submissions
        >>>
        >>> # Analyze SOI data
        >>> soi = dataset.soi
        >>> print(soi.groupby('industry')['fair_value'].sum().head())
    """
    if quarter not in (1, 2, 3, 4):
        raise ValueError(f"Quarter must be 1, 2, 3, or 4, got {quarter}")

    url = _build_quarterly_url(year, quarter)

    # Download the ZIP file
    response = get_with_retry(url)
    response.raise_for_status()

    zip_content = response.content

    # Parse each file from the ZIP
    # Note: Files use .tsv extension and may be in 'datasets/' subdirectory
    submissions = _parse_tsv_from_zip(zip_content, 'sub.tsv')
    numbers = _parse_tsv_from_zip(zip_content, 'num.tsv')
    presentation = _parse_tsv_from_zip(zip_content, 'pre.tsv')
    soi = _parse_tsv_from_zip(zip_content, 'soi.tsv')

    # Convert date columns if present
    if 'filed' in submissions.columns:
        submissions['filed'] = pd.to_datetime(submissions['filed'], errors='coerce')
    if 'period' in submissions.columns:
        submissions['period'] = pd.to_datetime(submissions['period'], errors='coerce')

    return BDCDataset(
        year=year,
        quarter=quarter,
        submissions=submissions,
        numbers=numbers,
        presentation=presentation,
        soi=soi,
    )


@lru_cache(maxsize=1)
def get_available_quarters(max_years_back: int = 5) -> list[tuple[int, int]]:
    """
    Get list of available BDC data set quarters.

    Probes the SEC server to find which quarterly data sets are available.
    Results are cached for performance.

    Args:
        max_years_back: Maximum number of years to look back (default: 5)

    Returns:
        List of (year, quarter) tuples in descending order (most recent first)

    Example:
        >>> quarters = get_available_quarters()
        >>> print(quarters[:4])
        [(2024, 3), (2024, 2), (2024, 1), (2023, 4)]
    """
    available = []
    current_year = date.today().year

    for year in range(current_year, current_year - max_years_back, -1):
        for quarter in range(4, 0, -1):
            url = _build_quarterly_url(year, quarter)
            try:
                response = get_with_retry(url, timeout=5.0)
                if response.status_code == 200:
                    available.append((year, quarter))
            except Exception:
                continue

    return available


def list_bdc_datasets(max_years_back: int = 3) -> pd.DataFrame:
    """
    List available BDC data sets with metadata.

    Args:
        max_years_back: Maximum number of years to look back (default: 3)

    Returns:
        DataFrame with columns: year, quarter, period, url

    Example:
        >>> df = list_bdc_datasets()
        >>> print(df)
           year  quarter  period                                              url
        0  2024        4  2024Q4  https://www.sec.gov/files/structureddata/data/...
        1  2024        3  2024Q3  https://www.sec.gov/files/structureddata/data/...
    """
    quarters = get_available_quarters(max_years_back)

    data = []
    for year, quarter in quarters:
        data.append({
            'year': year,
            'quarter': quarter,
            'period': f"{year}Q{quarter}",
            'url': _build_quarterly_url(year, quarter),
        })

    return pd.DataFrame(data)


def fetch_bdc_dataset_monthly(year: int, month: int) -> BDCDataset:
    """
    Fetch a monthly BDC data set from SEC.

    The SEC publishes monthly BDC data sets in addition to quarterly ones.
    Monthly data is typically available for more recent periods.

    Args:
        year: The year (e.g., 2025)
        month: The month (1-12)

    Returns:
        BDCDataset containing all parsed data

    Raises:
        ValueError: If the month is invalid
        httpx.HTTPError: If the download fails

    Example:
        >>> dataset = fetch_bdc_dataset_monthly(2025, 11)
        >>> print(f"Found {dataset.num_submissions} submissions")
    """
    if month not in range(1, 13):
        raise ValueError(f"Month must be 1-12, got {month}")

    url = _build_monthly_url(year, month)

    # Download the ZIP file
    response = get_with_retry(url)
    response.raise_for_status()

    zip_content = response.content

    # Parse each file from the ZIP
    # Note: Files use .tsv extension and may be in 'datasets/' subdirectory
    submissions = _parse_tsv_from_zip(zip_content, 'sub.tsv')
    numbers = _parse_tsv_from_zip(zip_content, 'num.tsv')
    presentation = _parse_tsv_from_zip(zip_content, 'pre.tsv')
    soi = _parse_tsv_from_zip(zip_content, 'soi.tsv')

    # Convert date columns if present
    if 'filed' in submissions.columns:
        submissions['filed'] = pd.to_datetime(submissions['filed'], errors='coerce')
    if 'period' in submissions.columns:
        submissions['period'] = pd.to_datetime(submissions['period'], errors='coerce')

    # For monthly datasets, we compute a synthetic quarter
    quarter = (month - 1) // 3 + 1

    return BDCDataset(
        year=year,
        quarter=quarter,
        submissions=submissions,
        numbers=numbers,
        presentation=presentation,
        soi=soi,
    )
