"""Regression test for Issue #796.

DX Q4 2025 NetIncomeLoss returned -133,387,935 instead of the correct
+185,359,000 (FY 319,066,000 - 9M 133,707,000). Root cause: a DEF 14A
proxy fact had corrupt fiscal metadata (fiscal_year=0, fiscal_period='')
and a wrong scale (319,065 vs 319,066,000). It entered the ANNUAL bucket
in TTMCalculator._derive_q4_from_fy and produced a buggy Q4 candidate
that won the dedup tiebreaker because the proxy was filed AFTER the 10-K.

Fix has two layers:
1. Skip facts with fiscal_period != expected value in derivation methods
2. Prefer periodic-report sources (10-K, 10-Q) over non-periodic in dedup
"""
from datetime import date

import pytest

from edgar.entity.models import DataQuality, FinancialFact
from edgar.ttm.calculator import TTMCalculator


def _fact(value, period_start, period_end, fiscal_year, fiscal_period,
          filing_date, form_type, accession='0000000000-00-000000'):
    return FinancialFact(
        concept='us-gaap:NetIncomeLoss',
        taxonomy='us-gaap',
        label='Net Income (Loss)',
        value=value,
        numeric_value=value,
        unit='USD',
        scale=1,
        period_start=period_start,
        period_end=period_end,
        period_type='duration',
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        filing_date=filing_date,
        accession=accession,
        form_type=form_type,
        data_quality=DataQuality.HIGH,
    )


@pytest.mark.fast
def test_q4_derivation_ignores_corrupt_def14a_fy_fact():
    """Reproduces DX scenario: 10-K FY fact + DEF 14A junk fact for same period."""
    facts = [
        # Quarterly facts (Q1, Q2, Q3 reported)
        _fact(-3_076_000, date(2025, 1, 1), date(2025, 3, 31),
              2025, 'Q1', date(2025, 4, 30), '10-Q'),
        _fact(-13_606_000, date(2025, 4, 1), date(2025, 6, 30),
              2025, 'Q2', date(2025, 7, 28), '10-Q'),
        _fact(150_388_000, date(2025, 7, 1), date(2025, 9, 30),
              2025, 'Q3', date(2025, 10, 27), '10-Q'),
        # YTD periods
        _fact(-16_682_000, date(2025, 1, 1), date(2025, 6, 30),
              2025, 'Q2', date(2025, 7, 28), '10-Q'),
        _fact(133_707_000, date(2025, 1, 1), date(2025, 9, 30),
              2025, 'Q3', date(2025, 10, 27), '10-Q'),
        # FY 2025 from 10-K (canonical)
        _fact(319_066_000, date(2025, 1, 1), date(2025, 12, 31),
              2025, 'FY', date(2026, 2, 25), '10-K'),
        # The bug: DEF 14A proxy historical fact with corrupt metadata and
        # wrong scale (1000x off). Filed AFTER the 10-K.
        _fact(319_065, date(2025, 1, 1), date(2025, 12, 31),
              0, '', date(2026, 4, 7), 'DEF 14A'),
    ]

    calc = TTMCalculator(facts)
    quarterly = calc._quarterize_facts()

    q4_2025 = [q for q in quarterly
               if q.fiscal_period == 'Q4' and q.period_end == date(2025, 12, 31)]
    assert len(q4_2025) == 1, f"Expected one Q4 2025, got {len(q4_2025)}"

    q4 = q4_2025[0]
    expected = 319_066_000 - 133_707_000  # 185,359,000
    assert q4.numeric_value == expected, (
        f"Q4 2025 should derive to {expected:,} (FY - YTD_9M from 10-K), "
        f"got {q4.numeric_value:,}. The corrupt DEF 14A fact (319,065 with "
        f"fiscal_period='') must be excluded from derivation."
    )


@pytest.mark.fast
def test_dedup_prefers_periodic_report_over_proxy():
    """When two facts share the same period_end, the periodic-report source wins
    even if the proxy was filed later."""
    pe = date(2024, 12, 31)
    ten_k = _fact(100_000_000, date(2024, 1, 1), pe,
                  2024, 'FY', date(2025, 2, 25), '10-K')
    proxy = _fact(99_999, date(2024, 1, 1), pe,
                  0, '', date(2025, 4, 7), 'DEF 14A')

    calc = TTMCalculator([ten_k, proxy])
    result = calc._deduplicate_by_period_end([ten_k, proxy])

    assert len(result) == 1
    assert result[0].form_type == '10-K'
    assert result[0].numeric_value == 100_000_000


@pytest.mark.fast
def test_dedup_falls_back_to_filing_date_within_same_tier():
    """Within the periodic-report tier, the more recent filing wins (e.g.,
    10-K/A amendment supersedes original 10-K)."""
    pe = date(2024, 12, 31)
    original = _fact(100_000_000, date(2024, 1, 1), pe,
                     2024, 'FY', date(2025, 2, 25), '10-K')
    amendment = _fact(101_000_000, date(2024, 1, 1), pe,
                      2024, 'FY', date(2025, 5, 1), '10-K/A')

    calc = TTMCalculator([original, amendment])
    result = calc._deduplicate_by_period_end([original, amendment])

    assert len(result) == 1
    assert result[0].form_type == '10-K/A'
    assert result[0].numeric_value == 101_000_000
