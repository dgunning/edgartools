"""
Regression test for GitHub Issue #582: Certain filings losing numeric data during dataframe conversion

Problem: BIO 2019/2020 10-K filings had current year values zeroed out when calling
to_dataframe(include_dimensions=False). The rendered statement showed all periods correctly,
but the DataFrame conversion was losing the most recent period's data.

Root cause: Multiple periods mapped to the same column name (e.g., both
'duration_2018-01-01_2018-12-31' and 'duration_2017-12-01_2018-12-31' mapped to '2018-12-31').
The second period (a transition period for accounting standard changes) had no values,
and was overwriting the valid values from the first period.

Fix: In _build_dataframe_from_raw_data(), don't overwrite a non-None value with None.

See: https://github.com/dgunning/edgartools/issues/582
"""
import pytest


class TestIssue582BIODataframeLoss:
    """Test that BIO filings don't lose data during DataFrame conversion."""

    @pytest.fixture
    def bio_2019_xbrl(self):
        """Get BIO 2019 10-K XBRL for testing."""
        from edgar import Company
        company = Company('BIO')
        filings = company.get_filings(form='10-K', amendments=False)
        filing = filings.filter(date='2019-01-01:2019-12-31').latest()
        return filing.xbrl()

    @pytest.fixture
    def bio_2020_xbrl(self):
        """Get BIO 2020 10-K XBRL for testing."""
        from edgar import Company
        company = Company('BIO')
        filings = company.get_filings(form='10-K', amendments=False)
        filing = filings.filter(date='2020-01-01:2020-12-31').latest()
        return filing.xbrl()

    @pytest.mark.network
    def test_bio_2019_current_period_has_data(self, bio_2019_xbrl):
        """Test that BIO 2019 10-K income statement has data for all periods including 2018."""
        import warnings
        warnings.filterwarnings('ignore', category=DeprecationWarning)

        income = bio_2019_xbrl.statements.income_statement()
        df = income.to_dataframe(include_dimensions=False)

        # Filter to non-abstract rows
        non_abstract = df[df['abstract'] == False]

        # Check that 2018-12-31 has values (this was the column that was being zeroed out)
        assert '2018-12-31' in df.columns, "2018-12-31 column should exist"
        non_null_2018 = non_abstract['2018-12-31'].notna().sum()
        assert non_null_2018 > 10, f"2018-12-31 should have >10 non-null values, got {non_null_2018}"

        # Also check prior periods still work
        if '2017-12-31' in df.columns:
            non_null_2017 = non_abstract['2017-12-31'].notna().sum()
            assert non_null_2017 > 10, f"2017-12-31 should have >10 non-null values, got {non_null_2017}"

    @pytest.mark.network
    def test_bio_2020_current_period_has_data(self, bio_2020_xbrl):
        """Test that BIO 2020 10-K income statement has data for all periods including 2019."""
        import warnings
        warnings.filterwarnings('ignore', category=DeprecationWarning)

        income = bio_2020_xbrl.statements.income_statement()
        df = income.to_dataframe(include_dimensions=False)

        # Filter to non-abstract rows
        non_abstract = df[df['abstract'] == False]

        # Check that 2019-12-31 has values
        assert '2019-12-31' in df.columns, "2019-12-31 column should exist"
        non_null_2019 = non_abstract['2019-12-31'].notna().sum()
        assert non_null_2019 > 10, f"2019-12-31 should have >10 non-null values, got {non_null_2019}"

    @pytest.mark.network
    def test_view_standard_also_works(self, bio_2019_xbrl):
        """Test that view='standard' (recommended replacement for include_dimensions=False) also works."""
        income = bio_2019_xbrl.statements.income_statement()
        df = income.to_dataframe(view='standard')

        # Filter to non-abstract rows
        non_abstract = df[df['abstract'] == False]

        # Check that 2018-12-31 has values
        assert '2018-12-31' in df.columns, "2018-12-31 column should exist"
        non_null_2018 = non_abstract['2018-12-31'].notna().sum()
        assert non_null_2018 > 10, f"2018-12-31 should have >10 non-null values, got {non_null_2018}"

    @pytest.mark.network
    def test_revenue_has_values_for_all_periods(self, bio_2019_xbrl):
        """Test that Revenue specifically has values for all periods."""
        import warnings
        warnings.filterwarnings('ignore', category=DeprecationWarning)

        income = bio_2019_xbrl.statements.income_statement()
        df = income.to_dataframe(include_dimensions=False)

        # Find revenue row
        revenue_rows = df[df['concept'].str.contains('Revenue', case=False, na=False)]
        assert len(revenue_rows) > 0, "Should have at least one Revenue row"

        revenue = revenue_rows.iloc[0]

        # Check all period columns have values
        for col in ['2018-12-31', '2017-12-31', '2016-12-31']:
            if col in df.columns:
                assert revenue[col] is not None and revenue[col] > 0, \
                    f"Revenue should have a positive value for {col}, got {revenue[col]}"
