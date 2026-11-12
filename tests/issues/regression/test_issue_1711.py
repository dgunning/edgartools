"""XBRL.to_pandas() facts include catalog metadata for colon-form concept ids.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1711

The export tested colon-form fact ids against an underscore-keyed catalog.
Lookup tries the exact key, then only the namespace separator. A non-standard
label is kept when the standard label is absent. Filed amounts stay put,
including a zero and an empty fact, and a context's period, entity and
dimensions are exported beside the new columns. Auburn National
Bancorporation FY2023 10-K, accession 0001193125-24-067944.
"""
from pathlib import Path

import pandas as pd
import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.core import STANDARD_LABEL
from edgar.xbrl.models import Context, ElementCatalog, Fact

AUBN = Path("tests/fixtures/xbrl/aubn/10k_2023")
METADATA = (
    "element_name",
    "element_type",
    "element_period_type",
    "element_balance",
    "element_label",
)
NEGATED_LABEL = "http://www.xbrl.org/2009/role/negatedLabel"
DOCUMENTATION_LABEL = "http://www.xbrl.org/2003/role/documentation"
CREDIT = (
    "aubn_EmployeeRetentionTaxCredit",
    "xbrli:monetaryItemType",
    "duration",
    "debit",
    "Employee Retention Tax Credit",
)
ASSESSMENTS = (
    "ex_Assessments",
    "xbrli:monetaryItemType",
    "duration",
    "debit",
    "Assessments",
)

# fact_id, element_id, value, numeric_value (None when unparsed), metadata, context_ref.
# metadata is a tuple, or None when the catalog must not match. A None field
# inside the tuple must stay missing.
SPELLINGS = [
    ("colon", "aubn:EmployeeRetentionTaxCredit", "10", 10.0, CREDIT, "c-plain"),
    ("exact", "ns:Concept", "10", 10.0, (
        "ns:Concept", "exactType", "duration", "credit", "Exact label"), "c-plain"),
    ("embedded", "pref:Local_Name", "10", 10.0, (
        "pref_Local_Name", "xbrli:monetaryItemType", "duration", "debit", "Embedded underscore"), "c-plain"),
    ("second-colon", "pref:Local:Name", "10", 10.0, (
        "pref_Local:Name", "xbrli:monetaryItemType", "duration", "debit", "Second colon kept"), "c-plain"),
    ("underscore", "pref_Local_Name", "10", 10.0, (
        "pref_Local_Name", "xbrli:monetaryItemType", "duration", "debit", "Embedded underscore"), "c-plain"),
    ("other-prefix", "other:EmployeeRetentionTaxCredit", "10", 10.0, None, "c-plain"),
    ("local-name", "EmployeeRetentionTaxCredit", "10", 10.0, None, "c-plain"),
    # No standard label: the first other role is used, and unknown type and balance stay missing.
    ("alternate-label", "only_alt", "10", 10.0, (
        "only_alt", None, "instant", None, "Docs only"), "c-plain"),
]
# A filed zero is a value. An empty fact stays empty. Neither invents metadata.
# The dimensioned fact keeps its period, entity and member beside the catalog columns.
PRESERVED = [
    ("zero", "ex:Zero", "0", 0.0, None, "c-plain"),
    ("empty", "ex:Empty", "", None, None, "c-plain"),
    ("dimension", "ex:Assessments", "631000", 631_000.0, ASSESSMENTS, "c-dim"),
]
CASES = SPELLINGS + PRESERVED


def _missing(value) -> bool:
    return value is None or pd.isna(value)


def _row(facts: pd.DataFrame, fact_id: str) -> pd.Series:
    rows = facts.loc[facts["fact_id"] == fact_id]
    assert len(rows) == 1
    return rows.iloc[0]


def _assert_filed(row, element_id, value, amount, context_ref):
    assert (row["element_id"], row["context_ref"], row["value"]) == (element_id, context_ref, value)
    if amount is None:
        assert _missing(row["numeric_value"])
    else:
        assert row["numeric_value"] == amount


def _assert_metadata(row, metadata):
    if metadata is None:
        assert all(_missing(row[column]) for column in METADATA)
        return
    for column, expected in zip(METADATA, metadata, strict=True):
        if expected is None:
            assert _missing(row[column])
        else:
            assert row[column] == expected


def _entry(name, *, data_type="xbrli:monetaryItemType", period_type="duration",
           balance="debit", labels=None):
    return ElementCatalog(
        name=name,
        data_type=data_type,
        period_type=period_type,
        balance=balance,
        labels=labels if labels is not None else {STANDARD_LABEL: name},
    )


