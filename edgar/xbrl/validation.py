"""
Balance sheet and financial statement validation.

This module provides validation for financial statements, ensuring
accounting equations balance and data integrity is maintained.

Phase 1 of Context-Aware Standardization (Issue #494).
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from edgar.exceptions import ValidationError

logger = logging.getLogger(__name__)


class ValidationLevel(str, Enum):
    """Validation strictness levels."""
    FUNDAMENTAL = "fundamental"  # Basic equation: Assets = Liabilities + Equity
    SECTIONS = "sections"        # Section subtotals roll up correctly
    DETAILED = "detailed"        # Same checks as SECTIONS; line-item rollups are not implemented


def _parse_level(level: Union["ValidationLevel", str]) -> "ValidationLevel":
    """The ValidationLevel named by ``level``, a member or its value in any case.

    Raises:
        ValidationError: ``level`` names no level. An unknown string used to
            fall back to FUNDAMENTAL, so a typo such as "detalied" ran the
            equation check alone and reported success (bead edgartools-zvgw2).
    """
    if isinstance(level, ValidationLevel):
        return level
    try:
        return ValidationLevel(level.lower())
    except (AttributeError, ValueError):
        valid = ", ".join(member.value for member in ValidationLevel)
        raise ValidationError(
            f"Unknown validation level {level!r}. Valid levels: {valid}",
            parameter="level",
            invalid_value=level,
        ) from None


class ValidationSeverity(str, Enum):
    """Severity of validation issues."""
    ERROR = "error"      # Definite problem (e.g., equation doesn't balance)
    WARNING = "warning"  # Potential issue (e.g., missing expected concept)
    INFO = "info"        # Informational (e.g., rounding adjustments applied)


@dataclass
class ValidationIssue:
    """A single validation issue found during checking."""

    severity: ValidationSeverity
    code: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.code}: {self.message}"


@dataclass
class ValidationResult:
    """Result of validating a financial statement."""

    is_valid: bool
    """True if no errors found (warnings allowed)."""

    issues: List[ValidationIssue] = field(default_factory=list)
    """All validation issues found."""

    checks_performed: List[str] = field(default_factory=list)
    """List of validation checks that were run."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata about the validation."""

    @property
    def errors(self) -> List[ValidationIssue]:
        """Get only error-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> List[ValidationIssue]:
        """Get only warning-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    @property
    def error_count(self) -> int:
        """Count of error-level issues."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Count of warning-level issues."""
        return len(self.warnings)

    def __str__(self) -> str:
        status = "VALID" if self.is_valid else "INVALID"
        return (
            f"ValidationResult: {status} "
            f"({self.error_count} errors, {self.warning_count} warnings)"
        )

    def __rich__(self):
        """Rich console representation."""
        from rich.console import Group
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        status_color = "green" if self.is_valid else "red"
        status_symbol = "✓" if self.is_valid else "✗"
        status = "VALID" if self.is_valid else "INVALID"

        # Build content sections
        sections = []

        # Status header
        header = Text()
        header.append(f" {status_symbol} ", style=f"bold {status_color}")
        header.append("Validation: ", style="bold")
        header.append(status, style=f"bold {status_color}")
        sections.append(header)

        # Equation check details (if available)
        equation_data = self.metadata.get('liab_equity_check') or self.metadata.get('equation_check')
        if equation_data:
            sections.append(Text(""))  # spacer

            eq_table = Table(show_header=False, box=None, padding=(0, 1))
            eq_table.add_column("Label", style="dim")
            eq_table.add_column("Value", justify="right")

            assets = equation_data.get('assets')
            if assets is not None:
                eq_table.add_row("Total Assets", f"${assets:,.0f}")

            liab_eq = equation_data.get('liabilities_and_equity')
            if liab_eq is not None:
                eq_table.add_row("Liabilities + Equity", f"${liab_eq:,.0f}")
            else:
                liab = equation_data.get('liabilities')
                equity = equation_data.get('equity')
                if liab is not None and equity is not None:
                    eq_table.add_row("Liabilities", f"${liab:,.0f}")
                    eq_table.add_row("Equity", f"${equity:,.0f}")

            diff = equation_data.get('difference', 0)
            diff_style = "green" if diff == 0 else "red"
            eq_table.add_row("Difference", Text(f"${diff:,.0f}", style=diff_style))

            sections.append(eq_table)

        # Errors
        if self.errors:
            sections.append(Text(""))
            sections.append(Text(f"Errors ({len(self.errors)}):", style="bold red"))
            for error in self.errors:
                sections.append(Text(f"  ✗ {error.message}", style="red"))

        # Warnings
        if self.warnings:
            sections.append(Text(""))
            sections.append(Text(f"Warnings ({len(self.warnings)}):", style="bold yellow"))
            for warning in self.warnings:
                sections.append(Text(f"  ⚠ {warning.message}", style="yellow"))

        # Info messages (only if no errors/warnings)
        info_issues = [i for i in self.issues if i.severity == ValidationSeverity.INFO]
        if info_issues and not self.errors and not self.warnings:
            sections.append(Text(""))
            for info in info_issues:
                sections.append(Text(f"  ℹ {info.message}", style="dim"))

        return Panel(
            Group(*sections),
            title="Balance Sheet Validation",
            border_style=status_color,
            padding=(0, 1)
        )


