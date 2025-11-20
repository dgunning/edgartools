"""
Tests for smart warnings that guide users between get_filings() and get_current_filings()

Tests related to GitHub issue #496: Users expect get_filings().latest() to return today's filings,
but it only returns data through yesterday. These warnings help guide users to get_current_filings()
when they're trying to access current-day data.
"""
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock
import pyarrow as pa

from edgar._filings import (
    _get_data_staleness_days,
    _is_requesting_current_filings,
    _warn_use_current_filings,
    Filings
)


class TestHelperFunctions:
    """Test the helper functions for staleness detection"""

    def test_get_data_staleness_days_with_datetime(self):
        """Test staleness calculation with datetime input"""
        # 3 days ago
        three_days_ago = datetime.now() - timedelta(days=3)
        assert _get_data_staleness_days(three_days_ago) == 3

    def test_get_data_staleness_days_with_date(self):
        """Test staleness calculation with date input"""
        # 5 days ago
        five_days_ago = date.today() - timedelta(days=5)
        assert _get_data_staleness_days(five_days_ago) == 5

    def test_get_data_staleness_days_today(self):
        """Test that today's date returns 0 days old"""
        today = date.today()
        assert _get_data_staleness_days(today) == 0

    def test_is_requesting_current_filings_single_date_today(self):
        """Test detection when user requests today's date"""
        today_str = date.today().isoformat()
        assert _is_requesting_current_filings(today_str) is True

    def test_is_requesting_current_filings_range_includes_today(self):
        """Test detection when date range includes today"""
        yesterday = date.today() - timedelta(days=1)
        tomorrow = date.today() + timedelta(days=1)
        date_range = f"{yesterday.isoformat()}:{tomorrow.isoformat()}"
        assert _is_requesting_current_filings(date_range) is True

    def test_is_requesting_current_filings_open_range_to_today(self):
        """Test detection with open-ended range to today"""
        last_week = date.today() - timedelta(days=7)
        date_range = f"{last_week.isoformat()}:"  # Open-ended to today
        assert _is_requesting_current_filings(date_range) is True

    def test_is_requesting_current_filings_historical_date(self):
        """Test that historical dates don't trigger warning"""
        last_month = date.today() - timedelta(days=30)
        assert _is_requesting_current_filings(last_month.isoformat()) is False

    def test_is_requesting_current_filings_none(self):
        """Test that None parameter doesn't trigger warning"""
        assert _is_requesting_current_filings(None) is False


class TestWarningMessages:
    """Test that warning messages are formatted correctly"""

    @patch('edgar._filings.log')
    def test_warn_use_current_filings_with_date(self, mock_log):
        """Test warning message includes date information"""
        three_days_ago = date.today() - timedelta(days=3)
        _warn_use_current_filings("Test reason", three_days_ago)

        # Verify log.warning was called
        assert mock_log.warning.called
        warning_message = mock_log.warning.call_args[0][0]

        # Check message contents
        assert "Test reason" in warning_message
        assert "get_current_filings(page_size=None)" in warning_message
        assert str(three_days_ago) in warning_message
        assert "3 days ago" in warning_message

    @patch('edgar._filings.log')
    def test_warn_use_current_filings_without_date(self, mock_log):
        """Test warning message without date information"""
        _warn_use_current_filings("Test reason")

        assert mock_log.warning.called
        warning_message = mock_log.warning.call_args[0][0]
        assert "Test reason" in warning_message
        assert "get_current_filings(page_size=None)" in warning_message


@pytest.mark.fast
class TestFilingsLatestWarning:
    """Test warnings in Filings.latest() method"""

    @patch('edgar._filings.log')
    def test_latest_warns_on_stale_data(self, mock_log):
        """Test that latest() warns when data is >2 days old"""
        # Create mock filing data that's 3 days old
        three_days_ago = datetime.now() - timedelta(days=3)

        filing_data = pa.Table.from_pylist([
            {
                'cik': 1234567890,
                'company': 'Test Company',
                'form': '10-K',
                'filing_date': three_days_ago,
                'accession_number': '0001234567-23-000001',
            }
        ])

        filings = Filings(filing_data)
        result = filings.latest()

        # Verify warning was logged
        assert mock_log.warning.called
        warning_message = mock_log.warning.call_args[0][0]
        assert "get_current_filings(page_size=None)" in warning_message

    @patch('edgar._filings.log')
    def test_latest_no_warning_on_recent_data(self, mock_log):
        """Test that latest() doesn't warn for data from yesterday"""
        # Create mock filing data from yesterday (not stale enough)
        yesterday = datetime.now() - timedelta(days=1)

        filing_data = pa.Table.from_pylist([
            {
                'cik': 1234567890,
                'company': 'Test Company',
                'form': '10-K',
                'filing_date': yesterday,
                'accession_number': '0001234567-23-000001',
            }
        ])

        filings = Filings(filing_data)
        result = filings.latest()

        # Verify NO warning was logged (data is only 1 day old)
        assert not mock_log.warning.called


@pytest.mark.fast
class TestFilingsFilterWarning:
    """Test warnings in Filings.filter() method"""

    @patch('edgar._filings.log')
    def test_filter_warns_when_requesting_today_with_stale_data(self, mock_log):
        """Test that filter() warns when user requests today but data is from yesterday"""
        # Create mock filing data from 2 days ago
        two_days_ago = datetime.now() - timedelta(days=2)

        filing_data = pa.Table.from_pylist([
            {
                'cik': 1234567890,
                'company': 'Test Company',
                'form': '10-K',
                'filing_date': two_days_ago,
                'accession_number': '0001234567-23-000001',
            }
        ])

        filings = Filings(filing_data)

        # Try to filter for today's date
        today_str = date.today().isoformat()
        result = filings.filter(filing_date=today_str)

        # Verify warning was logged
        assert mock_log.warning.called
        warning_message = mock_log.warning.call_args[0][0]
        assert "get_current_filings(page_size=None)" in warning_message

    @patch('edgar._filings.log')
    def test_filter_no_warning_for_historical_date(self, mock_log):
        """Test that filter() doesn't warn for clearly historical queries"""
        # Create mock filing data from 30 days ago
        thirty_days_ago = datetime.now() - timedelta(days=30)
        thirty_days_ago_str = (date.today() - timedelta(days=30)).isoformat()

        filing_data = pa.Table.from_pylist([
            {
                'cik': 1234567890,
                'company': 'Test Company',
                'form': '10-K',
                'filing_date': thirty_days_ago,
                'accession_number': '0001234567-23-000001',
            }
        ])

        filings = Filings(filing_data)

        # Filter for the same historical date
        result = filings.filter(filing_date=thirty_days_ago_str)

        # Verify NO warning (this is clearly a historical query)
        assert not mock_log.warning.called


# Note: Tests for get_filings() warning behavior would require mocking the SEC API
# and are better suited for integration tests. The core warning logic is tested above.
