"""
Regression test for Issue #441: CurrentFilings pagination assertion error

This test ensures that CurrentFilings pagination works correctly and does not
throw AssertionError when iterating through pages.

Fixed issues:
1. AssertionError in CurrentFilings.__getitem__ when get() returned None
2. Iterator not handling page-relative indices correctly
3. Proper error handling for out-of-bounds access

The fix involved:
1. Replacing assertion with proper IndexError/KeyError exceptions in __getitem__
2. Overriding __iter__ and __next__ to handle page-relative iteration correctly
3. Using super().get_filing_at() directly with page-relative indices during iteration
"""

import pytest
from edgar import get_current_filings


class TestCurrentFilingsPagination:
    """Test suite for CurrentFilings pagination functionality"""

    def test_pagination_iteration_no_assertion_error(self):
        """
        Test that iterating through CurrentFilings pages doesn't throw AssertionError.

        This was the core issue reported in #441.
        """
        current_filings = get_current_filings(page_size=5)
        assert len(current_filings) > 0, "Should have some current filings"

        # This should not raise AssertionError
        page_count = 0
        total_filings = 0

        while current_filings is not None and page_count < 3:  # Limit to 3 pages
            # This iteration was throwing AssertionError before fix
            for filing in current_filings:
                assert filing is not None
                assert hasattr(filing, 'form')
                assert hasattr(filing, 'company')
                assert hasattr(filing, 'filing_date')
                total_filings += 1

            current_filings = current_filings.next()
            page_count += 1

        assert total_filings > 0, "Should have processed some filings"
        assert page_count > 0, "Should have processed at least one page"

    @pytest.mark.slow
    @pytest.mark.vcr
    def test_out_of_bounds_indexing_raises_proper_errors(self):
        """
        Test that out-of-bounds indexing raises IndexError instead of AssertionError
        """
        current_filings = get_current_filings(page_size=5)

        # Test valid indexing works
        if len(current_filings) > 0:
            filing = current_filings[0]
            assert filing is not None

        # Test invalid integer index raises IndexError
        with pytest.raises(IndexError, match="Filing index .* is out of range for current page"):
            current_filings[999]

        # Test invalid accession number raises KeyError
        with pytest.raises(KeyError, match="Filing with accession number .* not found"):
            current_filings["0000000000-00-000000"]  # Invalid accession number

    def test_user_reported_pattern_works(self):
        """
        Test the exact pattern reported by user in Issue #441
        """
        all_current = []
        current_filings = get_current_filings(page_size=5)  # Small page size for faster test
        page_limit = 2  # Limit iterations for test

        iteration_count = 0
        while current_filings is not None and iteration_count < page_limit:
            # This exact pattern was failing before the fix
            for filing in current_filings:
                all_current.append(filing)

            current_filings = current_filings.next()
            iteration_count += 1

        assert len(all_current) > 0, "Should have collected some filings"

    def test_page_relative_iteration_correctness(self):
        """
        Test that iteration within each page uses correct page-relative indices
        """
        current_filings = get_current_filings(page_size=3)

        # Collect filings from first page via iteration
        iteration_filings = []
        for filing in current_filings:
            iteration_filings.append(filing)

        # Collect filings from first page via direct indexing
        direct_filings = []
        for i in range(len(current_filings.data)):
            filing = current_filings.data['accession_number'][i].as_py()
            direct_filings.append(filing)

        # They should match
        assert len(iteration_filings) == len(direct_filings)
        for iter_filing, direct_accession in zip(iteration_filings, direct_filings):
            assert iter_filing.accession_no == direct_accession

    def test_multiple_page_consistency(self):
        """
        Test that moving between pages maintains consistency
        """
        current_filings = get_current_filings(page_size=3)

        # Get first page data
        first_page_count = len(current_filings)
        first_page_start = current_filings._start

        # Move to next page
        next_page = current_filings.next()
        if next_page is not None:
            # Verify page transition worked correctly
            assert next_page._start > first_page_start
            assert len(next_page) > 0  # Should have data

            # Test iteration on second page works
            second_page_filings = []
            for filing in next_page:
                second_page_filings.append(filing)

            assert len(second_page_filings) == len(next_page.data)


if __name__ == "__main__":
    # Run the tests
    test_instance = TestCurrentFilingsPagination()

    print("Running regression tests for Issue #441...")

    test_instance.test_pagination_iteration_no_assertion_error()
    print("✅ Pagination iteration test passed")

    test_instance.test_out_of_bounds_indexing_raises_proper_errors()
    print("✅ Out of bounds error handling test passed")

    test_instance.test_user_reported_pattern_works()
    print("✅ User reported pattern test passed")

    test_instance.test_page_relative_iteration_correctness()
    print("✅ Page relative iteration test passed")

    test_instance.test_multiple_page_consistency()
    print("✅ Multiple page consistency test passed")

    print("\n🎉 All regression tests for Issue #441 passed!")