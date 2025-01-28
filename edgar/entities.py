import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache, cached_property
from itertools import zip_longest
from typing import List, Dict, Optional, Union, Tuple, Any

import httpx
import numpy as np
import orjson as json
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
from rich import box
from rich.columns import Columns
from rich.console import Group
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table, Column
from rich.text import Text

from edgar._filings import Filing, Filings, PagingState
from edgar.company_reports import TenK, TenQ
from edgar.core import (log, Result, display_size, listify,
                        filter_by_date, IntString, InvalidDateException, reverse_name,
                        parse_acceptance_datetime, datefmt)
from edgar.storage import is_using_local_storage, get_edgar_data_directory
from edgar.financials import Financials
from edgar.httprequests import download_json, download_text
from edgar.reference.forms import describe_form
from edgar.reference.tickers import get_company_tickers, get_icon_from_ticker, find_cik
from edgar.richtools import df_to_rich_table, repr_rich
from edgar.search.datasearch import FastSearch, company_ticker_preprocess, company_ticker_score

__all__ = [
    'Address',
    'Entity',
    'EntityFacts',
    'EntityData',
    'Company',
    'CompanyData',
    'get_concept',
    'get_entity',
    'CompanyFacts',
    'CompanyFiling',
    'find_company',
    'CompanyFilings',
    'CompanyConcept',
    'CompanySearchResults',
    'CompanySearchIndex',
    'get_company_facts',
    'get_company_tickers',
    'get_entity_submissions',
    'empty_company_filings',
    'parse_entity_submissions',
    'get_ticker_to_cik_lookup',
    'get_cik_lookup_data'
]


class Address:
    def __init__(self,
                 street1: str,
                 street2: Optional[str],
                 city: str,
                 state_or_country: str,
                 zipcode: str,
                 state_or_country_desc: str
                 ):
        self.street1: str = street1
        self.street2: Optional[str] = street2
        self.city: str = city
        self.state_or_country: str = state_or_country
        self.zipcode: str = zipcode
        self.state_or_country_desc: str = state_or_country_desc

    @property
    def empty(self):
        return not self.street1 and not self.street2 and not self.city and not self.state_or_country and not self.zipcode

    def __str__(self):
        if not self.street1:
            return ""
        address_format = "{street1}\n"
        if self.street2:
            address_format += "{street2}\n"
        address_format += "{city}, {state_or_country} {zipcode}"

        return address_format.format(
            street1=self.street1,
            street2=self.street2,
            city=self.city,
            state_or_country=self.state_or_country_desc,
            zipcode=self.zipcode
        )

    def __repr__(self):
        return (f'Address(street1="{self.street1 or ""}", street2="{self.street2 or ""}", city="{self.city or ""}",'
                f'zipcode="{self.zipcode or ""}", state_or_country="{self.state_or_country}")'
                )

    def to_json(self):
        return {
            'street1': self.street1,
            'street2': self.street2,
            'city': self.city,
            'state_or_country': self.state_or_country,
            'zipcode': self.zipcode,
            'state_or_country_desc': self.state_or_country_desc
        }


class Fact:

    def __init__(self,
                 end: str,
                 value: object,
                 accn: str,
                 fy: str,
                 fp: str,
                 form: str,
                 filed: str,
                 frame: str,
                 unit: str
                 ):
        self.end: str = end
        self.value: object = value
        self.accn: str = accn
        self.fy: str = fy
        self.fp: str = fp
        self.form: str = form
        self.filed: str = filed
        self.frame: str = frame
        self.unit: str = unit

    def __repr__(self):
        return (f"Fact(value={self.value}, unit={self.unit}, form={self.form}, accession={self.accn} "
                f"filed={self.filed}, fy={self.fy}, fp={self.fp}, frame={self.frame})"
                )


class EntityFiling(Filing):

    def __init__(self,
                 cik: int,
                 company: str,
                 form: str,
                 filing_date: str,
                 report_date: str,
                 acceptance_datetime: str,
                 accession_no: str,
                 file_number: str,
                 items: str,
                 size: int,
                 primary_document: str,
                 primary_doc_description: str,
                 is_xbrl: bool,
                 is_inline_xbrl: bool):
        super().__init__(cik=cik, company=company, form=form, filing_date=filing_date, accession_no=accession_no)
        self.report_date = report_date
        self.acceptance_datetime = acceptance_datetime
        self.file_number: str = file_number
        self.items: str = items
        self.size: int = size
        self.primary_document: str = primary_document
        self.primary_doc_description: str = primary_doc_description
        self.is_xbrl: bool = is_xbrl
        self.is_inline_xbrl: bool = is_inline_xbrl

    def related_filings(self):
        """Get all the filings related to this one"""
        return self.get_entity().get_filings(file_number=self.file_number, sort_by="filing_date")

    def __str__(self):
        return (f"Filing(company='{self.company}', cik={self.cik}, form='{self.form}', "
                f"filing_date='{self.filing_date}', accession_no='{self.accession_no}')"
                )


