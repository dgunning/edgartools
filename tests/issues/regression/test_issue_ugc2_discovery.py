"""
Regression tests for ugc2 (2.1): Concept and period discovery on EntityFacts.

Verifies search_concepts() and available_periods() on Apple (CIK 320193).
"""
import pytest
from edgar.entity.entity_facts import get_company_facts
from edgar.entity.models import (
    ConceptMatch,
    ConceptSearchResults,
    PeriodEntry,
    PeriodSummary,
)


@pytest.fixture(scope="module")
def aapl_facts():
    return get_company_facts(320193)


# ---------------------------------------------------------------------------
# search_concepts
# ---------------------------------------------------------------------------

class TestSearchConcepts:

    def test_search_returns_matches_for_revenue(self, aapl_facts):
        results = aapl_facts.search_concepts("revenue")
        assert len(results) > 0
        concepts = [m.concept for m in results]
        # Apple reports revenue under this concept
        assert any("Revenue" in c for c in concepts)

    def test_search_returns_concept_match_fields(self, aapl_facts):
        results = aapl_facts.search_concepts("revenue")
        m = results[0]
        assert isinstance(m, ConceptMatch)
        assert m.fact_count > 0
        assert len(m.fiscal_years) > 0
        assert len(m.periods) > 0
        assert len(m.units) > 0

    def test_search_is_case_insensitive(self, aapl_facts):
        upper = aapl_facts.search_concepts("REVENUE")
        lower = aapl_facts.search_concepts("revenue")
        assert len(upper) == len(lower)

    def test_search_miss_returns_empty(self, aapl_facts):
        results = aapl_facts.search_concepts("xyznonexistent999")
        assert len(results) == 0
        assert not results  # bool is False

    def test_search_results_sorted_by_fact_count(self, aapl_facts):
        results = aapl_facts.search_concepts("revenue")
        counts = [m.fact_count for m in results]
        assert counts == sorted(counts, reverse=True)

    def test_search_results_to_dataframe(self, aapl_facts):
        results = aapl_facts.search_concepts("revenue")
        df = results.to_dataframe()
        assert "concept" in df.columns
        assert "label" in df.columns
        assert "fact_count" in df.columns
        assert len(df) == len(results)

    def test_search_results_iterable(self, aapl_facts):
        results = aapl_facts.search_concepts("revenue")
        items = list(results)
        assert len(items) == len(results)
        assert all(isinstance(m, ConceptMatch) for m in items)

    def test_search_results_indexable(self, aapl_facts):
        results = aapl_facts.search_concepts("revenue")
        first = results[0]
        assert isinstance(first, ConceptMatch)

    def test_search_results_has_rich_repr(self, aapl_facts):
        results = aapl_facts.search_concepts("revenue")
        text = repr(results)
        assert "revenue" in text.lower()

    def test_search_matches_label_too(self, aapl_facts):
        """Pattern matching should also check the human-readable label."""
        results = aapl_facts.search_concepts("Shares Outstanding")
        assert len(results) > 0


# ---------------------------------------------------------------------------
# available_periods
# ---------------------------------------------------------------------------

class TestAvailablePeriods:

    def test_all_periods_returns_entries(self, aapl_facts):
        periods = aapl_facts.available_periods()
        assert len(periods) > 0

    def test_period_entry_fields(self, aapl_facts):
        periods = aapl_facts.available_periods()
        e = periods[0]
        assert isinstance(e, PeriodEntry)
        assert e.fiscal_year > 2000
        assert e.fiscal_period in ("FY", "Q1", "Q2", "Q3", "Q4")
        assert e.fact_count > 0
        assert e.concept_count > 0

    def test_periods_sorted_descending(self, aapl_facts):
        periods = aapl_facts.available_periods()
        years = [e.fiscal_year for e in periods]
        # First entry should have the highest year
        assert years[0] >= years[-1]

    def test_fy_before_quarters_in_same_year(self, aapl_facts):
        """Within the same fiscal year, FY should appear before Q4, Q3, etc."""
        periods = aapl_facts.available_periods()
        # Find a year that has both FY and Q entries
        from collections import defaultdict
        by_year = defaultdict(list)
        for e in periods:
            by_year[e.fiscal_year].append(e.fiscal_period)

        for year, period_list in by_year.items():
            if "FY" in period_list and len(period_list) > 1:
                fy_idx = period_list.index("FY")
                # FY should be first in the year group
                assert fy_idx == 0, f"FY not first in year {year}: {period_list}"
                break

    def test_filtered_periods(self, aapl_facts):
        """Filter periods to a specific concept."""
        periods = aapl_facts.available_periods(
            "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
        )
        assert len(periods) > 0
        # All entries should have concept_count == 1 (single concept)
        for e in periods:
            assert e.concept_count == 1

    def test_filtered_periods_fewer_than_all(self, aapl_facts):
        all_periods = aapl_facts.available_periods()
        filtered = aapl_facts.available_periods(
            "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
        )
        assert len(filtered) < len(all_periods)

    def test_periods_to_dataframe(self, aapl_facts):
        periods = aapl_facts.available_periods()
        df = periods.to_dataframe()
        assert "period" in df.columns
        assert "fact_count" in df.columns
        assert "concept_count" in df.columns
        assert len(df) == len(periods)

    def test_periods_iterable(self, aapl_facts):
        periods = aapl_facts.available_periods()
        items = list(periods)
        assert len(items) == len(periods)
        assert all(isinstance(e, PeriodEntry) for e in items)

    def test_periods_has_rich_repr(self, aapl_facts):
        periods = aapl_facts.available_periods()
        text = repr(periods)
        assert "Period" in text or "period" in text.lower()

    def test_nonexistent_concept_returns_empty(self, aapl_facts):
        periods = aapl_facts.available_periods("xyznonexistent999")
        assert len(periods) == 0
        assert not periods
