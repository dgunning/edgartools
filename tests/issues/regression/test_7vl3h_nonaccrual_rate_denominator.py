"""Regression: the non-accrual rate is measured against the balance-sheet total.

Bead: edgartools-7vl3h

``_extract_nonaccrual_from_xbrl`` used to add up every ``InvestmentOwnedAtFairValue``
fact on ``InvestmentIdentifierAxis`` for the period. Many BDCs also tag subtotals
and totals on that axis ("Total Investments", "Debt Investments", country and lien
subtotals), so the denominator counted the portfolio two to five times and the
rate came out too low. Goldman Sachs Private Credit's FY2024 10-K
(0000950170-25-032199) summed to $45.42B against a $7.27B balance sheet; across
985 BDC filings 267 summed more than 1.5x their balance sheet.

Main Street's FY2024 10-K (0001396440-25-000018) reports "Total investments"
of $4,932,669 thousand on its balance sheet; the identifier rows summed to
$7,873,831,000, which put its rate at 0.58% instead of 0.92%.
"""
from decimal import Decimal

import pytest

from edgar.bdc.nonaccrual import _portfolio_total_fair_value

FV = 'us-gaap:InvestmentOwnedAtFairValue'
AXIS = 'dim_us-gaap_InvestmentIdentifierAxis'


def _fact(value, decimals='-3', **dims):
    return {'concept': FV, 'period_instant': '2024-12-31', 'numeric_value': value,
            'decimals': decimals, 'unit_ref': 'U_USD', **dims}


def test_balance_sheet_total_wins_over_identifier_rows():
    facts = [
        _fact(100.0, **{AXIS: 'Loan A'}),
        _fact(50.0, **{AXIS: 'Loan B'}),
        _fact(150.0, **{AXIS: 'Total Investments'}),
        _fact(150.0),
    ]
    assert _portfolio_total_fair_value(facts, '2024-12-31') == (Decimal('150.0'), 'balance_sheet')


def test_identifier_rows_are_summed_only_without_a_balance_sheet_total():
    facts = [_fact(100.0, **{AXIS: 'Loan A'}), _fact(50.0, **{AXIS: 'Loan B'})]
    assert _portfolio_total_fair_value(facts, '2024-12-31') == (Decimal('150.0'), 'schedule_sum')
    assert _portfolio_total_fair_value(facts, '2023-12-31') == (None, None)


@pytest.mark.network
@pytest.mark.vcr
def test_main_street_rate_uses_its_balance_sheet_total():
    """Ground truth: Main Street Capital 10-K for 2024-12-31, accession 0001396440-25-000018."""
    from edgar import find
    from edgar.bdc.nonaccrual import extract_nonaccrual

    result = extract_nonaccrual(find('0001396440-25-000018'))
    assert result.extraction_method == 'footnote'
    assert result.total_portfolio_fair_value == Decimal('4932669000')
    assert result.total_source == 'balance_sheet'
    assert result.nonaccrual_fair_value == Decimal('45343000')
    assert result.nonaccrual_rate == pytest.approx(0.009192, abs=1e-6)
