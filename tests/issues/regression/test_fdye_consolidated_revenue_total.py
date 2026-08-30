"""Regression test for bead edgartools-fdye, on top of the #1149 fix in #1151.

#1151 made the standardized getters rank candidates by recency, which settles
*which year* to answer from. It cannot settle which of two concepts tagged for
that same year is the consolidated total: among same-recency candidates the
variant list decides, and that list is an order over NAMES, not over what those
names measure.

Insurers and banks report ASC-606 contract revenue beside a much larger
consolidated `Revenues` for the same period, and the contract tag is ranked
first. MetLife tags both for FY2025:

    RevenueFromContractWithCustomerExcludingAssessedTax   2,436,000,000
    Revenues                                            77,084,000,000

so `get_revenue()` returned the slice — a ~32x understatement — and the income
statement showed $2.4B of revenue above $6.1B of operating income, an
arithmetically impossible statement that also disagreed with `get_revenue()`
for the same company and year.

A same-period candidate that dwarfs the ranked pick is now treated as the total
the pick is a slice of. Magnitude is a cross-check on the ranked pick, never the
ranking itself: taking the largest outright would prefer `IncludingAssessedTax`
over `Excluding`, and gross over net.

General Mills is the control that rules out the naive repairs. Its correct value
is the *lower-ranked* concept in the *newer* period, and its `Revenues` tag is a
small slice of a different year — so neither "newest wins" nor "largest wins"
would be safe on its own.

Ground truth, from each company's own filing:
  MET FY2025 revenue  77,084,000,000
  GIS FY2026 revenue  18,424,600,000
"""
import pytest


class _Fact:
    def __init__(self, value, period_end):
        self.numeric_value = value
        self.period_end = period_end


# --- Offline: the rule -------------------------------------------------------

class TestConsolidatedTotalSelection:
    def test_a_dwarfing_same_period_candidate_wins(self):
        from edgar.entity.entity_facts import _consolidated_total_fact

        slice_ = _Fact(2_436_000_000, "2025-12-31")     # ASC-606
        total = _Fact(77_084_000_000, "2025-12-31")     # consolidated

        assert _consolidated_total_fact(slice_, [slice_, total]) is total

    def test_a_near_equal_candidate_does_not_override(self):
        """Two names for one figure sit close together and must not fight."""
        from edgar.entity.entity_facts import _consolidated_total_fact

        picked = _Fact(100, "2025-12-31")
        gross = _Fact(150, "2025-12-31")

        assert _consolidated_total_fact(picked, [picked, gross]) is picked

    def test_it_never_crosses_periods(self):
        """A big number from an older year is not this year's total."""
        from edgar.entity.entity_facts import _consolidated_total_fact

        current = _Fact(18_424_600_000, "2026-05-31")
        old_and_large = _Fact(90_000_000_000, "2024-05-26")

        assert _consolidated_total_fact(current, [current, old_and_large]) is current

    def test_a_fact_without_a_value_is_left_alone(self):
        from edgar.entity.entity_facts import _consolidated_total_fact

        chosen = _Fact(None, "2025-12-31")
        assert _consolidated_total_fact(chosen, [chosen]) is chosen


class TestThreshold:
    """The shared predicate. Imported inside each test so the behavioural tests
    below still run against pre-fix code instead of erroring at collection."""

    def test_only_a_multiple_counts_as_a_total(self):
        from edgar.entity.utils import is_consolidated_total_over

        assert is_consolidated_total_over(200, 100)
        assert not is_consolidated_total_over(199, 100)

    def test_negatives_are_not_compared_by_ratio(self):
        """A loss must not be 'dwarfed' by a smaller loss."""
        from edgar.entity.utils import is_consolidated_total_over

        assert not is_consolidated_total_over(-500, -100)
        assert not is_consolidated_total_over(100, -100)

    def test_missing_values_never_override(self):
        from edgar.entity.utils import is_consolidated_total_over

        assert not is_consolidated_total_over(None, 100)
        assert not is_consolidated_total_over(200, None)


def test_the_cross_check_is_off_for_other_concept_families():
    """Net income's variants are not slices of one another.

    `ProfitLoss` exceeds `NetIncomeLoss` by the noncontrolling interest, so a
    magnitude rule applied everywhere would quietly change whose earnings are
    reported.
    """
    import inspect

    from edgar.entity.entity_facts import EntityFacts

    for getter in ('get_net_income', 'get_total_assets', 'get_total_liabilities'):
        source = inspect.getsource(getattr(EntityFacts, getter))
        assert 'prefer_consolidated_total' not in source, (
            f"{getter} opted into the revenue-only magnitude cross-check"
        )
    assert 'prefer_consolidated_total=True' in inspect.getsource(EntityFacts.get_revenue)


# --- Network: the companies --------------------------------------------------

@pytest.mark.network
@pytest.mark.regression
@pytest.mark.parametrize("ticker,expected", [
    ("MET", 77_084_000_000),   # was 2,436,000,000, the ASC-606 slice
    ("GIS", 18_424_600_000),   # control: correct before and after
])
def test_get_revenue_returns_the_consolidated_total(ticker, expected):
    from edgar import Company

    assert Company(ticker).get_facts().get_revenue() == expected


@pytest.mark.network
@pytest.mark.regression
def test_the_income_statement_agrees_with_get_revenue():
    """The second copy of the priority list must not disagree with the first."""
    from edgar import Company

    facts = Company("MET").get_facts()
    df = facts.income_statement(annual=True, periods=1).to_dataframe()

    revenue_row = df[df['label'] == 'Total Revenue']
    assert len(revenue_row) == 1
    period_column = [c for c in df.columns if c.startswith('FY ')][0]

    assert revenue_row.iloc[0][period_column] == 77_084_000_000
    assert revenue_row.index[0] == 'Revenues', (
        "the row must name the concept its value came from, not the "
        "highest-priority concept merely present in the filing"
    )
