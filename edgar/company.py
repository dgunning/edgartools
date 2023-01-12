import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Dict, Optional, Union, Tuple

import duckdb
import httpx
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
from fastcore.basics import listify
from rich.console import Group
from rich.text import Text

from edgar.core import http_client, repr_df, log, Result, df_to_rich_table, repr_rich, display_size, get_bool
from edgar.filing import Filing, Filings

__all__ = [
    'Address',
    'Company',
    'get_concept',
    'get_company',
    'CompanyFacts',
    'CompanyFiling',
    'CompanyFilings',
    'CompanyConcept',
    'get_company_facts',
    'get_company_tickers',
    'get_company_submissions',
    'parse_company_submissions',
    'get_ticker_to_cik_lookup'
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


class CompanyFiling(Filing):

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
                 is_inline_xbrl: str):
        super().__init__(cik=cik, company=company, form=form, filing_date=filing_date, accession_no=accession_no)
        self.report_date = report_date
        self.file_number: str = file_number
        self.items: str = items
        self.size: int = size
        self.primary_document: str = primary_document
        self.primary_doc_description: str = primary_doc_description
        self.is_xbrl: bool = is_xbrl
        self.is_inline_xbrl: bool = is_inline_xbrl

    def get_related_filings(self):
        """Get all the filings related to this one"""
        return self.get_entity().get_filings(file_number=self.file_number, sort_by="filingDate")

    def __str__(self):
        return (f"CompanyFiling(company={self.company}, cik={self.cik}, form={self.form}, "
                f"filing_date={self.filing_date}, accession_no={self.accession_no})"
                )


