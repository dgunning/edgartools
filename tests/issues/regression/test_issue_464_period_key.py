"""
Tests for Issue #464 - Missing period_key column in DataFrame exports

This module tests that the period_key column is included in DataFrame exports
to enable time series analysis across periods.
"""

import pytest
from edgar import Company


class TestPeriodKeyColumn:
    """Test that period_key column is present in DataFrame exports."""

    @pytest.fixture(scope='class')
    def apple_10q(self):
        """Get AAPL 10-Q XBRL for testing (has multiple comparative periods)."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-Q').latest(1)
        return filing.xbrl()

    @pytest.fixture(scope='class')
    def apple_10k(self):
        """Get AAPL 10-K XBRL for testing."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-K').latest(1)
        return filing.xbrl()

    def test_period_key_in_balance_sheet_dataframe(self, apple_10q):
        """period_key column should be present in Balance Sheet DataFrame."""
        df = apple_10q.facts.query().by_statement_type("BalanceSheet").to_dataframe()

        assert 'period_key' in df.columns, "period_key column missing from Balance Sheet DataFrame"
        assert not df['period_key'].isna().all(), "period_key column has no values"

        # Should have multiple periods
        unique_periods = df['period_key'].nunique()
        assert unique_periods >= 2, f"Expected at least 2 periods, found {unique_periods}"

    def test_period_key_in_income_statement_dataframe(self, apple_10q):
        """period_key column should be present in Income Statement DataFrame."""
        df = apple_10q.facts.query().by_statement_type("IncomeStatement").to_dataframe()

        assert 'period_key' in df.columns, "period_key column missing from Income Statement DataFrame"
        assert not df['period_key'].isna().all(), "period_key column has no values"

        # Should have multiple periods
        unique_periods = df['period_key'].nunique()
        assert unique_periods >= 2, f"Expected at least 2 periods, found {unique_periods}"

    def test_period_key_in_cash_flow_dataframe(self, apple_10q):
        """period_key column should be present in Cash Flow Statement DataFrame."""
        df = apple_10q.facts.query().by_statement_type("CashFlowStatement").to_dataframe()

        assert 'period_key' in df.columns, "period_key column missing from Cash Flow DataFrame"
        assert not df['period_key'].isna().all(), "period_key column has no values"

        # Should have multiple periods
        unique_periods = df['period_key'].nunique()
        assert unique_periods >= 2, f"Expected at least 2 periods, found {unique_periods}"

    def test_period_key_format_instant(self, apple_10q):
        """period_key should have correct format for instant periods (Balance Sheet)."""
        df = apple_10q.facts.query().by_statement_type("BalanceSheet").to_dataframe()

        period_keys = df['period_key'].dropna().unique()
        assert len(period_keys) > 0, "No period_key values found"

        # Check format: instant_YYYY-MM-DD
        for pk in period_keys:
            assert pk.startswith('instant_'), f"Invalid period_key format: {pk}"
            date_part = pk.replace('instant_', '')
            assert len(date_part) == 10, f"Invalid date format in period_key: {pk}"
            assert date_part.count('-') == 2, f"Invalid date format in period_key: {pk}"

    def test_period_key_format_duration(self, apple_10q):
        """period_key should have correct format for duration periods (Income Statement)."""
        df = apple_10q.facts.query().by_statement_type("IncomeStatement").to_dataframe()

        period_keys = df['period_key'].dropna().unique()
        assert len(period_keys) > 0, "No period_key values found"

        # Check format: duration_YYYY-MM-DD_YYYY-MM-DD
        for pk in period_keys:
            assert pk.startswith('duration_'), f"Invalid period_key format: {pk}"
            dates_part = pk.replace('duration_', '')
            parts = dates_part.split('_')
            assert len(parts) == 2, f"Invalid duration format in period_key: {pk}"
            for date_part in parts:
                assert len(date_part) == 10, f"Invalid date format in period_key: {pk}"
                assert date_part.count('-') == 2, f"Invalid date format in period_key: {pk}"

    def test_period_key_column_ordering(self, apple_10q):
        """period_key should appear near the front of the DataFrame."""
        df = apple_10q.facts.query().by_statement_type("BalanceSheet").to_dataframe()

        columns = list(df.columns)
        period_key_index = columns.index('period_key')

        # period_key should be before dimension columns
        dim_columns = [c for c in columns if c.startswith('dim_')]
        if dim_columns:
            first_dim_index = columns.index(dim_columns[0])
            assert period_key_index < first_dim_index, \
                "period_key should come before dimension columns"

        # period_key should be near the front (within first 15 columns)
        assert period_key_index < 15, \
            f"period_key at index {period_key_index} should be nearer to front"