class EntityFacts:
    """
    Contains company facts data
    """

    def __init__(self,
                 cik: int,
                 name: str,
                 facts: pa.Table,
                 fact_meta: pd.DataFrame):
        self.cik: int = cik
        self.name: str = name
        self.facts: pa.Table = facts
        self.fact_meta: pd.DataFrame = fact_meta

    def to_pandas(self):
        return self.facts.to_pandas()

    def __len__(self):
        return len(self.facts)

    def num_facts(self):
        return len(self.fact_meta)

    def __rich__(self):
        return Panel(
            Group(
                df_to_rich_table(self.facts)
            ), title=f"Company Facts({self.name} [{self.cik}] {len(self.facts):,} total facts)"
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class EntityFilings(Filings):

    def __init__(self,
                 data: pa.Table,
                 cik: int,
                 company_name: str,
                 original_state: PagingState = None):
        super().__init__(data, original_state=original_state)
        self.cik = cik
        self.company_name = company_name

    def __getitem__(self, item):
        return self.get_filing_at(item)

    @property
    def empty(self):
        return len(self.data) == 0

    def get_filing_at(self, item: int):
        return CompanyFiling(
            cik=self.cik,
            company=self.company_name,
            form=self.data['form'][item].as_py(),
            filing_date=self.data['filing_date'][item].as_py(),
            report_date=self.data['reportDate'][item].as_py(),
            acceptance_datetime=self.data['acceptanceDateTime'][item].as_py(),
            accession_no=self.data['accession_number'][item].as_py(),
            file_number=self.data['fileNumber'][item].as_py(),
            items=self.data['items'][item].as_py(),
            size=self.data['size'][item].as_py(),
            primary_document=self.data['primaryDocument'][item].as_py(),
            primary_doc_description=self.data['primaryDocDescription'][item].as_py(),
            is_xbrl=self.data['isXBRL'][item].as_py(),
            is_inline_xbrl=self.data['isInlineXBRL'][item].as_py()
        )

    def filter(self,
               form: Union[str, List[str]] = None,
               amendments: bool = None,
               filing_date: str = None,
               date: str = None,
               cik: Union[IntString, List[IntString]] = None,
               ticker: Union[str, List[str]] = None,
               accession_number: Union[str, List[str]] = None, ):
        # The super filter returns Filings. We want CompanyFilings
        res = super().filter(form=form,
                             amendments=amendments,
                             filing_date=filing_date,
                             date=date,
                             cik=cik,
                             ticker=ticker,
                             accession_number=accession_number)
        return CompanyFilings(data=res.data, cik=self.cik, company_name=self.company_name)

    def latest(self, n: int = 1):
        """Get the latest n filings"""
        sort_indices = pc.sort_indices(self.data, sort_keys=[("filing_date", "descending")])
        sort_indices_top = sort_indices[:min(n, len(sort_indices))]
        latest_filing_index = pc.take(data=self.data, indices=sort_indices_top)
        filings = CompanyFilings(latest_filing_index,
                                 cik=self.cik,
                                 company_name=self.company_name)
        if filings.empty:
            return None
        if len(filings) == 1:
            return filings[0]
        else:
            return filings

    def head(self, n: int):
        """Get the first n filings"""
        selection = self._head(n)
        return CompanyFilings(data=selection, cik=self.cik, company_name=self.company_name)

    def tail(self, n: int):
        """Get the last n filings"""
        selection = self._tail(n)
        return CompanyFilings(data=selection, cik=self.cik, company_name=self.company_name)

    def sample(self, n: int):
        """Get a random sample of n filings"""
        selection = self._sample(n)
        return CompanyFilings(data=selection, cik=self.cik, company_name=self.company_name)

    def __str__(self):
        return f"{self.company_name} {self.cik} {super().__repr__()}"

    @staticmethod
    def summarize(data) -> pd.DataFrame:
        return (data
                .assign(size=lambda df: df['size'].apply(display_size),
                        isXBRL=lambda df: df.isXBRL.map({'1': "\u2713", 1: "\u2713"}).fillna(""),
                        )
                .filter(["form", "filing_date", "accession_number", "isXBRL"])
                .rename(columns={"filing_date": "filed", "isXBRL": "xbrl"})
                )

    def next(self):
        """Show the next page"""
        data_page = self.data_pager.next()
        if data_page is None:
            log.warning("End of data .. use prev() \u2190 ")
            return None
        start_index, _ = self.data_pager._current_range
        filings_state = PagingState(page_start=start_index, num_records=len(self))
        return CompanyFilings(data_page,
                              cik=self.cik,
                              company_name=self.company_name,
                              original_state=filings_state)

    def previous(self):
        """
        Show the previous page of the data
        :return:
        """
        data_page = self.data_pager.previous()
        if data_page is None:
            log.warning(" No previous data .. use next() \u2192 ")
            return None
        start_index, _ = self.data_pager._current_range
        filings_state = PagingState(page_start=start_index, num_records=len(self))
        return CompanyFilings(data_page,
                              cik=self.cik,
                              company_name=self.company_name,
                              original_state=filings_state)

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __rich__(self):
        # Create table with appropriate columns and styling
        table = Table(
            show_header=True,
            header_style="bold",
            show_edge=True,
            expand=False,
            padding=(0, 1),
            box=box.SIMPLE,
            row_styles=["", "bold"]
        )

        # Add columns with specific styling and alignment
        table.add_column("#", style="dim", justify="right")
        table.add_column("Form", width=8, style="bold yellow")
        table.add_column("Description", width=50, style="bold blue"),
        table.add_column("Filing Date", width=11)
        table.add_column("Accession Number", style="dim", width=20)

        # Get current page from data pager
        current_page = self.data_pager.current()

        # Calculate start index for proper indexing
        start_idx = self._original_state.page_start if self._original_state else self.data_pager.start_index

        # Iterate through rows in current page
        for i in range(len(current_page)):
            form = current_page['form'][i].as_py()
            description = describe_form(current_page['form'][i].as_py(), prepend_form=False)

            row = [
                str(start_idx + i),
                form,
                description,
                str(current_page['filing_date'][i].as_py()),
                current_page['accession_number'][i].as_py()
            ]
            table.add_row(*row)

        # Show paging information only if there are multiple pages
        elements = [table]

        if self.data_pager.total_pages > 1:
            total_filings = self._original_state.num_records
            current_count = len(current_page)
            start_num = start_idx + 1
            end_num = start_idx + current_count

            page_info = Text.assemble(
                ("Showing ", "dim"),
                (f"{start_num:,}", "bold red"),
                (" to ", "dim"),
                (f"{end_num:,}", "bold red"),
                (" of ", "dim"),
                (f"{total_filings:,}", "bold"),
                (" filings.", "dim"),
                (" Page using ", "dim"),
                ("← prev()", "bold gray54"),
                (" and ", "dim"),
                ("next() →", "bold gray54")
            )

            elements.extend([Text("\n"), page_info])

        # Get the title
        title = Text.assemble(
            ("Filings for ", "bold"),
            (f"{self.company_name}", "bold green"),
            (" [", "dim"),
            (f"{self.cik}", "bold yellow"),
            ("]", "dim")
        )

        # Get the subtitle
        start_date, end_date = self.date_range
        subtitle = f"Company filings between {start_date:%Y-%m-%d} and {end_date:%Y-%m-%d}" if start_date else ""
        return Panel(
            Group(*elements),
            title=title,
            subtitle=subtitle,
            border_style="bold grey54"
        )


class EntityData:
    """
    A company populated from a call to the company submissions endpoint
    """

    def __init__(self,
                 cik: int,
                 name: str,
                 tickers: List[str],
                 exchanges: List[str],
                 sic: int,
                 sic_description: str,
                 category: str,
                 fiscal_year_end: str,
                 entity_type: str,
                 phone: str,
                 flags: str,
                 business_address: Address,
                 mailing_address: Address,
                 filings: EntityFilings,
                 insider_transaction_for_owner_exists: bool,
                 insider_transaction_for_issuer_exists: bool,
                 ein: str,
                 description: str,
                 website: str,
                 investor_website: str,
                 state_of_incorporation: str,
                 state_of_incorporation_description: str,
                 former_names: List[Dict[str, Any]],
                 files: List[str]
                 ):
        self.cik: int = cik
        self.name: str = name
        self.tickers: List[str] = tickers
        self.exchanges: List[str] = exchanges
        self.sic: int = sic
        self.sic_description: str = sic_description
        self.category: str = category
        self.fiscal_year_end: str = fiscal_year_end
        self.entity_type: str = entity_type
        self.phone: str = phone
        self.flags: str = flags
        self.business_address: Address = business_address
        self.mailing_address: Address = mailing_address
        self.filings: CompanyFilings = filings
        self.insider_transaction_for_owner_exists: bool = insider_transaction_for_owner_exists
        self.insider_transaction_for_issuer_exists: bool = insider_transaction_for_issuer_exists
        self.ein: str = ein
        self.description: str = description
        self.website: str = website
        self.investor_website: str = investor_website
        self.state_of_incorporation: str = state_of_incorporation
        self.state_of_incorporation_description: str = state_of_incorporation_description
        self.former_names: List[Dict[str, Any]] = former_names
        self._files = files
        self._loaded_all_filings: bool = False

    @property
    def latest_tenk(self) -> Optional[TenK]:
        if self.is_company:
            latest_10k = self.get_filings(form='10-K', trigger_full_load=False).latest()
            if latest_10k is not None:
                return latest_10k.obj()

    @property
    def latest_tenq(self) -> Optional[TenQ]:
        if self.is_company:
            latest_10q = self.get_filings(form='10-Q', trigger_full_load=False).latest()
            if latest_10q is not None:
                return latest_10q.obj()

    @property
    def financials(self) -> Optional[Financials]:
        """
        Get the latest 10-K financials
        """
        tenk_filing = self.latest_tenk
        if tenk_filing is not None:
            return tenk_filing.financials

    @property
    def quarterly_financials(self) -> Optional[Financials]:
        """
        Get the latest 10-Q financials
        """
        tenq_filing = self.latest_tenq
        if tenq_filing is not None:
            return tenq_filing.financials

    @cached_property
    def is_company(self) -> bool:
        return not self.is_individual

    @property
    def icon(self) -> Optional[bytes]:
        # If there are no tickers, we can't get an icon
        if len(self.tickers) == 0:
            return None
        # Get the icon for the first ticker, if it exists.
        return get_icon_from_ticker(self.tickers[0])

    @cached_property
    def is_individual(self) -> bool:
        """ Tricky logic to detect if a company is an individual or a company.
            Companies have a ein, individuals do not. Oddly Warren Buffet has an EIN but not a state of incorporation
            There may be other edge cases
            If you have a ticker or exchange you are a company
        """
        if len(self.tickers) > 0 or len(self.exchanges) > 0:
            return False
        if self.state_of_incorporation is not None and self.state_of_incorporation != '':
            return False
        if self.entity_type not in ['', 'other']:
            return False
        if self.ein is None or self.ein == "000000000":  # The Warren Buffett case
            return True
        return False

    @property
    def _unicode_symbol(self):
        if self.is_company:
            return "\U0001F3EC"  # Building
        else:
            return "\U0001F464"  # Person

    @property
    @lru_cache(maxsize=1)
    def display_name(self) -> str:
        """Reverse the name if it is a company"""
        if self.is_company:
            return self.name
        return reverse_name(self.name)

    @property
    def industry(self) -> str:
        return self.sic_description

    @classmethod
    def for_cik(cls, cik: int):
        return get_entity_submissions(cik)

    @classmethod
    def for_ticker(cls, ticker: str):
        cik = find_cik(ticker)
        if cik:
            return CompanyData.for_cik(cik)

    def latest(self, form: str, n=1):
        """Get the latest for a given form"""
        return self.get_filings(form=form, trigger_full_load=False).latest(n)

    def get_facts(self) -> Optional[EntityFacts]:
        """
        Get the company facts
        :return: CompanyFacts
        """
        try:
            return get_company_facts(self.cik)
        except NoCompanyFactsFound:
            return None

    def _load_older_filings(self):
        """
        Load the older filings
        """
        if not self._files:
            return

        filing_tables = [self.filings.data]
        for file in self._files:
            submissions = download_json("https://data.sec.gov/submissions/" + file['name'])
            filing_table = extract_company_filings_table(submissions)
            filing_tables.append(filing_table)
        combined_tables = pa.concat_tables(filing_tables)
        self.filings = CompanyFilings(combined_tables, cik=self.cik, company_name=self.name)

    def get_empty_filings(self):
        return empty_company_filings(self.cik, self.name)

    def get_filings(self,
                    *,
                    form: Union[str, List] = None,
                    accession_number: Union[str, List] = None,
                    file_number: Union[str, List] = None,
                    filing_date: Union[str, Tuple[str, str]] = None,
                    date: Union[str, Tuple[str, str]] = None,
                    is_xbrl: bool = None,
                    is_inline_xbrl: bool = None,
                    sort_by: Union[str, List[Tuple[str, str]]] = None,
                    trigger_full_load: bool = True
                    ):
        """
        Get the company's filings and optionally filter by multiple criteria

        form: The form as a string e.g. '10-K' or List of strings ['10-Q', '10-K']

        accession_number: The accession number that uniquely identifies an SEC filing e.g. 0001640147-22-000100

        file_number: The file number e.g. 001-39504

        is_xbrl: Whether the filing is xbrl

        is_inline_xbrl: Whether the filing is inline_xbrl

        :return: The CompanyFiling instance with the filings that match the filters
        """

        if not self._loaded_all_filings:
            if not is_using_local_storage():
                if trigger_full_load:
                    self._load_older_filings()
                    self._loaded_all_filings = True

        company_filings = self.filings.data

        # Filter by accession number
        if accession_number:
            company_filings = company_filings.filter(
                pc.is_in(company_filings['accession_number'], pa.array(listify(accession_number))))
            if len(company_filings) >= 1:
                # We found the single filing or oops, didn't find any
                return CompanyFilings(company_filings, cik=self.cik, company_name=self.name)

        # Filter by form
        if form:
            forms = pa.array([str(f) for f in listify(form)])
            company_filings = company_filings.filter(pc.is_in(company_filings['form'], forms))

        # Filter by file number
        if file_number:
            company_filings = company_filings.filter(pc.is_in(company_filings['fileNumber'],
                                                              pa.array(listify(file_number))))
        if is_xbrl is not None:
            company_filings = company_filings.filter(pc.equal(company_filings['isXBRL'], int(is_xbrl)))
        if is_inline_xbrl is not None:
            company_filings = company_filings.filter(pc.equal(company_filings['isInlineXBRL'], int(is_inline_xbrl)))

        filing_date = filing_date or date
        if filing_date:
            # Filter by date
            try:
                company_filings = filter_by_date(company_filings, filing_date, 'filing_date')
            except InvalidDateException as e:
                log.error(e)
                return None

        if sort_by:
            company_filings = company_filings.sort_by(sort_by)

        return CompanyFilings(company_filings,
                              cik=self.cik,
                              company_name=self.name)

    @lru_cache(maxsize=1)
    def summary(self) -> pd.DataFrame:
        return pd.DataFrame([{'company': self.name,
                              'cik': self.cik,
                              'category': self.category,
                              'industry': self.sic_description}]).set_index('cik')

    @lru_cache(maxsize=1)
    def ticker_info(self) -> pd.DataFrame:
        return pd.DataFrame({"exchange": self.exchanges, "ticker": self.tickers}).set_index("ticker")

    @property
    def ticker_display(self) -> str:
        """Show a simplified version of the tickers"""
        len_tickers = len(self.tickers)
        if len_tickers == 0:
            return ""
        elif len_tickers == 1:
            return self.tickers[0]
        else:
            return f"{self.tickers[0]} + {len_tickers - 1} other{'s' if len_tickers > 2 else ''}"

    def __str__(self):
        return f"""Company({self.name} [{self.cik}] {','.join(self.tickers)}, {self.sic_description})"""

    def to_dict(self, include_filings: bool = False):
        company_dict = {
            'cik': self.cik,
            'name': self.name,
            'display_name': self.display_name,
            'is_company': self.is_company,
            'tickers': self.tickers,
            'exchanges': self.exchanges,
            'sic': self.sic,
            'industry': self.sic_description,
            'category': self.category,
            'fiscal_year_end': self.fiscal_year_end,
            'entity_type': self.entity_type,
            'phone': self.phone,
            'flags': self.flags,
            'mailing_address': self.mailing_address.__dict__,
            'business_address': self.business_address.__dict__,
            'insider_transaction_for_owner_exists': self.insider_transaction_for_owner_exists,
            'insider_transaction_for_issuer_exists': self.insider_transaction_for_issuer_exists,
            'ein': self.ein,
            'description': self.description,
            'website': self.website,
            'investor_website': self.investor_website,
            'state_of_incorporation': self.state_of_incorporation,
            'state_of_incorporation_description': self.state_of_incorporation_description,
            'former_names': self.former_names
        }
        if include_filings:
            company_dict['filings'] = self.filings.to_dict()
        return company_dict

    @staticmethod
    def get_operating_type_emoticon(entity_type: str) -> str:
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
    def format_fiscal_year_date(date_str):
        # Dictionary of months
        months = {
            "01": "Jan", "02": "Feb", "03": "Mar",
            "04": "Apr", "05": "May", "06": "Jun",
            "07": "Jul", "08": "Aug", "09": "Sep",
            "10": "Oct", "11": "Nov", "12": "Dec"
        }

        # Extract month and day
        month = date_str[:2]
        day = str(int(date_str[2:]))  # Remove leading zero

        return f"{months[month]} {day}"

    def __rich__(self) -> Panel:
        """Creates a rich representation of the entity with clear information hierarchy."""

        # Primary entity identification section
        if self.is_company:
            ticker_display = f" ({self.ticker_display})" if self.ticker_display else ""
            entity_title = Text.assemble("🏢", (f"{self.display_name}{ticker_display}", "bold deep_sky_blue3"))
        else:
            entity_title = Text.assemble("👤", (self.display_name, "bold green"))

        # Primary Information Table
        main_info = Table(box=box.SIMPLE_HEAVY, show_header=False, padding=(0, 1))
        main_info.add_column("Row", style="")  # Single column for the entire row

        row_parts = []
        row_parts.extend([Text("CIK", style="grey60"), Text(str(self.cik), style="bold deep_sky_blue3")])
        if self.entity_type:
            if self.is_individual:
                row_parts.extend([Text("Type", style="grey60"),
                                  Text("Individual", style="bold yellow")])
            else:
                row_parts.extend([Text("Type", style="grey60"),
                                  Text(self.entity_type.title(), style="bold yellow"),
                                  Text(EntityData.get_operating_type_emoticon(self.entity_type), style="bold yellow")])
        main_info.add_row(*row_parts)

        # Detailed Information Table
        details = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
        details.add_column("Category", style="bold grey70")
        details.add_column("Industry", style="bold grey70")
        details.add_column("Fiscal Year End", style="bold grey70")

        details.add_row(
            self.category or "-",
            f"{self.sic}: {self.sic_description}" if self.sic else "-",
            EntityData.format_fiscal_year_date(self.fiscal_year_end) if self.fiscal_year_end else "-"
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
            trading_info.add_column("Exchange", style="bold grey70")
            trading_info.add_column("Symbol", style="bold deep_sky_blue3")

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

        has_contact_info = any([self.phone, self.website, self.investor_website])
        if self.website:
            contact_info.add_row("Website", self.website)
        if self.investor_website:
            contact_info.add_row("Investor Relations", self.investor_website)
        if self.phone:
            contact_info.add_row("Phone", self.phone)

        # Three-column layout for addresses and contact info
        contact_renderables = []
        if not self.business_address.empty:
            contact_renderables.append(Panel(
                Text(str(self.business_address), style="grey85"),
                title="🏢 Business Address",
                border_style="grey50"
            ))
        if not self.mailing_address.empty:
            contact_renderables.append(Panel(
                Text(str(self.mailing_address), style="grey85"),
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
        if self.former_names:
            former_names_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
            former_names_table.add_column("Previous Company Names", style="bold grey70")
            former_names_table.add_column("", style="grey85")  # Empty column for better spacing

            for former_name in self.former_names:
                from_date = datefmt(former_name['from'], '%B %Y')
                to_date = datefmt(former_name['to'], '%B %Y')
                former_names_table.add_row(Text(former_name['name'], style="italic"), f"{from_date} to {to_date}")

            former_names_panel = Panel(
                former_names_table,
                title="📜 Former Names",
                border_style="grey50"
            )
        else:
            former_names_panel = None

        # Combine all sections using Group
        if self.is_company:
            content_renderables = [Padding("", (1, 0, 0, 0)), basic_info_panel, trading_panel]
            if len(content_renderables):
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

    def __repr__(self):
        return repr_rich(self.__rich__())


# Aliases for Companies
CompanyFiling = EntityFiling
CompanyFilings = EntityFilings
CompanyFacts = EntityFacts
CompanyData = EntityData

COMPANY_FILINGS_SCHEMA = schema = pa.schema([
            ('accession_number', pa.string()),
            ('filing_date', pa.date32()),
            ('reportDate', pa.string()),
            ('acceptanceDateTime', pa.timestamp('us')),  # Changed to timestamp
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

def empty_company_filings_table():
    """
    Create an empty company filings table
    """
    return pa.Table.from_arrays([[] for _ in range(13)], schema=COMPANY_FILINGS_SCHEMA)

def empty_company_filings(cik:IntString, company_name:str):
    return CompanyFilings(empty_company_filings_table(), cik=cik, company_name=company_name)

def extract_company_filings_table(filings_json: Dict[str, Any]) -> pa.Table:
    """
    Extract company filings from the json response
    """
    # Handle case of no data
    if not filings_json['accessionNumber']:
        filings_table = empty_company_filings_table()
    else:
        # Convert acceptanceDateTime string to datetime
        acceptance_datetimes = [
            parse_acceptance_datetime(dt) for dt in filings_json['acceptanceDateTime']
        ]

        fields = {
            'accession_number': filings_json['accessionNumber'],
            'filing_date': pc.cast(pc.strptime(pa.array(filings_json['filingDate']), '%Y-%m-%d', 'us'), pa.date32()),
            'reportDate': filings_json['reportDate'],
            'acceptanceDateTime': acceptance_datetimes,  # Now passing datetime objects
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
        filings_table = pa.Table.from_arrays(
            arrays=[pa.array(v) if k not in ['filing_date', 'acceptanceDateTime']
                    else v for k, v in fields.items()],
            names=list(fields.keys())
        )
    return filings_table


def create_company_filings(filings_json: Dict[str, Any],
                           cik: int,
                           company_name: str) -> CompanyFilings:
    """
    Extract company filings from the json response
    """
    recent_filings = extract_company_filings_table(filings_json['recent'])
    return CompanyFilings(recent_filings, cik=cik, company_name=company_name)


class AdditionalFilings:
    """Tracks additional filing files that haven't been loaded yet"""

    def __init__(self, files: List[Dict[str, str]]):
        self.files = files
        self.loaded = False

    def load(self) -> List[Dict[str, Any]]:
        """Load all additional filing files"""
        if not self.loaded:
            additional_filings = []
            for file in self.files:
                file_data = download_json("https://data.sec.gov/submissions/" + file['name'])

                additional_filings.append(file_data)
            self.loaded = True
            return additional_filings
        return []


def parse_entity_submissions(cjson: Dict[str, Any]):
    mailing_addr = cjson['addresses']['mailing']
    business_addr = cjson['addresses']['business']
    cik = cjson['cik']
    company_name = cjson["name"]
    former_names = cjson.get('formerNames', [])
    for former_name in former_names:
        former_name['from'] = former_name['from'][:10] if former_name['from'] else former_name['from']
        former_name['to'] = former_name['to'][:10] if former_name['to'] else former_name['to']
    return CompanyData(cik=int(cik),
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


@lru_cache(maxsize=64)
def get_entity(entity_identifier: IntString) -> EntityData:
    """
        Get a company by cik or ticker

        Get company by ticker e.g.

        >>> get_entity("SNOW") or get_entity("tsla")

        Get company by cik e.g.

        >>> get_entity(1090990)

    :param entity_identifier: The company identifier. Can be a cik or a ticker
    :return:
    """
    is_int_cik = isinstance(entity_identifier, int)
    # Sometimes the cik is left zero padded e.g. 000198706
    is_string_cik = isinstance(entity_identifier, str) and entity_identifier.isdigit()
    is_cik = is_int_cik or is_string_cik

    if is_cik:
        # Cast to int to handle zero-padding
        return EntityData.for_cik(int(entity_identifier))

    # Get by ticker
    is_ticker = isinstance(entity_identifier, str) and re.match("[A-Za-z]{1,6}", entity_identifier, re.IGNORECASE)

    if is_ticker:
        return EntityData.for_ticker(entity_identifier)

    log.warn("""
    To use get_company() provide a valid cik or ticker.
    
    e.g. to get by cik
    >>> get_company(91184670) or get_company("0091184670")
    
    or to get by ticker
    
    >>> get_company("SNOW") or get_company("snow")
    """)


# This is an alias for get_company allowing for this -> Company("SNOW")
get_company = get_entity
Company = get_entity
Entity = get_entity


@lru_cache(maxsize=32)
def get_entity_submissions(cik: int) -> Optional[EntityData]:
    # Check the environment var EDGAR_USE_LOCAL_DATA
    if is_using_local_storage():
        submissions_json = load_company_submissions_from_local(cik)
        if not submissions_json:
            submissions_json = download_entity_submissions_from_sec(cik)
    else:
        submissions_json = download_entity_submissions_from_sec(cik)
    if submissions_json:
        return parse_entity_submissions(submissions_json)


@lru_cache(maxsize=32)
def download_entity_submissions_from_sec(cik: int) -> Optional[Dict[str, Any]]:
    """Get the company filings for a given cik"""
    try:
        submission_json = download_json(f"https://data.sec.gov/submissions/CIK{cik:010}.json")
    except httpx.HTTPStatusError as e:
        # Handle the case where the cik is invalid and not found on Edgar
        if e.response.status_code == 404:
            return None
        else:
            raise
            # check for older submission files
    return submission_json


def parse_company_facts(fjson: Dict[str, object]):
    unit_dfs = []
    fact_meta_lst = []
    columns = ['namespace', 'fact', 'val', 'accn', 'start', 'end', 'fy', 'fp', 'form', 'filed', 'frame']

    # facts must be present
    if 'facts' in fjson and fjson['facts']:
        for namespace, namespace_json in fjson['facts'].items():
            for fact, fact_json in namespace_json.items():
                # Metadata about the facts
                fact_meta_lst.append({'fact': fact,
                                      'label': fact_json['label'],
                                      'description': fact_json['description']})

                for unit_key, unit_json in fact_json['units'].items():
                    unit_data = (pd.DataFrame(unit_json)
                                 .assign(namespace=namespace,
                                         fact=fact,
                                         label=fact_json['label'])
                                 .filter(columns)
                                 )
                    unit_dfs.append(unit_data)
    else:
        return None

    # can't concatenate an empty list
    if len(unit_dfs) > 0:
        unit_dfs = pd.concat(unit_dfs, ignore_index=True)
    facts = pa.Table.from_pandas(unit_dfs)
    return CompanyFacts(cik=fjson['cik'],
                        name=fjson['entityName'],
                        facts=facts,
                        fact_meta=pd.DataFrame(fact_meta_lst))


class NoCompanyFactsFound(Exception):

    def __init__(self, cik: int):
        super().__init__()
        self.message = f"""No Company facts found for cik {cik}"""


@lru_cache(maxsize=32)
def get_company_facts(cik: int):
    # Check the environment var EDGAR_USE_LOCAL_DATA
    if os.getenv("EDGAR_USE_LOCAL_DATA"):
        company_facts_json = load_company_facts_from_local(cik)
        if not company_facts_json:
            company_facts_json = download_company_facts_from_sec(cik)
    else:
        company_facts_json = download_company_facts_from_sec(cik)
    return parse_company_facts(company_facts_json)


def download_company_facts_from_sec(cik: int) -> Dict[str, Any]:
    """
    Download company facts from the SEC
    """
    company_facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010}.json"
    try:
        return download_json(company_facts_url)
    except httpx.HTTPStatusError as err:
        if err.response.status_code == 404:
            logging.warning(f"No company facts found on url {company_facts_url}")
            raise NoCompanyFactsFound(cik=cik)
        else:
            raise


def load_company_facts_from_local(cik: int) -> Optional[Dict[str, Any]]:
    """
    Load company facts from local data
    """
    company_facts_dir = get_edgar_data_directory() / "companyfacts"
    if not company_facts_dir.exists():
        return None
    company_facts_file = company_facts_dir / f"CIK{cik:010}.json"
    if not company_facts_file.exists():
        company_facts_json = download_company_facts_from_sec(cik)
        with open(company_facts_file, "wb") as f:
            f.write(json.dumps(company_facts_json))
            f.flush()
            f.close()
        return company_facts_json
    return json.loads(company_facts_file.read_text())


def load_company_submissions_from_local(cik: int) -> Optional[Dict[str, Any]]:
    """
    Load company submissions from local data
    """
    submissions_dir = get_edgar_data_directory() / "submissions"
    if not submissions_dir.exists():
        return None
    submissions_file = submissions_dir / f"CIK{cik:010}.json"
    if not submissions_file.exists():
        submissions_json = download_entity_submissions_from_sec(cik)
        with open(submissions_file, "wb") as f:
            f.write(json.dumps(submissions_json))
            f.flush()
            f.close()
        return submissions_json
    return json.loads(submissions_file.read_text())


@dataclass(frozen=True)
class Concept:
    taxonomy: str
    tag: str
    label: str
    description: str


class CompanyConcept:

    def __init__(self,
                 cik: str,
                 entity_name: str,
                 concept: Concept,
                 data: pd.DataFrame):
        self.cik: str = cik
        self.entity_name: str = entity_name
        self.concept: Concept = concept
        self.data: pd.DataFrame = data

    @staticmethod
    def create_fact(row) -> Fact:
        return Fact(
            end=row.end,
            value=row.val,
            accn=row.accn,
            fy=row.fy,
            fp=row.fp,
            form=row.form,
            filed=row.filed,
            frame=row.frame,
            unit=row.unit
        )

    def latest(self) -> pd.DataFrame:
        return (self.data
                .assign(cnt=self.data.groupby(['unit']).cumcount())
                .query("cnt==0")
                )

    def __repr__(self):
        return (f"CompanyConcept({self.concept.taxonomy}:{self.concept.tag}, {self.entity_name} - {self.cik})"
                "\n"
                f"{self.data}")

    @classmethod
    def from_json(cls,
                  cjson: Dict[str, Any]):
        data = pd.concat([
            (pd.DataFrame(unit_data)
             .assign(unit=unit, frame=lambda df: df.frame.replace(np.nan, None))
             .filter(['filed', 'val', 'unit', 'fy', 'fp', 'end', 'form', 'frame', 'accn'])
             .sort_values(["filed"], ascending=[False])
             .reset_index(drop=True)
             )
            for unit, unit_data in cjson["units"].items()
        ])
        return cls(
            cik=cjson['cik'],
            entity_name=cjson["entityName"],
            concept=Concept(
                taxonomy=cjson["taxonomy"],
                tag=cjson["tag"],
                label=cjson["tag"],
                description=cjson["description"],
            )
            , data=data
        )


@lru_cache(maxsize=32)
def get_concept(cik: int,
                taxonomy: str,
                concept: str):
    """
    The company-concept API returns all the XBRL disclosures from a single company (CIK) and concept
     (a taxonomy and tag) into a single JSON file, with a separate array of facts for each units on measure
     that the company has chosen to disclose (e.g. net profits reported in U.S. dollars and in Canadian dollars).

    https://data.sec.gov/api/xbrl/companyconcept/CIK##########/us-gaap/AccountsPayableCurrent.json
    :param cik: The company cik
    :param taxonomy: The taxonomy e.g. "us-gaap"
    :param concept: The concept or tag e.g. AccountsPayableCurrent
    :return: a CompanyConcept
    """
    try:
        company_concept_json = download_json(
            f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010}/{taxonomy}/{concept}.json")
        company_concept: CompanyConcept = CompanyConcept.from_json(company_concept_json)
        return company_concept
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            # Get the company
            company = CompanyData.for_cik(int(cik))
            if not company:
                return Result.Fail("No company found for cik {cik}")
            else:
                error_message = (f"{taxonomy}:{concept} does not exist for company {company.name} [{cik}]. "
                                 "See https://fasb.org/xbrl")
                log.error(error_message)
                return Result.Fail(error=error_message)


@lru_cache(maxsize=1)
def get_ticker_to_cik_lookup():
    tickers_json = download_json(
        "https://www.sec.gov/files/company_tickers.json"
    )
    return {value['ticker']: value['cik_str']
            for value in tickers_json.values()
            }


def _parse_cik_lookup_data(content):
    return [
        {
            # for companies with : in the name
            'name': ":".join(line.split(':')[:-2]),
            'cik': int(line.split(':')[-2])
        } for line in content.split("\n") if line != '']


@lru_cache(maxsize=1)
def get_cik_lookup_data() -> pd.DataFrame:
    """
    Get a dataframe of company/entity names and their cik
    or a Dict of int(cik) to str(name)
    DECADE CAPITAL MANAGEMENT LLC:0001426822:
    DECADE COMPANIES INCOME PROPERTIES:0000775840:
    """
    content = download_text("https://www.sec.gov/Archives/edgar/cik-lookup-data.txt")
    cik_lookup_df = pd.DataFrame(_parse_cik_lookup_data(content))
    return cik_lookup_df


company_types_re = r"(L\.?L\.?C\.?|Inc\.?|Ltd\.?|L\.?P\.?|/[A-Za-z]{2,3}/?| CORP(ORATION)?|PLC| AG)$"


def preprocess_company(company: str) -> str:
    """preprocess the company name for storing in the search index"""
    comp = re.sub(company_types_re, "", company.lower(), flags=re.IGNORECASE)
    comp = re.sub(r"\.|,", "", comp)
    return comp.strip()


class CompanySearchResults:

    def __init__(self, query: str,
                 search_results: List[Dict[str, Any]]):
        self.query: str = query
        self.results: pd.DataFrame = pd.DataFrame(search_results, columns=['cik', 'ticker', 'company', 'score'])

    @property
    def tickers(self):
        return self.results.ticker.tolist()

    @property
    def ciks(self):
        return self.results.cik.tolist()

    @property
    def empty(self):
        return self.results.empty

    def __len__(self):
        return len(self.results)

    def __getitem__(self, item):
        if 0 <= item < len(self):
            row = self.results.iloc[item]
            cik: int = int(row.cik)
            return Company(cik)

    def __rich__(self):
        table = Table(Column(""),
                      Column("Ticker", justify="left"),
                      Column("Name", justify="left"),
                      Column("Score", justify="left"),
                      title=f"Search results for '{self.query}'",
                      box=box.SIMPLE)
        for index, row in enumerate(self.results.itertuples()):
            table.add_row(str(index), row.ticker.rjust(6), row.company, f"{int(row.score)}%")
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


class CompanySearchIndex(FastSearch):
    def __init__(self):
        data = get_company_tickers(as_dataframe=False)
        super().__init__(data, ['company', 'ticker'],
                         preprocess_func=company_ticker_preprocess,
                         score_func=company_ticker_score)

    def search(self, query: str, top_n: int = 10, threshold: float = 60) -> CompanySearchResults:
        results = super().search(query, top_n, threshold)
        return CompanySearchResults(query=query, search_results=results)

    def __len__(self):
        return len(self.data)

    def __hash__(self):
        # Combine column names and last 10 values in the 'company' column to create a hash
        column_names = tuple(self.data[0].keys())
        last_10_companies = tuple(entry['company'] for entry in self.data[-10:])
        return hash((column_names, last_10_companies))

    def __eq__(self, other):
        if not isinstance(other, CompanySearchIndex):
            return False
        return (self.data[-10:], tuple(self.data[0].keys())) == (other.data[-10:], tuple(other.data[0].keys()))


@lru_cache(maxsize=1)
def _get_company_search_index():
    return CompanySearchIndex()


@lru_cache(maxsize=16)
def find_company(company: str, top_n: int = 10):
    return _get_company_search_index().search(company, top_n=top_n)
