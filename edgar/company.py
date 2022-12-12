from functools import lru_cache
from typing import List, Dict, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import duckdb
from pydantic import BaseModel
from edgar.filing import Filing, Filings
from edgar.core import http_client

__all__ = [
    'Address',
    'Company',
    'CompanyFacts',
    'CompanyFilings',
    'get_company_facts',
    'get_company_tickers',
    'get_company_submissions',
    'get_ticker_to_cik_lookup'
]


class Address(BaseModel):
    street1: str
    street2: Optional[str]
    city: str
    state_or_country: str
    zipcode: str
    state_or_country_desc: str


class CompanyFacts:

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
    def db(self):
        con = duckdb.connect(database=':memory:')
        con.register('facts', self.facts)
        return con

    def __len__(self):
        return len(self.facts)

    def num_facts(self):
        return len(self.fact_meta)

    def __repr__(self):
        return f"Company Facts({self.name} [{self.cik}] {len(self.facts):,} total facts)"


class CompanyFilings(Filings):

    def __init__(self,
                 data: pa.Table,
                 cik: int,
                 company_name: str):
        super().__init__(data)
        self.cik = cik
        self.company_name = company_name

    def get_filing_at(self, item: int):
        return Filing(
            cik=self.cik,
            company=self.company_name,
            form=self.filing_index['form'][item].as_py(),
            date=self.filing_index['filingDate'][item].as_py(),
            accession_no=self.filing_index['accessionNumber'][item].as_py(),
        )


class Company(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    cik: int
    name: str
    tickers: List[str]
    exchanges: List[str]
    sic: int
    sic_description: str
    category: str
    fiscal_year_end: str
    entity_type: str
    phone: str
    flags: str
    business_address: Address
    mailing_address: Address
    filings: Filings

    @classmethod
    def for_cik(cls, cik: int):
        return get_company_submissions(cik)

    @classmethod
    def for_ticker(cls, ticker: str):
        cik = get_ticker_to_cik_lookup().get(ticker)
        if cik:
            return Company.for_cik(cik)

    @lru_cache(maxsize=1)
    def get_facts(self):
        return get_company_facts(self.cik)

    def get_filings(self, *form: str):
        company_filings = self.filings.filing_index
        if len(form) > 0:
            company_filings = company_filings.filter(
                pc.is_in(self.filings.filing_index['form'], pa.array(form)))
        return CompanyFilings(company_filings,
                              cik=self.cik,
                              company_name=self.name)

    def summary(self):
        return pd.DataFrame(
            [
                {'CIK': self.cik,
                 'Ticker': ','.join(self.tickers),
                 'Industry': self.sic_description,
                 'Exchange(s)': ','.join(self.exchanges)}
            ]
        )

    def _repr_html_(self):
        return f"""
        <h3>{self.name}</h3>
        {self.summary().style.hide(axis="index")._repr_html_()}
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


def parse_company_submissions(cjson: Dict[str, object]):
    mailing_addr = cjson['addresses']['mailing']
    business_addr = cjson['addresses']['business']
    cik = cjson['cik']
    company_name = cjson["name"]
    return Company(cik=cik,
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


@lru_cache(maxsize=32)
def get_company_facts(cik: int):
    company_facts_json = get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010}.json")
    return parse_company_facts(company_facts_json)


@lru_cache(maxsize=32)
def get_company_concept(cik: int,
                        taxonomy: str,
                        concept: str):
    company_concept_json = get_json(
        f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010}/{taxonomy}/{concept}.json")
    return company_concept_json


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
