"""Regression tests for GH #1149 and bead edgartools-fdye.

Both are the same loop in ``_get_standardized_concept_value``, which returned on
the first concept variant with any match:

    for concept in concept_variants:
        for concept_variant in [concept, f'us-gaap:{concept}', ...]:
            fact = self.get_annual_fact(concept_variant)
            ...
            return unit_result.value

The variant list ranks *names for one figure*. Ranking by name before anything
else produced two different wrong answers:

  GH #1149 (period)   NVDA migrated off RevenueFromContractWithCustomer...,
                      which stayed top-ranked, so get_revenue() answered FY2022
                      forever while Revenues carried FY2026.
  fdye (concept)      MetLife tags the ASC-606 slice AND consolidated Revenues
                      for the SAME year; priority took the slice, a ~32x
                      understatement, and the income statement showed $2.4B of
                      revenue above $6.1B of operating income.

The fix is period first, then priority, then a magnitude cross-check that is
opt-in per concept family. General Mills is the control that rules out the naive
repairs: its correct value is the *older-ranked* concept in the *newer* period,
so "newest period wins" alone keeps it right, and its Revenues tag is a small
slice, so "largest wins" would break it if magnitude ranked first.

Ground truth (verified against each company's own income statement):
  NVDA FY2026 revenue  215,938,000,000
  MET  FY2025 revenue   77,084,000,000
  GIS  FY2026 revenue   18,424,600,000
"""
import pytest

from edgar.entity.utils import is_consolidated_total_over


class _Result:
    """Stand-in for UnitResult; only .value is read by the selector."""

    def __init__(self, value):
        self.value = value
        self.success = True


class _Fact:
    def __init__(self, period_end):
        self.period_end = period_end


def _candidate(priority, period_end, value):
    return (priority, _Fact(period_end), _Result(value))


# --- Offline: the selection rule itself --------------------------------------

class TestPeriodBeatsPriority:
    """GH #1149. A newer period outranks a better-ranked name."""

    def test_the_newest_period_wins_over_the_top_ranked_concept(self):
        from edgar.entity.entity_facts import _select_concept_candidate

        # NVDA's shape: top-ranked concept is four years stale.
        stale = _candidate(0, "2022-01-30", 26_914_000_000)
        current = _candidate(2, "2026-01-25", 215_938_000_000)

        assert _select_concept_candidate([stale, current]).value == 215_938_000_000

    def test_priority_still_decides_within_one_period(self):
        from edgar.entity.entity_facts import _select_concept_candidate

        preferred = _candidate(0, "2026-01-25", 100)
        other = _candidate(3, "2026-01-25", 110)

        # 110 is larger but not a different figure, and the cross-check is off.
        assert _select_concept_candidate([preferred, other]).value == 100

    def test_a_fact_without_a_period_cannot_outrank_one_that_has_it(self):
        from edgar.entity.entity_facts import _select_concept_candidate

        undated = _candidate(0, None, 1)
        dated = _candidate(1, "2026-01-25", 2)

        assert _select_concept_candidate([undated, dated]).value == 2


class TestConsolidatedTotalCrossCheck:
    """fdye. Within a period, a candidate that dwarfs the pick is the total."""

    def test_a_dwarfing_same_period_candidate_wins_when_enabled(self):
        from edgar.entity.entity_facts import _select_concept_candidate

        # MetLife's shape: both tagged for FY2025.
        slice_ = _candidate(0, "2025-12-31", 2_436_000_000)
        total = _candidate(2, "2025-12-31", 77_084_000_000)

        chosen = _select_concept_candidate([slice_, total],
                                           prefer_consolidated_total=True)
        assert chosen.value == 77_084_000_000

    def test_it_is_off_by_default(self):
        """Net income's variants are not slices of one another.

        ``ProfitLoss`` exceeds ``NetIncomeLoss`` by the noncontrolling interest,
        so a magnitude rule applied to every concept family would quietly change
        whose earnings are reported.
        """
        from edgar.entity.entity_facts import _select_concept_candidate

        attributable = _candidate(0, "2025-12-31", 100)
        including_nci = _candidate(1, "2025-12-31", 300)

        assert _select_concept_candidate([attributable, including_nci]).value == 100

    def test_a_near_equal_candidate_does_not_override(self):
        """Two names for one figure sit close together and must not fight."""
        from edgar.entity.entity_facts import _select_concept_candidate

        picked = _candidate(0, "2025-12-31", 100)
        gross = _candidate(1, "2025-12-31", 150)

        chosen = _select_concept_candidate([picked, gross],
                                           prefer_consolidated_total=True)
        assert chosen.value == 100

    def test_the_cross_check_never_crosses_periods(self):
        """A big number from an old year is not this year's total."""
        from edgar.entity.entity_facts import _select_concept_candidate

        current = _candidate(0, "2026-05-31", 18_424_600_000)
        old_and_large = _candidate(2, "2024-05-26", 90_000_000_000)

        chosen = _select_concept_candidate([current, old_and_large],
                                           prefer_consolidated_total=True)
        assert chosen.value == 18_424_600_000


class TestThresholdPredicate:
    def test_only_a_multiple_counts_as_a_total(self):
        assert is_consolidated_total_over(200, 100)
        assert not is_consolidated_total_over(199, 100)

    def test_negatives_are_not_compared_by_ratio(self):
        """A loss must not be 'dwarfed' by a smaller loss."""
        assert not is_consolidated_total_over(-500, -100)
        assert not is_consolidated_total_over(100, -100)

    def test_missing_values_never_override(self):
        assert not is_consolidated_total_over(None, 100)
        assert not is_consolidated_total_over(200, None)


# --- Network: the three companies, against their own filings -----------------

@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("ticker,expected", [
    ("NVDA", 215_938_000_000),   # GH #1149: was 26,914,000,000 from FY2022
    ("MET",   77_084_000_000),   # fdye: was 2,436,000,000, the ASC-606 slice
    ("GIS",   18_424_600_000),   # control: correct before and after
])
def test_get_revenue_returns_the_consolidated_total_for_the_latest_year(ticker, expected):
    from edgar import Company

    assert Company(ticker).get_facts().get_revenue() == expected


@pytest.mark.network
@pytest.mark.regression
def test_the_income_statement_agrees_with_get_revenue():
    """The second copy of the priority list must not disagree with the first.

    MetLife's statement reported $2.4B of revenue above $6.1B of operating
    income — internally impossible, and a different answer than get_revenue()
    gave for the same company and year.
    """
    from edgar import Company

    facts = Company("MET").get_facts()
    statement = facts.income_statement(annual=True, periods=1)
    df = statement.to_dataframe()

    revenue_row = df[df['label'] == 'Total Revenue']
    assert len(revenue_row) == 1
    period_column = [c for c in df.columns if c.startswith('FY ')][0]

    assert revenue_row.iloc[0][period_column] == 77_084_000_000
    assert revenue_row.index[0] == 'Revenues', (
        "the row must name the concept its value came from, not the "
        "highest-priority concept merely present in the filing"
    )
