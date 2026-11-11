"""Regression test for GH #1838: a table-first primary income statement was left untyped.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1838

``XBRL.get_all_statements()`` typed a role by its first presentation node only.
STERIS presents its income statement under ``us-gaap:StatementTable``, with
``us-gaap:IncomeStatementAbstract`` beneath ``us-gaap:StatementLineItems``, so
the face role had no type. ``Statements.get("IncomeStatement")`` then fell to a
role-name match on a segment disclosure, and ``get_statement_facts`` returned no
rows. A role declared a statement (FilingSummary menu "Statements", or the
schema definition's "Statement" category when there is no summary) is now typed
by the abstract under its line items; ``primary_concept`` stays the literal
first node.

Ground truth: STERIS plc 10-Q, Q1 fiscal 2027 (0001628280-26-054830), R4
"CONSOLIDATED STATEMENTS OF INCOME": revenues for April 1 - June 30, 2026 are
1,492,700 (USD thousands) = 1,492,700,000 USD.
"""
import pytest

from edgar import find
from edgar.xbrl.models import PresentationNode, PresentationTree
from edgar.xbrl.xbrl import _statement_typing_concept

FACE_ROLE = "http://www.steris.com/role/CONSOLIDATEDSTATEMENTSOFINCOME"


def _table_first_tree(definition: str) -> PresentationTree:
    nodes = {
        "us-gaap_StatementTable": PresentationNode(
            element_id="us-gaap_StatementTable",
            children=["srt_ProductOrServiceAxis", "us-gaap_StatementLineItems"]),
        "srt_ProductOrServiceAxis": PresentationNode(element_id="srt_ProductOrServiceAxis",
                                                     parent="us-gaap_StatementTable"),
        "us-gaap_StatementLineItems": PresentationNode(
            element_id="us-gaap_StatementLineItems", parent="us-gaap_StatementTable",
            children=["us-gaap_IncomeStatementAbstract"]),
        "us-gaap_IncomeStatementAbstract": PresentationNode(
            element_id="us-gaap_IncomeStatementAbstract", parent="us-gaap_StatementLineItems",
            children=["us-gaap_Revenues"]),
        "us-gaap_Revenues": PresentationNode(element_id="us-gaap_Revenues",
                                             parent="us-gaap_IncomeStatementAbstract"),
    }
    return PresentationTree(role_uri=FACE_ROLE, definition=definition,
                            root_element_id="us-gaap_StatementTable",
                            root_element_ids=["us-gaap_StatementTable"], all_nodes=nodes)


@pytest.mark.fast
def test_declared_statement_is_typed_by_the_abstract_under_its_line_items():
    tree = _table_first_tree("9952153 - Statement - CONSOLIDATED STATEMENTS OF INCOME")
    # No FilingSummary: the schema definition's category declares the statement.
    assert _statement_typing_concept(tree, None) == "us-gaap_IncomeStatementAbstract"
    assert _statement_typing_concept(tree, "Statements") == "us-gaap_IncomeStatementAbstract"


@pytest.mark.fast
def test_a_disclosure_is_not_typed_through_its_line_items():
    # A standard abstract inside a disclosure is not enough by itself.
    disclosure = _table_first_tree("9955537 - Disclosure - Business Segment Information (Details)")
    assert _statement_typing_concept(disclosure, None) == "us-gaap_StatementTable"
    # An explicit non-statement menu is not overridden by the definition.
    statement_def = _table_first_tree("9952153 - Statement - CONSOLIDATED STATEMENTS OF INCOME")
    assert _statement_typing_concept(statement_def, "Details") == "us-gaap_StatementTable"


@pytest.mark.network
def test_steris_face_income_statement_is_cataloged_and_reached():
    xbrl = find("0001628280-26-054830").xbrl()
    entry = next(s for s in xbrl.get_all_statements() if s["role"] == FACE_ROLE)
    assert entry["type"] == "IncomeStatement"  # was None
    assert entry["primary_concept"] == "us-gaap_StatementTable"  # still the literal first node

    # Was the BusinessSegmentInformationIncomeStatementDetails disclosure.
    assert xbrl.statements.get("IncomeStatement").role_or_type == FACE_ROLE
    assert xbrl.statements.income_statement().role_or_type == FACE_ROLE

    facts = xbrl.facts.get_statement_facts("IncomeStatement")  # was 0 rows
    revenue = facts[(facts["concept"] == "us-gaap:Revenues") & (facts["period_start"] == "2026-04-01")
                    & (facts["period_end"] == "2026-06-30") & (~facts["is_dimensioned"].astype(bool))]
    assert set(revenue["numeric_value"]) == {1_492_700_000.0}
