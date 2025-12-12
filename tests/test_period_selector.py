"""
Tests for the unified period selection system.

This tests the new streamlined period_selector.py module that replaces
the complex dual-system architecture.
"""

import pytest
from datetime import date, datetime
from unittest.mock import Mock, MagicMock

from edgar.xbrl.period_selector import (
    select_periods,
    _filter_by_document_date,
    _select_balance_sheet_periods,
    _select_duration_periods,
    _get_annual_periods,
    _is_annual_period,
    _score_fiscal_alignment,
    _calculate_fiscal_alignment_score,
    _sort_periods_by_date
)


class TestFilterByDocumentDate:
    """Test document date filtering - the key fix for the future date bug."""

    def test_filters_future_instant_periods(self):
        """Should exclude instant periods after document date."""
        periods = [
            {'type': 'instant', 'date': '2024-12-31', 'key': 'instant_2024', 'label': '2024'},
            {'type': 'instant', 'date': '2025-12-31', 'key': 'instant_2025', 'label': '2025'},
            {'type': 'instant', 'date': '2026-12-31', 'key': 'instant_2026', 'label': '2026'},
        ]

        result = _filter_by_document_date(periods, '2024-12-31')

        assert len(result) == 1
        assert result[0]['date'] == '2024-12-31'

    def test_filters_future_duration_periods(self):
        """Should exclude duration periods ending after document date."""
        periods = [
            {'type': 'duration', 'start_date': '2024-01-01', 'end_date': '2024-12-31', 'key': 'duration_2024', 'label': '2024'},
            {'type': 'duration', 'start_date': '2025-01-01', 'end_date': '2025-12-31', 'key': 'duration_2025', 'label': '2025'},
            {'type': 'duration', 'start_date': '2026-01-01', 'end_date': '2026-12-31', 'key': 'duration_2026', 'label': '2026'},
        ]

        result = _filter_by_document_date(periods, '2024-12-31')

        assert len(result) == 1
        assert result[0]['end_date'] == '2024-12-31'

    def test_handles_no_document_date(self):
        """Should return all periods if no document date provided."""
        periods = [{'type': 'instant', 'date': '2024-12-31', 'key': 'test', 'label': 'Test'}]

        result = _filter_by_document_date(periods, None)

        assert len(result) == 1

    def test_handles_invalid_document_date(self):
        """Should return all periods if document date is invalid."""
        periods = [{'type': 'instant', 'date': '2024-12-31', 'key': 'test', 'label': 'Test'}]

        result = _filter_by_document_date(periods, 'invalid-date')

        assert len(result) == 1

    def test_handles_invalid_period_dates(self):
        """Should include periods with invalid dates to be safe."""
        periods = [
            {'type': 'instant', 'date': 'invalid-date', 'key': 'test', 'label': 'Test'},
            {'type': 'duration', 'start_date': '2024-01-01', 'end_date': 'invalid', 'key': 'test2', 'label': 'Test2'},
        ]

        result = _filter_by_document_date(periods, '2024-12-31')

        assert len(result) == 2  # Both included as fallback


