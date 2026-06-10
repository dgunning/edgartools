"""
Regression test for Issue #848.

GAIN reports ``us-gaap:InvestmentCompanyDividendDistribution`` as discrete
~90-day quarters (no cumulative 9-month YTD fact). With YTD_9M absent,
``TTMCalculator._derive_q4_from_fy`` falls back to ``Q4 = FY - (Q1+Q2+Q3)``.

The fallback used to select the three input quarters by their ``fiscal_period``
label. But the SEC tags comparative facts in a re-filing with the FILING's
fiscal_period, so the same calendar quarter (2025-04-01..06-30, 28.79M) appears
labeled Q1, Q2 AND Q3 across successive 10-Qs. Keying on the label selected that
one quarter for all three slots, giving::

    Q4 = 57,162,000 - (28,788,000 * 3) = -29,202,000   # wrong, negative

The fix selects the input quarters by distinct calendar period (dedup by
period_end, latest periodic filing wins) instead of by the unreliable label.
This is the same fiscal_period-unreliability root cause as #793 / #796, applied
to the FY-minus-Q1Q2Q3 fallback path.

Correct Q4 for GAIN FY2026 = 57,162,000 - (28,788,000 + 9,289,000 + 9,528,000)
                           = 9,557,000.
"""

from datetime import date

import pytest

from edgar import Company, set_identity
from edgar.entity.models import DataQuality, FinancialFact
from edgar.ttm.calculator import TTMCalculator

CONCEPT = "us-gaap:InvestmentCompanyDividendDistribution"


def _q(period_start: date, period_end: date, value: float, fp: str, fy: int,
       filing_date: date, form_type: str = "10-Q") -> FinancialFact:
    """Build a discrete quarterly fact with explicit fy/fp tagging."""
    return FinancialFact(
        concept=CONCEPT,
        taxonomy="us-gaap",
        label="Investment Company Dividend Distribution",
        value=value,
        numeric_value=value,
        unit="USD",
        scale=1,
        period_start=period_start,
        period_end=period_end,
        period_type="duration",
        fiscal_year=fy,
        fiscal_period=fp,
        filing_date=filing_date,
        accession=f"0000000000-{fy % 100:02d}-{fp}",
        form_type=form_type,
        data_quality=DataQuality.HIGH,
    )


def _build_gain_like_discrete_quarters_with_comparatives():
    """Reproduce GAIN's FY2026 (Apr 2025 - Mar 2026) discrete-quarter pattern.

    Each successive 10-Q re-files the prior quarters as comparatives, tagged with
    the FILING's fiscal_period. So the same calendar quarter ends up labeled with
    multiple fiscal_periods across filings - the trap the fix must survive.
    """
    facts = []

    # Discrete quarter values (the actual GAIN numbers).
    q1 = (date(2025, 4, 1), date(2025, 6, 30), 28_788_000.0)
    q2 = (date(2025, 7, 1), date(2025, 9, 30), 9_289_000.0)
    q3 = (date(2025, 10, 1), date(2025, 12, 31), 9_528_000.0)

    # Q1 10-Q (filed 2025-08-12): Q1 only, tagged Q1.
    facts.append(_q(*q1, fp="Q1", fy=2026, filing_date=date(2025, 8, 12)))

    # Q2 10-Q (filed 2025-11-04): current Q2, plus Q1 comparative - BOTH tagged Q2.
    facts.append(_q(*q1, fp="Q2", fy=2026, filing_date=date(2025, 11, 4)))
    facts.append(_q(*q2, fp="Q2", fy=2026, filing_date=date(2025, 11, 4)))

    # Q3 10-Q (filed 2026-02-03): current Q3, plus Q1 & Q2 comparatives - ALL tagged Q3.
    facts.append(_q(*q1, fp="Q3", fy=2026, filing_date=date(2026, 2, 3)))
    facts.append(_q(*q2, fp="Q3", fy=2026, filing_date=date(2026, 2, 3)))
    facts.append(_q(*q3, fp="Q3", fy=2026, filing_date=date(2026, 2, 3)))

    # FY 10-K (filed 2026-05-12): full fiscal year.
    facts.append(_q(date(2025, 4, 1), date(2026, 3, 31), 57_162_000.0,
                    fp="FY", fy=2026, filing_date=date(2026, 5, 12), form_type="10-K"))

    return facts


