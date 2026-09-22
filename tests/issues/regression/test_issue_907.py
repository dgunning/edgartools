"""
Regression test for Issue #907.

``TTMCalculator.quarterize()`` returned only Q1 facts for GOOGL's
``us-gaap:NetCashProvidedByUsedInInvestingActivities`` — 12 quarters out of the
~48 the data supports — even though every YTD and FY input was present and
correctly bucketed. Q1 is the one quarter that needs no subtraction
(YTD_Q1 == Q1), so *every derived quarter* was being dropped.

Root cause: ``_is_positive_concept`` substring-matched ``'cash'`` from its
must-be-positive keyword list. "NetCashProvidedByUsedInInvestingActivities"
contains "cash", and no negative-OK keyword matched it, so the concept was
classified as one that can never be negative. The four derivation guards
(Q2/Q3/Q4) then silently skipped any negative result — and investing and
financing cash flows are negative in most periods.

The keyword protected nothing real: the cash *balance* concepts it appeared to
target (CashAndCashEquivalentsAtCarryingValue and friends) are ``instant``
facts, which ``_is_additive_concept`` rejects before this guard is reachable.

Measured on GOOGL before the fix — yield tracked the sign of the derived value
exactly, which is what pinned the diagnosis::

    ...OperatingActivities  (always +)  102 facts -> 47 quarters   OK
    ...InvestingActivities  (always -)  102 facts -> 12 quarters   Q1 only
    ...FinancingActivities  (mostly -)  102 facts -> 15 quarters   Q1 + 3 flukes

Ground truth, GOOGL FY2024 investing cash flow (10-K, accession
0001652044-25-000014), in USD billions::

    Q1  -8.564   (reported discrete)
    Q2  -2.781   = YTD_6M  -11.345 - Q1      -8.564
    Q3 -18.011   = YTD_9M  -29.356 - YTD_6M -11.345
    Q4 -16.180   = FY      -45.536 - YTD_9M -29.356
                  ------
    sum -45.536  == the reported FY figure

GitHub Issue: https://github.com/dgunning/edgartools/issues/907
"""

from datetime import date

import pytest

from edgar import Company, set_identity
from edgar.entity.models import DataQuality, FinancialFact
from edgar.ttm.calculator import TTMCalculator

CONCEPT = "us-gaap:NetCashProvidedByUsedInInvestingActivities"

pytestmark = pytest.mark.regression


