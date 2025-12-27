"""
Tests for TTM (Trailing Twelve Months) integration with EntityFacts.

This module tests the TTM calculation methods added to the EntityFacts class,
including get_ttm(), get_ttm_revenue(), get_ttm_net_income(), and
get_ttm_operating_cash_flow().
"""

import pytest
from datetime import date
from unittest.mock import Mock, MagicMock

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact
from edgar.entity.ttm import TTMMetric


# Test Fixtures
# ==============================================================================

def create_mock_fact(
    concept: str = 'us-gaap:Revenue',
    label: str = 'Revenue',
    value: float = 100_000_000,
    fiscal_year: int = 2024,
    fiscal_period: str = 'Q1',
    period_end: date = date(2024, 3, 30),
    period_start: date = None,
    duration_days: int = 91
) -> FinancialFact:
    """Helper to create a FinancialFact for testing."""
    if period_start is None:
        # Calculate period_start as duration_days before period_end
        from datetime import timedelta
        period_start = period_end - timedelta(days=duration_days)

    return FinancialFact(
        concept=concept,
        taxonomy='us-gaap',
        label=label,
        value=value,
        numeric_value=value,
        unit='USD',
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        period_type='duration',
        period_start=period_start,
        period_end=period_end,
        filing_date=period_end,
        form_type='10-Q',
        accession='0001234567-24-000001'
    )


def create_mock_entity_facts():
    """Create a mock EntityFacts instance with query functionality."""
    facts_obj = Mock(spec=EntityFacts)
    facts_obj.name = "Test Company Inc."
    facts_obj.cik = "0001234567"

    # Create quarterly revenue facts (8 quarters)
    quarters_data = [
        (2023, 'Q1', date(2023, 3, 30), 80_000_000),
        (2023, 'Q2', date(2023, 6, 30), 85_000_000),
        (2023, 'Q3', date(2023, 9, 30), 90_000_000),
        (2023, 'Q4', date(2023, 12, 31), 95_000_000),
        (2024, 'Q1', date(2024, 3, 30), 100_000_000),
        (2024, 'Q2', date(2024, 6, 30), 105_000_000),
        (2024, 'Q3', date(2024, 9, 30), 110_000_000),
        (2024, 'Q4', date(2024, 12, 31), 115_000_000),
    ]

    revenue_facts = [
        create_mock_fact(
            concept='us-gaap:Revenue',
            label='Revenue',
            value=value,
            fiscal_year=fy,
            fiscal_period=fp,
            period_end=end_date
        )
        for fy, fp, end_date, value in quarters_data
    ]

    # Setup query mock to return facts
    mock_query = Mock()
    mock_execute = Mock(return_value=revenue_facts)
    mock_by_concept = Mock(return_value=mock_query)
    mock_query.by_concept = mock_by_concept
    mock_query.execute = mock_execute

    facts_obj.query = Mock(return_value=mock_query)

    return facts_obj, revenue_facts


# Test Classes
# ==============================================================================

class TestEntityFactsParseAsOf:
    """Tests for _parse_as_of_parameter method."""

    def test_parse_as_of_none(self):
        """Test parsing None returns None."""
        facts, _ = create_mock_entity_facts()
        # Bind the actual method to the mock
        from edgar.entity.entity_facts import EntityFacts
        result = EntityFacts._parse_as_of_parameter(facts, None)
        assert result is None

    def test_parse_as_of_date_object(self):
        """Test parsing date object returns same date."""
        facts, _ = create_mock_entity_facts()
        from edgar.entity.entity_facts import EntityFacts
        test_date = date(2024, 6, 30)
        result = EntityFacts._parse_as_of_parameter(facts, test_date)
        assert result == test_date

    def test_parse_as_of_q1_period_string(self):
        """Test parsing Q1 period string."""
        facts, _ = create_mock_entity_facts()
        from edgar.entity.entity_facts import EntityFacts
        result = EntityFacts._parse_as_of_parameter(facts, '2024-Q1')
        assert result == date(2024, 3, 31)

    def test_parse_as_of_q2_period_string(self):
        """Test parsing Q2 period string."""
        facts, _ = create_mock_entity_facts()
        from edgar.entity.entity_facts import EntityFacts
        result = EntityFacts._parse_as_of_parameter(facts, '2024-Q2')
        assert result == date(2024, 6, 30)

    def test_parse_as_of_q3_period_string(self):
        """Test parsing Q3 period string."""
        facts, _ = create_mock_entity_facts()
        from edgar.entity.entity_facts import EntityFacts
        result = EntityFacts._parse_as_of_parameter(facts, '2024-Q3')
        assert result == date(2024, 9, 30)

    def test_parse_as_of_q4_period_string(self):
        """Test parsing Q4 period string."""
        facts, _ = create_mock_entity_facts()
        from edgar.entity.entity_facts import EntityFacts
        result = EntityFacts._parse_as_of_parameter(facts, '2024-Q4')
        assert result == date(2024, 12, 31)

    def test_parse_as_of_fy_period_string(self):
        """Test parsing FY period string."""
        facts, _ = create_mock_entity_facts()
        from edgar.entity.entity_facts import EntityFacts
        result = EntityFacts._parse_as_of_parameter(facts, '2024-FY')
        assert result == date(2024, 12, 31)

    def test_parse_as_of_invalid_format(self):
        """Test parsing invalid period format raises ValueError."""
        facts, _ = create_mock_entity_facts()
        from edgar.entity.entity_facts import EntityFacts
        with pytest.raises(ValueError, match="Invalid period format"):
            EntityFacts._parse_as_of_parameter(facts, '2024')

    def test_parse_as_of_invalid_period(self):
        """Test parsing invalid period raises ValueError."""
        facts, _ = create_mock_entity_facts()
        from edgar.entity.entity_facts import EntityFacts
        with pytest.raises(ValueError, match="Invalid period"):
            EntityFacts._parse_as_of_parameter(facts, '2024-Q5')

    def test_parse_as_of_invalid_year(self):
        """Test parsing invalid year raises ValueError."""
        facts, _ = create_mock_entity_facts()
        from edgar.entity.entity_facts import EntityFacts
        with pytest.raises(ValueError, match="Invalid year"):
            EntityFacts._parse_as_of_parameter(facts, 'ABCD-Q1')


