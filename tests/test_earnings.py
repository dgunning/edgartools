"""
Unit tests for edgar.earnings — data accuracy fixes (#633).

All tests are fast (no network, no VCR cassettes).
"""
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd
import pytest

from edgar.earnings import (
    FinancialTable,
    RowType,
    Scale,
    StatementType,
    _classify_row_type,
    _classify_statement,
    _detect_table_scale,
    _parse_numeric,
)


# ── _parse_numeric edge cases ──────────────────────────────────────────────


class TestParseNumeric:
    """Bug 5: Negative signs for parenthesized currency formats."""

    def test_dollar_outside_parens(self):
        """$(0.09) → -0.09"""
        assert _parse_numeric("$(0.09)") == -0.09

    def test_dollar_inside_parens(self):
        """($0.09) → -0.09"""
        assert _parse_numeric("($0.09)") == -0.09

    def test_parens_no_currency(self):
        """(0.09) → -0.09"""
        assert _parse_numeric("(0.09)") == -0.09

    def test_parens_large_negative(self):
        """(1,234.56) → -1234.56"""
        assert _parse_numeric("(1,234.56)") == -1234.56

    def test_dollar_inside_parens_large(self):
        """($1,234) → -1234.0"""
        assert _parse_numeric("($1,234)") == -1234.0

    def test_positive_currency(self):
        """$1,234.56 → 1234.56"""
        assert _parse_numeric("$1,234.56") == 1234.56

    def test_euro_currency(self):
        """€500 → 500.0"""
        assert _parse_numeric("€500") == 500.0

    def test_negative_euro(self):
        """(€500) → -500.0"""
        assert _parse_numeric("(€500)") == -500.0

    def test_dash_returns_none(self):
        """Em dash → None"""
        assert _parse_numeric("—") is None

    def test_en_dash_returns_none(self):
        """En dash → None"""
        assert _parse_numeric("–") is None

    def test_na_passthrough(self):
        """N/A stays as string"""
        assert _parse_numeric("N/A") == "N/A"

    def test_nm_passthrough(self):
        """n/m stays as string"""
        assert _parse_numeric("n/m") == "n/m"

    def test_none_input(self):
        assert _parse_numeric(None) is None

    def test_empty_string(self):
        assert _parse_numeric("") is None

    def test_asterisk(self):
        assert _parse_numeric("*") is None

    def test_plain_integer(self):
        assert _parse_numeric("42") == 42.0

    def test_whitespace_around_parens(self):
        """Handles whitespace inside currency+parens."""
        assert _parse_numeric(" ($0.09) ") == -0.09


# ── Scale.detect ───────────────────────────────────────────────────────────


class TestScaleDetect:
    """Scale.detect() works on arbitrary text strings."""

    def test_in_millions(self):
        assert Scale.detect("(In millions, except per share data)") == Scale.MILLIONS

    def test_in_thousands(self):
        assert Scale.detect("Amounts in thousands") == Scale.THOUSANDS

    def test_in_billions(self):
        assert Scale.detect("revenue of $143.8 billion in 2025") == Scale.BILLIONS

    def test_no_scale(self):
        assert Scale.detect("Plain text with no scale indicator") == Scale.UNITS

    def test_millions_word_boundary(self):
        assert Scale.detect("in millions") == Scale.MILLIONS

    def test_case_insensitive(self):
        assert Scale.detect("IN MILLIONS") == Scale.MILLIONS


# ── scaled_dataframe ──────────────────────────────────────────────────────


