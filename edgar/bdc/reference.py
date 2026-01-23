"""
SEC BDC (Business Development Company) reference data.

This module provides access to the SEC's authoritative list of Business Development Companies
from the SEC BDC Report, published annually.

Data source: https://www.sec.gov/about/opendatasetsshtmlbdc
"""
import io
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from functools import lru_cache
from typing import Optional
from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import httpx
import pandas as pd

from edgar.display.formatting import cik_text
from edgar.httprequests import get_with_retry

__all__ = [
    'BDCEntity',
    'BDCEntities',
    'get_bdc_list',
    'get_active_bdc_ciks',
    'is_bdc_cik',
    'fetch_bdc_report',
    'get_latest_bdc_report_year',
]

# Base URL for SEC BDC Report files
BDC_REPORT_BASE_URL = "https://www.sec.gov/files/investment/data/other/business-development-company-report"


@dataclass
class BDCEntity:
    """
    A Business Development Company from the SEC BDC Report.

    BDCs are closed-end investment companies that invest in small and mid-sized
    private companies. They file with the SEC under the Investment Company Act
    of 1940 and have file numbers starting with "814-".
    """
    file_number: str  # e.g., "814-00663"
    cik: int  # e.g., 1287750
    name: str  # e.g., "ARES CAPITAL CORP"
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    last_filing_date: Optional[date] = None
    last_filing_type: Optional[str] = None

    @property
    def is_active(self) -> bool:
        """
        Check if the BDC is actively filing with the SEC.

        A BDC is considered active if it has filed within the last 18 months.
        BDCs that haven't filed recently may have been acquired, liquidated,
        or converted to a different structure.

        Returns:
            True if the BDC has filed within the last 18 months.
        """
        if not self.last_filing_date:
            return False
        cutoff = date.today() - relativedelta(months=18)
        return self.last_filing_date >= cutoff

    def __rich__(self):

        # Create info table
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("Field", style="dim")
        table.add_column("Value")

        table.add_row("CIK", cik_text(self.cik))
        table.add_row("File Number", self.file_number)

        # Location
        if self.city or self.state:
            location = ", ".join(filter(None, [self.city, self.state]))
            table.add_row("Location", location)

        # Last filing info with status indicator
        if self.last_filing_date:
            filing_text = f"{self.last_filing_type or ''} ({self.last_filing_date})"
            if not self.is_active:
                filing_text = f"[red]{filing_text}[/red]"
            table.add_row("Last Filing", filing_text)

        # Status indicator
        status = "[green]Active[/green]" if self.is_active else "[red]Inactive[/red]"
        table.add_row("Status", status)

        return Panel(
            table,
            title=Text.assemble("🏢 ", (self.name, "bold")),
            subtitle="Business Development Company",
            border_style="blue" if self.is_active else "red",
            width=100
        )

    def __repr__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())

    def get_company(self):
        """
        Get the Company object for this BDC.

        Returns:
            Company object for this BDC's CIK.
        """
        from edgar import Company
        return Company(self.cik)

    def get_filings(self, form: Optional[str] = None):
        """
        Get filings for this BDC.

        Args:
            form: Optional form type to filter (e.g., '10-K', '10-Q')

        Returns:
            Filings for this BDC.
        """
        company = self.get_company()
        if form:
            return company.get_filings(form=form)
        return company.get_filings()

    def schedule_of_investments(self, form: str = "10-K"):
        """
        Get the Schedule of Investments from the latest filing.

        Fetches the latest 10-K (or specified form) for this BDC and
        extracts the Schedule of Investments statement from the XBRL data.

        Args:
            form: The form type to use ('10-K' or '10-Q'). Defaults to '10-K'.

        Returns:
            Statement object containing the Schedule of Investments,
            or None if not available.

        Example:
            >>> arcc = get_bdc_list()[0]
            >>> soi = arcc.schedule_of_investments()
            >>> soi.to_dataframe()
        """
        company = self.get_company()
        # Exclude amendments to get full XBRL data
        filings = company.get_filings(form=form, amendments=False)
        if len(filings) == 0:
            return None

        latest_filing = filings[0]
        xbrl = latest_filing.xbrl()

        if xbrl is None:
            return None

        return xbrl.statements.schedule_of_investments()

    def portfolio_investments(self, form: str = "10-K", include_untyped: bool = False):
        """
        Get individual portfolio investments from the latest filing.

        Parses the Schedule of Investments XBRL data to extract individual
        investment holdings with fair value, cost, interest rate, etc.

        This method tries two extraction approaches:
        1. Statement-based: Uses the XBRL presentation hierarchy
        2. Facts-based: Extracts directly from XBRL facts with dimensions

        Some BDCs (like Blue Owl) have dimensional investment data in facts
        but not in the Statement presentation hierarchy, so both approaches
        are attempted.

        Args:
            form: The form type to use ('10-K' or '10-Q'). Defaults to '10-K'.
            include_untyped: If False (default), excludes investments with "Unknown"
                type. These are typically company-level rollup entries that would
                inflate totals. Set to True to include all entries.

        Returns:
            PortfolioInvestments collection, or None if not available.

        Example:
            >>> arcc = get_bdc_list()[0]
            >>> investments = arcc.portfolio_investments()
            >>> len(investments)
            1070
            >>> investments.total_fair_value
            Decimal('27000000000')
            >>> investments.filter(investment_type='First lien')
            PortfolioInvestments with first lien loans
        """
        from edgar.bdc.investments import PortfolioInvestments

        # Get XBRL for the filing
        company = self.get_company()
        filings = company.get_filings(form=form, amendments=False)
        if len(filings) == 0:
            return None

        xbrl = filings[0].xbrl()
        if xbrl is None:
            return None

        # Try facts-based extraction first (works for more BDCs)
        investments = PortfolioInvestments.from_xbrl(xbrl, include_untyped=include_untyped)
        if len(investments) > 0:
            return investments

        # Fall back to statement-based extraction
        soi = xbrl.statements.schedule_of_investments()
        if soi is None:
            return None

        return PortfolioInvestments.from_statement(soi, include_untyped=include_untyped)

    def has_detailed_investments(self, form: str = "10-K") -> bool:
        """
        Check if this BDC has detailed investment data in its XBRL filings.

        Some BDCs provide detailed per-investment XBRL data in their Schedule
        of Investments, while others only provide aggregate totals or only
        tag dividend income. This method checks whether useful per-investment
        data (fair value, cost) is available for extraction.

        Checks both statement-based and facts-based sources.

        Args:
            form: The form type to check ('10-K' or '10-Q'). Defaults to '10-K'.

        Returns:
            True if detailed investment data is available, False otherwise.

        Example:
            >>> arcc = get_bdc_list()[0]
            >>> arcc.has_detailed_investments()
            True
            >>> htgc = get_bdc_list()['Hercules']  # Example of BDC without detailed data
            >>> htgc.has_detailed_investments()
            False
        """
        # Get XBRL for the filing
        company = self.get_company()
        filings = company.get_filings(form=form, amendments=False)
        if len(filings) == 0:
            return False

        xbrl = filings[0].xbrl()
        if xbrl is None:
            return False

        # Check facts-based data (more reliable)
        all_facts = xbrl.facts.get_facts()
        dim_key = 'dim_us-gaap_InvestmentIdentifierAxis'
        useful_concepts = {'us-gaap:InvestmentOwnedAtFairValue', 'us-gaap:InvestmentOwnedAtCost'}

        for fact in all_facts:
            concept = fact.get('concept', '')
            has_dim = fact.get(dim_key) is not None
            is_useful = concept in useful_concepts

            if has_dim and is_useful:
                return True

        return False


