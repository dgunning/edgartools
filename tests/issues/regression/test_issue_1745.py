"""Regression: a role split across several presentation links keeps every link's arcs.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1745

IMAX's FY2018 10-K (0001193125-19-052075) declares its cash-flow role in two
consecutive presentationLink elements: the first holds 56 arcs (operating,
investing and financing lines and the opening cash balance), the second holds
one arc, the closing cash balance. `PresentationParser` built a tree per link
and stored it with `presentation_trees[role] = tree`, so the one-arc link
replaced the 56-arc tree. The role was left with a single child relationship,
statement resolution found no cash-flow statement, and
`xbrl.statements.cash_flow_statement()` returned None.

The parser now collects every link's arcs per role and builds the tree once.
An arc repeated with the same endpoints, order and preferred label is kept once.

Ground truth is the filed statement (in thousands): net cash provided by operating
activities 109,972; investing (56,874); financing (70,862); cash at beginning of
year 158,725 and at end of year 141,590.
"""

import pytest

from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.parsers.presentation import PresentationParser

ROLE = "http://example.com/role/CashFlows"

SPLIT_ROLE_LINKBASE = f"""<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
               xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:presentationLink xlink:type="extended" xlink:role="{ROLE}">
    <link:loc xlink:type="locator" xlink:href="x.xsd#us-gaap_CashFlowAbstract" xlink:label="root"/>
    <link:loc xlink:type="locator" xlink:href="x.xsd#us-gaap_NetCashProvidedByUsedInOperatingActivities" xlink:label="ops"/>
    <link:loc xlink:type="locator" xlink:href="x.xsd#us-gaap_Cash" xlink:label="cash"/>
    <link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child"
        xlink:from="root" xlink:to="ops" order="1"/>
    <link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child"
        xlink:from="root" xlink:to="cash" order="2"
        preferredLabel="http://www.xbrl.org/2003/role/periodStartLabel"/>
  </link:presentationLink>
  <link:presentationLink xlink:type="extended" xlink:role="{ROLE}">
    <link:loc xlink:type="locator" xlink:href="x.xsd#us-gaap_CashFlowAbstract" xlink:label="root"/>
    <link:loc xlink:type="locator" xlink:href="x.xsd#us-gaap_Cash" xlink:label="cash"/>
    <link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child"
        xlink:from="root" xlink:to="cash" order="2"
        preferredLabel="http://www.xbrl.org/2003/role/periodStartLabel"/>
    <link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child"
        xlink:from="root" xlink:to="cash" order="3"
        preferredLabel="http://www.xbrl.org/2003/role/periodEndLabel"/>
  </link:presentationLink>
</link:linkbase>
"""


def test_later_link_of_a_role_does_not_replace_earlier_one():
    trees = {}
    PresentationParser({}, trees, {}, role_types={}).parse_presentation_content(SPLIT_ROLE_LINKBASE)

    root = trees[ROLE].all_nodes["us-gaap_CashFlowAbstract"]
    # Both links' arcs, with the periodStart arc repeated in the second link kept once.
    assert root.children == [
        "us-gaap_NetCashProvidedByUsedInOperatingActivities",
        "us-gaap_Cash",
        "us-gaap_Cash",
    ]
    assert root.child_preferred_labels == [
        None,
        "http://www.xbrl.org/2003/role/periodStartLabel",
        "http://www.xbrl.org/2003/role/periodEndLabel",
    ]


def test_period_arc_repeated_at_another_order_is_kept_once():
    # The second link repeats the opening-cash arc at order 1 instead of 2.
    linkbase = SPLIT_ROLE_LINKBASE.replace(
        'xlink:from="root" xlink:to="cash" order="2"\n        preferredLabel="http://www.xbrl.org/2003/role/periodStartLabel"/>\n'
        '    <link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child"\n'
        '        xlink:from="root" xlink:to="cash" order="3"',
        'xlink:from="root" xlink:to="cash" order="1"\n        preferredLabel="http://www.xbrl.org/2003/role/periodStartLabel"/>\n'
        '    <link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child"\n'
        '        xlink:from="root" xlink:to="cash" order="3"',
    )
    assert 'to="cash" order="1"' in linkbase
    trees = {}
    PresentationParser({}, trees, {}, role_types={}).parse_presentation_content(linkbase)

    root = trees[ROLE].all_nodes["us-gaap_CashFlowAbstract"]
    assert root.child_preferred_labels == [
        None,
        "http://www.xbrl.org/2003/role/periodStartLabel",
        "http://www.xbrl.org/2003/role/periodEndLabel",
    ]


IMAX_FOLDER ="https://www.sec.gov/Archives/edgar/data/921582/000119312519052075/"
IMAX_FILES = ("imax-20181231.xsd", "imax-20181231.xml", "imax-20181231_pre.xml", "imax-20181231_lab.xml")
IMAX_CASH_FLOW_ROLE = "http://imax.com/role/StatementConsolidatedStatementsOfCashFlows"
FY2018 = "duration_2018-01-01_2018-12-31"


@pytest.mark.vcr
def test_imax_fy2018_cash_flow_statement_is_found(tmp_path):
    """Ground truth: IMAX FY2018 10-K, 0001193125-19-052075, consolidated statements of cash flows."""
    for name in IMAX_FILES:
        (tmp_path / name).write_text(download_file(IMAX_FOLDER + name), encoding="utf-8")
    xbrl = XBRL.from_directory(tmp_path)

    tree = xbrl.presentation_trees[IMAX_CASH_FLOW_ROLE]
    assert sum(len(node.children) for node in tree.all_nodes.values()) == 57

    statement = xbrl.statements.cash_flow_statement()
    assert statement is not None
    values = {
        row["concept"]: row["values"].get(FY2018)
        for row in statement.get_raw_data()
        if not row.get("is_dimension")
    }
    assert values["us-gaap_NetCashProvidedByUsedInOperatingActivities"] == 109_972_000
    assert values["us-gaap_NetCashProvidedByUsedInInvestingActivities"] == -56_874_000
    assert values["us-gaap_NetCashProvidedByUsedInFinancingActivities"] == -70_862_000

    cash_rows = [
        row for row in statement.get_raw_data()
        if row["concept"] == "us-gaap_CashAndCashEquivalentsAtCarryingValue" and not row.get("is_dimension")
    ]
    assert [row["values"].get("instant_2017-12-31") for row in cash_rows] == [158_725_000, 158_725_000]
    assert [row["values"].get("instant_2018-12-31") for row in cash_rows] == [141_590_000, 141_590_000]