def _fact(element_id, fact_id, *, value="10", numeric_value=10.0, context_ref="c-plain",
          unit_ref="USD", decimals="-3"):
    return Fact(
        element_id=element_id,
        context_ref=context_ref,
        value=value,
        unit_ref=unit_ref,
        decimals=decimals,
        numeric_value=numeric_value,
        fact_id=fact_id,
    )


@pytest.fixture(scope="module")
def aubn_facts():
    xbrl = XBRL.from_directory(AUBN)
    facts = xbrl.to_pandas()["facts"]
    assert len(facts) == len(xbrl._facts) == 1844
    return facts


@pytest.fixture(scope="module")
def exported_facts():
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
        "only_alt": _entry(
            "only_alt", data_type=None, period_type="instant", balance=None,
            labels={DOCUMENTATION_LABEL: "Docs only"}),
        "ex_Assessments": _entry("ex_Assessments", labels={STANDARD_LABEL: "Assessments"}),
    }
    facts = []
    for fact_id, element_id, value, numeric_value, _metadata, context_ref in CASES:
        kwargs = {"value": value, "numeric_value": numeric_value, "context_ref": context_ref}
        if fact_id == "empty":
            kwargs["unit_ref"] = None
            kwargs["decimals"] = None
        facts.append(_fact(element_id, fact_id, **kwargs))
    xbrl = XBRL()
    xbrl.parser.facts = {fact.fact_id: fact for fact in facts}
    xbrl.parser.element_catalog = catalog
    xbrl.parser.contexts = {
        "c-dim": Context(
            context_id="c-dim",
            entity={"identifier": "0000750574", "scheme": "http://www.sec.gov/CIK"},
            period={"type": "duration", "startDate": "2023-01-01", "endDate": "2023-12-31"},
            dimensions={"us-gaap:StatementClassOfStockAxis": "us-gaap:CommonStockMember"},
        ),
    }
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
    _assert_filed(row, "aubn:EmployeeRetentionTaxCredit", value, amount, context_ref)
    assert (row["unit_ref"], int(row["decimals"])) == ("USD", -3)
    assert row["fact_key"] == f"aubn_EmployeeRetentionTaxCredit|{context_ref}"
    _assert_metadata(row, CREDIT)


def test_aubn_standard_concept_leaves_unknown_type_and_balance_missing(aubn_facts):
    """ID_754 is undimensioned total assets of 975,255,000 at 2023-12-31.

    us-gaap:Assets is not in the company schema, so type and balance stay unknown.
    """
    row = _row(aubn_facts, "ID_754")
    _assert_filed(
        row, "us-gaap:Assets", "975255000", 975_255_000.0, "AS_OF_Dec31_2023_Entity_0000750574")
    _assert_metadata(row, ("us-gaap_Assets", None, "instant", None, "Total assets"))


@pytest.mark.parametrize(
    "fact_id,element_id,value,amount,metadata,context_ref", SPELLINGS, ids=[case[0] for case in SPELLINGS])
def test_catalog_lookup_uses_exact_key_then_only_the_namespace_separator(
        exported_facts, fact_id, element_id, value, amount, metadata, context_ref):
    """Exact key wins. Another prefix, a second colon, or a bare local name does not match.

    A concept whose only label is a non-standard role still exports that label.
    """
    row = _row(exported_facts, fact_id)
    _assert_filed(row, element_id, value, amount, context_ref)
    _assert_metadata(row, metadata)


@pytest.mark.parametrize(
    "fact_id,element_id,value,amount,metadata,context_ref", PRESERVED, ids=[case[0] for case in PRESERVED])
def test_export_keeps_filed_amounts_and_context_fields(
        exported_facts, fact_id, element_id, value, amount, metadata, context_ref):
    """Zero and empty facts stay as filed. Period, entity and dimensions stay too."""
    row = _row(exported_facts, fact_id)
    _assert_filed(row, element_id, value, amount, context_ref)
    _assert_metadata(row, metadata)
    if context_ref != "c-dim":
        return
    assert (row["period_type"], row["period_start"], row["period_end"]) == (
        "duration", "2023-01-01", "2023-12-31")
    assert row["entity_identifier"] == "0000750574"
    assert row["dim_us-gaap_StatementClassOfStockAxis"] == "us-gaap:CommonStockMember"
