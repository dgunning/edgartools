"""Expected-correct reproductions of stale stitched period-filter DataFrames.

Source: Golub Capital BDC, Inc., March 31, 2025 10-Q,
accession 0001476765-25-000040, tests/fixtures/xbrl/gbdc/gbdc-20250331_htm.xml.
The three selected observations retain their source values, contexts and units.
Only get_statement is a controlled adapter; XBRLS.query, StitchedFactsView and
StitchedFactQuery are the real implementations. This does not test full filing
parsing or statement stitching.

For complete_periods_only, the adapter deliberately includes StockIssued1 f-505
but omits its comparative f-506. That sparse input is a test arrangement, not a
claim that the issuer omitted a comparative value. Labels are adapter labels.
"""

import platform
import sys
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from lxml import etree

import edgar
from edgar.xbrl import XBRLS
from edgar.xbrl.stitching import query as query_module

pytestmark = [pytest.mark.reproduction, pytest.mark.fast]

XBRLI = "http://www.xbrl.org/2003/instance"
US_GAAP = "http://fasb.org/us-gaap/2024"
FIELDS = ("concept", "label", "period_start", "period_end", "numeric_value")
LABELS = {"InterestPaidNet": "Interest paid, net", "StockIssued1": "Stock issued"}


@pytest.fixture(scope="module")
def source_observations():
    """Read the selected source fields once, stopping after the third fact."""
    fixture = Path(__file__).resolve().parents[3] / "fixtures/xbrl/gbdc/gbdc-20250331_htm.xml"
    wanted = {"c-1", "c-26", "usd", "f-501", "f-502", "f-505"}
    selected = {}
    measure_namespaces = {}
    with fixture.open("rb") as source:
        for _, element in etree.iterparse(source, events=("end",), no_network=True):
            if element.get("id") in wanted:
                selected[element.get("id")] = deepcopy(element)
                if element.get("id") == "usd":
                    # deepcopy can omit namespaces used only in QName text.
                    measure_namespaces = element.find(f"{{{XBRLI}}}measure").nsmap
            parent = element.getparent()
            if parent is not None and parent.tag == f"{{{XBRLI}}}xbrl":
                element.clear()
                while element.getprevious() is not None:
                    del parent[0]
            if selected.keys() == wanted:
                break
    assert selected.keys() == wanted

    measure = selected["usd"].find(f"{{{XBRLI}}}measure")
    prefix, _, currency = measure.text.strip().rpartition(":")
    assert (measure_namespaces[prefix or None], currency) == (
        "http://www.xbrl.org/2003/iso4217", "USD"
    )

    contexts = {}
    for context_id, start, end in (
        ("c-1", "2024-10-01", "2025-03-31"),
        ("c-26", "2023-10-01", "2024-03-31"),
    ):
        context = selected[context_id]
        identifier = context.find(f"{{{XBRLI}}}entity/{{{XBRLI}}}identifier")
        dates = (
            context.findtext(f"{{{XBRLI}}}period/{{{XBRLI}}}startDate").strip(),
            context.findtext(f"{{{XBRLI}}}period/{{{XBRLI}}}endDate").strip(),
        )
        assert (identifier.get("scheme"), identifier.text.strip(), *dates) == (
            "http://www.sec.gov/CIK", "0001476765", start, end
        )
        contexts[context_id] = dates

    observations = []
    for fact_id, local_name, context_id, amount in (
        ("f-501", "InterestPaidNet", "c-1", 133282000),
        ("f-502", "InterestPaidNet", "c-26", 71205000),
        ("f-505", "StockIssued1", "c-1", 33704000),
    ):
        fact = selected[fact_id]
        name = etree.QName(fact)
        value = Decimal(fact.text.strip())
        assert (name.namespace, name.localname, fact.get("contextRef"), value,
                fact.get("unitRef"), int(fact.get("decimals"))) == (
            US_GAAP, local_name, context_id, amount, "usd", -3
        )
        start, end = contexts[fact.get("contextRef")]
        observations.append({
            "fact_id": fact_id,
            "context_ref": fact.get("contextRef"),
            "concept": f"us-gaap:{name.localname}",
            "label": LABELS[name.localname],
            "numeric_value": int(value),
            "unit_ref": fact.get("unitRef"),
            "currency": currency,
            "decimals": int(fact.get("decimals")),
            "period_start": start,
            "period_end": end,
        })

    print({"python": platform.python_version(), "pandas": pd.__version__,  # noqa: T201 - reproduction diagnostics
           "platform": platform.platform(), "edgartools_source_version": edgar.__version__,
           "executable": sys.executable, "imported_query": query_module.__file__})
    print({"accession": "0001476765-25-000040", "source_observations": observations})  # noqa: T201
    return observations


class SourceStatements(XBRLS):
    """Supply selected source rows at the stitched-statement input boundary."""

    def __init__(self, observations):
        super().__init__([SimpleNamespace(
            entity_info={"document_type": "10-Q"},
            entity_name="Golub Capital BDC, Inc.",
        )])
        self.observations = observations

    def get_statement(self, statement_type, max_periods=8, standard=True, **kwargs):
        assert statement_type == "CashFlowStatement"
        assert standard is False
        items = {}
        periods = {}
        for row in self.observations:
            period = f"duration_{row['period_start']}_{row['period_end']}"
            periods[period] = row["period_end"]
            item = items.setdefault(row["concept"], {
                "concept": row["concept"], "label": row["label"],
                "is_abstract": False, "has_values": True,
                "values": {}, "decimals": {},
            })
            item["values"][period] = row["numeric_value"]
            item["decimals"][period] = row["decimals"]
        return {
            "periods": list(periods.items()),
            "statement_data": list(items.values()),
            "period_sources": dict.fromkeys(periods, 0),
        }