class CompanyFacts:
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

    @lru_cache(maxsize=1)
    def to_duckdb(self):
        con = duckdb.connect(database=':memory:')
        con.register('facts', self.facts)
        return con

    def to_pandas(self):
        return self.facts.to_pandas()

    def __len__(self):
        return len(self.facts)

    def num_facts(self):
        return len(self.fact_meta)

    def __rich__(self) -> str:
        return Group(
            Text(f"Company Facts({self.name} [{self.cik}] {len(self.facts):,} total facts)")
            ,
            df_to_rich_table(self.facts)
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class CompanyFilings(Filings):

    def __init__(self,
                 data: pa.Table,
                 cik: int,
                 company_name: str):
        super().__init__(data)
        self.cik = cik
        self.company_name = company_name

    def __getitem__(self, item):
        return self.get_filing_at(item)

    def get_filing_at(self, item: int):
        return CompanyFiling(
            cik=self.cik,
            company=self.company_name,
            form=self.data['form'][item].as_py(),
            filing_date=self.data['filingDate'][item].as_py(),
            report_date=self.data['reportDate'][item].as_py(),
            accession_no=self.data['accessionNumber'][item].as_py(),
            file_number=self.data['fileNumber'][item].as_py(),
            items=self.data['items'][item].as_py(),
            size=self.data['size'][item].as_py(),
            primary_document=self.data['primaryDocument'][item].as_py(),
            primary_doc_description=self.data['primaryDocDescription'][item].as_py(),
            is_xbrl=self.data['isXBRL'][item].as_py(),
            is_inline_xbrl=self.data['isInlineXBRL'][item].as_py()
        )

    def latest(self, n: int = 1) -> int:
        """Get the latest n filings"""
        sort_indices = pc.sort_indices(self.data, sort_keys=[("filingDate", "descending")])
        sort_indices_top = sort_indices[:min(n, len(sort_indices))]
        latest_filing_index = pc.take(data=self.data, indices=sort_indices_top)
        filings = CompanyFilings(latest_filing_index,
                                 cik=self.cik,
                                 company_name=self.company_name)
        if len(filings) == 1:
            return filings[0]
        return filings

    def __str__(self):
        return f"{self.company_name} {self.cik} {super().__repr__()}"

    @lru_cache(maxsize=2)
    def data_summary(self) -> pd.DataFrame:
        return (self.data
                .to_pandas()
                .assign(size=lambda df: df['size'].apply(display_size),
                        isXBRL=lambda df: df.isXBRL.map({'1': True, 1: True}).fillna(""),
                        )
                .filter(["form", "filingDate", "accessionNumber", "isXBRL"])
                .rename(columns={"filingDate": "filed", "isXBRL": "xbrl"})
                )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __rich__(self) -> str:
        return Group(
            Text(self.summary),
            df_to_rich_table(self.data_summary())
        )

    def _repr_html_(self):
        start_date, end_date = self.date_range
        return f"""
            <h3>Filings for {self.company_name} - {self.cik}</h3>
            {repr_df(pd.DataFrame([{'Count': len(self), 'Start': start_date, 'End': end_date}]))}
        """


class Company:
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
                 filings: CompanyFilings,
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

    @property
    def industry(self):
        return self.sic_description

    @classmethod
    def for_cik(cls, cik: int):
        return get_company_submissions(cik)

    @classmethod
    def for_ticker(cls, ticker: str):
        cik = get_ticker_to_cik_lookup().get(ticker.upper())
        if cik:
            return Company.for_cik(cik)

    def get_facts(self) -> CompanyFacts:
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

        if form:
            company_filings = company_filings.filter(pc.is_in(company_filings['form'], pa.array(listify(form))))
        if accession_number:
            company_filings = company_filings.filter(
                pc.is_in(company_filings['accessionNumber'], pa.array(listify(accession_number))))
        if file_number:
            company_filings = company_filings.filter(pc.is_in(company_filings['fileNumber'],
                                                              pa.array(listify(file_number))))
        if is_xbrl is not None:
            company_filings = company_filings.filter(pc.equal(company_filings['isXBRL'], int(is_xbrl)))
        if is_inline_xbrl is not None:
            company_filings = company_filings.filter(pc.equal(company_filings['isInlineXBRL'], int(is_inline_xbrl)))

        if sort_by:
            company_filings = company_filings.sort_by(sort_by)

        return CompanyFilings(company_filings,
                              cik=self.cik,
                              company_name=self.name)

    def __repr__(self):
        return f"""Company({self.name} [{self.cik}] {','.join(self.tickers)}, {self.sic_description})"""

    def _repr_html_(self):
        summary = pd.DataFrame([{'CIK': self.cik, 'Industry': self.industry, 'Category': self.category}])
        ticker_info = pd.DataFrame({"Exchange": self.exchanges, "Ticker": self.tickers})
        return f"""
        <h3>{self.name}</h3>
        {repr_df(summary)}
        {repr_df(ticker_info)}
        """

    @staticmethod
    def parse_filings(filings_json: Dict[str, object],
                      cik: int,
                      company_name: str):
        rjson: Dict[str, List[object]] = filings_json['recent']

        filings_table = pa.Table.from_arrays(
            [pa.array(rjson['accessionNumber']),
             pa.array(rjson['filingDate']),
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
            names=['accessionNumber',
                   'filingDate',
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


def parse_company_submissions(cjson: Dict[str, object]):
    mailing_addr = cjson['addresses']['mailing']
    business_addr = cjson['addresses']['business']
    cik = cjson['cik']
    company_name = cjson["name"]
    return Company(cik=int(cik),
                   name=company_name,
                   tickers=cjson['tickers'],
                   exchanges=cjson['exchanges'],
                   sic=cjson['sic'],
                   sic_description=cjson['sicDescription'],
                   category=cjson['category'],
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
                   filings=Company.parse_filings(cjson['filings'], cik=cik, company_name=company_name)
                   )


def get_company(*,
                cik: int = None,
                ticker: str = None) -> Company:
    """
    Get a company by cik or ticker
    :param cik: The cik
    :param ticker: The ticker
    :return:
    """
    if cik:
        return Company.for_cik(cik)
    elif ticker:
        return Company.for_ticker(ticker)
    raise AssertionError("Provide either a cik or ticker")


def get_json(data_url: str):
    with http_client() as client:
        r = client.get(data_url)
        if r.status_code == 200:
            return r.json()
        r.raise_for_status()


@lru_cache(maxsize=32)
def get_company_submissions(cik: int):
    submission_json = get_json(f"https://data.sec.gov/submissions/CIK{cik:010}.json")
    return parse_company_submissions(submission_json)


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
    company_facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010}.json"
    try:
        company_facts_json = get_json(company_facts_url)
        return parse_company_facts(company_facts_json)
    except httpx.HTTPStatusError as err:
        if err.response.status_code == 404:
            logging.warning(f"No company facts found on url {company_facts_url}")
            raise NoCompanyFactsFound(cik=cik)
        else:
            raise


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
                 data: pa.Table):
        self.cik: str = cik
        self.entity_name: str = entity_name
        self.concept: Concept = concept
        self.data: pa.Table = data

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
                  cjson: Dict[str, object]):
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
        company_concept_json = get_json(
            f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010}/{taxonomy}/{concept}.json")
        company_concept: CompanyConcept = CompanyConcept.from_json(company_concept_json)
        return company_concept
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            # Get the company
            company = Company.for_cik(int(cik))
            if not company:
                return Result.Fail("No company found for cik {cik}")
            else:
                error_message = (f"{taxonomy}:{concept} does not exist for company {company.name} [{cik}]. "
                                 "See https://fasb.org/xbrl")
                log.error(error_message)
                return Result.Fail(error=error_message)


def get_company_tickers():
    tickers_json = get_json(
        "https://www.sec.gov/files/company_tickers.json"
    )
    ticker_df = (pd.DataFrame(list(tickers_json.values()))
                 .set_axis(['CIK', 'Ticker', 'Company'], axis=1)
                 .astype({'CIK': pd.Int64Dtype()})
                 )
    return ticker_df


def get_ticker_to_cik_lookup():
    tickers_json = get_json(
        "https://www.sec.gov/files/company_tickers.json"
    )
    return {value['ticker']: value['cik_str']
            for value in tickers_json.values()
            }
