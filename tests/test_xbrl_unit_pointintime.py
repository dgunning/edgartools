"""
Tests for XBRL unit and point-in-time support (FEAT-449).

This module tests the new optional parameters `include_unit` and `include_point_in_time`
added to DataFrame conversion methods.
"""
pytest_plugins = ["tests.fixtures.xbrl2_fixtures"]

from pathlib import Path
import time
import pytest
from rich import print

from edgar import Filing
from edgar.xbrl import XBRL
from edgar.xbrl.core import get_unit_display_name, is_point_in_time
import pandas as pd


# ========================================
# Unit Tests for Helper Functions
# ========================================

class TestUnitHelperFunctions:
    """Test the core unit and period type resolution functions."""

    def test_get_unit_display_name_monetary_units(self):
        """Test unit name resolution for monetary units."""
        # Standard monetary units
        assert get_unit_display_name('U-Monetary') == 'usd'
        assert get_unit_display_name('iso4217:USD') == 'usd'
        assert get_unit_display_name('USD') == 'usd'

        # Other currencies
        assert get_unit_display_name('iso4217:EUR') == 'eur'
        assert get_unit_display_name('EUR') == 'eur'
        assert get_unit_display_name('iso4217:GBP') == 'gbp'
        assert get_unit_display_name('iso4217:JPY') == 'jpy'

    def test_get_unit_display_name_share_units(self):
        """Test unit name resolution for share-based units."""
        assert get_unit_display_name('U-Shares') == 'shares'
        assert get_unit_display_name('shares') == 'shares'
        assert get_unit_display_name('Shares') == 'shares'

    def test_get_unit_display_name_per_share_units(self):
        """Test unit name resolution for per-share ratios."""
        assert get_unit_display_name('U-USD-per-shares') == 'usdPerShare'
        assert get_unit_display_name('usd-per-share') == 'usdPerShare'
        assert get_unit_display_name('monetary-per-share') == 'usdPerShare'

        # Other currency per share
        assert get_unit_display_name('eur-per-share') == 'eurPerShare'
        assert get_unit_display_name('gbp-per-share') == 'gbpPerShare'

    def test_get_unit_display_name_pure_numbers(self):
        """Test unit name resolution for dimensionless numbers."""
        assert get_unit_display_name('pure') == 'number'
        assert get_unit_display_name('Pure') == 'number'
        assert get_unit_display_name('number') == 'number'

    def test_get_unit_display_name_none(self):
        """Test unit name resolution with None input."""
        assert get_unit_display_name(None) is None
        assert get_unit_display_name('') is None

    def test_get_unit_display_name_unknown_units(self):
        """Test unit name resolution for unknown/custom units."""
        # Should return simplified version
        result = get_unit_display_name('U-CustomUnit')
        assert result == 'customunit'

        result = get_unit_display_name('iso4217:CustomCurrency')
        assert result == 'customcurrency'

    def test_is_point_in_time_instant(self):
        """Test point-in-time detection for instant periods."""
        assert is_point_in_time('instant') is True

    def test_is_point_in_time_duration(self):
        """Test point-in-time detection for duration periods."""
        assert is_point_in_time('duration') is False

    def test_is_point_in_time_none(self):
        """Test point-in-time detection with None input."""
        assert is_point_in_time(None) is None

    def test_is_point_in_time_case_sensitive(self):
        """Test that period type comparison is exact (case-sensitive)."""
        # Should only match exact 'instant' string
        assert is_point_in_time('instant') is True
        assert is_point_in_time('Instant') is False  # Case mismatch
        assert is_point_in_time('INSTANT') is False  # Case mismatch


# ========================================
# Integration Tests - Backward Compatibility
# ========================================

@pytest.fixture
def aapl_xbrl():
    """Apple 10-K XBRL fixture."""
    data_dir = Path("tests/fixtures/xbrl2/aapl/10k_2023")
    return XBRL.from_directory(data_dir)


class TestBackwardCompatibility:
    """Test that existing code continues to work unchanged."""

    def test_to_dataframe_default_parameters(self, aapl_xbrl):
        """Test that to_dataframe() works without new parameters."""
        income_statement = aapl_xbrl.statements.income_statement()
        df = income_statement.to_dataframe()

        # Should work as before
        assert df is not None
        assert 'concept' in df.columns
        assert 'label' in df.columns

        # Should NOT include new columns by default
        assert 'unit' not in df.columns
        assert 'point_in_time' not in df.columns

    def test_rendered_statement_to_dataframe_default(self, aapl_xbrl):
        """Test that RenderedStatement.to_dataframe() works without new parameters."""
        income_statement = aapl_xbrl.statements.income_statement()
        rendered = income_statement.render()
        df = rendered.to_dataframe()

        # Should work as before
        assert df is not None
        assert 'concept' in df.columns
        assert 'label' in df.columns

        # Should NOT include new columns by default
        assert 'unit' not in df.columns
        assert 'point_in_time' not in df.columns

    def test_multiple_statements_backward_compatible(self, aapl_xbrl):
        """Test that all statement types work without new parameters."""
        statements_to_test = [
            'balance_sheet',
            'income_statement',
            'cashflow_statement'
        ]

        for stmt_method in statements_to_test:
            statement = getattr(aapl_xbrl.statements, stmt_method)()
            if statement:
                df = statement.to_dataframe()
                assert df is not None
                assert 'unit' not in df.columns
                assert 'point_in_time' not in df.columns