class TestEntityFactsGetTTM:
    """Tests for get_ttm method integration."""

    def test_get_ttm_basic(self):
        """Test basic TTM calculation through EntityFacts."""
        # This test would require actual EntityFacts integration
        # For now, we'll mark it as integration test
        pytest.skip("Integration test - requires actual company data")

    def test_get_ttm_with_period_string(self):
        """Test TTM calculation with period string."""
        pytest.skip("Integration test - requires actual company data")

    def test_get_ttm_concept_not_found(self):
        """Test get_ttm raises KeyError when concept not found."""
        facts, _ = create_mock_entity_facts()

        # Mock query to return empty list
        mock_query = Mock()
        mock_query.by_concept = Mock(return_value=mock_query)
        mock_query.execute = Mock(return_value=[])
        facts.query = Mock(return_value=mock_query)

        # Bind the actual method
        from edgar.entity.entity_facts import EntityFacts

        with pytest.raises(KeyError, match="Concept .* not found"):
            EntityFacts.get_ttm(facts, 'NonExistentConcept')


class TestEntityFactsConvenienceMethods:
    """Tests for TTM convenience methods (get_ttm_revenue, etc.)."""

    def test_get_ttm_revenue(self):
        """Test get_ttm_revenue convenience method."""
        pytest.skip("Integration test - requires actual company data")

    def test_get_ttm_net_income(self):
        """Test get_ttm_net_income convenience method."""
        pytest.skip("Integration test - requires actual company data")

    def test_get_ttm_operating_cash_flow(self):
        """Test get_ttm_operating_cash_flow convenience method."""
        pytest.skip("Integration test - requires actual company data")


# Integration Tests (require network access)
# ==============================================================================

@pytest.mark.network
class TestEntityFactsTTMIntegration:
    """Integration tests with real company data."""

    def test_apple_ttm_revenue(self):
        """Test TTM revenue calculation for Apple."""
        from edgar import Company

        aapl = Company("AAPL")
        facts = aapl.get_facts()

        # Get TTM revenue
        ttm = facts.get_ttm_revenue()

        # Verify result structure
        assert isinstance(ttm, TTMMetric)
        assert ttm.value > 0
        assert len(ttm.periods) == 4
        assert ttm.concept in ['us-gaap:Revenue', 'us-gaap:Revenues',
                               'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax']
        assert ttm.label == 'Revenue'

        # Verify periods are consecutive quarters
        for i in range(len(ttm.periods) - 1):
            fy1, fp1 = ttm.periods[i]
            fy2, fp2 = ttm.periods[i + 1]

            # Check that periods advance by 1 quarter
            if fp1 == 'Q4':
                assert fy2 == fy1 + 1 and fp2 == 'Q1'
            else:
                quarter_map = {'Q1': 'Q2', 'Q2': 'Q3', 'Q3': 'Q4'}
                assert fy2 == fy1 and fp2 == quarter_map[fp1]

    def test_apple_ttm_net_income(self):
        """Test TTM net income calculation for Apple."""
        from edgar import Company

        aapl = Company("AAPL")
        facts = aapl.get_facts()

        ttm = facts.get_ttm_net_income()

        assert isinstance(ttm, TTMMetric)
        assert ttm.value > 0
        assert len(ttm.periods) == 4

    def test_apple_ttm_as_of_period(self):
        """Test TTM calculation as of specific period."""
        from edgar import Company

        aapl = Company("AAPL")
        facts = aapl.get_facts()

        # Get TTM as of Q2 2024
        ttm = facts.get_ttm_revenue(as_of='2024-Q2')

        # Should include Q3 2023 through Q2 2024
        assert len(ttm.periods) == 4
        assert ttm.periods[-1] == (2024, 'Q2')  # Most recent period

    def test_apple_ttm_as_of_date(self):
        """Test TTM calculation as of specific date."""
        from edgar import Company

        aapl = Company("AAPL")
        facts = aapl.get_facts()

        # Get TTM as of June 30, 2024
        ttm = facts.get_ttm_revenue(as_of=date(2024, 6, 30))

        assert len(ttm.periods) == 4
        assert ttm.as_of_date <= date(2024, 6, 30)

    def test_multiple_companies_ttm(self):
        """Test TTM calculation across different companies."""
        from edgar import Company

        companies = ['AAPL', 'MSFT', 'GOOGL']

        for ticker in companies:
            company = Company(ticker)
            facts = company.get_facts()

            ttm = facts.get_ttm_revenue()

            assert isinstance(ttm, TTMMetric)
            assert ttm.value > 0
            assert len(ttm.periods) == 4
            assert ttm.company_name == facts.name or ttm.label == 'Revenue'
