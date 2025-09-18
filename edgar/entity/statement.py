"""
Financial Statement wrapper classes with rich display and concept-aware formatting.

This module provides Statement classes that wrap pandas DataFrames with:
- Intelligent formatting based on financial concept types
- Rich display for professional presentation  
- Access to underlying data for calculations
- LLM-ready context generation
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd
from rich.box import SIMPLE, SIMPLE_HEAVY
from rich.console import Group
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .terminal_styles import get_current_scheme


@dataclass
class ConceptFormatting:
    """Formatting rules for specific financial concepts"""
    decimal_places: int = 2
    show_currency: bool = True
    scale_display: bool = True  # Show M, B suffixes
    percentage: bool = False


class FinancialStatement:
    """
    A wrapper around pandas DataFrame for financial statements with intelligent formatting.

    This class provides:
    - Concept-aware formatting (EPS to 2 decimals, revenue in millions, etc.)
    - Rich display for professional presentation
    - Access to underlying numeric data
    - LLM context generation
    """

    # Formatting rules by concept pattern
    CONCEPT_FORMATS = {
        # Earnings per share - always show decimals
        'earningspershare': ConceptFormatting(decimal_places=2, show_currency=False, scale_display=False),
        'earnings per share': ConceptFormatting(decimal_places=2, show_currency=False, scale_display=False),
        'eps': ConceptFormatting(decimal_places=2, show_currency=False, scale_display=False),

        # Ratios and percentages
        'ratio': ConceptFormatting(decimal_places=2, show_currency=False, scale_display=False),
        'margin': ConceptFormatting(decimal_places=1, show_currency=False, scale_display=False, percentage=True),
        'percent': ConceptFormatting(decimal_places=1, show_currency=False, scale_display=False, percentage=True),

        # Per-share values
        'per share': ConceptFormatting(decimal_places=2, show_currency=False, scale_display=False),
        'pershare': ConceptFormatting(decimal_places=2, show_currency=False, scale_display=False),
        'book value': ConceptFormatting(decimal_places=2, show_currency=False, scale_display=False),
        'dividend': ConceptFormatting(decimal_places=2, show_currency=False, scale_display=False),

        # Share counts - show full numbers with commas
        'shares outstanding': ConceptFormatting(decimal_places=0, show_currency=False, scale_display=False),
        'common stock': ConceptFormatting(decimal_places=0, show_currency=False, scale_display=False),
        'weighted average': ConceptFormatting(decimal_places=0, show_currency=False, scale_display=False),

        # Large financial amounts - show full numbers with commas
        'revenue': ConceptFormatting(decimal_places=0, show_currency=True, scale_display=False),
        'income': ConceptFormatting(decimal_places=0, show_currency=True, scale_display=False),
        'assets': ConceptFormatting(decimal_places=0, show_currency=True, scale_display=False),
        'liabilities': ConceptFormatting(decimal_places=0, show_currency=True, scale_display=False),
    }

    def __init__(self, 
                 data: pd.DataFrame, 
                 statement_type: str,
                 entity_name: str = "",
                 period_lengths: Optional[List[str]] = None,
                 mixed_periods: bool = False):
        """
        Initialize financial statement.

        Args:
            data: DataFrame with financial data
            statement_type: Type of statement (IncomeStatement, BalanceSheet, etc.)
            entity_name: Company name
            period_lengths: List of period lengths in the data
            mixed_periods: Whether data contains mixed period lengths
        """
        self.data = data
        self.statement_type = statement_type
        self.entity_name = entity_name
        self.period_lengths = period_lengths or []
        self.mixed_periods = mixed_periods

        # Store original numeric data
        self._numeric_data = data.copy()

    def get_concept_formatting(self, concept_label: str) -> ConceptFormatting:
        """
        Get formatting rules for a specific concept.

        Args:
            concept_label: Label of the financial concept

        Returns:
            ConceptFormatting rules for this concept
        """
        label_lower = concept_label.lower()

        # Check for exact matches first
        for pattern, formatting in self.CONCEPT_FORMATS.items():
            if pattern in label_lower:
                return formatting

        # Default formatting for large amounts - show full numbers with commas
        return ConceptFormatting(decimal_places=0, show_currency=True, scale_display=False)

    def format_value(self, value: float, concept_label: str) -> str:
        """
        Format a single value based on its concept.

        Args:
            value: Numeric value to format
            concept_label: Label of the financial concept

        Returns:
            Formatted string representation
        """
        if pd.isna(value):
            return ''

        formatting = self.get_concept_formatting(concept_label)

        # Handle percentage formatting
        if formatting.percentage:
            return f"{value:.{formatting.decimal_places}f}%"

        # Always use full number formatting with commas - no scaling to preserve precision
        if formatting.show_currency:
            return f"${value:,.{formatting.decimal_places}f}"
        else:
            return f"{value:,.{formatting.decimal_places}f}"

    def _repr_html_(self) -> str:
        """
        Rich HTML representation for Jupyter notebooks.

        Returns:
            HTML string for rich display
        """
        # Create a formatted copy as string DataFrame
        formatted_data = pd.DataFrame(index=self.data.index, columns=self.data.columns, dtype=str)

        # Apply formatting to each cell
        for index in self.data.index:
            concept_label = str(index)
            for column in self.data.columns:
                value = self.data.loc[index, column]
                if pd.notna(value) and isinstance(value, (int, float)):
                    formatted_data.loc[index, column] = self.format_value(value, concept_label)
                else:
                    formatted_data.loc[index, column] = str(value) if pd.notna(value) else ''

        # Create HTML with styling
        html = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
            <h3 style="color: #2c3e50; margin-bottom: 10px;">
                {self.entity_name} - {self.statement_type.replace('Statement', ' Statement')}
            </h3>
        """

        # Add period warning if mixed
        if self.mixed_periods:
            html += """
            <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; 
                       padding: 8px; margin-bottom: 10px; border-radius: 4px;">
                <strong>⚠️ Mixed Period Lengths:</strong> This statement contains periods of different lengths 
                ({periods}). Consider filtering to comparable periods for accurate analysis.
            </div>
            """.format(periods=', '.join(self.period_lengths))

        # Add the formatted table
        html += formatted_data.to_html(classes='financial-statement', 
                                     table_id='fs-table',
                                     escape=False)

        # Add CSS styling
        html += """
        <style>
        .financial-statement {
            border-collapse: collapse;
            width: 100%;
            font-size: 12px;
            margin-top: 10px;
        }
        .financial-statement th {
            background-color: #34495e;
            color: white;
            padding: 8px;
            text-align: right;
            font-weight: bold;
        }
        .financial-statement td {
            padding: 6px 8px;
            text-align: right;
            border-bottom: 1px solid #ecf0f1;
        }
        .financial-statement tr:hover {
            background-color: #f8f9fa;
        }
        .financial-statement tr:nth-child(even) {
            background-color: #fdfdfd;
        }
        .financial-statement td:first-child {
            text-align: left;
            font-weight: 500;
        }
        </style>
        </div>
        """

        return html

    def __str__(self) -> str:
        """
        String representation for console display.

        Returns:
            Formatted string representation
        """
        # Create formatted version as string DataFrame
        formatted_data = pd.DataFrame(index=self.data.index, columns=self.data.columns, dtype=str)

        # Apply formatting to each cell
        for index in self.data.index:
            concept_label = str(index)
            for column in self.data.columns:
                value = self.data.loc[index, column]
                if pd.notna(value) and isinstance(value, (int, float)):
                    formatted_data.loc[index, column] = self.format_value(value, concept_label)
                else:
                    formatted_data.loc[index, column] = str(value) if pd.notna(value) else ''

        header = f"\n{self.entity_name} - {self.statement_type.replace('Statement', ' Statement')}\n"
        header += "=" * len(header.strip()) + "\n"

        if self.mixed_periods:
            header += f"⚠️  Mixed period lengths: {', '.join(self.period_lengths)}\n\n"

        return header + str(formatted_data)

    def __rich__(self):
        """Creates a rich representation for professional financial statement display."""


        colors = get_current_scheme()

        if self.data.empty:
            return Panel(
                Text("No data available", style=colors["empty_value"]),
                title=f"📊 {self.statement_type.replace('Statement', ' Statement')}",
                border_style=colors["panel_border"]
            )

        # Statement type icon mapping
        icon_map = {
            'IncomeStatement': '💰',
            'BalanceSheet': '⚖️',
            'CashFlow': '💵',
            'Statement': '📊'
        }
        icon = icon_map.get(self.statement_type, '📊')

        # Title with company name and statement type
        if self.entity_name:
            title = Text.assemble(
                icon + " ",
                (self.entity_name, colors["company_name"]),
                " ",
                (self.statement_type.replace('Statement', ' Statement'), colors["statement_type"])
            )
        else:
            title = Text.assemble(
                icon + " ",
                (self.statement_type.replace('Statement', ' Statement'), colors["statement_type"])
            )

        # Create the main financial statement table
        statement_table = Table(box=SIMPLE, show_header=True, padding=(0, 1))
        statement_table.add_column("Line Item", style=colors["total_item"], no_wrap=True, max_width=30)

        # Add period columns (limit to reasonable number for display)
        periods = list(self.data.columns)
        display_periods = periods[:6]  # Show max 6 periods for readability
        has_more_periods = len(periods) > 6

        for period in display_periods:
            statement_table.add_column(str(period), justify="right", max_width=15)

        # Add rows with formatted values
        for index in self.data.index:
            concept_label = str(index)
            # Truncate long concept names
            display_label = concept_label[:28] + "..." if len(concept_label) > 30 else concept_label

            row_values = [display_label]
            for period in display_periods:
                value = self.data.loc[index, period]
                if pd.notna(value) and isinstance(value, (int, float)):
                    formatted_value = self.format_value(value, concept_label)
                    row_values.append(formatted_value)
                else:
                    row_values.append("-" if pd.isna(value) else str(value)[:12])

            statement_table.add_row(*row_values)

        # Create summary info panel
        info_table = Table(box=SIMPLE_HEAVY, show_header=False, padding=(0, 1))
        info_table.add_column("Metric", style=colors["low_confidence_item"])
        info_table.add_column("Value", style=colors["total_item"])

        info_table.add_row("Line Items", f"{len(self.data.index):,}")
        info_table.add_row("Periods", f"{len(self.data.columns):,}")
        if self.period_lengths:
            info_table.add_row("Period Types", ", ".join(set(self.period_lengths)))

        info_panel = Panel(
            info_table,
            title="📋 Statement Info",
            border_style="bright_black"
        )

        # Create period warning if needed
        warning_panel = None
        if self.mixed_periods:
            warning_text = Text.assemble(
                "⚠️  Mixed period lengths detected: ",
                (", ".join(self.period_lengths), "yellow"),
                "\nConsider filtering to comparable periods for accurate analysis."
            )
            warning_panel = Panel(
                warning_text,
                title="🚨 Period Warning",
                border_style=colors.get("warning", "yellow")
            )

        # Subtitle with additional info
        subtitle_parts = [f"{len(self.data.index):,} line items"]
        if has_more_periods:
            subtitle_parts.append(f"showing first {len(display_periods)} of {len(periods)} periods")
        subtitle = " • ".join(subtitle_parts)

        # Main statement panel
        statement_panel = Panel(
            statement_table,
            title="📊 Financial Data",
            subtitle=subtitle,
            border_style="bright_black"
        )

        # Combine all panels
        content_renderables = [
            Padding("", (1, 0, 0, 0)),
            info_panel
        ]

        if warning_panel:
            content_renderables.append(warning_panel)

        content_renderables.append(statement_panel)

        content = Group(*content_renderables)

        return Panel(
            content,
            title=title,
            border_style=colors["panel_border"]
        )

    def __repr__(self):
        """String representation using rich formatting."""
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())

    def to_numeric(self) -> pd.DataFrame:
        """
        Get the underlying numeric DataFrame for calculations.

        Returns:
            DataFrame with original numeric values
        """
        return self._numeric_data.copy()

    def to_llm_context(self) -> Dict[str, Any]:
        """
        Generate LLM-friendly context from the statement.

        Returns:
            Dictionary with structured financial data for LLM consumption
        """
        context = {
            "entity_name": self.entity_name,
            "statement_type": self.statement_type,
            "period_lengths": self.period_lengths,
            "mixed_periods": self.mixed_periods,
            "periods": list(self.data.columns),
            "line_items": {}
        }

        # Convert each line item to LLM-friendly format
        for index in self.data.index:
            concept_label = str(index)
            line_item = {
                "label": concept_label,
                "values": {},
                "formatting": self.get_concept_formatting(concept_label).__dict__
            }

            for column in self.data.columns:
                value = self.data.loc[index, column]
                if pd.notna(value):
                    line_item["values"][str(column)] = {
                        "raw_value": float(value),
                        "formatted_value": self.format_value(value, concept_label)
                    }

            context["line_items"][concept_label] = line_item

        return context

    def get_concept(self, concept_name: str) -> Optional[pd.Series]:
        """
        Get data for a specific concept across all periods.

        Args:
            concept_name: Name of the concept to retrieve

        Returns:
            Series with values across periods, or None if not found
        """
        # Try exact match first
        if concept_name in self.data.index:
            return self.data.loc[concept_name]

        # Try case-insensitive partial match
        concept_lower = concept_name.lower()
        for index in self.data.index:
            if concept_lower in str(index).lower():
                return self.data.loc[index]

        return None

    def calculate_growth(self, concept_name: str, periods: int = 2) -> Optional[pd.Series]:
        """
        Calculate period-over-period growth for a concept.

        Args:
            concept_name: Name of the concept
            periods: Number of periods to calculate growth over

        Returns:
            Series with growth rates, or None if concept not found
        """
        concept_data = self.get_concept(concept_name)
        if concept_data is None:
            return None

        # Calculate percentage change
        return concept_data.pct_change(periods=periods) * 100

    @property
    def shape(self) -> tuple:
        """Get the shape of the underlying data."""
        return self.data.shape

    @property
    def columns(self) -> pd.Index:
        """Get the columns of the underlying data."""
        return self.data.columns

    @property
    def index(self) -> pd.Index:
        """Get the index of the underlying data."""
        return self.data.index

    @property 
    def empty(self) -> bool:
        """Check if the underlying DataFrame is empty."""
        return self.data.empty

    def __len__(self) -> int:
        """Get the length of the underlying DataFrame."""
        return len(self.data)
