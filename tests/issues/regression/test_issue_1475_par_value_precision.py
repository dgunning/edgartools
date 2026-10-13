"""Per-share par values must render at the precision they were filed with.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1475

Apple's FY2023 10-K (0000320193-23-000106) files its common-stock par value
as exactly 0.00001 USD per share (facts f-196 and f-197, decimals="INF"). The
per-share formatter capped values under 10 at three decimal places and then
padded to two, so the parenthetical balance sheet showed 0.00 at both
instants.

Tesla's Q2 2024 10-Q (0001628280-24-032662) files a 0.001 USD-per-share
preferred-stock par value (facts f-84 and f-85, decimals="INF").
PreferredStockParOrStatedValuePerShare was missing from the per-share concept
list, so the statement's monetary scale was applied and both cells showed 0.
Tesla's common-stock par value, the same 0.001, already displayed correctly
and is kept as the control. JPMorgan's FY2023 10-K (0000019617-24-000225)
shows the same omission at a larger value: its $1 preferred par value (f-286,
f-287) displayed as 0 beside a $1 common par value displayed as 1.00.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.rendering import _format_value_for_display_as_string

pytestmark = [pytest.mark.fast, pytest.mark.regression]

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl"


def _xbrl(folder):
    return XBRL.from_directory(FIXTURES / folder)


def _per_share_cells(statement, standard):
    rendered = statement.render(standard=standard)
    return {
        row.metadata["concept"]: [cell.get_formatted_value() for cell in row.cells]
        for row in rendered.rows
        if "PerShare" in row.metadata["concept"] and any(cell.value for cell in row.cells)
    }


@pytest.mark.parametrize("standard", [False, True])
def test_apple_common_par_value_is_not_rounded_to_zero(standard):
    statement = _xbrl("aapl/10k_2023").statements.balance_sheet(parenthetical=True)
    assert _per_share_cells(statement, standard) == {
        "us-gaap_CommonStockParOrStatedValuePerShare": ["0.00001", "0.00001"],
    }


@pytest.mark.parametrize("standard", [False, True])
def test_tesla_preferred_par_value_is_not_scaled(standard):
    statement = _xbrl("tsla").statements.balance_sheet(parenthetical=True)
    assert _per_share_cells(statement, standard) == {
        "us-gaap_PreferredStockParOrStatedValuePerShare": ["0.001", "0.001"],
        "us-gaap_CommonStockParOrStatedValuePerShare": ["0.001", "0.001"],
    }


@pytest.mark.parametrize("standard", [False, True])
def test_jpmorgan_preferred_par_value_is_not_scaled(standard):
    statement = _xbrl("jpm/10k_2024").statements.balance_sheet(parenthetical=True)
    assert _per_share_cells(statement, standard) == {
        "us-gaap_PreferredStockParOrStatedValuePerShare": ["1.00", "1.00"],
        "us-gaap_CommonStockParOrStatedValuePerShare": ["1.00", "1.00"],
    }


def test_apple_printed_parenthetical_shows_the_par_value():
    statement = _xbrl("aapl/10k_2023").statements.balance_sheet(parenthetical=True)
    par_line = next(line for line in str(statement).splitlines() if "par value" in line)
    assert par_line.count("0.00001") == 2


def test_apple_eps_keeps_two_decimal_places():
    statement = _xbrl("aapl/10k_2023").statements.income_statement()
    assert _per_share_cells(statement, standard=False) == {
        "us-gaap_EarningsPerShareBasic": ["6.16", "6.15", "5.67"],
        "us-gaap_EarningsPerShareDiluted": ["6.13", "6.11", "5.61"],
    }


@pytest.mark.parametrize(
    "value,decimals,expected",
    [
        (1.5, "INF", "1.50"),
        (0.2375, 4, "0.2375"),
        (-0.42, 2, "-0.42"),
        (0.125, None, "0.125"),
    ],
)
def test_per_share_values_use_filed_precision(value, decimals, expected):
    period = "duration_2023-01-01_2023-12-31"
    item = {"concept": "us-gaap_CommonStockDividendsPerShareDeclared", "decimals": {period: decimals}}
    assert _format_value_for_display_as_string(value, item, period, True, -6, None) == expected
