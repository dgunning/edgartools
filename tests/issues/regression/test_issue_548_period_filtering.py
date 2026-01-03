"""
Regression test for Issue #548: Income statement to_dataframe period filtering broken

GitHub Issue: https://github.com/dgunning/edgartools/issues/548

Problem:
1. period_view parameter caused AttributeError: 'list' object has no attribute 'get'
   - Root cause: get_period_views() returns List[Dict], but code tried to call .get() on it
2. period_filter parameter returned DataFrame with no numerical values
   - Root cause: period_filter was not passed to determine_periods_to_display()

Fix:
- Delegated period handling to determine_periods_to_display() which correctly handles both
  period_filter (specific period key) and period_view (predefined view name)

Reporter: maupardh1 (Hadrien Maupard)
Fix Version: 5.5.1
"""
import pytest


@pytest.fixture
def pltr_10q():
    """Get PLTR 10-Q filing for testing."""
    from edgar import Company
    return Company("PLTR").get_filings(form="10-Q").latest()


class TestIssue548PeriodFiltering:
    """Test period filtering in Statement.to_dataframe()."""

    @pytest.mark.network
    def test_period_view_with_valid_view_name(self, pltr_10q):
        """Test that period_view parameter works with valid view names."""
        xbrl = pltr_10q.xbrl()

        # Get available period views
        period_views = xbrl.get_period_views(statement_type="IncomeStatement")
        assert period_views, "Should have period views available"

        view_name = period_views[0]["name"]

        # This should NOT raise AttributeError anymore
        df = xbrl.statements.income_statement().to_dataframe(period_view=view_name)

        assert df is not None
        assert not df.empty
        assert "concept" in df.columns
        assert "label" in df.columns

        # Should have numeric columns with data
        numeric_cols = [c for c in df.columns if c not in [
            "concept", "label", "level", "abstract", "dimension", "dimension_label",
            "balance", "weight", "preferred_sign", "parent_concept", "parent_abstract_concept",
            "unit", "point_in_time", "is_breakdown", "dimension_axis", "dimension_member"
        ]]
        assert len(numeric_cols) > 0, "Should have period columns"

    @pytest.mark.network
    def test_period_view_with_invalid_name_falls_back_to_default(self, pltr_10q):
        """Test that invalid period_view gracefully falls back to default periods."""
        xbrl = pltr_10q.xbrl()

        # Pass an invalid view name - should fall back to default behavior
        df = xbrl.statements.income_statement().to_dataframe(period_view="NonExistentView")

        assert df is not None
        assert not df.empty

        # Should still have data from default period selection
        numeric_cols = [c for c in df.columns if c not in [
            "concept", "label", "level", "abstract", "dimension", "dimension_label",
            "balance", "weight", "preferred_sign", "parent_concept", "parent_abstract_concept",
            "unit", "point_in_time", "is_breakdown", "dimension_axis", "dimension_member"
        ]]
        assert len(numeric_cols) > 0, "Should fall back to default periods"

    @pytest.mark.network
    def test_period_filter_returns_data(self, pltr_10q):
        """Test that period_filter parameter returns DataFrame with numerical values."""
        xbrl = pltr_10q.xbrl()

        # Get a specific period key
        period_views = xbrl.get_period_views(statement_type="IncomeStatement")
        period_key = period_views[0]["period_keys"][0]

        # This should return data (not empty values)
        df = xbrl.statements.income_statement().to_dataframe(period_filter=period_key)

        assert df is not None
        assert not df.empty

        # Should have exactly one period column (the filtered period)
        numeric_cols = [c for c in df.columns if c not in [
            "concept", "label", "level", "abstract", "dimension", "dimension_label",
            "balance", "weight", "preferred_sign", "parent_concept", "parent_abstract_concept",
            "unit", "point_in_time", "is_breakdown", "dimension_axis", "dimension_member"
        ]]
        assert len(numeric_cols) == 1, f"Should have exactly one period column, got: {numeric_cols}"

        # The period column should have non-null values (this was the bug)
        period_col = numeric_cols[0]
        non_null_count = df[period_col].notna().sum()
        assert non_null_count > 0, f"Period column '{period_col}' should have data (not all null)"

    @pytest.mark.network
    def test_default_behavior_unchanged(self, pltr_10q):
        """Test that default behavior (no period params) still works."""
        xbrl = pltr_10q.xbrl()

        # Default call with no period parameters
        df = xbrl.statements.income_statement().to_dataframe()

        assert df is not None
        assert not df.empty
        assert "concept" in df.columns
        assert "label" in df.columns

        # Should have multiple period columns
        numeric_cols = [c for c in df.columns if c not in [
            "concept", "label", "level", "abstract", "dimension", "dimension_label",
            "balance", "weight", "preferred_sign", "parent_concept", "parent_abstract_concept",
            "unit", "point_in_time", "is_breakdown", "dimension_axis", "dimension_member"
        ]]
        assert len(numeric_cols) >= 1, "Should have period columns"

    @pytest.mark.network
    def test_balance_sheet_period_filter(self, pltr_10q):
        """Test period_filter also works for balance sheet."""
        xbrl = pltr_10q.xbrl()

        # Get a specific instant period for balance sheet
        period_views = xbrl.get_period_views(statement_type="BalanceSheet")
        if period_views and period_views[0].get("period_keys"):
            period_key = period_views[0]["period_keys"][0]

            df = xbrl.statements.balance_sheet().to_dataframe(period_filter=period_key)

            assert df is not None
            assert not df.empty

            # Should have data in the filtered period
            numeric_cols = [c for c in df.columns if c not in [
                "concept", "label", "level", "abstract", "dimension", "dimension_label",
                "balance", "weight", "preferred_sign", "parent_concept", "parent_abstract_concept",
                "unit", "point_in_time", "is_breakdown"
            ]]
            if numeric_cols:
                period_col = numeric_cols[0]
                non_null_count = df[period_col].notna().sum()
                assert non_null_count > 0, f"Period column '{period_col}' should have data"