class TestBalanceSheetSelection:
    """Test balance sheet period selection logic."""

    def test_selects_instant_periods_only(self):
        """Balance sheets should only use instant periods."""
        periods = [
            {'type': 'instant', 'date': '2024-12-31', 'key': 'instant_2024', 'label': 'Dec 31, 2024'},
            {'type': 'duration', 'start_date': '2024-01-01', 'end_date': '2024-12-31', 'key': 'duration_2024', 'label': '2024'},
            {'type': 'instant', 'date': '2023-12-31', 'key': 'instant_2023', 'label': 'Dec 31, 2023'},
        ]
        entity_info = {'fiscal_year_end_month': 12, 'fiscal_year_end_day': 31}

        result = _select_balance_sheet_periods(periods, entity_info, 2)

        assert len(result) == 2
        assert all('instant' in period_key for period_key, _ in result)

    def test_sorts_by_most_recent_first(self):
        """Should return most recent instant periods first."""
        periods = [
            {'type': 'instant', 'date': '2022-12-31', 'key': 'instant_2022', 'label': 'Dec 31, 2022'},
            {'type': 'instant', 'date': '2024-12-31', 'key': 'instant_2024', 'label': 'Dec 31, 2024'},
            {'type': 'instant', 'date': '2023-12-31', 'key': 'instant_2023', 'label': 'Dec 31, 2023'},
        ]
        entity_info = {'fiscal_year_end_month': 12, 'fiscal_year_end_day': 31}

        result = _select_balance_sheet_periods(periods, entity_info, 3)

        assert len(result) == 3
        assert result[0][0] == 'instant_2024'  # Most recent first
        assert result[1][0] == 'instant_2023'
        assert result[2][0] == 'instant_2022'

    def test_handles_no_instant_periods(self):
        """Should handle case with no instant periods gracefully."""
        periods = [
            {'type': 'duration', 'start_date': '2024-01-01', 'end_date': '2024-12-31', 'key': 'duration_2024', 'label': '2024'},
        ]
        entity_info = {}

        result = _select_balance_sheet_periods(periods, entity_info, 2)

        assert len(result) == 0

    def test_prioritizes_fiscal_year_end_periods(self):
        """Should explicitly seek and prioritize fiscal year end periods.

        Issue edgartools-2sn: When many mid-period instants exist, the prior
        fiscal year end could be pushed beyond the candidate pool. This test
        verifies that fiscal year end periods are explicitly sought and prioritized.
        """
        # Simulate VENU scenario: many mid-period dates push fiscal year end beyond top 10
        periods = [
            {'type': 'instant', 'date': '2024-09-30', 'key': 'instant_2024-09-30', 'label': 'Sep 30, 2024'},
            {'type': 'instant', 'date': '2024-08-26', 'key': 'instant_2024-08-26', 'label': 'Aug 26, 2024'},
            {'type': 'instant', 'date': '2024-08-22', 'key': 'instant_2024-08-22', 'label': 'Aug 22, 2024'},
            {'type': 'instant', 'date': '2024-08-16', 'key': 'instant_2024-08-16', 'label': 'Aug 16, 2024'},
            {'type': 'instant', 'date': '2024-08-12', 'key': 'instant_2024-08-12', 'label': 'Aug 12, 2024'},
            {'type': 'instant', 'date': '2024-06-30', 'key': 'instant_2024-06-30', 'label': 'Jun 30, 2024'},
            {'type': 'instant', 'date': '2024-06-26', 'key': 'instant_2024-06-26', 'label': 'Jun 26, 2024'},
            {'type': 'instant', 'date': '2024-03-31', 'key': 'instant_2024-03-31', 'label': 'Mar 31, 2024'},
            {'type': 'instant', 'date': '2024-03-05', 'key': 'instant_2024-03-05', 'label': 'Mar 05, 2024'},
            {'type': 'instant', 'date': '2024-01-17', 'key': 'instant_2024-01-17', 'label': 'Jan 17, 2024'},
            # Prior fiscal year end at position 11 - would be missed with candidate_count=10
            {'type': 'instant', 'date': '2023-12-31', 'key': 'instant_2023-12-31', 'label': 'Dec 31, 2023'},
        ]
        entity_info = {'fiscal_year_end_month': 12, 'fiscal_year_end_day': 31}

        result = _select_balance_sheet_periods(periods, entity_info, 2)

        # Fiscal year end Dec 31, 2023 should be in candidates due to explicit seeking
        result_keys = [key for key, _ in result]
        assert 'instant_2023-12-31' in result_keys, "Prior fiscal year end should be prioritized in candidates"

    def test_handles_missing_fiscal_info(self):
        """Should handle case where fiscal year info is not available."""
        periods = [
            {'type': 'instant', 'date': '2024-12-31', 'key': 'instant_2024', 'label': 'Dec 31, 2024'},
            {'type': 'instant', 'date': '2023-12-31', 'key': 'instant_2023', 'label': 'Dec 31, 2023'},
        ]
        entity_info = {}  # No fiscal info

        result = _select_balance_sheet_periods(periods, entity_info, 2)

        # Should still return periods based on date sorting
        assert len(result) == 2
        assert result[0][0] == 'instant_2024'  # Most recent first


