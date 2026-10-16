"""
`to_pandas()` works on facts objects, as an alias of `to_dataframe()`.

Bead: edgartools-m3jpa

`Filings`, `XBRL` and `FilingSummary` export with `to_pandas()`; the facts
objects only had `to_dataframe()`. Code written against the first reaches for
`to_pandas()` here too: in the README agent eval it was the most common invented
API (8 of 19 failing Haiku scripts wrote `EntityFacts.to_pandas` or
`FactsView.to_pandas`), and docs/quick-guide.md itself documented it.

Ground truth: JPMorgan Chase 10-K for FY2023, accession 0000019617-24-000225,
us-gaap:RevenuesNetOfInterestExpense 2023-01-01..2023-12-31 = 158,104,000,000
(data.sec.gov companyconcept). The XBRL fixture is that filing; the
company-facts payload below is that one fact as data.sec.gov reports it.
"""
import pandas as pd
import pytest

from edgar.entity.parser import EntityFactsParser
from edgar.xbrl import XBRL
from tests.paths import FIXTURES_DIR

JPM_FY2023_TOTAL_NET_REVENUE = 158_104_000_000

COMPANY_FACTS = {
    "cik": 19617,
    "entityName": "JPMORGAN CHASE & CO",
    "facts": {"us-gaap": {"RevenuesNetOfInterestExpense": {
        "label": "Revenues, Net of Interest Expense",
        "description": "Revenue net of interest expense.",
        "units": {"USD": [{
            "start": "2023-01-01", "end": "2023-12-31", "val": JPM_FY2023_TOTAL_NET_REVENUE,
            "accn": "0000019617-24-000225", "fy": 2023, "fp": "FY", "form": "10-K",
            "filed": "2024-02-16", "frame": "CY2023",
        }]},
    }}},
}

pytestmark = pytest.mark.fast


@pytest.fixture(scope="module")
def jpm_xbrl():
    return XBRL.from_directory(FIXTURES_DIR / "xbrl" / "jpm" / "10k_2024")


def _assert_same_frame(alias: pd.DataFrame, original: pd.DataFrame):
    pd.testing.assert_frame_equal(alias, original)
    values = pd.to_numeric(alias.select_dtypes(exclude="bool").stack(), errors="coerce")  # noqa: PD013
    assert JPM_FY2023_TOTAL_NET_REVENUE in set(values.dropna())


def test_entity_facts_to_pandas():
    facts = EntityFactsParser.parse_company_facts(COMPANY_FACTS)
    _assert_same_frame(facts.to_pandas(), facts.to_dataframe())


def test_entity_facts_to_pandas_passes_arguments_through():
    facts = EntityFactsParser.parse_company_facts(COMPANY_FACTS)
    pd.testing.assert_frame_equal(facts.to_pandas(include_metadata=True),
                                  facts.to_dataframe(include_metadata=True))


def test_entity_fact_query_to_pandas():
    query = EntityFactsParser.parse_company_facts(COMPANY_FACTS).query().by_concept("RevenuesNetOfInterestExpense")
    _assert_same_frame(query.to_pandas(), query.to_dataframe())


def test_xbrl_facts_view_to_pandas(jpm_xbrl):
    pd.testing.assert_frame_equal(jpm_xbrl.facts.to_pandas(), jpm_xbrl.facts.to_dataframe())


def test_xbrl_fact_query_to_pandas(jpm_xbrl):
    query = jpm_xbrl.facts.query().by_concept("us-gaap:RevenuesNetOfInterestExpense", exact=True)
    _assert_same_frame(query.to_pandas(), query.to_dataframe())
