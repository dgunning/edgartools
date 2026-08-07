"""Regression test for GitHub Issue #893.

``EntityFacts.get_ttm_revenue()`` / ``get_ttm_net_income()`` silently returned
values that were wrong by more than an order of magnitude for companies that
migrated XBRL revenue tags. NVIDIA reported revenue under
``RevenueFromContractWithCustomerExcludingAssessedTax`` only through FY2022, then
moved to ``us-gaap:Revenues``; GOOG did the same a year later. ``get_ttm_revenue``
tried candidate concepts in a fixed order and returned the *first* that resolved
(>=4 quarters), so it stayed on the abandoned tag and summed its most-recent
quarters — NVDA's FY2020 quarters, giving $10.9B instead of $250B+, with no
exception, no ``has_gaps``, and no ``warning``.

Fix (companion of GH #892's get_concept recency fix):
1. Primary — ``get_ttm_revenue``/``get_ttm_net_income`` now evaluate every
   candidate concept and return the one whose TTM window ends most recently
   (by ``as_of_date``), tie-broken by priority order, instead of the first that
   resolves. This alone moves NVDA/GOOG onto the current ``Revenues`` tag.
2. Defense-in-depth — ``TTMCalculator`` now sets ``TTMMetric.is_stale`` (and a
   warning) when the newest quarter lags the reference date (``as_of``, or today)
   by more than one reporting cycle, so genuinely stale data across *all*
   candidates is still detectable programmatically.
"""
import datetime
from datetime import date

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact

pytestmark = pytest.mark.regression


def _quarter_fact(concept, value, period_end, fiscal_year, fiscal_period):
    """A discrete single-quarter (~90 day) revenue fact."""
    return FinancialFact(
        concept=concept,
        taxonomy='us-gaap',
        label='Revenue',
        value=value,
        numeric_value=float(value),
        unit='USD',
        period_type='duration',
        period_start=period_end - datetime.timedelta(days=89),
        period_end=period_end,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        accession=f'0001234-{str(fiscal_year)[2:]}-000001',
        filing_date=period_end + datetime.timedelta(days=30),
        form_type='10-Q',
    )


_STALE_TAG = 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'  # priority 0
_FRESH_TAG = 'us-gaap:Revenues'  # priority 1

# Four FY2020 quarters under the top-priority (later abandoned) tag.
_STALE_QUARTERS = [
    _quarter_fact(_STALE_TAG, 100, date(2020, 3, 31), 2020, 'Q1'),
    _quarter_fact(_STALE_TAG, 101, date(2020, 6, 30), 2020, 'Q2'),
    _quarter_fact(_STALE_TAG, 102, date(2020, 9, 30), 2020, 'Q3'),
    _quarter_fact(_STALE_TAG, 103, date(2020, 12, 31), 2020, 'Q4'),
]
# Four current quarters under the lower-priority (current) tag.
_FRESH_QUARTERS = [
    _quarter_fact(_FRESH_TAG, 1000, date(2025, 6, 30), 2025, 'Q2'),
    _quarter_fact(_FRESH_TAG, 1001, date(2025, 9, 30), 2025, 'Q3'),
    _quarter_fact(_FRESH_TAG, 1002, date(2025, 12, 31), 2025, 'Q4'),
    _quarter_fact(_FRESH_TAG, 1003, date(2026, 3, 31), 2026, 'Q1'),
]

# Reference date well after both windows; keeps the "fresh" window (ends
# 2026-03-31) inside the staleness threshold while flagging the 2020 window.
_AS_OF = date(2026, 7, 1)


# --- Offline: the cross-concept recency core of the fix (deterministic) -------

@pytest.mark.fast
def test_ttm_picks_fresh_concept_over_stale_top_priority_tag():
    """The NVDA/GOOG scenario: a stale window under the top-priority revenue tag
    must not win over a current window under a lower-priority synonym."""
    ef = EntityFacts(cik=123456, name='Test Co', facts=_STALE_QUARTERS + _FRESH_QUARTERS)

    ttm = ef.get_ttm_revenue(as_of=_AS_OF)

    assert ttm.concept.endswith('Revenues'), "stayed on the abandoned high-priority tag"
    assert ttm.value == 1000 + 1001 + 1002 + 1003, "summed the stale window, not the fresh one"
    assert ttm.periods == [(2025, 'Q2'), (2025, 'Q3'), (2025, 'Q4'), (2026, 'Q1')]
    assert ttm.is_stale is False
    assert ttm.as_of_date == date(2026, 3, 31)