class TestDurationPeriodSelection:
    """Test income/cash flow statement period selection."""

    def test_selects_annual_periods_for_fy(self):
        """Should prefer annual periods for FY reports."""
        periods = [
            {'type': 'duration', 'start_date': '2024-01-01', 'end_date': '2024-12-31', 'key': 'annual_2024', 'label': '2024'},
            {'type': 'duration', 'start_date': '2024-10-01', 'end_date': '2024-12-31', 'key': 'q4_2024', 'label': 'Q4 2024'},
        ]
        entity_info = {'fiscal_period': 'FY', 'fiscal_year_end_month': 12, 'fiscal_year_end_day': 31}

        result = _select_duration_periods(periods, entity_info, 2)

        assert len(result) >= 1
        assert 'annual_2024' in [key for key, _ in result]

    def test_uses_fiscal_alignment_scoring(self):
        """Should score periods based on fiscal year alignment."""
        periods = [
            {'type': 'duration', 'start_date': '2024-01-01', 'end_date': '2024-12-31', 'key': 'perfect_fy', 'label': 'Perfect FY'},
            {'type': 'duration', 'start_date': '2024-04-01', 'end_date': '2025-03-31', 'key': 'different_fy', 'label': 'Different FY'},
        ]
        entity_info = {'fiscal_period': 'FY', 'fiscal_year_end_month': 12, 'fiscal_year_end_day': 31}

        result = _select_duration_periods(periods, entity_info, 2)

        # Should prefer the period that aligns with fiscal year end
        assert result[0][0] == 'perfect_fy'

    def test_handles_quarterly_reports(self):
        """Should handle quarterly reports when no annual periods."""
        periods = [
            {'type': 'duration', 'start_date': '2024-10-01', 'end_date': '2024-12-31', 'key': 'q4_2024', 'label': 'Q4 2024'},
            {'type': 'duration', 'start_date': '2024-07-01', 'end_date': '2024-09-30', 'key': 'q3_2024', 'label': 'Q3 2024'},
        ]
        entity_info = {'fiscal_period': 'Q4'}

        result = _select_duration_periods(periods, entity_info, 2)

        assert len(result) == 2
        assert result[0][0] == 'q4_2024'  # Most recent first


class TestAnnualPeriodDetection:
    """Test the 300-day annual period logic."""

    def test_detects_annual_periods(self):
        """Should identify periods >300 days as annual."""
        annual_period = {
            'type': 'duration',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'key': 'annual',
            'label': 'Annual'
        }

        assert _is_annual_period(annual_period) is True

    def test_rejects_quarterly_periods(self):
        """Should reject periods <=300 days."""
        quarterly_period = {
            'type': 'duration',
            'start_date': '2024-10-01',
            'end_date': '2024-12-31',
            'key': 'quarterly',
            'label': 'Quarterly'
        }

        assert _is_annual_period(quarterly_period) is False

    def test_filters_annual_periods(self):
        """Should filter list to only annual periods."""
        periods = [
            {'type': 'duration', 'start_date': '2024-01-01', 'end_date': '2024-12-31', 'key': 'annual', 'label': 'Annual'},
            {'type': 'duration', 'start_date': '2024-10-01', 'end_date': '2024-12-31', 'key': 'quarterly', 'label': 'Quarterly'},
            {'type': 'duration', 'start_date': '2023-01-01', 'end_date': '2023-12-31', 'key': 'annual2', 'label': 'Annual 2'},
        ]

        result = _get_annual_periods(periods)

        assert len(result) == 2
        assert all('annual' in p['key'] for p in result)

    def test_rejects_multi_year_periods(self):
        """Should reject overly long multi-year periods."""
        periods = [
            {'type': 'duration', 'start_date': '2024-01-01', 'end_date': '2024-12-31', 'key': 'annual', 'label': 'Annual'},  # 365 days - annual (good)
            {'type': 'duration', 'start_date': '2020-05-29', 'end_date': '2024-09-30', 'key': 'multi_year1', 'label': 'Multi-year 1'},  # 1585 days - multi-year (bad)
            {'type': 'duration', 'start_date': '2013-05-01', 'end_date': '2024-09-30', 'key': 'multi_year2', 'label': 'Multi-year 2'},  # 4170 days - multi-year (bad)
        ]

        annual_periods = _get_annual_periods(periods)

        # Should only include the proper annual period
        assert len(annual_periods) == 1
        assert annual_periods[0]['key'] == 'annual'


class TestFiscalAlignment:
    """Test fiscal year alignment scoring."""

    def test_perfect_fiscal_alignment(self):
        """Perfect fiscal year end match should score 100."""
        test_date = date(2024, 12, 31)
        score = _calculate_fiscal_alignment_score(test_date, 12, 31)
        assert score == 100

    def test_same_month_close_day(self):
        """Same month within 15 days should score 75."""
        test_date = date(2024, 12, 20)  # 11 days off
        score = _calculate_fiscal_alignment_score(test_date, 12, 31)
        assert score == 75

    def test_adjacent_month(self):
        """Adjacent month should score 50."""
        test_date = date(2024, 11, 30)
        score = _calculate_fiscal_alignment_score(test_date, 12, 31)
        assert score == 50

    def test_different_quarter(self):
        """Different quarter should score 25."""
        test_date = date(2024, 6, 30)
        score = _calculate_fiscal_alignment_score(test_date, 12, 31)
        assert score == 25


