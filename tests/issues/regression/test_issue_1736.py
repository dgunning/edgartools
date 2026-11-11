"""Regression: prohibited and overridden relationships stay out of every linkbase network.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1736

XBRL 2.1 section 3.5.3.9.7 decides which arcs become relationships: within a
base set, equivalent relationships (same endpoints, S-Equal non-exempt
attributes) are resolved by priority, a prohibiting arc (use="prohibited") is
never in the network, and a prohibiting arc at the highest priority removes
every equivalent relationship. The calculation, presentation, definition and
label parsers read `use` and `priority` nowhere, so a prohibited relationship
stayed in the calculation tree, the presentation tree, the domain members and
the element's labels.

All four parsers now record each arc as a candidate and keep only the effective
relationships (`edgar/xbrl/parsers/relationships.py`).

Real filing: Travelers' 10-Q/A for Q2 2009 (accession 0001104659-09-047320)
extends the 2008 US-GAAP statement templates and prohibits the template
relationships it does not use: 23 calculation arcs and 1,466 presentation arcs.
A prohibiting arc carries both endpoints, so main read each one as the very
relationship it removes. Its calculation linkbase gained an
OperatingCostsAndExpenses -> InterestExpense summation the filer prohibited, and
its presentation linkbase rebuilt the template balance sheet (245 rows), which
statement resolution then chose over Travelers' own 36-row balance sheet.
"""

from pathlib import Path

import pytest

from edgar.xbrl.parsers.calculation import CalculationParser
from edgar.xbrl.parsers.definition import DefinitionParser
from edgar.xbrl.parsers.labels import LabelsParser
from edgar.xbrl.parsers.presentation import PresentationParser

ROLE = "http://example.com/role/R"
OTHER_ROLE = "http://example.com/role/Other"
NS = ('xmlns:link="http://www.xbrl.org/2003/linkbase" '
      'xmlns:xlink="http://www.w3.org/1999/xlink"')
ARCROLES = {
    "calculation": "http://www.xbrl.org/2003/arcrole/summation-item",
    "presentation": "http://www.xbrl.org/2003/arcrole/parent-child",
    "definition": "http://xbrl.org/int/dim/arcrole/domain-member",
    "label": "http://www.xbrl.org/2003/arcrole/concept-label",
}


def linkbase(kind, attributes, role=ROLE):
    """One extended link of `kind` with one arc a_Total -> X per attribute string.

    Each arc starts from its own locator, all pointing at the same concept, so
    the arcs are not XLink duplicates of one another but their relationships
    are equivalent apart from the attributes given.
    """
    extra = ' weight="1"' if kind == "calculation" else ""
    arcs = "".join(
        f'<link:{kind}Arc xlink:type="arc" xlink:from="t{i}" xlink:to="x" '
        f'xlink:arcrole="{ARCROLES[kind]}"{extra} {attrs}/>'
        for i, attrs in enumerate(attributes, 1))
    locators = "".join(
        f'<link:loc xlink:type="locator" xlink:label="t{i}" xlink:href="a.xsd#a_Total"/>'
        for i in range(1, len(attributes) + 1))
    if kind == "label":
        target = ('<link:label xlink:type="resource" xlink:label="x" '
                  'xlink:role="http://www.xbrl.org/2003/role/label" '
                  'xml:lang="en-US">Visible label</link:label>')
    else:
        target = '<link:loc xlink:type="locator" xlink:label="x" xlink:href="a.xsd#a_X"/>'
    return (f'<link:linkbase {NS}><link:{kind}Link xlink:type="extended" '
            f'xlink:role="{role}">{locators}{target}{arcs}'
            f'</link:{kind}Link></link:linkbase>')


def calculation_edges(*contents):
    trees = {}
    parser = CalculationParser({}, trees, {}, {})
    for content in contents:
        parser.parse_calculation_content(content)
    return [(a.parent_id, a.child_id, a.weight) for tree in trees.values() for a in tree.all_arcs]


