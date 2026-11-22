"""Regression: every element-catalog lookup of a QName finds the concept.

Bead: edgartools-gtmsn (follow-up to GitHub Issue
https://github.com/dgunning/edgartools/issues/1711, PR #1909)

Facts and context dimensions name a concept by its QName ('us-gaap:Assets');
the element catalog keys on 'us-gaap_Assets'. Each caller converted on its
own, and ``check_period_data_quality`` never did: it looked up every fact by
its QName and found none. On the Auburn, Apple, Microsoft and JPMorgan
fixtures 0 of 13,058 fact lookups hit, so every period read 0% essential
coverage.

The rule now lives once in ``edgar.xbrl.core`` (``element_catalog_key``,
``catalog_entry``) and every caller uses it, except one exception kept on
purpose: ``XBRL._describe_dimension`` looks up the axis raw, so a statement
row's ``dimension_label`` keeps the axis QName. Callers string-match on it
(``edgar/bdc/investments.py``, GH #574, GH #1682).
"""
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.core import catalog_entry, element_catalog_key
from edgar.xbrl.period_data_check import check_period_data_quality

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl"


@pytest.mark.parametrize("element_id,key", [
    ("us-gaap:Assets", "us-gaap_Assets"),
    ("pref:Local_Name", "pref_Local_Name"),   # a local name keeps its underscores
    ("pref:Local:Name", "pref_Local:Name"),   # only the namespace separator changes
    ("us-gaap_Assets", "us-gaap_Assets"),
    ("Assets", "Assets"),
])
def test_catalog_key_changes_only_the_namespace_separator(element_id, key):
    assert element_catalog_key(element_id) == key


def test_catalog_entry_tries_the_exact_key_then_the_catalog_spelling():
    catalog = {"ns:Concept": "exact", "ns_Concept": "fallback", "us-gaap_Assets": "assets"}
    assert catalog_entry(catalog, "ns:Concept") == "exact"
    assert catalog_entry(catalog, "us-gaap:Assets") == "assets"
    assert catalog_entry(catalog, "us-gaap_Assets") == "assets"
    # a bare local name, another prefix, or nothing is never matched
    assert catalog_entry(catalog, "Assets") is None
    assert catalog_entry(catalog, "ifrs-full:Assets") is None
    assert catalog_entry(catalog, None) is None
    assert catalog_entry(catalog, "") is None


@pytest.fixture(scope="module")
def aubn():
    """Auburn National Bancorporation FY2023 10-K, accession 0001193125-24-067944."""
    return XBRL.from_directory(FIXTURES / "aubn" / "10k_2023")


def test_period_check_finds_the_balance_sheet_concepts(aubn):
    """Auburn tags us-gaap:Assets = 975,255,000 at 2023-12-31 (fact ID_754)."""
    assert aubn._facts["us-gaap_Assets|AS_OF_Dec31_2023_Entity_0000750574"].numeric_value == 975_255_000
    quality = check_period_data_quality(aubn, "instant_2023-12-31", "BalanceSheet")
    assert {"Assets", "Liabilities", "StockholdersEquity", "Cash"} <= set(quality["found_essentials"])
    assert quality["essential_coverage"] > 0


def test_a_statement_rows_dimension_label_keeps_the_axis_qname(aubn):
    """Auburn's parent-company noninterest expense: 239,000 for 2023, 326,000 for 2022.
    The axis stays a QName in dimension_label; only the member reads as a label."""
    df = aubn.statements.income_statement(view="detailed").to_dataframe(view="detailed")
    row = df[(df["concept"] == "us-gaap_NoninterestExpense") & (df["dimension_member"] == "srt_ParentCompanyMember")]
    assert len(row) == 1
    row = row.iloc[0]
    assert (row["2023-12-31 (FY)"], row["2022-12-31 (FY)"]) == (239_000.0, 326_000.0)
    assert row["dimension_axis"] == "srt:ConsolidatedEntitiesAxis"
    assert row["dimension_label"] == "srt:ConsolidatedEntitiesAxis: Parent Company"


def test_to_pandas_label_falls_back_to_a_display_role():
    """Microsoft FY2024 10-K: us-gaap:NetIncomeLoss has no standard label, only
    verbose and total ones; net income is 88,136,000,000."""
    msft = XBRL.from_directory(FIXTURES / "msft" / "10k_2024")
    facts = msft.to_pandas()["facts"]
    rows = facts[(facts["element_id"] == "us-gaap:NetIncomeLoss") & (facts["value"] == "88136000000")]
    assert len(rows) >= 1
    assert set(rows["element_label"]) == {"Net income available for common shareholders (A)"}
