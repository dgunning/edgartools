"""Regression: non-accrual footnotes linked to subtotals, and links looser than the printed marks.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1959
Bead: edgartools-pjlj5.1

Since edgartools-jv8b8 (#1928), a non-accrual footnote linked to any instant
cell of a row stands for that row's fair value, which recovered New Mountain's
and Sixth Street's non-accruals. Trinity Capital also links its footnote to the
cost and principal of two subtotals, "Portfolio Company Debt Securities- United
States" and "... United States Transportation Technology", so its Q1 2025 10-Q
read $1,849,193,000 at cost where it tags trin:NonAccrualCost = $49,700,000.
Identifier-axis members carry no hierarchy; a row is now read as a subtotal
and left out when two or more rows filed under its name add up to its fair
value within 5%.

Filers also link the footnote to holdings their printed schedule does not mark.
Sixth Street links it to a Varinem loan marked (3)(4) exactly as to an ASP
Unifrax note marked (14) "Investment is on non-accrual status", so no rule over
the links can separate them. Across 124 filings of 31 BDCs, 6.1 added about 52
real non-accruals and 18 false ones this way. The false holdings stay, and the
result warns when it disagrees with a non-accrual total or loan count the filer
tags. The fixtures are real fact rows; see tests/fixtures/bdc/nonaccrual_1959.
"""
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from edgar.bdc.nonaccrual import _extract_nonaccrual_from_xbrl

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "bdc" / "nonaccrual_1959"
TRIN = "trin_10q_0000950170-25-065028.json"
BXSL = "bxsl_10k_0001736035-26-000004.json"
US = "Portfolio Company Debt Securities- United States"
US_TRANSPORTATION = "Portfolio Company Debt Securities- United States Transportation Technology"


def _read(name):
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    footnotes = {fn["id"]: SimpleNamespace(text=fn["text"], lang=fn["lang"], related_fact_ids=fn["related_fact_ids"])
                 for fn in data["footnotes"]}
    xbrl = SimpleNamespace(footnotes=footnotes, element_catalog={})
    return _extract_nonaccrual_from_xbrl(xbrl, period=data["period"], all_facts=data["facts"])


@pytest.fixture(scope="module")
def trin():
    return _read(TRIN)


def test_trinity_subtotals_flagged_on_their_cost_are_not_holdings(trin):
    identifiers = {inv.identifier for inv in trin.investments}
    assert US not in identifiers
    assert US_TRANSPORTATION not in identifiers
    assert len(trin.investments) == 19
    # The issue's figure for "dropping the subtotals alone": $1,637,052,000 and
    # $64,811,000 of subtotal cost no longer count.
    assert sum(inv.cost for inv in trin.investments) == Decimal("147330000")


def test_trinity_warns_against_the_total_it_tags(trin):
    assert trin.extraction_method == "footnote"
    [warning] = trin.warnings
    assert "trin:NonAccrualCost = $49,700,000 at 2025-03-31" in warning
    assert "$147,330,000 at cost" in warning


def test_blackstone_compares_its_loan_count_not_its_borrower_count():
    result = _read(BXSL)
    assert len(result.investments) == 9
    [warning] = result.warnings
    assert "bxsl:InvestmentOwnedNonaccrualNumberOfLoans = 8 at 2025-12-31" in warning
    assert "Borrowers" not in warning


# Synthetic schedules: the shapes the rule must leave alone

DIM = "dim_us-gaap_InvestmentIdentifierAxis"
P = "2026-09-30"
FV = "us-gaap:InvestmentOwnedAtFairValue"
COST = "us-gaap:InvestmentOwnedAtCost"


def _fact(fact_id, concept, value, member=None, **extra):
    fact = {"fact_id": fact_id, "concept": concept, "numeric_value": value, "period_instant": P, **extra}
    if member:
        fact[DIM] = member
    return fact


def _run(members, flagged, extra_facts=(), fair_values=None):
    fair_values = fair_values or {}
    facts = [_fact("total", FV, 1_000_000_000.0)]
    for n, member in enumerate(members):
        facts.append(_fact(f"fv{n}", FV, fair_values.get(member, 10_000_000.0), member))
        facts.append(_fact(f"cost{n}", COST, 12_000_000.0, member))
    facts.extend(extra_facts)
    linked = [f"cost{members.index(m)}" for m in flagged]
    footnote = SimpleNamespace(text="Investment is on non-accrual status.", lang="en-US", related_fact_ids=linked)
    return _extract_nonaccrual_from_xbrl(SimpleNamespace(footnotes={"fn": footnote}, element_catalog={}),
                                         period=P, all_facts=facts)


def test_a_parent_beside_its_numbered_tranches_is_still_a_holding():
    result = _run(["Bolder Panther Group, LLC | Secured Debt", "Bolder Panther Group, LLC | Secured Debt 1.1",
                   "Bolder Panther Group, LLC | Secured Debt 1.2"],
                  flagged=["Bolder Panther Group, LLC | Secured Debt"])
    assert [inv.identifier for inv in result.investments] == ["Bolder Panther Group, LLC | Secured Debt"]


def test_a_holding_whose_listed_pieces_do_not_add_up_to_it_is_still_a_holding():
    # New Mountain's 10-Q for 2026-09-30 (0001496099-26-000034): LogRhythm's first lien is worth
    # $3,454,000 and its "- Drawn" and "- Undrawn" pieces $73,000 and $0.
    head = "LogRhythm, Inc. | First lien"
    members = [head, f"{head} - Drawn", f"{head} - Undrawn", "Beta Inc"]
    result = _run(members, flagged=[head],
                  fair_values={head: 3_454_000.0, f"{head} - Drawn": 73_000.0, f"{head} - Undrawn": 0.0})
    assert [inv.identifier for inv in result.investments] == [head]


def test_a_heading_its_rows_add_up_to_is_a_subtotal():
    head = "Debt Securities- United States Transportation Technology"
    members = [head, f"{head} Acme Corp Secured Loan", f"{head} Beta Inc Secured Loan",
               f"{head} Total Beta Inc", "Gamma LLC"]
    fair_values = {head: 20_000_000.0, f"{head} Acme Corp Secured Loan": 12_000_000.0,
                   f"{head} Beta Inc Secured Loan": 8_000_000.0, f"{head} Total Beta Inc": 8_000_000.0}
    result = _run(members, flagged=[head, f"{head} Acme Corp Secured Loan"], fair_values=fair_values)
    assert [inv.identifier for inv in result.investments] == [f"{head} Acme Corp Secured Loan"]


def test_a_name_another_holding_extends_once_is_still_a_holding():
    result = _run(["Acme Corp", "Acme Corp Holdings, LLC", "Beta Inc"], flagged=["Acme Corp"])
    assert [inv.identifier for inv in result.investments] == ["Acme Corp"]


def test_no_warning_when_the_tagged_total_agrees_within_rounding():
    # The filer tags $12.0M rounded to $0.1M; the holding's cost is $12,000,000.
    tagged = _fact("na", "xx:NonAccrualCost", 12_000_000.0, period_instant=None, period_start="2026-07-01",
                   period_end=P)
    result = _run(["Acme Corp", "Beta Inc"], flagged=["Acme Corp"], extra_facts=[tagged])
    assert result.warnings == []


def test_no_warning_without_a_tagged_total():
    result = _run(["Acme Corp", "Beta Inc"], flagged=["Acme Corp"])
    assert len(result.investments) == 1
    assert result.warnings == []
