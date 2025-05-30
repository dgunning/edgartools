"""
Core entity classes for working with SEC filings.

This module provides the main classes for interacting with SEC entities,
including companies, funds, and individuals.
"""
from abc import ABC, abstractmethod
from functools import cached_property
from functools import lru_cache
from typing import List, Dict, Optional, Union, Tuple, Any, TypeVar, Iterable

from edgar._filings import Filings
from edgar.company_reports import TenK, TenQ
from edgar.formatting import reverse_name, datefmt
from edgar.entity.data import Address, EntityData, CompanyData
# Import from our new modules
from edgar.entity.filings import EntityFacts
from edgar.entity.tickers import get_icon_from_ticker
from edgar.financials import Financials
from edgar.reference.tickers import find_cik
from edgar.richtools import repr_rich

# Performance optimization: use set for O(1) lookups
COMPANY_FORMS = {
    # Registration statements
    "S-1", "S-3", "S-4", "S-8", "S-11",
    # Foreign issuers registration forms
    "F-1", "F-3", "F-4", "F-6", "F-7", "F-8", "F-9", "F-10", "F-80",
    # Foreign form amendments and effectiveness
    "F-6EF", "F-6 POS", "F-3ASR", "F-4MEF", "F-10EF", "F-3D", "F-3MEF",
    # Exchange Act registration
    "10-12B", "10-12G",
    # Periodic reports
    "10-K", "10-Q", "10-K/A", "10-Q/A",
    "20-F", "40-F",  # Foreign issuers
    "11-K",  # Employee benefit plans
    # Current reports
    "8-K", "6-K",
    # Proxy materials
    "DEF 14A", "PRE 14A", "DEFA14A", "DEFM14A",
    # Other corporate filings
    "424B1", "424B2", "424B3", "424B4", "424B5",
    "ARS", "NT 10-K", "NT 10-Q",
    "SC 13D", "SC 13G", "SC TO-I", "SC TO-T",
    "SD", "PX14A6G",
    # Specialized corporate filings
    "N-CSR", "N-Q", "N-MFP", "N-CEN",
    "X-17A-5", "17-H",
    "TA-1", "TA-2",
    "ATS-N",
    # Corporate disclosures
    "EFFECT", "FWP", "425", "CB",
    "POS AM", "CORRESP", "UPLOAD"
}

def has_company_filings(filings_form_array: 'pyarrow.ChunkedArray', max_filings: int = 50) -> bool:
    """
    Efficiently check if any form in the PyArrow ChunkedArray matches company-only forms.
    Limited to checking the first max_filings entries for performance.
    
    Args:
        filings_form_array: PyArrow ChunkedArray containing form values
        max_filings: Maximum number of filings to check
        
    Returns:
        True if any form matches a company form, False otherwise
    """

    # Early exit for empty arrays
    if filings_form_array.null_count == filings_form_array.length:
        return False

    # Handle case with fewer than max_filings
    total_filings = filings_form_array.length()
    filings_to_check = min(total_filings, max_filings)

    # Track how many we've checked so far
    checked_count = 0

    # Process chunks in the ChunkedArray until we hit our limit
    for chunk in filings_form_array.chunks:
        chunk_size = len(chunk)

        # If this chunk would exceed our limit, slice it
        if checked_count + chunk_size > filings_to_check:
            # Only check remaining forms needed to reach filings_to_check
            remaining = filings_to_check - checked_count
            sliced_chunk = chunk.slice(0, remaining)

            # Use safer iteration over array values
            for i in range(len(sliced_chunk)):
                # Get value safely, handling nulls
                val = sliced_chunk.take([i]).to_pylist()[0]
                if val is not None and val in COMPANY_FORMS:
                    return True
        else:
            # Process full chunk safely
            for val in chunk.to_pylist():
                if val is not None and val in COMPANY_FORMS:
                    return True

        # Update count of checked filings
        if checked_count + chunk_size > filings_to_check:
            checked_count += (filings_to_check - checked_count)
        else:
            checked_count += chunk_size

        # Stop if we've checked enough
        if checked_count >= filings_to_check:
            break

    return False

# Type variables for better type annotations
T = TypeVar('T')

