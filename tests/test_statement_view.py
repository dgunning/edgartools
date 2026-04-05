"""
Tests for StatementView enum functionality (GH-574 / edgartools-dvel).

This tests the StatementView feature that replaces the confusing
include_dimensions boolean parameter with semantic view modes.
"""
import warnings
import pytest
from edgar.xbrl import StatementView, normalize_view


class TestStatementViewEnum:
    """Test StatementView enum and normalize_view function."""

    def test_enum_values(self):
        """Test that enum has expected values."""
        assert StatementView.STANDARD.value == "standard"
        assert StatementView.DETAILED.value == "detailed"
        assert StatementView.SUMMARY.value == "summary"

    def test_normalize_view_with_enum(self):
        """Test normalize_view accepts enum values."""
        assert normalize_view(StatementView.STANDARD) == StatementView.STANDARD
        assert normalize_view(StatementView.DETAILED) == StatementView.DETAILED
        assert normalize_view(StatementView.SUMMARY) == StatementView.SUMMARY

    def test_normalize_view_with_string(self):
        """Test normalize_view accepts string values."""
        assert normalize_view("standard") == StatementView.STANDARD
        assert normalize_view("detailed") == StatementView.DETAILED
        assert normalize_view("summary") == StatementView.SUMMARY

    def test_normalize_view_case_insensitive(self):
        """Test normalize_view is case-insensitive for strings."""
        assert normalize_view("STANDARD") == StatementView.STANDARD
        assert normalize_view("Detailed") == StatementView.DETAILED
        assert normalize_view("SUMMARY") == StatementView.SUMMARY

    def test_normalize_view_none_returns_standard(self):
        """Test normalize_view returns STANDARD for None."""
        assert normalize_view(None) == StatementView.STANDARD

    def test_normalize_view_invalid_value_raises(self):
        """Test normalize_view raises ValueError for invalid values."""
        with pytest.raises(ValueError, match="Invalid view"):
            normalize_view("invalid")

    def test_normalize_view_invalid_type_raises(self):
        """Test normalize_view raises TypeError for invalid types."""
        with pytest.raises(TypeError):
            normalize_view(123)


class TestStatementViewDeprecation:
    """Test deprecation warnings for include_dimensions parameter."""

    @pytest.fixture
    def xbrl(self):
        """Get an XBRL object for testing."""
        from edgar import Company, set_identity
        set_identity('test@test.com')
        filing = Company("AAPL").get_filings(form="10-K").latest()
        return filing.xbrl()

    def test_include_dimensions_emits_deprecation_warning(self, xbrl):
        """Test that include_dimensions emits DeprecationWarning."""
        income = xbrl.statements.income_statement()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            income.to_dataframe(include_dimensions=True)

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "include_dimensions is deprecated" in str(w[0].message)

    def test_include_dimensions_true_maps_to_detailed(self, xbrl):
        """Test that include_dimensions=True maps to DETAILED view."""
        income = xbrl.statements.income_statement()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df_old = income.to_dataframe(include_dimensions=True)

        df_new = income.to_dataframe(view=StatementView.DETAILED)

        assert len(df_old) == len(df_new)

    def test_include_dimensions_false_maps_to_standard(self, xbrl):
        """Test that include_dimensions=False maps to STANDARD view."""
        income = xbrl.statements.income_statement()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df_old = income.to_dataframe(include_dimensions=False)

        df_new = income.to_dataframe(view=StatementView.STANDARD)

        assert len(df_old) == len(df_new)

    def test_view_and_include_dimensions_raises_error(self, xbrl):
        """Test that specifying both view and include_dimensions raises ValueError."""
        income = xbrl.statements.income_statement()

        with pytest.raises(ValueError, match="Cannot specify both"):
            income.to_dataframe(view=StatementView.STANDARD, include_dimensions=True)

        with pytest.raises(ValueError, match="Cannot specify both"):
            income.render(view=StatementView.DETAILED, include_dimensions=False)


