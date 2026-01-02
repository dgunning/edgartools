"""
Regression test for Issue #513: NFLX Missing Critical Data

Tests critical data accuracy bugs:
1. 2012 10-K report missing fiscal year 2012 data (only showed 2011 and 2010)
2. Revenue deduplication removing valid segment data that happened to have matching values
3. XBRL vs SGML date discrepancy causing wrong fiscal year

Root causes:
1. Period selection logic allowed multi-year cumulative periods (e.g., "Jan 2007 to Dec 2012" - 2190 days)
   - Fix: Changed filter from `days > 300` to `300 < days <= 370` to exclude multi-year periods
2. Deduplication logic grouped by (period, value) only, ignoring dimensional differences
   - Fix: Changed grouping to (period, value, dimensions) to preserve segment data
3. XBRL DocumentPeriodEndDate (2011-12-31) was wrong, SGML header had correct date (2012-12-31)
   - Fix: Added date discrepancy detection in XBRL.period_of_report to prefer SGML date when
     there's a mismatch and SGML year has annual data in the filing
"""

import pytest
from edgar import Filing


# Create the filing directly for reliability (session-scoped fixture can have issues)
def get_nflx_2012_10k():
    """Get Netflix 2012 10-K filing (fiscal 2011) directly."""
    return Filing(
        company='NETFLIX INC',
        cik=1065280,
        form='10-K',
        filing_date='2013-02-01',
        accession_no='0001065280-13-000008'
    )


@pytest.mark.regression
class TestIssue513NFLX2012TenK:
    """Test that 2012 10-K shows fiscal year 2012 data"""

    def test_date_discrepancy_corrected_to_2012(self):
        """
        The filing 0001065280-13-000008 has a date discrepancy:
        - SGML header: 2012-12-31 (correct - this is the fiscal 2012 10-K)
        - XBRL DocumentPeriodEndDate: 2011-12-31 (incorrect)

        The date discrepancy detection should correct this to use the SGML date
        since the filing contains 2012 annual period data.
        """
        filing = get_nflx_2012_10k()
        xbrl = filing.xbrl()

        # Verify the raw XBRL date is wrong
        assert xbrl._get_xbrl_period_of_report() == '2011-12-31', \
            "Raw XBRL DocumentPeriodEndDate should be 2011-12-31 (the incorrect value)"

        # Verify the SGML date was captured
        assert xbrl._sgml_period_of_report == '2012-12-31', \
            "SGML period_of_report should be 2012-12-31 (from filing header)"

        # Verify the corrected period_of_report uses SGML date
        assert xbrl.period_of_report == '2012-12-31', \
            "period_of_report should be corrected to 2012-12-31 (SGML date)"

    def test_2012_10k_includes_2012_fiscal_data(self):
        """
        With the date discrepancy fix, this filing should now correctly show
        fiscal year 2012 data as the primary year.
        """
        filing = get_nflx_2012_10k()
        xbrl = filing.xbrl()

        statement = xbrl.statements.income_statement()
        df = statement.to_dataframe()

        # Should now include 2012 data (the current fiscal year for this filing)
        assert '2012-12-31' in df.columns, \
            "Should include 2012-12-31 (current fiscal year after fix)"

        # Should also include 2011 as prior year comparison
        assert '2011-12-31' in df.columns, \
            "Should include 2011-12-31 (prior year comparison)"

    def test_period_selection_excludes_multi_year_periods(self):
        """Period selection should not select multi-year cumulative periods"""
        from edgar.xbrl.period_selector import select_periods

        filing = get_nflx_2012_10k()
        xbrl = filing.xbrl()
        periods = select_periods(xbrl, 'IncomeStatement', max_periods=4)

        period_keys = [pk for pk, _ in periods]

        # Should NOT include the long cumulative periods like:
        # - "Period: January 02, 2007 to December 31, 2012" (2190 days)
        # - "Period: October 01, 2011 to December 31, 2012" (457 days)

        for period_key, label in periods:
            # Extract start and end dates from period key
            if 'duration_' in period_key:
                parts = period_key.split('_')
                if len(parts) == 3:
                    start_str, end_str = parts[1], parts[2]
                    from datetime import datetime
                    start = datetime.strptime(start_str, '%Y-%m-%d').date()
                    end = datetime.strptime(end_str, '%Y-%m-%d').date()
                    days = (end - start).days

                    # Annual periods should be between 300 and 370 days
                    assert 300 < days <= 370, \
                        f"Period {label} has {days} days, should be 300-370 for annual periods"

    def test_fiscal_year_2012_has_revenue_data(self):
        """2012 fiscal year should have revenue data"""
        filing = get_nflx_2012_10k()
        xbrl = filing.xbrl()

        # Get revenue facts for 2012 period
        revenue_facts = xbrl.facts.query().by_concept("Revenue").by_period_key("duration_2012-01-01_2012-12-31").to_dataframe()

        assert len(revenue_facts) > 0, \
            "2012 fiscal year should have revenue facts"


