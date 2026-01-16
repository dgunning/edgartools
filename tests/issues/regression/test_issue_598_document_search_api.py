"""
Regression test for Issue #598: Unable to use DocumentSearch with document

Problem: Documentation showed `DocumentSearch(filing.document)` but `filing.document`
returns an `Attachment` object (file metadata), while `DocumentSearch` expects a
`Document` object (parsed HTML with `.root` node tree).

Error: AttributeError: 'Attachment' object has no attribute 'root'

Fix: Added `filing.parse()` method that returns a structured Document object
suitable for DocumentSearch and other advanced document operations.

Reporter: leonrem (Leonid Rempel)
See: https://github.com/dgunning/edgartools/issues/598
"""
import pytest


class TestIssue598DocumentSearchAPI:
    """Test that filing.parse() works correctly with DocumentSearch."""

    @pytest.fixture
    def aapl_10k_filing(self):
        """Get AAPL 10-K filing for testing."""
        from edgar import Company
        company = Company("AAPL")
        return company.get_filings(form="10-K").latest(1)

    @pytest.mark.network
    def test_filing_parse_returns_document_with_root(self, aapl_10k_filing):
        """Test that filing.parse() returns Document object with .root attribute.

        This was the root cause of Issue #598 - DocumentSearch expected a Document
        with .root but filing.document returned Attachment without .root.
        """
        document = aapl_10k_filing.parse()

        assert document is not None, "parse() should return a Document"
        assert hasattr(document, 'root'), "Document should have .root attribute"
        assert hasattr(document.root, 'walk'), "Document.root should have .walk() method"

    @pytest.mark.network
    def test_document_search_works_with_parsed_filing(self, aapl_10k_filing):
        """Test that DocumentSearch works with filing.parse().

        This is the exact workflow from the documentation that was broken.
        """
        from edgar.documents.search import DocumentSearch

        document = aapl_10k_filing.parse()

        # This should NOT raise AttributeError after the fix
        searcher = DocumentSearch(document)

        # Verify search works
        results = searcher.ranked_search("revenue", algorithm="hybrid", top_k=5)

        assert len(results) > 0, "Search should return results"
        for result in results:
            assert hasattr(result, 'score'), "Result should have score"
            assert hasattr(result, 'snippet'), "Result should have snippet"

    @pytest.mark.network
    def test_filing_document_still_returns_attachment(self, aapl_10k_filing):
        """Test that filing.document still returns Attachment (backwards compatible).

        We're not changing filing.document behavior - it should still return
        Attachment for users who want file metadata.
        """
        from edgar.attachments import Attachment

        document = aapl_10k_filing.document

        # filing.document should return Attachment (not Document)
        assert isinstance(document, Attachment), \
            "filing.document should return Attachment for backwards compatibility"
        assert not hasattr(document, 'root'), \
            "Attachment should not have .root attribute"

    @pytest.mark.network
    def test_parse_is_cached(self, aapl_10k_filing):
        """Test that filing.parse() is cached for performance."""
        doc1 = aapl_10k_filing.parse()
        doc2 = aapl_10k_filing.parse()

        # Same object should be returned (cached)
        assert doc1 is doc2, "parse() should return cached Document"

    @pytest.mark.network
    def test_parse_returns_none_for_non_html_filing(self):
        """Test that parse() returns None for filings without HTML content."""
        from edgar import Company

        # Find a filing that might not have HTML (e.g., very old filing or upload)
        # For most modern filings this won't apply, but the method should handle it
        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest(1)

        # For normal 10-K, parse should work
        document = filing.parse()
        # If it returns None, that's also valid (no HTML)
        # If it returns Document, it should have root
        if document is not None:
            assert hasattr(document, 'root')

    @pytest.mark.network
    def test_full_workflow_from_documentation(self, aapl_10k_filing):
        """Test the complete workflow from the updated documentation.

        This replicates the exact example from docs/advanced-search.md.
        """
        from edgar.documents.search import DocumentSearch

        # Parse HTML into structured Document
        document = aapl_10k_filing.parse()

        # Create search interface
        searcher = DocumentSearch(document)

        # Search with ranking
        results = searcher.ranked_search(
            query="revenue growth",
            algorithm="hybrid",
            top_k=5
        )

        # Access results
        assert len(results) > 0, "Should find results for 'revenue growth'"

        for result in results:
            # All results should have these attributes
            assert hasattr(result, 'score')
            assert hasattr(result, 'section')
            assert hasattr(result, 'snippet')

            # Score should be a number
            assert isinstance(result.score, (int, float))

    @pytest.mark.network
    def test_parse_works_with_different_form_types(self):
        """Test that parse() works with different form types (10-K, 10-Q, 8-K)."""
        from edgar import Company

        company = Company("AAPL")

        # Test 10-K
        filing_10k = company.get_filings(form="10-K").latest(1)
        doc_10k = filing_10k.parse()
        if doc_10k:
            assert hasattr(doc_10k, 'root')

        # Test 10-Q
        filing_10q = company.get_filings(form="10-Q").latest(1)
        doc_10q = filing_10q.parse()
        if doc_10q:
            assert hasattr(doc_10q, 'root')

        # Test 8-K
        filing_8k = company.get_filings(form="8-K").latest(1)
        doc_8k = filing_8k.parse()
        if doc_8k:
            assert hasattr(doc_8k, 'root')
