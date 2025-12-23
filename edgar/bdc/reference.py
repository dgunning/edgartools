"""
SEC BDC (Business Development Company) reference data.

This module provides access to the SEC's authoritative list of Business Development Companies
from the SEC BDC Report, published annually.

Data source: https://www.sec.gov/about/opendatasetsshtmlbdc
"""
import io
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Optional
from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import httpx
import pandas as pd

from edgar.formatting import cik_text
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

        # Last filing info
        if self.last_filing_date:
            table.add_row("Last Filing", f"{self.last_filing_type or ''} ({self.last_filing_date})")

        return Panel(
            table,
            title=Text.assemble("🏢 ", (self.name, "bold")),
            subtitle="Business Development Company",
            border_style="blue",
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

        soi = self.schedule_of_investments(form=form)
        if soi is None:
            return None

        return PortfolioInvestments.from_statement(soi, include_untyped=include_untyped)


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

    def filter(self, state: Optional[str] = None, active: bool = False) -> 'BDCEntities':
        """
        Filter BDC entities.

        Args:
            state: Filter by state (e.g., 'NY', 'CA')
            active: If True, only include BDCs that filed in 2023 or later

        Returns:
            Filtered BDCEntities
        """
        entities = self._entities

        if state:
            entities = [e for e in entities if e.state and e.state.upper() == state.upper()]

        if active:
            cutoff = date(2023, 1, 1)
            entities = [e for e in entities if e.last_filing_date and e.last_filing_date >= cutoff]

        return BDCEntities(entities)

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

        # Show first 20 rows, then ellipsis if more
        display_entities = self._entities
        for index, entity in enumerate(display_entities):
            last_filing = ""
            if entity.last_filing_date:
                last_filing = f"{entity.last_filing_type or ''} ({entity.last_filing_date})"

            table.add_row(
                str(index),
                entity.name,
                cik_text(entity.cik),
                entity.file_number,
                entity.state or "",
                last_filing,
            )

        return Panel(
            table,
            subtitle=f"[bold]{len(self._entities)}[/bold] BDCs",
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