class TestScaledDataframe:
    """Bug 1: scaled_dataframe must actually apply scaling to object-dtype columns."""

    def test_scales_numeric_values(self):
        """Object-dtype columns with float values get multiplied by scale."""
        df = pd.DataFrame({
            "Item": ["Revenue", "Cost of Sales", "Gross Profit"],
            "Q1 2025": [143.8, 60.2, 83.6],
            "Q1 2024": [127.5, 54.1, 73.4],
        })
        # Force object dtype (as _extract_clean_dataframe does)
        df = df.astype(object)
        assert df["Q1 2025"].dtype == object

        table = FinancialTable(
            dataframe=df,
            scale=Scale.MILLIONS,
            statement_type=StatementType.INCOME_STATEMENT,
        )

        scaled = table.scaled_dataframe
        assert scaled["Q1 2025"].iloc[0] == 143.8 * 1_000_000
        assert scaled["Q1 2024"].iloc[1] == 54.1 * 1_000_000

    def test_preserves_non_numeric(self):
        """String labels in data columns survive scaling."""
        df = pd.DataFrame({
            "Item": ["Revenue", "Cost"],
            "Val": [100.0, "N/A"],
        }).astype(object)

        table = FinancialTable(dataframe=df, scale=Scale.THOUSANDS)
        scaled = table.scaled_dataframe
        # Numeric value is scaled
        assert scaled["Val"].iloc[0] == 100.0 * 1_000
        # Non-numeric value is preserved
        assert scaled["Val"].iloc[1] == "N/A"

    def test_units_returns_copy(self):
        """Scale.UNITS returns an unmodified copy."""
        df = pd.DataFrame({"A": [1.0, 2.0]}).astype(object)
        table = FinancialTable(dataframe=df, scale=Scale.UNITS)
        scaled = table.scaled_dataframe
        assert scaled["A"].iloc[0] == 1.0
        # Ensure it's a copy, not the same object
        assert scaled is not table.dataframe

    def test_scales_thousands(self):
        df = pd.DataFrame({"Val": [5.0, 10.0]}).astype(object)
        table = FinancialTable(dataframe=df, scale=Scale.THOUSANDS)
        scaled = table.scaled_dataframe
        assert scaled["Val"].iloc[0] == 5000.0

    def test_scales_billions(self):
        df = pd.DataFrame({"Val": [1.5]}).astype(object)
        table = FinancialTable(dataframe=df, scale=Scale.BILLIONS)
        scaled = table.scaled_dataframe
        assert scaled["Val"].iloc[0] == 1.5 * 1_000_000_000


# ── _detect_table_scale ───────────────────────────────────────────────────

# Minimal mock objects matching TableNode interface for unit tests


@dataclass
class _MockCell:
    content: str = ""


@dataclass
class _MockRow:
    cells: List[_MockCell] = field(default_factory=list)


@dataclass
class _MockTableNode:
    headers: List[List[_MockCell]] = field(default_factory=list)
    rows: List[_MockRow] = field(default_factory=list)
    footer: List[_MockRow] = field(default_factory=list)
    caption: Optional[str] = None


class TestDetectTableScale:
    """Bug 2: Per-table scale detection checks caption, headers, rows, footer, index."""

    def test_header_millions(self):
        node = _MockTableNode(
            headers=[[_MockCell("(In millions)")]]
        )
        df = pd.DataFrame({"A": [1]})
        assert _detect_table_scale(node, df, Scale.UNITS) == Scale.MILLIONS

    def test_header_thousands(self):
        node = _MockTableNode(
            headers=[[_MockCell("(In thousands)")]]
        )
        df = pd.DataFrame({"A": [1]})
        assert _detect_table_scale(node, df, Scale.UNITS) == Scale.THOUSANDS

    def test_caption_millions(self):
        node = _MockTableNode(caption="Revenue (in millions)")
        df = pd.DataFrame({"A": [1]})
        assert _detect_table_scale(node, df, Scale.UNITS) == Scale.MILLIONS

    def test_first_row_content(self):
        node = _MockTableNode(
            rows=[_MockRow(cells=[_MockCell("(in thousands)")])]
        )
        df = pd.DataFrame({"A": [1]})
        assert _detect_table_scale(node, df, Scale.UNITS) == Scale.THOUSANDS

    def test_footer_millions(self):
        node = _MockTableNode(
            footer=[_MockRow(cells=[_MockCell("Amounts in millions")])]
        )
        df = pd.DataFrame({"A": [1]})
        assert _detect_table_scale(node, df, Scale.UNITS) == Scale.MILLIONS

    def test_index_label_millions(self):
        node = _MockTableNode()
        df = pd.DataFrame({"A": [1, 2, 3]}, index=[
            "(In millions, except per share data)",
            "Revenue",
            "Cost",
        ])
        assert _detect_table_scale(node, df, Scale.UNITS) == Scale.MILLIONS

    def test_no_scale_returns_default(self):
        node = _MockTableNode()
        df = pd.DataFrame({"A": [1]})
        assert _detect_table_scale(node, df, Scale.UNITS) == Scale.UNITS

    def test_no_scale_with_billions_default(self):
        """When nothing is found per-table, falls back to default_scale."""
        node = _MockTableNode()
        df = pd.DataFrame({"A": [1]})
        # This tests the fallback behavior — caller now passes Scale.UNITS
        assert _detect_table_scale(node, df, Scale.BILLIONS) == Scale.BILLIONS

    def test_caption_takes_priority_over_default(self):
        """Caption 'millions' overrides a billions default."""
        node = _MockTableNode(caption="(In millions)")
        df = pd.DataFrame({"A": [1]})
        assert _detect_table_scale(node, df, Scale.BILLIONS) == Scale.MILLIONS