# Standard concepts for balance sheet validation
# These map to mpreiss9's taxonomy via display_names.json
BALANCE_SHEET_TOTALS = {
    # Assets
    "total_assets": [
        "Total Assets",
        "Assets",
    ],
    # Liabilities
    "total_liabilities": [
        "Total Liabilities",
        "Liabilities",
    ],
    # Equity variants
    "stockholders_equity": [
        "Total Stockholders' Equity",
        "Total Equity",
        "Stockholders' Equity",
        "Shareholders' Equity",
    ],
    "total_equity_with_nci": [
        "Total Equity Including Noncontrolling Interest",
        "Total Equity",
    ],
    "noncontrolling_interest": [
        "Noncontrolling Interest",
        "Minority Interest",
    ],
    # Combined totals
    "liabilities_and_equity": [
        "Total Liabilities and Equity",
        "Total Liabilities and Stockholders' Equity",
        "Liabilities and Equity",
    ],
}

# Section subtotals for Level 2 validation
BALANCE_SHEET_SECTIONS = {
    "current_assets": [
        "Total Current Assets",
        "Current Assets",
    ],
    "noncurrent_assets": [
        "Total Non-Current Assets",
        "Non-Current Assets",
        "Total Long-Term Assets",
    ],
    "current_liabilities": [
        "Total Current Liabilities",
        "Current Liabilities",
    ],
    "noncurrent_liabilities": [
        "Total Non-Current Liabilities",
        "Non-Current Liabilities",
        "Total Long-Term Liabilities",
    ],
}


# The XBRL concept of each total, tried before the labels above. Filers word
# these captions freely ("Total shareholders’ equity", "Total assets(a)"), so
# matching on labels alone left 15 of 26 tracked fixtures, among them AAPL,
# MSFT, JPM and NVDA, with an equation that was never checked (bead
# edgartools-9g8um). Labels remain the fallback for frames without a concept
# column and for filers that use an extension concept.
BALANCE_SHEET_CONCEPTS = {
    "total_assets": ["us-gaap_Assets", "ifrs-full_Assets"],
    "total_liabilities": ["us-gaap_Liabilities", "ifrs-full_Liabilities"],
    "stockholders_equity": ["us-gaap_StockholdersEquity", "ifrs-full_EquityAttributableToOwnersOfParent"],
    "total_equity_with_nci": [
        "us-gaap_StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "ifrs-full_Equity",
    ],
    "noncontrolling_interest": ["us-gaap_MinorityInterest", "ifrs-full_NoncontrollingInterests"],
    "liabilities_and_equity": ["us-gaap_LiabilitiesAndStockholdersEquity", "ifrs-full_EquityAndLiabilities"],
    "current_assets": ["us-gaap_AssetsCurrent", "ifrs-full_CurrentAssets"],
    "noncurrent_assets": ["us-gaap_AssetsNoncurrent", "ifrs-full_NoncurrentAssets"],
    "current_liabilities": ["us-gaap_LiabilitiesCurrent", "ifrs-full_CurrentLiabilities"],
    "noncurrent_liabilities": ["us-gaap_LiabilitiesNoncurrent", "ifrs-full_NoncurrentLiabilities"],
}


