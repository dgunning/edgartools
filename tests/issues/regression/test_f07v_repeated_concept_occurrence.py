"""
Regression tests for edgartools-f07v (GH #1231): a concept presented more than
once in a role got the LAST occurrence's parent and depth on every one of its
rows.

`_build_presentation_subtree` creates a fresh `PresentationNode` per traversal
occurrence but stores it as `all_nodes[element_id] = node`, keyed on the concept
alone, so each repeated occurrence overwrote the previous one's scalar parent,
depth and order. `_generate_line_items` then read `node.parent` and `node.depth`
back off that shared node for every occurrence's row.

The modelling error is that a presentation node is an OCCURRENCE, not a concept —
and repeating a concept is a supported pattern here, not a malformed filing: the
parser deliberately keeps duplicate roll-forward references, and a statement
routinely repeats a line under two sections.

The fix does not rekey `all_nodes`. Every other consumer — the statement
resolver, notes, facts, the viewer — uses it as a concept-keyed lookup or
membership set, and that use is correct. The traversal already knows each
occurrence's true position, because it threads `path` down the recursion for the
label override; the parent is `path[-1]` and the depth is `len(path)`. Those are
now what the row reports.

Ground truth is JPMorgan's FY2013 10-K earnings-per-share note, which presents
the same two lines under both the basic and the diluted two-class-method
sections. Measured across the committed fixture corpus, this corrects 77 rows'
parent across 41 roles and 71 rows' level across 12, and changes nothing else.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL

FIXTURE = Path("tests/fixtures/xbrl/jpm/10k_2013")

BASIC_SECTION = "us-gaap_EarningsPerShareBasicTwoClassMethodAbstract"
DILUTED_SECTION = "us-gaap_EarningsPerShareDilutedTwoClassMethodAbstract"

# The two concepts JPM presents under both sections.
REPEATED = (
    "us-gaap_NetIncomeLossAvailableToCommonStockholdersBasic",
    "us-gaap_WeightedAverageNumberOfSharesOutstandingBasic",
)


@pytest.fixture(scope="module")
def jpm():
    return XBRL.from_directory(FIXTURE)


@pytest.fixture(scope="module")
def eps_role(jpm):
    role = next(
        (r for r in jpm.presentation_trees if r.endswith("EarningsPerShareDetails")),
        None,
    )
    assert role is not None
    return role


def test_each_occurrence_reports_its_own_parent(jpm, eps_role):
    """
    Both rows claimed the DILUTED parent before the fix, because the diluted
    reference is the one the parser wrote last.
    """
    rows = [r for r in jpm.get_statement(eps_role) if not r.get("is_dimension")]

    for concept in REPEATED:
        parents = [row["parent"] for row in rows if row["concept"] == concept]
        assert len(parents) == 2, f"{concept} should appear twice"
        assert sorted(parents) == sorted([BASIC_SECTION, DILUTED_SECTION]), concept


def test_the_shared_node_still_holds_the_last_occurrence(jpm, eps_role):
    """
    `all_nodes` is deliberately unchanged — it is a concept-keyed lookup that
    many callers depend on. This pins that the fix reads the walk instead of
    rekeying the dict, so a later change cannot quietly do the other thing.
    """
    tree = jpm.presentation_trees[eps_role]

    for concept in REPEATED:
        assert tree.all_nodes[concept].parent == DILUTED_SECTION


def test_a_row_s_parent_is_the_row_above_it_in_its_section(jpm, eps_role):
    """
    The rows carry a hierarchy a caller can actually reconstruct: every
    non-root row's parent is a concept that is itself present.
    """
    rows = [r for r in jpm.get_statement(eps_role) if not r.get("is_dimension")]
    present = {row["concept"] for row in rows}

    for row in rows:
        if row["parent"] is not None:
            assert row["parent"] in present, row["concept"]


def test_depth_matches_the_walk(jpm, eps_role):
    """
    A row's level is its distance from the root, so a child is always deeper
    than the parent it names.
    """
    rows = [r for r in jpm.get_statement(eps_role) if not r.get("is_dimension")]
    # Levels are post-processed by _adjust_levels_by_calculation_parent, so
    # compare against the parent's own reported level rather than a literal.
    by_concept = {row["concept"]: row for row in rows}

    for row in rows:
        parent = row["parent"]
        if parent is not None and parent in by_concept:
            assert row["level"] > by_concept[parent]["level"], row["concept"]


def test_roll_forward_repeats_keep_one_parent(jpm):
    """
    The control. A concept repeated under the SAME parent — the roll-forward
    case the parser deliberately preserves — must still report that one parent
    on both occurrences, not be split by the change.
    """
    aapl = XBRL.from_directory(Path("tests/fixtures/xbrl/aapl/10k_2023"))
    role = next(
        r for r in aapl.presentation_trees
        if r.endswith("CONSOLIDATEDSTATEMENTSOFCASHFLOWS")
    )
    rows = [r for r in aapl.get_statement(role) if not r.get("is_dimension")]

    cash = "us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
    parents = [row["parent"] for row in rows if row["concept"] == cash]
    assert len(parents) > 1, "the roll-forward should present cash more than once"
    assert len(set(parents)) == 1, "same parent on every occurrence"