def normalize_cik(cik_or_identifier: Union[str, int]) -> int:
    """
    Normalize a CIK to an integer by removing leading zeros.
    
    Args:
        cik_or_identifier: CIK as string or int
    
    Returns:
        Normalized CIK as an integer
    """
    if isinstance(cik_or_identifier, int):
        return cik_or_identifier
    
    # If it's a string that represents an int (like '0000320193')
    if isinstance(cik_or_identifier, str) and cik_or_identifier.isdigit():
        return int(cik_or_identifier)
    
    # If it's another type of string (like a ticker), we can't normalize it
    # This should be handled by the caller
    return cik_or_identifier

__all__ = [
    'SecFiler',
    'Entity',
    'Company',
    'EntityData',
    'CompanyData',
    'get_entity',
    'get_company',
    'NoCompanyFactsFound',
    'has_company_filings',
    'COMPANY_FORMS',
]

class SecFiler(ABC):
    """
    Abstract base class for all SEC filing entities.
    
    This is the root of the entity hierarchy and defines the common interface
    that all entity types must implement.
    """
    
    @abstractmethod
    def get_filings(self, **kwargs) -> Filings:
        """Get filings for this entity."""
        pass
        
    @abstractmethod
    def get_facts(self) -> Optional[EntityFacts]:
        """Get structured facts about this entity."""
        pass
    
    @property
    @abstractmethod
    def cik(self) -> int:
        """Get the CIK number for this entity."""
        pass
    
    @property
    @abstractmethod
    def data(self) -> 'EntityData':
        """Get detailed data for this entity."""
        pass


