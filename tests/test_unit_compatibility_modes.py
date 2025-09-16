"""
Test different unit compatibility modes in the enhanced unit handling system.

This module tests the strict vs. compatible unit matching behavior to ensure
users get predictable results when requesting specific units.
"""

import pytest
from edgar import Company
from edgar.core import set_identity
from edgar.entity.unit_handling import UnitNormalizer, UnitResult

# Set identity for SEC API requests
set_identity("EdgarTools Test Suite test@edgartools.dev")


class TestUnitCompatibilityModes:
    """Test strict vs compatible unit matching behavior."""

    def test_strict_unit_matching_default(self):
        """Test that standardized methods use strict unit matching by default."""
        company = Company("AAPL")
        facts = company.get_facts()

        # USD should work (exact match or company reports in USD)
        usd_revenue = facts.get_revenue(unit="USD")
        assert usd_revenue is not None, "USD revenue should be available"

        # EUR should return None (strict matching - no currency conversion)
        eur_revenue = facts.get_revenue(unit="EUR")
        assert eur_revenue is None, "EUR revenue should return None (strict mode)"

        # Incompatible unit type should return None
        shares_revenue = facts.get_revenue(unit="shares")
        assert shares_revenue is None, "shares unit should return None for revenue"

    def test_unit_normalizer_strict_mode(self):
        """Test UnitNormalizer strict mode behavior directly."""
        from edgar.entity.models import FinancialFact
        from datetime import date

        fact = FinancialFact(
            concept="Revenue",
            taxonomy="us-gaap",
            label="Revenue",
            value=1000000,
            numeric_value=1000000.0,
            unit="USD",
            period_end=date(2023, 12, 31),
            fiscal_year=2023
        )

        # Strict mode: EUR should fail
        result_strict = UnitNormalizer.get_normalized_value(
            fact, target_unit="EUR", strict_unit_match=True
        )
        assert not result_strict.success, "Strict mode should fail for different currencies"
        assert result_strict.value is None, "Strict mode should return None value"

        # Compatible mode: EUR should succeed with suggestion
        result_compatible = UnitNormalizer.get_normalized_value(
            fact, target_unit="EUR", strict_unit_match=False
        )
        assert result_compatible.success, "Compatible mode should succeed for currencies"
        assert result_compatible.value is not None, "Compatible mode should return value"
        assert len(result_compatible.suggestions) > 0, "Should provide conversion suggestion"

    def test_per_share_unit_precision(self):
        """Test that per-share units require exact matching even in compatible mode."""
        # USD/shares and USD/shares_unit should not be compatible
        assert not UnitNormalizer.are_compatible("USD/shares", "USD/shares_unit")

        # But variations of the same concept should be
        assert UnitNormalizer.are_compatible("USD/shares", "USD per share")
        assert UnitNormalizer.are_compatible("USD/shares_unit", "USD per share unit")

    def test_unit_type_classification(self):
        """Test that unit types are correctly classified."""
        # Regular currencies
        assert UnitNormalizer.get_unit_type("USD").name == "CURRENCY"
        assert UnitNormalizer.get_unit_type("EUR").name == "CURRENCY"

        # Per-share units should also be classified as currency-like
        assert UnitNormalizer.get_unit_type("USD/shares").name == "CURRENCY"
        assert UnitNormalizer.get_unit_type("USD/shares_unit").name == "CURRENCY"

        # Share counts
        assert UnitNormalizer.get_unit_type("shares").name == "SHARES"
        assert UnitNormalizer.get_unit_type("shares_unit").name == "SHARES"

    def test_fallback_calculation_unit_handling(self):
        """Test that fallback calculations handle unit compatibility appropriately."""
        company = Company("AAPL")
        facts = company.get_facts()

        # Test gross profit calculation fallback
        gross_profit = facts.get_gross_profit()
        if gross_profit is not None:
            # Should get a reasonable value
            assert gross_profit > 0, "Gross profit should be positive"

    def test_real_world_unit_variations(self):
        """Test handling of real-world unit variations."""
        # Test various currency representations
        currency_variations = [
            ("USD", "US DOLLAR"),
            ("EUR", "EURO"),
            ("GBP", "POUND"),
            ("JPY", "YEN")
        ]

        for normalized, variation in currency_variations:
            assert UnitNormalizer.normalize_unit(variation) == normalized
            assert UnitNormalizer.are_compatible(normalized, variation)

    def test_error_messages_and_suggestions(self):
        """Test that unit mismatch errors provide helpful suggestions."""
        from edgar.entity.models import FinancialFact
        from datetime import date

        fact = FinancialFact(
            concept="Revenue",
            taxonomy="us-gaap",
            label="Revenue",
            value=1000000,
            numeric_value=1000000.0,
            unit="USD",
            period_end=date(2023, 12, 31),
            fiscal_year=2023
        )

        # Test incompatible unit types
        result = UnitNormalizer.get_normalized_value(
            fact, target_unit="shares", strict_unit_match=True
        )

        assert not result.success, "Should fail for incompatible units"
        assert result.error_reason is not None, "Should provide error reason"
        assert len(result.suggestions) > 0, "Should provide helpful suggestions"