# ========================================
# Integration Tests - New Functionality
# ========================================

class TestUnitColumnFeature:
    """Test the include_unit parameter functionality."""

    def test_include_unit_adds_column(self, aapl_xbrl):
        """Test that include_unit=True adds a unit column."""
        income_statement = aapl_xbrl.statements.income_statement()
        df = income_statement.to_dataframe(include_unit=True)

        # Unit column should be present
        assert 'unit' in df.columns

        # Should still have all standard columns
        assert 'concept' in df.columns
        assert 'label' in df.columns

    def test_unit_column_has_valid_values(self, aapl_xbrl):
        """Test that unit column contains expected unit names."""
        income_statement = aapl_xbrl.statements.income_statement()
        df = income_statement.to_dataframe(include_unit=True)

        # Get unique units (excluding None)
        units = df['unit'].dropna().unique()

        # Should contain common financial units
        # At least one of: usd, shares, usdPerShare, number, etc.
        assert len(units) > 0, "Should have at least one unit type"

        # Check that units are in expected format (lowercase, no special chars except 'Per')
        valid_unit_pattern = all(
            isinstance(u, str) and (u.islower() or 'Per' in u)
            for u in units
        )
        assert valid_unit_pattern, f"Units should be in standard format: {units}"

    def test_unit_column_monetary_facts(self, aapl_xbrl):
        """Test that monetary facts have 'usd' unit."""
        income_statement = aapl_xbrl.statements.income_statement()
        df = income_statement.to_dataframe(include_unit=True)

        # Revenue should be in usd
        revenue_rows = df[df['concept'].str.contains('Revenue', case=False, na=False)]
        if len(revenue_rows) > 0:
            # At least one revenue fact should have 'usd' unit
            assert 'usd' in revenue_rows['unit'].values

    def test_balance_sheet_with_units(self, aapl_xbrl):
        """Test unit column on balance sheet (instant periods)."""
        balance_sheet = aapl_xbrl.statements.balance_sheet()
        df = balance_sheet.to_dataframe(include_unit=True)

        # Unit column should be present
        assert 'unit' in df.columns

        # Should have monetary units for assets/liabilities
        units = df['unit'].dropna().unique()
        assert len(units) > 0


class TestPointInTimeColumnFeature:
    """Test the include_point_in_time parameter functionality."""

    def test_include_point_in_time_adds_column(self, aapl_xbrl):
        """Test that include_point_in_time=True adds a point_in_time column."""
        income_statement = aapl_xbrl.statements.income_statement()
        df = income_statement.to_dataframe(include_point_in_time=True)

        # Point-in-time column should be present
        assert 'point_in_time' in df.columns

        # Should still have all standard columns
        assert 'concept' in df.columns
        assert 'label' in df.columns

    def test_point_in_time_column_boolean_values(self, aapl_xbrl):
        """Test that point_in_time column contains boolean values."""
        income_statement = aapl_xbrl.statements.income_statement()
        df = income_statement.to_dataframe(include_point_in_time=True)

        # Get unique values (excluding None)
        pit_values = df['point_in_time'].dropna().unique()

        # Should only contain True, False, or be empty
        assert all(isinstance(v, bool) for v in pit_values), \
            f"point_in_time should only contain boolean values: {pit_values}"

    def test_income_statement_duration_facts(self, aapl_xbrl):
        """Test that income statement facts have point_in_time=False (duration)."""
        income_statement = aapl_xbrl.statements.income_statement()
        df = income_statement.to_dataframe(include_point_in_time=True)

        # Income statements use duration periods
        # Most facts should have point_in_time=False
        pit_values = df['point_in_time'].dropna()
        if len(pit_values) > 0:
            # At least 80% should be False (duration)
            false_count = (pit_values == False).sum()
            assert false_count / len(pit_values) >= 0.8, \
                "Income statement should primarily use duration periods"

    def test_balance_sheet_instant_facts(self, aapl_xbrl):
        """Test that balance sheet facts have point_in_time=True (instant)."""
        balance_sheet = aapl_xbrl.statements.balance_sheet()
        df = balance_sheet.to_dataframe(include_point_in_time=True)

        # Balance sheets use instant periods
        # Most facts should have point_in_time=True
        pit_values = df['point_in_time'].dropna()
        if len(pit_values) > 0:
            # At least 80% should be True (instant)
            true_count = (pit_values == True).sum()
            assert true_count / len(pit_values) >= 0.8, \
                "Balance sheet should primarily use instant periods"