class Entity(SecFiler):
    """
    Represents any entity that files with the SEC.
    
    This is the base concrete implementation that can be used directly
    or specialized for specific entity types.
    """
    
    def __init__(self, cik_or_identifier: Union[str, int]):
        # If it's a ticker, convert to CIK first
        if isinstance(cik_or_identifier, str) and not cik_or_identifier.isdigit():
            cik = find_cik(cik_or_identifier)
            if cik is None:
                self._cik = -999999999
            else:
                self._cik = cik
        else:
            self._cik = normalize_cik(cik_or_identifier)

        self._data = None
    
    @property
    def cik(self) -> int:
        """Get the CIK number for this entity."""
        return self._cik

    @property
    def name(self):
        """Get the name of the company."""
        if hasattr(self.data, 'name'):
            return self.data.name
        return None

    @cached_property
    def display_name(self) -> str:
        """Reverse the name if it is a company"""
        if self.is_company:
            return self.name
        return reverse_name(self.name)
    
    @cached_property
    def data(self) -> 'EntityData':
        """Get detailed data for this entity."""
        if self._data is None:
            # Import locally to avoid circular imports
            from edgar.entity.submissions import get_entity_submissions
            
            # get_entity_submissions returns the EntityData directly
            entity_data = get_entity_submissions(self.cik)
            
            if entity_data:
                self._data = entity_data
                self._data._not_found = False
            else:
                # Instead of raising an error, create a default EntityData
                #log.warning(f"Could not find entity data for CIK {self.cik}, using placeholder data")
                from edgar.entity.data import create_default_entity_data
                self._data = create_default_entity_data(self.cik)
                self._data._not_found = True
        return self._data

    def mailing_address(self) -> Optional[Address]:
        """Get the mailing address of the entity."""
        if hasattr(self.data, 'mailing_address') and self.data.mailing_address:
            return self.data.mailing_address

    def business_address(self) -> Optional[Address]:
        """Get the business address of the entity."""
        if hasattr(self.data, 'business_address') and self.data.business_address:
            return self.data.business_address

    
    @property
    def not_found(self) -> bool:
        """
        Check if the entity data was not found.
        
        Returns:
            True if the entity data could not be found, False otherwise
        """
        if not hasattr(self, '_data') or self._data is None:
            # We haven't loaded the data yet, so we don't know if it's not found
            # Loading the data will set the not_found flag
            _ = self.data
            
        return getattr(self._data, '_not_found', False)

    @property
    def is_company(self) -> bool:
        """
        Check if this entity is a company.

        Returns:
            True if the entity is a company, False otherwise
        """
        return hasattr(self.data, 'is_company') and self.data.is_company

    def is_individual(self) -> bool:
        """
        Check if this entity is an individual.

        Returns:
            True if the entity is an individual, False otherwise
        """
        return not self.is_company

    
    def get_filings(self, 
                   *,
                   year: Union[int, List[int]] = None,
                   quarter: Union[int, List[int]] = None,
                   form: Union[str, List] = None,
                   accession_number: Union[str, List] = None,
                   file_number: Union[str, List] = None,
                   filing_date: Union[str, Tuple[str, str]] = None,
                   date: Union[str, Tuple[str, str]] = None,
                   amendments: bool = True,
                   is_xbrl: bool = None,
                   is_inline_xbrl: bool = None,
                   sort_by: Union[str, List[Tuple[str, str]]] = None,
                   trigger_full_load: bool = True) -> Filings:
        """
        Get the entity's filings and optionally filter by multiple criteria.
        
        This method has a special behavior for loading filings. When first called,
        it only loads the most recent filings. If trigger_full_load=True, it will 
        automatically fetch all historical filings from the SEC (potentially making 
        multiple API calls) as needed.
        
        Args:
            year: The year or list of years to filter by (e.g. 2023, [2022, 2023])
            quarter: The quarter or list of quarters to filter by (1-4, e.g. 4, [3, 4])
            form: The form as a string e.g. '10-K' or List of strings ['10-Q', '10-K']
            accession_number: The accession number that identifies a filing
            file_number: The file number e.g. 001-39504
            filing_date: Filter by filing date (YYYY-MM-DD or range)
            date: Alias for filing_date
            amendments: Whether to include amendments (default: True)
            is_xbrl: Whether the filing is XBRL
            is_inline_xbrl: Whether the filing is Inline XBRL
            sort_by: Sort criteria
            trigger_full_load: Whether to load all historical filings if not already loaded
            
        Returns:
            Filtered filings matching the criteria
        """
        # Simply delegate to the EntityData implementation
        # This preserves the lazy-loading behavior while keeping the API clean
        return self.data.get_filings(
            year=year,
            quarter=quarter,
            form=form,
            accession_number=accession_number,
            file_number=file_number,
            filing_date=filing_date or date,
            amendments=amendments,
            is_xbrl=is_xbrl,
            is_inline_xbrl=is_inline_xbrl,
            sort_by=sort_by,
            trigger_full_load=trigger_full_load
        )
        
    def get_facts(self) -> Optional[EntityFacts]:
        """Get structured facts about this entity."""
        try:
            return get_company_facts(self.cik)
        except NoCompanyFactsFound:
            return None
    
    def latest(self, form: str, n=1):
        """Get the latest filing(s) for a given form."""
        return self.get_filings(form=form, trigger_full_load=False).latest(n)
    
    def __str__(self):
        if hasattr(self, 'data'):
            return f"Entity({self.data.name} [{self.cik}])"
        return f"Entity(CIK={self.cik})"

    def __rich__(self):
        return self.data.__rich__()
    
    def __repr__(self):
        return repr_rich(self.__rich__())
        
    def __bool__(self):
        """
        Allow truthiness check for entities.
        
        Returns False if the entity doesn't exist (has a sentinel CIK value or not_found is True).
        This enables code patterns like: `if company: do_something()`
        """
        # Check for sentinel CIK value (-999999999) or not_found flag
        return self.cik != -999999999 and not self.not_found


