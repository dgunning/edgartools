"""
Regression tests for Issue #648: DECK missing Income Before Tax mapping.

DECK (Deckers Outdoor) uses the XBRL tag
IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments
which was in the exclusions list, preventing it from being mapped to PretaxIncomeLoss.

Fix: Removed the tag from exclusions.py and added it to gaap_mappings.json → PretaxIncomeLoss.
"""

import pytest

from edgar.xbrl.standardization.reverse_index import ReverseIndex
from edgar.xbrl.standardization.exclusions import should_exclude


@pytest.mark.fast
class TestIssue648DeckIncomeBeforeTax:
    """Verify the Income Before Tax tag is no longer excluded and maps correctly."""

    def test_tag_not_excluded(self):
        """The previously-excluded tag should no longer be in the exclusions list."""
        tag = "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"
        assert not should_exclude(tag), (
            f"Tag {tag} should no longer be excluded"
        )

    def test_tag_maps_to_pretax_income_loss(self):
        """The tag should map to the PretaxIncomeLoss standard concept."""
        index = ReverseIndex()
        tag = "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"

        result = index.lookup(tag)
        assert result is not None, f"Tag {tag} should have a mapping"
        assert "PretaxIncomeLoss" in result.standard_concepts

    def test_tag_display_name_is_income_before_tax(self):
        """The tag should resolve to 'Income Before Tax' display name."""
        index = ReverseIndex()
        tag = "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"

        display = index.get_display_name(tag)
        assert display == "Income Before Tax", (
            f"Expected 'Income Before Tax', got '{display}'"
        )

    def test_existing_tag_still_works(self):
        """The previously-mapped variant should still work correctly."""
        index = ReverseIndex()
        tag = "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"

        result = index.lookup(tag)
        assert result is not None
        assert "PretaxIncomeLoss" in result.standard_concepts
