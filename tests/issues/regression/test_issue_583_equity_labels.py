"""
Regression test for Issue #583: Multiple issues with Statement of Equity

Problems:
1. Incorrect labels: Beginning balances labeled as "Ending balances"
2. Duplicated dimensions: Dimensional breakdowns have identical values
3. is_breakdown flag: Users expected True for dimensional items (actually by design)
4. include_dimensions parameter: Doesn't filter dimensional rows (by design for STANDARD view)

Fixes:
- Added "Beginning balance" / "Ending balance" suffixes to labels in to_dataframe()
- Fixed beginning/ending instant value matching for dimensional items
- Clarified: is_breakdown=False is correct for equity component dimensions (structural)
- Clarified: view='summary' hides all dimensions; view='standard' keeps face-level

See: https://github.com/dgunning/edgartools/issues/583
"""
import pytest
import pandas as pd


class TestIssue583EquityLabels:
    """Test that Statement of Equity labels correctly distinguish beginning vs ending balances."""

    @pytest.fixture
    def aapl_10k_xbrl(self):
        """Get AAPL 10-K XBRL for testing."""
        from edgar import Company
        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        return filing.xbrl()

    @pytest.mark.network
    def test_equity_labels_have_beginning_ending_suffix(self, aapl_10k_xbrl):
        """Test that labels have 'Beginning balance' / 'Ending balance' suffixes."""
        stmt = aapl_10k_xbrl.statements.statement_of_equity()
        df = stmt.to_dataframe()

        # Find rows with Beginning/Ending balance labels
        beginning_rows = df[df['label'].str.contains('Beginning balance', na=False)]
        ending_rows = df[df['label'].str.contains('Ending balance', na=False) &
                         ~df['label'].str.contains('Beginning', na=False)]

        # Should have both beginning and ending balance rows
        assert len(beginning_rows) > 0, \
            "Should have rows with 'Beginning balance' in label"
        assert len(ending_rows) > 0, \
            "Should have rows with 'Ending balance' in label"

    @pytest.mark.network
    def test_stockholders_equity_has_distinct_beginning_ending_labels(self, aapl_10k_xbrl):
        """Test that StockholdersEquity rows have distinct beginning/ending labels."""
        stmt = aapl_10k_xbrl.statements.statement_of_equity()
        df = stmt.to_dataframe()

        # Filter to StockholdersEquity concept
        se_df = df[df['concept'] == 'us-gaap_StockholdersEquity']

        # Should have at least 2 non-dimensional rows (beginning + ending)
        non_dim = se_df[se_df['dimension'] == False]
        assert len(non_dim) >= 2, \
            "Should have at least 2 non-dimensional StockholdersEquity rows"

        # Labels should include both beginning and ending
        labels = non_dim['label'].tolist()
        has_beginning = any('Beginning balance' in l for l in labels)
        has_ending = any('Ending balance' in l and 'Beginning' not in l for l in labels)

        assert has_beginning, "Should have a 'Beginning balance' row"
        assert has_ending, "Should have an 'Ending balance' row"

    @pytest.mark.network
    def test_beginning_and_ending_values_differ(self, aapl_10k_xbrl):
        """Test that beginning balance values differ from ending balance values."""
        stmt = aapl_10k_xbrl.statements.statement_of_equity()
        df = stmt.to_dataframe()

        # Get value columns
        meta_cols = ['concept', 'label', 'level', 'abstract', 'dimension', 'is_breakdown',
                     'dimension_axis', 'dimension_member', 'dimension_member_label',
                     'dimension_label', 'balance', 'weight', 'preferred_sign',
                     'parent_concept', 'parent_abstract_concept', 'unit', 'point_in_time',
                     'standard_concept']
        value_cols = [c for c in df.columns if c not in meta_cols]

        if not value_cols:
            pytest.skip("No value columns found")

        # Get non-dimensional StockholdersEquity rows
        se_df = df[(df['concept'] == 'us-gaap_StockholdersEquity') & (df['dimension'] == False)]

        beginning_rows = se_df[se_df['label'].str.contains('Beginning balance', na=False)]
        ending_rows = se_df[se_df['label'].str.contains('Ending balance', na=False) &
                            ~se_df['label'].str.contains('Beginning', na=False)]

        if len(beginning_rows) == 0 or len(ending_rows) == 0:
            pytest.skip("Could not find both beginning and ending balance rows")

        # Compare values in first value column
        value_col = value_cols[0]
        begin_val = beginning_rows.iloc[0][value_col]
        end_val = ending_rows.iloc[0][value_col]

        # Values should be different (beginning ≠ ending)
        assert begin_val != end_val, \
            f"Beginning ({begin_val}) and ending ({end_val}) values should differ"

    @pytest.mark.network
    def test_dimensional_rows_have_beginning_ending_logic(self, aapl_10k_xbrl):
        """Test that dimensional rows also have beginning/ending balance distinction."""
        stmt = aapl_10k_xbrl.statements.statement_of_equity()
        df = stmt.to_dataframe()

        # Get dimensional StockholdersEquity rows
        se_df = df[(df['concept'] == 'us-gaap_StockholdersEquity') & (df['dimension'] == True)]

        if len(se_df) == 0:
            pytest.skip("No dimensional StockholdersEquity rows found")

        # Group by base label (without Beginning/Ending suffix)
        # Each unique dimensional label should appear twice (beginning + ending)
        labels = se_df['label'].tolist()
        beginning_labels = [l for l in labels if 'Beginning balance' in l]
        ending_labels = [l for l in labels if 'Ending balance' in l and 'Beginning' not in l]

        assert len(beginning_labels) > 0, \
            "Dimensional rows should have 'Beginning balance' labels"
        assert len(ending_labels) > 0, \
            "Dimensional rows should have 'Ending balance' labels"

    @pytest.mark.network
    def test_dimensional_beginning_ending_values_differ(self, aapl_10k_xbrl):
        """Test that dimensional beginning/ending balance values differ."""
        stmt = aapl_10k_xbrl.statements.statement_of_equity()
        df = stmt.to_dataframe()

        # Get value columns
        meta_cols = ['concept', 'label', 'level', 'abstract', 'dimension', 'is_breakdown',
                     'dimension_axis', 'dimension_member', 'dimension_member_label',
                     'dimension_label', 'balance', 'weight', 'preferred_sign',
                     'parent_concept', 'parent_abstract_concept', 'unit', 'point_in_time',
                     'standard_concept']
        value_cols = [c for c in df.columns if c not in meta_cols]

        if not value_cols:
            pytest.skip("No value columns found")

        # Find a dimensional concept that appears twice
        dim_df = df[(df['concept'] == 'us-gaap_StockholdersEquity') & (df['dimension'] == True)]

        # Find pairs of beginning/ending rows with same base label pattern
        beginning_dim = dim_df[dim_df['label'].str.contains('Common stock', na=False) &
                                dim_df['label'].str.contains('Beginning balance', na=False)]
        ending_dim = dim_df[dim_df['label'].str.contains('Common stock', na=False) &
                            dim_df['label'].str.contains('Ending balance', na=False) &
                            ~dim_df['label'].str.contains('Beginning', na=False)]

        if len(beginning_dim) == 0 or len(ending_dim) == 0:
            pytest.skip("Could not find both beginning and ending dimensional rows")

        # Compare values
        value_col = value_cols[0]
        begin_val = beginning_dim.iloc[0][value_col]
        end_val = ending_dim.iloc[0][value_col]

        # Values should be different
        assert begin_val != end_val, \
            f"Dimensional beginning ({begin_val}) and ending ({end_val}) values should differ"


