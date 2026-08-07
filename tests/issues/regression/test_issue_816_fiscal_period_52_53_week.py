"""
Regression test for Issue #816 — fiscal_period mislabeled in
xbrl.facts.to_dataframe() for 52/53-week fiscal year companies (PFE, JNJ).

The XBRL instance parser's `_quarter_for_date` previously classified the
fiscal quarter from the raw calendar month of the period end. For 52/53-week
filers whose quarter ends pin to a weekday near the calendar quarter boundary,
the period_end can drift into the first days of the following calendar month
(e.g. JNJ Q2 2023 ended 2023-07-02). That caused:

    period_end 2023-07-02 → fiscal_period 'Q3' (should be 'Q2')
    period_end 2023-10-01 → fiscal_period 'Q4' (should be 'Q3')

The fix treats end dates within the first 7 days of a month as belonging to
the previous month for quarter classification, matching the ±15-day tolerance
already used for fiscal-year-end matching elsewhere in the XBRL package.
"""

from datetime import date

import pytest

from edgar.xbrl.parsers.instance import _quarter_for_date


# JNJ / PFE pattern: Dec FYE, quarter ends on Sunday nearest calendar quarter end.

@pytest.mark.fast
def test_jnj_pfe_q2_drifts_into_july():
    """JNJ Q2 2023 ended 2023-07-02 (Sun nearest Jun 30) — must classify as Q2."""
    assert _quarter_for_date(date(2023, 7, 2), 12) == "Q2"


@pytest.mark.fast
def test_jnj_pfe_q3_drifts_into_october():
    """JNJ Q3 2023 ended 2023-10-01 (Sun nearest Sep 30) — must classify as Q3."""
    assert _quarter_for_date(date(2023, 10, 1), 12) == "Q3"


@pytest.mark.fast
def test_jnj_recent_quarters_unaffected():
    """JNJ 2024 quarters fell on day 29/30 — must still classify correctly."""
    assert _quarter_for_date(date(2024, 6, 30), 12) == "Q2"
    assert _quarter_for_date(date(2024, 9, 29), 12) == "Q3"


# Standard calendar quarter ends (MRK, LLY, ABBV) — must remain unaffected.

@pytest.mark.fast
def test_calendar_quarter_ends_unaffected():
    """Companies with exact calendar quarter ends must classify as before."""
    assert _quarter_for_date(date(2023, 3, 31), 12) == "Q1"
    assert _quarter_for_date(date(2023, 6, 30), 12) == "Q2"
    assert _quarter_for_date(date(2023, 9, 30), 12) == "Q3"
    assert _quarter_for_date(date(2023, 12, 31), 12) == "Q4"


# Non-calendar FYE 52/53-week patterns.

@pytest.mark.fast
def test_aapl_53_week_q1_drifts_into_january():
    """AAPL Q1 of a 53-week fiscal year can end on Jan 3 — must classify as Q1."""
    # AAPL FYE: last Saturday of September. Q1 = first 13 weeks of fiscal year.
    # In a 53-week year, Q1 can land on the first few days of January.
    assert _quarter_for_date(date(2026, 1, 3), 9) == "Q1"


@pytest.mark.fast
def test_aapl_normal_quarters_unaffected():
    """AAPL quarter ends in late month (Sat nearest end of month) — classify correctly."""
    # FY2024 Q1 = Dec 30, 2023; Q2 = Mar 30, 2024; Q3 = Jun 29, 2024; Q4 = Sep 28, 2024
    assert _quarter_for_date(date(2023, 12, 30), 9) == "Q1"
    assert _quarter_for_date(date(2024, 3, 30), 9) == "Q2"
    assert _quarter_for_date(date(2024, 6, 29), 9) == "Q3"
    assert _quarter_for_date(date(2024, 9, 28), 9) == "Q4"


@pytest.mark.fast
def test_jan_fye_q1_drift_into_may():
    """Jan FYE filers (WMT/TGT-style) whose Q1 drifts into early May."""
    # FY end Jan: Q1=Feb-Apr, Q2=May-Jul, Q3=Aug-Oct, Q4=Nov-Jan.
    # A May 3 period end (drifted from late April) must still classify as Q1.
    assert _quarter_for_date(date(2024, 5, 3), 1) == "Q1"
    # Control: late-April end classifies as Q1.
    assert _quarter_for_date(date(2024, 4, 28), 1) == "Q1"


@pytest.mark.fast
def test_jun_fye_q2_drift_into_january():
    """Jun FYE filers (MSFT-style) whose Q2 drifts into early January."""
    # FY end Jun: Q1=Jul-Sep, Q2=Oct-Dec, Q3=Jan-Mar, Q4=Apr-Jun.
    # A Jan 2 period end (drifted from late December) must still classify as Q2.
    assert _quarter_for_date(date(2024, 1, 2), 6) == "Q2"


# Boundary: ensure the day-7 cutoff is inclusive and day-8 is not shifted.

@pytest.mark.fast
def test_day_7_treated_as_previous_month():
    """Day 7 is within the tolerance window — shift to previous month."""
    # Dec FYE: Apr 7 → would be Q2 without shift, Q1 with shift. Q1 is correct
    # for a 52/53-week filer whose Q1 drifted past Mar 31.
    assert _quarter_for_date(date(2024, 4, 7), 12) == "Q1"


@pytest.mark.fast
def test_day_8_not_shifted():
    """Day 8 is outside the tolerance window — classify by raw month."""
    # Dec FYE: Apr 8 stays as Q2.
    assert _quarter_for_date(date(2024, 4, 8), 12) == "Q2"