def _fact(period_start: date, period_end: date, value: float, fp: str, fy: int,
          filing_date: date, form_type: str = "10-Q") -> FinancialFact:
    """Build a duration cash-flow fact."""
    return FinancialFact(
        concept=CONCEPT,
        taxonomy="us-gaap",
        label="Net Cash Provided by (Used in) Investing Activities",
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


def _googl_fy2024_investing_facts():
    """GOOGL's real FY2024 investing cash flow, as filed: Q1 discrete then YTD."""
    return [
        # Q1 10-Q: discrete Q1.
        _fact(date(2024, 1, 1), date(2024, 3, 31), -8_564_000_000.0,
              fp="Q1", fy=2024, filing_date=date(2024, 4, 25)),
        # Q2 10-Q: six-month YTD.
        _fact(date(2024, 1, 1), date(2024, 6, 30), -11_345_000_000.0,
              fp="Q2", fy=2024, filing_date=date(2024, 7, 24)),
        # Q3 10-Q: nine-month YTD.
        _fact(date(2024, 1, 1), date(2024, 9, 30), -29_356_000_000.0,
              fp="Q3", fy=2024, filing_date=date(2024, 10, 29)),
        # 10-K: full year.
        _fact(date(2024, 1, 1), date(2024, 12, 31), -45_536_000_000.0,
              fp="FY", fy=2024, filing_date=date(2025, 2, 4), form_type="10-K"),
    ]


# --- Root cause: concept sign classification ---------------------------------

@pytest.mark.fast
def test_cash_flow_concepts_allow_negative_values():
    """Cash *flows* are signed; they must not be classified must-be-positive."""
    calc = TTMCalculator(_googl_fy2024_investing_facts())

    for concept in (
        "us-gaap:NetCashProvidedByUsedInInvestingActivities",
        "us-gaap:NetCashProvidedByUsedInFinancingActivities",
        "us-gaap:NetCashProvidedByUsedInOperatingActivities",
        "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
        "PeriodIncreaseDecreaseIncludingExchangeRateEffect",
    ):
        assert calc._is_positive_concept(concept) is False, (
            f"{concept} was classified must-be-positive; negative derived "
            f"quarters would be silently dropped (regression of #907)"
        )


@pytest.mark.fast
def test_revenue_like_concepts_still_guarded():
    """The fix must not disarm the guard for genuinely non-negative concepts."""
    calc = TTMCalculator(_googl_fy2024_investing_facts())

    assert calc._is_positive_concept("us-gaap:Revenues") is True
    assert calc._is_positive_concept("us-gaap:InventoryNet") is True
    assert calc._is_positive_concept("us-gaap:AccountsReceivableNetCurrent") is True
    # Losses stay permitted.
    assert calc._is_positive_concept("us-gaap:NetIncomeLoss") is False


@pytest.mark.fast
def test_period_movement_concepts_allow_negative_values():
    """Same defect class as #907, different concept family.

    ``IncreaseDecreaseIn*`` working-capital lines match 'receivable',
    'revenue', 'asset' or 'goodwill' in the must-be-positive list, so their
    negative quarters were dropped exactly as the cash flows were. A decrease
    in receivables is a legitimate negative, not a data-quality error.

    On GOOGL these recover 11, 4 and 7 negative quarters respectively.
    """
    calc = TTMCalculator(_googl_fy2024_investing_facts())

    for concept in (
        "us-gaap:IncreaseDecreaseInAccountsReceivable",
        "us-gaap:IncreaseDecreaseInDeferredRevenue",
        "us-gaap:IncreaseDecreaseInOtherOperatingAssets",
        "us-gaap:GoodwillOtherIncreaseDecrease",
    ):
        assert calc._is_positive_concept(concept) is False, (
            f"{concept} was classified must-be-positive; its negative "
            f"quarters would be silently dropped"
        )


@pytest.mark.fast
def test_known_substring_matching_quirk_is_unchanged():
    """Pin a pre-existing quirk this fix deliberately does not address.

    ``_is_positive_concept`` matches loose substrings against two ordered
    keyword lists, negative-OK first. So the revenue concept most filers
    actually use — RevenueFromContractWithCustomerExcludingAssessedTax —
    matches 'tax' and escapes the must-be-positive guard entirely.

    That is harmless today (it only makes the guard more permissive, which
    never drops data) but it shows the classifier is doing keyword roulette
    rather than knowing anything about concepts. Worth replacing with exact
    or prefix matching over a curated set; tracked separately from #907.
    """
    calc = TTMCalculator(_googl_fy2024_investing_facts())

    assert calc._is_positive_concept(
        "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
    ) is False


# --- Behaviour: all four quarters are derived with correct values ------------

@pytest.mark.fast
def test_negative_cash_flow_quarters_are_derived():
    """All four quarters must come back, not just the reported Q1."""
    quarterly = TTMCalculator(_googl_fy2024_investing_facts()).quarterize()

    periods = {q.fiscal_period for q in quarterly}
    assert periods == {"Q1", "Q2", "Q3", "Q4"}, (
        f"expected all four quarters, got {sorted(periods)}. Before the fix "
        f"only Q1 survived — every derived quarter was dropped as negative."
    )


@pytest.mark.fast
def test_derived_quarter_values_match_filed_figures():
    """Ground truth: each derived quarter equals the YTD difference."""
    quarterly = TTMCalculator(_googl_fy2024_investing_facts()).quarterize()
    by_period = {q.fiscal_period: q for q in quarterly}

    assert by_period["Q1"].numeric_value == -8_564_000_000.0
    assert by_period["Q2"].numeric_value == -2_781_000_000.0
    assert by_period["Q3"].numeric_value == -18_011_000_000.0
    assert by_period["Q4"].numeric_value == -16_180_000_000.0

    # Derivation provenance is recorded.
    assert "derived_q2_ytd6_minus_q1" in (by_period["Q2"].calculation_context or "")
    assert "derived_q3_ytd9_minus_ytd6" in (by_period["Q3"].calculation_context or "")
    assert "derived_q4_fy_minus_ytd9" in (by_period["Q4"].calculation_context or "")


@pytest.mark.fast
def test_derived_quarters_tile_the_fiscal_year():
    """The four quarters must be contiguous, non-overlapping, and sum to FY."""
    quarterly = TTMCalculator(_googl_fy2024_investing_facts()).quarterize()
    ordered = sorted(quarterly, key=lambda q: q.period_end)

    assert ordered[0].period_start == date(2024, 1, 1)
    assert ordered[-1].period_end == date(2024, 12, 31)
    for earlier, later in zip(ordered, ordered[1:]):
        assert (later.period_start - earlier.period_end).days == 1, (
            f"gap or overlap between {earlier.period_end} and {later.period_start}"
        )

    assert sum(q.numeric_value for q in ordered) == -45_536_000_000.0, (
        "quarterized values must reconcile to the reported FY figure"
    )


# --- Live data ---------------------------------------------------------------

@pytest.mark.network
def test_googl_investing_cash_flow_quarterizes_real_data():
    """The originally reported repro, against live SEC facts."""
    set_identity("test@example.com")

    concept_facts = (
        Company("GOOGL").get_facts()
        .query().by_concept(CONCEPT, exact=True).execute()
    )
    assert concept_facts, f"expected {CONCEPT} facts for GOOGL"

    quarterly = TTMCalculator(concept_facts).quarterize()

    # Before the fix this returned Q1 only.
    assert {q.fiscal_period for q in quarterly} == {"Q1", "Q2", "Q3", "Q4"}

    fy2024 = sorted(
        (q for q in quarterly
         if q.period_start.year == 2024 and q.period_end.year == 2024),
        key=lambda q: q.period_end,
    )
    assert len(fy2024) == 4, f"expected 4 quarters in FY2024, got {len(fy2024)}"
    assert [q.numeric_value for q in fy2024] == [
        -8_564_000_000.0,
        -2_781_000_000.0,
        -18_011_000_000.0,
        -16_180_000_000.0,
    ]
    assert sum(q.numeric_value for q in fy2024) == -45_536_000_000.0
