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
    Scale,
    StatementType,
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
