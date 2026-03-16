"""
Regression test for GH #711: PG stitching income statement EBIT concept rename.

PG changed their XBRL concept for pre-tax income (EBIT) at the FY2024 boundary:
- Pre-2024: pg_IncomeLossFromContinuingOperationsBeforeIncomeTaxes
- 2024+: us-gaap_IncomeLossIncludingPortionAttributableToNoncontrollingInterest

The stitching engine must recognize these as the same economic concept and merge
them into a single row.

Fix: Add concept-level equivalence pairs in _EQUIVALENT_CONCEPTS that the stitcher
uses to merge rows with completely different concept names, guarded by value
agreement on overlapping periods.
"""

import pytest


class TestPGConceptRenameStitching:
    """Test that PG's concept rename is handled correctly in stitching."""

    def test_concept_equivalence_map_contains_pg_pair(self):
        """The two PG concepts should be registered as equivalent."""
        from edgar.xbrl.stitching.core import _RENAME_MAP
        assert 'IncomeLossFromContinuingOperationsBeforeIncomeTaxes' in _RENAME_MAP
        assert 'IncomeLossIncludingPortionAttributableToNoncontrollingInterest' in _RENAME_MAP
        # Both should map to the same canonical
        assert (_RENAME_MAP['IncomeLossFromContinuingOperationsBeforeIncomeTaxes']
                == _RENAME_MAP['IncomeLossIncludingPortionAttributableToNoncontrollingInterest'])

    def test_concept_name_variants_does_not_match_pg_concepts(self):
        """Verify that the two PG concepts are NOT name variants of each other,
        confirming the concept equivalence mechanism is needed."""
        from edgar.xbrl.stitching.core import StatementStitcher
        assert not StatementStitcher._are_concept_name_variants(
            'pg_IncomeLossFromContinuingOperationsBeforeIncomeTaxes',
            'us-gaap_IncomeLossIncludingPortionAttributableToNoncontrollingInterest'
        )

    def test_bare_concept_name_strips_prefix(self):
        """Bare concept name extraction should strip namespace prefixes."""
        from edgar.xbrl.stitching.core import StatementStitcher
        assert (StatementStitcher._bare_concept_name('pg_IncomeLossFromContinuingOperationsBeforeIncomeTaxes')
                == 'IncomeLossFromContinuingOperationsBeforeIncomeTaxes')
        assert (StatementStitcher._bare_concept_name('us-gaap_IncomeLossIncludingPortionAttributableToNoncontrollingInterest')
                == 'IncomeLossIncludingPortionAttributableToNoncontrollingInterest')

    def test_income_loss_before_taxes_maps_to_pretax(self):
        """IncomeLossFromContinuingOperationsBeforeIncomeTaxes should
        map to PretaxIncomeLoss in gaap_mappings (semantically correct)."""
        from edgar.xbrl.standardization.reverse_index import ReverseIndex
        ri = ReverseIndex()
        result = ri.get_standard_concept('IncomeLossFromContinuingOperationsBeforeIncomeTaxes')
        assert result is not None
        assert result == 'PretaxIncomeLoss'

    def test_nci_concept_stays_excluded(self):
        """IncomeLossIncludingPortionAttributableToNoncontrollingInterest should
        remain in exclusions — it's semantically 'net income including NCI',
        not pre-tax income. The stitcher handles PG's case via concept equivalence."""
        from edgar.xbrl.standardization.exclusions import EXCLUDED_TAGS
        assert 'IncomeLossIncludingPortionAttributableToNoncontrollingInterest' in EXCLUDED_TAGS
