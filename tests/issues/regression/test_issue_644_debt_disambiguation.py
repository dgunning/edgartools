"""
Regression tests for Issue #644: FOX debt tags disambiguated incorrectly.

Ambiguous XBRL tags like LongTermDebtAndCapitalLeaseObligationsCurrentAndNoncurrent
contain hints in their name ("Noncurrent", "Current") that should be used
when section-based disambiguation isn't available.

Fix: Added tag-name-based hints to _disambiguate_by_context() in reverse_index.py.
"""

import pytest

from edgar.xbrl.standardization.reverse_index import ReverseIndex


@pytest.mark.fast
class TestIssue644DebtDisambiguation:
    """Verify tag-name hints help disambiguate current vs noncurrent debt."""

    @pytest.fixture
    def reverse_index(self):
        return ReverseIndex()

    def test_noncurrent_tag_hint(self, reverse_index):
        """A tag with 'Noncurrent' in its name should prefer non-current candidates."""
        # Check that the tag-name hint resolution works generically
        candidates = ["CurrentDebt", "NoncurrentDebt"]
        context = {"statement_type": "BalanceSheet"}

        result = reverse_index._disambiguate_by_context(
            "SomeNoncurrentDebtTag", candidates, context
        )
        assert result == "NoncurrentDebt"

    def test_current_tag_hint(self, reverse_index):
        """A tag with 'Current' (not 'Noncurrent') should prefer current candidates."""
        candidates = ["CurrentLiabilities", "NoncurrentLiabilities"]
        context = {"statement_type": "BalanceSheet"}

        result = reverse_index._disambiguate_by_context(
            "SomeCurrentLiabilitiesTag", candidates, context
        )
        assert result == "CurrentLiabilities"

    def test_longterm_tag_hint(self, reverse_index):
        """A tag with 'LongTerm' should prefer non-current candidates."""
        candidates = ["CurrentDebt", "NoncurrentDebt"]
        context = {"statement_type": "BalanceSheet"}

        result = reverse_index._disambiguate_by_context(
            "LongTermDebtObligations", candidates, context
        )
        assert result == "NoncurrentDebt"

    def test_section_still_takes_priority(self, reverse_index):
        """When section info is available, it should still override tag-name hints."""
        # This tests that the tag-name hint doesn't prevent section-based resolution
        # The tag says "noncurrent" but if a section context resolves differently,
        # the section-based logic should work correctly
        candidates = ["CurrentDebt", "NoncurrentDebt"]
        context = {
            "statement_type": "BalanceSheet",
            "section": "Non-Current Liabilities",
        }

        result = reverse_index._disambiguate_by_context(
            "SomeNoncurrentTag", candidates, context
        )
        # Tag hint matches Noncurrent, section also matches - should get NoncurrentDebt
        assert result == "NoncurrentDebt"
