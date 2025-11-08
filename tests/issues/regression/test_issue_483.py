"""
Regression test for issue #483: CurrentFilings missing current_page attribute

Issue: https://github.com/dgunning/edgartools/issues/483
The documented example shows using page.current_page in iter_current_filings_pages()
but CurrentFilings objects didn't have this attribute.
"""
import pytest
from edgar import iter_current_filings_pages


@pytest.mark.network
def test_current_page_attribute_exists():
    """Test that CurrentFilings has current_page attribute as shown in docs."""
    # Get first page
    page_iter = iter_current_filings_pages(form="8-K")
    page = next(page_iter)

    # Verify current_page attribute exists and is correct
    assert hasattr(page, 'current_page'), "CurrentFilings should have current_page attribute"
    assert page.current_page == 1, "First page should be page 1"


@pytest.mark.network
def test_current_page_increments():
    """Test that current_page increments correctly across pages."""
    page_count = 0

    for page in iter_current_filings_pages(form="8-K"):
        page_count += 1

        # Verify current_page matches the iteration count
        assert page.current_page == page_count, \
            f"Expected page {page_count}, got {page.current_page}"

        # Test the documented pattern - break after 3 pages
        if page.current_page >= 3:
            break

    # Verify we actually iterated through pages
    assert page_count == 3, "Should have processed exactly 3 pages"


@pytest.mark.network
def test_documented_example_pattern():
    """Test the exact pattern from the documentation works without errors."""
    processed_count = 0

    # This is the exact pattern from the docs that was failing
    for page in iter_current_filings_pages(form="8-K"):
        processed_count += len(page)

        for filing in page:
            # Just verify we can iterate
            assert filing.company is not None
            break  # Only check first filing per page

        # This line was causing AttributeError before the fix
        if page.current_page >= 3:
            break

    # Verify we processed some filings
    assert processed_count > 0, "Should have processed at least some filings"


def test_current_page_calculation():
    """Test current_page calculation with different page sizes and start positions."""
    from edgar.current_filings import CurrentFilings, _empty_filing_index

    # Test page 1 with page_size=100
    page1 = CurrentFilings(_empty_filing_index(), start=1, page_size=100)
    assert page1.current_page == 1

    # Test page 2 with page_size=100
    page2 = CurrentFilings(_empty_filing_index(), start=101, page_size=100)
    assert page2.current_page == 2

    # Test page 3 with page_size=100
    page3 = CurrentFilings(_empty_filing_index(), start=201, page_size=100)
    assert page3.current_page == 3

    # Test with different page size (40)
    page1_small = CurrentFilings(_empty_filing_index(), start=1, page_size=40)
    assert page1_small.current_page == 1

    page2_small = CurrentFilings(_empty_filing_index(), start=41, page_size=40)
    assert page2_small.current_page == 2

    page3_small = CurrentFilings(_empty_filing_index(), start=81, page_size=40)
    assert page3_small.current_page == 3
