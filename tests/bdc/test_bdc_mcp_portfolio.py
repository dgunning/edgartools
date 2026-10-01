"""MCP bdc_portfolio records named no borrower (edgartools-rd23).

The record builder checked ``hasattr(inv, 'name')``, but PortfolioInvestment has
``company_name`` and ``identifier`` and no ``name``, so every record came back as
type/fair_value/cost/interest_rate with nothing saying whose loan it was. It also
dropped principal, PIK rate, spread and percent of net assets.

The rows below are MAIN's 10-K for 2025-12-31 (0001396440-26-000016) as
``bdc.portfolio_investments()`` returned them on 2026-10-01.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from edgar.bdc.investments import PortfolioInvestment

MAIN_ROWS = [
    PortfolioInvestment(
        identifier="MSC Adviser I, LLC | Member Units",
        company_name="MSC Adviser I, LLC",
        investment_type="Member Units",
        fair_value=Decimal("255020000"),
        cost=Decimal("29500000"),
    ),
    PortfolioInvestment(
        identifier="Bolder Panther Group, LLC | Secured Debt 1.1",
        company_name="Bolder Panther Group, LLC",
        investment_type="Secured Debt",
        fair_value=Decimal("101046000"),
        interest_rate=0.111,
        spread=0.0722,
    ),
]


def _fake_main():
    bdc = MagicMock()
    bdc.name = "MAIN STREET CAPITAL CORP"
    bdc.cik = 1396440
    bdc.is_active = True
    bdc.state = "TX"
    bdc.portfolio_investments.return_value = MAIN_ROWS
    bdcs = MagicMock()
    bdcs.get_by_ticker.return_value = bdc
    return bdcs


async def _records():
    from edgar.ai.mcp.tools.fund import _bdc_portfolio
    with patch("edgar.bdc.reference.get_bdc_list", return_value=_fake_main()):
        response = await _bdc_portfolio(identifier="MAIN", limit=5)
    assert response.success
    return response.data["investments"]


@pytest.mark.fast
@pytest.mark.asyncio
async def test_each_record_names_the_borrower_and_the_holding():
    records = await _records()

    assert [r["company_name"] for r in records] == ["MSC Adviser I, LLC", "Bolder Panther Group, LLC"]
    assert [r["identifier"] for r in records] == [
        "MSC Adviser I, LLC | Member Units",
        "Bolder Panther Group, LLC | Secured Debt 1.1",
    ]
    assert records[0]["fair_value"] == 255020000.0
    assert records[0]["cost"] == 29500000.0
    assert records[1]["interest_rate"] == 0.111
    assert records[1]["spread"] == 0.0722


@pytest.mark.fast
@pytest.mark.asyncio
async def test_every_record_has_the_same_keys_and_a_missing_figure_is_none():
    records = await _records()

    keys = {"company_name", "identifier", "type", "industry", "principal_amount", "cost", "fair_value",
            "shares", "interest_rate", "pik_rate", "spread", "percent_of_net_assets"}
    assert all(set(r) == keys for r in records)
    # Bolder Panther's cost is not tagged: None, never a zero position
    assert records[1]["cost"] is None
    assert records[1]["principal_amount"] is None


# ---------------------------------------------------------------------------
# Ambiguous names (edgartools-1c6z). Scores are find_bdc's on 2026-10-01: every
# whole-word hit lands near 100, so the top hit alone identified nothing and
# "Golub" silently became GOLUB CAPITAL BDC.
# ---------------------------------------------------------------------------

def _rows(*hits):
    return [{"cik": cik, "ticker": None, "name": name, "state": None, "is_active": True, "score": score}
            for cik, name, score in hits]


GOLUB = _rows((1476765, "GOLUB CAPITAL BDC, Inc.", 100.0), (1901612, "Golub Capital BDC 4, Inc.", 99.8),
              (1868878, "GOLUB CAPITAL DIRECT LENDING CORP", 99.4), (1930087, "Golub Capital Private Credit Fund", 99.4))
ARES = _rows((1287750, "ARES CAPITAL CORP", 100.0), (1918712, "ARES STRATEGIC INCOME FUND", 99.3),
             (1990049, "Ares Core Infrastructure Fund", 99.3))
MAIN_STREET = _rows((1396440, "Main Street Capital CORP", 100.0), (1999999, "Phillip Street BDC LLC", 70.6))


@pytest.mark.fast
@pytest.mark.parametrize("query, rows, expected", [
    ("Golub", GOLUB, None),
    ("Ares Capital", ARES, 1287750),        # equal to ARES CAPITAL CORP once the suffix goes
    ("ares capital corp.", ARES, 1287750),
    ("Ares", ARES, None),                   # three Ares funds; nothing says which
    ("Main Street", MAIN_STREET, 1396440),  # clear winner: 100 against 70.6
    ("Golub Capital BDC", GOLUB, 1476765),  # "Inc." dropped; BDC 4 differs by its "4"
])
def test_a_name_resolves_only_when_it_identifies_one_bdc(query, rows, expected):
    from edgar.ai.mcp.tools.fund import _pick_bdc_search_winner
    assert _pick_bdc_search_winner(query, rows) == expected


@pytest.mark.fast
def test_a_single_weak_hit_is_not_used():
    from edgar.ai.mcp.tools.fund import _pick_bdc_search_winner
    assert _pick_bdc_search_winner("Phillip", _rows((1999999, "Phillip Street BDC LLC", 72.0))) is None


@pytest.mark.fast
@pytest.mark.asyncio
async def test_an_ambiguous_name_lists_the_candidates_instead_of_picking_one():
    import pandas as pd

    from edgar.ai.mcp.tools.fund import _bdc_portfolio

    bdcs = MagicMock()
    bdcs.get_by_ticker.return_value = None
    search = MagicMock()
    search.results = pd.DataFrame(GOLUB)
    with patch("edgar.bdc.reference.get_bdc_list", return_value=bdcs), \
            patch("edgar.bdc.search.find_bdc", return_value=search):
        response = await _bdc_portfolio(identifier="Golub", limit=5)

    assert not response.success
    assert response.error_code == "AMBIGUOUS_BDC"
    assert response.suggestions == [
        "GOLUB CAPITAL BDC, Inc.: identifier='1476765'",
        "Golub Capital BDC 4, Inc.: identifier='1901612'",
        "GOLUB CAPITAL DIRECT LENDING CORP: identifier='1868878'",
        "Golub Capital Private Credit Fund: identifier='1930087'",
    ]
    bdcs.portfolio_investments.assert_not_called()
