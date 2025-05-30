"""
Data classes for the Entity package.

This module contains classes for working with entity data, including
addresses, facts, and other structured data from SEC filings.
"""
import re
from functools import cached_property
from typing import List, Dict, Optional, Union, Tuple, Any

import pyarrow as pa
import pyarrow.compute as pc

from edgar.dates import InvalidDateException
from edgar.filtering import filter_by_date
from edgar.formatting import reverse_name
from edgar.core import listify
from edgar.filtering import filter_by_year_quarter, filter_by_form
from edgar.entity.filings import EntityFilings
from edgar.core import log
from edgar.storage import is_using_local_storage

# Module-level import cache for lazy imports
_IMPORT_CACHE = {}


def lazy_import(module_path):
    """
    Lazily import a module or attribute and cache the result to avoid repeated imports.
    
    Args:
        module_path: String path to the module or attribute
        
    Returns:
        The imported module or attribute
    """
    if module_path not in _IMPORT_CACHE:
        parts = module_path.split('.')
        if len(parts) == 1:
            # Simple module import
            _IMPORT_CACHE[module_path] = __import__(module_path)
        else:
            # Import from module (potentially nested)
            module_name = '.'.join(parts[:-1])
            attr_name = parts[-1]

            module = __import__(module_name, fromlist=[attr_name])
            _IMPORT_CACHE[module_path] = getattr(module, attr_name)

    return _IMPORT_CACHE[module_path]


__all__ = [
    'Address',
    'EntityData',
    'CompanyData',
    'preprocess_company',
    'parse_entity_submissions',
    'extract_company_filings_table',
    'create_company_filings',
    'create_default_entity_data'
]


def extract_company_filings_table(filings_json: Dict[str, Any]) -> pa.Table:
    """
    Extract company filings from the json response.
    
    Args:
        filings_json: The JSON data containing filings
        
    Returns:
        A PyArrow Table containing the filings data
    """
    # Import this here to avoid circular imports
    from edgar.core import parse_acceptance_datetime

    # Handle case of no data
    if not filings_json.get('accessionNumber'):
        # Create an empty table with the right schema
        schema = pa.schema([
            ('accession_number', pa.string()),
            ('filing_date', pa.date32()),
            ('reportDate', pa.string()),
            ('acceptanceDateTime', pa.timestamp('us')),
            ('act', pa.string()),
            ('form', pa.string()),
            ('fileNumber', pa.string()),
            ('items', pa.string()),
            ('size', pa.string()),
            ('isXBRL', pa.string()),
            ('isInlineXBRL', pa.string()),
            ('primaryDocument', pa.string()),
            ('primaryDocDescription', pa.string())
        ])
        return pa.Table.from_arrays([[] for _ in range(13)], schema=schema)
    else:
        # Convert acceptanceDateTime string to datetime
        acceptance_datetimes = [
            parse_acceptance_datetime(dt) for dt in filings_json['acceptanceDateTime']
        ]

        fields = {
            'accession_number': filings_json['accessionNumber'],
            'filing_date': pc.cast(pc.strptime(pa.array(filings_json['filingDate']), '%Y-%m-%d', 'us'), pa.date32()),
            'reportDate': filings_json['reportDate'],
            'acceptanceDateTime': acceptance_datetimes,
            'act': filings_json['act'],
            'form': filings_json['form'],
            'fileNumber': filings_json['fileNumber'],
            'items': filings_json['items'],
            'size': filings_json['size'],
            'isXBRL': filings_json['isXBRL'],
            'isInlineXBRL': filings_json['isInlineXBRL'],
            'primaryDocument': filings_json['primaryDocument'],
            'primaryDocDescription': filings_json['primaryDocDescription']
        }

        # Create table using dictionary
        return pa.Table.from_arrays(
            arrays=[pa.array(v) if k not in ['filing_date', 'acceptanceDateTime']
                    else v for k, v in fields.items()],
            names=list(fields.keys())
        )