def presentation_children(*contents):
    trees = {}
    parser = PresentationParser({}, trees, {})
    for content in contents:
        parser.parse_presentation_content(content)
    return trees[ROLE].all_nodes["a_Total"].children if ROLE in trees else []


def domain_members(*contents):
    parser = DefinitionParser({}, {}, {}, {}, {})
    for content in contents:
        parser.parse_definition_content(content)
    domain = parser.domains_for_role(ROLE).get("a_Total")
    return domain.members if domain else []


def labels(content):
    catalog = {}
    LabelsParser(catalog).parse_labels_content(content)
    return catalog["a_Total"].labels if "a_Total" in catalog else {}


# (name, arc attributes, whether a_Total -> a_X is in the network), per
# XBRL 2.1 section 3.5.3.9.7.5 rules i-iv
CASES = [
    ("optional", ['use="optional" priority="0"'], True),
    ("lone prohibiting arc", ['use="prohibited" priority="1"'], False),
    ("prohibited by higher priority", ['use="optional" priority="0"', 'use="prohibited" priority="1"'], False),
    ("prohibited at equal priority", ['use="optional" priority="1"', 'use="prohibited" priority="1"'], False),
    ("overrides lower prohibition", ['use="prohibited" priority="0"', 'use="optional" priority="1"'], True),
    ("below a higher prohibition", ['use="prohibited" priority="2"', 'use="optional" priority="1"'], False),
    ("default priority is 0", ['', 'use="prohibited"'], False),
]


@pytest.mark.parametrize("name, attributes, included", CASES, ids=[case[0] for case in CASES])
def test_prohibition_and_overriding_in_every_parser(name, attributes, included):
    attributes = [f'order="1" {attrs}' for attrs in attributes]
    assert calculation_edges(linkbase("calculation", attributes)) == (
        [("a_Total", "a_X", 1.0)] if included else [])
    assert presentation_children(linkbase("presentation", attributes)) == (["a_X"] if included else [])
    assert domain_members(linkbase("definition", attributes)) == (["a_X"] if included else [])
    assert labels(linkbase("label", attributes)) == (
        {"http://www.xbrl.org/2003/role/label": "Visible label"} if included else {})


def test_prohibition_needs_an_equivalent_relationship():
    # order is non-exempt, so a prohibiting arc at another order does not touch
    # the optional one (section 3.5.3.9.7.4) ...
    different_order = ['order="1" use="optional"', 'order="2" use="prohibited" priority="1"']
    assert presentation_children(linkbase("presentation", different_order)) == ["a_X"]
    assert calculation_edges(linkbase("calculation", different_order)) == [("a_Total", "a_X", 1.0)]

    # ... but order is compared as a decimal, and an absent order is 1 (3.5.3.9.5)
    same_order = ['order="1.0000" use="optional"', 'use="prohibited" priority="1"']
    assert presentation_children(linkbase("presentation", same_order)) == []
    assert calculation_edges(linkbase("calculation", same_order)) == []

    # weight is non-exempt on a calculation arc
    weights = ['order="1" weight="-1" use="prohibited" priority="1"']
    content = linkbase("calculation", ['order="1"']).replace(
        "</link:calculationLink>",
        '<link:loc xlink:type="locator" xlink:label="t9" xlink:href="a.xsd#a_Total"/>'
        '<link:calculationArc xlink:type="arc" xlink:from="t9" xlink:to="x" '
        'xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item" '
        f'{weights[0]}/></link:calculationLink>')
    assert calculation_edges(content) == [("a_Total", "a_X", 1.0)]


def test_prohibition_is_scoped_to_its_base_set():
    optional = linkbase("calculation", ['order="1"'])
    prohibiting_elsewhere = linkbase("calculation", ['order="1" use="prohibited" priority="1"'], role=OTHER_ROLE)
    assert calculation_edges(optional, prohibiting_elsewhere) == [("a_Total", "a_X", 1.0)]


