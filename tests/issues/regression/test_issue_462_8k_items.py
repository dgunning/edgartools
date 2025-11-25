"""
Regression test for GitHub Issue #462: Incorrect items parsed from 8-K

Problem: SEC metadata `items` field is incorrect or empty for legacy 8-K filings (1999-2011).
- 1999 filing with CIK 864509: SEC metadata shows "3" but filing contains Item 7
- 2008-2011 filings: SEC metadata is empty but filings contain valid items

Solution: Added `parsed_items` property that parses items from the filing document text,
filtering out items marked "Not Applicable".

GitHub Issue: https://github.com/dgunning/edgartools/issues/462
"""
import pytest
from edgar import Company


@pytest.mark.network
class TestIssue462ParsedItems:
    """Tests for the parsed_items property added in Issue #462."""

    def test_1999_legacy_filing_returns_correct_items(self):
        """
        Original issue: 1999 8-K has wrong SEC metadata.

        SEC metadata shows "3" but the filing only has Item 7 with content
        (all other items are marked "Not Applicable").
        """
        filing = Company(864509).get_filings(
            form='8-K',
            amendments=False,
            filing_date='1999-10-13'
        )[0]

        # SEC metadata is wrong
        assert filing.items == "3"

        # parsed_items correctly extracts Item 7 (the only substantive item)
        assert filing.parsed_items == "7"

    def test_2011_filing_with_empty_metadata(self):
        """
        2011 8-K with empty SEC metadata should return parsed items.

        CIK 919130, accession 0001144204-11-047401
        """
        filings = Company(919130).get_filings(form='8-K')
        filing = None
        for f in filings:
            if f.accession_no == '0001144204-11-047401':
                filing = f
                break

        assert filing is not None, "Filing not found"

        # SEC metadata is empty
        assert filing.items == ""

        # parsed_items correctly extracts items from document
        assert filing.parsed_items == "2.02,9.01"

    def test_2008_filing_with_empty_metadata(self):
        """
        2008 8-K with empty SEC metadata should return parsed items.

        CIK 713095, accession 0000713095-08-000011
        """
        filings = Company(713095).get_filings(form='8-K')
        filing = None
        for f in filings:
            if f.accession_no == '0000713095-08-000011':
                filing = f
                break

        assert filing is not None, "Filing not found"

        # SEC metadata is empty
        assert filing.items == ""

        # parsed_items correctly extracts items from document
        assert filing.parsed_items == "8.01,9.01"

    def test_modern_filing_matches_sec_metadata(self):
        """
        Modern 8-K filings should have parsed_items match SEC metadata.

        This validates that parsing works correctly for current filings
        where SEC metadata is accurate.
        """
        filing = Company('AAPL').get_filings(form='8-K')[0]

        # parsed_items should match SEC metadata for modern filings
        assert filing.parsed_items == filing.items

    def test_non_8k_filing_returns_empty_string(self):
        """parsed_items should return empty string for non-8K filings."""
        filing = Company('AAPL').get_filings(form='10-K')[0]

        # Non-8K filings should return empty string
        assert filing.parsed_items == ""

    def test_items_sorted_correctly(self):
        """Items should be sorted numerically (2.02 before 9.01)."""
        filing = Company('AAPL').get_filings(form='8-K')[0]

        if ',' in filing.parsed_items:
            items = filing.parsed_items.split(',')
            # Verify items are sorted
            for i in range(len(items) - 1):
                current = float(items[i].replace('.', ''))
                next_item = float(items[i + 1].replace('.', ''))
                assert current < next_item, f"Items not sorted: {items}"