# ── _classify_statement ──────────────────────────────────────────────────


class TestClassifyStatement:
    """Bug 3: Improved income statement classification via titles and expanded keywords."""

    def test_title_income_statement(self):
        """Header 'Consolidated Statements of Operations' → INCOME_STATEMENT."""
        node = _MockTableNode(
            headers=[[_MockCell("Consolidated Statements of Operations")]],
            rows=[_MockRow(cells=[_MockCell("Revenue")])],
        )
        df = pd.DataFrame({"A": [1]}, index=["Revenue"])
        assert _classify_statement(node, df) == StatementType.INCOME_STATEMENT

    def test_title_condensed_balance_sheet(self):
        """Header 'Condensed Consolidated Balance Sheets' → BALANCE_SHEET."""
        node = _MockTableNode(
            headers=[[_MockCell("Condensed Consolidated Balance Sheets")]],
            rows=[_MockRow(cells=[_MockCell("Total assets")])],
        )
        df = pd.DataFrame({"A": [1]}, index=["Total assets"])
        assert _classify_statement(node, df) == StatementType.BALANCE_SHEET

    def test_title_cash_flow(self):
        """Header 'Consolidated Statements of Cash Flows' → CASH_FLOW."""
        node = _MockTableNode(
            headers=[[_MockCell("Consolidated Statements of Cash Flows")]],
            rows=[_MockRow(cells=[_MockCell("Net income")])],
        )
        df = pd.DataFrame({"A": [1]}, index=["Net income"])
        assert _classify_statement(node, df) == StatementType.CASH_FLOW

    def test_caption_based_title(self):
        """Caption 'Statements of Income' → INCOME_STATEMENT."""
        node = _MockTableNode(
            caption="Consolidated Statements of Income",
            rows=[_MockRow(cells=[_MockCell("Revenue")])],
        )
        df = pd.DataFrame({"A": [1]}, index=["Revenue"])
        assert _classify_statement(node, df) == StatementType.INCOME_STATEMENT

    def test_keyword_net_sales(self):
        """Expanded keywords: 'net sales' + 'cost of goods sold' → INCOME_STATEMENT."""
        node = _MockTableNode(
            rows=[
                _MockRow(cells=[_MockCell("Net sales")]),
                _MockRow(cells=[_MockCell("Cost of goods sold")]),
                _MockRow(cells=[_MockCell("Gross profit")]),
            ],
        )
        df = pd.DataFrame({"A": [1, 2, 3]}, index=[
            "Net sales", "Cost of goods sold", "Gross profit",
        ])
        assert _classify_statement(node, df) == StatementType.INCOME_STATEMENT

    def test_banking_keywords(self):
        """Banking keywords: 'net interest income' + 'total interest income' → INCOME_STATEMENT."""
        node = _MockTableNode(
            rows=[
                _MockRow(cells=[_MockCell("Net interest income")]),
                _MockRow(cells=[_MockCell("Total interest income")]),
                _MockRow(cells=[_MockCell("Provision for credit losses")]),
            ],
        )
        df = pd.DataFrame({"A": [1, 2, 3]}, index=[
            "Net interest income", "Total interest income",
            "Provision for credit losses",
        ])
        assert _classify_statement(node, df) == StatementType.INCOME_STATEMENT

    def test_unknown_fallback(self):
        """Table with no matching content → UNKNOWN."""
        node = _MockTableNode(
            rows=[
                _MockRow(cells=[_MockCell("Some random text")]),
                _MockRow(cells=[_MockCell("Another random row")]),
            ],
        )
        df = pd.DataFrame({"A": [1, 2]}, index=[
            "Some random text", "Another random row",
        ])
        assert _classify_statement(node, df) == StatementType.UNKNOWN


