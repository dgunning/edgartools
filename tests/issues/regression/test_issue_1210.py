"""Validation printed VALID when nothing had been compared.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1210

``ValidationResult.is_valid`` means "no error-severity issue", so an income
statement (no validator), a balance sheet whose equation could not be
evaluated (INCOMPLETE_DATA) and a section check skipped for a missing subtotal
all printed ``VALID``. The result now records the comparisons whose arithmetic
ran (``checks_completed``) and the requested ``level``, and ``status`` is
"inconclusive" when a requested comparison did not run. ``is_valid``,
severities and tolerances are unchanged.

Ground truth, read from the tracked instance documents:

- ExxonMobil 10-K FY2022, accession 0000034088-23-000020
  (tests/fixtures/xbrl/xom/10k_2023). At 2022-12-31, in the non-dimensional
  context i15692b26353e42aea7351f84210cab69_I20221231: Assets and
  LiabilitiesAndStockholdersEquity $369,067M, AssetsCurrent $97,631M,
  LiabilitiesCurrent $69,045M. The balance sheet reports no non-current
  subtotals (the instance's AssetsNoncurrent facts are all under
  EquityMethodInvestmentNonconsolidatedInvesteeAxis).
- Apple 10-K FY2023, accession 0000320193-23-000106
  (tests/fixtures/xbrl/aapl/10k_2023). At 2023-09-30 (context c-22): Assets
  and LiabilitiesAndStockholdersEquity $352,583M = AssetsCurrent $143,566M +
  AssetsNoncurrent $209,017M; Liabilities $290,437M = LiabilitiesCurrent
  $145,308M + LiabilitiesNoncurrent $145,129M.
- National Presto 10-Q Q1 2026, accession 0001437749-26-017365
  (tests/fixtures/xbrl/npk/10q_2026q1). Assets $469,312,000 are tagged at
  2026-04-05 but liabilities and equity only at 2026-03-31 (GH #1852), so the
  equation is not evaluated.

Over the 33 tracked balance sheets 32 are valid at the default level and 1
(NPK) inconclusive; at "sections"/"detailed" 4 are valid and 29 inconclusive.
All 30 income and 33 cash flow statements are inconclusive. ``is_valid`` is
unchanged for every one.
"""
from pathlib import Path

import pandas as pd
import pytest
from rich.console import Console

from edgar.xbrl import XBRL
from edgar.xbrl.validation import ValidationResult, validate_balance_sheet

pytestmark = pytest.mark.fast


@pytest.fixture(scope="module")
def xom():
    return XBRL.from_directory(Path("tests/fixtures/xbrl/xom/10k_2023"))


@pytest.fixture(scope="module")
def aapl_balance_sheet():
    return XBRL.from_directory(Path("tests/fixtures/xbrl/aapl/10k_2023")).statements.balance_sheet()


def _rendered(result):
    console = Console(width=120, record=True)
    console.print(result)
    return console.export_text()


def test_income_statement_is_inconclusive(xom):
    result = xom.statements.income_statement().validate()
    assert result.is_valid is True
    assert [i.code for i in result.issues] == ["NO_VALIDATOR"]
    assert result.checks_completed == []
    assert result.validation_complete is False
    assert result.status == "inconclusive"
    assert str(result) == "ValidationResult: INCONCLUSIVE (0 errors, 0 warnings)"
    assert "no validator for this statement type" in _rendered(result)


def test_equation_not_evaluated_is_inconclusive():
    bs = XBRL.from_directory(Path("tests/fixtures/xbrl/npk/10q_2026q1")).statements.balance_sheet()
    result = bs.validate()
    assert result.is_valid is True
    assert [i.code for i in result.issues] == ["INCOMPLETE_DATA"]
    assert result.metadata["extracted_values"]["total_assets"] == 469_312_000
    assert "liab_equity_check" not in result.metadata and "equation_check" not in result.metadata
    assert result.checks_completed == []
    assert result.status == "inconclusive"
    assert str(result) == "ValidationResult: INCONCLUSIVE (0 errors, 1 warnings)"
    rendered = _rendered(result)
    assert "INCONCLUSIVE" in rendered and "not evaluated: fundamental_equation" in rendered


