"""
Regression test for Issue #571: Statement of Equity NaN values

Problem: After v5.7.0 changed the `include_dimensions` default to False,
Statement of Equity and Comprehensive Income statements showed mostly NaN
values because these are inherently dimensional statements that require
dimensional data to display values correctly.

Fix: Changed the default for `statement_of_equity()` and `comprehensive_income()`
to `include_dimensions=True` since these are inherently dimensional statements.

See: https://github.com/dgunning/edgartools/issues/571
"""
import pytest


class TestIssue571EquityNaNValues:
    """Test that Statement of Equity has values (not NaN) by default."""

    @pytest.fixture
    def aapl_10k_xbrl(self):
        """Get AAPL 10-K XBRL for testing."""
        from edgar import Company
        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        return filing.xbrl()

    @pytest.mark.network
    def test_statement_of_equity_default_includes_dimensions(self, aapl_10k_xbrl):
        """Test that statement_of_equity() defaults to include_dimensions=True."""
        stmt = aapl_10k_xbrl.statements.statement_of_equity()

        # The Statement should have include_dimensions=True by default
        assert stmt._include_dimensions is True, \
            "statement_of_equity() should default to include_dimensions=True"

    @pytest.mark.network
    def test_statement_of_equity_has_values(self, aapl_10k_xbrl):
        """Test that Statement of Equity DataFrame has values (not all NaN)."""
        stmt = aapl_10k_xbrl.statements.statement_of_equity()
        df = stmt.to_dataframe()

        # Get value columns (date columns)
        meta_cols = ['concept', 'label', 'level', 'abstract', 'dimension',
                     'dimension_label', 'balance', 'weight', 'preferred_sign',
                     'parent_concept', 'parent_abstract_concept']
        value_cols = [c for c in df.columns if c not in meta_cols]

        assert len(value_cols) > 0, "Should have at least one value column"

        # Filter to non-abstract concepts
        non_abstract = df[df['abstract'] == False]

        # Check that at least some non-abstract concepts have values
        value_col = value_cols[0]
        has_value = non_abstract[non_abstract[value_col].notna()]

        # Before the fix: only 4 out of 13 concepts had values (31%)
        # After the fix: at least 12 out of 27 concepts have values (44%)
        assert len(has_value) >= 10, \
            f"Expected at least 10 concepts with values, got {len(has_value)}"

        # Verify specific equity-related concepts have values
        concepts_with_values = set(has_value['concept'].tolist())

        # These concepts should have values in Statement of Equity
        expected_concepts = [
            'us-gaap_NetIncomeLoss',
            'us-gaap_StockRepurchasedAndRetiredDuringPeriodValue',
        ]

        for expected in expected_concepts:
            matching = [c for c in concepts_with_values if expected in c]
            assert len(matching) > 0, \
                f"Expected to find value for {expected}, but it was NaN"

    @pytest.mark.network
    def test_comprehensive_income_default_includes_dimensions(self, aapl_10k_xbrl):
        """Test that comprehensive_income() defaults to include_dimensions=True."""
        stmt = aapl_10k_xbrl.statements.comprehensive_income()

        if stmt:
            # The Statement should have include_dimensions=True by default
            assert stmt._include_dimensions is True, \
                "comprehensive_income() should default to include_dimensions=True"

    @pytest.mark.network
    def test_backwards_compatibility_explicit_false(self, aapl_10k_xbrl):
        """Test that users can still explicitly set include_dimensions=False."""
        stmt = aapl_10k_xbrl.statements.statement_of_equity(include_dimensions=False)

        # Should respect explicit False setting
        assert stmt._include_dimensions is False

        # DataFrame should filter out dimensional items
        df = stmt.to_dataframe()
        non_abstract = df[df['abstract'] == False]

        # With include_dimensions=False, should have fewer rows than with True
        stmt_with_dims = aapl_10k_xbrl.statements.statement_of_equity(include_dimensions=True)
        df_with_dims = stmt_with_dims.to_dataframe()
        non_abstract_with_dims = df_with_dims[df_with_dims['abstract'] == False]

        assert len(non_abstract) < len(non_abstract_with_dims), \
            "include_dimensions=False should result in fewer rows"

    @pytest.mark.network
    def test_statement_of_equity_rendering_has_values(self, aapl_10k_xbrl):
        """Test that rich rendering also shows values."""
        stmt = aapl_10k_xbrl.statements.statement_of_equity()

        # The statement should render without errors
        rendered = str(stmt)

        # Should contain actual dollar values (not just NaN/empty)
        assert 'NaN' not in rendered, "Rendered statement should not contain 'NaN'"

        # Should contain some recognizable line items
        assert 'Stockholders' in rendered or 'Equity' in rendered, \
            "Rendered statement should contain equity-related labels"
