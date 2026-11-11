"""XBRL.to_pandas() facts include catalog metadata for colon-form concept ids.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1711

The export tested colon-form fact ids against an underscore-keyed catalog.
Auburn National Bancorporation FY2023 10-K, accession 0001193125-24-067944.
"""
from pathlib import Path

import pandas as pd
import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.core import STANDARD_LABEL
from edgar.xbrl.models import ElementCatalog, Fact

AUBN = Path("tests/fixtures/xbrl/aubn/10k_2023")
METADATA = (
    "element_name",
    "element_type",
    "element_period_type",
    "element_balance",
    "element_label",
)
NEGATED_LABEL = "http://www.xbrl.org/2009/role/negatedLabel"
CREDIT = (
    "aubn_EmployeeRetentionTaxCredit",
    "xbrli:monetaryItemType",
    "duration",
    "debit",
    "Employee Retention Tax Credit",
)

# fact_id, element_id, metadata tuple or None when the catalog must not match.
SPELLINGS = [
    ("colon", "aubn:EmployeeRetentionTaxCredit", CREDIT),
    ("exact", "ns:Concept", (
        "ns:Concept", "exactType", "duration", "credit", "Exact label")),
    ("embedded", "pref:Local_Name", (
        "pref_Local_Name", "xbrli:monetaryItemType", "duration", "debit", "Embedded underscore")),
    ("second-colon", "pref:Local:Name", (
        "pref_Local:Name", "xbrli:monetaryItemType", "duration", "debit", "Second colon kept")),
    ("underscore", "pref_Local_Name", (
        "pref_Local_Name", "xbrli:monetaryItemType", "duration", "debit", "Embedded underscore")),
    ("other-prefix", "other:EmployeeRetentionTaxCredit", None),
    ("local-name", "EmployeeRetentionTaxCredit", None),
]


def _missing(value) -> bool:
    return value is None or pd.isna(value)


def _row(facts: pd.DataFrame, fact_id: str) -> pd.Series:
    rows = facts.loc[facts["fact_id"] == fact_id]
    assert len(rows) == 1
    return rows.iloc[0]


def _metadata(row):
    return tuple(row[column] for column in METADATA)


def _entry(name, *, data_type="xbrli:monetaryItemType", period_type="duration",
           balance="debit", labels=None):
    return ElementCatalog(
        name=name,
        data_type=data_type,
        period_type=period_type,
        balance=balance,
        labels=labels if labels is not None else {STANDARD_LABEL: name},
    )


def _fact(element_id, fact_id):
    return Fact(
        element_id=element_id,
        context_ref="c-plain",
        value="10",
        unit_ref="USD",
        decimals="-3",
        numeric_value=10.0,
        fact_id=fact_id,
    )


@pytest.fixture(scope="module")
def aubn_facts():
    xbrl = XBRL.from_directory(AUBN)
    facts = xbrl.to_pandas()["facts"]
    assert len(facts) == len(xbrl._facts) == 1844
    return facts


@pytest.fixture(scope="module")
def spelling_facts():
    catalog = {
        "aubn_EmployeeRetentionTaxCredit": _entry(
            "aubn_EmployeeRetentionTaxCredit",
            labels={NEGATED_LABEL: "Negated display", STANDARD_LABEL: "Employee Retention Tax Credit"}),
        "ns:Concept": _entry(
            "ns:Concept", data_type="exactType", balance="credit",
            labels={STANDARD_LABEL: "Exact label"}),
        "ns_Concept": _entry(
            "ns_Concept", data_type="fallbackType", period_type="instant",
            labels={STANDARD_LABEL: "Fallback label"}),
        "pref_Local_Name": _entry("pref_Local_Name", labels={STANDARD_LABEL: "Embedded underscore"}),
        "pref_Local:Name": _entry("pref_Local:Name", labels={STANDARD_LABEL: "Second colon kept"}),
        "pref_Local_Name_collapsed": _entry(
            "pref_Local_Name_collapsed", labels={STANDARD_LABEL: "All colons replaced"}),
    }
    xbrl = XBRL()
    facts = [_fact(element_id, fact_id) for fact_id, element_id, _ in SPELLINGS]
    xbrl.parser.facts = {fact.fact_id: fact for fact in facts}
    xbrl.parser.element_catalog = catalog
    exported = xbrl.to_pandas()["facts"]
    assert len(exported) == len(facts)
    return exported


@pytest.mark.parametrize("fact_id,context_ref,value,amount", [
    ("ID_910", "FROM_Jan01_2023_TO_Dec31_2023_Entity_0000750574", "0", 0.0),
    ("ID_911", "FROM_Jan01_2022_TO_Dec31_2022_Entity_0000750574", "-1569000", -1_569_000.0),
])
def test_aubn_retention_credit_keeps_its_amount_and_gains_metadata(aubn_facts, fact_id, context_ref, value, amount):
    """ID_910 is the filed 2023 zero and ID_911 the filed 2022 credit of -1,569,000."""
    absent = [column for column in METADATA if column not in aubn_facts.columns]
    assert absent == []
    row = _row(aubn_facts, fact_id)
    assert row["context_ref"] == context_ref
    assert (row["value"], row["numeric_value"], row["unit_ref"], int(row["decimals"])) == (
        value, amount, "USD", -3)
    assert row["element_id"] == "aubn:EmployeeRetentionTaxCredit"
    assert row["fact_key"] == f"aubn_EmployeeRetentionTaxCredit|{context_ref}"
    assert _metadata(row) == CREDIT


def test_aubn_standard_concept_leaves_unknown_type_and_balance_missing(aubn_facts):
    """ID_754 is undimensioned total assets of 975,255,000 at 2023-12-31.

    us-gaap:Assets is not in the company schema, so type and balance stay unknown.
    """
    row = _row(aubn_facts, "ID_754")
    assert (row["element_id"], row["context_ref"], row["value"], row["numeric_value"]) == (
        "us-gaap:Assets", "AS_OF_Dec31_2023_Entity_0000750574", "975255000", 975_255_000.0)
    assert (row["element_name"], row["element_period_type"], row["element_label"]) == (
        "us-gaap_Assets", "instant", "Total assets")
    assert _missing(row["element_type"]) and _missing(row["element_balance"])


@pytest.mark.parametrize("fact_id,element_id,metadata", SPELLINGS, ids=[case[0] for case in SPELLINGS])
def test_catalog_lookup_uses_exact_key_then_only_the_namespace_separator(spelling_facts, fact_id, element_id, metadata):
    """Exact key wins. Another prefix, a second colon, or a bare local name does not match."""
    row = _row(spelling_facts, fact_id)
    assert (row["element_id"], row["context_ref"], row["value"], row["numeric_value"]) == (
        element_id, "c-plain", "10", 10.0)
    if metadata is None:
        assert all(_missing(row[column]) for column in METADATA)
    else:
        assert _metadata(row) == metadata