def create_company_filings(filings_json: Dict[str, Any], cik: int, company_name: str) -> EntityFilings:
    """
    Extract company filings from the json response.
    
    Args:
        filings_json: The JSON data containing filings
        cik: The company CIK
        company_name: The company name
        
    Returns:
        An EntityFilings object containing the filings
    """
    recent_filings = extract_company_filings_table(filings_json['recent'])
    return EntityFilings(recent_filings, cik=cik, company_name=company_name)


def parse_entity_submissions(cjson: Dict[str, Any]) -> 'CompanyData':
    """
    Parse entity submissions from the SEC API.
    
    Args:
        cjson: The JSON data from the SEC submissions API
        
    Returns:
        A CompanyData object representing the entity
    """
    mailing_addr = cjson['addresses']['mailing']
    business_addr = cjson['addresses']['business']
    cik = cjson['cik']
    company_name = cjson["name"]
    former_names = cjson.get('formerNames', [])

    for former_name in former_names:
        former_name['from'] = former_name['from'][:10] if former_name['from'] else former_name['from']
        former_name['to'] = former_name['to'][:10] if former_name['to'] else former_name['to']

    return CompanyData(
        cik=int(cik),
        name=company_name,
        tickers=cjson['tickers'],
        exchanges=cjson['exchanges'],
        sic=cjson['sic'],
        sic_description=cjson['sicDescription'],
        category=cjson['category'].replace("<br>", " | ") if cjson['category'] else None,
        fiscal_year_end=cjson['fiscalYearEnd'],
        entity_type=cjson['entityType'],
        phone=cjson['phone'],
        flags=cjson['flags'],
        mailing_address=Address(
            street1=mailing_addr['street1'],
            street2=mailing_addr['street2'],
            city=mailing_addr['city'],
            state_or_country_desc=mailing_addr['stateOrCountryDescription'],
            state_or_country=mailing_addr['stateOrCountry'],
            zipcode=mailing_addr['zipCode'],
        ),
        business_address=Address(
            street1=business_addr['street1'],
            street2=business_addr['street2'],
            city=business_addr['city'],
            state_or_country_desc=business_addr['stateOrCountryDescription'],
            state_or_country=business_addr['stateOrCountry'],
            zipcode=business_addr['zipCode'],
        ),
        filings=create_company_filings(cjson['filings'], cik=cik, company_name=company_name),
        insider_transaction_for_owner_exists=bool(cjson['insiderTransactionForOwnerExists']),
        insider_transaction_for_issuer_exists=bool(cjson['insiderTransactionForIssuerExists']),
        ein=cjson['ein'],
        description=cjson['description'],
        website=cjson['website'],
        investor_website=cjson['investorWebsite'],
        state_of_incorporation=cjson['stateOfIncorporation'],
        state_of_incorporation_description=cjson['stateOfIncorporationDescription'],
        former_names=former_names,
        files=cjson['filings']['files']
    )


