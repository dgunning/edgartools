"""XBRL.to_pandas() facts include catalog metadata for colon-form concept ids.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1711

The facts export tested ``fact.element_id`` (``aubn:EmployeeRetentionTaxCredit``)
against a catalog keyed ``aubn_EmployeeRetentionTaxCredit``, so
``element_name``, ``element_type``, ``element_period_type``, ``element_balance``
and ``element_label`` were absent. The lookup tries the exact key, then only
the namespace separator. Auburn National Bancorporation FY2023 10-K,
accession 0001193125-24-067944.
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


def _missing(value) -> bool:
    return value is None or pd.isna(value)


def _row(facts: pd.DataFrame, fact_id: str) -> pd.Series:
    rows = facts.loc[facts["fact_id"] == fact_id]
    assert len(rows) == 1
    return rows.iloc[0]


@pytest.fixture(scope="module")
def aubn_xbrl():
    return XBRL.from_directory(AUBN)


def test_aubn_employee_retention_credit_keeps_filed_amounts_and_gains_metadata(aubn_xbrl):
    """ID_910 is the filed 2023 zero and ID_911 the filed 2022 credit of -1,569,000.

    Both are duration/debit monetary facts labeled "Employee Retention Tax Credit".
    The debit balance is metadata: it does not flip the sign. The concept id on
    the row stays the colon form the instance used.
    """
    facts = aubn_xbrl.to_pandas()["facts"]
    assert len(facts) == len(aubn_xbrl._facts) == 1844
    absent = [column for column in METADATA if column not in facts.columns]
    assert absent == []

    current = _row(facts, "ID_910")
    prior = _row(facts, "ID_911")
    assert (current["context_ref"], prior["context_ref"]) == (
        "FROM_Jan01_2023_TO_Dec31_2023_Entity_0000750574",
        "FROM_Jan01_2022_TO_Dec31_2022_Entity_0000750574",
    )
    assert (current["value"], prior["value"]) == ("0", "-1569000")
    assert (current["numeric_value"], prior["numeric_value"]) == (0.0, -1_569_000.0)
    assert (current["unit_ref"], prior["unit_ref"]) == ("USD", "USD")
    assert (int(current["decimals"]), int(prior["decimals"])) == (-3, -3)
    assert (current["element_id"], prior["element_id"]) == (
        "aubn:EmployeeRetentionTaxCredit",
        "aubn:EmployeeRetentionTaxCredit",
    )
    assert (current["fact_key"], prior["fact_key"]) == (
        "aubn_EmployeeRetentionTaxCredit|FROM_Jan01_2023_TO_Dec31_2023_Entity_0000750574",
        "aubn_EmployeeRetentionTaxCredit|FROM_Jan01_2022_TO_Dec31_2022_Entity_0000750574",
    )
    for row in (current, prior):
        assert (
            row["element_name"],
            row["element_type"],
            row["element_period_type"],
            row["element_balance"],
            row["element_label"],
        ) == (
            "aubn_EmployeeRetentionTaxCredit",
            "xbrli:monetaryItemType",
            "duration",
            "debit",
            "Employee Retention Tax Credit",
        )

    # Standard label, not the terse "FDIC and other regulatory assessments".
    # ID_605 is the filed 2023 assessment of 631,000.
    assessments = _row(facts, "ID_605")
    assert assessments["context_ref"] == "FROM_Jan01_2023_TO_Dec31_2023_Entity_0000750574"
    assert (assessments["value"], assessments["numeric_value"]) == ("631000", 631_000.0)
    assert assessments["element_id"] == "aubn:FdicAndOtherRegulatoryAssessments"
    assert (
        assessments["element_name"],
        assessments["element_type"],
        assessments["element_period_type"],
        assessments["element_balance"],
        assessments["element_label"],
    ) == (
        "aubn_FdicAndOtherRegulatoryAssessments",
        "xbrli:monetaryItemType",
        "duration",
        "debit",
        "Fdic and other regulatory assessments",
    )


def test_aubn_standard_concept_exports_its_label_and_leaves_unknown_fields_unknown(aubn_xbrl):
    """us-gaap:Assets is not in the company schema, so type and balance stay unknown.

    ID_754 is the undimensioned total assets of 975,255,000 at 2023-12-31. The
    label linkbase's standard label is "Total assets". Nothing in the export
    invents a balance or uses one to change the amount.
    """
    facts = aubn_xbrl.to_pandas()["facts"]
    assets = _row(facts, "ID_754")
    assert assets["element_id"] == "us-gaap:Assets"
    assert assets["context_ref"] == "AS_OF_Dec31_2023_Entity_0000750574"
    assert (assets["value"], assets["numeric_value"], assets["unit_ref"]) == (
        "975255000",
        975_255_000.0,
        "USD",
    )
    assert int(assets["decimals"]) == -3
    assert assets["element_name"] == "us-gaap_Assets"
    assert assets["element_period_type"] == "instant"
    assert assets["element_label"] == "Total assets"
    assert _missing(assets["element_type"])
    assert _missing(assets["element_balance"])


def _catalog_entry(name, *, data_type="xbrli:monetaryItemType", period_type="duration",
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


def _frames(facts, catalog, contexts=None):
    xbrl = XBRL()
    xbrl.parser.facts = {fact.fact_id: fact for fact in facts}
    xbrl.parser.element_catalog = catalog
    if contexts:
        xbrl.parser.contexts = contexts
    exported = xbrl.to_pandas()["facts"]
    assert len(exported) == len(facts)
    return exported


def test_exact_catalog_key_beats_the_namespace_fallback_and_only_the_separator_changes():
    """Colon form reaches the underscore entry. A second colon, another prefix,
    and an embedded underscore are not rewritten further. An exact key wins
    when both spellings are present.
    """
    credit_labels = {
        NEGATED_LABEL: "Negated display",
        STANDARD_LABEL: "Employee Retention Tax Credit",
    }
    catalog = {
        "aubn_EmployeeRetentionTaxCredit": _catalog_entry(
            "aubn_EmployeeRetentionTaxCredit", labels=credit_labels),
        "ns:Concept": _catalog_entry(
            "ns:Concept", data_type="exactType", period_type="duration",
            balance="credit", labels={STANDARD_LABEL: "Exact label"}),
        "ns_Concept": _catalog_entry(
            "ns_Concept", data_type="fallbackType", period_type="instant",
            balance="debit", labels={STANDARD_LABEL: "Fallback label"}),
        "pref_Local_Name": _catalog_entry(
            "pref_Local_Name", labels={STANDARD_LABEL: "Embedded underscore"}),
        "pref_Local:Name": _catalog_entry(
            "pref_Local:Name", labels={STANDARD_LABEL: "Second colon kept"}),
        "pref_Local_Name_collapsed": _catalog_entry(
            "pref_Local_Name_collapsed", labels={STANDARD_LABEL: "All colons replaced"}),
        "only_alt": _catalog_entry(
            "only_alt", data_type=None, period_type="instant", balance=None,
            labels={DOCUMENTATION_LABEL: "Docs only"}),
    }
    facts = _frames([
        _fact("aubn:EmployeeRetentionTaxCredit", "colon"),
        _fact("other:EmployeeRetentionTaxCredit", "other-prefix"),
        _fact("ns:Concept", "exact"),
        _fact("pref:Local_Name", "embedded"),
        _fact("pref:Local:Name", "second-colon"),
        _fact("pref_Local_Name", "already-underscore"),
        _fact("missing:Thing", "missing"),
        _fact("only_alt", "alternate-label"),
        _fact("ex:Zero", "zero", value="0", numeric_value=0.0),
        _fact("ex:Empty", "empty", value="", numeric_value=None, unit_ref=None, decimals=None),
    ], catalog)

    credit = _row(facts, "colon")
    assert credit["element_id"] == "aubn:EmployeeRetentionTaxCredit"
    assert (credit["numeric_value"], credit["value"]) == (10.0, "10")
    assert (
        credit["element_name"], credit["element_type"], credit["element_period_type"],
        credit["element_balance"], credit["element_label"],
    ) == (
        "aubn_EmployeeRetentionTaxCredit", "xbrli:monetaryItemType", "duration",
        "debit", "Employee Retention Tax Credit",
    )

    other = _row(facts, "other-prefix")
    assert other["element_id"] == "other:EmployeeRetentionTaxCredit"
    assert all(_missing(other[column]) for column in METADATA)

    exact = _row(facts, "exact")
    assert (exact["element_name"], exact["element_type"], exact["element_label"],
            exact["element_balance"], exact["element_period_type"]) == (
        "ns:Concept", "exactType", "Exact label", "credit", "duration")

    assert _row(facts, "embedded")["element_label"] == "Embedded underscore"
    assert _row(facts, "second-colon")["element_label"] == "Second colon kept"
    assert _row(facts, "already-underscore")["element_label"] == "Embedded underscore"
    assert _row(facts, "already-underscore")["element_id"] == "pref_Local_Name"

    missing = _row(facts, "missing")
    assert missing["element_id"] == "missing:Thing"
    assert all(_missing(missing[column]) for column in METADATA)

    alternate = _row(facts, "alternate-label")
    assert alternate["element_label"] == "Docs only"
    assert alternate["element_period_type"] == "instant"
    assert _missing(alternate["element_type"])
    assert _missing(alternate["element_balance"])

    zero = _row(facts, "zero")
    assert (zero["value"], zero["numeric_value"]) == ("0", 0.0)
    assert all(_missing(zero[column]) for column in METADATA)
    empty = _row(facts, "empty")
    assert empty["value"] == ""
    assert _missing(empty["numeric_value"])


def test_context_and_dimension_fields_stay_beside_the_new_metadata():
    context = Context(
        context_id="c-dim",
        entity={"identifier": "0000750574", "scheme": "http://www.sec.gov/CIK"},
        period={"type": "duration", "startDate": "2023-01-01", "endDate": "2023-12-31"},
        dimensions={"us-gaap:StatementClassOfStockAxis": "us-gaap:CommonStockMember"},
    )
    catalog = {
        "ex_Assessments": _catalog_entry(
            "ex_Assessments",
            labels={STANDARD_LABEL: "Assessments"},
        )
    }
    facts = _frames(
        [_fact(
            "ex:Assessments",
            "dim-fact",
            value="631000",
            numeric_value=631_000.0,
            context_ref="c-dim",
        )],
        catalog,
        contexts={"c-dim": context},
    )
    row = _row(facts, "dim-fact")
    assert (row["value"], row["numeric_value"], row["element_id"]) == (
        "631000", 631_000.0, "ex:Assessments")
    assert row["element_label"] == "Assessments"
    assert row["element_balance"] == "debit"
    assert (row["period_type"], row["period_start"], row["period_end"]) == (
        "duration", "2023-01-01", "2023-12-31")
    assert row["entity_identifier"] == "0000750574"
    assert row["dim_us-gaap_StatementClassOfStockAxis"] == "us-gaap:CommonStockMember"
