"""Regression: the presentation tree keeps same-child relationships with a distinct order or preferred label.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1758

A parent may present the same concept twice: Coca-Cola's FY2011 debt details
show long-term debt as a total at order 21 and again, with a verbose label, at
order 30. Under XBRL 2.1 section 3.5.3.9.7.4 the two relationships are not
equivalent (order and preferredLabel are non-exempt attributes), so both are
in the network. `PresentationParser` kept only the first: the builder lists a
child concept once per parent so the statement does not render the same row
twice (GH #825), and nothing else recorded the second relationship.

`PresentationTree.relationships` now holds every effective relationship of the
role as filed. `PresentationNode.children`, the statement view, is unchanged:
one reference per child concept, except a period start/end pair.
"""

from pathlib import Path

from edgar.xbrl import XBRL
from edgar.xbrl.parsers.presentation import PresentationParser

ROLE = "http://example.com/role/R"
LABEL = "http://www.xbrl.org/2003/role/"


def network(first, second):
    trees = {}
    PresentationParser({}, trees, {}).parse_presentation_content(f"""
    <link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
                   xmlns:xlink="http://www.w3.org/1999/xlink">
      <link:presentationLink xlink:type="extended" xlink:role="{ROLE}">
        <link:loc xlink:type="locator" xlink:label="t1" xlink:href="a.xsd#a_Total"/>
        <link:loc xlink:type="locator" xlink:label="t2" xlink:href="a.xsd#a_Total"/>
        <link:loc xlink:type="locator" xlink:label="x" xlink:href="a.xsd#a_X"/>
        <link:presentationArc xlink:type="arc" xlink:from="t1" xlink:to="x"
          xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child" {first}/>
        <link:presentationArc xlink:type="arc" xlink:from="t2" xlink:to="x"
          xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child" {second}/>
      </link:presentationLink>
    </link:linkbase>""")
    tree = trees[ROLE]
    relationships = [(r.parent_id, r.child_id, r.order, r.preferred_label.rsplit("/", 1)[-1])
                     for r in tree.relationships]
    return relationships, tree.all_nodes["a_Total"].children


TERSE = f'order="1" preferredLabel="{LABEL}terseLabel"'


def test_equivalent_relationship_is_kept_once():
    assert network(TERSE, TERSE) == ([("a_Total", "a_X", 1.0, "terseLabel")], ["a_X"])


def test_distinct_order_or_label_keeps_both_relationships():
    order_only = network(TERSE, f'order="5" preferredLabel="{LABEL}terseLabel"')
    assert order_only == ([("a_Total", "a_X", 1.0, "terseLabel"), ("a_Total", "a_X", 5.0, "terseLabel")],
                          ["a_X"])

    label_only = network(TERSE, f'order="1" preferredLabel="{LABEL}verboseLabel"')
    assert label_only[0] == [("a_Total", "a_X", 1.0, "terseLabel"), ("a_Total", "a_X", 1.0, "verboseLabel")]

    both = network(TERSE, f'order="5" preferredLabel="{LABEL}verboseLabel"')
    assert both[0] == [("a_Total", "a_X", 1.0, "terseLabel"), ("a_Total", "a_X", 5.0, "verboseLabel")]
    # The statement view still shows the concept once (GH #825)
    assert both[1] == ["a_X"]


def test_roll_forward_pair_is_in_both_views():
    relationships, children = network(f'order="1" preferredLabel="{LABEL}periodStartLabel"',
                                      f'order="5" preferredLabel="{LABEL}periodEndLabel"')
    assert relationships == [("a_Total", "a_X", 1.0, "periodStartLabel"), ("a_Total", "a_X", 5.0, "periodEndLabel")]
    assert children == ["a_X", "a_X"]


def test_coca_cola_fy2011_long_term_debt_presented_twice():
    """Coca-Cola 10-K for FY2011, accession 0000021344-12-000007.

    ko-20120223_pre.xml, role DebtAndBorrowingArrangementsDetails: the parent
    us-gaap_DebtInstrumentLineItems presents us-gaap_LongTermDebt at order 21
    with totalLabel and again at order 30 with verboseLabel.
    """
    xbrl = XBRL.from_directory(Path("tests/fixtures/xbrl/ko/10k_2012"))
    tree = xbrl.presentation_trees["http://www.thecocacolacompany.com/role/DebtAndBorrowingArrangementsDetails"]
    long_term_debt = [(r.order, r.preferred_label) for r in tree.relationships
                      if r.parent_id == "us-gaap_DebtInstrumentLineItems" and r.child_id == "us-gaap_LongTermDebt"]
    assert long_term_debt == [(21.0, "http://www.xbrl.org/2003/role/totalLabel"),
                              (30.0, "http://www.xbrl.org/2003/role/verboseLabel")]
    assert tree.all_nodes["us-gaap_DebtInstrumentLineItems"].children.count("us-gaap_LongTermDebt") == 1