class Address:
    """
    Represents a physical address.
    
    This class is optimized for memory usage and performance.
    """
    __slots__ = ('street1', 'street2', 'city', 'state_or_country', 'zipcode', 'state_or_country_desc', '_str_cache')

    def __init__(self,
                 street1: str,
                 street2: Optional[str],
                 city: str,
                 state_or_country: str,
                 zipcode: str,
                 state_or_country_desc: str
                 ):
        """
        Initialize an Address object.
        
        Args:
            street1: First line of street address
            street2: Second line of street address (optional)
            city: City name
            state_or_country: State or country code
            zipcode: Postal/ZIP code
            state_or_country_desc: Human-readable state or country name
        """
        # Store empty strings instead of None to avoid type checks later
        self.street1: str = street1 or ""
        self.street2: Optional[str] = street2 or ""
        self.city: str = city or ""
        self.state_or_country: str = state_or_country or ""
        self.zipcode: str = zipcode or ""
        self.state_or_country_desc: str = state_or_country_desc or ""
        self._str_cache = None

    @property
    def empty(self) -> bool:
        """Check if the address is empty. Optimized to avoid multiple attribute checks when possible."""
        # Short-circuit on common empty case
        if not self.street1:
            if not self.city and not self.zipcode:
                return True

        # Full check
        return not (self.street1 or self.street2 or self.city or self.state_or_country or self.zipcode)

    def __str__(self):
        """
        Generate a formatted string representation of the address.
        Caches result for repeated calls.
        """
        if self._str_cache is not None:
            return self._str_cache

        if not self.street1:
            self._str_cache = ""
            return ""

        # Build string only once and cache it
        parts = []
        parts.append(self.street1)

        if self.street2:
            parts.append(self.street2)

        parts.append(f"{self.city}, {self.state_or_country_desc} {self.zipcode}")

        self._str_cache = "\n".join(parts)
        return self._str_cache

    def __repr__(self):
        """Generate a string representation suitable for debugging."""
        # Simplified representation that avoids unnecessary string operations
        return f'Address(street1="{self.street1}", street2="{self.street2}", city="{self.city}", zipcode="{self.zipcode}")'

    def to_json(self) -> Dict[str, str]:
        """Convert the address to a JSON-serializable dict."""
        # Direct dictionary creation is faster than multiple assignments
        return {
            'street1': self.street1,
            'street2': self.street2,
            'city': self.city,
            'state_or_country': self.state_or_country,
            'zipcode': self.zipcode,
            'state_or_country_desc': self.state_or_country_desc
        }