class TestUnitHandlingDocumentation:
    """Document expected behavior through tests."""

    def test_user_expectations_documentation(self):
        """Document what users should expect from unit filtering."""
        company = Company("AAPL")
        facts = company.get_facts()

        # EXPECTED: Exact unit matching
        # facts.get_revenue(unit="USD") -> Returns USD value if available, None if not
        # facts.get_revenue(unit="EUR") -> Returns None (no automatic currency conversion)
        # facts.get_revenue(unit="shares") -> Returns None (incompatible unit type)

        usd_revenue = facts.get_revenue(unit="USD")
        eur_revenue = facts.get_revenue(unit="EUR")
        shares_revenue = facts.get_revenue(unit="shares")

        assert usd_revenue is not None, "Apple should have USD revenue"
        assert eur_revenue is None, "Should not auto-convert to EUR"
        assert shares_revenue is None, "Shares is incompatible with revenue"

    def test_advanced_usage_patterns(self):
        """Test advanced usage patterns for power users."""
        # Power users can access the unit handling directly for more control
        from edgar.entity.unit_handling import UnitNormalizer
        from edgar.entity.models import FinancialFact
        from datetime import date

        fact = FinancialFact(
            concept="Revenue",
            taxonomy="us-gaap",
            label="Revenue",
            value=1000000,
            numeric_value=1000000.0,
            unit="US DOLLAR",
            period_end=date(2023, 12, 31),
            fiscal_year=2023
        )

        # Check what unit normalization would produce
        normalized_unit = UnitNormalizer.normalize_unit("US DOLLAR")
        assert normalized_unit == "USD"

        # Check compatibility before requesting conversion
        compatible_with_eur = UnitNormalizer.are_compatible("US DOLLAR", "EUR")
        assert compatible_with_eur, "Currencies should be compatible"

        # Get detailed unit handling results
        result = UnitNormalizer.get_normalized_value(fact, target_unit="EUR")
        assert result.success, "Should succeed with suggestion"
        assert len(result.suggestions) > 0, "Should suggest currency conversion"


if __name__ == "__main__":
    # Run specific demonstration
    print("🧪 Unit Compatibility Mode Testing")
    print("=" * 50)

    test_instance = TestUnitCompatibilityModes()

    print("Testing strict unit matching...")
    try:
        test_instance.test_strict_unit_matching_default()
        print("✅ Strict unit matching works correctly")
    except Exception as e:
        print(f"❌ Strict unit matching failed: {e}")

    print("Testing unit normalizer modes...")
    try:
        test_instance.test_unit_normalizer_strict_mode()
        print("✅ Unit normalizer modes work correctly")
    except Exception as e:
        print(f"❌ Unit normalizer modes failed: {e}")

    print("\n📖 Usage Documentation:")
    print("- facts.get_revenue(unit='USD') -> Returns USD value or None")
    print("- facts.get_revenue(unit='EUR') -> Returns None (no auto-conversion)")
    print("- facts.get_revenue(unit='shares') -> Returns None (incompatible)")
    print("- Use UnitNormalizer directly for advanced unit handling")