def _label_column(df: pd.DataFrame) -> str:
    return 'label' if 'label' in df.columns else df.columns[0]


def _first_value(rows: pd.DataFrame, columns: List[str]) -> Optional[float]:
    """The first non-null numeric value in ``columns``, scanning ``rows`` in order."""
    for _, row in rows.iterrows():
        for col in columns:
            val = row.get(col)
            if pd.notna(val):
                try:
                    return float(val)
                except (ValueError, TypeError):
                    continue
    return None


def _total_concept_rows(df: pd.DataFrame, concepts: List[str]) -> pd.DataFrame:
    """The face rows tagged with one of ``concepts``: not abstract and not dimensional.

    A statement frame repeats a concept on its breakdown rows (JPM tags its
    segment and VIE assets us-gaap:Assets under a member, NFLX each equity
    component us-gaap:StockholdersEquity), so only the row without a dimension
    is the total.
    """
    if 'concept' not in df.columns:
        return df.iloc[0:0]
    mask = df['concept'].astype(str).str.replace(':', '_', regex=False).isin(concepts)
    for flag in ('abstract', 'dimension'):
        if flag in df.columns:
            mask &= ~df[flag].eq(True)
    return df[mask]


def _find_total(df: pd.DataFrame, key: str, columns: List[str]) -> Optional[float]:
    """The value of balance-sheet total ``key`` in ``columns``: by concept, then by label."""
    value = _first_value(_total_concept_rows(df, BALANCE_SHEET_CONCEPTS.get(key, [])), columns)
    if value is not None:
        return value
    labels = BALANCE_SHEET_TOTALS.get(key) or BALANCE_SHEET_SECTIONS.get(key, [])
    result = _find_value_by_labels(df, labels, columns)
    return result[1] if result else None


def _value_columns(df: pd.DataFrame) -> List[str]:
    """The DataFrame's value columns, in order: numeric columns other than metadata."""
    label_col = _label_column(df)
    return [
        c for c in df.columns
        if c not in [label_col, 'level', 'concept', 'balance', 'weight', 'preferred_sign', 'unit', 'point_in_time']
        and df[c].dtype in ['float64', 'int64', 'object']
    ]


def _select_period_column(df: pd.DataFrame) -> Optional[str]:
    """The column every operand of the checks is read from.

    The first value column that reports Total Assets: the statement's current
    period. Each operand used to take the first non-null value of its own row,
    so a total missing from the current column was taken from a comparative
    one and the equation compared different dates (GH #1852).
    """
    if df is None or df.empty:
        return None
    for column in _value_columns(df):
        if _find_total(df, "total_assets", [column]) is not None:
            return column
    return None


def _find_value_by_labels(
    df: pd.DataFrame,
    label_variants: List[str],
    value_columns: Optional[List[str]] = None
) -> Optional[Tuple[str, float]]:
    """
    Find a value in a DataFrame by trying multiple label variants.

    Args:
        df: DataFrame with 'label' column and value columns
        label_variants: List of possible labels to search for
        value_columns: Columns to search for values. If None, uses all numeric columns.

    Returns:
        Tuple of (label_found, value) or None if not found
    """
    if df is None or df.empty:
        return None

    label_col = _label_column(df)
    if value_columns is None:
        value_columns = _value_columns(df)

    # Search for each label variant
    for label in label_variants:
        # Case-insensitive search
        mask = df[label_col].str.lower() == label.lower()
        if mask.any():
            row = df[mask].iloc[0]
            # Get first non-null value from value columns
            for col in value_columns:
                val = row.get(col)
                if pd.notna(val):
                    try:
                        return (label, float(val))
                    except (ValueError, TypeError):
                        continue

    return None