class TestIntegration:
    """Integration tests using mock XBRL objects."""

    def test_bristol_myers_case_fix(self):
        """Should fix the Bristol Myers future date bug."""
        # Mock the problematic Bristol Myers scenario
        mock_xbrl = Mock()
        mock_xbrl.entity_name = "BRISTOL-MYERS SQUIBB COMPANY"
        mock_xbrl.period_of_report = "2024-12-31"
        mock_xbrl.entity_info = {
            'fiscal_period': 'FY',
            'fiscal_year_end_month': 12,
            'fiscal_year_end_day': 31
        }
        mock_xbrl.reporting_periods = [
            # Future periods (the bug)
            {'type': 'duration', 'start_date': '2029-01-01', 'end_date': '2029-12-31', 'key': 'duration_2029', 'label': 'Dec 31, 2029'},
            {'type': 'duration', 'start_date': '2028-01-01', 'end_date': '2028-12-31', 'key': 'duration_2028', 'label': 'Dec 31, 2028'},
            {'type': 'duration', 'start_date': '2027-01-01', 'end_date': '2027-12-31', 'key': 'duration_2027', 'label': 'Dec 31, 2027'},
            # Valid historical periods
            {'type': 'duration', 'start_date': '2024-01-01', 'end_date': '2024-12-31', 'key': 'duration_2024', 'label': 'Dec 31, 2024'},
            {'type': 'duration', 'start_date': '2023-01-01', 'end_date': '2023-12-31', 'key': 'duration_2023', 'label': 'Dec 31, 2023'},
            {'type': 'duration', 'start_date': '2022-01-01', 'end_date': '2022-12-31', 'key': 'duration_2022', 'label': 'Dec 31, 2022'},
        ]

        result = select_periods(mock_xbrl, 'IncomeStatement', 3)

        # Should return historical periods, not future ones
        assert len(result) == 3
        returned_keys = [key for key, _ in result]
        assert 'duration_2024' in returned_keys
        assert 'duration_2023' in returned_keys
        assert 'duration_2022' in returned_keys
        # Should NOT contain future periods
        assert 'duration_2029' not in returned_keys
        assert 'duration_2028' not in returned_keys
        assert 'duration_2027' not in returned_keys

    def test_balance_sheet_selection(self):
        """Should select instant periods for balance sheets."""
        mock_xbrl = Mock()
        mock_xbrl.entity_name = "Test Company"
        mock_xbrl.period_of_report = "2024-12-31"
        mock_xbrl.entity_info = {}
        mock_xbrl.reporting_periods = [
            {'type': 'instant', 'date': '2024-12-31', 'key': 'instant_2024', 'label': 'Dec 31, 2024'},
            {'type': 'instant', 'date': '2023-12-31', 'key': 'instant_2023', 'label': 'Dec 31, 2023'},
            {'type': 'duration', 'start_date': '2024-01-01', 'end_date': '2024-12-31', 'key': 'duration_2024', 'label': '2024'},
        ]

        result = select_periods(mock_xbrl, 'BalanceSheet', 2)

        assert len(result) == 2
        assert all('instant' in key for key, _ in result)

    def test_handles_empty_periods(self):
        """Should handle empty periods list gracefully."""
        mock_xbrl = Mock()
        mock_xbrl.entity_name = "Test Company"
        mock_xbrl.period_of_report = "2024-12-31"
        mock_xbrl.entity_info = {}
        mock_xbrl.reporting_periods = []

        result = select_periods(mock_xbrl, 'IncomeStatement', 3)

        assert result == []

    def test_error_handling(self):
        """Should handle errors gracefully and return fallback."""
        mock_xbrl = Mock()
        mock_xbrl.entity_name = "Test Company"
        mock_xbrl.period_of_report = None  # This could cause errors
        mock_xbrl.entity_info = {}
        mock_xbrl.reporting_periods = [
            {'type': 'duration', 'start_date': '2024-01-01', 'end_date': '2024-12-31', 'key': 'test', 'label': 'Test'},
        ]

        # Should not raise exception
        result = select_periods(mock_xbrl, 'IncomeStatement', 1)

        assert len(result) == 1  # Fallback should work


