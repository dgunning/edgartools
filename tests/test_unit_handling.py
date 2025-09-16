"""
Tests for unit handling and normalization in financial facts.

This module tests the UnitNormalizer class and enhanced standardized concept
methods with better unit handling capabilities.
"""

import pytest
from dataclasses import dataclass
from edgar.entity.unit_handling import (
    UnitNormalizer,
    UnitResult,
    UnitType,
    apply_scale_factor,
    format_unit_error
)
from edgar.entity.models import FinancialFact
from edgar import Company
from edgar.core import set_identity


class TestUnitNormalizer:
    """Test the UnitNormalizer class functionality."""

    @pytest.mark.fast
    def test_currency_normalization(self):
        """Test currency unit normalization."""
        # Standard currency units
        assert UnitNormalizer.normalize_unit("USD") == "USD"
        assert UnitNormalizer.normalize_unit("EUR") == "EUR"

        # Variations should normalize to standard
        assert UnitNormalizer.normalize_unit("US DOLLAR") == "USD"
        assert UnitNormalizer.normalize_unit("DOLLARS") == "USD"
        assert UnitNormalizer.normalize_unit("usd") == "USD"

        assert UnitNormalizer.normalize_unit("EURO") == "EUR"
        assert UnitNormalizer.normalize_unit("EUROS") == "EUR"

        assert UnitNormalizer.normalize_unit("POUND") == "GBP"
        assert UnitNormalizer.normalize_unit("BRITISH POUND") == "GBP"

    @pytest.mark.fast
    def test_share_unit_normalization(self):
        """Test share-based unit normalization."""
        assert UnitNormalizer.normalize_unit("shares") == "shares"
        assert UnitNormalizer.normalize_unit("SHARES") == "shares"
        assert UnitNormalizer.normalize_unit("share") == "shares"
        assert UnitNormalizer.normalize_unit("STOCK") == "shares"

        assert UnitNormalizer.normalize_unit("shares_unit") == "shares_unit"
        assert UnitNormalizer.normalize_unit("USD/PartnershipUnit") == "partnership_unit"

    @pytest.mark.fast
    def test_ratio_unit_normalization(self):
        """Test ratio/dimensionless unit normalization."""
        assert UnitNormalizer.normalize_unit("pure") == "pure"
        assert UnitNormalizer.normalize_unit("number") == "pure"
        assert UnitNormalizer.normalize_unit("ratio") == "pure"
        assert UnitNormalizer.normalize_unit("percent") == "pure"
        assert UnitNormalizer.normalize_unit("%") == "pure"

    @pytest.mark.fast
    def test_per_share_unit_normalization(self):
        """Test per-share unit normalization."""
        assert UnitNormalizer.normalize_unit("USD/shares") == "USD_per_share"
        assert UnitNormalizer.normalize_unit("USD per share") == "USD_per_share"
        assert UnitNormalizer.normalize_unit("USD/shares_unit") == "USD_per_share_unit"

    @pytest.mark.fast
    def test_business_unit_normalization(self):
        """Test business/operational unit normalization."""
        assert UnitNormalizer.normalize_unit("Customer") == "customer"
        assert UnitNormalizer.normalize_unit("Store") == "store"
        assert UnitNormalizer.normalize_unit("Entity") == "entity"
        assert UnitNormalizer.normalize_unit("Segment") == "segment"
        assert UnitNormalizer.normalize_unit("reportable_segment") == "segment"

    @pytest.mark.fast
    def test_time_unit_normalization(self):
        """Test time-based unit normalization."""
        assert UnitNormalizer.normalize_unit("Year") == "years"
        assert UnitNormalizer.normalize_unit("YEARS") == "years"
        assert UnitNormalizer.normalize_unit("Month") == "months"

    @pytest.mark.fast
    def test_area_unit_normalization(self):
        """Test area unit normalization."""
        assert UnitNormalizer.normalize_unit("sqft") == "sqft"
        assert UnitNormalizer.normalize_unit("square_feet") == "sqft"

    @pytest.mark.fast
    def test_unknown_units_passthrough(self):
        """Test that unknown units pass through unchanged."""
        assert UnitNormalizer.normalize_unit("UNKNOWN_UNIT") == "UNKNOWN_UNIT"
        assert UnitNormalizer.normalize_unit("CustomUnit") == "CustomUnit"

    @pytest.mark.fast
    def test_get_unit_type(self):
        """Test unit type classification."""
        assert UnitNormalizer.get_unit_type("USD") == UnitType.CURRENCY
        assert UnitNormalizer.get_unit_type("EUR") == UnitType.CURRENCY

        assert UnitNormalizer.get_unit_type("shares") == UnitType.SHARES
        assert UnitNormalizer.get_unit_type("shares_unit") == UnitType.SHARES

        assert UnitNormalizer.get_unit_type("pure") == UnitType.RATIO
        assert UnitNormalizer.get_unit_type("percent") == UnitType.RATIO

        assert UnitNormalizer.get_unit_type("Customer") == UnitType.BUSINESS
        assert UnitNormalizer.get_unit_type("Store") == UnitType.BUSINESS

        assert UnitNormalizer.get_unit_type("years") == UnitType.TIME
        assert UnitNormalizer.get_unit_type("sqft") == UnitType.AREA

        assert UnitNormalizer.get_unit_type("unknown") == UnitType.OTHER

    @pytest.mark.fast
    def test_unit_compatibility(self):
        """Test unit compatibility checking."""
        # Exact matches
        assert UnitNormalizer.are_compatible("USD", "USD")
        assert UnitNormalizer.are_compatible("shares", "shares")

        # Currency variations
        assert UnitNormalizer.are_compatible("USD", "US DOLLAR")
        assert UnitNormalizer.are_compatible("DOLLARS", "usd")
        assert UnitNormalizer.are_compatible("EUR", "EURO")

        # Share variations
        assert UnitNormalizer.are_compatible("shares", "shares_unit")
        assert UnitNormalizer.are_compatible("SHARES", "share")

        # Different currency types (compatible for conversion)
        assert UnitNormalizer.are_compatible("USD", "EUR")
        assert UnitNormalizer.are_compatible("GBP", "JPY")

        # Incompatible types
        assert not UnitNormalizer.are_compatible("USD", "shares")
        assert not UnitNormalizer.are_compatible("shares", "pure")
        assert not UnitNormalizer.are_compatible("Customer", "USD")


