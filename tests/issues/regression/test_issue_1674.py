"""Regression test for GH #1674: the Company cash-flow view listed dividends paid twice.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1674

The base cash-flow virtual tree has a PaymentsOfDividendsCommonStock node and
the industry extensions (banking, consumer goods, ...) add a PaymentsOfDividends
node. Both concepts normalize to DividendsPaid, so for a filer reporting only
PaymentsOfDividends the first node borrowed that fact through the normalized
key while the second node showed it under its own name: two rows, one payment.
A node no longer borrows a fact whose own concept has a row in the tree.

Ground truth: JPMorgan Chase 10-K FY2025 (0001628280-26-008131), consolidated
statement of cash flows (R9): dividends paid (16,625) million, filed as
us-gaap:PaymentsOfDividends; the company facts carry no
PaymentsOfDividendsCommonStock fact. Coca-Cola FY2025: 8,779 million.
"""
from datetime import date

import pytest

from edgar import Company
from edgar.entity.enhanced_statement import EnhancedStatementBuilder
from edgar.entity.models import FinancialFact


def _fact(concept, value, year):
    return FinancialFact(
        concept=f"us-gaap:{concept}", taxonomy="us-gaap", label=concept, value=value,
        numeric_value=float(value), unit="USD", period_start=date(year, 1, 1),
        period_end=date(year, 12, 31), period_type="duration", fiscal_year=year,
        fiscal_period="FY", filing_date=date(year + 1, 2, 15), form_type="10-K",
        statement_type="CashFlowStatement")


# Filler so each period clears the builder's five-facts threshold.
_FILLER = ["NetIncomeLoss", "ShareBasedCompensation", "IncreaseDecreaseInAccountsReceivable",
           "NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInFinancingActivities"]


def _facts(concept, values):
    return [fact for year, value in values.items()
            for fact in [_fact(concept, value, year)] + [_fact(f, 1_000_000, year) for f in _FILLER]]


def _rows(statement, concepts):
    found = []

    def walk(items):
        for item in items:
            if item.concept in concepts and any(v is not None for v in item.values.values()):
                found.append(item.concept)
            walk(item.children)
    walk(statement.items)
    return found


@pytest.mark.fast
def test_one_dividends_row_when_only_payments_of_dividends_is_filed():
    facts = _facts("PaymentsOfDividends", {2025: 16_625_000_000, 2024: 15_120_000_000})
    builder = EnhancedStatementBuilder(sic_code="6021")  # banking extension adds the second node
    statement = builder.build_multi_period_statement(facts, "CashFlowStatement", periods=2, annual=True)
    assert _rows(statement, {"PaymentsOfDividends", "PaymentsOfDividendsCommonStock"}) == ["PaymentsOfDividends"]


@pytest.mark.fast
def test_the_normalized_fallback_still_fills_a_row_with_no_own_node():
    # Base tree only (no industry extension): the common-stock node still shows the payment.
    facts = _facts("PaymentsOfDividends", {2025: 8_779_000_000, 2024: 8_359_000_000})
    statement = EnhancedStatementBuilder().build_multi_period_statement(
        facts, "CashFlowStatement", periods=2, annual=True)
    assert len(_rows(statement, {"PaymentsOfDividends", "PaymentsOfDividendsCommonStock"})) == 1


@pytest.mark.fast
def test_a_series_that_changes_concept_stays_one_row():
    # PaymentsOfDividendsCommonStock through FY2022, PaymentsOfDividends from FY2023:
    # one dividends series, not two half rows.
    facts = []
    for year in (2021, 2022, 2023, 2024):
        concept = "PaymentsOfDividendsCommonStock" if year <= 2022 else "PaymentsOfDividends"
        facts += [_fact(concept, 1_000_000 * year, year)] + [_fact(f, 1_000_000, year) for f in _FILLER]
    statement = EnhancedStatementBuilder(sic_code="6021").build_multi_period_statement(
        facts, "CashFlowStatement", periods=4, annual=True)
    rows = []

    def walk(items):
        for item in items:
            if item.concept in {"PaymentsOfDividends", "PaymentsOfDividendsCommonStock"}:
                rows.append(item)
            walk(item.children)
    walk(statement.items)
    assert len(rows) == 1
    assert rows[0].values == {f"FY {y}": 1_000_000.0 * y for y in (2024, 2023, 2022, 2021)}


@pytest.mark.network
def test_jpm_cash_flow_has_one_dividends_row():
    df = Company("JPM").cash_flow_statement(as_dataframe=True)
    rows = df[df.index.str.contains("PaymentsOfDividends")]
    assert rows["FY 2025"].tolist() == [16_625_000_000]