def _query(owner):
    return owner.query(statement_types=["CashFlowStatement"], standardize=False)


def _rows(result, columns=FIELDS):
    records = result.to_dict("records") if isinstance(result, pd.DataFrame) else result
    return [tuple(row[field] for field in columns) for row in records]


def test_across_periods_rechecks_minimum_after_dataframe_is_cached(source_observations):
    owner = SourceStatements(source_observations[:2])
    query = _query(owner).across_periods(2)
    warm = _rows(query.to_dataframe())
    assert warm == _rows(source_observations[:2])

    query.across_periods(3)
    executed = _rows(query.execute())
    fresh = _rows(_query(owner).across_periods(3).to_dataframe())
    assert executed == fresh == []

    retained = _rows(query.to_dataframe())
    print({"case": "across_periods(2) -> across_periods(3)",  # noqa: T201 - reproduction diagnostics
           "warm": warm, "execute": executed, "fresh": fresh, "retained": retained})
    assert retained == [], "Cached DataFrame must reflect the new three-period minimum"


def test_complete_periods_only_rechecks_after_dataframe_is_cached(source_observations):
    owner = SourceStatements(source_observations)
    query = _query(owner)
    warm = _rows(query.to_dataframe())
    assert warm == _rows(source_observations)

    query.complete_periods_only()
    executed = _rows(query.execute())
    fresh = _rows(_query(owner).complete_periods_only().to_dataframe())
    expected = _rows(source_observations[:2])
    assert executed == fresh == expected

    retained = _rows(query.to_dataframe())
    print({"case": "complete_periods_only() after warm DataFrame",  # noqa: T201 - reproduction diagnostics
           "warm": warm, "execute": executed, "fresh": fresh, "retained": retained})
    assert retained == expected, "Cached DataFrame must exclude the one-period stock-issued row"


def test_across_periods_can_be_enabled_after_an_ordinary_dataframe(source_observations):
    owner = SourceStatements(source_observations)
    query = _query(owner)
    assert _rows(query.to_dataframe()) == _rows(source_observations)

    query.across_periods()
    fresh = _query(owner).across_periods().to_dataframe()
    assert _rows(query.to_dataframe()) == _rows(fresh) == _rows(source_observations[:2])


def test_across_periods_minimum_can_return_to_previous_population(source_observations):
    owner = SourceStatements(source_observations)
    query = _query(owner)
    for minimum, expected in (
        (1, source_observations),
        (2, source_observations[:2]),
        (1, source_observations),
        (3, []),
        (2, source_observations[:2]),
    ):
        retained = query.across_periods(minimum).to_dataframe()
        fresh = _query(owner).across_periods(minimum).to_dataframe()
        assert _rows(retained) == _rows(fresh) == _rows(expected)


def test_complete_periods_only_is_idempotent_and_reuses_frame(source_observations):
    query = _query(SourceStatements(source_observations)).complete_periods_only()
    first = query.to_dataframe()
    assert _rows(first) == _rows(source_observations[:2])
    assert query.complete_periods_only().to_dataframe() is first


def test_period_filters_compose_with_projection_sort_and_limit(source_observations):
    query = (_query(SourceStatements(source_observations))
             .across_periods(1).sort_by("numeric_value").limit(1))
    columns = ("numeric_value", "concept", "period_end")
    warm = query.to_pandas(*columns)
    assert list(warm.columns) == list(columns)
    assert _rows(warm, columns) == _rows(source_observations[2:], columns)

    query.complete_periods_only()
    complete = query.to_pandas(*columns)
    assert _rows(complete, columns) == _rows(source_observations[1:2], columns)

    query.across_periods(2).sort_by("numeric_value", ascending=False).limit(2)
    reversed_columns = ("period_end", "numeric_value")
    descending = query.to_dataframe(*reversed_columns)
    assert list(descending.columns) == list(reversed_columns)
    assert _rows(descending, reversed_columns) == _rows(source_observations[:2], reversed_columns)

    query.sort_by("numeric_value").limit(1)
    assert _rows(query.to_pandas(*columns), columns) == _rows(source_observations[1:2], columns)


def test_period_filter_cache_and_sibling_sort_preserve_source_order(source_observations):
    """Changing the retained population must not expose a sibling's ordering."""
    owner = SourceStatements(source_observations)
    query = _query(owner).across_periods(2)
    columns = ("concept", "label", "period_start", "period_end", "numeric_value")
    expected = [
        ("us-gaap:InterestPaidNet", "Interest paid, net", "2024-10-01", "2025-03-31", 133282000),
        ("us-gaap:InterestPaidNet", "Interest paid, net", "2023-10-01", "2024-03-31", 71205000),
        ("us-gaap:StockIssued1", "Stock issued", "2024-10-01", "2025-03-31", 33704000),
    ]
    warm = query.to_dataframe(*columns)
    assert _rows(query.execute(), columns) == _rows(warm, columns) == expected[:2]

    # No filters or transformations: this sibling reaches the owner's cached
    # list directly, so an in-place sort would reorder later populations.
    sibling = _query(owner).sort_by("numeric_value").execute()
    assert _rows(sibling, columns) == [expected[2], expected[1], expected[0]]

    # Keep the projection and every other retained-query setting unchanged.
    query.across_periods(1)
    assert _rows(query.execute(), columns) == expected
    widened = query.to_dataframe(*columns)
    assert list(widened.columns) == list(columns)
    assert _rows(widened, columns) == expected

    query.across_periods(2)
    assert _rows(query.execute(), columns) == expected[:2]
    restored = query.to_dataframe(*columns)
    assert _rows(restored, columns) == expected[:2]
    assert restored is warm
