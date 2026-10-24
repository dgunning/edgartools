"""
Regression test: split adjustment skipped per-share amounts not named EarningsPerShare.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1687

EntityFactsParser maps the SEC unit "USD/shares" to "USD per share", which
apply_split_adjustments did not recognise as per-share, so dividends per share
and continuing-operations EPS stayed on the pre-split basis.
"""
from datetime import date

import pytest

from edgar.entity.models import FinancialFact
from edgar.entity.parser import EntityFactsParser
from edgar.ttm.splits import apply_split_adjustments

SPLIT = [{"date": date(2024, 6, 7), "ratio": 10.0}]


def _fact(concept, value, unit, accession=""):
    return FinancialFact(concept=concept, taxonomy="us-gaap", label=concept, value=value,
                         numeric_value=value, unit=unit, period_start=date(2023, 1, 30),
                         period_end=date(2023, 4, 30), period_type="duration",
                         filing_date=date(2023, 5, 26), form_type="10-Q", accession=accession)


@pytest.mark.fast
def test_parser_unit_is_adjusted_for_any_per_share_concept():
    unit = EntityFactsParser._clean_unit("USD/shares")
    assert unit == "USD per share"
    facts = [
        _fact("us-gaap:EarningsPerShareDiluted", 0.82, unit),
        _fact("us-gaap:CommonStockDividendsPerShareDeclared", 0.04, unit),
        _fact("us-gaap:IncomeLossFromContinuingOperationsPerDilutedShare", 0.82, unit),
    ]
    out = {f.concept.split(":")[1]: f.numeric_value for f in apply_split_adjustments(facts, SPLIT)}
    assert out["EarningsPerShareDiluted"] == pytest.approx(0.082)
    assert out["CommonStockDividendsPerShareDeclared"] == pytest.approx(0.004)
    assert out["IncomeLossFromContinuingOperationsPerDilutedShare"] == pytest.approx(0.082)


@pytest.mark.fast
def test_share_counts_and_non_share_units_unchanged_in_behaviour():
    shares = _fact("us-gaap:WeightedAverageNumberOfSharesOutstandingBasic", 2_470_000_000.0, "shares")
    money = _fact("us-gaap:Revenues", 7_192_000_000.0, "USD")
    ratio = _fact("us-gaap:EffectiveIncomeTaxRateContinuingOperations", 0.1, "number")
    out = apply_split_adjustments([shares, money, ratio], SPLIT)
    assert out[0].numeric_value == pytest.approx(24_700_000_000.0)
    assert out[1].numeric_value == 7_192_000_000.0
    assert out[2].numeric_value == 0.1


@pytest.mark.fast
def test_nvda_q1_fy2024_dividend_per_share_real_filing_value():
    """NVDA 10-Q accession 0001045810-23-000093 (quarter ended 2023-04-30) reports
    dividends declared per share of $0.04; on the June 2024 10-for-1 basis it is $0.004."""
    fact = _fact("us-gaap:CommonStockDividendsPerShareDeclared", 0.04, "USD per share",
                 accession="0001045810-23-000093")
    adjusted = apply_split_adjustments([fact], SPLIT)[0]
    assert adjusted.numeric_value == pytest.approx(0.004)
