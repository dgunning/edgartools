"""
Unit tests for edgar.llm return type contracts.

Tests Issue #1 fix: Ensure extract_sections() returns correct types
based on track_filtered parameter.
"""

from unittest.mock import Mock, patch
from edgar.llm import extract_sections, ExtractedSection


def test_extract_sections_returns_list_when_track_filtered_false():
    """
    Test that extract_sections returns a list when track_filtered=False.

    This verifies Issue #1 fix: API contract should match documentation.
    """
    # Create a mock filing
    mock_filing = Mock()
    mock_filing.html.return_value = None  # No HTML to avoid actual extraction

    # Call with track_filtered=False (default)
    result = extract_sections(mock_filing, item="1")

    # Should return a list, not a tuple
    assert isinstance(result, list), \
        f"Expected list but got {type(result)}. Return value: {result}"

    # Should be list of ExtractedSection objects (may be empty)
    assert all(isinstance(s, ExtractedSection) for s in result), \
        "All items should be ExtractedSection instances"


def test_extract_sections_returns_tuple_when_track_filtered_true():
    """
    Test that extract_sections returns a tuple when track_filtered=True.

    This verifies the documented behavior for filtered data tracking.
    """
    # Create a mock filing
    mock_filing = Mock()
    mock_filing.html.return_value = None

    # Call with track_filtered=True
    result = extract_sections(mock_filing, item="1", track_filtered=True)

    # Should return a tuple
    assert isinstance(result, tuple), \
        f"Expected tuple but got {type(result)}. Return value: {result}"

    # Tuple should have exactly 2 elements
    assert len(result) == 2, \
        f"Expected tuple of length 2 but got {len(result)}"

    # First element should be list of sections
    sections, filtered_data = result
    assert isinstance(sections, list), \
        f"First element should be list but got {type(sections)}"

    # Second element should be dict with filtered metadata
    assert isinstance(filtered_data, dict), \
        f"Second element should be dict but got {type(filtered_data)}"

    # Dict should have expected keys
    expected_keys = {"xbrl_metadata_tables", "duplicate_tables", "filtered_text_blocks", "details"}
    assert expected_keys.issubset(filtered_data.keys()), \
        f"Filtered data dict missing expected keys. Got: {filtered_data.keys()}"


def test_extract_sections_list_unpacking_works():
    """
    Test that list unpacking works when track_filtered=False.

    This is the common use case that would fail with old behavior.
    """
    mock_filing = Mock()
    mock_filing.html.return_value = None

    # This should work without unpacking errors
    sections = extract_sections(mock_filing, item="1", track_filtered=False)

    # Should be able to iterate directly (list behavior)
    for section in sections:
        assert isinstance(section, ExtractedSection)

    # Should be able to check length (list behavior)
    assert len(sections) >= 0


def test_extract_sections_tuple_unpacking_works():
    """
    Test that tuple unpacking works when track_filtered=True.
    """
    mock_filing = Mock()
    mock_filing.html.return_value = None

    # This should allow tuple unpacking
    sections, filtered_data = extract_sections(
        mock_filing,
        item="1",
        track_filtered=True
    )

    # Both should be accessible
    assert isinstance(sections, list)
    assert isinstance(filtered_data, dict)


def test_backward_compatibility_no_track_filtered_param():
    """
    Test backward compatibility when track_filtered is not specified.

    Should default to False and return a list.
    """
    mock_filing = Mock()
    mock_filing.html.return_value = None

    # Call without track_filtered parameter
    result = extract_sections(mock_filing, item="1")

    # Should behave like track_filtered=False (return list)
    assert isinstance(result, list), \
        "Default behavior should return list when track_filtered not specified"


if __name__ == "__main__":
    # Run tests
    test_extract_sections_returns_list_when_track_filtered_false()
    print("[PASS] test_extract_sections_returns_list_when_track_filtered_false")

    test_extract_sections_returns_tuple_when_track_filtered_true()
    print("[PASS] test_extract_sections_returns_tuple_when_track_filtered_true")

    test_extract_sections_list_unpacking_works()
    print("[PASS] test_extract_sections_list_unpacking_works")

    test_extract_sections_tuple_unpacking_works()
    print("[PASS] test_extract_sections_tuple_unpacking_works")

    test_backward_compatibility_no_track_filtered_param()
    print("[PASS] test_backward_compatibility_no_track_filtered_param")

    print("\n[SUCCESS] All tests passed!")