@pytest.mark.fast
def test_ttm_flags_stale_when_every_candidate_is_old():
    """When the only data available is years behind the reference date, the value
    is still returned but ``is_stale`` and a warning make the problem detectable
    programmatically (the original bug's core complaint)."""
    ef = EntityFacts(cik=123456, name='Test Co', facts=list(_STALE_QUARTERS))

    ttm = ef.get_ttm_revenue(as_of=_AS_OF)

    assert ttm.value == 100 + 101 + 102 + 103
    assert ttm.is_stale is True
    assert ttm.warning is not None and 'stale' in ttm.warning.lower()


@pytest.mark.fast
def test_ttm_single_fresh_top_priority_tag_unchanged():
    """A company using the top-priority tag with current data still resolves to
    it — no regression from the recency-selection change."""
    ef = EntityFacts(cik=123456, name='Test Co',
                     facts=[_quarter_fact(_STALE_TAG, 1000 + i, pe, fy, fp)
                            for i, (pe, fy, fp) in enumerate([
                                (date(2025, 6, 30), 2025, 'Q2'),
                                (date(2025, 9, 30), 2025, 'Q3'),
                                (date(2025, 12, 31), 2025, 'Q4'),
                                (date(2026, 3, 31), 2026, 'Q1'),
                            ])])

    ttm = ef.get_ttm_revenue(as_of=_AS_OF)

    assert ttm.concept.endswith('RevenueFromContractWithCustomerExcludingAssessedTax')
    assert ttm.is_stale is False


@pytest.mark.fast
def test_ttm_explicit_past_as_of_is_not_stale():
    """Asking for a historical ``as_of`` is a deliberate request for that point in
    time — the matching window is not 'stale' relative to what was asked for."""
    ef = EntityFacts(cik=123456, name='Test Co', facts=list(_STALE_QUARTERS))

    ttm = ef.get_ttm_revenue(as_of=date(2021, 1, 15))

    assert ttm.value == 100 + 101 + 102 + 103
    assert ttm.is_stale is False


# --- End-to-end: the reported companies under VCR ----------------------------

@pytest.mark.network
@pytest.mark.vcr
def test_nvda_ttm_revenue_not_stale_2020():
    """NVDA get_ttm_revenue() returns current revenue via ``Revenues``, not the
    $10.918B FY2020 figure summed from the abandoned Contract-with-Customer tag."""
    from edgar import Company

    ttm = Company("NVDA").get_facts().get_ttm_revenue()
    assert ttm.concept.endswith('Revenues')
    assert ttm.value != 10_918_000_000, "returned the FY2020 stale-tag sum"
    assert ttm.value > 200_000_000_000, "NVDA TTM revenue is well over $200B"
    assert ttm.is_stale is False
    # Four distinct periods — the bug summed (2020,'FY') four times.
    assert len(set(ttm.periods)) == 4


@pytest.mark.network
@pytest.mark.vcr
def test_goog_ttm_revenue_tracks_recent_window():
    """GOOG get_ttm_revenue() tracks the current window (was ~1 year behind on the
    abandoned Contract-with-Customer tag)."""
    from edgar import Company

    ttm = Company("GOOG").get_facts().get_ttm_revenue()
    assert ttm.concept.endswith('Revenues')
    assert ttm.as_of_date.year >= 2025
    assert ttm.is_stale is False


@pytest.mark.network
@pytest.mark.vcr
def test_amzn_ttm_revenue_matches_reference():
    """AMZN was already correct in the report ($742.8B); the recency fix keeps it
    correct and, notably, exceeds the reporter's manual workaround ($685.1B)."""
    from edgar import Company

    ttm = Company("AMZN").get_facts().get_ttm_revenue()
    # Reporter's independently-verified figure was ~$742.8B.
    assert abs(ttm.value - 742_776_000_000) < 1_000_000_000
    assert ttm.is_stale is False
