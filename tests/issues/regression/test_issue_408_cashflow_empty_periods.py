"""
Regression test for Issue #408: Cash flow statement missing values

Ensures that cash flow statements filter out periods containing only empty strings,
showing only periods with meaningful financial data.
"""

import pytest
from edgar import *
import pandas as pd


# Metadata columns that should be excluded when looking at period/data columns
METADATA_COLUMNS = [
    'concept', 'label', 'level', 'abstract', 'dimension',
    'balance', 'weight', 'preferred_sign', 'parent_concept', 'parent_abstract_concept',
    'dimension_label', 'unit', 'point_in_time'
]


class TestCashFlowEmptyPeriods:
    """Test cash flow statement handling of empty periods"""


    def test_recent_filing_shows_all_periods_with_data(self):
        """Recent filings should show all periods that have meaningful data"""
        # Test recent Apple filing that works correctly
        # Use relative lookup to get latest Q2/Q3 filing instead of hardcoded accession
        company = Company("AAPL")
        filing = company.get_filings(form="10-Q").latest(1)
        print(str(filing))
        cashflow_stmt = filing.xbrl().statements.cashflow_statement()
        print(cashflow_stmt)
        df = cashflow_stmt.to_dataframe()

        # Get data columns (excluding metadata)
        data_cols = [col for col in df.columns if col not in METADATA_COLUMNS]

        # All periods should have meaningful numeric data
        for col in data_cols:
            numeric_values = pd.to_numeric(df[col], errors='coerce').notna().sum()
            assert numeric_values > 0, f"Period {col} should have numeric data"

    def test_problematic_filing_empty_period_filtering(self):
        """Problematic filings should have empty periods filtered out by Issue #408 fix"""
        # Test filing that previously had empty string periods - now they should be filtered out
        filing = get_by_accession_number('0000320193-18-000070')  # Apple Q1 2018
        cashflow_stmt = filing.xbrl().statements.cashflow_statement()
        df = cashflow_stmt.to_dataframe()

        # Get data columns
        data_cols = [col for col in df.columns if col not in METADATA_COLUMNS]

        # Check that all remaining periods have meaningful data
        empty_periods = []
        meaningful_periods = []

        for col in data_cols:
            numeric_values = pd.to_numeric(df[col], errors='coerce').notna().sum()
            if numeric_values == 0:
                empty_periods.append(col)
            else:
                meaningful_periods.append(col)

        # After the fix, empty periods should be filtered out
        assert len(empty_periods) == 0, f"Empty periods should be filtered out, but found: {empty_periods}"
        assert len(meaningful_periods) > 0, "Should still have some meaningful periods"

        # The previously empty period '2017-09-30 (Q3)' should no longer appear
        assert '2017-09-30 (Q3)' not in data_cols, "Previously empty period should be filtered out"

        # After v4.20.1 dynamic thresholds, we filter more intelligently
        # Expect at least 1 meaningful period (dynamic thresholds may filter more aggressively)
        assert len(data_cols) >= 1, f"Expected at least 1 period after filtering, got {len(data_cols)}: {data_cols}"

    def test_empty_period_filtering_logic(self):
        """Test the logic for identifying periods that should be filtered"""
        # Test multiple problematic filings
        test_cases = [
            {
                'accession': '0000320193-18-000070',  # Apple Q1 2018
                'expected_empty': ['2017-09-30 (Q3)'],
                'should_have_meaningful': True
            },
            {
                'accession': '0000320193-17-000009',  # Apple Q3 2017
                'expected_empty': ['2017-04-01 (Q2)', '2016-12-31 (Q1)'],
                'should_have_meaningful': True
            }
        ]

        for case in test_cases:
            filing = get_by_accession_number(case['accession'])
            cashflow_stmt = filing.xbrl().statements.cashflow_statement()
            df = cashflow_stmt.to_dataframe()

            data_cols = [col for col in df.columns if col not in METADATA_COLUMNS]

            # Identify empty periods
            empty_periods = []
            for col in data_cols:
                numeric_values = pd.to_numeric(df[col], errors='coerce').notna().sum()
                if numeric_values == 0:
                    empty_periods.append(col)

            # After the fix, no periods should be empty (they should be filtered out)
            assert len(empty_periods) == 0, f"Empty periods should be filtered out in {case['accession']}, but found: {empty_periods}"

            # Previously empty periods should no longer appear in the dataframe
            for expected_empty in case['expected_empty']:
                assert expected_empty not in data_cols, \
                    f"Previously empty period {expected_empty} should be filtered out in {case['accession']}"

            # Should still have some meaningful data
            assert len(data_cols) > 0, \
                f"Should have meaningful periods remaining in {case['accession']}"

    def test_filter_periods_with_only_empty_strings(self):
        """Test that the fix automatically filters periods with only empty strings"""

        # Test on previously problematic filing
        filing = get_by_accession_number('0000320193-18-000070')
        cashflow_stmt = filing.xbrl().statements.cashflow_statement()
        df = cashflow_stmt.to_dataframe()

        # Get data columns
        data_cols = [col for col in df.columns if col not in METADATA_COLUMNS]

        # After v4.20.1 dynamic thresholds, we filter more intelligently - not just empty periods
        # but also periods with insufficient data quality. Expect at least 1 meaningful period.
        assert len(data_cols) >= 1, f"Expected at least 1 period after filtering, got {len(data_cols)}: {data_cols}"

        # All remaining periods should have meaningful data
        for col in data_cols:
            numeric_values = pd.to_numeric(df[col], errors='coerce').notna().sum()
            assert numeric_values > 0, f"Period {col} should have meaningful data after filtering"

        # The previously empty period should not be included
        assert '2017-09-30 (Q3)' not in data_cols, "Previously empty period should be filtered out"

        # After v4.20.1, dynamic thresholds may filter more aggressively
        # Check that at least one of the expected meaningful periods is included
        expected_periods = ['2018-03-31 (Q1)', '2018-03-31', '2017-12-30 (Q1)']
        has_meaningful_period = any(expected in data_cols for expected in expected_periods)
        assert has_meaningful_period, f"At least one meaningful period should be included. Got: {data_cols}"

    def test_baseline_filing_unchanged_by_filtering(self):
        """Ensure that good filings are not affected by empty period filtering"""

        def filter_meaningful_periods(dataframe):
            """Same filtering logic as above"""
            data_cols = [col for col in dataframe.columns if col not in METADATA_COLUMNS]

            # Start with all metadata columns that exist in the dataframe
            meaningful_cols = [col for col in METADATA_COLUMNS if col in dataframe.columns]

            for col in data_cols:
                numeric_values = pd.to_numeric(dataframe[col], errors='coerce').notna().sum()
                if numeric_values > 0:
                    meaningful_cols.append(col)

            return dataframe[meaningful_cols]

        # Test on recent working filing - use relative lookup
        company = Company("AAPL")
        filing = company.get_filings(form="10-Q").latest(1)
        cashflow_stmt = filing.xbrl().statements.cashflow_statement()
        original_df = cashflow_stmt.to_dataframe()

        # Apply filtering
        filtered_df = filter_meaningful_periods(original_df)

        # Should be unchanged - all periods have data
        original_data_cols = [col for col in original_df.columns if col not in METADATA_COLUMNS]
        filtered_data_cols = [col for col in filtered_df.columns if col not in METADATA_COLUMNS]

        assert len(original_data_cols) == len(filtered_data_cols)
        assert set(original_data_cols) == set(filtered_data_cols)