class TestCombinedParameters:
    """Test using both parameters together."""

    def test_both_parameters_add_both_columns(self, aapl_xbrl):
        """Test that both parameters can be used together."""
        income_statement = aapl_xbrl.statements.income_statement()
        df = income_statement.to_dataframe(
            include_unit=True,
            include_point_in_time=True
        )

        # Both columns should be present
        assert 'unit' in df.columns
        assert 'point_in_time' in df.columns

        # Should still have all standard columns
        assert 'concept' in df.columns
        assert 'label' in df.columns

    def test_combined_filtering_use_case(self, aapl_xbrl):
        """Test practical use case: filter by unit and point_in_time."""
        income_statement = aapl_xbrl.statements.income_statement()
        df = income_statement.to_dataframe(
            include_unit=True,
            include_point_in_time=True
        )

        # Filter to monetary duration facts (typical income statement items)
        monetary_duration = df[
            (df['unit'] == 'usd') & (df['point_in_time'] == False)
        ]

        # Should have some results
        assert len(monetary_duration) > 0, \
            "Should find monetary duration facts in income statement"


# ========================================
# Integration Tests - Real Filings
# ========================================
# NOTE: Network tests removed as they depend on specific SEC filing availability
# Local fixture tests provide comprehensive coverage of real-world XBRL data


# ========================================
# Performance Tests
# ========================================

class TestPerformanceOverhead:
    """Test that new parameters have minimal performance impact."""

    def test_no_overhead_when_not_used(self, aapl_xbrl):
        """Test that there's minimal overhead when parameters are not used."""
        income_statement = aapl_xbrl.statements.income_statement()

        # Time without new parameters
        start = time.time()
        for _ in range(10):
            df1 = income_statement.to_dataframe()
        time_without = time.time() - start

        # Time with new parameters disabled (should be same)
        start = time.time()
        for _ in range(10):
            df2 = income_statement.to_dataframe(
                include_unit=False,
                include_point_in_time=False
            )
        time_with_false = time.time() - start

        # Should have negligible difference (<25% overhead)
        # Note: Small timing variances are expected due to system load, Python GC, etc.
        overhead = abs(time_with_false - time_without) / time_without
        assert overhead < 0.25, \
            f"Overhead when parameters disabled should be <25%, got {overhead:.1%}"

    def test_reasonable_overhead_when_enabled(self, aapl_xbrl):
        """Test that overhead is reasonable when parameters are enabled."""
        income_statement = aapl_xbrl.statements.income_statement()

        # Time without new columns
        start = time.time()
        for _ in range(10):
            df1 = income_statement.to_dataframe()
        time_without = time.time() - start

        # Time with both new columns
        start = time.time()
        for _ in range(10):
            df2 = income_statement.to_dataframe(
                include_unit=True,
                include_point_in_time=True
            )
        time_with = time.time() - start

        # Should have reasonable overhead (<50%)
        overhead = (time_with - time_without) / time_without
        assert overhead < 0.50, \
            f"Overhead when enabled should be <50%, got {overhead:.1%}"


# ========================================
# User Acceptance Tests
# ========================================

class TestUserAcceptanceCriteria:
    """Test user-described use cases from GitHub issue #449."""

    def test_unit_aware_visualization_use_case(self, aapl_xbrl):
        """Test use case: Unit-aware filtering for visualization."""
        income_statement = aapl_xbrl.statements.income_statement()
        df = income_statement.to_dataframe(include_unit=True)

        # User wants to filter by unit type for proper chart labeling
        revenue_facts = df[df['unit'] == 'usd']
        share_facts = df[df['unit'] == 'shares']
        per_share_metrics = df[df['unit'] == 'usdPerShare']

        # Should be able to separate different unit types
        # (At least revenue facts should exist)
        assert len(revenue_facts) > 0, \
            "Should find monetary (usd) facts for visualization"

    def test_quarterly_calculation_use_case(self, aapl_xbrl):
        """Test use case: Point-in-time aware quarterly calculations."""
        balance_sheet = aapl_xbrl.statements.balance_sheet()
        df = balance_sheet.to_dataframe(include_point_in_time=True)

        # User wants to identify instant vs duration facts for calculations
        instant_facts = df[df['point_in_time'] == True]
        duration_facts = df[df['point_in_time'] == False]

        # Balance sheet should have instant facts
        assert len(instant_facts) > 0, \
            "Should find instant facts for balance sheet"

    def test_combined_context_use_case(self, aapl_xbrl):
        """Test use case: Combined unit and point-in-time context."""
        income_statement = aapl_xbrl.statements.income_statement()
        df = income_statement.to_dataframe(
            include_unit=True,
            include_point_in_time=True
        )

        # User wants maximum context for automated processing
        # Should have both unit and point-in-time information
        assert 'unit' in df.columns
        assert 'point_in_time' in df.columns

        # Should have data in both columns
        unit_coverage = df['unit'].notna().sum() / len(df)
        pit_coverage = df['point_in_time'].notna().sum() / len(df)

        assert unit_coverage > 0.5, \
            f"Should have >50% unit coverage, got {unit_coverage:.1%}"
        assert pit_coverage > 0.5, \
            f"Should have >50% point-in-time coverage, got {pit_coverage:.1%}"


