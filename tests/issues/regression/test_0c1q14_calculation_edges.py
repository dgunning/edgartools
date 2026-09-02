"""
Regression tests for edgartools-0c1q.14 (cluster B): calculation relationships
were stored per concept and per link element, when they are inherently per edge.

The same modelling error appeared at two levels of `calculation.py`:

  .3  NODE level (gh #1184) — `all_nodes[element_id] = node` stores one node per
      concept, so a concept with two calculation parents kept only the last
      traversal's parent and that edge's weight. `calculation_linkbase()`
      documents its result as one row per parent-to-child relationship and was
      emitting one row per concept.
  .6  TREE level — `calculation_trees[role] = tree` assigned unconditionally
      while the enclosing loop built relationships from a single
      `calculationLink` element, so a role split across two such elements lost
      the first entirely. Splitting one role across multiple extended links is
      legal XBRL.

Multiple calculation parents are ordinary, not exotic: across the checked-in
fixtures, Coca-Cola FY2023 has 28 such concepts, Amazon FY2022 has 56, Apple
FY2023 21 and JPMorgan FY2023 18. No fixture splits a role across two
`calculationLink` elements, so `.6` is covered synthetically.

Ground truth comes from checked-in fixtures, so these run offline.
"""

from pathlib import Path

import pytest

from edgar.xbrl.parsers import XBRLParser
from edgar.xbrl.xbrl import XBRL

KO_DIR = Path("tests/fixtures/xbrl/ko/10k_2024")
AAPL_DIR = Path("tests/fixtures/xbrl/aapl/10k_2023")
JPM_DIR = Path("tests/fixtures/xbrl/jpm/10k_2024")

# Coca-Cola files this concept under two parents with OPPOSITE weights, so
# whichever the old code kept, the sign was a coin flip.
KO_TWO_PARENT_CONCEPT = (
    "OtherComprehensiveIncomeAvailableforsaleSecuritiesAdjustment"
    "NetOfTaxPortionAttributableToNoncontrollingInterest"
)
KO_PARENTS = {
    ("ComprehensiveIncomeNetOfTaxAttributableToNoncontrollingInterest", 1.0),
    ("OtherComprehensiveIncomeAvailableforsaleSecuritiesAdjustment"
     "NetOfTaxPortionAttributableToParent", -1.0),
}


@pytest.fixture(scope="module")
def ko():
    return XBRL.from_directory(KO_DIR)


@pytest.fixture(scope="module")
def aapl():
    return XBRL.from_directory(AAPL_DIR)


@pytest.fixture(scope="module")
def jpm():
    return XBRL.from_directory(JPM_DIR)


