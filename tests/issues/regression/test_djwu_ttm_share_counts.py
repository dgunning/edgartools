"""TTM summed weighted-average share counts instead of averaging them, and both
statement renderers printed a share count as an amount of money.

bead edgartools-djwu, found while triaging GH #910.

`TTMStatementBuilder` routes EPS concepts to a path that correctly averages
shares, but every other concept fell through to `TTMCalculator.calculate_ttm_trend`,
whose aggregation was an unconditional sum over the trailing four quarters. A
weighted-average share count already averages within its own quarter, so summing
four of them reported roughly four times the shares a company has:

    Alphabet Q2 2026 TTM basic   48,458,000,000   actual ~12,114,500,000
    Tesla   Q2 2026 TTM basic    12,921,000,000   actual  ~3,230,250,000

The fix is narrower than it first appears, and `_is_additive_concept` -- which
already excludes shares -- is the wrong predicate to reuse. It also excludes
per-share amounts, and `CommonStockDividendsPerShareDeclared` is a genuine flow:
JPMorgan's trailing-twelve-month dividend is the 5.90 it declared across four
quarters, not the 1.48 they average to. Only SHARES and RATIO units are levels
rather than flows.
"""

from datetime import date

import pytest

from edgar.entity.models import FinancialFact
from edgar.ttm.calculator import TTMCalculator


def _fact(concept, unit, value, year, quarter):
    """A duration fact for one quarter, which is what reaches the TTM rollup."""
    month = {1: 3, 2: 6, 3: 9, 4: 12}[quarter]
    return FinancialFact(
        concept=concept,
        taxonomy="us-gaap",
        label=concept,
        value=value,
        numeric_value=float(value),
        unit=unit,
        period_start=date(year, month - 2, 1),
        period_end=date(year, month, 28),
        period_type="duration",
        fiscal_year=year,
        fiscal_period=f"Q{quarter}",
        filing_date=date(year, month, 28),
        form_type="10-Q",
        accession="0000000000-00-000000",
    )


def _quarterly(concept, unit, values):
    return [_fact(concept, unit, v, 2025, i + 1) for i, v in enumerate(values)]


SHARE_COUNTS = [12_086_000_000, 12_116_000_000, 12_099_000_000, 12_151_000_000]


def test_share_counts_are_averaged_over_the_window():
    """Four weighted averages do not add up to a year's share count."""
    facts = _quarterly("us-gaap:WeightedAverageNumberOfSharesOutstandingBasic",
                       "shares", SHARE_COUNTS)
    trend = TTMCalculator(facts).calculate_ttm_trend(periods=1)

    expected = sum(SHARE_COUNTS) / 4
    assert trend.iloc[0]["ttm_value"] == pytest.approx(expected)
    # The defect, stated as the thing it must not be.
    assert trend.iloc[0]["ttm_value"] != pytest.approx(sum(SHARE_COUNTS))


def test_monetary_flows_are_still_summed():
    """The control: averaging everything non-additive would break revenue."""
    revenue = [100.0, 110.0, 120.0, 130.0]
    facts = _quarterly("us-gaap:Revenues", "USD", revenue)
    trend = TTMCalculator(facts).calculate_ttm_trend(periods=1)
    assert trend.iloc[0]["ttm_value"] == pytest.approx(sum(revenue))


def test_dividends_per_share_are_summed_not_averaged():
    """A per-share amount is a flow, and `_is_additive_concept` would average it.

    JPMorgan declared 1.40 + 1.50 + 1.50 + 1.50 over four quarters; its TTM
    dividend per share is 5.90, not 1.475.
    """
    declared = [1.40, 1.50, 1.50, 1.50]
    facts = _quarterly("us-gaap:CommonStockDividendsPerShareDeclared",
                       "USD per share", declared)
    trend = TTMCalculator(facts).calculate_ttm_trend(periods=1)
    assert trend.iloc[0]["ttm_value"] == pytest.approx(sum(declared))


def test_the_predicate_separates_levels_from_flows():
    calc = TTMCalculator(_quarterly("us-gaap:Revenues", "USD", [1.0, 1.0, 1.0, 1.0]))

    shares = _fact("us-gaap:WeightedAverageNumberOfSharesOutstandingBasic", "shares", 1, 2025, 1)
    per_share = _fact("us-gaap:CommonStockDividendsPerShareDeclared", "USD per share", 1, 2025, 1)
    money = _fact("us-gaap:Revenues", "USD", 1, 2025, 1)

    assert calc._is_window_average_concept(shares)
    assert not calc._is_window_average_concept(per_share)
    assert not calc._is_window_average_concept(money)


def test_yoy_growth_uses_the_same_aggregation():
    """A window average compared against a prior window SUM would be meaningless."""
    eight = SHARE_COUNTS + [12_200_000_000, 12_250_000_000, 12_300_000_000, 12_350_000_000]
    facts = [_fact("us-gaap:WeightedAverageNumberOfSharesOutstandingBasic", "shares", v,
                   2024 + i // 4, (i % 4) + 1) for i, v in enumerate(eight)]
    trend = TTMCalculator(facts).calculate_ttm_trend(periods=1)
    growth = trend.iloc[0]["yoy_growth"]
    # Both windows average, so growth is a few percent -- not the ~0 a
    # mean-over-sum comparison would give, nor the 3x an sum-over-mean would.
    assert growth is not None
    assert 0.0 < float(growth) < 0.10


def test_share_counts_do_not_render_as_currency():
    """A count of shares took the currency path and printed as '$12.1B'."""
    from edgar.entity.unit_handling import is_per_share_label, is_share_count_label

    assert is_share_count_label("us-gaap:WeightedAverageNumberOfSharesOutstandingBasic",
                                "Weighted Average Number of Shares Outstanding, Basic")
    # EPS must keep its dollars-and-cents formatting, so the two are exclusive.
    assert is_per_share_label("us-gaap:EarningsPerShareBasic", "Earnings Per Share, Basic")
    assert not is_share_count_label("us-gaap:EarningsPerShareBasic", "Earnings Per Share, Basic")
    assert not is_share_count_label("us-gaap:Revenues", "Total net sales")