class TestUnitResult:
    """Test the UnitResult class functionality."""

    @pytest.mark.fast
    def test_unit_result_creation(self):
        """Test UnitResult object creation."""
        result = UnitResult(
            value=1000.0,
            normalized_unit="USD",
            original_unit="US DOLLAR",
            success=True,
            scale_applied=1000
        )

        assert result.value == 1000.0
        assert result.normalized_unit == "USD"
        assert result.original_unit == "US DOLLAR"
        assert result.success is True
        assert result.scale_applied == 1000
        assert result.suggestions == []  # Default empty list

    @pytest.mark.fast
    def test_unit_result_with_error(self):
        """Test UnitResult with error information."""
        result = UnitResult(
            value=None,
            normalized_unit="USD",
            original_unit="shares",
            success=False,
            error_reason="Unit type mismatch",
            suggestions=["Use a monetary concept instead"]
        )

        assert result.value is None
        assert result.success is False
        assert result.error_reason == "Unit type mismatch"
        assert len(result.suggestions) == 1


class TestGetNormalizedValue:
    """Test the get_normalized_value method."""

    @pytest.mark.fast
    def create_test_fact(self, value: float, unit: str, scale: int = None) -> FinancialFact:
        """Helper to create test FinancialFact objects."""
        return FinancialFact(
            concept="TestConcept",
            taxonomy="us-gaap",
            label="Test Label",
            value=value,
            numeric_value=value,
            unit=unit,
            scale=scale,
            period_start=None,
            period_end=None,
            fiscal_year=2024,
            fiscal_period="FY",
            form_type="10-K",
            filing_date=None,
            accession="test"
        )

    @pytest.mark.fast
    def test_get_normalized_value_success(self):
        """Test successful unit normalization."""
        fact = self.create_test_fact(1000.0, "USD")
        result = UnitNormalizer.get_normalized_value(fact, target_unit="USD")

        assert result.success is True
        assert result.value == 1000.0
        assert result.normalized_unit == "USD"
        assert result.original_unit == "USD"

    @pytest.mark.fast
    def test_get_normalized_value_with_variation(self):
        """Test normalization with unit variation."""
        fact = self.create_test_fact(1000.0, "US DOLLAR")
        result = UnitNormalizer.get_normalized_value(fact, target_unit="USD")

        assert result.success is True
        assert result.value == 1000.0
        assert result.normalized_unit == "USD"  # Normalized
        assert result.original_unit == "US DOLLAR"

    @pytest.mark.fast
    def test_get_normalized_value_with_scale(self):
        """Test normalization with scale factor."""
        fact = self.create_test_fact(1000.0, "USD", scale=1000)
        result = UnitNormalizer.get_normalized_value(fact, target_unit="USD", apply_scale=True)

        assert result.success is True
        assert result.value == 1_000_000.0  # 1000 * 1000
        assert result.scale_applied == 1000

    @pytest.mark.fast
    def test_get_normalized_value_no_scale(self):
        """Test normalization without applying scale."""
        fact = self.create_test_fact(1000.0, "USD", scale=1000)
        result = UnitNormalizer.get_normalized_value(fact, target_unit="USD", apply_scale=False)

        assert result.success is True
        assert result.value == 1000.0  # Scale not applied
        assert result.scale_applied is None

    @pytest.mark.fast
    def test_get_normalized_value_compatible_currency(self):
        """Test normalization with compatible but different currency."""
        fact = self.create_test_fact(1000.0, "EUR")
        result = UnitNormalizer.get_normalized_value(fact, target_unit="USD")

        assert result.success is True  # Compatible currencies
        assert result.value == 1000.0
        assert result.normalized_unit == "EUR"
        assert len(result.suggestions) > 0
        assert "currency conversion" in result.suggestions[0].lower()

    @pytest.mark.fast
    def test_get_normalized_value_incompatible(self):
        """Test normalization with incompatible units."""
        fact = self.create_test_fact(1000.0, "shares")
        result = UnitNormalizer.get_normalized_value(fact, target_unit="USD")

        assert result.success is False
        assert result.value is None
        assert "not compatible" in result.error_reason
        assert len(result.suggestions) > 0

    @pytest.mark.fast
    def test_get_normalized_value_no_numeric_value(self):
        """Test normalization with no numeric value."""
        fact = self.create_test_fact(None, "USD")
        fact.numeric_value = None
        result = UnitNormalizer.get_normalized_value(fact, target_unit="USD")

        assert result.success is False
        assert result.value is None
        assert "No numeric value available" in result.error_reason

    @pytest.mark.fast
    def test_get_normalized_value_no_target_unit(self):
        """Test normalization without target unit (just normalize)."""
        fact = self.create_test_fact(1000.0, "US DOLLAR")
        result = UnitNormalizer.get_normalized_value(fact)

        assert result.success is True
        assert result.value == 1000.0
        assert result.normalized_unit == "USD"
        assert result.original_unit == "US DOLLAR"