def _linkbase(*links: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<linkbase xmlns="http://www.xbrl.org/2003/linkbase"
          xmlns:xlink="http://www.w3.org/1999/xlink">
  {"".join(links)}
</linkbase>"""


def _link(role_uri: str, locators: str, arcs: str) -> str:
    return f"""
      <calculationLink xlink:type="extended" xlink:role="{role_uri}">
        {locators}
        {arcs}
      </calculationLink>"""


def _loc(label: str) -> str:
    return (f'<loc xlink:type="locator" xlink:href="ex.xsd#{label}" '
            f'xlink:label="{label}"/>')


def _arc(frm: str, to: str, weight: str = "1.0", order: str = "1") -> str:
    return ('<calculationArc xlink:type="arc" '
            'xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item" '
            f'xlink:from="{frm}" xlink:to="{to}" weight="{weight}" order="{order}"/>')


def _arcs_of(parser: XBRLParser, role: str):
    """(parent, child, weight) triples for one role."""
    tree = parser.calculation_trees[role]
    return {(a.parent_id, a.child_id, a.weight) for a in tree.all_arcs}


# ---------------------------------------------------------------------------
# .3 — one node per concept collapsed two relationships into one
# ---------------------------------------------------------------------------

def test_concept_under_two_totals_keeps_both_relationships(ko):
    """
    The reported shape, in a real filing. Coca-Cola rolls this concept into the
    noncontrolling-interest total at +1 and out of the parent-attributable total
    at -1; the old code returned a single row, so the weight it reported was
    whichever edge the traversal happened to reach last.
    """
    df = ko.calculation_linkbase(include_abstract=True)
    rows = df[df.concept == KO_TWO_PARENT_CONCEPT]

    assert len(rows) == 2
    assert set(zip(rows.parent_concept, rows.weight)) == KO_PARENTS


def test_opposite_weights_are_both_preserved(ko):
    """Both signs survive — the point of the previous test stated as a value."""
    df = ko.calculation_linkbase(include_abstract=True)
    weights = df[df.concept == KO_TWO_PARENT_CONCEPT].weight

    assert sorted(weights) == [-1.0, 1.0]


@pytest.mark.parametrize(
    "company,expected_arcs",
    [("ko", 306), ("aapl", 215), ("jpm", 456)],
)
def test_every_filed_arc_reaches_the_dataframe(request, company, expected_arcs):
    """
    `calculation_linkbase()` documents one row per parent-to-child relationship,
    so its row count must equal the number of distinct arcs in `_cal.xml`.
    Before the fix Coca-Cola lost 28 of 306, Apple 21 of 215 and JPMorgan 18 of
    456 — every one of them a second parent for a concept already emitted.
    """
    xbrl = request.getfixturevalue(company)
    df = xbrl.calculation_linkbase(include_abstract=True)

    assert len(df) == expected_arcs


def test_synthetic_shared_child_under_two_totals():
    """The minimal construct from gh #1184, small enough to read in full."""
    link = _link(
        "http://example.com/role/Calc",
        _loc("TotalA") + _loc("TotalB") + _loc("Shared"),
        _arc("TotalA", "Shared", weight="1.0")
        + _arc("TotalB", "Shared", weight="-1.0", order="2"),
    )

    parser = XBRLParser()
    parser.parse_calculation_content(_linkbase(link))

    assert _arcs_of(parser, "http://example.com/role/Calc") == {
        ("TotalA", "Shared", 1.0),
        ("TotalB", "Shared", -1.0),
    }


# ---------------------------------------------------------------------------
# .6 — a second calculationLink for one role replaced the first
# ---------------------------------------------------------------------------

def test_role_split_across_two_link_elements_keeps_both():
    """
    One role, two `calculationLink` elements. The second used to replace the
    whole tree built from the first, so the first's relationships vanished.
    """
    role = "http://example.com/role/Split"
    content = _linkbase(
        _link(role, _loc("Total") + _loc("PartOne"), _arc("Total", "PartOne")),
        _link(role, _loc("Total") + _loc("PartTwo"),
              _arc("Total", "PartTwo", order="2")),
    )

    parser = XBRLParser()
    parser.parse_calculation_content(content)

    assert _arcs_of(parser, role) == {
        ("Total", "PartOne", 1.0),
        ("Total", "PartTwo", 1.0),
    }


def test_role_split_across_two_files_keeps_both():
    """The same role arriving in separate calculation linkbase files."""
    role = "http://example.com/role/Split"
    first = _linkbase(_link(role, _loc("Total") + _loc("PartOne"),
                            _arc("Total", "PartOne")))
    second = _linkbase(_link(role, _loc("Total") + _loc("PartTwo"),
                             _arc("Total", "PartTwo", order="2")))

    parser = XBRLParser()
    parser.parse_calculation_content(first)
    parser.parse_calculation_content(second)

    assert _arcs_of(parser, role) == {
        ("Total", "PartOne", 1.0),
        ("Total", "PartTwo", 1.0),
    }


def test_split_role_children_are_merged_into_one_tree():
    """Both halves hang off the same parent node, not two competing trees."""
    role = "http://example.com/role/Split"
    content = _linkbase(
        _link(role, _loc("Total") + _loc("PartOne"), _arc("Total", "PartOne")),
        _link(role, _loc("Total") + _loc("PartTwo"),
              _arc("Total", "PartTwo", order="2")),
    )

    parser = XBRLParser()
    parser.parse_calculation_content(content)
    tree = parser.calculation_trees[role]

    assert tree.all_nodes["Total"].children == ["PartOne", "PartTwo"]


# ---------------------------------------------------------------------------
# Controls — the rework must not disturb what already worked
# ---------------------------------------------------------------------------

def test_all_nodes_still_keyed_by_concept(ko):
    """
    `all_nodes` is read as a membership set in a dozen places
    (`element_id in tree.all_nodes`). Per-edge storage is added beside it, not
    in place of it.
    """
    role, tree = next(iter(ko.calculation_trees.items()))

    assert all(node_id == node.element_id for node_id, node in tree.all_nodes.items())
    assert tree.role_uri == role


def test_every_arc_endpoint_has_a_node(ko):
    """Nothing appears as an edge endpoint without also appearing as a node."""
    for tree in ko.calculation_trees.values():
        for arc in tree.all_arcs:
            assert arc.parent_id in tree.all_nodes
            assert arc.child_id in tree.all_nodes


def test_single_parent_concepts_are_unchanged(aapl):
    """
    A concept with one calculation parent must still produce exactly one row.
    Apple's gross profit rolls up only into operating income.
    """
    df = aapl.calculation_linkbase(include_abstract=True)
    rows = df[df.concept == "GrossProfit"]

    assert len(rows) == 1
    assert rows.iloc[0].parent_concept == "OperatingIncomeLoss"
    assert rows.iloc[0].weight == 1.0


def test_a_cycle_does_not_recurse_forever():
    """
    Merging relationships across link elements makes a directed cycle reachable
    where separate builds could not produce one. A cycle is not valid XBRL, but
    it must fail as a missing edge rather than as a stack overflow.
    """
    role = "http://example.com/role/Cycle"
    content = _linkbase(
        _link(role, _loc("A") + _loc("B"), _arc("A", "B")),
        _link(role, _loc("B") + _loc("A"), _arc("B", "A")),
    )

    parser = XBRLParser()
    parser.parse_calculation_content(content)  # must return, not hang

    assert role in parser.calculation_roles
