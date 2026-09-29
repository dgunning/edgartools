"""
Tests for balance sheet validation (edgar.xbrl.validation).

Pure logic — no network calls. Uses pandas DataFrames as input.
"""

import pytest
import pandas as pd

from edgar.xbrl.validation import (
    ValidationLevel,
    ValidationSeverity,
    ValidationIssue,
    ValidationResult,
    _find_value_by_labels,
    _get_balance_sheet_values,
    validate_balance_sheet,
    validate_statement,
    BALANCE_SHEET_TOTALS,
)


# ── Enums ────────────────────────────────────────────────────────────────────

def test_validation_level_values():
    assert ValidationLevel.FUNDAMENTAL.value == "fundamental"
    assert ValidationLevel.SECTIONS.value == "sections"
    assert ValidationLevel.DETAILED.value == "detailed"


def test_validation_severity_values():
    assert ValidationSeverity.ERROR.value == "error"
    assert ValidationSeverity.WARNING.value == "warning"
    assert ValidationSeverity.INFO.value == "info"


# ── ValidationIssue ──────────────────────────────────────────────────────────

def test_validation_issue_str():
    issue = ValidationIssue(
        severity=ValidationSeverity.ERROR,
        code="TEST_CODE",
        message="Something went wrong"
    )
    assert "[ERROR] TEST_CODE: Something went wrong" == str(issue)


def test_validation_issue_defaults():
    issue = ValidationIssue(severity=ValidationSeverity.INFO, code="X", message="Y")
    assert issue.details == {}


# ── ValidationResult ─────────────────────────────────────────────────────────

class TestValidationResult:

    def test_valid_result(self):
        result = ValidationResult(is_valid=True)
        assert result.is_valid
        assert result.error_count == 0
        assert result.warning_count == 0
        assert "VALID" in str(result)

    def test_invalid_result_with_errors(self):
        result = ValidationResult(
            is_valid=False,
            issues=[
                ValidationIssue(ValidationSeverity.ERROR, "E1", "error 1"),
                ValidationIssue(ValidationSeverity.ERROR, "E2", "error 2"),
                ValidationIssue(ValidationSeverity.WARNING, "W1", "warning 1"),
            ]
        )
        assert not result.is_valid
        assert result.error_count == 2
        assert result.warning_count == 1
        assert len(result.errors) == 2
        assert len(result.warnings) == 1
        assert "INVALID" in str(result)


# ── _find_value_by_labels ────────────────────────────────────────────────────

@pytest.fixture
def balance_sheet_df():
    """Minimal balance sheet DataFrame."""
    return pd.DataFrame({
        "label": [
            "Total Assets",
            "Total Liabilities",
            "Stockholders' Equity",
            "Total Liabilities and Equity",
        ],
        "FY2024": [352_583.0, 290_437.0, 62_146.0, 352_583.0],
    })


class TestFindValueByLabels:

    def test_exact_match(self, balance_sheet_df):
        result = _find_value_by_labels(balance_sheet_df, ["Total Assets"])
        assert result == ("Total Assets", 352_583.0)

    def test_case_insensitive(self, balance_sheet_df):
        result = _find_value_by_labels(balance_sheet_df, ["total assets"])
        assert result is not None
        assert result[1] == 352_583.0

    def test_first_variant_wins(self, balance_sheet_df):
        result = _find_value_by_labels(balance_sheet_df, ["Assets", "Total Assets"])
        # "Assets" not found, falls through to "Total Assets"
        assert result is not None
        assert result[0] == "Total Assets"

    def test_not_found_returns_none(self, balance_sheet_df):
        assert _find_value_by_labels(balance_sheet_df, ["Nonexistent"]) is None

    def test_none_df_returns_none(self):
        assert _find_value_by_labels(None, ["Total Assets"]) is None

    def test_empty_df_returns_none(self):
        assert _find_value_by_labels(pd.DataFrame(), ["Total Assets"]) is None


# ── _get_balance_sheet_values ────────────────────────────────────────────────

def test_get_balance_sheet_values(balance_sheet_df):
    values = _get_balance_sheet_values(balance_sheet_df)
    assert values["total_assets"] == 352_583.0
    assert values["total_liabilities"] == 290_437.0
    assert values["stockholders_equity"] == 62_146.0
    assert values["liabilities_and_equity"] == 352_583.0


# ── validate_balance_sheet ───────────────────────────────────────────────────

class TestValidateBalanceSheet:

    def test_balanced_sheet_is_valid(self, balance_sheet_df):
        """Assets == Liabilities and Equity → valid."""
        result = validate_balance_sheet(balance_sheet_df)
        assert result.is_valid
        assert result.error_count == 0

    def test_unbalanced_sheet_is_invalid(self):
        df = pd.DataFrame({
            "label": ["Total Assets", "Total Liabilities and Equity"],
            "FY2024": [100_000.0, 90_000.0],  # $10K difference
        })
        result = validate_balance_sheet(df)
        assert not result.is_valid
        assert result.error_count >= 1
        assert any("EQUATION_IMBALANCE" == i.code for i in result.issues)

    def test_empty_df_is_invalid(self):
        result = validate_balance_sheet(pd.DataFrame())
        assert not result.is_valid
        assert any("EMPTY_STATEMENT" == i.code for i in result.issues)

    def test_none_df_is_invalid(self):
        result = validate_balance_sheet(None)
        assert not result.is_valid

    def test_fallback_equation_components(self):
        """When no combined total, uses Liabilities + Equity."""
        df = pd.DataFrame({
            "label": ["Total Assets", "Total Liabilities", "Total Equity"],
            "FY2024": [100_000.0, 60_000.0, 40_000.0],
        })
        result = validate_balance_sheet(df)
        assert result.is_valid

    def test_rounding_within_tolerance(self):
        """$1 difference within default tolerance."""
        df = pd.DataFrame({
            "label": ["Total Assets", "Total Liabilities and Equity"],
            "FY2024": [100_000.0, 99_999.5],
        })
        result = validate_balance_sheet(df)
        assert result.is_valid  # Within $1 tolerance

    def test_section_validation(self):
        """SECTIONS level checks current + non-current = total."""
        df = pd.DataFrame({
            "label": [
                "Total Current Assets", "Total Non-Current Assets", "Total Assets",
                "Total Current Liabilities", "Total Non-Current Liabilities", "Total Liabilities",
                "Total Equity", "Total Liabilities and Equity",
            ],
            "FY2024": [50_000.0, 50_000.0, 100_000.0,
                       30_000.0, 30_000.0, 60_000.0,
                       40_000.0, 100_000.0],
        })
        result = validate_balance_sheet(df, level=ValidationLevel.SECTIONS)
        assert result.is_valid
        assert "section_totals" in result.checks_performed

    def test_missing_assets_is_error(self):
        df = pd.DataFrame({
            "label": ["Total Liabilities", "Total Equity"],
            "FY2024": [60_000.0, 40_000.0],
        })
        result = validate_balance_sheet(df)
        assert any("MISSING_ASSETS" == i.code for i in result.issues)


# ── validate_statement dispatch ──────────────────────────────────────────────

def test_validate_statement_unknown_type():
    """Unknown statement type returns valid with info."""
    result = validate_statement(pd.DataFrame(), statement_type="IncomeStatement")
    assert result.is_valid
    assert any("NO_VALIDATOR" == i.code for i in result.issues)
