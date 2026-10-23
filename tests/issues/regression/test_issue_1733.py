"""ConceptGraph.validate() reported cash-flow subtotals that foot as not footing.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1733

Two defects in the same check, both making a statement that foots fail:

1. R*.htm shows a row presented with a negated label role with its sign
   flipped, and validate() multiplied that display number by the calculation
   weight, flipping it a second time. MetaLinks.json carries each role's label
   text, so the row label now identifies a negated role and the sign is undone.
2. Every value came from the concept's first row across all reports, so net
   income in the six-month cash flow was the income statement's three-month
   value. Values are now read from the report being validated.

Ground truth: Apple 10-Q for the quarter ended 2025-03-29, accession
0000320193-25-000057 (fixture tests/fixtures/attachments/aapl/20250329).
Fact f-326, us-gaap:PaymentsToAcquireAvailableForSaleSecuritiesDebt, is
+12,442 (millions) with weight -1.0 into net cash from investing activities of
12,709; R7 shows it as (12,442). Before the fix 5 of 19 checks failed
(investing computed 50,885); after, all 19 foot.
"""
import re
from pathlib import Path

import pytest

from edgar.sgml.concept_extractor import extract_concepts_from_report
from edgar.sgml.metalinks import MetaLinks
from edgar.xbrl.concept_graph import ConceptGraph

pytestmark = pytest.mark.fast

FIXTURE = Path("tests/fixtures/attachments/aapl/20250329")


@pytest.fixture(scope="module")
def graph():
    metalinks = MetaLinks.parse((FIXTURE / "MetaLinks.json").read_text())
    r_files = sorted(FIXTURE.glob("R*.htm"), key=lambda p: int(re.sub(r"\D", "", p.stem)))
    reports = {p.stem: extract_concepts_from_report(p.read_text()) for p in r_files}
    return ConceptGraph.build(metalinks, reports)


@pytest.fixture(scope="module")
def results(graph):
    return {r["parent"].id: r for r in graph.validate()}


def test_every_statement_check_foots(results):
    assert len(results) == 19
    failed = [cid for cid, r in results.items() if not r["valid"]]
    assert failed == []


def test_investing_uses_fact_sign_not_display_sign(results):
    investing = results["us-gaap_NetCashProvidedByUsedInInvestingActivities"]
    assert investing["expected"] == 12709.0
    assert investing["computed"] == pytest.approx(12709.0)


def test_operating_reads_net_income_from_the_cash_flow_report(results):
    operating = results["us-gaap_NetCashProvidedByUsedInOperatingActivities"]
    assert operating["expected"] == 53887.0
    assert operating["computed"] == pytest.approx(53887.0)


def test_negated_row_fact_value(graph):
    concept = graph["us-gaap_PaymentsToAcquireAvailableForSaleSecuritiesDebt"]
    assert concept.value == "(12,442)"           # display value is unchanged
    assert concept.numeric_value == -12442.0
    assert concept._fact_numeric_value("R7") == 12442.0
    assert concept._tag.role_labels["negatedLabel"] == "Purchases of marketable securities"


def test_concept_absent_from_validated_report_has_no_value_there(graph):
    # The AFS purchase line is presented only in the cash flow (R7). Read for the
    # income statement (R4) it must not borrow R7's number.
    concept = graph["us-gaap_PaymentsToAcquireAvailableForSaleSecuritiesDebt"]
    assert concept._fact_numeric_value("R4") is None
    assert concept._fact_numeric_value("R999") is None


def test_negated_label_match_ignores_entities_and_case(graph):
    from dataclasses import replace

    from edgar.xbrl.concept_graph import Concept

    original = graph["us-gaap_PaymentsToAcquireAvailableForSaleSecuritiesDebt"]
    tag = replace(original._tag, role_labels={
        "label": "Payments to Acquire Debt Securities, Available-for-Sale",
        "negatedLabel": "PURCHASES&#32;of  marketable securities",
    })
    assert Concept(tag, graph)._fact_numeric_value("R7") == 12442.0