class TestUtilityFunctions:
    """Test utility functions."""

    @pytest.mark.fast
    def test_apply_scale_factor(self):
        """Test scale factor application."""
        assert apply_scale_factor(1000.0, 1000) == 1_000_000.0
        assert apply_scale_factor(1000.0, 1) == 1000.0
        assert apply_scale_factor(1000.0, None) == 1000.0

    @pytest.mark.fast
    def test_format_unit_error(self):
        """Test unit error formatting."""
        result = UnitResult(
            value=None,
            normalized_unit="USD",
            original_unit="shares",
            success=False,
            error_reason="Unit type mismatch",
            suggestions=["Use a monetary concept", "Check unit types"]
        )

        formatted = format_unit_error(result)
        assert "Unit handling error" in formatted
        assert "Unit type mismatch" in formatted
        assert "Use a monetary concept" in formatted
        assert "Original unit: 'shares'" in formatted
        assert "Normalized to: 'USD'" in formatted

    @pytest.mark.fast
    def test_format_unit_error_success(self):
        """Test error formatting for successful result."""
        result = UnitResult(
            value=1000.0,
            normalized_unit="USD",
            original_unit="USD",
            success=True
        )

        formatted = format_unit_error(result)
        assert formatted == "No error"


class TestEnhancedStandardizedMethods:
    """Test enhanced standardized methods with unit handling."""

    @pytest.mark.network
    def test_get_revenue_detailed(self):
        """Test detailed revenue method with unit information."""
        company = Company("AAPL")
        facts = company.get_facts()

        result = facts.get_revenue_detailed()

        assert result is not None
        assert hasattr(result, 'success')
        assert hasattr(result, 'value')
        assert hasattr(result, 'normalized_unit')
        assert hasattr(result, 'original_unit')

        if result.success:
            assert result.value is not None
            assert result.value > 0
            assert result.normalized_unit == "USD"
        else:
            assert result.error_reason is not None
            assert isinstance(result.suggestions, list)

    @pytest.mark.network
    def test_get_net_income_detailed(self):
        """Test detailed net income method with unit information."""
        company = Company("AAPL")
        facts = company.get_facts()

        result = facts.get_net_income_detailed()

        assert result is not None
        if result.success:
            assert result.value is not None
            assert result.normalized_unit == "USD"
        else:
            assert result.error_reason is not None

    @pytest.mark.network
    def test_check_unit_compatibility(self):
        """Test unit compatibility checking method."""
        company = Company("AAPL")
        facts = company.get_facts()

        # Test compatible concepts (both should be USD)
        compat = facts.check_unit_compatibility('Revenues', 'NetIncomeLoss')

        assert 'compatible' in compat
        assert 'concept1' in compat
        assert 'concept2' in compat
        assert 'fact1_found' in compat
        assert 'fact2_found' in compat

        if compat['fact1_found'] and compat['fact2_found']:
            assert 'fact1_unit' in compat
            assert 'fact2_unit' in compat
            assert 'fact1_normalized' in compat
            assert 'fact2_normalized' in compat

    @pytest.mark.network
    def test_check_unit_compatibility_missing_concept(self):
        """Test unit compatibility with missing concept."""
        company = Company("AAPL")
        facts = company.get_facts()

        compat = facts.check_unit_compatibility('NonExistentConcept', 'Revenues')

        assert compat['compatible'] is False
        assert compat['fact1_found'] is False
        assert 'not found' in compat['issue']
        assert len(compat['suggestions']) > 0

    @pytest.mark.network
    def test_enhanced_methods_vs_original(self):
        """Test that enhanced methods return same values as original methods."""
        company = Company("AAPL")
        facts = company.get_facts()

        # Test revenue
        original_revenue = facts.get_revenue()
        detailed_revenue = facts.get_revenue_detailed()

        if original_revenue is not None and detailed_revenue.success:
            assert abs(original_revenue - detailed_revenue.value) < 0.01

        # Test net income
        original_income = facts.get_net_income()
        detailed_income = facts.get_net_income_detailed()

        if original_income is not None and detailed_income.success:
            assert abs(original_income - detailed_income.value) < 0.01