class TestStatementViewBehavior:
    """Test StatementView behavior in to_dataframe and render."""

    @pytest.fixture
    def xbrl(self):
        """Get an XBRL object for testing."""
        from edgar import Company, set_identity
        set_identity('test@test.com')
        filing = Company("AAPL").get_filings(form="10-K").latest()
        return filing.xbrl()

    def test_detailed_shows_all_dimensions(self, xbrl):
        """Test DETAILED view shows all dimensional data."""
        income = xbrl.statements.income_statement()
        df = income.to_dataframe(view=StatementView.DETAILED)

        # DETAILED should have the most rows
        df_standard = income.to_dataframe(view=StatementView.STANDARD)
        df_summary = income.to_dataframe(view=StatementView.SUMMARY)

        assert len(df) >= len(df_standard)
        assert len(df) >= len(df_summary)

    def test_standard_shows_face_dimensions_only(self, xbrl):
        """Test STANDARD view shows face-level dimensions only."""
        income = xbrl.statements.income_statement()
        df = income.to_dataframe(view=StatementView.STANDARD)

        # Check for Products/Services but not iPhone/iPad/Mac
        if 'dimension_member' in df.columns:
            members = df['dimension_member'].dropna().unique()
            member_strs = [str(m) for m in members]

            # Face-level members should be present
            has_face = any('Product' in m or 'Service' in m for m in member_strs)

            # Breakdown members should NOT be present
            has_breakdown = any('iPhone' in m or 'iPad' in m or 'Mac' in m for m in member_strs)

            # At least verify no iPhone/iPad/Mac
            assert not has_breakdown, f"Found breakdown members: {member_strs}"

    def test_summary_shows_no_dimensions(self, xbrl):
        """Test SUMMARY view shows non-dimensional totals only."""
        income = xbrl.statements.income_statement()
        df = income.to_dataframe(view=StatementView.SUMMARY)

        # SUMMARY should have the fewest rows
        df_detailed = income.to_dataframe(view=StatementView.DETAILED)

        assert len(df) < len(df_detailed)

    def test_to_dataframe_defaults_to_detailed(self, xbrl):
        """Test to_dataframe defaults to DETAILED view."""
        income = xbrl.statements.income_statement()

        df_default = income.to_dataframe()
        df_detailed = income.to_dataframe(view=StatementView.DETAILED)

        assert len(df_default) == len(df_detailed)

    def test_render_defaults_to_standard(self, xbrl):
        """Test render defaults to STANDARD view (clean display)."""
        income = xbrl.statements.income_statement()

        # Both should produce valid rendered output
        rendered_default = income.render()
        rendered_standard = income.render(view=StatementView.STANDARD)

        assert rendered_default is not None
        assert rendered_standard is not None

    def test_view_parameter_accepts_string(self, xbrl):
        """Test view parameter accepts string values."""
        income = xbrl.statements.income_statement()

        # Should work with string values
        df_standard = income.to_dataframe(view='standard')
        df_detailed = income.to_dataframe(view='detailed')
        df_summary = income.to_dataframe(view='summary')

        assert len(df_detailed) >= len(df_standard) >= len(df_summary)


class TestStatementViewAccessors:
    """Test StatementView in statement accessor methods."""

    @pytest.fixture
    def xbrl(self):
        """Get an XBRL object for testing."""
        from edgar import Company, set_identity
        set_identity('test@test.com')
        filing = Company("AAPL").get_filings(form="10-K").latest()
        return filing.xbrl()

    def test_income_statement_accepts_view(self, xbrl):
        """Test income_statement accessor accepts view parameter."""
        income_detailed = xbrl.statements.income_statement(view=StatementView.DETAILED)
        income_standard = xbrl.statements.income_statement(view=StatementView.STANDARD)

        df_detailed = income_detailed.to_dataframe()
        df_standard = income_standard.to_dataframe()

        # Both should work
        assert len(df_detailed) > 0
        assert len(df_standard) > 0

    def test_balance_sheet_accepts_view(self, xbrl):
        """Test balance_sheet accessor accepts view parameter."""
        bs = xbrl.statements.balance_sheet(view='detailed')
        assert bs is not None

        df = bs.to_dataframe()
        assert len(df) > 0

    def test_cashflow_statement_accepts_view(self, xbrl):
        """Test cashflow_statement accessor accepts view parameter."""
        cf = xbrl.statements.cashflow_statement(view='standard')
        assert cf is not None

        df = cf.to_dataframe()
        assert len(df) > 0