class EntityData:
    """
    Container for entity data loaded from SEC submissions API.
    
    This class provides access to entity metadata and filings.
    """

    def __init__(self,
                 cik: int,
                 name: str,
                 tickers: List[str],
                 exchanges: List[str],
                 sic: str,
                 sic_description: str,
                 ein: str,
                 entity_type: str,
                 fiscal_year_end: str,
                 filings: EntityFilings,
                 business_address: Address,
                 mailing_address: Address,
                 state_of_incorporation: str,
                 **kwargs):
        """
        Initialize a new EntityData instance.
        
        Args:
            cik: The CIK number
            name: The entity name
            sic: The Standard Industrial Classification code
            ein: The Employer Identification Number
            fiscal_year_end: The fiscal year end date
            tickers: List of ticker symbols
            exchanges: List of exchanges
            entity_type: The entity type
            filings: The entity's filings
            business_address: The business address
            mailing_address: The mailing address
            state_of_incorporation: The state of incorporation
            **kwargs: Additional attributes
        """
        self.cik: int = cik
        self.name: str = name
        self.sic = sic
        self.sic_description: str = sic_description
        self.ein: str = ein
        self.fiscal_year_end: str = fiscal_year_end
        self.tickers: List[str] = tickers
        self.exchanges: List[str] = exchanges
        self.filings: EntityFilings = filings
        self.entity_type = entity_type
        self.business_address: Address = business_address
        self.mailing_address: Address = mailing_address
        self.state_of_incorporation: str = state_of_incorporation

        # Store all other attributes
        for key, value in kwargs.items():
            setattr(self, key, value)

        # Initialize lazy loading flag
        self._loaded_all_filings: bool = False
        self._files = kwargs.get('files', [])

    def _load_older_filings(self):
        """
        Load older filings that were not included in the initial data.
        
        This method implements the lazy loading behavior of filings.
        When first creating an entity, only the most recent filings are loaded
        to keep API response times fast. When more filings are needed, this
        method will load additional filings from the SEC.
        """
        # If we have no files to load, we're done
        if not self._files:
            return

        # Import locally to avoid circular imports using the lazy import cache
        download_json = lazy_import('edgar.httprequests.download_json')

        # Load additional filings from the SEC
        filing_tables = [self.filings.data]
        for file in self._files:
            submissions = download_json("https://data.sec.gov/submissions/" + file['name'])
            filing_table = extract_company_filings_table(submissions)
            filing_tables.append(filing_table)

        # Combine all filing tables
        combined_tables = pa.concat_tables(filing_tables)

        # Update filings
        EntityFilings = lazy_import('edgar.entity.filings.EntityFilings')
        self.filings = EntityFilings(combined_tables, cik=self.cik, company_name=self.name)

    def get_filings(self,
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
                    trigger_full_load: bool = True
                    ) -> EntityFilings:
        """
        Get entity filings with lazy loading behavior.
        
        Args:
            year: Filter by year(s) (e.g. 2023, [2022, 2023])
            quarter: Filter by quarter(s) (1-4, e.g. 4, [3, 4])
            form: Filter by form type(s)
            accession_number: Filter by accession number(s)
            file_number: Filter by file number(s)
            filing_date: Filter by filing date (YYYY-MM-DD or range)
            date: Alias for filing_date
            amendments: Whether to include amendments (default: True)
            is_xbrl: Filter by XBRL status
            is_inline_xbrl: Filter by inline XBRL status
            sort_by: Sort criteria
            trigger_full_load: Whether to load all historical filings if not already loaded
            
        Returns:
            Filtered filings
        """

        # Lazy loading behavior
        if not self._loaded_all_filings and not is_using_local_storage() and trigger_full_load:
            self._load_older_filings()
            self._loaded_all_filings = True

        # Get filings data
        company_filings = self.filings.data

        # Filter by year/quarter first (most selective)
        if year is not None:
            company_filings = filter_by_year_quarter(company_filings, year, quarter)

        # Filter by accession number
        if accession_number:
            company_filings = company_filings.filter(
                pc.is_in(company_filings['accession_number'], pa.array(listify(accession_number))))
            if len(company_filings) >= 1:
                # We found the filing(s)
                return EntityFilings(company_filings, cik=self.cik, company_name=self.name)

        # Filter by form (with amendments support)
        if form:
            company_filings = filter_by_form(company_filings, form, amendments)

        # Filter by file number
        if file_number:
            company_filings = company_filings.filter(
                pc.is_in(company_filings['fileNumber'], pa.array(listify(file_number))))

        # Filter by XBRL status
        if is_xbrl is not None:
            company_filings = company_filings.filter(pc.equal(company_filings['isXBRL'], int(is_xbrl)))

        # Filter by inline XBRL status
        if is_inline_xbrl is not None:
            company_filings = company_filings.filter(pc.equal(company_filings['isInlineXBRL'], int(is_inline_xbrl)))

        # Filter by filing date
        filing_date = filing_date or date
        if filing_date:
            try:
                company_filings = filter_by_date(company_filings, filing_date, 'filing_date')
            except InvalidDateException as e:
                log.error(e)
                return None

        # Sort filings
        if sort_by:
            company_filings = company_filings.sort_by(sort_by)

        # Return filtered filings
        return EntityFilings(company_filings, cik=self.cik, company_name=self.name)

    @property
    def is_company(self) -> bool:
        """Determine if this entity is a company."""
        return not self.is_individual

    @cached_property
    def is_individual(self) -> bool:
        """
        Determine if this entity is an individual.
        
        Tricky logic to detect if a company is an individual or a company.
        Companies have an ein, individuals do not. Oddly Warren Buffet has an EIN but not a state of incorporation
        There may be other edge cases.
        If you have a ticker or exchange you are a company.
        """
        # Import locally using the lazy import cache
        has_company_filings = lazy_import('edgar.entity.core.has_company_filings')

        if len(self.tickers) > 0 or len(self.exchanges) > 0:
            return False
        elif hasattr(self,
                     'state_of_incorporation') and self.state_of_incorporation is not None and self.state_of_incorporation != '':
            return False
        elif hasattr(self, 'entity_type') and self.entity_type not in ['', 'other']:
            return False
        elif has_company_filings(self.filings.data['form']):
            if self.cik == 315090:  # The Warren Buffett exception
                return True
            return False
        elif not hasattr(self, 'ein') or self.ein is None or self.ein == "000000000":
            return True
        else:
            return False

    def __str__(self):
        return f"EntityData({self.name} [{self.cik}])"

    def __repr__(self):
        repr_rich = lazy_import('edgar.richtools.repr_rich')
        return repr_rich(self.__rich__())

    def __rich__(self):
        """Creates a rich representation of the entity with clear information hierarchy."""
        # Use lazy imports for rich components
        box = lazy_import('rich.box')
        Group = lazy_import('rich.console.Group')
        Columns = lazy_import('rich.columns.Columns')
        Padding = lazy_import('rich.padding.Padding')
        Panel = lazy_import('rich.panel.Panel')
        Table = lazy_import('rich.table.Table')
        Text = lazy_import('rich.text.Text')
        find_ticker = lazy_import('edgar.reference.tickers.find_ticker')
        zip_longest = lazy_import('itertools.zip_longest')
        datefmt = lazy_import('edgar.formatting.datefmt')
        reverse_name = lazy_import('edgar.formatting.reverse_name')

        # Primary entity identification section
        if self.is_company:
            ticker = find_ticker(self.cik)
            ticker = f"{ticker}" if ticker else ""

            # The title of the panel
            entity_title = Text.assemble("🏢 ",
                                         (self.display_name, "bold green"),
                                         " ",
                                         (f"[{self.cik}] ", "dim"),
                                         (ticker, "bold yellow")
                                         )
        else:
            entity_title = Text.assemble("👤", (self.display_name, "bold green"))

        # Primary Information Table
        main_info = Table(box=box.SIMPLE_HEAVY, show_header=False, padding=(0, 1))
        main_info.add_column("Row", style="")  # Single column for the entire row

        row_parts = []
        row_parts.extend([Text("CIK", style="grey60"), Text(str(self.cik), style="bold deep_sky_blue3")])
        if hasattr(self, 'entity_type') and self.entity_type:
            if self.is_individual:
                row_parts.extend([Text("Type", style="grey60"),
                                  Text("Individual", style="bold yellow")])
            else:
                row_parts.extend([Text("Type", style="grey60"),
                                  Text(self.entity_type.title(), style="bold yellow"),
                                  Text(self._get_operating_type_emoticon(self.entity_type), style="bold yellow")])
        main_info.add_row(*row_parts)

        # Detailed Information Table
        details = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
        details.add_column("Category")
        details.add_column("Industry")
        details.add_column("Fiscal Year End")

        details.add_row(
            getattr(self, 'category', '-') or "-",
            f"{getattr(self, 'sic', '')}: {getattr(self, 'sic_description', '')}" if hasattr(self,
                                                                                             'sic') and self.sic else "-",
            self._format_fiscal_year_date(getattr(self, 'fiscal_year_end', '')) if hasattr(self,
                                                                                           'fiscal_year_end') and self.fiscal_year_end else "-"
        )

        # Combine main_info and details in a single panel
        if self.is_company:
            basic_info_renderables = [main_info, details]
        else:
            basic_info_renderables = [main_info]
        basic_info_panel = Panel(
            Group(*basic_info_renderables),
            title="📋 Entity",
            border_style="grey50"
        )

        # Trading Information
        if self.tickers and self.exchanges:
            trading_info = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
            trading_info.add_column("Exchange")
            trading_info.add_column("Symbol", style="bold yellow")

            for exchange, ticker in zip_longest(self.exchanges, self.tickers, fillvalue="-"):
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
            hasattr(self, 'phone') and self.phone,
            hasattr(self, 'website') and self.website,
            hasattr(self, 'investor_website') and self.investor_website
        ])

        if hasattr(self, 'website') and self.website:
            contact_info.add_row("Website", self.website)
        if hasattr(self, 'investor_website') and self.investor_website:
            contact_info.add_row("Investor Relations", self.investor_website)
        if hasattr(self, 'phone') and self.phone:
            contact_info.add_row("Phone", self.phone)

        # Three-column layout for addresses and contact info
        contact_renderables = []
        if hasattr(self, 'business_address') and not self.business_address.empty:
            contact_renderables.append(Panel(
                Text(str(self.business_address)),
                title="🏢 Business Address",
                border_style="grey50"
            ))
        if hasattr(self, 'mailing_address') and not self.mailing_address.empty:
            contact_renderables.append(Panel(
                Text(str(self.mailing_address)),
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
        if hasattr(self, 'former_names') and self.former_names:
            former_names_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
            former_names_table.add_column("Previous Company Names")
            former_names_table.add_column("")  # Empty column for better spacing

            for former_name in self.former_names:
                from_date = datefmt(former_name['from'], '%B %Y')
                to_date = datefmt(former_name['to'], '%B %Y')
                former_names_table.add_row(Text(former_name['name'], style="italic"), f"{from_date} to {to_date}")

            former_names_panel = Panel(
                former_names_table,
                title="📜 Former Names",
                border_style="grey50"
            )

        # Combine all sections using Group
        if self.is_company:
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

    @property
    def display_name(self) -> str:
        """Reverse the name if it is a company"""
        if self.is_company:
            return self.name

        return reverse_name(self.name)

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


class CompanyData(EntityData):
    """
    Specialized container for company data loaded from SEC submissions API.
    
    This is a specialized version of EntityData specifically for companies.
    It adds company-specific methods and properties.
    """

    def __init__(self, **kwargs):
        """Construct a new CompanyData object."""
        super().__init__(**kwargs)

    @property
    def industry(self) -> str:
        """Get the industry description for this company."""
        return getattr(self, 'sic_description', '')

    def get_ticker(self) -> Optional[str]:
        """Get the primary ticker for this company."""
        if self.tickers and len(self.tickers) > 0:
            return self.tickers[0]
        return None

    def __str__(self):
        ticker = self.get_ticker()
        ticker_str = f" - {ticker}" if ticker else ""
        return f"CompanyData({self.name} [{self.cik}]{ticker_str})"


# Compile regex patterns for better performance
_COMPANY_TYPES_PATTERN = re.compile(r"(L\.?L\.?C\.?|Inc\.?|Ltd\.?|L\.?P\.?|/[A-Za-z]{2,3}/?| CORP(ORATION)?|PLC| AG)$",
                                    re.IGNORECASE)
_PUNCTUATION_PATTERN = re.compile(r"\.|,")


def preprocess_company(company: str) -> str:
    """preprocess the company name for storing in the search index"""
    comp = _COMPANY_TYPES_PATTERN.sub("", company.lower())
    comp = _PUNCTUATION_PATTERN.sub("", comp)
    return comp.strip()


def create_default_entity_data(cik: int) -> 'EntityData':
    """
    Create a default EntityData instance for when entity data cannot be found.
    
    Args:
        cik: The CIK number to use for the entity
        
    Returns:
        A minimal EntityData instance with default values
    """
    # Create a minimal EntityData with blank/empty values
    empty_address = Address(
        street1="",
        street2="",
        city="",
        state_or_country="",
        zipcode="",
        state_or_country_desc=""
    )

    # Import using lazy import cache
    empty_company_filings = lazy_import('edgar.entity.filings.empty_company_filings')

    # Use the CIK as the name since we don't know the real name
    name = f"Entity {cik}"

    # Create a minimal entity data
    return EntityData(
        cik=cik,
        name=name,
        tickers=[],
        exchanges=[],
        filings=empty_company_filings(cik, name),
        business_address=empty_address,
        mailing_address=empty_address,
        category="",
        sic=None,
        sic_description="",
        fiscal_year_end="",
        entity_type="",
        phone="",
        flags="",
        insider_transaction_for_owner_exists=False,
        insider_transaction_for_issuer_exists=False,
        ein="",
        description="",
        website="",
        investor_website="",
        state_of_incorporation="",
        state_of_incorporation_description="",
        former_names=[],
        files=[]
    )
