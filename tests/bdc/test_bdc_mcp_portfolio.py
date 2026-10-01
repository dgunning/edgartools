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