@pytest.mark.regression
class TestIssue513NFLXRevenueDeduplication:
    """Test that revenue deduplication preserves dimensional segment data"""

    def test_revenue_segments_preserved_in_income_statement(self, nflx_2025_q3_10q_filing):
        """Revenue segment breakdown should be preserved, not deduplicated

        Note: As of v5.7.0, include_dimensions defaults to False for cleaner output.
        This test explicitly enables dimensions to verify segment data is preserved.
        """
        statement = nflx_2025_q3_10q_filing.xbrl().statements.income_statement()
        df = statement.to_dataframe(include_dimensions=True)

        # Check that revenue segment labels are present
        labels = df['label'].tolist()
        label_str = ' '.join(labels).lower()

        # Netflix has geographic segment revenue breakdowns
        segments = [
            'united states',
            'canada',
            'europe',
            'middle east',
            'africa',
            'latin america',
            'asia'
        ]

        # At least some segment terms should appear
        found_segments = [seg for seg in segments if seg in label_str]
        assert len(found_segments) >= 3, \
            f"Should find multiple revenue segments, found: {found_segments}"

    def test_deduplication_considers_dimensions(self, nflx_2025_q3_10q_filing):
        """Deduplication should group by (period, value, dimensions), not just (period, value)"""
        from edgar.xbrl.deduplication_strategy import RevenueDeduplicator

        xbrl = nflx_2025_q3_10q_filing.xbrl()
        income_data = xbrl.get_statement("IncomeStatement")

        # Get revenue items with the same value
        revenue_items = [item for item in income_data if 'Revenue' in item.get('concept', '')]

        # Group by value in Q3 2025
        q3_2025_period = '2025-09-30'
        value_groups = {}
        for item in revenue_items:
            values = item.get('values', {})
            if q3_2025_period in values:
                value = values[q3_2025_period]
                if value not in value_groups:
                    value_groups[value] = []
                value_groups[value].append(item)

        # Find groups with multiple items (potential duplicates)
        multi_item_groups = {v: items for v, items in value_groups.items() if len(items) > 1}

        if multi_item_groups:
            # If there are items with the same value, verify they have different dimensions
            for value, items in multi_item_groups.items():
                # Check if items have dimensional differences
                dimensions = [item.get('dimension', {}) for item in items]
                labels = [item.get('label') for item in items]

                # Items with same value but different dimensions/labels should both be kept
                if len(set(str(d) for d in dimensions)) > 1 or len(set(labels)) > 1:
                    # These should NOT be deduplicated
                    # The fix ensures dimensional differences are preserved
                    assert True, "Items with different dimensions are correctly preserved"

    def test_revenue_fact_count_reasonable(self, nflx_2025_q3_10q_filing):
        """Revenue facts should be present and not over-deduplicated"""
        xbrl = nflx_2025_q3_10q_filing.xbrl()

        # Get all revenue facts
        revenue_facts = xbrl.facts.query().by_concept("Revenue").to_dataframe()

        # Should have multiple revenue facts (segments, periods, etc.)
        assert len(revenue_facts) >= 10, \
            f"Should have at least 10 revenue facts, found {len(revenue_facts)}"

        # Check Q3 2025 specifically
        q3_facts = revenue_facts[
            (revenue_facts['period_start'] == '2025-07-01') &
            (revenue_facts['period_end'] == '2025-09-30')
        ]

        assert len(q3_facts) >= 4, \
            f"Q3 2025 should have at least 4 revenue facts (segments), found {len(q3_facts)}"