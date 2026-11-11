"""Regression test for GH #1679: SAP's cash-flow "Dividends paid" row showed the equity total.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1679

``ifrs-full:DividendsPaid`` is "dividends recognised as distributions to owners",
an element of the statement of changes in equity. The IFRS fallback classed it as
a cash-flow concept, and its bare name is the normalization target of the
dividends concepts, so the Company cash-flow view's "Dividends paid" row
(PaymentsOfDividendsCommonStock) borrowed it. The filed cash-flow lines,
``DividendsPaidToEquityHoldersOfParentClassifiedAsFinancingActivities`` and
``DividendsPaidToNoncontrollingInterestsClassifiedAsFinancingActivities``, were
not classified at all and had no row.

Ground truth: SAP SE 20-F FY2025 (0001104659-26-020058), consolidated statement
of cash flows (R6): dividends paid EUR (2,743), (2,565), (2,395) million for
FY2025/2024/2023, and dividends paid on non-controlling interests (2), (1), (13).
The statement of changes in equity totals EUR 2,746 / 2,566 / 2,417 million.
"""
from datetime import date

import pytest

from edgar.entity.enhanced_statement import EnhancedStatementBuilder
from edgar.entity.mappings_loader import get_primary_statement
from edgar.entity.models import FinancialFact

PARENT = "DividendsPaidToEquityHoldersOfParentClassifiedAsFinancingActivities"
NCI = "DividendsPaidToNoncontrollingInterestsClassifiedAsFinancingActivities"

SAP_CASH = {PARENT: {2025: 2_743, 2024: 2_565}, NCI: {2025: 2, 2024: 1}}
SAP_EQUITY_TOTAL = {"DividendsPaid": {2025: 2_746, 2024: 2_566}}
_FILLER = ["ProfitLoss", "CashFlowsFromUsedInOperatingActivities", "CashFlowsFromUsedInFinancingActivities",
           "PaymentsOfLeaseLiabilitiesClassifiedAsFinancingActivities", "ProceedsFromBorrowingsClassifiedAsFinancingActivities"]


def _fact(concept, millions, year):
    return FinancialFact(
        concept=f"ifrs-full:{concept}", taxonomy="ifrs-full", label=concept, value=millions * 1_000_000,
        numeric_value=float(millions * 1_000_000), unit="EUR", period_start=date(year, 1, 1),
        period_end=date(year, 12, 31), period_type="duration", fiscal_year=year,
        fiscal_period="FY", filing_date=date(year + 1, 2, 26), form_type="20-F",
        # The parser classifies a fact this way (edgar/entity/parser.py)
        statement_type=get_primary_statement(concept))


def _sap_like_facts():
    facts = []
    for concept, series in {**SAP_CASH, **SAP_EQUITY_TOTAL}.items():
        facts += [_fact(concept, value, year) for year, value in series.items()]
    for year in (2025, 2024):
        facts += [_fact(concept, 1_000, year) for concept in _FILLER]
    return facts


def _rows(statement):
    rows = {}

    def walk(items):
        for item in items:
            if any(v is not None for v in item.values.values()):
                rows[item.concept] = item.values
            walk(item.children)
    walk(statement.items)
    return rows


@pytest.mark.fast
def test_equity_distribution_is_not_a_cash_flow_concept():
    assert get_primary_statement("DividendsPaid") == "StatementOfEquity"
    assert get_primary_statement(PARENT) == "CashFlowStatement"
    assert get_primary_statement(NCI) == "CashFlowStatement"


@pytest.mark.fast
def test_dividends_row_carries_the_filed_cash_line_and_nci_has_its_own_row():
    statement = EnhancedStatementBuilder().build_multi_period_statement(
        _sap_like_facts(), "CashFlowStatement", periods=2, annual=True)
    rows = _rows(statement)
    assert rows["PaymentsOfDividendsCommonStock"] == {"FY 2025": 2_743_000_000.0, "FY 2024": 2_565_000_000.0}
    assert rows[NCI] == {"FY 2025": 2_000_000.0, "FY 2024": 1_000_000.0}
    # The equity total is in no cash-flow row, under its own name or borrowed
    assert "DividendsPaid" not in rows
    assert not any(2_746_000_000.0 in values.values() for values in rows.values())


@pytest.mark.network
def test_sap_cash_flow_dividends_match_the_filed_statement():
    from edgar import Company

    df = Company("SAP").cash_flow_statement(as_dataframe=True)
    years = ["FY 2025", "FY 2024", "FY 2023"]
    assert df.loc["PaymentsOfDividendsCommonStock", years].tolist() == [2_743_000_000, 2_565_000_000, 2_395_000_000]
    assert df.loc[NCI, years].tolist() == [2_000_000, 1_000_000, 13_000_000]
