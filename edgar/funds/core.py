"""
Core classes for working with investment funds.

This module provides the main classes used to interact with investment funds:
- Fund: Represents an investment fund entity
- FundClass: Represents a specific share class of a fund
- FundSeries: Represents a fund series
"""
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import pandas as pd
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.entity.core import Entity
from edgar.richtools import repr_rich

if TYPE_CHECKING:
    from edgar._filings import Filings
    from edgar.entity.data import EntityData

log = logging.getLogger(__name__)

__all__ = ['Fund', 'FundCompany', 'FundClass', 'FundSeries', 'get_fund_company', 'get_fund_class', 'get_fund_series', 'find_fund', 'find_funds']

# Keys the browse-edgar Filings.filter interface accepts directly.
_FILINGS_FILTER_KEYS = frozenset(
    {'form', 'amendments', 'filing_date', 'date', 'cik', 'exchange', 'ticker', 'accession_number'}
)


def _year_quarter_to_filing_date(year, quarter) -> Optional[str]:
    """Translate entity-style ``year``/``quarter`` into a ``Filings.filter``
    ``filing_date`` range (``"YYYY-MM-DD:YYYY-MM-DD"``), or None if it can't be
    expressed simply (e.g. a list of years)."""
    if not isinstance(year, int):
        return None
    if quarter is None:
        return f"{year}-01-01:{year}-12-31"
    if isinstance(quarter, int) and 1 <= quarter <= 4:
        bounds = {1: ("01-01", "03-31"), 2: ("04-01", "06-30"),
                  3: ("07-01", "09-30"), 4: ("10-01", "12-31")}
        start, end = bounds[quarter]
        return f"{year}-{start}:{year}-{end}"
    return None


def _series_filter_kwargs(kwargs: dict) -> dict:
    """Map entity-style ``get_filings`` kwargs onto the ``Filings.filter``
    interface used by the series (browse-edgar) path.

    ``Filings.filter`` is keyword-only and accepts a narrower set than
    ``Entity.get_filings`` — forwarding raw kwargs raised ``TypeError`` for
    entity-only args such as ``year``/``quarter``/``is_xbrl`` (GH #888 review).
    We forward the supported keys, translate ``year``/``quarter`` into a
    ``filing_date`` range, default ``amendments`` to ``True`` to match the
    entity path (``Filings.filter`` otherwise drops amendments when a form is
    given), and log — rather than crash on — any filter we can't honor here.
    """
    filter_kwargs = {k: v for k, v in kwargs.items() if k in _FILINGS_FILTER_KEYS}

    # Match the entity path, which includes amendments by default.
    if 'form' in filter_kwargs and 'amendments' not in filter_kwargs:
        filter_kwargs['amendments'] = True

    # Translate year/quarter unless an explicit date filter was already given.
    if kwargs.get('year') is not None and not {'filing_date', 'date'} & filter_kwargs.keys():
        date_range = _year_quarter_to_filing_date(kwargs.get('year'), kwargs.get('quarter'))
        if date_range:
            filter_kwargs['filing_date'] = date_range

    # Anything left that we did not honor (is_xbrl, file_number, sort_by,
    # untranslatable year/quarter, …) is logged so it isn't silently misleading.
    honored = set(_FILINGS_FILTER_KEYS)
    if 'filing_date' in filter_kwargs:
        honored |= {'year', 'quarter'}
    unsupported = sorted(set(kwargs) - honored)
    if unsupported:
        log.debug("series_only path does not apply these filters: %s", unsupported)

    return filter_kwargs


