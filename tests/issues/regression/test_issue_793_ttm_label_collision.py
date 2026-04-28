"""
Regression test for Issue #793.

When the SEC re-files prior-period facts as comparatives in next year's 10-Q,
the comparative version is tagged with the FILING's fiscal_year, not the
period's true fiscal_year. AGNC's Q1 2024 (period_end=2024-03-31) appears
twice in the facts: once tagged fy=2024 (original 2024 10-Q) and once tagged
fy=2025 (comparative in a 2025 10-Q).

`_deduplicate_by_period_end` keeps the most recently filed version, which
carries the comparative-shifted fiscal_year. `TTMCalculator.calculate_ttm_trend`
then labels each window with `as_of_fact.fiscal_year`, producing duplicate
column labels like "Q1 2025" for two distinct windows. The rendering layer's
dict-keyed mapping then collides, with the wrong window winning.

The fix: derive the label fiscal_year from period_end + FYE month rather than
trusting `as_of_fact.fiscal_year`.
"""

from datetime import date

import pandas as pd
import pytest

from edgar.entity.models import DataQuality, FinancialFact
from edgar.ttm.calculator import TTMCalculator


def _filing_date_after(period_end: date, year_offset: int = 0) -> date:
    """Compute a plausible filing date ~1 month after period_end, in (year+offset)."""
    y = period_end.year + year_offset
    m = period_end.month + 1
    if m > 12:
        m -= 12
        y += 1
    return date(y, m, 15)


def _quarter_start(period_end: date) -> date:
    """Approx quarter start = first day of (period_end.month - 2)."""
    m = period_end.month - 2
    if m < 1:
        # Should not happen for Q1/Q2/Q3/Q4 of a Dec-FYE company; defensive.
        m += 12
        y = period_end.year - 1
        return date(y, m, 1)
    return date(period_end.year, m, 1)


def _q(period_start: date, period_end: date, value: float, fp: str, fy: int,
       filing_date: date, concept: str = 'us-gaap:NetIncomeLoss') -> FinancialFact:
    """Build a quarterly fact with explicit fy/fp tagging."""
    return FinancialFact(
        concept=concept,
        taxonomy='us-gaap',
        label='Net Income',
        value=value,
        numeric_value=value,
        unit='USD',
        scale=1,
        period_start=period_start,
        period_end=period_end,
        period_type='duration',
        fiscal_year=fy,
        fiscal_period=fp,
        filing_date=filing_date,
        accession=f'0000000000-25-{fy:04d}',
        form_type='10-Q' if fp != 'Q4' else '10-K',
        data_quality=DataQuality.HIGH,
    )


def _build_dec_fye_quarterly_with_comparatives():
    """Build 12 quarters of facts mimicking AGNC's pattern: comparative re-filings.

    Pattern: original fact filed in year N's 10-Q has fy=N. Comparative refiled
    in year N+1's 10-Q has fy=N+1 but same period_end and value. The Q4 of any
    year is only filed once (as the FY 10-K), so it doesn't get a comparative.
    """
    quarters = []
    # Period ends and values for 3 fiscal years (2023, 2024, 2025)
    spec = {
        2023: [(date(2023, 3, 31), 'Q1', -181_000_000.0),
               (date(2023, 6, 30), 'Q2', 255_000_000.0),
               (date(2023, 9, 30), 'Q3', -423_000_000.0),
               (date(2023, 12, 31), 'Q4', 381_000_000.0)],
        2024: [(date(2024, 3, 31), 'Q1', 412_000_000.0),
               (date(2024, 6, 30), 'Q2', -80_000_000.0),
               (date(2024, 9, 30), 'Q3', 313_000_000.0),
               (date(2024, 12, 31), 'Q4', 86_000_000.0)],
        2025: [(date(2025, 3, 31), 'Q1', 15_000_000.0),
               (date(2025, 6, 30), 'Q2', -178_000_000.0),
               (date(2025, 9, 30), 'Q3', 764_000_000.0),
               (date(2025, 12, 31), 'Q4', 908_000_000.0)],
    }
    for fy, items in spec.items():
        for period_end, fp, value in items:
            period_start = _quarter_start(period_end)
            # Original filing in same fiscal year
            quarters.append(_q(period_start, period_end, value, fp, fy,
                               filing_date=_filing_date_after(period_end)))
            # Comparative re-filing in NEXT year (skip Q4 — Q4 is only the 10-K)
            if fp != 'Q4' and fy < 2025:
                quarters.append(_q(period_start, period_end, value, fp, fy + 1,
                                   filing_date=_filing_date_after(period_end, year_offset=1)))
    return quarters


