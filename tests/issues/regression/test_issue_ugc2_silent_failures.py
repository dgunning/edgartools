"""
Regression tests for ugc2 Theme 4: Helpful warnings on silent None returns.

get_fact(), get_annual_fact(), and get_concept() now emit UserWarning with
"did you mean?" hints when they return None, instead of failing silently.
Internal callers (get_revenue, _get_standardized_concept_value, etc.) suppress
these warnings via _suppress_warnings to avoid noise during synonym resolution.
"""

import warnings
from datetime import date

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact


def _make_fact(concept: str, label: str, fiscal_year: int, fiscal_period: str,
               value: float = 1000.0) -> FinancialFact:
    """Create a minimal FinancialFact for testing."""
    return FinancialFact(
        concept=concept,
        taxonomy='us-gaap',
        label=label,
        value=value,
        numeric_value=value,
        unit='USD',
        period_end=date(fiscal_year, 12, 31),
        period_start=date(fiscal_year, 1, 1),
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        filing_date=date(fiscal_year + 1, 2, 15),
        form_type='10-K' if fiscal_period == 'FY' else '10-Q',
    )


@pytest.fixture
def entity_facts():
    """EntityFacts with a small set of known concepts."""
    facts = [
        _make_fact('us-gaap:Revenues', 'Revenues', 2023, 'FY', 50000.0),
        _make_fact('us-gaap:Revenues', 'Revenues', 2022, 'FY', 45000.0),
        _make_fact('us-gaap:Revenues', 'Revenues', 2023, 'Q1', 12000.0),
        _make_fact('us-gaap:Revenues', 'Revenues', 2023, 'Q2', 13000.0),
        _make_fact('us-gaap:NetIncomeLoss', 'Net Income (Loss)', 2023, 'FY', 10000.0),
        _make_fact('us-gaap:Assets', 'Assets', 2023, 'FY', 200000.0),
    ]
    return EntityFacts(cik=320193, name='Test Company', facts=facts)


# --- get_fact() warnings ---

@pytest.mark.fast
class TestGetFactWarnings:

    def test_bad_concept_warns_with_suggestions(self, entity_facts):
        """get_fact() with a nonexistent concept emits a warning with similar concepts."""
        with pytest.warns(UserWarning, match="No fact found for concept 'Revenue'"):
            result = entity_facts.get_fact('Revenue')
        assert result is None

    def test_bad_concept_warning_includes_search_tip(self, entity_facts):
        """Warning includes tip to use search_concepts()."""
        with pytest.warns(UserWarning, match="search_concepts"):
            entity_facts.get_fact('Revenue')

    def test_bad_concept_suggests_similar(self, entity_facts):
        """Warning suggests similar concept names."""
        with pytest.warns(UserWarning, match="us-gaap:Revenues"):
            entity_facts.get_fact('Revenue')

    def test_good_concept_no_warning(self, entity_facts):
        """get_fact() with a valid concept returns data and emits no warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = entity_facts.get_fact('us-gaap:Revenues')
        assert result is not None
        assert result.numeric_value == 50000.0
        user_warnings = [x for x in w if issubclass(x.category, UserWarning)
                         and "No fact found" in str(x.message)]
        assert len(user_warnings) == 0

    def test_good_concept_bad_period_warns(self, entity_facts):
        """get_fact() with valid concept but non-matching period warns with available periods."""
        with pytest.warns(UserWarning, match="no facts match period '2030-FY'"):
            result = entity_facts.get_fact('us-gaap:Revenues', period='2030-FY')
        assert result is None

    def test_bad_period_warning_includes_available(self, entity_facts):
        """Period mismatch warning lists recent periods."""
        with pytest.warns(UserWarning, match="Recent periods"):
            entity_facts.get_fact('us-gaap:Revenues', period='2030-FY')

    def test_bad_period_warning_includes_tip(self, entity_facts):
        """Period mismatch warning includes available_periods() tip."""
        with pytest.warns(UserWarning, match="available_periods"):
            entity_facts.get_fact('us-gaap:Revenues', period='2030-FY')

    def test_good_concept_good_period_no_warning(self, entity_facts):
        """get_fact() with valid concept and matching period emits no warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = entity_facts.get_fact('us-gaap:Revenues', period='2023-FY')
        assert result is not None
        assert result.numeric_value == 50000.0
        user_warnings = [x for x in w if issubclass(x.category, UserWarning)
                         and "fact" in str(x.message).lower()]
        assert len(user_warnings) == 0


# --- get_annual_fact() warnings ---