class FundCompany(Entity):
    """
    Represents an investment fund that files with the SEC.

    Provides fund-specific functionality like share classes, series information,
    portfolio holdings, etc.
    """

    def __init__(self,
                 cik_or_identifier: Union[str, int],
                 fund_name: Optional[str] = None,
                 all_series: Optional[List['FundSeries']] = None):
        # Import locally to avoid circular imports
        from edgar.funds.data import resolve_fund_identifier

        # Handle fund-specific identifiers
        super().__init__(resolve_fund_identifier(cik_or_identifier))
        self._name = fund_name
        self.all_series:Optional[List['FundSeries']] = all_series or []
        self._cached_portfolio = None


    @property
    def name(self):
        """Get the name of the company."""
        return self._name or super().name

    def list_series(self) -> Optional[List['FundSeries']]:
        """
        List all fund series associated with this company.

        Returns:
            List of FundSeries instances
        """
        return self.all_series

    @property
    def data(self) -> 'EntityData':
        """Get detailed data for this fund."""
        base_data = super().data

        # If we already have fund-specific data, return it
        if hasattr(base_data, 'is_fund') and base_data.is_fund:
            return base_data

        # Otherwise, try to convert to fund-specific data
        # This could be enhanced in the future
        return base_data

    def __str__(self):
        return f"{self.name} [{self.cik}]"


    def __rich__(self):
        """Creates a rich representation of the fund with detailed information."""
        return super().__rich__()

    def __repr__(self):
        return repr_rich(self.__rich__())

class FundClass:
    """
    Represents a specific class of an investment fund.

    Fund classes typically have their own ticker symbols and fee structures,
    but belong to the same underlying fund. Each class belongs to a specific
    fund series.
    """

    def __init__(self, class_id: str, name: Optional[str] = None,
                ticker: Optional[str] = None, series: Optional['FundSeries'] = None):
        self.class_id = class_id
        self.name = name
        self.ticker = ticker
        self.series = series  # The series ID this class belongs to

    def __str__(self):
        ticker_str = f" - {self.ticker}" if self.ticker else ""
        return f"FundClass({self.name} [{self.class_id}]{ticker_str})"

    def get_classes(self) -> List['FundClass']:
        """Get all share classes in the same series as this class."""
        if self.series and self.series.series_id:
            from edgar.funds.data import get_fund_object
            full_series = get_fund_object(self.series.series_id)
            if full_series and hasattr(full_series, 'get_classes'):
                return full_series.get_classes()
        return [self]  # fallback

    def __repr__(self):
        return self.__str__()

    def __rich__(self):
        """Creates a rich representation of the fund class."""
        table = Table(
            title=None,
            box=box.ROUNDED,
            show_header=True
        )

        table.add_column("Fund", style="bold")
        table.add_column("Class ID", style="bold")
        table.add_column("Series ID", style="bold cyan")
        table.add_column("Ticker", style="bold yellow")

        table.add_row(
                self.name,
                self.class_id,
                self.series.series_id if self.series else "Unknown",
                self.ticker or ""
        )

        return Panel(
                table,
                title=f"🏦 {self.name}",
                subtitle="Fund Class"
        )

class FundSeries:
    """Represents a fund series with multiple share classes."""

    def __init__(self, series_id: str, name: str,
                 fund_classes:Optional[List[FundClass]]=None,
                 fund_company: Optional[FundCompany] = None):
        self.series_id = series_id
        self.name = name
        self.fund_classes:List[FundClass] = fund_classes or []
        self.fund_company: Optional[FundCompany] = fund_company

    def get_classes(self) -> List[FundClass]:
        """
        Get all share classes in this series.

        Returns:
            List of FundClass instances belonging to this specific series
        """
        return self.fund_classes

    def get_filings(self, **kwargs) -> 'Filings':
        """
        Get filings for this fund series.

        Args:
            **kwargs: Filtering parameters passed to get_filings

        Returns:
            Filings object with filtered filings
        """
        return self.fund_company.get_filings(**kwargs)

    def __str__(self):
        return f"FundSeries({self.name} [{self.series_id}])"

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __rich__(self):
        """Creates a rich representation of the fund series."""

        # Classes information
        classes = self.get_classes()
        classes_table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
        classes_table.add_column("Class ID")
        classes_table.add_column("Class Name")
        classes_table.add_column("Ticker", style="bold yellow")

        for class_obj in classes:
            classes_table.add_row(
                        class_obj.class_id,
                    class_obj.name,
                    class_obj.ticker or "-"
             )

        classes_panel = Panel(
                classes_table,
                title="📊 Share Classes",
                border_style="grey50"
        )

        content = Group(classes_panel)
        return Panel(
            content,
            title=f"🏦 {self.name} [{self.series_id}]",
            subtitle="Fund Series"
        )