@pytest.mark.fast
def test_ttm_trend_produces_unique_labels_under_comparative_filings():
    """Comparative fact contamination must not produce duplicate "Q1 2025" labels."""
    facts = _build_dec_fye_quarterly_with_comparatives()
    calc = TTMCalculator(facts)

    trend = calc.calculate_ttm_trend(periods=12)

    labels = trend['as_of_quarter'].tolist()
    assert len(labels) == len(set(labels)), (
        f"TTM labels must be unique. Got: {labels}, dupes: "
        f"{[l for l in labels if labels.count(l) > 1]}"
    )


@pytest.mark.fast
def test_ttm_trend_labels_match_period_end_year_for_dec_fye():
    """Label fiscal_year must equal period_end.year for Dec-FYE companies."""
    facts = _build_dec_fye_quarterly_with_comparatives()
    calc = TTMCalculator(facts)

    trend = calc.calculate_ttm_trend(periods=12)

    for _, row in trend.iterrows():
        period_end = row['as_of_date']
        expected_fy = period_end.year  # Dec FYE
        expected_label = f"{row['fiscal_period']} {expected_fy}"
        assert row['as_of_quarter'] == expected_label, (
            f"Window ending {period_end} should be labeled '{expected_label}', "
            f"got '{row['as_of_quarter']}'"
        )
        assert row['fiscal_year'] == expected_fy


@pytest.mark.fast
def test_ttm_value_aligns_with_label_for_dec_fye():
    """The 4-quarter sum must match the value for the labeled period."""
    facts = _build_dec_fye_quarterly_with_comparatives()
    calc = TTMCalculator(facts)

    trend = calc.calculate_ttm_trend(periods=12)

    # Q3 2024 TTM = Q4 2023 + Q1 2024 + Q2 2024 + Q3 2024 = 381 + 412 - 80 + 313 = 1,026M
    q3_2024 = trend[trend['as_of_quarter'] == 'Q3 2024']
    assert len(q3_2024) == 1
    assert q3_2024.iloc[0]['ttm_value'] == 1_026_000_000.0

    # Q3 2025 TTM = Q4 2024 + Q1 2025 + Q2 2025 + Q3 2025 = 86 + 15 - 178 + 764 = 687M
    q3_2025 = trend[trend['as_of_quarter'] == 'Q3 2025']
    assert len(q3_2025) == 1
    assert q3_2025.iloc[0]['ttm_value'] == 687_000_000.0

    # Q4 2025 TTM = full FY2025 = 15 - 178 + 764 + 908 = 1,509M
    q4_2025 = trend[trend['as_of_quarter'] == 'Q4 2025']
    assert len(q4_2025) == 1
    assert q4_2025.iloc[0]['ttm_value'] == 1_509_000_000.0


@pytest.mark.fast
def test_ttm_trend_works_when_no_comparative_contamination():
    """Sanity: the fix must not regress the simple case (no comparative duplicates)."""
    # Only originals — no comparative re-filings
    facts = []
    spec = [
        (date(2024, 3, 31), 'Q1', 2024, 100.0),
        (date(2024, 6, 30), 'Q2', 2024, 110.0),
        (date(2024, 9, 30), 'Q3', 2024, 120.0),
        (date(2024, 12, 31), 'Q4', 2024, 130.0),
        (date(2025, 3, 31), 'Q1', 2025, 140.0),
        (date(2025, 6, 30), 'Q2', 2025, 150.0),
        (date(2025, 9, 30), 'Q3', 2025, 160.0),
        (date(2025, 12, 31), 'Q4', 2025, 170.0),
    ]
    for period_end, fp, fy, val in spec:
        facts.append(_q(_quarter_start(period_end), period_end, val, fp, fy,
                        filing_date=_filing_date_after(period_end)))

    calc = TTMCalculator(facts)
    trend = calc.calculate_ttm_trend(periods=5)

    labels = trend['as_of_quarter'].tolist()
    assert len(labels) == len(set(labels)), f"unexpected dupes: {labels}"

    # First row = most recent = Q4 2025 = sum of all 4 quarters of 2025
    assert trend.iloc[0]['as_of_quarter'] == 'Q4 2025'
    assert trend.iloc[0]['ttm_value'] == 140.0 + 150.0 + 160.0 + 170.0
