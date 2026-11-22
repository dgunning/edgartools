"""Regression: extract_nonaccrual() answers for the period asked, never another.

Bead: edgartools-a3m66

With no investment facts at the requested period, ``_determine_latest_instant``
fell back to the most common instant of the filing's other facts. A 10-K/A
that amends Part III only carries a cover page, so Ares Capital's FY2025
10-K/A (0001628280-26-020560) came back labelled 2025-06-30, its public-float
date, with no rate. A caller storing results by ``result.period`` overwrote
that quarter's real result with an empty one.

The same fallback, given investment facts on another date, moved Oxford Square's
10-Q for 2026-09-30 (0001213900-26-115688) to 2026-06-30, where its schedule
facts are dated, and read a 0.40% rate over a $1.71B schedule sum against a
$260M balance sheet. Across the latest 10-K and 10-Q of 351 active BDCs that
was the only filing the fallback changed, so a known period is now read as
given.
"""
from decimal import Decimal

import pytest

from edgar.bdc.nonaccrual import _determine_latest_instant


def test_no_period_falls_back_to_the_investment_instant():
    dim = 'dim_us-gaap_InvestmentIdentifierAxis'
    facts = [{'period_instant': '2025-06-30'}, {'period_instant': '2025-12-31', dim: 'A'}]
    assert _determine_latest_instant(facts) == '2025-12-31'


@pytest.mark.network
@pytest.mark.vcr
def test_cover_page_amendment_is_read_at_its_own_period():
    """Ares Capital 10-K/A for 2025-12-31 (0001628280-26-020560): a cover page only."""
    from edgar import find
    from edgar.bdc.nonaccrual import extract_nonaccrual

    filing = find('0001628280-26-020560')
    for period in (None, '2025-12-31'):
        result = extract_nonaccrual(filing, period=period)
        assert result.period == '2025-12-31'
        assert result.extraction_method == 'none'
        assert result.nonaccrual_rate is None
        assert any('no investment data' in w for w in result.warnings)


@pytest.mark.network
@pytest.mark.vcr
def test_off_calendar_amendment_keeps_its_fiscal_year_end():
    """PennantPark Investment 10-K/A for 2025-09-30 (0001193125-26-292627) came back as 2025-03-31."""
    from edgar import find
    from edgar.bdc.nonaccrual import extract_nonaccrual

    result = extract_nonaccrual(find('0001193125-26-292627'))
    assert result.period == '2025-09-30'
    assert result.nonaccrual_rate is None


@pytest.mark.network
@pytest.mark.vcr
def test_a_quarter_is_not_read_from_another_quarters_schedule():
    """Oxford Square 10-Q for 2026-09-30 (0001213900-26-115688): balance sheet investments $260,081,298."""
    from edgar import find
    from edgar.bdc.nonaccrual import extract_nonaccrual

    result = extract_nonaccrual(find('0001213900-26-115688'))
    assert result.period == '2026-09-30'
    assert result.total_portfolio_fair_value == Decimal('260081298')
    assert result.total_source == 'balance_sheet'