class BDCEntities:
    """
    A collection of BDC entities from the SEC BDC Report.

    Provides table display and indexing for the list of BDCs.
    """

    def __init__(self, entities: list[BDCEntity]):
        self._entities = entities

    def __len__(self) -> int:
        return len(self._entities)

    def __getitem__(self, item) -> BDCEntity:
        return self._entities[item]

    def __iter__(self):
        return iter(self._entities)

    def filter(self, state: Optional[str] = None, active: Optional[bool] = None) -> 'BDCEntities':
        """
        Filter BDC entities.

        Args:
            state: Filter by state (e.g., 'NY', 'CA')
            active: If True, only include active BDCs (filed within last 18 months).
                   If False, only include inactive BDCs.
                   If None (default), include all.

        Returns:
            Filtered BDCEntities
        """
        entities = self._entities

        if state:
            entities = [e for e in entities if e.state and e.state.upper() == state.upper()]

        if active is True:
            entities = [e for e in entities if e.is_active]
        elif active is False:
            entities = [e for e in entities if not e.is_active]

        return BDCEntities(entities)

    def get_by_cik(self, cik: int) -> Optional[BDCEntity]:
        """
        Get a BDC by its CIK number.

        Args:
            cik: The SEC CIK number.

        Returns:
            BDCEntity if found, None otherwise.

        Example:
            >>> bdcs = get_bdc_list()
            >>> arcc = bdcs.get_by_cik(1287750)
            >>> arcc.name
            'ARES CAPITAL CORP'
        """
        for entity in self._entities:
            if entity.cik == cik:
                return entity
        return None

    def get_by_ticker(self, ticker: str) -> Optional[BDCEntity]:
        """
        Get a BDC by its ticker symbol.

        Uses the SEC ticker-to-CIK mapping to find the BDC.

        Args:
            ticker: The stock ticker symbol (e.g., 'ARCC', 'MAIN').

        Returns:
            BDCEntity if found, None otherwise.

        Example:
            >>> bdcs = get_bdc_list()
            >>> arcc = bdcs.get_by_ticker('ARCC')
            >>> arcc.name
            'ARES CAPITAL CORP'
        """
        from edgar.reference.tickers import find_cik

        cik = find_cik(ticker.upper())
        if cik is None:
            return None
        return self.get_by_cik(cik)

    def search(self, query: str, top_n: int = 10):
        """
        Search for BDCs by name or ticker.

        Supports fuzzy matching on BDC names and exact/prefix matching on tickers.

        Args:
            query: Search query (name or ticker)
            top_n: Maximum number of results

        Returns:
            BDCSearchResults with matching BDCs

        Example:
            >>> bdcs = get_bdc_list()
            >>> results = bdcs.search("Ares")
            >>> results[0].name
            'ARES CAPITAL CORP'

            >>> results = bdcs.search("MAIN")
            >>> results[0].name
            'MAIN STREET CAPITAL CORP'
        """
        from edgar.bdc.search import find_bdc
        return find_bdc(query, top_n=top_n)

    @property
    def ciks(self) -> list[int]:
        """
        Get list of CIKs for all BDCs in this collection.

        Returns:
            Sorted list of CIK numbers.

        Example:
            >>> bdcs = get_bdc_list()
            >>> bdcs.ciks[:5]
            [18349, 25254, 35315, 36377, 63602]
        """
        return sorted(e.cik for e in self._entities)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame."""
        return pd.DataFrame([
            {
                'name': e.name,
                'cik': e.cik,
                'file_number': e.file_number,
                'city': e.city,
                'state': e.state,
                'last_filing_date': e.last_filing_date,
                'last_filing_type': e.last_filing_type,
                'is_active': e.is_active,
            }
            for e in self._entities
        ])

    def __rich__(self):
        from edgar.richtools import repr_rich

        table = Table(
            title="SEC Business Development Companies",
            box=box.SIMPLE,
            show_header=True,
            header_style="bold",
            row_styles=["", "dim"],
        )
        table.add_column("")
        table.add_column("Name", style="bold")
        table.add_column("CIK", justify="right")
        table.add_column("File Number")
        table.add_column("State")
        table.add_column("Last Filing")
        table.add_column("Status", justify="center")

        # Count active/inactive for subtitle
        active_count = sum(1 for e in self._entities if e.is_active)
        inactive_count = len(self._entities) - active_count

        for index, entity in enumerate(self._entities):
            last_filing = ""
            if entity.last_filing_date:
                last_filing = f"{entity.last_filing_type or ''} ({entity.last_filing_date})"
                if not entity.is_active:
                    last_filing = f"[dim]{last_filing}[/dim]"

            status = "[green]Active[/green]" if entity.is_active else "[red]Inactive[/red]"

            # Dim the name for inactive BDCs
            name = entity.name if entity.is_active else f"[dim]{entity.name}[/dim]"

            table.add_row(
                str(index),
                name,
                cik_text(entity.cik),
                entity.file_number,
                entity.state or "",
                last_filing,
                status,
            )

        return Panel(
            table,
            subtitle=f"[green]{active_count}[/green] active, [red]{inactive_count}[/red] inactive — [bold]{len(self._entities)}[/bold] total",
            border_style="blue",
            expand=False,
        )

    def __repr__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())


def _excel_serial_to_date(serial: float) -> Optional[date]:
    """
    Convert Excel serial date to Python date.

    Excel uses a serial date system where day 1 is January 1, 1900.
    Note: Excel incorrectly treats 1900 as a leap year, so we use the
    epoch of December 30, 1899 to compensate.
    """
    if pd.isna(serial) or serial <= 0:
        return None
    try:
        return (datetime(1899, 12, 30) + timedelta(days=int(serial))).date()
    except (ValueError, OverflowError):
        return None


def get_latest_bdc_report_year() -> int:
    """
    Determine the latest available year for the SEC BDC Report.

    Checks backwards from the current year to find available reports.

    Returns:
        The latest year with an available BDC report.
    """
    current_year = datetime.now().year

    for year in range(current_year, 2015, -1):
        url = f"{BDC_REPORT_BASE_URL}/business-development-company-{year}.csv"
        try:
            response = get_with_retry(url, timeout=5)
            if response.status_code == 200:
                return year
        except Exception:
            continue

    return 2024  # Fallback to known good year


@lru_cache(maxsize=4)
def fetch_bdc_report(year: Optional[int] = None) -> pd.DataFrame:
    """
    Fetch the SEC BDC Report as a pandas DataFrame.

    Args:
        year: The report year. If None, uses the latest available year.

    Returns:
        DataFrame with columns: file_number, cik, registrant_name,
        address_1, city, state, zip_code, last_filling_date, last_filling_type

    Raises:
        httpx.HTTPError: If the request fails.
    """
    if year is None:
        year = get_latest_bdc_report_year()

    url = f"{BDC_REPORT_BASE_URL}/business-development-company-{year}.csv"
    response = get_with_retry(url)
    response.raise_for_status()

    df = pd.read_csv(io.StringIO(response.text))

    # Normalize column names (handle variations across years)
    column_mapping = {
        # 2024 format
        'File_No': 'file_number',
        'Registrant_Name': 'registrant_name',
        'Address_1': 'address_1',
        'Address_2': 'address_2',
        'Zip_Code': 'zip_code',
        'Filing Date': 'last_filing_date',
        'Filing Type': 'last_filing_type',
        # Earlier format variations
        'File Number': 'file_number',
        'file_number': 'file_number',
        'CIK': 'cik',
        'cik': 'cik',
        'Registrant Name': 'registrant_name',
        'registrant_name': 'registrant_name',
        'Address 1': 'address_1',
        'address_1': 'address_1',
        'City': 'city',
        'city': 'city',
        'State': 'state',
        'state': 'state',
        'Zip Code': 'zip_code',
        'zip_code': 'zip_code',
        'Last Filling Date': 'last_filing_date',
        'last_filling_date': 'last_filing_date',
        'Last Filling Type': 'last_filing_type',
        'last_filling_type': 'last_filing_type',
    }

    df = df.rename(columns=column_mapping)

    # Parse filing date (format: MM/DD/YY)
    if 'last_filing_date' in df.columns:
        df['last_filing_date'] = pd.to_datetime(
            df['last_filing_date'],
            format='%m/%d/%y',
            errors='coerce'
        )

    return df


def get_bdc_list(year: Optional[int] = None) -> BDCEntities:
    """
    Get all BDCs from the SEC BDC Report.

    Args:
        year: The report year. If None, uses the latest available year.

    Returns:
        BDCEntities collection of all BDCs in the report.

    Example:
        >>> bdcs = get_bdc_list()
        >>> len(bdcs)
        196
        >>> bdcs[0]
        BDCEntity(...)
        >>> bdcs.filter(state='NY')
        BDCEntities with NY-based BDCs
    """
    df = fetch_bdc_report(year)

    bdcs = []
    for _, row in df.iterrows():
        last_date = None
        if pd.notna(row.get('last_filing_date')):
            last_date = row['last_filing_date'].date()

        bdcs.append(BDCEntity(
            file_number=str(row.get('file_number', '')),
            cik=int(row['cik']) if pd.notna(row.get('cik')) else 0,
            name=str(row.get('registrant_name', '')),
            city=str(row.get('city', '')) if pd.notna(row.get('city')) else None,
            state=str(row.get('state', '')) if pd.notna(row.get('state')) else None,
            zip_code=str(row.get('zip_code', '')) if pd.notna(row.get('zip_code')) else None,
            last_filing_date=last_date,
            last_filing_type=str(row.get('last_filing_type', '')) if pd.notna(row.get('last_filing_type')) else None,
        ))

    # Sort by name
    bdcs.sort(key=lambda b: b.name.lower())

    return BDCEntities(bdcs)


@lru_cache(maxsize=1)
def get_active_bdc_ciks(min_year: int = 2023) -> frozenset[int]:
    """
    Get CIKs of actively filing BDCs.

    Args:
        min_year: Minimum year for last filing to be considered "active".
                  Defaults to 2023.

    Returns:
        Frozenset of CIKs for BDCs that have filed since min_year.
    """
    bdcs = get_bdc_list()
    cutoff = date(min_year, 1, 1)

    return frozenset(
        bdc.cik
        for bdc in bdcs
        if bdc.last_filing_date and bdc.last_filing_date >= cutoff
    )


def is_bdc_cik(cik: int) -> bool:
    """
    Check if a CIK belongs to a known BDC.

    Args:
        cik: The SEC CIK number to check.

    Returns:
        True if the CIK is in the SEC BDC Report, False otherwise.
    """
    bdcs = get_bdc_list()
    return any(bdc.cik == cik for bdc in bdcs)
