"""Regression test for GH #1670: the standard view kept note breakdowns on face statements.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1670

IFRS filers such as SAP file no hypercube for their face statements, so the
definition linkbase cannot say which axes a statement prints and the
axis-name heuristic decided. Note axes it does not list (business
combinations, subsidiaries, components of equity on the cash flow) stayed in
the standard view. The role's presentation tree lists every axis the
statement prints, so an axis it does not present is now a breakdown.

Ground truth: SAP 20-F FY2025 (0001104659-26-020058), consolidated statement
of cash flows: 42 printed lines carry a 2025 value; the standard view had 96
rows, 48 of them dimensional (including "Ariba Technologies India Private
Limited" on SignificantInvestmentsInSubsidiariesAxis).
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from edgar import find
from edgar.xbrl import XBRL
from edgar.xbrl.dimensions import is_breakdown_dimension
from edgar.xbrl.models import PresentationNode

NVDA_10K = Path("tests/fixtures/xbrl/nvda/10k_2026")


class _Stub:
    def __init__(self, presented):
        self.presented = presented

    def has_definition_linkbase_for_role(self, role_uri):
        return False

    def presented_axes_for_role(self, role_uri):
        return self.presented


def _item(axis):
    return {"is_dimension": True, "dimension_metadata": [{"dimension": axis, "member": "x:YMember"}]}


@pytest.mark.fast
def test_presentation_tree_decides_when_there_is_no_definition_linkbase():
    presented = _Stub({"ifrs-full_ComponentsOfEquityAxis": True})
    assert not is_breakdown_dimension(_item("ifrs-full:ComponentsOfEquityAxis"), xbrl=presented, role_uri="r")
    assert is_breakdown_dimension(_item("ifrs-full:BusinessCombinationsAxis"), xbrl=presented, role_uri="r")
    # A face axis on the heuristic list is a breakdown once the tree does not present it ...
    assert is_breakdown_dimension(_item("srt:ProductOrServiceAxis"), xbrl=presented, role_uri="r")
    # ... and with no presentation tree for the role the heuristic still decides.
    assert not is_breakdown_dimension(_item("srt:ProductOrServiceAxis"), xbrl=_Stub(None), role_uri="r")


def _role_presenting(nodes):
    xbrl = XBRL()
    tree = SimpleNamespace(all_nodes={node_id: PresentationNode(element_id=node_id, children=children)
                                      for node_id, children in nodes.items()})
    xbrl.parser.presentation_trees = {"r": tree}
    return xbrl


@pytest.mark.fast
def test_an_axis_presented_with_only_its_domain_falls_back_to_the_heuristic():
    # A face role with no hypercube that shows StatementClassOfStockAxis with
    # its domain alone, as Disney and Coca-Cola do for LegalEntityAxis and
    # StatementScenarioAxis: the axis is presented, so its rows are not dropped
    # wholesale, and the heuristic (a class of stock is a face axis) keeps them.
    xbrl = _role_presenting({
        "us-gaap_StatementTable": ["us-gaap_StatementClassOfStockAxis", "us-gaap_StatementLineItems"],
        "us-gaap_StatementClassOfStockAxis": ["us-gaap_ClassOfStockDomain"],
        "us-gaap_ClassOfStockDomain": [],
        "us-gaap_StatementLineItems": ["us-gaap_CommonStockSharesOutstanding"],
        "us-gaap_CommonStockSharesOutstanding": [],
    })
    assert xbrl.presented_axes_for_role("r") == {"us-gaap_StatementClassOfStockAxis": False}
    class_a = {"is_dimension": True, "dimension_metadata": [
        {"dimension": "us-gaap:StatementClassOfStockAxis", "member": "us-gaap:CommonClassAMember"}]}
    assert not is_breakdown_dimension(class_a, xbrl=xbrl, role_uri="r")
    # An axis the role does not present at all is still a breakdown.
    segment = {"is_dimension": True, "dimension_metadata": [
        {"dimension": "us-gaap:StatementBusinessSegmentsAxis", "member": "x:AMember"}]}
    assert is_breakdown_dimension(segment, xbrl=xbrl, role_uri="r")


@pytest.mark.fast
def test_nvidia_income_statement_standard_view_drops_note_revenue_rows():
    # The fixture has no hypercube for this role and its tree presents no axis;
    # the revenue-by-product rows (Data Center, Gaming, ...) come from the segment note.
    statement = XBRL.from_directory(NVDA_10K).statements.income_statement()
    assert int(statement.to_dataframe(view="standard").dimension.sum()) == 0
    detailed = statement.to_dataframe(view="detailed")
    assert "Data Center" in detailed.loc[detailed.dimension, "label"].tolist()


@pytest.mark.network
def test_sap_cash_flow_standard_view_is_the_printed_face():
    df = find("0001104659-26-020058").xbrl().statements.cash_flow_statement().to_dataframe(view="standard")
    assert int(df.dimension.sum()) == 0  # was 48
    period = next(c for c in df.columns if str(c).startswith("2025-12-31"))
    assert int(df[period].notna().sum()) == 42