class Company(Entity):
    """
    Represents a public company that files with the SEC.
    
    Provides company-specific functionality like financial statements,
    ticker lookup, etc.
    """
    
    def __init__(self, cik_or_ticker: Union[str, int]):


        super().__init__(cik_or_ticker)
    
    @property
    def data(self) -> 'EntityData':  # We'll return the base type to simplify
        """Get detailed data for this company."""
        # For simplicity, return the base EntityData
        # Type checkers will still see this as a CompanyData due to the annotation
        return super().data

    @property
    def tickers(self):
        """Get all ticker symbols for this company."""
        if hasattr(self.data, 'tickers'):
            return self.data.tickers
        return []

    def get_ticker(self) -> Optional[str]:
        """Get the primary ticker symbol for this company."""
        if self.data and self.data.tickers and len(self.data.tickers) > 0:
            return self.data.tickers[0]
        return None

    def get_exchanges(self ):
        """Get all exchanges for this company."""
        if hasattr(self.data, 'exchanges'):
            return self.data.exchanges
        return []
    
    def get_financials(self) -> Optional[Financials]:
        """Get financial statements for this company."""
        tenk_filing = self.latest_tenk
        if tenk_filing is not None:
            return tenk_filing.financials
        return None
    
    def get_quarterly_financials(self) -> Optional[Financials]:
        """Get quarterly financial statements for this company."""
        tenq_filing = self.latest_tenq
        if tenq_filing is not None:
            return tenq_filing.financials
        return None

    @property
    def fiscal_year_end(self):
        """Get the fiscal year end date for this company."""
        if hasattr(self.data, 'fiscal_year_end'):
            return self.data.fiscal_year_end
        return None

    @property
    def sic(self):
        """Get the SIC code for this company."""
        if hasattr(self.data, 'sic'):
            return self.data.sic
        return None

    @property
    def industry(self):
        """Get the industry description for this company."""
        if hasattr(self.data, 'sic_description'):
            return self.data.sic_description
        return None
    
    @property
    def latest_tenk(self) -> Optional[TenK]:
        """Get the latest 10-K filing for this company."""
        latest_10k = self.get_filings(form='10-K', trigger_full_load=False).latest()
        if latest_10k is not None:
            return latest_10k.obj()
        return None

    @property
    def latest_tenq(self) -> Optional[TenQ]:
        """Get the latest 10-Q filing for this company."""
        latest_10q = self.get_filings(form='10-Q', trigger_full_load=False).latest()
        if latest_10q is not None:
            return latest_10q.obj()
        return None

    def get_icon(self):
        return get_icon_from_ticker(self.tickers[0])
    
    def __str__(self):
        ticker = self.get_ticker()
        ticker_str = f" - {ticker}" if ticker else ""
        if hasattr(self, 'data'):
            return f"Company({self.data.name} [{self.cik}]{ticker_str})"
        return f"Company(CIK={self.cik}{ticker_str})"
        
    def __repr__(self):
        # Delegate to the rich representation for consistency with the old implementation
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())
        
    def __rich__(self):
        """Creates a rich representation of the company with detailed information."""
        # Import rich components locally to prevent circular imports
        from rich import box
        from rich.console import Group
        from rich.columns import Columns
        from rich.padding import Padding
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        
        # The title of the panel
        ticker = self.get_ticker()
        if self.data.is_company:
            entity_title = Text.assemble("🏢 ",
                                  (self.data.name, "bold green"),
                                  " ",
                                  (f"[{self.cik}] ", "dim"),
                                  (ticker if ticker else "", "bold yellow")
                                  )
        else:
            entity_title = Text.assemble("👤", (self.data.name, "bold green"))

        # Primary Information Table
        main_info = Table(box=box.SIMPLE_HEAVY, show_header=False, padding=(0, 1))
        main_info.add_column("Row", style="")  # Single column for the entire row

        row_parts = []
        row_parts.extend([Text("CIK", style="grey60"), Text(str(self.cik), style="bold deep_sky_blue3")])
        if hasattr(self.data, 'entity_type') and self.data.entity_type:
            if self.data.is_individual:
                row_parts.extend([Text("Type", style="grey60"),
                              Text("Individual", style="bold yellow")])
            else:
                row_parts.extend([Text("Type", style="grey60"),
                              Text(self.data.entity_type.title(), style="bold yellow"),
                              Text(self._get_operating_type_emoticon(self.data.entity_type), style="bold yellow")])
        main_info.add_row(*row_parts)

        # Detailed Information Table
        details = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
        details.add_column("Category")
        details.add_column("Industry")
        details.add_column("Fiscal Year End")

        details.add_row(
            getattr(self.data, 'category', '-') or "-",
            f"{getattr(self.data, 'sic', '')}: {getattr(self.data, 'sic_description', '')}" if hasattr(self.data, 'sic') and self.data.sic else "-",
            self._format_fiscal_year_date(getattr(self.data, 'fiscal_year_end', '')) if hasattr(self.data, 'fiscal_year_end') and self.data.fiscal_year_end else "-"
        )

        # Combine main_info and details in a single panel
        if self.data.is_company:
            basic_info_renderables = [main_info, details]
        else:
            basic_info_renderables = [main_info]
        basic_info_panel = Panel(
            Group(*basic_info_renderables),
            title="📋 Entity",
            border_style="grey50"
        )

        # Trading Information
        if hasattr(self.data, 'tickers') and hasattr(self.data, 'exchanges') and self.data.tickers and self.data.exchanges:
            trading_info = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
            trading_info.add_column("Exchange")
            trading_info.add_column("Symbol", style="bold yellow")

            for exchange, ticker in zip(self.data.exchanges, self.data.tickers):
                trading_info.add_row(exchange, ticker)

            trading_panel = Panel(
                trading_info,
                title="📈 Exchanges",
                border_style="grey50"
            )
        else:
            trading_panel = Panel(
                Text("No trading information available", style="grey58"),
                title="📈 Trading Information",
                border_style="grey50"
            )

        # Contact Information
        contact_info = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        contact_info.add_column("Label", style="bold grey70")
        contact_info.add_column("Value")

        has_contact_info = any([
            hasattr(self.data, 'phone') and self.data.phone, 
            hasattr(self.data, 'website') and self.data.website, 
            hasattr(self.data, 'investor_website') and self.data.investor_website
        ])
        
        if hasattr(self.data, 'website') and self.data.website:
            contact_info.add_row("Website", self.data.website)
        if hasattr(self.data, 'investor_website') and self.data.investor_website:
            contact_info.add_row("Investor Relations", self.data.investor_website)
        if hasattr(self.data, 'phone') and self.data.phone:
            contact_info.add_row("Phone", self.data.phone)

        # Three-column layout for addresses and contact info
        contact_renderables = []
        if hasattr(self.data, 'business_address') and not self.data.business_address.empty:
            contact_renderables.append(Panel(
                Text(str(self.data.business_address)),
                title="🏢 Business Address",
                border_style="grey50"
            ))
        if hasattr(self.data, 'mailing_address') and not self.data.mailing_address.empty:
            contact_renderables.append(Panel(
                Text(str(self.data.mailing_address)),
                title="📫 Mailing Address",
                border_style="grey50"
            ))
        if has_contact_info:
            contact_renderables.append(Panel(
                contact_info,
                title="📞 Contact Information",
                border_style="grey50"
            ))

        # Former Names Table (if any exist)
        former_names_panel = None
        if hasattr(self.data, 'former_names') and self.data.former_names:

            
            former_names_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
            former_names_table.add_column("Previous Company Names")
            former_names_table.add_column("")  # Empty column for better spacing

            for former_name in self.data.former_names:
                from_date = datefmt(former_name['from'], '%B %Y')
                to_date = datefmt(former_name['to'], '%B %Y')
                former_names_table.add_row(Text(former_name['name'], style="italic"), f"{from_date} to {to_date}")

            former_names_panel = Panel(
                former_names_table,
                title="📜 Former Names",
                border_style="grey50"
            )

        # Combine all sections using Group
        if self.data.is_company:
            content_renderables = [Padding("", (1, 0, 0, 0)), basic_info_panel, trading_panel]
            if len(contact_renderables):
                contact_and_addresses = Columns(contact_renderables, equal=True, expand=True)
                content_renderables.append(contact_and_addresses)
            if former_names_panel:
                content_renderables.append(former_names_panel)
        else:
            content_renderables = [Padding("", (1, 0, 0, 0)), basic_info_panel]
            if len(contact_renderables):
                contact_and_addresses = Columns(contact_renderables, equal=True, expand=True)
                content_renderables.append(contact_and_addresses)

        content = Group(*content_renderables)

        # Create the main panel
        return Panel(
            content,
            title=entity_title,
            subtitle="SEC Entity Data",
            border_style="grey50"
        )
    
    @staticmethod
    def _get_operating_type_emoticon(entity_type: str) -> str:
        """
        Generate a meaningful single-width symbol based on the SEC entity type.
        All symbols are chosen to be single-width to work well with rich borders.

        Args:
            entity_type (str): The SEC entity type (case-insensitive)

        Returns:
            str: A single-width symbol representing the entity type
        """
        symbols = {
            "operating": "○",  # Circle for active operations
            "subsidiary": "→",  # Arrow showing connection to parent
            "inactive": "×",  # Cross for inactive
            "holding company": "■",  # Square for solid corporate structure
            "investment company": "$",  # Dollar for investment focus
            "investment trust": "$",  # Dollar for investment focus
            "shell": "□",  # Empty square for shell
            "development stage": "∆",  # Triangle for growth/development
            "financial services": "¢",  # Cent sign for financial services
            "reit": "⌂",  # House symbol
            "spv": "◊",  # Diamond for special purpose
            "joint venture": "∞"  # Infinity for partnership
        }

        # Clean input: convert to lowercase and strip whitespace
        cleaned_type = entity_type.lower().strip()

        # Handle some common variations
        if "investment" in cleaned_type:
            return symbols["investment company"]
        if "real estate" in cleaned_type or "reit" in cleaned_type:
            return symbols["reit"]

        # Return default question mark if type not found
        return symbols.get(cleaned_type, "")
    
    @staticmethod
    def _format_fiscal_year_date(date_str):
        """Format fiscal year end date in a human-readable format."""
        if not date_str:
            return "-"
            
        # Dictionary of months
        months = {
            "01": "Jan", "02": "Feb", "03": "Mar",
            "04": "Apr", "05": "May", "06": "Jun",
            "07": "Jul", "08": "Aug", "09": "Sep",
            "10": "Oct", "11": "Nov", "12": "Dec"
        }

        # Extract month and day
        month = date_str[:2]
        if month not in months:
            return date_str
            
        try:
            day = str(int(date_str[2:]))  # Remove leading zero
            return f"{months[month]} {day}"
        except (ValueError, IndexError):
            return date_str


