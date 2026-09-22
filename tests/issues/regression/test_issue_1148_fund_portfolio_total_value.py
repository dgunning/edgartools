"""MCP fund_portfolio's total_value summed share counts, not dollars.

``_fund_portfolio``'s candidate column list for the aggregate dollar total was
``['value', 'market_value', 'val', 'balance']``. None of the first three exist
in the real DataFrame returned by ``FundReport.investment_data()`` — the actual
dollar column is ``value_usd`` — so the loop fell through to ``'balance'``
(a share/unit count) and summed that instead. Per-holding records were
unaffected (they include every column, ``value_usd`` included), so only the
aggregate ``total_value`` field was wrong, and wrong by whatever the average
per-share price of the portfolio happens to be — for VFINX (Vanguard 500) this
produced a ``total_value`` of $14.4B against a top-5-holdings sum of ~$366B: a
smaller "total" than a subset of its own holdings.

Ground truth here is structural, not filing-specific: `value_usd` is present
in every ``FundReport.investment_data()`` DataFrame and is always the intended
dollar column, so the test just needs a portfolio DataFrame shaped the way
that method actually returns it.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1148
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Three holdings, small enough that summing 'balance' (shares) instead of
# 'value_usd' (dollars) produces an obviously wrong total.
PORTFOLIO = pd.DataFrame(
    [
        {"name": "APPLE INC", "cusip": "037833100", "balance": 1000, "value_usd": 250000.0, "pct_value": 40.0},
        {"name": "MICROSOFT CORP", "cusip": "594918104", "balance": 500, "value_usd": 200000.0, "pct_value": 32.0},
        {"name": "NVIDIA CORP", "cusip": "67066G104", "balance": 2000, "value_usd": 180000.0, "pct_value": 28.0},
    ]
)


def _fake_fund():
    fund = MagicMock()
    fund.name = "TEST 500 INDEX FUND"
    fund.identifier = "TFIVX"
    fund.get_portfolio.return_value = PORTFOLIO
    return fund


@pytest.mark.asyncio
async def test_fund_portfolio_total_value_uses_dollars_not_shares():
    """total_value must sum value_usd ($630,000), not balance (3,500 shares)."""
    from edgar.ai.mcp.tools.fund import _fund_portfolio

    with patch("edgar.funds.core.Fund", return_value=_fake_fund()):
        response = await _fund_portfolio(identifier="TFIVX", limit=5)

    assert response.success
    assert response.data["total_value"] == pytest.approx(630000.0), (
        "total_value fell back to summing 'balance' (share counts) instead of 'value_usd'"
    )
    assert response.data["total_value"] >= sum(h["value_usd"] for h in response.data["holdings"])