# ── _classify_row_type ────────────────────────────────────────────────────


class TestClassifyRowType:
    """Bug 4: Row-type metadata for distinguishing EPS, shares, and amounts."""

    def test_per_share_detection(self):
        """'Diluted earnings per share' → PER_SHARE."""
        assert _classify_row_type("Diluted earnings per share") == RowType.PER_SHARE

    def test_shares_detection(self):
        """'Weighted average diluted shares outstanding' → SHARES."""
        assert _classify_row_type("Weighted average diluted shares outstanding") == RowType.SHARES

    def test_percentage_detection(self):
        """'Operating margin' → PERCENTAGE."""
        assert _classify_row_type("Operating margin") == RowType.PERCENTAGE

    def test_amount_default(self):
        """'Total revenue' → AMOUNT (default)."""
        assert _classify_row_type("Total revenue") == RowType.AMOUNT

    def test_per_ads_variant(self):
        """'Net income per ADS' → PER_SHARE."""
        assert _classify_row_type("Net income per ADS") == RowType.PER_SHARE

    def test_per_adr_variant(self):
        """'Earnings per ADR' → PER_SHARE."""
        assert _classify_row_type("Earnings per ADR") == RowType.PER_SHARE

    def test_basic_shares(self):
        """'Basic shares' → SHARES."""
        assert _classify_row_type("Basic shares") == RowType.SHARES

    def test_effective_tax_rate(self):
        """'Effective tax rate' → PERCENTAGE."""
        assert _classify_row_type("Effective tax rate") == RowType.PERCENTAGE


# ── FinancialTable row_types integration ──────────────────────────────────


