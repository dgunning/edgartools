"""Regression: a statement row's calculation weight and parent come from its own role only.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1702

When a concept had no arc in the statement role's calculation network,
`XBRL._generate_line_items` looped over every calculation tree and took the
first node's weight and parent, and the Facts API's `_get_primary_weight` did the
same through keyword-matched and then arbitrary roles. Sonoco's 10-Q
(0000091767-26-000022) presents us-gaap:WeightedAverageNumberOfSharesOutstandingBasic
on its income statement, whose calculation role has no arc for it; the only arc is
in the EPS details note, weight 1.0 under WeightedAverageNumberOfDilutedSharesOutstanding,
and the income-statement row reported exactly that.

A calculation relationship belongs to its extended link role (XBRL 2.1 section
3.5.3.9.7.3). Rows and facts assigned to a statement now read only that role's
network; a concept with no arc there has weight and calculation_parent None.
"""

import math

import pytest

from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.models import CalculationNode, CalculationTree
from tests._synthetic_xbrl import NOTE, OPS, write_two_role_filing

SON_FOLDER = "https://www.sec.gov/Archives/edgar/data/91767/000009176726000022/"
SON_FILES = ("son-20260329.xsd", "son-20260329_htm.xml", "son-20260329_pre.xml",
             "son-20260329_lab.xml", "son-20260329_cal.xml")
INCOME_ROLE = "http://sonoco.com/role/CONDENSEDCONSOLIDATEDSTATEMENTSOFINCOMEunaudited"
BASIC_SHARES = "us-gaap_WeightedAverageNumberOfSharesOutstandingBasic"
COST_OF_SALES = "us-gaap_CostOfGoodsAndServicesSold"


@pytest.mark.vcr
def test_sonoco_income_statement_rows_do_not_borrow_another_roles_calculation(tmp_path):
    """Ground truth: Sonoco 10-Q, 0000091767-26-000022, son-20260329_cal.xml."""
    for name in SON_FILES:
        (tmp_path / name).write_text(download_file(SON_FOLDER + name), encoding="utf-8")
    xbrl = XBRL.from_directory(tmp_path)
    assert xbrl.find_statement("IncomeStatement")[1] == INCOME_ROLE

    # The EPS note does hold an arc for the share count ...
    eps_roles = [role for role, tree in xbrl.calculation_trees.items() if BASIC_SHARES in tree.all_nodes]
    assert [role.rsplit("/", 1)[-1] for role in eps_roles] == ["ShareholdersEquityScheduleofEarningsPerShareDetails"]
    assert BASIC_SHARES not in xbrl.calculation_trees[INCOME_ROLE].all_nodes

    rows = {}
    for item in xbrl.get_statement(INCOME_ROLE):
        if not item.get("is_dimension"):
            rows.setdefault(item["concept"], item)
    # ... but the income statement's row is not part of any income-statement summation.
    assert rows[BASIC_SHARES]["label"] == "Basic (in shares)"
    assert rows[BASIC_SHARES]["weight"] is None
    assert rows[BASIC_SHARES]["calculation_parent"] is None
    # A row the income statement's own network does sum keeps its arc: cost of sales
    # is subtracted from gross profit (weight -1.0).
    assert rows[COST_OF_SALES]["weight"] == -1.0
    assert rows[COST_OF_SALES]["calculation_parent"] == "us-gaap_GrossProfit"

    df = xbrl.statements.income_statement().to_dataframe()
    basic = df[df["concept"] == BASIC_SHARES].iloc[0]
    assert math.isnan(basic["weight"])
    cost = df[df["concept"] == COST_OF_SALES].iloc[0]
    assert cost["weight"] == -1.0

    facts = xbrl.facts.query().by_concept(BASIC_SHARES, exact=True).to_dataframe()
    assert set(facts["statement_type"]) == {"IncomeStatement"}
    assert facts["weight"].isna().all()


class _StubXBRL:
    def __init__(self, calculation_trees):
        self.calculation_trees = calculation_trees


def _tree(role, element_id, weight, parent):
    return CalculationTree(
        role_uri=role, definition=role, root_element_id=parent,
        all_nodes={element_id: CalculationNode(element_id=element_id, weight=weight, parent=parent)},
    )


def test_facts_weight_reads_only_the_assigned_statement_role():
    from edgar.xbrl.facts import FactsView

    note = "http://example.com/role/IncomeTaxDetails"
    income = "http://example.com/role/StatementOfIncome"
    view = FactsView.__new__(FactsView)
    view.xbrl = _StubXBRL({
        note: _tree(note, "us-gaap_Foo", -1.0, "us-gaap_Bar"),
        income: _tree(income, "us-gaap_Baz", 1.0, "us-gaap_Qux"),
    })
    # Assigned to the income statement, whose network has no arc for the concept.
    assert view._get_primary_weight("us-gaap_Foo", "IncomeStatement", income) is None
    assert view._get_primary_weight("us-gaap_Baz", "IncomeStatement", income) == 1.0
    # Unassigned facts still take the first weight found.
    assert view._get_primary_weight("us-gaap_Foo", None, None) == -1.0


def test_statement_row_without_an_arc_in_its_role_has_no_weight_or_parent(tmp_path):
    """Offline: the share count's only calculation arc is in the note role."""
    write_two_role_filing(tmp_path)
    xbrl = XBRL.from_directory(tmp_path)
    assert BASIC_SHARES in xbrl.calculation_trees[NOTE].all_nodes
    assert BASIC_SHARES not in xbrl.calculation_trees[OPS].all_nodes

    rows = {item["concept"]: item for item in xbrl.get_statement(OPS)}
    assert rows[BASIC_SHARES]["weight"] is None
    assert rows[BASIC_SHARES]["calculation_parent"] is None
    # The income statement's own arcs are still read.
    assert rows["us-gaap_InterestExpenseDebt"]["weight"] == -1.0
    assert rows["us-gaap_InterestExpenseDebt"]["calculation_parent"] == "us-gaap_NetIncomeLoss"
