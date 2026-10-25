"""Expected-correct reproductions of sibling stitched queries changing row order.

Source: Golub Capital BDC, Inc., March 31, 2025 10-Q,
accession 0001476765-25-000040, tests/fixtures/xbrl/gbdc/gbdc-20250331_htm.xml.
The selected InterestPaidNet observations keep their original values, contexts,
units and dates. Only the statement source is a controlled get_statement adapter;
XBRLS.query, StitchedFactsView and StitchedFactQuery are real implementations.
The label, minimal statement metadata and arrangement are synthetic test inputs,
not the result of parsing and stitching the full filing.

The newest-first order belongs to this controlled input. These tests require
independence from a sibling's requested ordering, not a universal newest-first
contract for unsorted queries. The second case never constructs a DataFrame.
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


@pytest.fixture(scope="module")
def source_observations():
    """Read the selected source fields once, stopping after the second fact."""
    fixture = Path(__file__).resolve().parents[3] / "fixtures/xbrl/gbdc/gbdc-20250331_htm.xml"
    wanted = {"c-1", "c-26", "usd", "f-501", "f-502"}
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
    for fact_id, context_id, amount in (
        ("f-501", "c-1", 133282000),
        ("f-502", "c-26", 71205000),
    ):
        fact = selected[fact_id]
        name = etree.QName(fact)
        value = Decimal(fact.text.strip())
        assert (name.namespace, name.localname, fact.get("contextRef"), value,
                fact.get("unitRef"), int(fact.get("decimals"))) == (
            US_GAAP, "InterestPaidNet", context_id, amount, "usd", -3
        )
        start, end = contexts[fact.get("contextRef")]
        observations.append({
            "fact_id": fact_id,
            "context_ref": fact.get("contextRef"),
            "concept": f"us-gaap:{name.localname}",
            "label": "Interest paid, net",
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
    """Supply authentic source observations in a controlled statement order."""

    def __init__(self, observations):
        super().__init__([SimpleNamespace(
            entity_info={"document_type": "10-Q"},
            entity_name="Golub Capital BDC, Inc.",
        )])
        self.observations = observations

    def get_statement(self, statement_type, max_periods=8, standard=True, **kwargs):
        assert statement_type == "CashFlowStatement"
        assert standard is False
        values = {}
        decimals = {}
        periods = []
        for row in self.observations:
            period = f"duration_{row['period_start']}_{row['period_end']}"
            values[period] = row["numeric_value"]
            decimals[period] = row["decimals"]
            periods.append((period, row["period_end"]))
        return {
            "periods": periods,
            "statement_data": [{
                "concept": self.observations[0]["concept"],
                "label": self.observations[0]["label"],
                "is_abstract": False, "has_values": True,
                "values": values, "decimals": decimals,
            }],
            "period_sources": dict.fromkeys(values, 0),
        }


def _query(owner):
    return owner.query(statement_types=["CashFlowStatement"], standardize=False)


def _rows(result):
    """Snapshot meaningful fields so later list mutations cannot alter a baseline."""
    records = result.to_dict("records") if isinstance(result, pd.DataFrame) else result
    return [tuple(row[field] for field in FIELDS) for row in records]


def test_sibling_sort_preserves_unchanged_limited_query_and_frame(source_observations):
    owner = SourceStatements(source_observations)
    query = _query(owner).limit(1)
    original = _rows(query.to_dataframe())
    assert original == _rows(source_observations[:1])

    sorted_rows = _rows(_query(owner).sort_by("period_end").execute())
    assert sorted_rows == list(reversed(_rows(source_observations)))

    executed = _rows(query.execute())
    same_owner = _rows(_query(owner).limit(1).to_dataframe())
    retained_frame = _rows(query.to_dataframe())
    fresh_owner = _rows(_query(SourceStatements(source_observations)).limit(1).to_dataframe())
    assert retained_frame == fresh_owner == original

    print({"case": "sibling sort after limited frame",  # noqa: T201 - reproduction diagnostics
           "initial": original, "sorted_sibling": sorted_rows,
           "unchanged_execute": executed, "fresh_same_owner": same_owner,
           "retained_frame": retained_frame, "fresh_owner": fresh_owner})
    assert {"unchanged_execute": executed, "fresh_same_owner": same_owner} == {
        "unchanged_execute": original, "fresh_same_owner": original,
    }, "A sibling sort must not change another query's selected observation"


def test_sibling_sort_preserves_owner_order_without_any_dataframe(source_observations):
    owner = SourceStatements(source_observations)
    query = _query(owner)
    original = _rows(query.execute())
    assert original == _rows(source_observations)

    sorted_rows = _rows(_query(owner).sort_by("period_end").execute())
    assert sorted_rows == list(reversed(original))

    executed = _rows(query.execute())
    same_owner = _rows(_query(owner).execute())
    fresh_owner = _rows(_query(SourceStatements(source_observations)).execute())
    assert fresh_owner == original

    print({"case": "sibling sort with execute only",  # noqa: T201 - reproduction diagnostics
           "initial": original, "sorted_sibling": sorted_rows,
           "unchanged_execute": executed, "fresh_same_owner": same_owner,
           "fresh_owner": fresh_owner})
    assert {"unchanged_execute": executed, "fresh_same_owner": same_owner} == {
        "unchanged_execute": original, "fresh_same_owner": original,
    }, "Sorting one query must preserve the owner's original order for other queries"


@pytest.mark.parametrize("limit", [None, 1])
def test_descending_sort_and_limit_preserve_reversed_owner_order(source_observations, limit):
    initial = list(reversed(source_observations))
    owner = SourceStatements(initial)
    query = _query(owner).sort_by("period_end", ascending=False)
    if limit is not None:
        query.limit(limit)

    result = query.execute()
    assert _rows(result) == _rows(source_observations[:limit])
    assert _rows(_query(owner).execute()) == _rows(initial)


@pytest.mark.parametrize("ascending", [True, False])
def test_equal_sort_keys_preserve_initial_order(source_observations, ascending):
    initial = list(reversed(source_observations))
    owner = SourceStatements(initial)
    # Both authentic observations share this concept; their distinct periods
    # and values make any reordering within the tie visible.
    result = _query(owner).sort_by("concept", ascending=ascending).execute()
    assert _rows(result) == _rows(initial)
    assert _rows(_query(owner).execute()) == _rows(initial)


def test_repeated_sorts_preserve_returned_lists_and_row_objects(source_observations):
    owner = SourceStatements(source_observations)
    original_rows = _query(owner).execute()
    original_by_period = {row["period_end"]: row for row in original_rows}
    expected = _rows(source_observations)
    assert _rows(original_rows) == expected

    ascending_query = _query(owner).sort_by("period_end")
    ascending_rows = ascending_query.execute()
    descending_rows = _query(owner).sort_by("period_end", ascending=False).execute()
    ascending_again = ascending_query.execute()

    assert _rows(original_rows) == expected
    assert _rows(ascending_rows) == list(reversed(expected))
    assert _rows(descending_rows) == expected
    assert _rows(ascending_again) == list(reversed(expected))
    for result in (ascending_rows, descending_rows, ascending_again):
        assert all(row is original_by_period[row["period_end"]] for row in result)
