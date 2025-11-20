"""
Test that get_current_filings(page_size=None) fetches all current filings.

This tests the Pythonic API improvement where page_size=None means "give me everything".
"""
import pytest
from edgar import get_current_filings
from edgar._filings import Filings


@pytest.mark.network
def test_get_current_filings_with_page_size_none():
    """Test that page_size=None fetches all current filings"""
    # Get all current filings
    all_filings = get_current_filings(page_size=None)

    # Should return a Filings object (not CurrentFilings)
    assert isinstance(all_filings, Filings)

    # Should have some filings
    assert len(all_filings) > 0

    # Compare with single page to verify we got more
    first_page = get_current_filings(page_size=40)

    # All filings should have at least as many as the first page
    # (could be equal if total filings < 40)
    assert len(all_filings) >= len(first_page)


@pytest.mark.network
def test_get_current_filings_page_size_none_with_form_filter():
    """Test that page_size=None works with form filtering"""
    # Get all current 8-K filings
    all_8k = get_current_filings(form="8-K", page_size=None)

    # Should return a Filings object
    assert isinstance(all_8k, Filings)

    # All filings should be 8-K or 8-K/A
    if len(all_8k) > 0:
        for filing in all_8k:
            assert filing.form in ["8-K", "8-K/A"]


@pytest.mark.network
def test_get_current_filings_default_behavior_unchanged():
    """Test that default behavior (page_size=40) is unchanged"""
    # Default should still return first page with 40 filings
    current = get_current_filings()

    # Should return CurrentFilings (not Filings)
    from edgar.current_filings import CurrentFilings
    assert isinstance(current, CurrentFilings)

    # Should have at most 40 filings (or less if total < 40)
    assert len(current) <= 40