class TestTimeSeriesAnalysis:
    """Test that period_key enables time series analysis."""

    @pytest.fixture(scope='class')
    def apple_10q(self):
        """Get AAPL 10-Q XBRL for testing."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-Q').latest(1)
        return filing.xbrl()

    def test_pivot_by_period_key(self, apple_10q):
        """Should be able to pivot data by period_key for time series analysis."""
        import pandas as pd

        df = apple_10q.facts.query().by_statement_type("BalanceSheet").to_dataframe()

        # Filter to a specific concept for testing
        concept_df = df[df['concept'].str.contains('Assets', case=False, na=False)].copy()

        assert not concept_df.empty, "No Assets concepts found for testing"
        assert 'period_key' in concept_df.columns, "period_key missing"

        # Should be able to pivot by period_key
        try:
            pivot = concept_df.pivot_table(
                values='numeric_value',
                index='label',
                columns='period_key',
                aggfunc='first'
            )
            assert not pivot.empty, "Pivot table is empty"
            assert len(pivot.columns) >= 2, f"Expected at least 2 period columns, got {len(pivot.columns)}"

        except Exception as e:
            pytest.fail(f"Failed to pivot by period_key: {e}")

    def test_group_by_period_key(self, apple_10q):
        """Should be able to group facts by period_key."""
        df = apple_10q.facts.query().by_statement_type("BalanceSheet").to_dataframe()

        # Group by period_key
        grouped = df.groupby('period_key').size()

        assert len(grouped) >= 2, f"Expected at least 2 periods, found {len(grouped)}"
        assert grouped.sum() == len(df), "Sum of grouped sizes should equal total rows"

    def test_filter_by_specific_period(self, apple_10q):
        """Should be able to filter facts to a specific period using period_key."""
        df = apple_10q.facts.query().by_statement_type("BalanceSheet").to_dataframe()

        # Get a specific period
        first_period = df['period_key'].dropna().iloc[0]

        # Filter to that period
        period_df = df[df['period_key'] == first_period]

        assert not period_df.empty, f"No facts found for period {first_period}"
        assert (period_df['period_key'] == first_period).all(), \
            "Filtered DataFrame contains facts from other periods"

    def test_comparative_period_analysis(self, apple_10q):
        """Should be able to compare same concept across different periods."""
        import pandas as pd

        df = apple_10q.facts.query().by_statement_type("BalanceSheet").to_dataframe()

        # Find a concept that appears in multiple periods
        concept_counts = df.groupby('concept')['period_key'].nunique()
        multi_period_concepts = concept_counts[concept_counts >= 2].index

        assert len(multi_period_concepts) > 0, "No concepts found in multiple periods"

        # Pick first multi-period concept
        test_concept = multi_period_concepts[0]
        concept_df = df[df['concept'] == test_concept]

        # Should have values for multiple periods
        periods = concept_df['period_key'].nunique()
        assert periods >= 2, f"Expected {test_concept} in at least 2 periods, found {periods}"


class TestBackwardCompatibility:
    """Test that the fix doesn't break existing functionality."""

    @pytest.fixture(scope='class')
    def apple_10q(self):
        """Get AAPL 10-Q XBRL for testing."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-Q').latest(1)
        return filing.xbrl()

    def test_other_columns_still_present(self, apple_10q):
        """Other essential columns should still be present."""
        df = apple_10q.facts.query().by_statement_type("BalanceSheet").to_dataframe()

        essential_columns = [
            'concept', 'label', 'value', 'numeric_value',
            'statement_type', 'decimals'
        ]

        for col in essential_columns:
            assert col in df.columns, f"Essential column '{col}' is missing"

    def test_period_instant_still_present(self, apple_10q):
        """period_instant column should still be present for instant periods."""
        df = apple_10q.facts.query().by_statement_type("BalanceSheet").to_dataframe()

        # Balance Sheet uses instant periods
        assert 'period_instant' in df.columns, "period_instant column missing"

    def test_query_methods_still_work(self, apple_10q):
        """Existing query methods should still work."""
        # Test various query methods
        df1 = apple_10q.facts.query().by_concept("Assets").to_dataframe()
        assert not df1.empty, "by_concept() query failed"

        df2 = apple_10q.facts.query().by_statement_type("IncomeStatement").to_dataframe()
        assert not df2.empty, "by_statement_type() query failed"

        df3 = apple_10q.facts.query().by_label("Revenue").to_dataframe()
        assert not df3.empty, "by_label() query failed"

    def test_fact_key_still_excluded(self, apple_10q):
        """fact_key should still be excluded from DataFrame (internal field)."""
        df = apple_10q.facts.query().by_statement_type("BalanceSheet").to_dataframe()

        assert 'fact_key' not in df.columns, "fact_key should be excluded from DataFrame"

    def test_original_label_still_excluded(self, apple_10q):
        """original_label should still be excluded from DataFrame (internal field)."""
        df = apple_10q.facts.query().by_statement_type("BalanceSheet").to_dataframe()

        assert 'original_label' not in df.columns, "original_label should be excluded from DataFrame"


class TestIssue464Resolution:
    """Test that Issue #464 is completely resolved."""

    @pytest.fixture(scope='class')
    def apple_10q(self):
        """Get AAPL 10-Q XBRL for testing."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-Q').latest(1)
        return filing.xbrl()

    @pytest.fixture(scope='class')
    def apple_10k(self):
        """Get AAPL 10-K XBRL for testing."""
        company = Company('AAPL')
        filing = company.get_filings(form='10-K').latest(1)
        return filing.xbrl()

    def test_10q_has_past_period_data(self, apple_10q):
        """10-Q DataFrame should include comparative period data (Issue #464)."""
        # Test all statement types mentioned in the issue
        statement_types = ["BalanceSheet", "IncomeStatement", "CashFlowStatement"]

        for stmt_type in statement_types:
            df = apple_10q.facts.query().by_statement_type(stmt_type).to_dataframe()

            assert 'period_key' in df.columns, \
                f"{stmt_type}: period_key column missing"

            unique_periods = df['period_key'].nunique()
            assert unique_periods >= 2, \
                f"{stmt_type}: Expected at least 2 periods, found {unique_periods}"

    def test_10k_has_past_period_data(self, apple_10k):
        """10-K DataFrame should include comparative period data (Issue #464)."""
        # 10-K Balance Sheet was specifically mentioned in the issue
        df = apple_10k.facts.query().by_statement_type("BalanceSheet").to_dataframe()

        assert 'period_key' in df.columns, "Balance Sheet: period_key column missing"

        unique_periods = df['period_key'].nunique()
        assert unique_periods >= 2, \
            f"Balance Sheet: Expected at least 2 periods, found {unique_periods}"

    def test_no_missing_concepts_per_period(self, apple_10q):
        """
        Major periods should have facts for key concepts (Issue #464).

        The original issue mentioned "27 missing values" per period,
        but this was actually about the period_key column being missing,
        not about missing concept values.
        """
        df = apple_10q.facts.query().by_statement_type("BalanceSheet").to_dataframe()

        # Count concepts per period
        concepts_per_period = df.groupby('period_key')['concept'].nunique()

        # At least one period should have substantial data (20+ concepts)
        max_concepts = concepts_per_period.max()
        assert max_concepts >= 20, \
            f"Expected at least one period with 20+ concepts, max found: {max_concepts}"

        # Most periods should have at least a few concepts
        periods_with_data = (concepts_per_period >= 3).sum()
        assert periods_with_data >= 2, \
            f"Expected at least 2 periods with 3+ concepts, found: {periods_with_data}"

    def test_time_series_analysis_works(self, apple_10q):
        """
        Time series analysis should work as described in Issue #464.

        The issue mentioned: "Values for past periods to be always propagated,
        as this is crucial for time series analysis"
        """
        import pandas as pd

        # Get Balance Sheet facts
        df = apple_10q.facts.query().by_statement_type("BalanceSheet").to_dataframe()

        # Find a concept that appears in multiple periods
        concept_counts = df.groupby('concept')['period_key'].nunique()
        multi_period_concept = concept_counts[concept_counts >= 2].index[0]

        # Filter to that concept
        concept_df = df[df['concept'] == multi_period_concept]

        # Should be able to create time series pivot
        try:
            pivot = concept_df.pivot_table(
                values='numeric_value',
                index='label',
                columns='period_key',
                aggfunc='first'
            )

            assert not pivot.empty, "Time series pivot is empty"
            assert len(pivot.columns) >= 2, "Time series should have at least 2 periods"

        except Exception as e:
            pytest.fail(f"Time series analysis failed: {e}")
