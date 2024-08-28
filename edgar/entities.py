import asyncio
import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
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
from rich.panel import Panel
from rich.table import Table, Column
from rich.text import Text

from edgar._filings import Filing, Filings, FilingsState
from edgar.richtools import df_to_rich_table, repr_rich
from edgar.core import (log, Result, display_size, listify,
                        filter_by_date, IntString, InvalidDateException, reverse_name, get_edgar_data_directory)
from edgar.httprequests import download_json, download_text, download_bulk_data
from edgar.reference import states
from edgar.reference.tickers import get_company_tickers, get_icon_from_ticker, find_cik
from edgar.search.datasearch import FastSearch, company_ticker_preprocess, company_ticker_score
from edgar.financials import Financials

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
                 original_state: FilingsState = None):
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
               date: str = None):
        # The super filter returns Filings. We want CompanyFilings
        res = super().filter(form, amendments, filing_date, date)
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
        filings_state = FilingsState(page_start=start_index, num_filings=len(self))
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
        filings_state = FilingsState(page_start=start_index, num_filings=len(self))
        return CompanyFilings(data_page,
                              cik=self.cik,
                              company_name=self.company_name,
                              original_state=filings_state)

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __rich__(self):
        page = self.data_pager.current().to_pandas()
        page.index = self._page_index()
        page_info = f"Showing {len(page)} filings of {self._original_state.num_filings:,} total"
        return Panel(
            Group(
                df_to_rich_table(CompanyFilings.summarize(page),
                                 max_rows=len(page),
                                 ),
                Text(page_info)
            ), title=f"Filings for {self.company_name} [{self.cik}]"
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
                 former_names: List[str],
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
        self.former_names: List[str] = former_names

    @property
    def financials(self):
        if self.is_company:
            # Get the latest 10-K
            latest_10k = self.filings.filter(form="10-K").latest()
            if latest_10k is not None:
                return Financials.extract(latest_10k)

    @property
    def is_company(self) -> bool:
        return not self.is_individual
    
    @property
    def icon(self) -> Optional[bytes]:
        # If there are no tickers, we can't get an icon
        if len(self.tickers) == 0:
            return None
        # Get the icon for the first ticker, if it exists.
        return get_icon_from_ticker(self.tickers[0])

    @property
    # Companies have a ein, individuals do not. Oddly Warren Buffet has an EIN but not a state of incorporation
    # There may be other edge cases
    def is_individual(self) -> bool:
        # If you have a ticker or exchange you are a company
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
    def for_cik(cls, cik: int, include_old_filings: bool = True):
        return get_entity_submissions(cik, include_old_filings=include_old_filings)

    @classmethod
    def for_ticker(cls, ticker: str, include_old_filings: bool = True):
        cik = find_cik(ticker)
        if cik:
            return CompanyData.for_cik(cik, include_old_filings=include_old_filings)

    def get_facts(self) -> Optional[EntityFacts]:
        """
        Get the company facts
        :return: CompanyFacts
        """
        try:
            return get_company_facts(self.cik)
        except NoCompanyFactsFound:
            return None

    def get_filings(self,
                    *,
                    form: Union[str, List] = None,
                    accession_number: Union[str, List] = None,
                    file_number: Union[str, List] = None,
                    filing_date: Union[str, Tuple[str, str]] = None,
                    date: Union[str, Tuple[str, str]] = None,
                    is_xbrl: bool = None,
                    is_inline_xbrl: bool = None,
                    sort_by: Union[str, List[Tuple[str, str]]] = None
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

    def __rich__(self):
        info_table = Table(Column("CIK", style="bold magenta"), box=box.SIMPLE)
        row = [str(self.cik)]
        if self.category:
            info_table.add_column("Category")
            row.append(self.category)
        if self.sic:
            info_table.add_column("Industry")
            row.append(self.industry)
        if self.state_of_incorporation:
            info_table.add_column("Incorporated")
            row.append(states.get(self.state_of_incorporation, self.state_of_incorporation_description))
        info_table.add_row(*row)

        # The addresses
        addresses = []
        if not self.mailing_address.empty:
            addresses.append(Panel(Text(str(self.mailing_address)), title='\U00002709 Mailing Address', width=40))
        if not self.business_address.empty:
            addresses.append(Panel((Text(str(self.business_address))), title='\U0001F3E2 Business Address', width=40))
        address_columns = Columns(addresses, equal=True, expand=True)

        if self.is_company:
            display_name = f"{self.display_name} ({self.ticker_display})" if self.ticker_display else self.display_name
        else:
            display_name = f"{self._unicode_symbol} {self.display_name}"

        title_style = "bold dark_sea_green4" if self.is_company else "bold dodger_blue1"
        return Panel(Group(info_table, address_columns),
                     title=Text(f"{display_name}", style=title_style))

    def __repr__(self):
        return repr_rich(self.__rich__())


# Aliases for Companies
CompanyFiling = EntityFiling
CompanyFilings = EntityFilings
CompanyFacts = EntityFacts
CompanyData = EntityData


def parse_filings(filings_json: Dict[str, object],
                  cik: int,
                  company_name: str) -> CompanyFilings:
    # Handle case of no data
    if filings_json['recent']['accessionNumber'] == []:
        # Create an empty table
        filings_table = pa.Table.from_arrays(arrays=
                                             [pa.array([], type=pa.string()),
                                              pa.array([], type=pa.date32()),
                                              pa.array([], type=pa.string()),
                                              pa.array([], type=pa.string()),
                                              pa.array([], type=pa.string()),
                                              pa.array([], type=pa.string()),
                                              pa.array([], type=pa.string()),
                                              pa.array([], type=pa.string()),
                                              pa.array([], type=pa.string()),
                                              pa.array([], type=pa.string()),
                                              pa.array([], type=pa.string()),
                                              pa.array([], type=pa.string()),
                                              pa.array([], type=pa.string()),
                                              ],
                                             names=['accession_number',
                                                    'filing_date',
                                                    'reportDate',
                                                    'acceptanceDateTime',
                                                    'act',
                                                    'form',
                                                    'fileNumber',
                                                    'items',
                                                    'size',
                                                    'isXBRL',
                                                    'isInlineXBRL',
                                                    'primaryDocument',
                                                    'primaryDocDescription'
                                                    ]
                                             )
    else:
        rjson: Dict[str, List[object]] = filings_json['recent']

        filings_table = pa.Table.from_arrays(
            [pa.array(rjson['accessionNumber']),
             pc.cast(pc.strptime(pa.array(rjson['filingDate']), '%Y-%m-%d', 'us'), pa.date32()),
             pa.array(rjson['reportDate']),
             pa.array(rjson['acceptanceDateTime']),
             pa.array(rjson['act']),
             pa.array(rjson['form']),
             pa.array(rjson['fileNumber']),
             pa.array(rjson['items']),
             pa.array(rjson['size']),
             pa.array(rjson['isXBRL']),
             pa.array(rjson['isInlineXBRL']),
             pa.array(rjson['primaryDocument']),
             pa.array(rjson['primaryDocDescription'])
             ],
            names=['accession_number',
                   'filing_date',
                   'reportDate',
                   'acceptanceDateTime',
                   'act',
                   'form',
                   'fileNumber',
                   'items',
                   'size',
                   'isXBRL',
                   'isInlineXBRL',
                   'primaryDocument',
                   'primaryDocDescription'
                   ]
        )
    return CompanyFilings(filings_table,
                          cik=cik,
                          company_name=company_name)


def parse_entity_submissions(cjson: Dict[str, Any]):
    mailing_addr = cjson['addresses']['mailing']
    business_addr = cjson['addresses']['business']
    cik = cjson['cik']
    company_name = cjson["name"]
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
                       filings=parse_filings(cjson['filings'], cik=cik, company_name=company_name),
                       insider_transaction_for_owner_exists=bool(cjson['insiderTransactionForOwnerExists']),
                       insider_transaction_for_issuer_exists=bool(cjson['insiderTransactionForIssuerExists']),
                       ein=cjson['ein'],
                       description=cjson['description'],
                       website=cjson['website'],
                       investor_website=cjson['investorWebsite'],
                       state_of_incorporation=cjson['stateOfIncorporation'],
                       state_of_incorporation_description=cjson['stateOfIncorporationDescription'],
                       former_names=cjson['formerNames'],
                       )


@lru_cache(maxsize=64)
def get_entity(entity_identifier: IntString, include_old_filings: bool = True) -> EntityData:
    """
        Get a company by cik or ticker

        Get company by ticker e.g.

        >>> get_entity("SNOW") or get_entity("tsla")

        Get company by cik e.g.

        >>> get_entity(1090990)

    :param entity_identifier: The company identifier. Can be a cik or a ticker
    :param include_old_filings: Include older filings
    :return:
    """
    is_int_cik = isinstance(entity_identifier, int)
    # Sometimes the cik is left zero padded e.g. 000198706
    is_string_cik = isinstance(entity_identifier, str) and entity_identifier.isdigit()
    is_cik = is_int_cik or is_string_cik

    if is_cik:
        # Cast to int to handle zero-padding
        return EntityData.for_cik(int(entity_identifier), include_old_filings=include_old_filings)

    # Get by ticker
    is_ticker = isinstance(entity_identifier, str) and re.match("[A-Za-z]{1,6}", entity_identifier, re.IGNORECASE)

    if is_ticker:
        return EntityData.for_ticker(entity_identifier, include_old_filings=include_old_filings)

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
def get_entity_submissions(cik: int,
                           include_old_filings: bool = True) -> Optional[EntityData]:
    # Check the environment var EDGAR_USE_LOCAL_DATA
    submissions_json: Optional[Dict[str, Any]] = None
    if os.getenv("EDGAR_USE_LOCAL_DATA"):
        submissions_json = load_company_submissions_from_local(cik)
        if not submissions_json:
            submissions_json = download_entity_submissions_from_sec(cik, include_old_filings=include_old_filings)
    else:
        submissions_json = download_entity_submissions_from_sec(cik, include_old_filings=include_old_filings)
    if submissions_json:
        return parse_entity_submissions(submissions_json)


@lru_cache(maxsize=32)
def download_entity_submissions_from_sec(cik: int,
                                         include_old_filings: bool = True) -> Dict[str, Any]:
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
    if include_old_filings:
        for old_file in submission_json['filings']['files']:
            old_sub = download_json("https://data.sec.gov/submissions/" + old_file['name'])
            for column in old_sub:
                submission_json['filings']['recent'][column] += old_sub[column]
    return submission_json


def parse_company_facts(fjson: Dict[str, object]):
    unit_dfs = []
    fact_meta_lst = []
    columns = ['namespace', 'fact', 'val', 'accn', 'start', 'end', 'fy', 'fp', 'form', 'filed', 'frame']

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

    facts = pa.Table.from_pandas(pd.concat(unit_dfs, ignore_index=True))
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
        return None
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
        return None
    return json.loads(submissions_file.read_text())


async def download_facts_async() -> Path:
    """
    Download company facts
    """
    log.info(f"Downloading Company facts to {get_edgar_data_directory()}/companyfacts")
    return await download_bulk_data("https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip")


def download_facts() -> Path:
    """
    Download company facts
    """
    return asyncio.run(download_facts_async())


async def download_submissions_async() -> Path:
    """
    Download company submissions
    """
    log.info(f"Downloading Company submissions to {get_edgar_data_directory()}/submissions")
    return await download_bulk_data("https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip")


def download_submissions() -> Path:
    """
    Download company facts
    """
    return asyncio.run(download_submissions_async())


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

    def latest(self) -> List[Fact]:
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
