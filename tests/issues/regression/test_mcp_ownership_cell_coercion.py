"""One reader for the DataFrame cells the MCP tools serialise by hand.

Several tools walk a pandas frame and build the response dict themselves, and
each one that grew its own coercion rules got the same two things wrong.

A missing cell is not falsy. `bool(float("nan"))` is `True`, so `if issuer:`
admits it and `str()` renders it as the literal `"nan"` — that is how
`{"company": "nan", "cusip": "nan"}` came back from `fund_portfolio`. Where the
guard was missing entirely the bare NaN survived into `ToolResponse.to_json`,
which is a plain `json.dumps`: it writes the literal `NaN`, and that is not JSON
a strict parser reads back. `portfolio_diff` did that with its issuer, cusip and
status while guarding only its ticker; `screen` did it with a company's name
while hand-rolling `str(x) != "nan"` for ticker and exchange three lines below;
`search` did it with a ticker.

And one missing cell makes its whole column float64, so a share count or a
dollar value came back as `65950296923.0` from `fund_portfolio` beside
`65950296923` from `portfolio_diff` — same filing, same number, two renderings,
because the two walks disagreed about int coercion.

`_cell_missing`, `_cell_text` and `_cell_number` now live in `tools/base.py` and
every walk reads through them.

Ground truth is Berkshire Hathaway's Q2 2026 13F-HR (`0001193125-26-352200`):
Apple 227,917,808 shares at $65,950,296,923, American Express 151,610,700 at
$51,282,319,275, Coca-Cola 400,000,000 at $32,508,000,000. The gaps here are
that filing after a degraded TXT-format parse that recovered some cells and not
others. Frames are built from recorded values, so these are unit tests and need
no network.

GitHub PR: https://github.com/dgunning/edgartools/pull/1137
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from edgar.ai.mcp.tools.base import _cell_missing, _cell_number, _cell_text

# Two clean positions, one that lost its issuer and its value, and one that lost
# its share count. Both numeric columns therefore arrive float64 for every row.
HOLDINGS_WITH_GAPS = pd.DataFrame(
    [
        {"Issuer": "APPLE INC", "Cusip": "037833100",
         "SharesPrnAmount": 227917808, "Value": 65950296923},
        {"Issuer": "AMERICAN EXPRESS CO", "Cusip": "025816109",
         "SharesPrnAmount": 151610700, "Value": 51282319275},
        {"Issuer": None, "Cusip": None,
         "SharesPrnAmount": 400000000, "Value": None},
        {"Issuer": "COCA COLA CO", "Cusip": "191216100",
         "SharesPrnAmount": None, "Value": 32508000000},
    ]
)

# The comparison frame for the same fund, with a gap in the same place.
DIFF_WITH_A_GAP = pd.DataFrame(
    [
        {"Ticker": "AAPL", "Issuer": "APPLE INC", "Cusip": "037833100",
         "Status": "HELD", "Shares": 227917808, "Value": 65950296923,
         "PrevShares": 300000000, "PrevValue": 63340000000,
         "ShareChange": -72082192, "ShareChangePct": -24.5,
         "ValueChange": 2610296923},
        {"Ticker": None, "Issuer": None, "Cusip": None,
         "Status": "NEW", "Shares": 400000000, "Value": None,
         "PrevShares": None, "PrevValue": None,
         "ShareChange": None, "ShareChangePct": None, "ValueChange": None},
    ]
)


def _fake_fund():
    """A resolved 13F filer whose latest filing carries the frames above."""
    thirteen_f = MagicMock()
    thirteen_f.holdings = HOLDINGS_WITH_GAPS

    comparison = MagicMock()
    comparison.data = DIFF_WITH_A_GAP
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
        "edgar.ai.mcp.tools.ownership.resolve_company", return_value=_fake_fund(),
    ):
        return await edgar_ownership(
            identifier="1067983", analysis_type=analysis_type, limit=limit,
        )


# --- fund_portfolio ---------------------------------------------------------

@pytest.mark.asyncio
async def test_a_missing_issuer_is_omitted_rather_than_named_nan():
    response = await _run("fund_portfolio")

    holdings = response.data["holdings"]
    assert [h.get("company") for h in holdings] == [
        "APPLE INC", "AMERICAN EXPRESS CO", None, "COCA COLA CO",
    ]
    assert "nan" not in json.dumps(holdings)
    assert "cusip" not in holdings[2]


@pytest.mark.asyncio
async def test_a_half_parsed_position_omits_the_half_it_lost():
    """Each of the pair stands on its own, the way company and cusip do. Writing
    them together put an explicit `"value": null` in the response, which reads as
    a value to a caller testing `"value" in holding`."""
    response = await _run("fund_portfolio")
    holdings = response.data["holdings"]

    assert holdings[2]["shares"] == 400000000
    assert "value" not in holdings[2]

    assert holdings[3]["value"] == 32508000000
    assert "shares" not in holdings[3]


@pytest.mark.asyncio
async def test_whole_number_columns_stay_whole():
    """Neither column survives the gaps as int64, so both assertions bite."""
    assert HOLDINGS_WITH_GAPS["SharesPrnAmount"].dtype == "float64"
    assert HOLDINGS_WITH_GAPS["Value"].dtype == "float64"

    apple = (await _run("fund_portfolio")).data["holdings"][0]

    assert apple["shares"] == 227917808
    assert isinstance(apple["shares"], int), "float64 column leaked into the payload"
    assert apple["value"] == 65950296923
    assert isinstance(apple["value"], int)


# --- portfolio_diff ---------------------------------------------------------

@pytest.mark.asyncio
async def test_portfolio_diff_omits_nan_text_cells():
    new_position = (await _run("portfolio_diff")).data["changes"][1]

    assert new_position["ticker"] is None
    assert new_position["issuer"] == ""
    assert new_position["cusip"] == ""
    assert new_position["status"] == "NEW"


@pytest.mark.asyncio
async def test_portfolio_diff_payload_is_strict_json():
    """A bare NaN serialises as the literal `NaN`, which is not valid JSON."""
    encoded = json.dumps((await _run("portfolio_diff")).data, allow_nan=False)

    assert json.loads(encoded)["changes"][0]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_a_fractional_column_is_not_floored():
    """`as_int` is per column. -24.5 rather than -24.03 because `int()` truncates
    to -24 and `-24 == -24.0` — a whole-number fixture cannot fail this."""
    change = (await _run("portfolio_diff")).data["changes"][0]["share_change_pct"]

    assert change == -24.5
    assert isinstance(change, float)


@pytest.mark.asyncio
async def test_both_analysis_types_render_the_same_cell_the_same_way():
    from_portfolio = (await _run("fund_portfolio")).data["holdings"][0]["value"]
    from_diff = (await _run("portfolio_diff")).data["changes"][0]["value"]

    assert from_portfolio == from_diff == 65950296923
    assert type(from_portfolio) is type(from_diff)


# --- the shared helpers -----------------------------------------------------

@pytest.mark.parametrize("absent", [None, float("nan"), pd.NA, pd.NaT])
def test_every_shape_of_a_missing_cell_is_recognised(absent):
    """`value != value` raises on pd.NA; `bool(float("nan"))` is True."""
    assert _cell_missing(absent)
    assert _cell_text(absent) is None
    assert _cell_number(absent) is None


def test_a_decimal_is_json_serialisable_on_the_way_out():
    """NPORT columns arrive as Decimal, which `json.dumps` refuses."""
    assert _cell_number(Decimal("1234.56")) == 1234.56
    assert isinstance(_cell_number(Decimal("1234.56")), float)
    assert _cell_number(Decimal("1234"), as_int=True) == 1234


def test_a_number_is_left_alone_unless_int_is_asked_for():
    """The default cannot silently floor a column that turns out fractional."""
    assert _cell_number(-24.5) == -24.5
    assert _cell_number(-24.5, as_int=True) == -24


# --- the same defect in the sibling tools -----------------------------------

@pytest.mark.asyncio
async def test_screen_does_not_name_a_company_nan():
    """`row.get('name') or row.get('company', '')` admitted a NaN name, and a
    bare NaN reaches `to_json` as the literal `NaN`."""
    from edgar.ai.mcp.tools.screen import edgar_screen

    frame = pd.DataFrame([
        {"cik": 320193, "name": "Apple Inc.", "ticker": "AAPL", "exchange": "Nasdaq"},
        {"cik": 1067983, "name": None, "ticker": None, "exchange": None},
    ])

    with patch("edgar.reference.get_companies_by_industry", return_value=frame):
        response = await edgar_screen(sic=3571)

    companies = response.data["companies"]
    assert companies[1]["name"] == ""
    assert "ticker" not in companies[1]
    assert json.dumps(response.data, allow_nan=False)


@pytest.mark.asyncio
async def test_search_does_not_hand_back_a_nan_ticker():
    """NaN is truthy, so `if row.ticker:` admitted a missing ticker."""
    from edgar.ai.mcp.tools.search import _search_companies

    matches = MagicMock()
    matches.__len__.return_value = 2
    matches.results = pd.DataFrame([
        {"cik": 320193, "ticker": "AAPL", "company": "Apple Inc.", "score": 100},
        {"cik": 1067983, "ticker": None, "company": "BERKSHIRE HATHAWAY INC", "score": 90},
    ])

    with patch("edgar.find_company", return_value=matches):
        companies = await _search_companies("apple", limit=2)

    assert companies[0]["ticker"] == "AAPL"
    assert "ticker" not in companies[1]
    assert json.dumps(companies, allow_nan=False)
