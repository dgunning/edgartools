"""validate_balance_sheet resolves its totals by XBRL concept before label.

Bead: edgartools-9g8um

The totals were found by label alone, and the label lists missed the captions
filers actually use: "Total shareholders’ equity" and "Total liabilities and
stockholders’ equity" with a typographic apostrophe, "Total assets(a)" with a
footnote marker. 18 of the 33 tracked XBRL fixtures with a balance sheet
returned INCOMPLETE_DATA (or MISSING_ASSETS) and the accounting equation was
never checked. Totals are now read from the non-dimensional row tagged
us-gaap:Assets, Liabilities, StockholdersEquity, LiabilitiesAndStockholdersEquity
and so on, with the labels as the fallback.

Ground truth, read from the fixture instances:

* JPMorgan Chase 10-K for FY2023, accession 0000019617-24-000225
  (tests/fixtures/xbrl/jpm/10k_2024). At 2023-12-31, us-gaap:Assets
  $3,875,393,000,000 (f-254), Liabilities $3,547,515,000,000 (f-282),
  StockholdersEquity $327,878,000,000 (f-312), LiabilitiesAndStockholdersEquity
  $3,875,393,000,000 (f-314). The same concepts are repeated on segment, VIE and
  pledged-asset rows under a dimension, which must not be read as the total.
* Apple 10-K for FY2023, accession 0000320193-23-000106
  (tests/fixtures/xbrl/aapl/10k_2023). At 2023-09-30, Assets $352,583,000,000
  (f-172), Liabilities $290,437,000,000 (f-192), StockholdersEquity
  $62,146,000,000 (f-210), LiabilitiesAndStockholdersEquity $352,583,000,000
  (f-212).
* JPMorgan Chase 10-K for FY2012, accession 0000019617-13-000221
  (tests/fixtures/xbrl/jpm/10k_2013), labels its total "Total assets(a)":
  Assets and LiabilitiesAndStockholdersEquity $2,359,141,000,000 at 2012-12-31.
"""
from pathlib import Path

import pandas as pd
import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.validation import validate_balance_sheet

pytestmark = pytest.mark.fast


def _validate(fixture):
    return validate_balance_sheet(XBRL.from_directory(Path(fixture)).statements.balance_sheet())


def test_bank_equation_is_checked_by_concept():
    result = _validate("tests/fixtures/xbrl/jpm/10k_2024")
    assert result.issues == []
    assert result.metadata["period"] == "2023-12-31"
    assert result.metadata["liab_equity_check"] == {
        "assets": 3_875_393_000_000.0,
        "liabilities_and_equity": 3_875_393_000_000.0,
        "difference": 0.0,
        "difference_pct": 0.0,
    }
    values = result.metadata["extracted_values"]
    # The non-dimensional totals, not a segment or VIE row of the same concept
    assert values["total_liabilities"] == 3_547_515_000_000.0
    assert values["stockholders_equity"] == 327_878_000_000.0


def test_tech_equation_is_checked_by_concept():
    result = _validate("tests/fixtures/xbrl/aapl/10k_2023")
    assert result.issues == []
    assert result.metadata["period"] == "2023-09-30"
    assert result.metadata["liab_equity_check"]["assets"] == 352_583_000_000.0
    assert result.metadata["liab_equity_check"]["liabilities_and_equity"] == 352_583_000_000.0
    values = result.metadata["extracted_values"]
    assert values["total_liabilities"] == 290_437_000_000.0
    assert values["stockholders_equity"] == 62_146_000_000.0


def test_footnoted_total_assets_label_is_found():
    result = _validate("tests/fixtures/xbrl/jpm/10k_2013")
    assert [issue.code for issue in result.issues] == []
    assert result.metadata["period"] == "2012-12-31"
    assert result.metadata["liab_equity_check"]["assets"] == 2_359_141_000_000.0
    assert result.metadata["liab_equity_check"]["liabilities_and_equity"] == 2_359_141_000_000.0


def test_dimensional_row_of_a_total_concept_is_not_the_total():
    # JPM's FY2023 figures with a segment row of us-gaap:Assets placed ahead of
    # the total and captions that no label variant matches.
    df = pd.DataFrame({
        "concept": ["us-gaap_Assets", "us-gaap_Assets", "us-gaap_LiabilitiesAndStockholdersEquity"],
        "label": ["Corporate", "Total assets(a)", "Total liabilities and stockholders’ equity"],
        "dimension": [True, False, False],
        "2023-12-31": [1_348_437_000_000.0, 3_875_393_000_000.0, 3_875_393_000_000.0],
    })
    result = validate_balance_sheet(df)
    assert result.issues == []
    assert result.metadata["liab_equity_check"]["assets"] == 3_875_393_000_000.0
