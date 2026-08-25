"""The two 13F walks in the ownership tool read a DataFrame cell the same way.

Both `fund_portfolio` and `portfolio_diff` serialise a pandas frame by hand, and
each grew its own coercion rules. That cost two things:

* A missing text cell arrives as NaN, which is truthy and which `str()` renders
  as `"nan"`, so `if issuer: holding["company"] = str(issuer)` emitted
  `{"company": "nan", "cusip": "nan"}`. In `portfolio_diff` the bare NaN went
  through untouched, which `json.dumps` writes as the literal `NaN` — not JSON
  any strict parser will read back.
* One missing cell makes its whole column float64. `fund_portfolio` returned the
  float as-is and `portfolio_diff` cast it to int, so the same 13F Value came
  back as `65950296923.0` from one analysis type and `65950296923` from the
  other.

Ground truth is Berkshire Hathaway's Q2 2026 13F-HR (`0001193125-26-352200`):
Apple 227,917,808 shares at $65,950,296,923, American Express 151,610,700 at
$51,282,319,275. The third row here is that same filing after a degraded parse
that recovered the numbers but not the issuer — the shape that puts NaN in a
text column and floats in a numeric one. Frames are built from recorded values,
so these are unit tests and need no network.

Follow-up to the review on the pull request that fixed the empty holdings list.

GitHub PR: https://github.com/dgunning/edgartools/pull/1137
"""

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Two clean positions and one whose Issuer/Cusip did not parse. The missing
# cells are what make SharesPrnAmount and Value float64 for every row.
HOLDINGS_WITH_A_GAP = pd.DataFrame(
    [
        {"Issuer": "APPLE INC", "Cusip": "037833100",
         "SharesPrnAmount": 227917808, "Value": 65950296923},
        {"Issuer": "AMERICAN EXPRESS CO", "Cusip": "025816109",
         "SharesPrnAmount": 151610700, "Value": 51282319275},
        {"Issuer": None, "Cusip": None,
         "SharesPrnAmount": 400000000, "Value": None},
    ]
)

# The comparison frame for the same fund, with the same gap in the same place.
DIFF_WITH_A_GAP = pd.DataFrame(
    [
        {"Ticker": "AAPL", "Issuer": "APPLE INC", "Cusip": "037833100",
         "Status": "HELD", "Shares": 227917808, "Value": 65950296923,
         "PrevShares": 300000000, "PrevValue": 63340000000,
         "ShareChange": -72082192, "ShareChangePct": -24.03,
         "ValueChange": 2610296923},
        {"Ticker": None, "Issuer": None, "Cusip": None,
         "Status": "NEW", "Shares": 400000000, "Value": None,
         "PrevShares": None, "PrevValue": None,
         "ShareChange": None, "ShareChangePct": None, "ValueChange": None},
    ]
)


def _fake_fund(holdings=None, comparison_data=None):
    """A resolved 13F filer whose latest filing carries the given frames."""
    thirteen_f = MagicMock()
    thirteen_f.holdings = holdings

    comparison = MagicMock()
    comparison.data = comparison_data
    comparison.current_period = "Q2 2026"
    comparison.previous_period = "Q1 2026"
    thirteen_f.compare_holdings.return_value = comparison

    filing = MagicMock()
    filing.filing_date = "2026-08-14"
    filing.accession_number = "0001193125-26-352200"
    filing.obj.return_value = thirteen_f

    filings = MagicMock()
    filings.__len__.return_value = 2
    filings.__getitem__.return_value = filing

    company = MagicMock()
    company.name = "BERKSHIRE HATHAWAY INC"
    company.cik = 1067983
    company.get_filings.return_value = filings
    return company


async def _run(analysis_type: str, limit: int = 10):
    from edgar.ai.mcp.tools.ownership import edgar_ownership

    with patch(
        "edgar.ai.mcp.tools.ownership.resolve_company",
        return_value=_fake_fund(HOLDINGS_WITH_A_GAP, DIFF_WITH_A_GAP),
    ):
        return await edgar_ownership(
            identifier="1067983", analysis_type=analysis_type, limit=limit,
        )


@pytest.mark.asyncio
async def test_fund_portfolio_omits_a_missing_issuer_rather_than_naming_it_nan():
    """The unparsed row keeps its numbers and claims no company or CUSIP."""
    response = await _run("fund_portfolio")

    holdings = response.data["holdings"]
    assert [h.get("company") for h in holdings] == [
        "APPLE INC", "AMERICAN EXPRESS CO", None,
    ]
    assert "nan" not in json.dumps(holdings)
    assert "cusip" not in holdings[2]
    assert holdings[2]["shares"] == 400000000


@pytest.mark.asyncio
async def test_fund_portfolio_keeps_whole_numbers_whole():
    """A missing cell elsewhere in the column must not float the whole column."""
    response = await _run("fund_portfolio")

    apple = response.data["holdings"][0]
    assert apple["shares"] == 227917808
    assert isinstance(apple["shares"], int), "float64 column leaked into the payload"
    assert apple["value"] == 65950296923
    assert isinstance(apple["value"], int)


@pytest.mark.asyncio
async def test_portfolio_diff_omits_nan_text_cells():
    """Ticker, issuer, CUSIP and status of the unparsed row are empty, not NaN."""
    response = await _run("portfolio_diff")

    new_position = response.data["changes"][1]
    assert new_position["ticker"] is None
    assert new_position["issuer"] == ""
    assert new_position["cusip"] == ""
    assert new_position["status"] == "NEW"


@pytest.mark.asyncio
async def test_portfolio_diff_payload_is_strict_json():
    """A bare NaN serialises as the literal `NaN`, which is not valid JSON."""
    response = await _run("portfolio_diff")

    encoded = json.dumps(response.data, allow_nan=False)
    assert json.loads(encoded)["changes"][0]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_both_analysis_types_render_the_same_cell_the_same_way():
    """One Value column, one rendering — whichever analysis type asked for it."""
    portfolio = await _run("fund_portfolio")
    diff = await _run("portfolio_diff")

    from_portfolio = portfolio.data["holdings"][0]["value"]
    from_diff = diff.data["changes"][0]["value"]

    assert from_portfolio == from_diff == 65950296923
    assert type(from_portfolio) is type(from_diff)


@pytest.mark.asyncio
async def test_fractional_columns_stay_fractional():
    """`as_int` is per column: a percentage change is not a whole number."""
    response = await _run("portfolio_diff")

    assert response.data["changes"][0]["share_change_pct"] == -24.0