class TestIssue583ViewFiltering:
    """Test that view parameter correctly filters dimensional data."""

    @pytest.fixture
    def aapl_10k_xbrl(self):
        """Get AAPL 10-K XBRL for testing."""
        from edgar import Company
        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        return filing.xbrl()

    @pytest.mark.network
    def test_summary_view_hides_all_dimensions(self, aapl_10k_xbrl):
        """Test that view='summary' hides all dimensional rows."""
        stmt = aapl_10k_xbrl.statements.statement_of_equity()
        df = stmt.to_dataframe(view='summary')

        # SUMMARY view should have no dimensional rows
        dim_count = len(df[df['dimension'] == True])
        assert dim_count == 0, \
            f"view='summary' should have 0 dimensional rows, got {dim_count}"

    @pytest.mark.network
    def test_detailed_view_shows_all_dimensions(self, aapl_10k_xbrl):
        """Test that view='detailed' shows all dimensional rows."""
        stmt = aapl_10k_xbrl.statements.statement_of_equity()
        df = stmt.to_dataframe(view='detailed')

        # DETAILED view should have dimensional rows
        dim_count = len(df[df['dimension'] == True])
        assert dim_count > 0, \
            f"view='detailed' should have dimensional rows, got {dim_count}"

    @pytest.mark.network
    def test_standard_view_keeps_equity_components(self, aapl_10k_xbrl):
        """Test that view='standard' keeps equity component dimensions.

        StatementEquityComponentsAxis is STRUCTURAL for Statement of Equity,
        so equity component dimensions should NOT be filtered out by 'standard' view.
        """
        stmt = aapl_10k_xbrl.statements.statement_of_equity()
        df_standard = stmt.to_dataframe(view='standard')
        df_detailed = stmt.to_dataframe(view='detailed')

        # For Statement of Equity, STANDARD and DETAILED should have similar row counts
        # because equity components are structural, not breakdown
        standard_dims = len(df_standard[df_standard['dimension'] == True])
        detailed_dims = len(df_detailed[df_detailed['dimension'] == True])

        # Should have the same number of dimensional rows
        assert standard_dims == detailed_dims, \
            f"STANDARD ({standard_dims}) and DETAILED ({detailed_dims}) should match for equity"


class TestIssue583IsBreakdownFlag:
    """Test that is_breakdown flag behaves correctly for equity statements."""

    @pytest.fixture
    def aapl_10k_xbrl(self):
        """Get AAPL 10-K XBRL for testing."""
        from edgar import Company
        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        return filing.xbrl()

    @pytest.mark.network
    def test_equity_components_are_not_breakdown(self, aapl_10k_xbrl):
        """Test that equity component dimensions have is_breakdown=False.

        StatementEquityComponentsAxis is STRUCTURAL for Statement of Equity
        (it defines the column structure), so is_breakdown should be False.
        This is by design, not a bug.
        """
        stmt = aapl_10k_xbrl.statements.statement_of_equity()
        df = stmt.to_dataframe()

        # Get dimensional StockholdersEquity rows with equity component axis
        equity_dims = df[
            (df['dimension'] == True) &
            (df['dimension_axis'].str.contains('StatementEquityComponentsAxis', na=False))
        ]

        if len(equity_dims) == 0:
            pytest.skip("No equity component dimensional rows found")

        # All equity component dimensions should have is_breakdown=False
        # because they are STRUCTURAL (define column headers), not BREAKDOWN (notes detail)
        breakdown_count = len(equity_dims[equity_dims['is_breakdown'] == True])
        assert breakdown_count == 0, \
            f"Equity component dimensions should have is_breakdown=False, but {breakdown_count} have True"