@pytest.mark.fast
def test_q4_fallback_ignores_unreliable_fiscal_period_labels():
    """Q4 must be derived from distinct calendar quarters, not fiscal_period labels."""
    facts = _build_gain_like_discrete_quarters_with_comparatives()
    calc = TTMCalculator(facts)

    quarterly = calc.quarterize()
    q4s = [q for q in quarterly if q.fiscal_period == "Q4"]

    assert len(q4s) == 1, f"expected exactly one derived Q4, got {len(q4s)}"
    q4 = q4s[0]

    # 57,162,000 - (28,788,000 + 9,289,000 + 9,528,000) = 9,557,000
    assert q4.numeric_value == 9_557_000.0, (
        f"Q4 should be 9,557,000 (FY minus the three DISTINCT quarters), "
        f"got {q4.numeric_value:,.0f}. The buggy label-keyed selection produced "
        f"-29,202,000 by reusing the first quarter for all three slots."
    )

    # The derived Q4 must cover the true Q4 calendar window, not start mid-year.
    assert q4.period_start == date(2026, 1, 1)
    assert q4.period_end == date(2026, 3, 31)
    assert "derived_q4_fy_minus_q1q2q3" in (q4.calculation_context or "")


@pytest.mark.fast
def test_q4_fallback_not_negative_under_comparative_contamination():
    """The exact failure from the report: derived Q4 must not be negative."""
    facts = _build_gain_like_discrete_quarters_with_comparatives()
    calc = TTMCalculator(facts)

    quarterly = calc.quarterize()
    q4 = next(q for q in quarterly if q.fiscal_period == "Q4")

    assert q4.numeric_value > 0, (
        f"derived Q4 went negative ({q4.numeric_value:,.0f}) - regression of #848"
    )


@pytest.mark.fast
def test_q4_fallback_skipped_when_discrete_q4_already_reported():
    """If the company reports a discrete Q4, no Q4 should be derived (avoid double-count)."""
    facts = _build_gain_like_discrete_quarters_with_comparatives()
    # Add a real discrete Q4 ending on the fiscal year-end.
    facts.append(_q(date(2026, 1, 1), date(2026, 3, 31), 9_557_000.0,
                    fp="Q4", fy=2026, filing_date=date(2026, 5, 12)))

    calc = TTMCalculator(facts)
    quarterly = calc.quarterize()

    derived_q4 = [
        q for q in quarterly
        if q.fiscal_period == "Q4"
        and "derived" in (q.calculation_context or "")
    ]
    assert not derived_q4, (
        "must not derive Q4 when a discrete Q4 is already reported"
    )


@pytest.mark.network
def test_gain_dividend_distribution_q4_is_correct_real_data():
    """Ground-truth check against live GAIN facts (the originally reported repro)."""
    set_identity("test@example.com")
    company = Company("GAIN")
    facts = company.get_facts()

    concept_facts = (
        facts.query().by_concept(CONCEPT, exact=True).execute()
    )
    assert concept_facts, "expected InvestmentCompanyDividendDistribution facts for GAIN"

    calc = TTMCalculator(concept_facts)
    quarterly = calc.quarterize()

    derived_q4 = [
        q for q in quarterly
        if q.fiscal_period == "Q4" and "derived" in (q.calculation_context or "")
    ]
    assert derived_q4, "expected at least one derived Q4"

    # Every derived Q4 for this (positive-flow) concept must be positive.
    for q4 in derived_q4:
        assert q4.numeric_value > 0, (
            f"derived Q4 ending {q4.period_end} is negative "
            f"({q4.numeric_value:,.0f}) - regression of #848"
        )

    # FY2026 (period ending 2026-03-31) Q4 == 9,557,000.
    fy2026_q4 = [q for q in derived_q4 if q.period_end == date(2026, 3, 31)]
    assert len(fy2026_q4) == 1
    assert fy2026_q4[0].numeric_value == 9_557_000.0