def test_balance_sheet_equation_checked_is_valid(xom):
    result = xom.statements.balance_sheet().validate()
    assert result.metadata["period"] == "2022-12-31"
    assert result.metadata["liab_equity_check"]["assets"] == 369_067_000_000
    assert result.metadata["liab_equity_check"]["liabilities_and_equity"] == 369_067_000_000
    assert result.level == "fundamental"
    assert result.checks_completed == ["fundamental_equation"]
    assert result.validation_complete is True
    assert result.status == "valid"
    assert str(result) == "ValidationResult: VALID (0 errors, 0 warnings)"


def test_skipped_section_comparisons_are_inconclusive(xom):
    result = xom.statements.balance_sheet().validate(level="detailed")
    assert result.is_valid is True
    values = result.metadata["extracted_values"]
    assert values["current_assets"] == 97_631_000_000
    assert values["current_liabilities"] == 69_045_000_000
    assert "noncurrent_assets" not in values and "noncurrent_liabilities" not in values
    assert [(i.severity.value, i.code, i.details) for i in result.issues] == [
        ("info", "SECTION_NOT_EVALUATED", {"comparison": "asset_sections", "missing": ["noncurrent_assets"]}),
        ("info", "SECTION_NOT_EVALUATED",
         {"comparison": "liability_sections", "missing": ["noncurrent_liabilities"]}),
    ]
    assert result.issues[0].message == (
        "Current Assets + Non-Current Assets not compared with Total Assets: Non-Current Assets not found")
    # The legacy category is still listed even though neither section ran
    assert result.checks_performed == ["fundamental_equation", "section_totals"]
    assert result.checks_completed == ["fundamental_equation"]
    assert result.checks_not_completed == ["asset_sections", "liability_sections"]
    assert result.status == "inconclusive"
    assert str(result) == "ValidationResult: INCONCLUSIVE (0 errors, 0 warnings)"


def test_section_comparisons_that_ran_are_valid(aapl_balance_sheet):
    result = aapl_balance_sheet.validate(level="detailed")
    values = result.metadata["extracted_values"]
    assert values["current_assets"] + values["noncurrent_assets"] == values["total_assets"] == 352_583_000_000
    assert values["noncurrent_assets"] == 209_017_000_000
    assert (values["current_liabilities"] + values["noncurrent_liabilities"]
            == values["total_liabilities"] == 290_437_000_000)
    assert values["noncurrent_liabilities"] == 145_129_000_000
    assert result.issues == []
    assert result.checks_completed == ["fundamental_equation", "asset_sections", "liability_sections"]
    assert result.status == "valid"
    assert str(result) == "ValidationResult: VALID (0 errors, 0 warnings)"


def test_error_is_invalid_even_when_incomplete():
    df = pd.DataFrame({"label": ["Total Liabilities"], "2024-12-31": [100.0]})
    result = validate_balance_sheet(df)
    assert [i.code for i in result.errors] == ["MISSING_ASSETS"]
    assert result.validation_complete is False
    assert result.status == "invalid"
    assert str(result) == "ValidationResult: INVALID (1 errors, 0 warnings)"


def test_constructor_order_is_unchanged():
    result = ValidationResult(True, [], ["fundamental_equation"], {"period": "2024-12-31"})
    assert result.checks_performed == ["fundamental_equation"]
    assert result.metadata == {"period": "2024-12-31"}
    # Nothing was recorded as completed, so the status is not inferred from is_valid
    assert result.checks_completed == [] and result.level is None
    assert result.status == "inconclusive"


def test_panel_title_names_the_validated_statement():
    """An income statement's INCONCLUSIVE result must not be drawn as a balance-sheet check."""


    def title(result):
        console = Console(record=True, width=100)
        console.print(result)
        return console.export_text()

    no_validator = ValidationResult(is_valid=True, metadata={"detected_type": "IncomeStatement"})
    assert "Income Statement Validation" in title(no_validator)
    assert "Balance Sheet" not in title(no_validator)
    balance = ValidationResult(is_valid=True, checks_performed=["fundamental_equation"])
    assert "Balance Sheet Validation" in title(balance)
    assert "Statement Validation" in title(ValidationResult(is_valid=True))
