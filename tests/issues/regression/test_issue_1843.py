"""Regression test for GH #1843: canonical income selection rejected declared primary statements.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1843

``StatementResolver.find_statement`` drops every candidate that lacks the
ordinary revenue and net-income concepts (issue #659). AEON's combined
operations statement ends in a custom ``aeon:LossAndComprehensiveLoss`` and has
no revenue; Barings BDC reports investment income. Both primaries, typed
``IncomeStatement`` by their root abstract and filed under the FilingSummary
"Statements" menu, were rejected: AEON fell through to a restatement-details
role and BBDC had no income statement at all. A candidate whose own catalog type
is the requested statement and which the filing declares a statement is now
accepted when no candidate in the same step passes the concept check, so a
validated role still wins over an unvalidated one.

Ground truth:
- AEON Biopharma 10-Q/A Q3 2023 (0001837607-24-000014), R4 "Condensed
  Consolidated Statements of Operations and Comprehensive Loss": operating
  income for the successor period July 23 - September 30, 2023 is 64,286
  (USD thousands); the predecessor January 1 - July 21, 2023 operating loss is
  (29,644).
- Barings BDC 10-Q Q2 2026 (0001379785-26-000030), R4 "Unaudited Consolidated
  Statements of Operations": total investment income for the three months
  ended June 30, 2026 is 65,202 (USD thousands).
"""
from types import SimpleNamespace

import pytest

from edgar import find
from edgar.exceptions import StatementNotFoundError
from edgar.xbrl.statement_resolver import StatementResolver

AEON_R4 = ("http://www.aeonbiopharma.com/role/"
           "StatementCondensedConsolidatedStatementsOfOperationsAndComprehensiveLoss")
AEON_R38 = ("http://www.aeonbiopharma.com/role/DisclosureRestatementOfPreviouslyIssuedFinancialStatements"
            "CondensedConsolidatedStatementOfOperationsAndComprehensiveLossDetails")
BBDC_R4 = "http://ir.barings.com/role/UnauditedConsolidatedStatementsofOperations"


def _stub(statements, nodes_by_role):
    trees = {role: SimpleNamespace(all_nodes=dict.fromkeys(nodes)) for role, nodes in nodes_by_role.items()}
    return SimpleNamespace(get_all_statements=lambda: statements, presentation_trees=trees)


def _stmt(role, stype, menu, definition, primary="us-gaap_IncomeStatementAbstract"):
    return {"role": role, "type": stype, "menu_category": menu, "definition": definition,
            "role_name": role.rsplit("/", 1)[-1], "primary_concept": primary}


@pytest.mark.fast
def test_declared_primary_without_ordinary_concepts_is_selected():
    primary = _stmt("http://x/role/StatementsOfOperations", "IncomeStatement", "Statements",
                    "00200 - Statement - STATEMENTS OF OPERATIONS")
    detail = _stmt("http://x/role/RestatementStatementOfOperationsDetails", "Disclosures", "Details",
                   "40303 - Disclosure - Restatement - Statement of Operations (Details)",
                   primary="us-gaap_PriorPeriodAdjustmentAbstract")
    xbrl = _stub([primary, detail], {
        primary["role"]: ["us-gaap_IncomeStatementAbstract", "us-gaap_OperatingIncomeLoss", "x_LossAndComprehensiveLoss"],
        detail["role"]: ["us-gaap_PriorPeriodAdjustmentAbstract", "us-gaap_NetIncomeLoss"],
    })
    _, role, _, _ = StatementResolver(xbrl).find_statement("IncomeStatement")
    assert role == primary["role"]  # was the restatement detail


@pytest.mark.fast
def test_a_validated_candidate_still_beats_a_declared_unvalidated_one():
    face = _stmt("http://x/role/StatementsOfIncome", "IncomeStatement", "Statements",
                 "00200 - Statement - STATEMENTS OF INCOME")
    sparse = _stmt("http://x/role/StatementsOfIncomeSupplement", "IncomeStatement", "Statements",
                   "00210 - Statement - STATEMENTS OF INCOME SUPPLEMENT")
    xbrl = _stub([sparse, face], {
        face["role"]: ["us-gaap_IncomeStatementAbstract", "us-gaap_Revenues", "us-gaap_NetIncomeLoss"],
        sparse["role"]: ["us-gaap_IncomeStatementAbstract", "us-gaap_OperatingIncomeLoss"],
    })
    _, role, _, _ = StatementResolver(xbrl).find_statement("IncomeStatement")
    assert role == face["role"]


@pytest.mark.fast
def test_a_role_not_declared_a_statement_is_still_rejected():
    # Typed by its root abstract, but filed as a detail: #659's protection holds.
    detail = _stmt("http://x/role/OperationsDetails", "IncomeStatement", "Details",
                   "40100 - Disclosure - Operations (Details)")
    xbrl = _stub([detail], {detail["role"]: ["us-gaap_IncomeStatementAbstract", "us-gaap_OperatingIncomeLoss"]})
    with pytest.raises(StatementNotFoundError):
        StatementResolver(xbrl).find_statement("IncomeStatement")


def _row(df, concept):
    return df[(df["concept"] == concept) & (df["dimension"] != True)].iloc[0]  # noqa: E712


@pytest.mark.network
def test_aeon_income_statement_is_the_primary_not_restatement_details():
    xbrl = find("0001837607-24-000014").xbrl()
    statement = xbrl.statements.income_statement()
    assert statement.role_or_type == AEON_R4  # was AEON_R38
    operating = _row(statement.to_dataframe(), "us-gaap_OperatingIncomeLoss")
    assert operating["2023-07-21 (YTD)"] == -29_644_000  # predecessor, Jan 1 - Jul 21, 2023


@pytest.mark.network
def test_bbdc_income_statement_is_available():
    xbrl = find("0001379785-26-000030").xbrl()
    statement = xbrl.statements.income_statement()  # was None
    assert statement.role_or_type == BBDC_R4
    income = _row(statement.to_dataframe(), "us-gaap_GrossInvestmentIncomeOperating")
    assert income["2026-06-30 (Q2)"] == 65_202_000