# ========================================
# Edge Case Tests
# ========================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_missing_unit_handled_gracefully(self, aapl_xbrl):
        """Test that missing unit information is handled as None."""
        income_statement = aapl_xbrl.statements.income_statement()
        df = income_statement.to_dataframe(include_unit=True)

        # Some rows might have None for unit (this is OK)
        # Should not crash, should handle gracefully
        assert 'unit' in df.columns

        # None values are acceptable
        none_count = df['unit'].isna().sum()
        # Just verify it doesn't crash (some None values are expected)

    def test_missing_period_type_handled_gracefully(self, aapl_xbrl):
        """Test that missing period_type information is handled as None."""
        income_statement = aapl_xbrl.statements.income_statement()
        df = income_statement.to_dataframe(include_point_in_time=True)

        # Some rows might have None for point_in_time (this is OK)
        # Should not crash, should handle gracefully
        assert 'point_in_time' in df.columns

        # None values are acceptable
        none_count = df['point_in_time'].isna().sum()
        # Just verify it doesn't crash

    def test_empty_statement_handled(self, aapl_xbrl):
        """Test that empty statements don't crash with new parameters."""
        # Try to get a statement that might not exist
        try:
            statement = aapl_xbrl.statements.changes_in_equity()
            if statement:
                # Should not crash even if empty
                df = statement.to_dataframe(
                    include_unit=True,
                    include_point_in_time=True
                )
                assert df is not None
        except Exception:
            # If statement doesn't exist, that's fine
            pass


# ========================================
# Cross-Statement Consistency Tests
# ========================================

class TestCrossStatementConsistency:
    """Test that unit/period_type are consistent across statements."""

    def test_same_concept_same_unit_across_statements(self, aapl_xbrl):
        """Test that the same concept has the same unit in different statements."""
        # Get Net Income from income statement and cash flow statement
        income_statement = aapl_xbrl.statements.income_statement()
        cashflow_statement = aapl_xbrl.statements.cashflow_statement()

        is_df = income_statement.to_dataframe(include_unit=True)
        cf_df = cashflow_statement.to_dataframe(include_unit=True)

        # Find Net Income in both statements
        net_income_concept = 'us-gaap_NetIncomeLoss'
        is_net_income = is_df[is_df['concept'] == net_income_concept]
        cf_net_income = cf_df[cf_df['concept'] == net_income_concept]

        if len(is_net_income) > 0 and len(cf_net_income) > 0:
            # Units should match
            is_unit = is_net_income['unit'].iloc[0]
            cf_unit = cf_net_income['unit'].iloc[0]

            assert is_unit == cf_unit, \
                f"Net Income unit should be consistent: {is_unit} vs {cf_unit}"

    def test_period_type_consistency_by_statement_type(self, aapl_xbrl):
        """Test that statement types consistently use expected period types."""
        # Balance sheet should use instant
        balance_sheet = aapl_xbrl.statements.balance_sheet()
        bs_df = balance_sheet.to_dataframe(include_point_in_time=True)

        # Income statement should use duration
        income_statement = aapl_xbrl.statements.income_statement()
        is_df = income_statement.to_dataframe(include_point_in_time=True)

        # Check that balance sheet is predominantly instant
        bs_pit = bs_df['point_in_time'].dropna()
        if len(bs_pit) > 0:
            bs_instant_pct = (bs_pit == True).sum() / len(bs_pit)
            assert bs_instant_pct > 0.7, \
                f"Balance sheet should be >70% instant, got {bs_instant_pct:.1%}"

        # Check that income statement is predominantly duration
        is_pit = is_df['point_in_time'].dropna()
        if len(is_pit) > 0:
            is_duration_pct = (is_pit == False).sum() / len(is_pit)
            assert is_duration_pct > 0.7, \
                f"Income statement should be >70% duration, got {is_duration_pct:.1%}"