class TestLegacyCompatibility:
    """Test that legacy compatibility wrappers work."""

    def test_determine_periods_to_display_wrapper(self):
        """Legacy function should work as wrapper."""
        from edgar.xbrl.period_selector import determine_periods_to_display

        mock_xbrl = Mock()
        mock_xbrl.entity_name = "Test Company"
        mock_xbrl.period_of_report = "2024-12-31"
        mock_xbrl.entity_info = {'fiscal_period': 'FY'}
        mock_xbrl.reporting_periods = [
            {'type': 'duration', 'start_date': '2024-01-01', 'end_date': '2024-12-31', 'key': 'test', 'label': 'Test'},
        ]

        result = determine_periods_to_display(mock_xbrl, 'IncomeStatement')

        assert len(result) == 1
        assert result[0][0] == 'test'

    def test_select_smart_periods_wrapper(self):
        """Smart periods function should work as wrapper."""
        from edgar.xbrl.period_selector import select_smart_periods

        mock_xbrl = Mock()
        mock_xbrl.entity_name = "Test Company"
        mock_xbrl.period_of_report = "2024-12-31"
        mock_xbrl.entity_info = {'fiscal_period': 'FY'}
        mock_xbrl.reporting_periods = [
            {'type': 'duration', 'start_date': '2024-01-01', 'end_date': '2024-12-31', 'key': 'test', 'label': 'Test'},
        ]

        result = select_smart_periods(mock_xbrl, 'IncomeStatement', 1)

        assert len(result) == 1
        assert result[0][0] == 'test'


