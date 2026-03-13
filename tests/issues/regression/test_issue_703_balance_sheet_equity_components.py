"""
Regression test for GitHub Issue #703: Concepts silently dropped from statements.

Root cause: _merge_same_label_line_items (GH-572) merged unrelated concepts that
shared a display label, silently dropping equity components, cash flow items, and
other concepts across all statement types.

Fix: Removed the merge heuristic entirely.  No concepts are merged or dropped
during statement rendering.  Duplicate-label rows (from XBRL concept switches)
are preserved as-is — data correctness over cosmetics.
"""

import pytest
from edgar.xbrl.xbrl import XBRL


@pytest.mark.fast
class TestIssue703NoMergeHeuristic:
    """Verify that no merge heuristic exists to silently drop concepts."""

    def test_no_merge_method_exists(self):
        """The merge heuristic should not exist on the XBRL class."""
        assert not hasattr(XBRL, '_merge_same_label_line_items')
        assert not hasattr(XBRL, '_merge_sibling_concept_switches')