def _get_balance_sheet_values(df: pd.DataFrame, column: Optional[str] = None) -> Dict[str, Optional[float]]:
    """
    Extract key balance sheet values from one column of a DataFrame.

    Args:
        df: Balance sheet DataFrame
        column: The value column to read. Defaults to _select_period_column(df).

    Returns:
        Dictionary with standardized keys and their values (or None if not found).
        Every value comes from the same column.
    """
    column = column if column is not None else _select_period_column(df)
    return {
        key: _find_total(df, key, [column]) if column is not None else None
        for key in {**BALANCE_SHEET_TOTALS, **BALANCE_SHEET_SECTIONS}
    }


def _check_section_totals(values: Dict[str, Optional[float]], tolerance: float) -> List[ValidationIssue]:
    """Current + non-current subtotals against total assets and total liabilities."""
    issues = []
    sections = [
        ("current_assets", "noncurrent_assets", "total_assets", "ASSET_SECTION_MISMATCH",
         "Current Assets + Non-Current Assets", "Total Assets"),
        ("current_liabilities", "noncurrent_liabilities", "total_liabilities", "LIABILITY_SECTION_MISMATCH",
         "Current Liabilities + Non-Current Liabilities", "Total Liabilities"),
    ]
    for current_key, noncurrent_key, total_key, code, parts_label, total_label in sections:
        current, noncurrent, total = values.get(current_key), values.get(noncurrent_key), values.get(total_key)
        if current is None or noncurrent is None or total is None:
            continue
        expected = current + noncurrent
        diff = abs(total - expected)
        if diff > tolerance:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code=code,
                message=f"{parts_label} ({expected:,.0f}) != {total_label} ({total:,.0f})",
                details={
                    current_key: current,
                    noncurrent_key: noncurrent,
                    total_key: total,
                    "difference": diff
                }
            ))
    return issues


def _incomplete_equation_issue(df: pd.DataFrame, column: str) -> ValidationIssue:
    """The equation could not be checked in ``column``; name the columns that do report the totals."""
    other_columns = [
        c for c in _value_columns(df) if c != column and any(
            _find_total(df, key, [c]) is not None
            for key in ("liabilities_and_equity", "total_liabilities"))
    ]
    message = f"Could not validate equation for {column}: missing Liabilities and/or Equity totals"
    if other_columns:
        message += f" (reported only for {', '.join(map(str, other_columns))})"
    return ValidationIssue(
        severity=ValidationSeverity.WARNING,
        code="INCOMPLETE_DATA",
        message=message,
        details={"period": column, "totals_reported_for": other_columns}
    )


