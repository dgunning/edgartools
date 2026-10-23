"""Regression: negated period-start and period-end rows of a roll-forward both survive.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1700

A roll-forward points at one balance concept twice under one parent: once with a
period-start label role (the opening balance) and once with a period-end role
(the closing balance). `PresentationParser` keeps a repeated child only when its
preferred label is a roll-forward role, and that set named only the 2003
`periodStartLabel` and `periodEndLabel`. A filer that presents the balance in
parentheses uses `negatedPeriodStartLabel` / `negatedPeriodEndLabel` instead, so
the closing arc was dropped as a duplicate. The statement and rendering code
then matched only the 2003 roles when it mapped instant balances onto duration
columns, so the surviving "Beginning Balance" row showed the period-END instant.

Period roles are now recognised by local name, negated or not, in the parser,
`Statement.to_dataframe()` and rendering.

Ground truth is Lesaka Technologies' 10-Q for the quarter ended 2023-09-30
(0001562762-23-000403), notes 6 and 7, in thousands: accumulated goodwill
impairment 18,876 opening and 18,816 closing; investment contracts 241 and 243;
insurance contracts 1,600 and 1,871.
"""

import pytest

from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.core import (
    is_period_boundary_label_role,
    is_period_end_label_role,
    is_period_start_label_role,
)
from edgar.xbrl.parsers.presentation import PresentationParser


@pytest.mark.parametrize("role, start, end", [
    ("http://www.xbrl.org/2003/role/periodStartLabel", True, False),
    ("http://www.xbrl.org/2003/role/periodEndLabel", False, True),
    ("http://www.xbrl.org/2009/role/negatedPeriodStartLabel", True, False),
    ("http://www.xbrl.org/2009/role/negatedPeriodEndLabel", False, True),
    ("http://xbrl.us/us-gaap/role/label/negatedPeriodStart", True, False),
    ("http://xbrl.us/us-gaap/role/label/negatedPeriodEnd", False, True),
    ("http://www.xbrl.org/2009/role/negatedLabel", False, False),
    ("http://www.xbrl.org/2003/role/totalLabel", False, False),
    (None, False, False),
])
def test_period_boundary_roles_are_recognised_negated_or_not(role, start, end):
    assert is_period_start_label_role(role) is start
    assert is_period_end_label_role(role) is end
    assert is_period_boundary_label_role(role) is (start or end)


NEGATED_ROLL_FORWARD = """<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
               xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:presentationLink xlink:type="extended" xlink:role="http://example.com/role/Goodwill">
    <link:loc xlink:type="locator" xlink:href="x.xsd#us-gaap_StatementLineItems" xlink:label="items"/>
    <link:loc xlink:type="locator" xlink:href="x.xsd#us-gaap_GoodwillImpairedAccumulatedImpairmentLoss" xlink:label="imp"/>
    <link:loc xlink:type="locator" xlink:href="x.xsd#us-gaap_GoodwillImpairmentLoss" xlink:label="loss"/>
    <link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child"
        xlink:from="items" xlink:to="imp" order="1"
        preferredLabel="http://www.xbrl.org/2009/role/negatedPeriodStartLabel"/>
    <link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child"
        xlink:from="items" xlink:to="loss" order="2"/>
    <link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child"
        xlink:from="items" xlink:to="imp" order="3"
        preferredLabel="http://www.xbrl.org/2009/role/negatedPeriodEndLabel"/>
  </link:presentationLink>
</link:linkbase>
"""


def test_roll_forward_labels_constant_includes_negated_period_roles():
    from edgar.xbrl.parsers.presentation import ROLL_FORWARD_LABELS
    assert "http://www.xbrl.org/2009/role/negatedPeriodStartLabel" in ROLL_FORWARD_LABELS
    assert "http://www.xbrl.org/2009/role/negatedPeriodEndLabel" in ROLL_FORWARD_LABELS
    assert all(is_period_boundary_label_role(role) for role in ROLL_FORWARD_LABELS)


def test_negated_closing_arc_is_not_deduplicated():
    trees = {}
    PresentationParser({}, trees, {}, role_types={}).parse_presentation_content(NEGATED_ROLL_FORWARD)
    node = trees["http://example.com/role/Goodwill"].all_nodes["us-gaap_StatementLineItems"]
    assert [label.rsplit("/", 1)[-1] if label else None
            for label in node.child_preferred_labels] == [
        "negatedPeriodStartLabel", None, "negatedPeriodEndLabel"]


LSAK_FOLDER = "https://www.sec.gov/Archives/edgar/data/1041514/000156276223000403/"
LSAK_FILES = ("lsak-20230930.xsd", "form10q_htm.xml", "lsak-20230930_pre.xml", "lsak-20230930_lab.xml")
BASE = "http://www.net1.com/role/"
ROLL_FORWARDS = {
    "GoodwillAndIntangibleAssetsNetSummaryOfMovementInCarryingValueOfGoodwillDetails":
        ("Accumulated impairment", 18_876_000, 18_816_000),
    "AssetsAndPolicyholderLiabilitiesUnderInsuranceAndInvestmentContractsSummaryOfMovementIn"
    "AssetsAndPolicyholderLiabilitiesUnderInvestmentContractsDetails":
        ("Investment contracts", 241_000, 243_000),
    "AssetsAndPolicyholderLiabilitiesUnderInsuranceAndInvestmentContractsSummaryOfTheMovementIn"
    "ReinsuranceAssetsAndPolicyholderLiabilitiesUnderInsuranceContractsDetails":
        ("Insurance contracts", 1_600_000, 1_871_000),
}


@pytest.mark.vcr
def test_lesaka_negated_roll_forwards_show_opening_and_closing_balances(tmp_path):
    """Ground truth: Lesaka Technologies 10-Q, 0001562762-23-000403, notes 6 and 7."""
    for name in LSAK_FILES:
        (tmp_path / name).write_text(download_file(LSAK_FOLDER + name), encoding="utf-8")
    xbrl = XBRL.from_directory(tmp_path)

    for role, (line, opening, closing) in ROLL_FORWARDS.items():
        statement = xbrl.get_disclosure(BASE + role)
        df = statement.to_dataframe()
        balances = df.set_index("label")["2023-09-30 (Q1)"]
        assert balances[f"{line}, Beginning Balance"] == opening
        assert balances[f"{line}, Ending Balance"] == closing

        rows = {text.strip().split("  ")[0]: text for text in str(statement).splitlines()}
        assert rows[f"{line}, Beginning Balance"].split()[-1] == f"{opening // 1000:,}"
        assert rows[f"{line}, Ending Balance"].split()[-1] == f"{closing // 1000:,}"
