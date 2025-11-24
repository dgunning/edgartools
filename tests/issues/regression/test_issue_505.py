"""
Regression test for Issue #505: TypeError crash on date filter with empty result set

GitHub Issue: https://github.com/dgunning/edgartools/issues/505
Reporter: jakobovski-arb

Bug: Filings.filter(date="...") crashed with TypeError when filtering returned no records.
The _get_data_staleness_days() function attempted date arithmetic on None when latest_date was null.

Root Cause: When filtering results in zero records, latest_date becomes None, but the code
didn't check for this before attempting date arithmetic.

Fix: Added null check in _get_data_staleness_days() to return a large number (999999) when
latest_date is None, preventing the TypeError.
"""

import pytest
from edgar import get_filings


@pytest.mark.network
def test_issue_505_empty_date_filter_no_crash():
    """
    Test that date filtering gracefully handles empty result sets without crashing.

    This test ensures that when filtering returns no records, the code doesn't
    crash with a TypeError due to None values in date calculations.
    """
    # Get some filings from a specific year
    filings = get_filings(form="10-K", year=2023)

    # Filter to a future date range that should return no results
    # This should not crash - it should return an empty Filings object
    filtered = filings.filter(date="2025-12-01:2025-12-31")

    # Verify we got an empty result set (not a crash)
    assert len(filtered) == 0, "Expected empty result set for future date range"
    assert filtered is not None, "filter() should return Filings object, not None"


@pytest.mark.network
def test_issue_505_date_filter_chained_operations():
    """
    Test that chained filter operations work correctly even when intermediate
    or final results are empty.
    """
    # Reproduce the exact scenario from the bug report
    filings = get_filings(year=2023)

    # Apply form filter
    filings = filings.filter(form="10-K", amendments=False)

    # Apply date filter that might return empty results
    # This should not crash even if no records match
    filtered = filings.filter(date="2025-12-01:2025-12-31")

    assert len(filtered) == 0
    assert filtered is not None


@pytest.mark.network
def test_issue_505_empty_filings_date_range():
    """
    Test that date_range property handles empty Filings correctly.
    """
    # Get filings and filter to empty set
    filings = get_filings(form="10-K", year=2023)
    empty_filings = filings.filter(date="2025-12-01:2025-12-31")

    # Access date_range property - should not crash
    date_range = empty_filings.date_range

    # When empty, both min and max should be None
    assert date_range[0] is None, "Empty filings should have None as min date"
    assert date_range[1] is None, "Empty filings should have None as max date"


@pytest.mark.fast
def test_get_data_staleness_days_handles_none():
    """
    Unit test to verify _get_data_staleness_days() handles None without crashing.
    """
    from edgar._filings import _get_data_staleness_days

    # Should not crash with None input
    staleness = _get_data_staleness_days(None)

    # Should return a large number indicating "very stale" or "no data"
    assert staleness == 999999, "Expected large staleness value for None input"
    assert isinstance(staleness, int), "Staleness should be an integer"
