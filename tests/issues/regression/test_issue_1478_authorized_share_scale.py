"""Authorized and preferred share counts must use the same display scale as issued shares.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1478

Apple's FY2023 10-K (0000320193-23-000106) files 50,400,000,000 authorized
shares (facts f-198 and f-199, decimals="INF") and 15,550,061,000 /
15,943,425,000 issued shares (decimals=-3). Issued shares went through the
share formatter and displayed in thousands, 15,550,061. Authorized shares
were not in the recognized share concepts, so the generic formatter applied
the monetary millions scale and displayed 50,400: a smaller number than the
issued count, with no caption saying either scale.

The same gap covered the preferred-stock share counts. Tesla's Q2 2024 10-Q
(0001628280-24-032662) files 100,000,000 authorized preferred shares
(f-86, f-87) next to 3,194,000,000 issued common shares; they displayed as
100 and 3,194,000,000. JPMorgan's FY2023 10-K (0000019617-24-000225) files
2,740,375 issued preferred shares (f-290, f-291), which displayed as 3.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL

pytestmark = [pytest.mark.fast, pytest.mark.regression]

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl"


def _share_cells(folder, standard):
    statement = XBRL.from_directory(FIXTURES / folder).statements.balance_sheet(parenthetical=True)
    rendered = statement.render(standard=standard)
    return {
        row.metadata["concept"]: [cell.get_formatted_value() for cell in row.cells]
        for row in rendered.rows
        if row.metadata["concept"].startswith(("us-gaap_CommonStockShares", "us-gaap_PreferredStockShares")) and any(cell.value for cell in row.cells)
    }


@pytest.mark.parametrize("standard", [False, True])
def test_apple_authorized_shares_use_the_issued_share_scale(standard):
    assert _share_cells("aapl/10k_2023", standard) == {
        "us-gaap_CommonStockSharesAuthorized": ["50,400,000,000", "50,400,000,000"],
        "us-gaap_CommonStockSharesIssued": ["15,550,061,000", "15,943,425,000"],
        "us-gaap_CommonStockSharesOutstanding": ["15,550,061,000", "15,943,425,000"],
    }


@pytest.mark.parametrize("standard", [False, True])
def test_tesla_authorized_shares_are_not_scaled_as_money(standard):
    assert _share_cells("tsla", standard) == {
        "us-gaap_PreferredStockSharesAuthorized": ["100,000,000", "100,000,000"],
        "us-gaap_CommonStockSharesAuthorized": ["6,000,000,000", "6,000,000,000"],
        "us-gaap_CommonStockSharesIssued": ["3,194,000,000", "3,185,000,000"],
        "us-gaap_CommonStockSharesOutstanding": ["3,194,000,000", "3,185,000,000"],
    }


@pytest.mark.parametrize("standard", [False, True])
def test_jpmorgan_issued_preferred_shares_are_not_scaled_as_money(standard):
    assert _share_cells("jpm/10k_2024", standard) == {
        "us-gaap_PreferredStockSharesAuthorized": ["200,000,000", "200,000,000"],
        "us-gaap_PreferredStockSharesIssued": ["2,740,375", "2,740,375"],
        "us-gaap_CommonStockSharesAuthorized": ["9,000,000,000", "9,000,000,000"],
        "us-gaap_CommonStockSharesIssued": ["4,104,933,895", "4,104,933,895"],
    }
