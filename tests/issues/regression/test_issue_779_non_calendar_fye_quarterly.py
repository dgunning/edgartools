"""
Regression test for Issue #779 follow-up regression introduced by #781.

When commit 310766f8 (fix for #781) added a `validate_fiscal_year_period_end`
filter to `_prepare_quarterly_facts`, the validator incorrectly assumed that
`fiscal_year == period_end.year` for all companies. That assumption is correct
for calendar-year-end filers but wrong for non-calendar FYE filers (ADSK,
WMT, NVDA, MSFT, etc.) whose fiscal_year is forward-looking — Q1/Q2/Q3 of
fiscal year N have period_end in calendar year N-1.

Effect on `Company('ADSK').income_statement(periods=4, annual=False)`:
  Before fix: columns ['Q4 2026', 'Q4 2025', 'Q4 2024', 'Q4 2023']
  After fix:  columns ['Q4 2026', 'Q3 2026', 'Q2 2026', 'Q1 2026']

This regression test exercises the validator at the unit level for all four
FYE patterns, plus the original #781 schedule-fact rejection case.
"""

from datetime import date

import pytest

from edgar.entity.enhanced_statement import validate_fiscal_year_period_end


@pytest.mark.fast
def test_validator_keeps_all_quarters_for_jan_fye_company():
    """ADSK / WMT / NVDA pattern: Jan 31 FYE — Q1/Q2/Q3 ended in prior calendar year."""
    # FY2026 ends Jan 31, 2026
    assert validate_fiscal_year_period_end(2026, date(2025, 4, 30), 1) is True   # Q1
    assert validate_fiscal_year_period_end(2026, date(2025, 7, 31), 1) is True   # Q2
    assert validate_fiscal_year_period_end(2026, date(2025, 10, 31), 1) is True  # Q3
    assert validate_fiscal_year_period_end(2026, date(2026, 1, 31), 1) is True   # Q4


@pytest.mark.fast
def test_validator_keeps_all_quarters_for_jun_fye_company():
    """MSFT pattern: Jun 30 FYE — Q1 ended in prior calendar year."""
    # FY2025 ends Jun 30, 2025
    assert validate_fiscal_year_period_end(2025, date(2024, 9, 30), 6) is True   # Q1
    assert validate_fiscal_year_period_end(2025, date(2024, 12, 31), 6) is True  # Q2
    assert validate_fiscal_year_period_end(2025, date(2025, 3, 31), 6) is True   # Q3
    assert validate_fiscal_year_period_end(2025, date(2025, 6, 30), 6) is True   # Q4


@pytest.mark.fast
def test_validator_keeps_all_quarters_for_sep_fye_company():
    """AAPL / ORCL pattern: Sep 30 FYE — Q1 ended in prior calendar year (late Dec)."""
    # FY2025 ends in late Sep 2025
    assert validate_fiscal_year_period_end(2025, date(2024, 12, 28), 9) is True  # Q1 (52/53-wk)
    assert validate_fiscal_year_period_end(2025, date(2025, 3, 29), 9) is True   # Q2
    assert validate_fiscal_year_period_end(2025, date(2025, 6, 28), 9) is True   # Q3
    assert validate_fiscal_year_period_end(2025, date(2025, 9, 27), 9) is True   # Q4


@pytest.mark.fast
def test_validator_keeps_all_quarters_for_dec_fye_company():
    """Control case: Dec 31 FYE (most companies) — must remain unaffected."""
    assert validate_fiscal_year_period_end(2024, date(2024, 3, 31), 12) is True  # Q1
    assert validate_fiscal_year_period_end(2024, date(2024, 6, 30), 12) is True  # Q2
    assert validate_fiscal_year_period_end(2024, date(2024, 9, 30), 12) is True  # Q3
    assert validate_fiscal_year_period_end(2024, date(2024, 12, 31), 12) is True  # Q4


@pytest.mark.fast
def test_validator_still_rejects_forward_looking_schedule_facts():
    """Original Issue #781 protection must still fire — schedule disclosures rejected."""
    # Forward-looking amortization schedule for a Dec-FYE company:
    # fy=2021 paired with end=2027-06-30 — 6 year mismatch, must be rejected
    assert validate_fiscal_year_period_end(2021, date(2027, 6, 30), 12) is False
    # Same shape for a Jan-FYE company — must still be rejected (year_diff is far too large)
    assert validate_fiscal_year_period_end(2021, date(2027, 6, 30), 1) is False
    # Schedule fact for Sep-FYE company
    assert validate_fiscal_year_period_end(2024, date(2028, 6, 30), 9) is False


@pytest.mark.fast
def test_validator_rejects_obvious_mismatches_for_jan_fye():
    """Sanity: the validator still catches genuine mismatches even with FYE awareness."""
    # ADSK: fy=2030 with period ending in 2025 is way off
    assert validate_fiscal_year_period_end(2030, date(2025, 4, 30), 1) is False
    # ADSK: fy=2020 with period ending in 2025 is way off the other direction
    assert validate_fiscal_year_period_end(2020, date(2025, 4, 30), 1) is False


@pytest.mark.fast
def test_validator_default_fye_preserves_issue_452_behavior():
    """Default fiscal_year_end_month=12 must preserve all existing #452 assertions."""
    # Early January (52/53-week calendar)
    assert validate_fiscal_year_period_end(2022, date(2023, 1, 1)) is True
    assert validate_fiscal_year_period_end(2023, date(2023, 1, 1)) is True
    assert validate_fiscal_year_period_end(2024, date(2023, 1, 1)) is False

    # Late December (year-end shift tolerance)
    assert validate_fiscal_year_period_end(2023, date(2023, 12, 31)) is True
    assert validate_fiscal_year_period_end(2024, date(2023, 12, 31)) is True
    assert validate_fiscal_year_period_end(2025, date(2023, 12, 31)) is False

    # Normal mid-year
    assert validate_fiscal_year_period_end(2023, date(2023, 6, 30)) is True
    assert validate_fiscal_year_period_end(2025, date(2023, 6, 30)) is False