@pytest.mark.fast
class TestGetAnnualFactWarnings:

    def test_bad_concept_warns(self, entity_facts):
        """get_annual_fact() with bad concept emits warning with suggestions."""
        with pytest.warns(UserWarning, match="No fact found for concept"):
            result = entity_facts.get_annual_fact('NonexistentConcept')
        assert result is None

    def test_no_fy_data_warns(self, entity_facts):
        """get_annual_fact() warns when concept exists but has no FY data."""
        # Create facts with only quarterly data
        q_facts = [
            _make_fact('us-gaap:SpecialItem', 'Special Item', 2023, 'Q1', 100.0),
            _make_fact('us-gaap:SpecialItem', 'Special Item', 2023, 'Q2', 200.0),
        ]
        ef = EntityFacts(cik=1, name='Test', facts=q_facts)
        with pytest.warns(UserWarning, match="has no annual \\(FY\\) data"):
            result = ef.get_annual_fact('us-gaap:SpecialItem')
        assert result is None

    def test_no_fy_data_warns_with_period_types(self, entity_facts):
        """Warning about missing FY data shows available period types."""
        q_facts = [
            _make_fact('us-gaap:SpecialItem', 'Special Item', 2023, 'Q1', 100.0),
        ]
        ef = EntityFacts(cik=1, name='Test', facts=q_facts)
        with pytest.warns(UserWarning, match="Available period types"):
            ef.get_annual_fact('us-gaap:SpecialItem')

    def test_bad_fiscal_year_warns(self, entity_facts):
        """get_annual_fact() warns when concept has FY data but not for requested year."""
        with pytest.warns(UserWarning, match="not for fiscal year 2030"):
            result = entity_facts.get_annual_fact('us-gaap:Revenues', fiscal_year=2030)
        assert result is None

    def test_bad_fiscal_year_shows_available(self, entity_facts):
        """Warning about wrong fiscal year shows available years."""
        with pytest.warns(UserWarning, match="Available fiscal years"):
            entity_facts.get_annual_fact('us-gaap:Revenues', fiscal_year=2030)

    def test_good_annual_fact_no_warning(self, entity_facts):
        """get_annual_fact() with valid concept and year emits no warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = entity_facts.get_annual_fact('us-gaap:Revenues', fiscal_year=2023)
        assert result is not None
        assert result.numeric_value == 50000.0
        user_warnings = [x for x in w if issubclass(x.category, UserWarning)
                         and "fact" in str(x.message).lower()]
        assert len(user_warnings) == 0


# --- get_concept() warnings ---

@pytest.mark.fast
class TestGetConceptWarnings:

    def test_unknown_concept_warns(self, entity_facts):
        """get_concept() with unknown concept name emits upgraded warning."""
        with pytest.warns(UserWarning, match="Unknown concept 'nonexistent_concept'"):
            result = entity_facts.get_concept('nonexistent_concept')
        assert result is None

    def test_unknown_concept_warning_includes_tips(self, entity_facts):
        """Warning includes list_supported_concepts() and search_concepts() tips."""
        with pytest.warns(UserWarning, match="list_supported_concepts"):
            entity_facts.get_concept('nonexistent_concept')

    def test_valid_concept_no_spurious_warnings(self, entity_facts):
        """get_concept() with a valid concept that resolves doesn't emit get_fact warnings."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # 'revenue' is a valid synonym group concept
            entity_facts.get_concept('revenue')
        # Filter to only our warnings (not deprecation etc.)
        our_warnings = [x for x in w if issubclass(x.category, UserWarning)
                        and "No fact found" in str(x.message)]
        assert len(our_warnings) == 0, f"Spurious warnings: {[str(x.message) for x in our_warnings]}"


# --- Suppression: get_revenue() etc. should not emit warnings ---

@pytest.mark.fast
class TestWarningSuppressionInInternalCallers:

    def test_get_revenue_no_spurious_warnings(self, entity_facts):
        """get_revenue() calls get_fact() internally but should not emit warnings."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            entity_facts.get_revenue()
        our_warnings = [x for x in w if issubclass(x.category, UserWarning)
                        and "No fact found" in str(x.message)]
        assert len(our_warnings) == 0, f"Spurious warnings: {[str(x.message) for x in our_warnings]}"

    def test_discover_concept_tags_no_spurious_warnings(self, entity_facts):
        """discover_concept_tags() calls get_fact() internally but should not emit warnings."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            entity_facts.discover_concept_tags('revenue')
        our_warnings = [x for x in w if issubclass(x.category, UserWarning)
                        and "No fact found" in str(x.message)]
        assert len(our_warnings) == 0, f"Spurious warnings: {[str(x.message) for x in our_warnings]}"


# --- _suggest_concepts() helper ---

@pytest.mark.fast
class TestSuggestConcepts:

    def test_suggests_similar_concepts(self, entity_facts):
        """_suggest_concepts returns close matches from the fact index."""
        suggestions = entity_facts._suggest_concepts('Revenue')
        assert len(suggestions) > 0
        assert any('Revenues' in s for s in suggestions)

    def test_no_suggestions_for_garbage(self, entity_facts):
        """_suggest_concepts returns empty list for totally unrelated input."""
        suggestions = entity_facts._suggest_concepts('zzzzzzzzzzz')
        assert suggestions == []