class TestFinancialTableRowTypes:
    """Bug 4: FinancialTable convenience methods for row-type metadata."""

    def _make_table(self, index, values=None, scale=Scale.MILLIONS):
        """Helper to create a FinancialTable with row_types populated."""
        if values is None:
            values = [100.0] * len(index)
        df = pd.DataFrame(
            {"Q1 2025": values},
            index=index,
        ).astype(object)
        row_types = {label: _classify_row_type(label) for label in index}
        return FinancialTable(
            dataframe=df,
            scale=scale,
            statement_type=StatementType.INCOME_STATEMENT,
            row_types=row_types,
        )

    def test_get_row_type(self):
        """get_row_type returns correct type or AMOUNT default."""
        table = self._make_table(["Revenue", "Diluted earnings per share"])
        assert table.get_row_type("Revenue") == RowType.AMOUNT
        assert table.get_row_type("Diluted earnings per share") == RowType.PER_SHARE
        # Unknown label defaults to AMOUNT
        assert table.get_row_type("Something unknown") == RowType.AMOUNT

    def test_per_share_rows_accessor(self):
        """per_share_rows returns only EPS rows from a mixed table."""
        table = self._make_table(
            ["Total revenue", "Diluted earnings per share",
             "Weighted average diluted shares outstanding", "Operating margin"],
            values=[100.0, 0.46, 50_780_325, 15.5],
        )
        eps_rows = table.per_share_rows
        assert len(eps_rows) == 1
        assert "Diluted earnings per share" in eps_rows.index

    def test_scaled_dataframe_skips_per_share(self):
        """EPS row unchanged, revenue row scaled."""
        table = self._make_table(
            ["Total revenue", "Diluted earnings per share"],
            values=[100.0, 0.46],
        )
        scaled = table.scaled_dataframe
        # Revenue should be scaled
        assert scaled.loc["Total revenue", "Q1 2025"] == 100.0 * 1_000_000
        # EPS should NOT be scaled
        assert scaled.loc["Diluted earnings per share", "Q1 2025"] == 0.46

    def test_scaled_dataframe_skips_shares(self):
        """Share count row unchanged after scaling."""
        table = self._make_table(
            ["Total revenue", "Weighted average diluted shares outstanding"],
            values=[100.0, 50_780_325],
        )
        scaled = table.scaled_dataframe
        # Revenue scaled
        assert scaled.loc["Total revenue", "Q1 2025"] == 100.0 * 1_000_000
        # Shares NOT scaled
        assert scaled.loc["Weighted average diluted shares outstanding", "Q1 2025"] == 50_780_325

    def test_scaled_dataframe_skips_percentage(self):
        """Percentage rows unchanged after scaling."""
        table = self._make_table(
            ["Total revenue", "Operating margin"],
            values=[100.0, 15.5],
        )
        scaled = table.scaled_dataframe
        assert scaled.loc["Total revenue", "Q1 2025"] == 100.0 * 1_000_000
        assert scaled.loc["Operating margin", "Q1 2025"] == 15.5

    def test_scaled_dataframe_units_unchanged(self):
        """Scale.UNITS returns copy without changes, regardless of row types."""
        table = self._make_table(
            ["Total revenue", "Diluted earnings per share"],
            values=[100.0, 0.46],
            scale=Scale.UNITS,
        )
        scaled = table.scaled_dataframe
        assert scaled.loc["Total revenue", "Q1 2025"] == 100.0
        assert scaled.loc["Diluted earnings per share", "Q1 2025"] == 0.46

    def test_scaled_dataframe_duplicate_columns(self):
        """Bug 6: scaled_dataframe should not crash on duplicate column names."""
        df = pd.DataFrame(
            {"Q1 2025": [100.0, 0.46], "Q1 2025": [200.0, 0.55]},
        )
        # Manually create duplicate columns (pandas deduplicates in constructor)
        df = pd.DataFrame(
            [[100.0, 200.0], [0.46, 0.55]],
            index=["Total revenue", "Diluted earnings per share"],
            columns=["Q1 2025", "Q1 2025"],
        ).astype(object)

        row_types = {
            "Total revenue": RowType.AMOUNT,
            "Diluted earnings per share": RowType.PER_SHARE,
        }
        table = FinancialTable(
            dataframe=df,
            scale=Scale.MILLIONS,
            statement_type=StatementType.INCOME_STATEMENT,
            row_types=row_types,
        )

        # Should not raise an error
        scaled = table.scaled_dataframe
        # Both duplicate columns should be scaled for the AMOUNT row
        assert scaled.iloc[0, 0] == 100.0 * 1_000_000
        assert scaled.iloc[0, 1] == 200.0 * 1_000_000
        # PER_SHARE row should not be scaled
        assert scaled.iloc[1, 0] == 0.46
        assert scaled.iloc[1, 1] == 0.55


# ── Bug 5: Split-cell negative sign detection ─────────────────────────────


class TestParseNumericSplitCell:
    """Bug 5: Negative detection for split-cell scenarios (unmatched parentheses)."""

    def test_opening_paren_only(self):
        """(1,234 → -1234.0 (opening paren from prior cell, closing missing)."""
        assert _parse_numeric("(1,234") == -1234.0

    def test_closing_paren_only(self):
        """1,234) → -1234.0 (closing paren, opening was in prior cell)."""
        assert _parse_numeric("1,234)") == -1234.0

    def test_dollar_opening_paren_only(self):
        """$(0.09 → -0.09 (split-cell with currency)."""
        assert _parse_numeric("$(0.09") == -0.09

    def test_dollar_closing_paren_only(self):
        """$0.09) → -0.09 (split-cell with currency)."""
        assert _parse_numeric("$0.09)") == -0.09

    def test_both_parens_still_works(self):
        """(1,234) → -1234.0 (complete parens still negative)."""
        assert _parse_numeric("(1,234)") == -1234.0

    def test_no_parens_still_positive(self):
        """1,234 → 1234.0 (no parens = positive)."""
        assert _parse_numeric("1,234") == 1234.0
