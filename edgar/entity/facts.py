"""
Company facts functionality for the entity package.
"""
import logging
from functools import lru_cache
from typing import Dict, Any, Optional

import httpx
import numpy as np
import pandas as pd
import pyarrow as pa
from rich.panel import Panel

from edgar.core import log
from edgar.httprequests import download_json
from edgar.richtools import df_to_rich_table, repr_rich
from edgar.storage import get_edgar_data_directory, is_using_local_storage

try:
    from rich.group import Group
except ImportError:
    from rich.console import Group

__all__ = [
    'get_company_facts',
    'NoCompanyFactsFound',
    'EntityFacts',
    'CompanyFacts',
    'Fact',
    'CompanyConcept',
    'Concept',
    'get_concept'
]


class NoCompanyFactsFound(Exception):
    """Exception raised when no company facts are found for a given CIK."""
    def __init__(self, cik: int):
        super().__init__()
        self.message = f"""No Company facts found for cik {cik}"""


class Fact:
    """A single company fact from XBRL data."""
    def __init__(self,
                 end: str,
                 value: object,
                 accn: str,
                 fy: str,
                 fp: str,
                 form: str,
                 filed: str,
                 frame: str,
                 unit: str):
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


class EntityFacts:
    """
    Contains entity facts data from XBRL filings.
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


# Alias for backward compatibility
CompanyFacts = EntityFacts


class Concept:
    """A concept in XBRL (taxonomy and tag)."""
    def __init__(self,
                 taxonomy: str,
                 tag: str,
                 label: str,
                 description: str):
        self.taxonomy: str = taxonomy
        self.tag: str = tag
        self.label: str = label
        self.description: str = description


class CompanyConcept:
    """A company concept from XBRL data."""
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
    def from_json(cls, cjson: Dict[str, Any]):
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
            ),
            data=data
        )


def parse_company_facts(fjson: Dict[str, object]):
    """Parse company facts from JSON data."""
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
            import orjson as json
            f.write(json.dumps(company_facts_json))
            f.flush()
            f.close()
        return company_facts_json
    import orjson as json
    return json.loads(company_facts_file.read_text())


@lru_cache(maxsize=32)
def get_company_facts(cik: int):
    """
    Get company facts for a given CIK.
    
    Args:
        cik: The company CIK
        
    Returns:
        CompanyFacts: The company facts
        
    Raises:
        NoCompanyFactsFound: If no facts are found for the given CIK
    """
    # Check the environment var EDGAR_USE_LOCAL_DATA
    if is_using_local_storage():
        company_facts_json = load_company_facts_from_local(cik)
        if not company_facts_json:
            company_facts_json = download_company_facts_from_sec(cik)
    else:
        company_facts_json = download_company_facts_from_sec(cik)
    return parse_company_facts(company_facts_json)


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
        from edgar.core import Result
        company_concept_json = download_json(
            f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010}/{taxonomy}/{concept}.json")
        company_concept: CompanyConcept = CompanyConcept.from_json(company_concept_json)
        return company_concept
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            # Get the company
            from edgar.entity.core import get_entity
            company = get_entity(int(cik))
            if company.not_found:
                return Result.Fail("No company found for cik {cik}")
            else:
                error_message = (f"{taxonomy}:{concept} does not exist for company {company.name} [{cik}]. "
                                 "See https://fasb.org/xbrl")
                log.error(error_message)
                return Result.Fail(error=error_message)