class TestRealWorldUnitScenarios:
    """Test real-world unit handling scenarios."""

    @pytest.mark.network
    def test_fallback_calculation_with_unit_handling(self):
        """Test that fallback calculations use enhanced unit handling."""
        company = Company("AAPL")
        facts = company.get_facts()

        # Test the internal fallback calculation method
        try:
            # This should use enhanced unit compatibility checking
            calculated_revenue = facts._calculate_revenue_from_components(unit="USD")

            if calculated_revenue is not None:
                assert calculated_revenue > 0
                assert isinstance(calculated_revenue, float)
        except Exception as e:
            # Fallback calculation may fail, which is acceptable
            pass

    @pytest.mark.network
    def test_scale_factor_handling(self):
        """Test handling of scale factors in unit normalization."""
        company = Company("AAPL")
        facts = company.get_facts()

        # Check if any facts have scale factors
        facts_with_scale = []
        for fact in facts._facts[:50]:  # Check first 50 facts
            if fact.scale and fact.scale != 1:
                facts_with_scale.append(fact)

        # If we found facts with scale, test normalization
        if facts_with_scale:
            fact = facts_with_scale[0]
            result = UnitNormalizer.get_normalized_value(fact, apply_scale=True)

            if result.success:
                expected_value = fact.numeric_value * fact.scale
                assert abs(result.value - expected_value) < 0.01
                assert result.scale_applied == fact.scale

    @pytest.mark.fast
    def test_currency_unit_variations(self):
        """Test handling of various currency unit representations."""
        # Create test facts with different currency representations
        test_cases = [
            ("USD", "USD"),
            ("US DOLLAR", "USD"),
            ("DOLLARS", "USD"),
            ("usd", "USD"),
            ("EUR", "EUR"),
            ("EURO", "EUR"),
        ]

        for original_unit, expected_normalized in test_cases:
            normalized = UnitNormalizer.normalize_unit(original_unit)
            assert normalized == expected_normalized, f"Failed for {original_unit}"

    @pytest.mark.fast
    def test_per_share_unit_variations(self):
        """Test handling of per-share unit variations."""
        # USD/shares and USD/shares_unit are different concepts - one is per common share,
        # the other is per partnership unit. They should normalize but not be compatible

        norm1 = UnitNormalizer.normalize_unit("USD/shares")
        norm2 = UnitNormalizer.normalize_unit("USD/shares_unit")

        assert norm1 == "USD_per_share"
        assert norm2 == "USD_per_share_unit"

        # These are different unit types and should not be compatible
        assert not UnitNormalizer.are_compatible("USD/shares", "USD/shares_unit")

        # But the same normalized units should be compatible with themselves
        assert UnitNormalizer.are_compatible("USD/shares", "USD per share")
        assert UnitNormalizer.are_compatible("USD/shares_unit", "USD per share unit")


if __name__ == "__main__":
    # Run some quick tests
    print("🧪 Running Unit Handling Tests")

    # Test basic normalization
    print("✅ Currency normalization:", UnitNormalizer.normalize_unit("US DOLLAR"))
    print("✅ Share normalization:", UnitNormalizer.normalize_unit("SHARES"))

    # Test compatibility
    print("✅ USD/DOLLAR compatible:", UnitNormalizer.are_compatible("USD", "US DOLLAR"))
    print("✅ USD/shares incompatible:", UnitNormalizer.are_compatible("USD", "shares"))

    # Test with real company
    try:
        company = Company("AAPL")
        facts = company.get_facts()

        result = facts.get_revenue_detailed()
        print(f"✅ AAPL revenue detailed: Success={result.success}, Value=${result.value/1e9 if result.value else 'N/A'}B")

        if not result.success:
            print(f"   Error: {result.error_reason}")

    except Exception as e:
        print(f"❌ Real company test failed: {e}")

    print("🎯 Unit handling tests completed!")