def test_prohibition_in_a_later_file_applies():
    """Calculation and definition networks span every linkbase read, so a
    prohibiting arc in a later file removes a relationship from an earlier one."""
    optional = ['order="1"']
    prohibiting = ['order="1" use="prohibited" priority="1"']
    assert calculation_edges(linkbase("calculation", optional), linkbase("calculation", prohibiting)) == []
    assert domain_members(linkbase("definition", optional), linkbase("definition", prohibiting)) == []
    # and re-reading the optional file afterwards does not bring it back
    assert calculation_edges(linkbase("calculation", optional), linkbase("calculation", prohibiting),
                             linkbase("calculation", optional)) == []


def test_specification_example_6():
    """XBRL 2.1 section 3.5.3.9.7.5, example 6: arcs A..E added one at a time."""
    from edgar.xbrl.parsers.relationships import effective_relationships

    def candidate(name, prohibiting, priority):
        return {"name": name, "equivalence": "same", "prohibiting": prohibiting, "priority": priority}

    a = candidate("A", False, 1)
    b = candidate("B", True, 2)
    c = candidate("C", True, 3)
    d = candidate("D", False, 4)
    e = candidate("E", False, 4)
    assert effective_relationships([a, b]) == []
    assert effective_relationships([a, b, c]) == []
    assert effective_relationships([a, b, c, d]) == [d]
    assert [r["name"] for r in effective_relationships([a, b, c, d, e])] == ["D"]


TRV_CAL = Path("tests/fixtures/xbrl/trv/10qa_2009q2/trv-20090630_cal.xml")
TRV_INSURANCE_INCOME = "http://xbrl.us/us-gaap/role/statement/StatementOfIncomeInsuranceBasedRevenue"


def test_travelers_prohibited_template_calculations_are_removed():
    """Travelers 10-Q/A, Q2 2009, accession 0001104659-09-047320, trv-20090630_cal.xml.

    The file has 201 summation-item arcs, 23 of them prohibiting arcs with no
    equivalent optional arc in the file, so 178 relationships remain.
    """
    trees = {}
    CalculationParser({}, trees, {}, {}).parse_calculation(TRV_CAL)
    assert sum(len(tree.all_arcs) for tree in trees.values()) == 178

    edges = {(a.parent_id, a.child_id): a.weight for a in trees[TRV_INSURANCE_INCOME].all_arcs}
    # prohibited by the filer
    assert ("us-gaap_OperatingCostsAndExpenses", "us-gaap_InterestExpense") not in edges
    assert ("us-gaap_InterestExpense", "us-gaap_InterestExpenseDebt") not in edges
    assert ("us-gaap_SellingGeneralAndAdministrativeExpense", "us-gaap_GeneralAndAdministrativeExpense") not in edges
    # what the filer put in their place
    assert edges[("us-gaap_BenefitsLossesAndExpenses", "us-gaap_InterestExpense")] == 1.0
    assert edges[("us-gaap_BenefitsLossesAndExpenses", "us-gaap_InterestExpenseDebt")] == 1.0
    assert edges[("us-gaap_BenefitsLossesAndExpenses", "us-gaap_GeneralAndAdministrativeExpense")] == 1.0


@pytest.mark.network
def test_travelers_balance_sheet_is_the_filers_own():
    from edgar import find
    from edgar.xbrl import XBRL

    xbrl = XBRL.from_filing(find("0001104659-09-047320"))
    balance_sheet = xbrl.statements.balance_sheet()
    assert balance_sheet.role_or_type == "http://www.trv.com/role/statement/StatementOfFinancialPosition"
    df = balance_sheet.to_dataframe()
    assert len(df) == 36
    total_assets = df.loc[df["concept"] == "us-gaap_Assets", "2009-06-30"].iloc[0]
    assert total_assets == 111_326_000_000