def find_fund(identifier: str) -> Union[FundCompany, FundSeries, FundClass]:
    """
    Smart factory that finds and returns the most appropriate fund entity.

    This function takes any type of fund identifier and returns the most specific
    entity that matches it. For a series ID, it returns a FundSeries. For a class ID
    or ticker, it returns a FundClass. For a company CIK, it returns a FundCompany.

    Args:
        identifier: Fund ticker (e.g., 'VFINX'), Series ID (e.g., 'S000001234'),
                  Class ID (e.g., 'C000012345'), or CIK number

    Returns:
        The most specific fund entity that matches the identifier:
        - FundClass for tickers and class IDs
        - FundSeries for series IDs
        - FundCompany for company CIKs
    """
    # Check for Series ID (S000XXXXX)
    if isinstance(identifier, str) and identifier.upper().startswith('S') and identifier[1:].isdigit():
        return get_fund_series(identifier)

    # Check for Class ID (C000XXXXX)
    if isinstance(identifier, str) and identifier.upper().startswith('C') and identifier[1:].isdigit():
        return get_fund_class(identifier)

    # Check for ticker symbol
    if is_fund_class_ticker(identifier):
        return get_fund_class(identifier)

    # Default to returning a FundCompany
    return get_fund_company(identifier)


# === Specialized Getter Functions ===

def get_fund_company(cik_or_identifier: Union[str, int]) -> FundCompany:
    """
    Get a fund company by its CIK or identifier.

    Args:
        cik_or_identifier: CIK number or other identifier

    Returns:
        FundCompany instance
    """
    return FundCompany(cik_or_identifier)


def get_fund_series(series_id: str) -> FundSeries:
    """
    Get a fund series by its Series ID.

    Args:
        series_id: Series ID (e.g., 'S000001234')

    Returns:
        FundSeries instance

    Raises:
        ValueError: If the series cannot be found
    """
    from edgar.funds.data import get_fund_object

    fund_series: Optional[FundSeries] = get_fund_object(series_id)
    return fund_series


def get_fund_class(class_id_or_ticker: str) -> FundClass:
    """
    Get a fund class by its Class ID or ticker.

    Args:
        class_id_or_ticker: Class ID (e.g., 'C000012345') or ticker symbol (e.g., 'VFINX')

    Returns:
        FundClass instance

    Raises:
        ValueError: If the class cannot be found
    """
    from edgar.funds.data import get_fund_object
    fund_class: FundClass = get_fund_object(class_id_or_ticker)
    return fund_class


# === Helper Functions ===

def is_fund_class_ticker(identifier: str) -> bool:
    """
    Determine if the given identifier is a fund class ticker.

    Args:
        identifier: The identifier to check

    Returns:
        True if it's a fund class ticker, False otherwise
    """
    from edgar.funds.data import is_fund_ticker
    return is_fund_ticker(identifier)


def find_funds(name: str, search_type: str = 'series') -> list:
    """Search for funds by name fragment.

    Uses FundReferenceData to search across fund companies, series, or classes.

    Args:
        name: Case-insensitive name fragment to search for
        search_type: 'company', 'series', or 'class'

    Returns:
        List of matching records
    """
    from edgar.funds.reference import get_fund_reference_data
    return get_fund_reference_data().find_by_name(name, search_type=search_type)