def validate_balance_sheet(
    statement_or_df: Union[Any, pd.DataFrame],
    level: ValidationLevel = ValidationLevel.FUNDAMENTAL,
    tolerance: float = 1.0,
    tolerance_pct: float = 0.001
) -> ValidationResult:
    """
    Validate a balance sheet for accounting equation compliance.

    Validates the fundamental accounting equation:
        Assets = Liabilities + Equity

    Or equivalently:
        Assets = Liabilities and Equity (combined total)

    Every operand is read from one value column, the first that reports Total
    Assets (the current period), named in ``metadata["period"]``. When that
    column lacks the liabilities or equity totals the equation is reported as
    INCOMPLETE_DATA rather than compared against another period's totals.

    Args:
        statement_or_df: A Statement object or pandas DataFrame containing balance sheet data
        level: Validation level. FUNDAMENTAL checks the equation; SECTIONS also
            checks current + non-current subtotals against total assets and total
            liabilities. DETAILED runs the same checks as SECTIONS: line-item
            rollups to subtotals are not implemented.
        tolerance: Absolute tolerance for rounding differences (default: $1)
        tolerance_pct: Percentage tolerance (default: 0.1% = 0.001)

    Returns:
        ValidationResult with validation status and any issues found

    Example:
        >>> from edgar import Company
        >>> company = Company("AAPL")
        >>> filing = company.get_filings(form="10-K").latest()
        >>> xbrl = filing.xbrl()
        >>> bs = xbrl.statements.balance_sheet()
        >>> result = validate_balance_sheet(bs)
        >>> print(result)
        ValidationResult: VALID (0 errors, 0 warnings)

    Raises:
        ValidationError: ``level`` is not a validation level.
    """
    level = _parse_level(level)
    issues: List[ValidationIssue] = []
    checks: List[str] = []
    metadata: Dict[str, Any] = {}

    # Convert Statement to DataFrame if needed
    if hasattr(statement_or_df, 'to_dataframe'):
        try:
            df = statement_or_df.to_dataframe(standard=True)
        except Exception as e:
            logger.warning("Failed to convert statement to DataFrame: %s", e)
            return ValidationResult(
                is_valid=False,
                issues=[ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="CONVERSION_ERROR",
                    message=f"Failed to convert statement to DataFrame: {e}"
                )],
                checks_performed=["statement_conversion"],
                metadata={"error": str(e)}
            )
    else:
        df = statement_or_df

    if df is None or df.empty:
        return ValidationResult(
            is_valid=False,
            issues=[ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="EMPTY_STATEMENT",
                message="Balance sheet is empty or could not be loaded"
            )],
            checks_performed=["data_check"],
            metadata={}
        )

    # Extract values, all from one column so the checks compare a single date
    column = _select_period_column(df)
    values = _get_balance_sheet_values(df, column)
    metadata["period"] = column
    metadata["extracted_values"] = {k: v for k, v in values.items() if v is not None}

    # Level 1: Fundamental equation check
    checks.append("fundamental_equation")

    assets = values.get("total_assets")
    liabilities = values.get("total_liabilities")
    equity = values.get("stockholders_equity") or values.get("total_equity_with_nci")
    liab_equity = values.get("liabilities_and_equity")
    nci = values.get("noncontrolling_interest")

    # Check for required values
    if assets is None:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            code="MISSING_ASSETS",
            message="Total Assets not found in balance sheet"
        ))

    equation_validated = False

    # Method 1 (Preferred): Assets = Liabilities and Equity (combined total)
    # This is most reliable as it uses the explicit total line
    if assets is not None and liab_equity is not None:
        diff = abs(assets - liab_equity)
        diff_pct = diff / max(abs(assets), 1) if assets != 0 else 0

        metadata["liab_equity_check"] = {
            "assets": assets,
            "liabilities_and_equity": liab_equity,
            "difference": diff,
            "difference_pct": diff_pct
        }

        if diff > tolerance and diff_pct > tolerance_pct:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="EQUATION_IMBALANCE",
                message=f"Assets ({assets:,.0f}) != Liabilities and Equity ({liab_equity:,.0f})",
                details={
                    "assets": assets,
                    "liabilities_and_equity": liab_equity,
                    "difference": diff,
                    "difference_pct": diff_pct
                }
            ))
        elif diff > 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                code="ROUNDING_ADJUSTMENT",
                message=f"Minor rounding difference of ${diff:,.0f} ({diff_pct:.4%})",
                details={"difference": diff}
            ))
        equation_validated = True

    # Method 2 (Fallback): Assets = Liabilities + Equity (components)
    # Use total_equity_with_nci first (more comprehensive), then stockholders_equity
    if not equation_validated and assets is not None and liabilities is not None:
        # Prefer comprehensive equity total over stockholders-only
        equity_for_calc = values.get("total_equity_with_nci") or values.get("stockholders_equity")

        if equity_for_calc is not None:
            expected = liabilities + equity_for_calc
            # Only add NCI if we're using stockholders_equity (not total_equity which already includes it)
            if values.get("total_equity_with_nci") is None and nci is not None:
                expected += nci

            diff = abs(assets - expected)
            diff_pct = diff / max(abs(assets), 1) if assets != 0 else 0

            metadata["equation_check"] = {
                "assets": assets,
                "liabilities": liabilities,
                "equity": equity_for_calc,
                "nci": nci if values.get("total_equity_with_nci") is None else None,
                "expected": expected,
                "difference": diff,
                "difference_pct": diff_pct
            }

            if diff > tolerance and diff_pct > tolerance_pct:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="EQUATION_IMBALANCE",
                    message=f"Accounting equation doesn't balance: Assets ({assets:,.0f}) != Liabilities ({liabilities:,.0f}) + Equity ({equity_for_calc:,.0f})",
                    details={
                        "assets": assets,
                        "liabilities_plus_equity": expected,
                        "difference": diff,
                        "difference_pct": diff_pct
                    }
                ))
            elif diff > 0:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    code="ROUNDING_ADJUSTMENT",
                    message=f"Minor rounding difference of ${diff:,.0f} ({diff_pct:.4%}) in accounting equation",
                    details={"difference": diff}
                ))
            equation_validated = True

    # Warn if we couldn't perform either check
    if not equation_validated and assets is not None:
        issues.append(_incomplete_equation_issue(df, column))

    # Level 2: Section validation
    if level in (ValidationLevel.SECTIONS, ValidationLevel.DETAILED):
        checks.append("section_totals")
        issues.extend(_check_section_totals(values, tolerance))

    # Determine overall validity (errors = invalid, warnings OK)
    is_valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)

    return ValidationResult(
        is_valid=is_valid,
        issues=issues,
        checks_performed=checks,
        metadata=metadata
    )


