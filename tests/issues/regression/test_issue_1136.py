"""MCP fund_portfolio returned an empty holdings list for every fund.

``_get_fund_holdings`` iterated ``ThirteenF.holdings`` directly. That attribute is
a ``pandas.DataFrame``, and iterating a DataFrame yields its column names as
strings, so every ``hasattr(h, 'cusip')`` probe was False, the per-holding dict
stayed empty and nothing was ever appended. ``holdings_count`` came out right
because it read ``len(obj.holdings)`` rather than iterating, which left the
response looking structurally valid: a fund with 29 positions and none of them
listed.

The ground truth here is Berkshire Hathaway's Q2 2026 13F-HR
(``0001193125-26-352200``): Apple 227,917,808 shares at $65,950,296,923, American
Express 151,610,700 at $51,282,319,275, Coca-Cola 400,000,000 at $32,508,000,000.
The holdings frame is built from those recorded values, so the test is a unit test
and needs no network.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1136
"""

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Berkshire Hathaway Q2 2026 13F-HR (0001193125-26-352200), three largest
# positions, with the column names ThirteenF.holdings actually carries.
BRK_HOLDINGS = pd.DataFrame(
    [
        {"Issuer": "APPLE INC", "Class": "COM", "Cusip": "037833100",
         "Ticker": "AAPL", "SharesPrnAmount": 227917808, "Value": 65950296923,
         "Type": "Shares", "PutCall": ""},
        {"Issuer": "AMERICAN EXPRESS CO", "Class": "COM", "Cusip": "025816109",
         "Ticker": "AXP", "SharesPrnAmount": 151610700, "Value": 51282319275,
         "Type": "Shares", "PutCall": ""},
        {"Issuer": "COCA COLA CO", "Class": "COM", "Cusip": "191216100",
         "Ticker": "KO", "SharesPrnAmount": 400000000, "Value": 32508000000,
         "Type": "Shares", "PutCall": ""},
    ]
)


def _fake_berkshire():
    """A resolved company whose latest 13F-HR exposes BRK_HOLDINGS."""
    thirteen_f = MagicMock()
    thirteen_f.holdings = BRK_HOLDINGS

    filing = MagicMock()
    filing.filing_date = "2026-08-14"
    filing.accession_number = "0001193125-26-352200"
    filing.obj.return_value = thirteen_f

    filings = MagicMock()
    filings.__len__.return_value = 1
    filings.__getitem__.return_value = filing

    company = MagicMock()
    company.name = "BERKSHIRE HATHAWAY INC"
    company.cik = 1067983
    company.get_filings.return_value = filings
    return company


async def _run(limit: int):
    from edgar.ai.mcp.tools.ownership import edgar_ownership

    with patch(
        "edgar.ai.mcp.tools.ownership.resolve_company",
        return_value=_fake_berkshire(),
    ):
        return await edgar_ownership(
            identifier="BRK-A", analysis_type="fund_portfolio", limit=limit,
        )


@pytest.mark.asyncio
async def test_fund_portfolio_lists_the_holdings():
    """Positions come back with issuer, CUSIP, shares and value from the filing."""
    response = await _run(limit=3)

    assert response.success
    holdings = response.data["holdings"]
    assert len(holdings) == 3, "holdings came back empty — the DataFrame regression"

    assert holdings[0] == {
        "company": "APPLE INC",
        "cusip": "037833100",
        "shares": 227917808,
        "value": 65950296923,
    }
    assert holdings[2]["company"] == "COCA COLA CO"
    assert holdings[2]["value"] == 32508000000

    assert response.data["holdings_count"] == 3
    assert response.data["total_value_shown"] == 65950296923 + 51282319275 + 32508000000


@pytest.mark.asyncio
async def test_fund_portfolio_honours_limit():
    """``limit`` truncates the listing without touching the reported count."""
    response = await _run(limit=2)

    assert [h["cusip"] for h in response.data["holdings"]] == ["037833100", "025816109"]
    assert response.data["holdings_count"] == 3


@pytest.mark.asyncio
async def test_fund_portfolio_payload_is_json_serialisable():
    """Pandas hands back numpy scalars; the MCP response has to survive json.dumps."""
    response = await _run(limit=3)

    encoded = json.loads(json.dumps(response.data))
    assert encoded["holdings"][0]["shares"] == 227917808