class Fund:
    """
    Unified wrapper for fund entities that provides a consistent interface
    regardless of the identifier type (ticker, series ID, class ID, or CIK).

    This class serves as a user-friendly entry point to the fund domain model.
    It internally resolves the appropriate entity type and provides access to
    the full hierarchy.

    Examples:
        ```python
        # Create a Fund object from any identifier
        fund = Fund("VFINX")         # From ticker
        fund = Fund("S000002277")    # From series ID
        fund = Fund("0000102909")    # From CIK

        # Access the hierarchy
        print(fund.name)              # Name of the entity
        print(fund.company.name)      # Name of the fund company
        print(fund.series.name)       # Name of the fund series
        print(fund.share_class.ticker) # Ticker of the share class
        ```
    """

    def __init__(self, identifier: Union[str, int]):
        """
        Initialize a Fund object from any identifier.

        Args:
            identifier: Any fund identifier (ticker, series ID, class ID, or CIK)
        """
        self._original_identifier = str(identifier)
        self._target_series_id = None  # New: specific series if determinable

        # Handle ticker resolution to series
        if isinstance(identifier, str) and self._is_fund_ticker(identifier):
            from edgar.funds.series_resolution import TickerSeriesResolver
            target_series_id = TickerSeriesResolver.get_primary_series(identifier)
            if target_series_id:
                self._target_series_id = target_series_id

        # Use existing find_fund to get the appropriate entity
        self._entity = find_fund(identifier)

        # Set up references to the full hierarchy
        if isinstance(self._entity, FundClass):
            self._class = self._entity
            self._series = self._class.series
            self._company = self._series.fund_company if self._series else None
        elif isinstance(self._entity, FundSeries):
            self._class = None
            self._series = self._entity
            self._company = self._series.fund_company
        elif isinstance(self._entity, FundCompany):
            self._class = None
            self._series = None
            self._company = self._entity

    def _is_fund_ticker(self, identifier: str) -> bool:
        """Check if an identifier appears to be a fund ticker"""
        from edgar.funds.series_resolution import TickerSeriesResolver
        series_list = TickerSeriesResolver.resolve_ticker_to_series(identifier)
        return len(series_list) > 0

    @property
    def company(self) -> Optional[FundCompany]:
        """Get the fund company (may be None if not resolved)"""
        return self._company

    @property
    def series(self) -> Optional[FundSeries]:
        """Get the fund series (may be None if only company was identified)"""
        return self._series

    @property
    def share_class(self) -> Optional[FundClass]:
        """Get the share class (may be None if only series or company was identified)"""
        return self._class

    @property
    def name(self) -> Optional[str]:
        """Get the name of the fund entity"""
        return self._entity.name

    @property
    def identifier(self) -> str:
        """Get the primary identifier of the fund entity"""
        if isinstance(self._entity, FundClass):
            return self._entity.class_id
        elif isinstance(self._entity, FundSeries):
            return self._entity.series_id
        elif isinstance(self._entity, FundCompany):
            return str(self._entity.cik)
        return ""

    @property
    def ticker(self) -> Optional[str]:
        """Get the ticker symbol (only available for share classes)"""
        if self._class:
            return self._class.ticker
        return None

    def get_filings(self, series_only: bool = False, **kwargs) -> 'Filings':
        """
        Get filings for this fund entity.

        This delegates to the appropriate entity's get_filings method.

        Args:
            series_only: If True and we have target series context, return only
                         this fund series' filings (resolved via SEC browse-edgar
                         using the series ID), rather than the whole umbrella
                         trust's. Returns an empty Filings if the series has no
                         matching filings.
            **kwargs: Filtering parameters (form, year, quarter, filing_date,
                      date, amendments, …) applied to the results.

        Returns:
            Filings object with filtered filings
        """
        # Series-aware path. This isolates a single series' filings from a
        # registrant that files one report per series (e.g. an ETF ticker whose
        # CIK is the umbrella trust). We query SEC browse-edgar with the series
        # ID as the CIK parameter, which returns exactly that series' filings.
        #
        # (A previous implementation used EFTS full-text search on the series
        # ID; that returns nothing — SEC full-text search does not index NPORT
        # series IDs — so it silently fell through to the unfiltered trust and
        # returned the WRONG series' data. GH #888.)
        if series_only and self._target_series_id and not self._target_series_id.startswith("ETF_"):
            series_filings = self._get_series_filings(self._target_series_id, **kwargs)
            # When series filtering is requested we must NOT silently return the
            # unfiltered trust: an empty result is correct if the series has no
            # matching filings, and returning trust-wide filings here would give
            # the caller a sibling series' data (GH #888).
            from edgar._filings import Filings
            return series_filings if series_filings is not None else Filings([])

        # Default path: delegate to entity
        filings = None
        if hasattr(self._entity, 'get_filings'):
            filings = self._entity.get_filings(**kwargs)
        elif self._series and hasattr(self._series, 'get_filings'):
            filings = self._series.get_filings(**kwargs)
        elif self._company and hasattr(self._company, 'get_filings'):
            filings = self._company.get_filings(**kwargs)

        if not filings:
            from edgar._filings import Filings
            return Filings([])

        return filings

    def _get_series_filings(self, series_id: str, **kwargs) -> Optional['Filings']:
        """Return only ``series_id``'s filings via SEC browse-edgar, or None.

        Uses the browse-edgar endpoint with the series ID as the CIK parameter,
        which SEC resolves to exactly that fund series' filing list (unlike EFTS
        full-text search, which does not index series IDs). When a form filter is
        given it is pushed to browse-edgar (``&type=``) per requested form so the
        query returns only those filings — a large fund otherwise pages through
        its entire history, which SEC 503s on deep pages and would drop the whole
        result to empty (GH #888). Returns None when the series cannot be
        resolved so the caller can surface an empty result rather than the
        unfiltered trust; ``kwargs`` are mapped onto ``Filings.filter``.
        """
        form = kwargs.get('form')
        if isinstance(form, str):
            form_types = [form]
        elif isinstance(form, (list, tuple)) and form:
            form_types = [str(f) for f in form]
        else:
            form_types = [None]  # no form filter — one unrestricted lookup

        try:
            from edgar.funds.data import direct_get_fund_with_filings
            resolved = False
            filing_tables = []
            for filing_type in form_types:
                series = direct_get_fund_with_filings(series_id, filing_type=filing_type)
                if series is None:
                    continue
                resolved = True
                series_filings = getattr(series, 'filings', None)
                if series_filings is not None and len(series_filings) > 0:
                    filing_tables.append(series_filings.data)
        except Exception as e:  # network / parse failure — do not fall back to the trust
            log.debug("Series filing lookup failed for %s: %s", series_id, e)
            return None

        if not resolved:
            # Could not resolve the series at all — signal the caller to return
            # empty, never the unfiltered trust.
            return None

        from edgar._filings import Filings
        if filing_tables:
            import pyarrow as pa

            from edgar.datatools import drop_duplicates_pyarrow
            combined = pa.concat_tables(filing_tables, mode="default")
            combined = drop_duplicates_pyarrow(combined, column_name='accession_number')
            filings = Filings(filing_index=combined)
        else:
            # Series resolved but has no filings of the requested form(s).
            return Filings([])

        filter_kwargs = _series_filter_kwargs(kwargs)
        if filter_kwargs and len(filings) > 0:
            filings = filings.filter(**filter_kwargs)
        return filings

    def get_series(self) -> Optional[FundSeries]:
        """
        Get the specific series for the original ticker if determinable.

        Returns:
            FundSeries if we can determine a specific series, None otherwise
        """
        if self._target_series_id:
            # Handle ETF synthetic series IDs
            if self._target_series_id.startswith("ETF_"):
                # Extract CIK from ETF series ID
                cik = self._target_series_id.replace("ETF_", "")
                try:
                    # Create ETF-specific series
                    from edgar.funds.series_resolution import TickerSeriesResolver
                    series_list = TickerSeriesResolver.resolve_ticker_to_series(self._original_identifier)
                    if series_list and len(series_list) > 0:
                        series_info = series_list[0]  # Get the ETF series info

                        # Create FundSeries for ETF
                        etf_company = FundCompany(cik_or_identifier=int(cik), fund_name=series_info.series_name)
                        return FundSeries(
                            series_id=self._target_series_id,
                            name=series_info.series_name or f"ETF Series for {self._original_identifier}",
                            fund_company=etf_company
                        )
                except Exception as e:
                    log.debug(f"Failed to create ETF series for {self._target_series_id}: {e}")
            else:
                # Regular mutual fund series - try to get by ID
                try:
                    return get_fund_series(self._target_series_id)
                except Exception as e:
                    log.debug(f"Failed to get fund series {self._target_series_id}: {e}")

        # Fallback to current series if available
        return self._series

    def get_resolution_diagnostics(self) -> Dict[str, Any]:
        """Get detailed information about how this Fund was resolved."""
        if self._target_series_id:
            if self._target_series_id.startswith("ETF_"):
                cik = self._target_series_id.replace("ETF_", "")
                return {
                    'status': 'success',
                    'method': 'etf_company_fallback',
                    'series_id': self._target_series_id,
                    'cik': int(cik),
                    'original_identifier': self._original_identifier,
                    'message': f"'{self._original_identifier}' resolved as ETF company ticker"
                }
            else:
                return {
                    'status': 'success',
                    'method': 'mutual_fund_lookup',
                    'series_id': self._target_series_id,
                    'original_identifier': self._original_identifier,
                    'message': f"'{self._original_identifier}' resolved as mutual fund ticker"
                }

        # Check if it's a company ticker (ETF) that we didn't resolve
        from edgar.reference.tickers import find_cik
        cik = find_cik(self._original_identifier)

        if cik:
            return {
                'status': 'partial_success',
                'method': 'company_lookup_unresolved',
                'cik': cik,
                'original_identifier': self._original_identifier,
                'message': f"'{self._original_identifier}' found as company ticker but series resolution failed",
                'suggestion': f"Try using CIK {cik} directly: Fund({cik})"
            }

        return {
            'status': 'failed',
            'method': 'no_resolution',
            'original_identifier': self._original_identifier,
            'message': f"'{self._original_identifier}' not found in SEC ticker databases",
            'suggestion': "Verify ticker spelling or try with CIK/series ID directly"
        }

    def get_latest_report(self, form: str = 'NPORT-P') -> Optional[Any]:
        """Get the latest fund report of the specified type.

        Args:
            form: SEC form type (default 'NPORT-P'). Common values:
                  'NPORT-P', 'N-MFP3', 'N-CEN', 'N-CSR', 'N-CSRS'
        """
        filings = self.get_filings(form=form)
        if filings and len(filings) > 0:
            return filings[0].obj()
        return None

    def get_portfolio(self) -> Optional[pd.DataFrame]:
        """Latest portfolio holdings as a DataFrame.

        Chains: latest NPORT-P -> FundReport -> investment_data().
        """
        report = self.get_latest_report(form='NPORT-P')
        if report and hasattr(report, 'investment_data'):
            return report.investment_data()
        return None

    def list_series(self) -> List[FundSeries]:
        """
        List all fund series associated with this fund.

        If this is a FundCompany, returns all series.
        If this is a FundSeries, returns a list with just this series.
        If this is a FundClass, returns a list with its parent series.

        Returns:
            List of FundSeries instances
        """
        if self._company and hasattr(self._company, 'list_series'):
            series_list = self._company.list_series()
            return series_list if series_list is not None else []

        if self._series:
            return [self._series]

        return []

    def list_classes(self) -> List[FundClass]:
        """
        List all share classes associated with this fund.

        If this is a FundSeries, returns all classes in the series.
        If this is a FundClass, returns a list with just this class.

        Returns:
            List of FundClass instances
        """
        if self._series and hasattr(self._series, 'get_classes'):
            return self._series.get_classes()

        if self._class:
            return [self._class]

        return []

    def __str__(self) -> str:
        return str(self._entity)

    def __repr__(self) -> str:
        return repr_rich(self.__rich__())

    def __rich__(self):
        """Creates a rich representation of the fund."""
        # Summary info table
        info_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        info_table.add_column("Field", style="bold")
        info_table.add_column("Value")

        info_table.add_row("Identifier", self._original_identifier)

        if self._company:
            info_table.add_row("Company CIK", str(self._company.cik))
            if self._company.name:
                info_table.add_row("Company", self._company.name)

        if self._series:
            info_table.add_row("Series ID", self._series.series_id)
            if self._series.name and self._series.name != self._series.series_id:
                info_table.add_row("Series", self._series.name)

        if self._class:
            info_table.add_row("Class ID", self._class.class_id)
            if self._class.ticker:
                info_table.add_row("Ticker", self._class.ticker)

        renderables = [info_table]

        # Share classes table
        classes = self.list_classes()
        if classes:
            classes_table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
            classes_table.add_column("Class ID")
            classes_table.add_column("Name")
            classes_table.add_column("Ticker", style="bold yellow")
            for c in classes:
                classes_table.add_row(
                    c.class_id,
                    c.name if c.name != c.class_id else "",
                    c.ticker or "-",
                )
            renderables.append(classes_table)

        title = self.name or self._original_identifier
        return Panel(
            Group(*renderables),
            title=title,
            subtitle="Fund",
        )
