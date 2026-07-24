"""Regression test for GOOGL cash-flow quarterization (GH #907)."""

from datetime import date

import pytest

from edgar.entity.models import FinancialFact
from edgar.ttm.calculator import TTMCalculator


def _fact(start: str, end: str, value: int, period: str) -> FinancialFact:
    return FinancialFact(
        concept="us-gaap:NetCashProvidedByUsedInInvestingActivities",
        taxonomy="us-gaap",
        label="Net Cash Provided by (Used in) Investing Activities",
        value=value,
        numeric_value=value,
        unit="USD",
        period_start=date.fromisoformat(start),
        period_end=date.fromisoformat(end),
        period_type="duration",
        fiscal_year=2025,
        fiscal_period=period,
        filing_date=date(2026, 2, 5),
        form_type="10-K" if period == "FY" else "10-Q",
        accession=f"2025-{period}",
        statement_type="CashFlowStatement",
    )


@pytest.mark.fast
def test_negative_cash_flow_quarters_are_derived():
    """Net cash outflows are valid and must not be rejected as negative cash."""
    facts = [
        _fact("2025-01-01", "2025-03-31", -16_194_000_000, "Q1"),
        _fact("2025-01-01", "2025-06-30", -40_738_000_000, "Q2"),
        _fact("2025-01-01", "2025-09-30", -68_515_000_000, "Q3"),
        _fact("2025-01-01", "2025-12-31", -120_291_000_000, "FY"),
    ]

    quarters = TTMCalculator(facts).quarterize()

    assert [(fact.fiscal_period, fact.numeric_value) for fact in quarters] == [
        ("Q1", -16_194_000_000),
        ("Q2", -24_544_000_000),
        ("Q3", -27_777_000_000),
        ("Q4", -51_776_000_000),
    ]