class NoCompanyFactsFound(Exception):
    """Exception raised when company facts cannot be found."""
    def __init__(self, cik: int):
        super().__init__()
        self.message = f"No company facts found for CIK {cik}"


# Factory functions for backward compatibility

def get_entity(cik_or_identifier: Union[str, int]) -> Entity:
    """
    Get any SEC filing entity by CIK or identifier.
    
    Args:
        cik_or_identifier: CIK number (as int or str) or other identifier
        
    Returns:
        Entity instance
    """
    return Entity(cik_or_identifier)


def get_company(cik_or_ticker: Union[str, int]) -> Company:
    """
    Get a public company by CIK or ticker.
    
    Args:
        cik_or_ticker: CIK number or ticker symbol
        
    Returns:
        Company instance
    """
    return Company(cik_or_ticker)


def public_companies() -> Iterable[Company]:
    """
    Iterator over all known public companies.
    
    Returns:
        Iterable of Company objects
    """
    from edgar.reference.tickers import get_cik_tickers
    
    df = get_cik_tickers()
    for _, row in df.iterrows():
        c = Company(row.cik)
        yield c


# Re-export necessary functions from the original entities.py
# This will be necessary during the transition period

# Functions from the original entities.py that we still need
@lru_cache(maxsize=32)
def download_entity_submissions_from_sec(cik: int) -> Optional[Dict[str, Any]]:
    """
    Get the entity filings for a given cik.
    
    Args:
        cik: The company CIK
        
    Returns:
        Optional[Dict[str, Any]]: The entity submissions JSON data, or None if not found
    """
    # Import here to avoid circular imports
    from edgar.entity.submissions import download_entity_submissions_from_sec as _download
    return _download(cik)


def parse_entity_submissions(submissions_json: Dict[str, Any]) -> 'EntityData':
    """
    Parse the entity submissions JSON data.
    
    Args:
        submissions_json: The JSON data from the SEC submissions API
        
    Returns:
        EntityData: The parsed entity data
    """
    # Import here to avoid circular imports
    from edgar.entity.data import parse_entity_submissions as _parse
    return _parse(submissions_json)


@lru_cache(maxsize=32)
def get_company_facts(cik: int) -> Optional[EntityFacts]:
    """
    Get company facts from the SEC.
    
    Args:
        cik: The company CIK
        
    Returns:
        Optional[EntityFacts]: The company facts, or None if not found
    """
    # Import here to avoid circular imports
    from edgar.entity.facts import get_company_facts as _get_facts
    return _get_facts(cik)