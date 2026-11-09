"""An unknown validation level raises instead of running the fundamental checks.

Bead: edgartools-zvgw2

``Statement.validate(level="detalied")`` (a typo) looked the level up in a dict
with ``FUNDAMENTAL`` as the default, so it ran the equation check alone and
reported success; ``validate_balance_sheet`` did the same with any string.
An unknown level now raises ``ValidationError`` naming the valid levels.

Ground truth for the valid-level path: Apple 10-K for FY2023, accession
0000320193-23-000106 (tests/fixtures/xbrl/aapl/10k_2023). At 2023-09-30,
us-gaap:Assets and LiabilitiesAndStockholdersEquity are both $352,583,000,000.
"""
from pathlib import Path

import pandas as pd
import pytest

from edgar.exceptions import ValidationError
from edgar.xbrl import XBRL
from edgar.xbrl.validation import ValidationLevel, validate_balance_sheet, validate_statement

pytestmark = pytest.mark.fast


@pytest.fixture(scope="module")
def aapl_balance_sheet():
    return XBRL.from_directory(Path("tests/fixtures/xbrl/aapl/10k_2023")).statements.balance_sheet()


@pytest.mark.parametrize("level", ["detalied", "full", ""])
def test_unknown_level_raises(aapl_balance_sheet, level):
    with pytest.raises(ValidationError, match="fundamental, sections, detailed") as excinfo:
        aapl_balance_sheet.validate(level=level)
    assert excinfo.value.parameter == "level"
    assert excinfo.value.invalid_value == level


def test_unknown_level_raises_from_the_functions():
    df = pd.DataFrame({"label": ["Total Assets"], "2023-09-30": [352_583_000_000.0]})
    with pytest.raises(ValidationError, match="'detalied'"):
        validate_balance_sheet(df, level="detalied")
    with pytest.raises(ValidationError, match="'detalied'"):
        validate_statement(df, statement_type="BalanceSheet", level="detalied")


@pytest.mark.parametrize("level, section_check", [
    ("fundamental", False), ("sections", True), ("detailed", True),
    ("SECTIONS", True), ("Detailed", True),
    (ValidationLevel.FUNDAMENTAL, False), (ValidationLevel.SECTIONS, True), (ValidationLevel.DETAILED, True),
    (ValidationLevel.SECTIONS.value, True),
])
def test_valid_levels_still_work(aapl_balance_sheet, level, section_check):
    result = aapl_balance_sheet.validate(level=level)
    assert result.is_valid
    assert result.metadata["liab_equity_check"]["assets"] == 352_583_000_000.0
    assert ("section_totals" in result.checks_performed) is section_check
