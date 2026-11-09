"""Balance-sheet validation compared operands from different periods.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1852

Each operand of ``validate_balance_sheet`` took the first non-null value of its
own row, so a total missing from the current column was taken from a
comparative one. All operands are now read from one column, the first that
reports Total Assets, and that column is named in ``metadata["period"]``. An
equation whose operands are not all in that column is reported as
INCOMPLETE_DATA naming the columns that do carry them, rather than as an
imbalance between two dates.

Ground truth: National Presto Industries 10-Q for fiscal Q1 2026, accession
0001437749-26-017365 (fixture tests/fixtures/xbrl/npk/10q_2026q1, the filed
instance and linkbases). Assets $469,312,000 (c146050965) and current assets
$373,917,000 (c146050937) are tagged at 2026-04-05, while liabilities
$74,143,000, current liabilities $63,626,000, equity $395,169,000 and
liabilities and equity $469,312,000 are tagged at 2026-03-31. At 2025-12-31
liabilities and equity (c146051058) is $500,730,000. Before the fix the
validator compared April assets with December liabilities and equity and
reported a $31,418,000 imbalance.
"""
from pathlib import Path

import pandas as pd
import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.validation import ValidationLevel, validate_balance_sheet

pytestmark = pytest.mark.fast


@pytest.fixture(scope="module")
def npk_balance_sheet():
    return XBRL.from_directory(Path("tests/fixtures/xbrl/npk/10q_2026q1")).statements.balance_sheet()


def test_no_cross_date_imbalance(npk_balance_sheet):
    result = npk_balance_sheet.validate(level="sections")
    assert "EQUATION_IMBALANCE" not in [issue.code for issue in result.issues]
    assert "liab_equity_check" not in result.metadata
    [issue] = result.issues
    assert issue.code == "INCOMPLETE_DATA"
    assert issue.details == {"period": "2026-04-05", "totals_reported_for": ["2025-12-31", "2026-03-31"]}
    assert "2026-04-05" in issue.message


def test_extracted_values_come_from_one_column(npk_balance_sheet):
    result = npk_balance_sheet.validate()
    assert result.metadata["period"] == "2026-04-05"
    # December liabilities (105,595,000) and current liabilities (94,952,000)
    # are no longer mixed in with April assets.
    assert result.metadata["extracted_values"] == {
        "total_assets": 469_312_000.0,
        "stockholders_equity": 395_169_000.0,
        "current_assets": 373_917_000.0,
    }


def test_equation_is_checked_within_the_selected_column():
    # Same NPK figures as a plain frame: the current column carries every
    # operand except liabilities and equity, which only the comparative has.
    df = pd.DataFrame({
        "label": ["Total Assets", "Total Liabilities and Equity"],
        "2026-04-05": [469_312_000.0, None],
        "2025-12-31": [500_730_000.0, 500_730_000.0],
    })
    result = validate_balance_sheet(df, level=ValidationLevel.SECTIONS)
    assert [issue.code for issue in result.issues] == ["INCOMPLETE_DATA"]
    assert result.metadata["period"] == "2026-04-05"

    df.loc[1, "2026-04-05"] = 469_312_000.0
    result = validate_balance_sheet(df)
    assert result.issues == []
    assert result.metadata["liab_equity_check"]["liabilities_and_equity"] == 469_312_000.0
