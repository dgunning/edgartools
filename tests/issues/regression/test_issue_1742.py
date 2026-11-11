"""Regression: the calculation parser reads xlink:arcrole.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1742

`CalculationParser` read every calculationArc without looking at its arcrole
and kept the first arc per (role, parent, child). So an arc with a foreign
arcrole was taken for a summation, and of a 2003 summation-item arc and a 2023
(Calculations 1.1) summation-item arc between the same concepts in one role
only the first survived, although the two are separate networks (different
base sets, XBRL 2.1 section 3.5.3.9.7.3). `CalculationArc` stored no arcrole,
so no caller could tell the two apart.

Only the two summation-item arcroles now build calculations, each network
keeps its own relationships, and every `CalculationArc` records its arcrole.

Out of scope here and left as filed: two arcs in ONE network with the same
endpoints and different weights still keep the first, and a missing weight
still reads as 1.0.
"""

from pathlib import Path

from edgar.xbrl import XBRL
from edgar.xbrl.parsers.calculation import CalculationParser

A03 = "http://www.xbrl.org/2003/arcrole/summation-item"
A23 = "https://xbrl.org/2023/arcrole/summation-item"
OTHER = "http://example.com/arcrole/other"
ROLE = "http://x/role/IS"


def calculation(arcs):
    locs = "".join(
        f'<link:loc xlink:type="locator" xlink:label="{c}" xlink:href="x.xsd#us-gaap_{c}"/>'
        for c in ["OI", "Revenues", "CostOfRevenue", "Other"])
    body = "".join(
        f'<link:calculationArc xlink:type="arc" xlink:arcrole="{arcrole}" xlink:from="OI" '
        f'xlink:to="{to}" weight="{weight}"/>'
        for arcrole, to, weight in arcs)
    xml = ('<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" '
           'xmlns:xlink="http://www.w3.org/1999/xlink">'
           f'<link:calculationLink xlink:type="extended" xlink:role="{ROLE}">{locs}{body}'
           '</link:calculationLink></link:linkbase>')
    trees = {}
    CalculationParser({}, trees, {}, {}).parse_calculation_content(xml)
    return [(a.child_id, a.weight, a.arcrole) for a in trees[ROLE].all_arcs] if ROLE in trees else []


def test_foreign_arcrole_is_not_a_summation():
    assert calculation([(OTHER, "Other", "1")]) == []
    assert calculation([(OTHER, "Other", "1"), (A23, "Revenues", "1")]) == [
        ("us-gaap_Revenues", 1.0, A23)]


def test_each_summation_arcrole_keeps_its_own_relationship():
    # Same parent and child in one role under both arcroles: two networks, two
    # relationships, whichever comes first.
    both = [("us-gaap_Revenues", 1.0, A03), ("us-gaap_Revenues", -1.0, A23)]
    assert calculation([(A03, "Revenues", "1"), (A23, "Revenues", "-1")]) == both
    assert calculation([(A23, "Revenues", "-1"), (A03, "Revenues", "1")]) == both[::-1]


def test_arcrole_is_recorded():
    assert calculation([(A03, "Revenues", "1"), (A23, "CostOfRevenue", "-1")]) == [
        ("us-gaap_Revenues", 1.0, A03), ("us-gaap_CostOfRevenue", -1.0, A23)]


def test_nike_fy2026_calculations_are_calculations_1_1():
    """NIKE, Inc. 10-K for FY ended 2026-05-31, accession 0000320187-26-000088.

    nke-20260531_cal.xml files all 161 calculation arcs with the 2023
    arcrole; on the income statement, gross profit is revenue less cost of
    sales (weight -1).
    """
    xbrl = XBRL.from_directory(Path("tests/fixtures/xbrl/nke/10k_2026"))
    arcs = [arc for tree in xbrl.calculation_trees.values() for arc in tree.all_arcs]
    assert len(arcs) == 161
    assert {arc.arcrole for arc in arcs} == {A23}

    income = xbrl.calculation_trees["http://www.nike.com/role/CONSOLIDATEDSTATEMENTSOFINCOME"]
    gross_profit = [(arc.child_id, arc.weight) for arc in income.all_arcs
                    if arc.parent_id == "us-gaap_GrossProfit"]
    assert gross_profit == [("us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax", 1.0),
                            ("us-gaap_CostOfGoodsAndServicesSold", -1.0)]