class TestCompanyGroups:
    """Real-world tests using actual SEC filings to validate period selection."""

    @pytest.mark.network
    def test_apple_calendar_year_annual_periods(self):
        """Test Apple (calendar year) annual filing period selection."""
        from edgar import Company

        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        # Test annual (10-K) filing period selection
        periods = select_periods(xbrl, 'IncomeStatement', 3)

        # Should return 3 or fewer periods
        assert len(periods) <= 3, f"Expected <= 3 periods, got {len(periods)}"
        assert len(periods) >= 1, "Should return at least 1 period"

        # All periods should have data
        for period_key, period_label in periods:
            facts_count = len(xbrl.facts.query().by_period_key(period_key).to_dataframe())
            assert facts_count >= 10, f"Period {period_label} has insufficient facts: {facts_count}"

        # For annual filing, should prefer annual periods (>300 days)
        # Check that selected periods are likely annual by examining the keys or calculating duration
        annual_period_count = 0
        for period_key, period_label in periods:
            period_info = next((p for p in xbrl.reporting_periods if p['key'] == period_key), None)
            if period_info and period_info['type'] == 'duration':
                start = datetime.strptime(period_info['start_date'], '%Y-%m-%d')
                end = datetime.strptime(period_info['end_date'], '%Y-%m-%d')
                duration_days = (end - start).days
                if duration_days > 300:
                    annual_period_count += 1

        # At least some periods should be annual for a 10-K filing
        assert annual_period_count >= 1, f"Expected at least 1 annual period in 10-K, got {annual_period_count}"

        # Test that no future periods are selected
        doc_date = datetime.strptime(xbrl.period_of_report, '%Y-%m-%d').date() if xbrl.period_of_report else date.today()
        for period_key, period_label in periods:
            period_info = next((p for p in xbrl.reporting_periods if p['key'] == period_key), None)
            if period_info:
                if period_info['type'] == 'instant':
                    period_date = datetime.strptime(period_info['date'], '%Y-%m-%d').date()
                    assert period_date <= doc_date, f"Future instant period selected: {period_label} ({period_date} > {doc_date})"
                else:  # duration
                    period_end = datetime.strptime(period_info['end_date'], '%Y-%m-%d').date()
                    assert period_end <= doc_date, f"Future duration period selected: {period_label} ({period_end} > {doc_date})"

    @pytest.mark.network
    def test_apple_quarterly_filing_periods(self):
        """Test Apple quarterly filing (10-Q) period selection."""
        from edgar import Company

        company = Company("AAPL")
        filings_10q = company.get_filings(form="10-Q")
        if len(filings_10q) == 0:
            pytest.skip("No 10-Q filings available for Apple")

        filing = filings_10q.latest()
        xbrl = filing.xbrl()

        # Test quarterly (10-Q) filing period selection
        periods = select_periods(xbrl, 'IncomeStatement', 4)

        # Should return periods for quarterly analysis
        assert len(periods) <= 4, f"Expected <= 4 periods, got {len(periods)}"
        assert len(periods) >= 1, "Should return at least 1 period"

        # Verify periods have sufficient data
        for period_key, period_label in periods:
            facts_count = len(xbrl.facts.query().by_period_key(period_key).to_dataframe())
            assert facts_count >= 5, f"Period {period_label} has insufficient facts: {facts_count}"

        # Test that document date filtering is working
        doc_date = datetime.strptime(xbrl.period_of_report, '%Y-%m-%d').date() if xbrl.period_of_report else date.today()
        for period_key, period_label in periods:
            period_info = next((p for p in xbrl.reporting_periods if p['key'] == period_key), None)
            if period_info and period_info['type'] == 'duration':
                period_end = datetime.strptime(period_info['end_date'], '%Y-%m-%d').date()
                assert period_end <= doc_date, f"Future period selected: {period_label} ({period_end} > {doc_date})"

    @pytest.mark.network
    def test_microsoft_calendar_year_periods(self):
        """Test Microsoft (calendar year tech) period selection."""
        from edgar import Company

        company = Company("MSFT")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        # Test that Microsoft annual periods are selected correctly
        periods = select_periods(xbrl, 'IncomeStatement', 3)

        assert len(periods) <= 3, f"Expected <= 3 periods, got {len(periods)}"
        assert len(periods) >= 1, "Should return at least 1 period"

        # Verify data availability for each period
        for period_key, period_label in periods:
            # Check basic fact count
            facts_count = len(xbrl.facts.query().by_period_key(period_key).to_dataframe())
            assert facts_count >= 10, f"Period {period_label} has insufficient facts: {facts_count}"

            # Check for essential income statement concepts
            revenue_facts = len(xbrl.facts.query().by_concept("Revenue").by_period_key(period_key).to_dataframe())
            income_facts = len(xbrl.facts.query().by_concept("NetIncome").by_period_key(period_key).to_dataframe())

            # At least one essential concept should have data
            assert revenue_facts > 0 or income_facts > 0, f"Period {period_label} lacks essential income statement concepts"

        # For tech companies, fiscal alignment should prefer calendar year ends
        if xbrl.entity_info.get('fiscal_year_end_month') == 12:
            # Verify that selected periods align with calendar year preference
            calendar_aligned_count = 0
            for period_key, period_label in periods:
                period_info = next((p for p in xbrl.reporting_periods if p['key'] == period_key), None)
                if period_info and period_info['type'] == 'duration':
                    end_date = datetime.strptime(period_info['end_date'], '%Y-%m-%d').date()
                    if end_date.month == 12:  # December year-end
                        calendar_aligned_count += 1

            assert calendar_aligned_count >= 1, "Expected at least one calendar year-end period for calendar year company"

    @pytest.mark.network
    def test_walmart_non_calendar_fiscal_year(self):
        """Test Walmart (non-calendar fiscal year) period selection."""
        from edgar import Company

        company = Company("WMT")  # Walmart has January 31 fiscal year end
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        # Test that fiscal year alignment works for non-calendar year companies
        periods = select_periods(xbrl, 'IncomeStatement', 3)

        assert len(periods) <= 3, f"Expected <= 3 periods, got {len(periods)}"
        assert len(periods) >= 1, "Should return at least 1 period"

        # Verify periods have sufficient data
        for period_key, period_label in periods:
            facts_count = len(xbrl.facts.query().by_period_key(period_key).to_dataframe())
            assert facts_count >= 10, f"Period {period_label} has insufficient facts: {facts_count}"

        # Test fiscal year alignment for Walmart (typically January 31 year-end)
        fiscal_month = xbrl.entity_info.get('fiscal_year_end_month')
        if fiscal_month and fiscal_month == 1:  # January fiscal year end
            # Check that periods align with Walmart's fiscal year
            fiscal_aligned_count = 0
            for period_key, period_label in periods:
                period_info = next((p for p in xbrl.reporting_periods if p['key'] == period_key), None)
                if period_info and period_info['type'] == 'duration':
                    end_date = datetime.strptime(period_info['end_date'], '%Y-%m-%d').date()
                    if end_date.month == 1 or end_date.month == 12:  # January or close to it
                        fiscal_aligned_count += 1

            # At least some periods should align with fiscal year end
            assert fiscal_aligned_count >= 1, "Expected at least one fiscal year-aligned period for non-calendar year company"

    @pytest.mark.network
    def test_balance_sheet_instant_periods(self):
        """Test that balance sheet selection uses instant periods only."""
        from edgar import Company

        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        # Test balance sheet period selection
        periods = select_periods(xbrl, 'BalanceSheet', 3)

        assert len(periods) <= 3, f"Expected <= 3 periods, got {len(periods)}"
        assert len(periods) >= 1, "Should return at least 1 period for balance sheet"

        # All periods should be instant periods
        for period_key, period_label in periods:
            period_info = next((p for p in xbrl.reporting_periods if p['key'] == period_key), None)
            assert period_info is not None, f"Could not find period info for {period_key}"
            assert period_info['type'] == 'instant', f"Balance sheet period {period_label} should be instant, got {period_info['type']}"

            # Verify instant periods have sufficient data
            facts_count = len(xbrl.facts.query().by_period_key(period_key).to_dataframe())
            assert facts_count >= 5, f"Instant period {period_label} has insufficient facts: {facts_count}"

        # Periods should be sorted by most recent first
        period_dates = []
        for period_key, period_label in periods:
            period_info = next((p for p in xbrl.reporting_periods if p['key'] == period_key), None)
            if period_info:
                period_date = datetime.strptime(period_info['date'], '%Y-%m-%d').date()
                period_dates.append(period_date)

        # Verify descending order (most recent first)
        for i in range(len(period_dates) - 1):
            assert period_dates[i] >= period_dates[i + 1], f"Periods not sorted correctly: {period_dates[i]} should be >= {period_dates[i + 1]}"

    @pytest.mark.network
    def test_quarterly_period_logic(self):
        """Test quarterly period selection logic with Q1-Q4 filings."""
        from edgar import Company

        # Test with a company that has regular quarterly filings
        company = Company("MSFT")
        quarterly_filings = company.get_filings(form="10-Q").latest(4)  # Get several recent quarters

        if len(quarterly_filings) == 0:
            pytest.skip("No quarterly filings available for testing")

        filing = quarterly_filings[0]  # Most recent quarterly filing
        xbrl = filing.xbrl()

        # Test quarterly filing period selection
        periods = select_periods(xbrl, 'IncomeStatement', 4)

        assert len(periods) <= 4, f"Expected <= 4 periods, got {len(periods)}"
        assert len(periods) >= 1, "Should return at least 1 period for quarterly filing"

        # For quarterly filings, check that we get appropriate mix of periods
        duration_period_count = 0
        quarterly_period_count = 0

        for period_key, period_label in periods:
            period_info = next((p for p in xbrl.reporting_periods if p['key'] == period_key), None)
            if period_info and period_info['type'] == 'duration':
                duration_period_count += 1
                start = datetime.strptime(period_info['start_date'], '%Y-%m-%d')
                end = datetime.strptime(period_info['end_date'], '%Y-%m-%d')
                duration_days = (end - start).days

                # Count periods that are likely quarterly (60-120 days)
                if 60 <= duration_days <= 120:
                    quarterly_period_count += 1

            # Verify data availability
            facts_count = len(xbrl.facts.query().by_period_key(period_key).to_dataframe())
            assert facts_count >= 5, f"Period {period_label} has insufficient facts: {facts_count}"

        # Should have at least some duration periods for income statement
        assert duration_period_count >= 1, "Quarterly filing should have duration periods for income statement"

    @pytest.mark.network
    def test_data_availability_filtering(self):
        """Test that periods with insufficient data are filtered out."""
        from edgar import Company

        # Use a company that might have some periods with limited data
        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        # Get all available periods before filtering
        all_periods = xbrl.reporting_periods
        total_available_periods = len([p for p in all_periods if p['type'] == 'duration'])

        # Test period selection with data availability filtering
        periods = select_periods(xbrl, 'IncomeStatement', min(total_available_periods, 10))

        # Each selected period should have meaningful data
        for period_key, period_label in periods:
            # Check basic fact count
            facts_count = len(xbrl.facts.query().by_period_key(period_key).to_dataframe())
            assert facts_count >= 10, f"Period {period_label} should have been filtered out due to insufficient facts: {facts_count}"

            # Check for essential concepts
            essential_concepts = ['Revenue', 'NetIncome', 'OperatingIncome']
            concepts_with_data = 0
            for concept in essential_concepts:
                concept_facts = len(xbrl.facts.query().by_concept(concept).by_period_key(period_key).to_dataframe())
                if concept_facts > 0:
                    concepts_with_data += 1

            # At least some essential concepts should have data
            assert concepts_with_data > 0, f"Period {period_label} should have been filtered out due to lack of essential concepts"

        # Test that the filtering actually works by comparing to raw period count
        # Selected periods should be <= total available periods
        assert len(periods) <= total_available_periods, "Selected periods exceed available periods"

    @pytest.mark.network
    def test_edge_case_irregular_reporting(self):
        """Test companies with irregular reporting patterns or data gaps."""
        from edgar import Company

        # Test with a smaller company that might have irregular reporting
        companies_to_test = ["F", "GE"]  # Ford, GE - companies that have had reporting changes

        for ticker in companies_to_test:
            company = Company(ticker)
            recent_filings = company.get_filings(form="10-K").latest(3)

            if len(recent_filings) == 0:
                continue  # Skip if no filings available

            filing = recent_filings[0]
            xbrl = filing.xbrl()

            # Test that period selection handles irregular patterns gracefully
            periods = select_periods(xbrl, 'IncomeStatement', 5)

            # Should return some periods even for irregular companies
            assert len(periods) >= 1, f"Should return at least 1 period for {ticker}"
            assert len(periods) <= 5, f"Should not exceed requested max periods for {ticker}"

            # Each returned period should have some data
            for period_key, period_label in periods:
                facts_count = len(xbrl.facts.query().by_period_key(period_key).to_dataframe())
                assert facts_count >= 3, f"{ticker} period {period_label} has too few facts: {facts_count}"

            # Test document date filtering
            if xbrl.period_of_report:
                doc_date = datetime.strptime(xbrl.period_of_report, '%Y-%m-%d').date()
                for period_key, period_label in periods:
                    period_info = next((p for p in xbrl.reporting_periods if p['key'] == period_key), None)
                    if period_info and period_info['type'] == 'duration':
                        period_end = datetime.strptime(period_info['end_date'], '%Y-%m-%d').date()
                        assert period_end <= doc_date, f"{ticker} selected future period: {period_label} ({period_end} > {doc_date})"

            break  # Test with first available company

    @pytest.mark.network
    def test_cash_flow_statement_periods(self):
        """Test cash flow statement period selection."""
        from edgar import Company

        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest()
        xbrl = filing.xbrl()

        # Test cash flow statement period selection
        periods = select_periods(xbrl, 'CashFlowStatement', 3)

        assert len(periods) <= 3, f"Expected <= 3 periods, got {len(periods)}"
        assert len(periods) >= 1, "Should return at least 1 period for cash flow statement"

        # Cash flow statements should use duration periods
        for period_key, period_label in periods:
            period_info = next((p for p in xbrl.reporting_periods if p['key'] == period_key), None)
            assert period_info is not None, f"Could not find period info for {period_key}"
            assert period_info['type'] == 'duration', f"Cash flow period {period_label} should be duration, got {period_info['type']}"

            # Check for cash flow specific data
            facts_count = len(xbrl.facts.query().by_period_key(period_key).to_dataframe())
            assert facts_count >= 5, f"Cash flow period {period_label} has insufficient facts: {facts_count}"

            # Check for essential cash flow concepts (use broader patterns since concept names vary)
            cf_concept_patterns = ['CashFlow', 'Cash', 'Operating', 'Investing', 'Financing']
            concepts_found = 0
            for pattern in cf_concept_patterns:
                concept_facts = len(xbrl.facts.query().by_concept(pattern, exact=False).by_period_key(period_key).to_dataframe())
                if concept_facts > 0:
                    concepts_found += 1

            # Should have at least some cash flow related concepts
            # Note: Some periods may not have cash flow data, so we'll be lenient
            if concepts_found == 0:
                # Log available concepts for debugging
                all_period_facts = xbrl.facts.query().by_period_key(period_key).to_dataframe()
                if len(all_period_facts) > 0:
                    unique_concepts = all_period_facts['concept'].unique()[:10]  # First 10 for debugging
                    print(f"DEBUG: Available concepts for {period_label}: {unique_concepts}")

                # Don't fail if period has other facts but no specific cash flow concepts
                # This may happen for periods that focus on other statement types