def validate_statement(
    statement: Any,
    statement_type: Optional[str] = None,
    level: ValidationLevel = ValidationLevel.FUNDAMENTAL
) -> ValidationResult:
    """
    Validate a financial statement based on its type.

    Dispatches to the appropriate validator based on statement type.
    Currently supports:
    - Balance Sheet: Accounting equation validation

    Future support planned for:
    - Income Statement: Revenue/expense consistency
    - Cash Flow Statement: Cash reconciliation

    Args:
        statement: A Statement object
        statement_type: Optional statement type override. If not provided,
                       will attempt to detect from the statement.
        level: Validation level (FUNDAMENTAL, SECTIONS, or DETAILED). DETAILED
            runs the same checks as SECTIONS; see validate_balance_sheet().

    Returns:
        ValidationResult with validation status and any issues found

    Raises:
        ValidationError: ``level`` is not a validation level.
    """
    level = _parse_level(level)

    # Try to detect statement type
    detected_type = statement_type

    if detected_type is None and hasattr(statement, 'canonical_type'):
        detected_type = statement.canonical_type

    if detected_type is None and hasattr(statement, 'role_or_type'):
        role = statement.role_or_type.lower()
        if 'balance' in role or 'financial position' in role:
            detected_type = 'BalanceSheet'
        elif 'income' in role or 'operations' in role:
            detected_type = 'IncomeStatement'
        elif 'cash' in role:
            detected_type = 'CashFlowStatement'

    # Dispatch to appropriate validator
    if detected_type == 'BalanceSheet':
        return validate_balance_sheet(statement, level=level)

    # For unsupported statement types, return a pass-through result
    return ValidationResult(
        is_valid=True,
        issues=[ValidationIssue(
            severity=ValidationSeverity.INFO,
            code="NO_VALIDATOR",
            message=f"No validator available for statement type: {detected_type}"
        )],
        checks_performed=["type_detection"],
        metadata={"detected_type": detected_type}
    )
