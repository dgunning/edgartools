"""
Rendering functions for XBRL data.

This module provides functions for formatting and displaying XBRL data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import pandas as pd
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table as RichTable
from rich.text import Text

from edgar.files.html import Document
from edgar.formatting import cik_text
from edgar.richtools import repr_rich, rich_to_text
from edgar.xbrl import standardization
from edgar.xbrl.core import determine_dominant_scale, format_date, format_value, parse_date

# Import color schemes from entity package
try:
    import os

    from edgar.entity.terminal_styles import get_color_scheme

    def get_xbrl_color_scheme():
        """Get XBRL-specific color scheme with filing as default."""
        scheme_name = os.environ.get("EDGAR_FINANCIALS_COLOR_SCHEME", "filing")  # Default to filing for XBRL
        return get_color_scheme(scheme_name)

except ImportError:
    # Fallback if terminal_styles not available
    def get_xbrl_color_scheme():
        return {
            "abstract_item": "bold",
            "total_item": "bold",
            "regular_item": "",
            "low_confidence_item": "dim",
            "positive_value": "",
            "negative_value": "",
            "total_value_prefix": "bold",
            "separator": "dim",
            "company_name": "bold",
            "statement_type": "bold",
            "panel_border": "white",
            "empty_value": "dim",
        }

# Enhanced style configuration using XBRL color schemes
def get_xbrl_styles():
    """Get XBRL rendering styles based on current color scheme."""
    colors = get_xbrl_color_scheme()

    return {
        'header': {
            'company_name': colors['company_name'],
            'statement_title': colors['statement_type'],
            'top_level': colors['abstract_item'],  # Major sections like ASSETS, LIABILITIES
            'section': colors['total_item'],       # Subtotals like Current assets
            'subsection': colors['regular_item']   # Regular line items
        },
        'value': {
            'positive': colors['positive_value'],
            'negative': colors['negative_value'],
            'total': colors['total_value_prefix'],
            'empty': colors['empty_value']
        },
        'structure': {
            'separator': colors['separator'],
            'border': colors['panel_border'],
            'abstract': colors['abstract_item'],
            'total': colors['total_item'],
            'regular': colors['regular_item'],
            'low_confidence': colors['low_confidence_item']
        },
        'comparison': {
            'increase': {'symbol': '▲', 'color': colors['positive_value']},
            'decrease': {'symbol': '▼', 'color': colors['negative_value']},
            'unchanged': {'symbol': '•', 'color': colors['separator']}
        }
    }

# Legacy fallback for existing code
DEFAULT_STYLES = get_xbrl_styles()

# Configuration for comparative analysis
COMPARISON_CONFIG = {
    'threshold': 0.01,  # 1% change threshold
    'enabled_types': ['IncomeStatement', 'CashFlowStatement'],  # Statement types to show comparisons for
    'excluded_concepts': ['us-gaap_SharesOutstanding', 'us-gaap_CommonStockSharesOutstanding']  # Concepts to exclude
}

def _apply_style(text: str, style_config: dict) -> str:
    """Apply rich text styling based on configuration.

    Args:
        text: Text to style
        style_config: Style configuration dictionary with 'style' and optional 'color' keys

    Returns:
        str: Styled text with rich markup
    """
    style = style_config.get('style', 'none')
    color = style_config.get('color', 'default')
    case = style_config.get('case', 'none')

    # Apply text case transformation
    if case == 'upper':
        text = text.upper()
    elif case == 'title':
        text = text.title()

    # Build style tags
    tags = []
    if style == 'bold':
        tags.append('bold')
    if style == 'italic':
        tags.append('italic')
    if style == 'dim':
        tags.append('dim')
    if color != 'default':
        tags.append(color)

    # Apply styling
    if tags:
        return f"[{' '.join(tags)}]{text}[/{' '.join(tags)}]"
    return text

def _calculate_comparison(current_value: Any, previous_value: Any) -> Optional[Tuple[float, str]]:
    """Calculate the percentage change between two values.

    Args:
        current_value: Current period value
        previous_value: Previous period value

    Returns:
        Tuple of (percentage_change, comparison_symbol) or None if comparison not possible
    """
    try:
        if isinstance(current_value, str):
            current_value = float(current_value.replace(',', ''))
        if isinstance(previous_value, str):
            previous_value = float(previous_value.replace(',', ''))

        if previous_value == 0:
            if current_value == 0:
                return (0.0, 'unchanged')
            return (float('inf'), 'increase' if current_value > 0 else 'decrease')

        pct_change = (current_value - previous_value) / abs(previous_value)

        if abs(pct_change) < COMPARISON_CONFIG['threshold']:
            return (0.0, 'unchanged')
        return (pct_change, 'increase' if pct_change > 0 else 'decrease')
    except (ValueError, TypeError):
        return None

@dataclass
class PeriodData:
    """Data about a single period for display in a statement."""
    key: str  # The period key (e.g., "instant_2023-12-31")
    label: str  # The formatted display label (e.g., "Dec 31, 2023")
    end_date: Optional[str] = None  # The end date in YYYY-MM-DD format
    start_date: Optional[str] = None  # The start date for duration periods
    is_duration: bool = False  # Whether this is a duration period
    quarter: Optional[str] = None  # Quarter identifier if applicable (Q1-Q4)


@dataclass
class StatementCell:
    """A single cell in a statement row."""
    value: Any
    style: Dict[str, str] = field(default_factory=dict)  # Style attributes like color, bold, etc.
    comparison: Optional[Dict[str, Any]] = None  # Comparison info if applicable
    # Custom formatter for the cell value
    formatter: Callable[[Any], str] = str  # Using built-in str function directly

    def get_formatted_value(self) -> str:
        return self.formatter(self.value)

@dataclass
class StatementRow:
    """A row in a financial statement."""
    label: str
    level: int  # Indentation/hierarchy level
    cells: List[StatementCell] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional info like concept name, type, etc.
    is_abstract: bool = False
    is_dimension: bool = False
    has_dimension_children: bool = False


@dataclass
class StatementHeader:
    """Header information for a financial statement."""
    columns: List[str] = field(default_factory=list)  # Period labels
    period_keys: List[str] = field(default_factory=list)  # Period keys for mapping to data
    periods: List[PeriodData] = field(default_factory=list)  # Detailed period information
    metadata: Dict[str, Any] = field(default_factory=dict)  # Info like date ranges, fiscal periods


@dataclass
class RenderedStatement:
    """Complete representation of a financial statement.

    This class provides an intermediate representation of statement data
    that can be used by different rendering backends (e.g. rich, web, etc).
    """
    title: str
    header: StatementHeader
    rows: List[StatementRow]
    metadata: Dict[str, Any] = field(default_factory=dict)  # Statement-level metadata like units, scales
    statement_type: str = ""
    fiscal_period_indicator: Optional[str] = None
    units_note: Optional[str] = None

    @property
    def periods(self):
        return self.header.periods

    def __rich__(self) -> RichTable:
        """Render as a rich table with professional styling"""
        # Get professional color scheme
        styles = get_xbrl_styles()

        # Clean up title - remove internal terminology like "(Standardized)"
        clean_title = self.title.replace("(Standardized)", "").strip()

        # Build title hierarchy with improved visual design
        title_parts = []

        # Main title (bold, prominent)
        title_parts.append(f"[{styles['header']['statement_title']}]{clean_title}[/{styles['header']['statement_title']}]")

        # Subtitle: fiscal period indicator (normal weight)
        if self.fiscal_period_indicator:
            title_parts.append(f"{self.fiscal_period_indicator}")

        # Units note (dim, subtle)
        if self.units_note:
            title_parts.append(f"[{styles['structure']['separator']}]{self.units_note}[/{styles['structure']['separator']}]")

        # Create the table with clean title hierarchy
        table = RichTable(title="\n".join(title_parts), 
                         box=box.SIMPLE, 
                         border_style=styles['structure']['border'])

        # Add columns with right-alignment for numeric columns
        table.add_column("", justify="left")
        for column in self.header.columns:
            # Apply styling to column headers
            header_style = styles['structure']['total']
            if header_style:
                styled_column = Text(column, style=header_style)
                table.add_column(styled_column)
            else:
                table.add_column(column)

        # Add rows with professional styling
        for row in self.rows:
            # Format the label based on level and properties with professional colors
            indent = "  " * row.level

            if row.is_dimension:
                # Format dimension items with italic style
                label_text = f"{indent}{row.label}"
                style = styles['structure']['low_confidence']
                styled_label = Text(label_text, style=style) if style else Text(label_text)
            elif row.is_abstract:
                if row.level == 0:
                    # Top-level header - major sections like ASSETS, LIABILITIES
                    label_text = row.label.upper()
                    style = styles['header']['top_level']
                    styled_label = Text(label_text, style=style) if style else Text(label_text)
                elif row.level == 1:
                    # Section header - subtotals like Current assets
                    label_text = row.label
                    style = styles['header']['section']
                    styled_label = Text(label_text, style=style) if style else Text(label_text)
                else:
                    # Sub-section header - indented, bold
                    sub_indent = "  " * (row.level - 1)
                    label_text = f"{sub_indent}{row.label}"
                    style = styles['header']['subsection']
                    styled_label = Text(label_text, style=style) if style else Text(label_text)
            else:
                # Regular line items - indented based on level
                if row.has_dimension_children and row.cells:
                    # Items with dimension children get bold styling and colon
                    label_text = f"{indent}{row.label}:"
                    style = styles['structure']['total']
                    styled_label = Text(label_text, style=style) if style else Text(label_text)
                else:
                    # Regular line items
                    label_text = f"{indent}{row.label}"
                    style = styles['header']['subsection'] if styles['header']['subsection'] else None
                    styled_label = Text(label_text, style=style) if style else Text(label_text)

            # Convert cells to their display representation with value-based styling
            cell_values = []
            for cell in row.cells:
                if cell.value is None or cell.value == "":
                    # Empty values - create empty Text object
                    cell_values.append(Text("", justify="right"))
                else:
                    # Format the cell value first
                    cell_value = cell.formatter(cell.value)
                    cell_str = str(cell_value)

                    # Determine the style to apply based on content
                    if row.is_abstract or "Total" in row.label:
                        # Totals get special styling
                        style = styles['value']['total']
                    elif cell_str.startswith('(') or cell_str.startswith('-') or cell_str.startswith('$('):
                        # Negative values
                        style = styles['value']['negative']
                    else:
                        # Positive values
                        style = styles['value']['positive']

                    # Create Rich Text object with proper styling
                    if style:
                        # Apply the style directly to the Text object
                        text_obj = Text(cell_str, style=style, justify="right")
                    else:
                        text_obj = Text(cell_str, justify="right")

                    cell_values.append(text_obj)

            table.add_row(styled_label, *cell_values)

        # Add footer metadata as table caption
        footer_parts = []

        # Extract metadata if available
        company_name = self.metadata.get('company_name')
        form_type = self.metadata.get('form_type')
        period_end = self.metadata.get('period_end')
        fiscal_period = self.metadata.get('fiscal_period')

        # Build footer with available information
        if company_name:
            footer_parts.append(company_name)
        if form_type:
            footer_parts.append(f"Form {form_type}")
        if period_end:
            footer_parts.append(f"Period ending {period_end}")
        if fiscal_period:
            footer_parts.append(f"Fiscal {fiscal_period}")

        # Always add source
        footer_parts.append("Source: SEC XBRL")

        # Apply dim styling to footer
        if footer_parts:
            footer_text = " • ".join(footer_parts)
            table.caption = f"[{styles['structure']['separator']}]{footer_text}[/{styles['structure']['separator']}]"

        return table

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self) -> str:
        """Convert to string with proper width to avoid truncation."""
        from edgar.richtools import rich_to_text
        return rich_to_text(self.__rich__(), width=150)

    def to_dataframe(self, include_unit: bool = False, include_point_in_time: bool = False) -> Any:
        """Convert to a pandas DataFrame

        Args:
            include_unit: If True, add a 'unit' column with unit information (e.g., 'usd', 'shares', 'usdPerShare')
            include_point_in_time: If True, add a 'point_in_time' boolean column (True for 'instant', False for 'duration')

        Returns:
            pd.DataFrame: DataFrame with statement data and optional unit/point-in-time columns
        """
        try:
            from edgar.xbrl.core import get_unit_display_name
            from edgar.xbrl.core import is_point_in_time as get_is_point_in_time

            # Create rows for the DataFrame
            df_rows = []

            # Create column map - use end_date from period data if available
            column_map = {}
            for i, period in enumerate(self.header.periods):
                # Use date strings as column names if available
                if period.end_date:
                    # Optional: add quarter info to column name
                    if period.quarter:
                        column_map[i] = f"{period.end_date} ({period.quarter})"
                    else:
                        column_map[i] = period.end_date
                else:
                    # Fallback to the display label
                    column_map[i] = self.header.columns[i]

            for row in self.rows:
                df_row = {
                    'concept': row.metadata.get('concept', ''),
                    'label': row.label
                }

                # Add unit column if requested
                if include_unit:
                    # Get units from row metadata
                    units_dict = row.metadata.get('units', {})
                    # Get the first non-None unit (all periods should have same unit for a given concept)
                    unit_ref = None
                    for period_key in self.header.period_keys:
                        if period_key in units_dict and units_dict[period_key] is not None:
                            unit_ref = units_dict[period_key]
                            break
                    # Convert to display name
                    df_row['unit'] = get_unit_display_name(unit_ref)

                # Add point_in_time column if requested
                if include_point_in_time:
                    # Get period_types from row metadata
                    period_types_dict = row.metadata.get('period_types', {})
                    # Get the first non-None period_type (all periods should have same type structure)
                    period_type = None
                    for period_key in self.header.period_keys:
                        if period_key in period_types_dict and period_types_dict[period_key] is not None:
                            period_type = period_types_dict[period_key]
                            break
                    # Convert to boolean
                    df_row['point_in_time'] = get_is_point_in_time(period_type)

                # Add cell values using date string column names where available
                for i, cell in enumerate(row.cells):
                    if i < len(self.header.periods):
                        column_name = column_map[i]
                        df_row[column_name] = cell.value

                df_row['level'] = row.level
                df_row['abstract'] = row.is_abstract
                df_row['dimension'] = row.is_dimension

                df_rows.append(df_row)

            return pd.DataFrame(df_rows)
        except ImportError:
            return "Pandas is required for DataFrame conversion"

    def to_markdown(self) -> str:
        """Convert to a markdown table representation"""
        lines = []

        # Add title as a header
        lines.append(f"## {self.title}")
        lines.append("")

        # Add subtitle info if available
        if self.fiscal_period_indicator or self.units_note:
            subtitle_parts = []
            if self.fiscal_period_indicator:
                subtitle_parts.append(f"**{self.fiscal_period_indicator}**")
            if self.units_note:
                # Remove rich formatting tags from units note
                clean_units = self.units_note.replace('[italic]', '').replace('[/italic]', '')
                subtitle_parts.append(f"*{clean_units}*")

            lines.append(" ".join(subtitle_parts))
            lines.append("")

        # Create header row
        header = [""] + self.header.columns
        lines.append("| " + " | ".join(header) + " |")

        # Add separator row
        separator = ["---"] + ["---" for _ in self.header.columns]
        lines.append("| " + " | ".join(separator) + " |")

        # Add data rows
        for row in self.rows:
            # Handle indentation for row label
            indent = "  " * row.level

            # Format row label based on properties
            if row.is_abstract:
                label = f"**{indent}{row.label}**"
            elif row.is_dimension:
                label = f"*{indent}{row.label}*"
            else:
                label = f"{indent}{row.label}"

            # Format cell values
            cell_values = []
            for cell in row.cells:
                cell_value = cell.formatter(cell.value)
                if cell_value is None or cell_value == "":
                    cell_values.append("")
                elif isinstance(cell_value, Text):
                    cell_values.append(str(cell_value))
                else:
                    cell_values.append(cell_value)

            # Add the row
            row_data = [label] + cell_values
            lines.append("| " + " | ".join(row_data) + " |")

        return "\n".join(lines)


def _format_comparison(pct_change: float, comparison_type: str) -> str:
    """Format a comparison indicator with the appropriate symbol and color.

    Args:
        pct_change: Percentage change value
        comparison_type: Type of comparison ('increase', 'decrease', or 'unchanged')

    Returns:
        str: Formatted comparison indicator with rich markup
    """
    style = DEFAULT_STYLES['comparison'][comparison_type]
    color = style['color']
    symbol = style['symbol']

    if comparison_type != 'unchanged':
        pct_text = f" {abs(pct_change):.1%}"
    else:
        pct_text = ""

    return f"[{color}]{symbol}{pct_text}[/{color}]"

share_concepts = [
    'us-gaap_CommonStockSharesOutstanding',
    'us-gaap_WeightedAverageNumberOfSharesOutstandingBasic',
    'us-gaap_WeightedAverageNumberOfSharesOutstandingDiluted',
    'us-gaap_WeightedAverageNumberOfDilutedSharesOutstanding',
    'us-gaap_CommonStockSharesIssued',
]

eps_concepts = [
    'us-gaap_EarningsPerShareBasic',
    'us-gaap_EarningsPerShareDiluted',
    'us-gaap_EarningsPerShareBasicAndDiluted',
    'us-gaap_IncomeLossFromContinuingOperationsPerBasicShare',
    'us-gaap_IncomeLossFromContinuingOperationsPerDilutedShare',
    'us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTaxPerBasicShare',
    'us-gaap_IncomeLossFromDiscontinuedOperationsNetOfTaxPerDilutedShare',
    'us-gaap_NetAssetValuePerShare',
    'us-gaap_BookValuePerShare',
    'us-gaap_CommonStockDividendsPerShareDeclared',
    'us-gaap_CommonStockDividendsPerShareCashPaid',
    'us-gaap_CommonStockParOrStatedValuePerShare',
]


def _is_html(text: str) -> bool:
    """
    Simple check to determine if a string contains HTML content.

    Args:
        text: The string to check

    Returns:
        bool: True if the string appears to contain HTML, False otherwise
    """
    html_tags = ['<p', '<div', '<span', '<br', '<table', '<tr', '<td', '<th',
                '<ul>', '<li', '<ol>', '<h1>', '<h2>', '<h3>', '<h4>', '<h5>', '<h6>']

    text_lower = text.lower()
    return any(tag in text_lower for tag in html_tags)


def html_to_text(html: str) -> str:
    """
    Convert HTML to plain text.

    Args:
        html: HTML content to convert

    Returns:
        str: Plain text representation of the HTML
    """
    # Wrap in html tag if not present
    html = f"<html>{html}</html>" if not html.startswith("<html>") else html
    document = Document.parse(html)
    return rich_to_text(document.__str__(), width=80)


def _format_period_labels(
    periods_to_display: List[Tuple[str, str]], 
    entity_info: Dict[str, Any],
    statement_type: str,
    show_date_range: bool = False
) -> Tuple[List[PeriodData], Optional[str]]:
    """
    Format period labels for display and determine fiscal period indicator.

    This function processes period keys and labels to create human-readable period labels
    for financial statements. When show_date_range=True, duration periods are displayed
    with both start and end dates (e.g., "Jan 1, 2023 - Mar 31, 2023"). When 
    show_date_range=False (default), only the end date is shown (e.g., "Mar 31, 2023").

    The function handles various input formats:
    1. Period keys in standard format (instant_YYYY-MM-DD or duration_YYYY-MM-DD_YYYY-MM-DD)
    2. Original labels with full or abbreviated month names
    3. Special formatted labels with date range information

    For quarterly periods, quarter numbers (Q1-Q4) are added to provide additional context.

    Args:
        periods_to_display: List of period keys and original labels
        entity_info: Entity information dictionary
        statement_type: Type of statement (BalanceSheet, IncomeStatement, etc.)
        show_date_range: Whether to show full date ranges for duration periods

    Returns:
        Tuple of (formatted_periods, fiscal_period_indicator)
        where formatted_periods is a list of PeriodData objects containing detailed period information
    """
    formatted_periods = []
    fiscal_period_indicator = None

    # We get entity_info but don't currently use document_period_end_date
    # Uncomment if needed: doc_period_end_date = entity_info.get('document_period_end_date')

    # Analyze ALL periods to detect mixed period types (not just the first one)
    period_types = []
    is_balance_sheet = False

    if periods_to_display:
        # Check if this is a balance sheet (instant periods)
        first_period_key = periods_to_display[0][0]
        is_balance_sheet = first_period_key.startswith('instant_')

        if is_balance_sheet:
            # For Balance Sheet - simple "As of" indicator
            fiscal_period_indicator = "As of"
            # Include dates in the indicator if multiple periods
            if len(periods_to_display) > 1:
                try:
                    dates = []
                    for period_key, _ in periods_to_display:
                        if period_key.startswith('instant_'):
                            date_str = period_key.split('_')[1]
                            date_obj = parse_date(date_str)
                            dates.append(date_obj.strftime("%B %d, %Y"))

                    if len(dates) == 2:
                        fiscal_period_indicator = f"As of {dates[0]} and {dates[1]}"
                    else:
                        fiscal_period_indicator = "As of"
                except (ValueError, TypeError, IndexError):
                    fiscal_period_indicator = "As of"
        else:
            # For Income/Cash Flow - analyze duration periods to detect mixed types
            for period_key, _ in periods_to_display:
                if not period_key.startswith('instant_') and '_' in period_key:
                    try:
                        parts = period_key.split('_')
                        if len(parts) >= 3:
                            start_date = parse_date(parts[1])
                            end_date = parse_date(parts[2])
                            duration_days = (end_date - start_date).days

                            # Categorize by duration
                            if 85 <= duration_days <= 95:
                                period_types.append("quarterly")
                            elif 175 <= duration_days <= 190:
                                period_types.append("semi-annual")
                            elif 265 <= duration_days <= 285:
                                period_types.append("nine-month")
                            elif 355 <= duration_days <= 375:
                                period_types.append("annual")
                            else:
                                period_types.append("other")
                    except (ValueError, TypeError, IndexError):
                        period_types.append("other")

            # Generate fiscal period indicator based on detected types
            unique_types = list(set(period_types))

            if len(unique_types) == 1:
                # Single period type
                period_type = unique_types[0]
                if period_type == "quarterly":
                    fiscal_period_indicator = "Three Months Ended"
                elif period_type == "semi-annual":
                    fiscal_period_indicator = "Six Months Ended"
                elif period_type == "nine-month":
                    fiscal_period_indicator = "Nine Months Ended"
                elif period_type == "annual":
                    fiscal_period_indicator = "Year Ended"
                else:
                    fiscal_period_indicator = "Period Ended"
            elif "quarterly" in unique_types and "nine-month" in unique_types:
                # Mixed quarterly and YTD - common for Q3 reports
                fiscal_period_indicator = "Three and Nine Months Ended"
            elif "quarterly" in unique_types and "semi-annual" in unique_types:
                # Mixed quarterly and semi-annual - common for Q2 reports
                fiscal_period_indicator = "Three and Six Months Ended"
            elif "quarterly" in unique_types and "annual" in unique_types:
                # Mixed quarterly and annual - common for Q4/year-end reports
                fiscal_period_indicator = "Three Months and Year Ended"
            elif len(unique_types) > 1:
                # Other mixed types
                fiscal_period_indicator = "Multiple Periods Ended"
            else:
                fiscal_period_indicator = "Period Ended"

    # Create formatted period columns
    for period_key, original_label in periods_to_display:
        # Extract start/end dates from duration periods for date range display
        start_date_obj = None
        end_date_obj = None
        start_date_str = None
        end_date_str = None
        is_duration = False
        duration_days = 0
        q_num = None

        # Parse dates from period key for duration periods
        if not period_key.startswith('instant_') and '_' in period_key and len(period_key.split('_')) >= 3:
            parts = period_key.split('_')
            try:
                start_date_str = parts[1]
                end_date_str = parts[2]
                start_date_obj = parse_date(start_date_str)
                end_date_obj = parse_date(end_date_str)
                is_duration = True
                duration_days = (end_date_obj - start_date_obj).days

                # Determine quarter number for quarterly periods
                if 80 <= duration_days <= 100:  # Quarterly period
                    month = end_date_obj.month
                    if month <= 3 or month == 12:
                        q_num = "Q1"
                    elif month <= 6:
                        q_num = "Q2"
                    elif month <= 9:
                        q_num = "Q3"
                    else:
                        q_num = "Q4"
            except (ValueError, TypeError, IndexError):
                pass
        # For instant periods, extract the date
        elif period_key.startswith('instant_'):
            try:
                end_date_str = period_key.split('_')[1]
                end_date_obj = parse_date(end_date_str)
            except (ValueError, TypeError, IndexError):
                pass

        # Start with the original label or an empty string
        final_label = ""

        # First check for date range labels with "to" - prioritize this check
        if original_label and 'to' in original_label:
            # Handle date range labels like "Annual: September 25, 2022 to September 30, 2023"
            try:
                parts = original_label.split(' to ')
                if len(parts) > 1:
                    if show_date_range:
                        # Use the full date range that's already in the label
                        final_label = original_label
                    else:
                        # Extract just the end date when show_date_range is False
                        end_date_display_str = parts[1].strip()
                        try:
                            if not end_date_obj:  # If we don't already have end_date from period_key
                                end_date_obj = parse_date(end_date_display_str)
                                if end_date_obj:
                                    end_date_str = end_date_obj.strftime('%Y-%m-%d')
                            final_label = format_date(end_date_obj)

                            # Add quarter info if available
                            if q_num and statement_type in ['IncomeStatement', 'CashFlowStatement']:
                                final_label = f"{final_label} ({q_num})"
                            # Add YTD indicator for year-to-date periods
                            elif duration_days and statement_type in ['IncomeStatement', 'CashFlowStatement']:
                                if 175 <= duration_days <= 190:  # ~6 months
                                    final_label = f"{final_label} (YTD)"
                                elif 265 <= duration_days <= 285:  # ~9 months
                                    final_label = f"{final_label} (YTD)"
                        except (ValueError, TypeError):
                            # If we can't parse the end date, use the original label
                            final_label = end_date_display_str

                    # Try to parse start date if we're dealing with a duration
                    if is_duration and not start_date_str and 'to' in original_label:
                        try:
                            start_date_display_str = parts[0].split(':')[-1].strip()
                            start_date_tmp = parse_date(start_date_display_str)
                            if start_date_tmp:
                                start_date_str = start_date_tmp.strftime('%Y-%m-%d')
                        except (ValueError, TypeError, IndexError):
                            pass
            except (ValueError, TypeError, IndexError):
                # If any parsing fails, leave label unchanged
                final_label = original_label

        # Case 1: If we still don't have a final label and have a date with commas, process it
        elif not final_label and original_label and ',' in original_label:
            for full_month, abbr in [
                ('January', 'Jan'), ('February', 'Feb'), ('March', 'Mar'),
                ('April', 'Apr'), ('May', 'May'), ('June', 'Jun'),
                ('July', 'Jul'), ('August', 'Aug'), ('September', 'Sep'),
                ('October', 'Oct'), ('November', 'Nov'), ('December', 'Dec')
            ]:
                if full_month in original_label:
                    try:
                        # Extract year from the original label
                        year = int(''.join(c for c in original_label.split(',')[1] if c.isdigit()))
                        # Extract day - find digits after the month
                        day_part = original_label.split(full_month)[1].strip()
                        day = int(''.join(c for c in day_part.split(',')[0] if c.isdigit()))
                        month_num = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                                   'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}[abbr]

                        try:
                            date_obj = datetime(year, month_num, day).date()
                            # If we don't already have an end date from the period key
                            if not end_date_obj:
                                end_date_obj = date_obj
                                end_date_str = date_obj.strftime('%Y-%m-%d')

                            final_label = format_date(date_obj)
                            # If showing date range and we have start_date for duration, use it
                            if show_date_range and is_duration and start_date_obj:
                                final_label = f"{format_date(start_date_obj)} - {final_label}"
                            break
                        except ValueError:
                            # Handle invalid dates
                            if day > 28:
                                if month_num == 2:  # February
                                    day = 28 if year % 4 != 0 else 29
                                elif month_num in [4, 6, 9, 11]:  # 30-day months
                                    day = 30
                                else:  # 31-day months
                                    day = 31
                                try:
                                    date_obj = datetime(year, month_num, day).date()
                                    # If we don't already have an end date from the period key
                                    if not end_date_obj:
                                        end_date_obj = date_obj
                                        end_date_str = date_obj.strftime('%Y-%m-%d')

                                    final_label = format_date(date_obj)
                                    # If showing date range and we have start_date for duration, use it
                                    if show_date_range and is_duration and start_date_obj:
                                        final_label = f"{format_date(start_date_obj)} - {final_label}"
                                    break
                                except ValueError:
                                    pass
                    except (ValueError, IndexError):
                        pass

            # If we couldn't extract a date but label has abbreviated month, use the original
            if not final_label:
                for abbr in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']:
                    if abbr in original_label:
                        final_label = original_label
                        break

                # If no month abbreviation was found, use original label
                if not final_label:
                    final_label = original_label

        # Case 2: Handle other special formatted period labels like those with colons
        elif original_label and len(original_label) > 4 and not final_label:
            if ':' in original_label:
                # Labels with prefix like "Annual:" but without "to"
                final_label = original_label
            else:
                # Any other labels we couldn't handle
                final_label = original_label

        # Case 3: Either use existing final_label (possibly from Case 1/2) or extract from period key
        # If final_label is set but we want date range for a duration period, check if we need to add the start date
        if final_label and show_date_range and is_duration and start_date_obj and end_date_obj:
            # Check if the final_label already includes a date range (contains a hyphen)
            if "-" not in final_label:
                # If it's not already a date range, it's likely just the end date
                # Try to detect if the label contains the formatted end date
                end_date_formatted = format_date(end_date_obj)
                if end_date_formatted in final_label:
                    # Replace the end date with the full range
                    full_range = f"{format_date(start_date_obj)} - {end_date_formatted}"
                    final_label = final_label.replace(end_date_formatted, full_range)
                else:
                    # If we can't detect the end date pattern, prepend the start date
                    final_label = f"{format_date(start_date_obj)} - {final_label}"

                # If we have quarter info, ensure it's present for income/cash flow statements
                if q_num and statement_type in ['IncomeStatement', 'CashFlowStatement'] and f"({q_num})" not in final_label:
                    final_label = f"{final_label} ({q_num})"
                # Add YTD indicator for year-to-date periods if not already added
                elif duration_days and statement_type in ['IncomeStatement', 'CashFlowStatement'] and "(YTD)" not in final_label:
                    if 175 <= duration_days <= 190:  # ~6 months
                        final_label = f"{final_label} (YTD)"
                    elif 265 <= duration_days <= 285:  # ~9 months
                        final_label = f"{final_label} (YTD)"

        # If we don't have a final_label yet, process based on period key
        if not final_label:
            if period_key.startswith('instant_'):
                # For instant periods, just use the date
                if end_date_obj:
                    final_label = format_date(end_date_obj)
                else:
                    final_label = original_label
            elif is_duration:
                # For duration periods, format based on show_date_range
                if show_date_range and start_date_obj and end_date_obj:
                    final_label = f"{format_date(start_date_obj)} - {format_date(end_date_obj)}"

                    # Add quarter info if available
                    if q_num and statement_type in ['IncomeStatement', 'CashFlowStatement']:
                        final_label = f"{final_label} ({q_num})"
                    # Add YTD indicator for year-to-date periods
                    elif duration_days and statement_type in ['IncomeStatement', 'CashFlowStatement']:
                        if 175 <= duration_days <= 190:  # ~6 months
                            final_label = f"{final_label} (YTD)"
                        elif 265 <= duration_days <= 285:  # ~9 months
                            final_label = f"{final_label} (YTD)"
                elif end_date_obj:
                    final_label = format_date(end_date_obj)

                    # Add quarter info if available
                    if q_num and statement_type in ['IncomeStatement', 'CashFlowStatement']:
                        final_label = f"{final_label} ({q_num})"
                    # Add YTD indicator for year-to-date periods
                    elif duration_days and statement_type in ['IncomeStatement', 'CashFlowStatement']:
                        if 175 <= duration_days <= 190:  # ~6 months
                            final_label = f"{final_label} (YTD)"
                        elif 265 <= duration_days <= 285:  # ~9 months
                            final_label = f"{final_label} (YTD)"
                else:
                    final_label = original_label
            else:
                # Fall back to original label for anything else
                final_label = original_label

        # Create PeriodData object with all the information
        period_data = PeriodData(
            key=period_key,
            label=final_label,
            end_date=end_date_str,
            start_date=start_date_str if is_duration else None,
            is_duration=is_duration,
            quarter=q_num
        )

        # Add the formatted period to the result
        formatted_periods.append(period_data)

    return formatted_periods, fiscal_period_indicator


def _create_units_note(
    is_monetary_statement: bool, 
    dominant_scale: int, 
    shares_scale: Optional[int]
) -> str:
    """
    Create the units note for the statement title.

    Args:
        is_monetary_statement: Whether the statement contains monetary values
        dominant_scale: The dominant scale for monetary values
        shares_scale: The scale for share values, if present

    Returns:
        str: Formatted units note or empty string
    """
    if not is_monetary_statement:
        return ""

    monetary_scale_text = ""
    if dominant_scale == -3:
        monetary_scale_text = "thousands"
    elif dominant_scale == -6:
        monetary_scale_text = "millions"
    elif dominant_scale == -9:
        monetary_scale_text = "billions"

    shares_scale_text = ""
    if shares_scale is not None:
        if shares_scale == -3:
            shares_scale_text = "thousands"
        elif shares_scale == -6:
            shares_scale_text = "millions"
        elif shares_scale == -9:
            shares_scale_text = "billions"
        elif shares_scale == 0:
            shares_scale_text = "actual amounts"
        else:
            # For other negative scales (like -4, -5, -7, etc.)
            # Use a more generic description based on the scale
            scale_factor = 10 ** (-shares_scale)
            if scale_factor >= 1000:
                shares_scale_text = f"scaled by {scale_factor:,}"

    # Construct appropriate units note
    if monetary_scale_text and shares_scale_text and shares_scale != dominant_scale:
        return f"[italic](In {monetary_scale_text}, except shares in {shares_scale_text} and per share data)[/italic]"
    elif monetary_scale_text:
        return f"[italic](In {monetary_scale_text}, except shares and per share data)[/italic]"
    else:
        return ""


def _format_value_for_display_as_string(
    value: Any,
    item: Dict[str, Any],
    period_key: str,
    is_monetary_statement: bool,
    dominant_scale: int,
    shares_scale: Optional[int],
    comparison_info: Optional[Dict[str, Any]] = None,
    xbrl_instance: Optional[Any] = None
) -> str:
    """
    Format a value for display in a financial statement, returning a string.

    Args:
        value: The value to format
        item: The statement line item containing the value
        period_key: The period key for this value
        is_monetary_statement: Whether this is a monetary statement
        dominant_scale: The dominant scale for monetary values
        shares_scale: The scale for share values, if present
        comparison_info: Optional comparison information for showing trends

    Returns:
        str: Formatted value as a string
    """
    # Fast path for empty values
    if not value or value == "":
        return ""

    # Type check without multiple isinstance calls
    value_type = type(value)
    if value_type not in (int, float, str):
        return ""

    # Extract only needed metadata
    concept = item.get('concept', '')

    # Fast check for common share and EPS concepts
    is_share_value = concept in share_concepts
    is_eps_value = concept in eps_concepts

    # Only perform expensive label operations if needed for monetary determination
    is_monetary = is_monetary_statement
    if is_eps_value or is_share_value:
        is_monetary = False
    elif not is_monetary:
        # Skip label checks entirely if we already know it's not monetary
        pass
    else:
        # Only check label for ratio-related items if we think it might be monetary
        label = item.get('label', '').lower()
        if any(keyword in label for keyword in ('ratio', 'percentage', 'per cent')):
            is_monetary = False

    # Get decimals with a default value to avoid conditional logic later
    fact_decimals = 0
    if period_key:
        decimals_dict = item.get('decimals', {})
        if decimals_dict:
            fact_decimals = decimals_dict.get(period_key, 0) or 0

    # Apply presentation logic for display (Issue #463)
    # Matches SEC HTML filing display - uses preferred_sign from presentation linkbase
    if value_type in (int, float) and period_key:
        # Get statement context
        statement_type = item.get('statement_type')

        # For Income Statement and Cash Flow Statement: Use preferred_sign
        # preferred_sign comes from preferredLabel in presentation linkbase
        # -1 = negate for display (e.g., expenses, dividends, outflows)
        # 1 = show as-is
        # None = no transformation specified
        if statement_type in ('IncomeStatement', 'CashFlowStatement'):
            preferred_sign = item.get('preferred_signs', {}).get(period_key)
            if preferred_sign is not None and preferred_sign != 0:
                value = value * preferred_sign

        # Balance Sheet: No transformation (use as-is)
        # else: pass

    # Format numeric values efficiently
    if value_type in (int, float):
        # Handle EPS values with decimal precision
        if is_eps_value:
            # EPS values should show 2-3 decimal places and not be scaled
            if abs(value) >= 1000:
                # For very large EPS values, use thousands separator
                return f"{value:,.2f}"
            elif abs(value) >= 10:
                # For EPS values >= 10, use 2 decimal places
                return f"{value:.2f}"
            else:
                # For typical EPS values < 10, use up to 3 decimal places but remove trailing zeros
                formatted = f"{value:.3f}".rstrip('0').rstrip('.')
                # Ensure at least 2 decimal places for EPS
                if '.' not in formatted or len(formatted.split('.')[1]) < 2:
                    return f"{value:.2f}"
                return formatted
        # Handle share values with a specialized path
        elif is_share_value:
            if fact_decimals <= -3:
                # Efficiently apply scaling
                scale_factor = 10 ** (-fact_decimals)
                scaled_value = value / scale_factor
                return f"{scaled_value:,.0f}"
            else:
                # For smaller share values, no scaling needed
                return f"{value:,.0f}"
        else:
            # Use cached format_value function for other values
            # Get currency symbol for this period using on-demand resolution
            currency_symbol = None
            if is_monetary and period_key and xbrl_instance:
                from edgar.xbrl.core import get_currency_symbol
                # Get element name from item
                element_name = item.get('name') or item.get('concept', '')
                if element_name:
                    currency_measure = xbrl_instance.get_currency_for_fact(element_name, period_key)
                    if currency_measure:
                        currency_symbol = get_currency_symbol(currency_measure)

            return format_value(value, is_monetary, dominant_scale, fact_decimals, currency_symbol)
    else:
        # String values - only check HTML if it might contain tags
        if '<' in value and '>' in value and _is_html(value):
            return html_to_text(value)
        return value


def _format_value_for_display(
    value: Any,
    item: Dict[str, Any],
    period_key: str,
    is_monetary_statement: bool,
    dominant_scale: int,
    shares_scale: Optional[int],
    comparison_info: Optional[Dict[str, Any]] = None,
    xbrl_instance: Optional[Any] = None
) -> Text:
    """
    Format a value for display in a financial statement, returning a Rich Text object.

    Args:
        value: The value to format
        item: The statement line item containing the value
        period_key: The period key for this value
        is_monetary_statement: Whether this is a monetary statement
        dominant_scale: The dominant scale for monetary values
        shares_scale: The scale for share values, if present
        comparison_info: Optional comparison information for showing trends

    Returns:
        Text: Formatted value as a Rich Text object
    """
    # Get the formatted string value
    formatted_str = _format_value_for_display_as_string(
        value, item, period_key, is_monetary_statement, dominant_scale, shares_scale, comparison_info, xbrl_instance
    )

    # Convert to Rich Text object with right justification
    return Text(formatted_str, justify="right")


def _filter_empty_string_periods(statement_data: List[Dict[str, Any]], periods_to_display: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """
    Filter out periods that contain only empty strings in their values.

    This addresses Issue #408 specifically - periods that have facts but only empty string values.
    This is a lighter filter than the full data availability system, targeting the specific problem.

    Args:
        statement_data: Statement data with items and values
        periods_to_display: List of period keys and labels

    Returns:
        Filtered list of periods that contain meaningful financial data
    """
    if not statement_data or not periods_to_display:
        return periods_to_display

    filtered_periods = []

    for period_key, period_label in periods_to_display:
        has_meaningful_value = False

        # Check all statement items for this period
        for item in statement_data:
            values = item.get('values', {})
            value = values.get(period_key)

            if value is not None:
                # Convert to string and check if it's meaningful
                str_value = str(value).strip()
                # Check for actual content (not just empty strings)
                if str_value and str_value.lower() not in ['', 'nan', 'none']:
                    # Try to parse as numeric - if successful, it's meaningful
                    try:
                        numeric_value = pd.to_numeric(str_value, errors='coerce')
                        if not pd.isna(numeric_value):
                            has_meaningful_value = True
                            break
                    except Exception:
                        # If not numeric but has content, still count as meaningful
                        if len(str_value) > 0:
                            has_meaningful_value = True
                            break

        # Only include periods that have at least some meaningful values
        if has_meaningful_value:
            filtered_periods.append((period_key, period_label))

    return filtered_periods


def render_statement(
    statement_data: List[Dict[str, Any]],
    periods_to_display: List[Tuple[str, str]],
    statement_title: str,
    statement_type: str,
    entity_info: Optional[Dict[str, Any]] = None,
    standard: bool = True,
    show_date_range: bool = False,
    show_comparisons: bool = True,
    xbrl_instance: Optional[Any] = None
) -> RenderedStatement:
    """
    Render a financial statement as a structured intermediate representation.

    Args:
        statement_data: Statement data with items and values
        periods_to_display: List of period keys and labels
        statement_title: Title of the statement
        statement_type: Type of statement (BalanceSheet, IncomeStatement, etc.)
        entity_info: Entity information (optional)
        standard: Whether to use standardized concept labels (default: True)
        show_date_range: Whether to show full date ranges for duration periods (default: False)
        show_comparisons: Whether to show period-to-period comparisons (default: True)

    Returns:
        RenderedStatement: A structured representation of the statement that can be rendered
                           in various formats
    """
    if entity_info is None:
        entity_info = {}

    # Filter out periods with only empty strings (Fix for Issue #408)
    # Apply to all major financial statement types that could have empty periods
    if statement_type in ['CashFlowStatement', 'IncomeStatement', 'BalanceSheet']:
        periods_to_display = _filter_empty_string_periods(statement_data, periods_to_display)

    # Apply standardization if requested
    if standard:
        # Create a concept mapper with default mappings
        mapper = standardization.ConceptMapper(standardization.initialize_default_mappings())

        # Add statement type to context for better mapping
        for item in statement_data:
            item['statement_type'] = statement_type

        # Standardize the statement data
        statement_data = standardization.standardize_statement(statement_data, mapper)

        # Update facts with standardized labels if XBRL instance is available
        entity_xbrl_instance = entity_info.get('xbrl_instance')
        # Use passed xbrl_instance or fall back to entity info
        facts_xbrl_instance = xbrl_instance or entity_xbrl_instance
        if facts_xbrl_instance and hasattr(facts_xbrl_instance, 'facts_view'):
            facts_view = facts_xbrl_instance.facts_view
            facts = facts_view.get_facts()

            # Create a mapping of concept -> standardized label from statement data
            standardization_map = {}
            for item in statement_data:
                if 'concept' in item and 'label' in item and 'original_label' in item:
                    if item.get('is_dimension', False):
                        continue
                    standardization_map[item['concept']] = {
                        'label': item['label'],
                        'original_label': item['original_label']
                    }

            # Update facts with standardized labels
            for fact in facts:
                if 'concept' in fact and fact['concept'] in standardization_map:
                    mapping = standardization_map[fact['concept']]
                    if fact.get('label') == mapping.get('original_label'):
                        # Store original label if not already set
                        if 'original_label' not in fact:
                            fact['original_label'] = fact['label']
                        # Update with standardized label
                        fact['label'] = mapping['label']

            # Clear the cache to ensure it's rebuilt with updated facts
            facts_view.clear_cache()

        # Indicate that standardization is being used in the title
        statement_title = f"{statement_title} (Standardized)"

    # Determine if this is likely a monetary statement
    is_monetary_statement = statement_type in ['BalanceSheet', 'IncomeStatement', 'CashFlowStatement']

    # Format period headers, but keep original tuples for now (we'll use the fully parsed objects later)
    # These are now PeriodData objects but we'll continue with string period_keys for compatibility 
    formatted_period_objects_initial, fiscal_period_indicator = _format_period_labels(
        periods_to_display, entity_info, statement_type, show_date_range
    )
    formatted_periods = [(p.key, p.label) for p in formatted_period_objects_initial]

    # Determine the dominant scale for monetary values in this statement
    dominant_scale = determine_dominant_scale(statement_data, periods_to_display)

    # Determine the scale used for share amounts if present
    shares_scale = None
    # Look for share-related concepts to determine their scaling from the decimals attribute
    for item in statement_data:
        concept = item.get('concept', '')
        if concept in share_concepts:
            # Check decimals attribute to determine proper scaling
            for period_key, _ in periods_to_display:
                decimals = item.get('decimals', {}).get(period_key)
                if isinstance(decimals, int) and decimals <= 0:
                    # Use the decimals attribute to determine the scale
                    # For shares, decimals is typically negative
                    # -3 means thousands, -6 means millions, etc.
                    shares_scale = decimals
                    break
            if shares_scale is not None:
                break

    # Create the units note
    units_note = _create_units_note(is_monetary_statement, dominant_scale, shares_scale)

    # Extract period metadata for each period for better filtering
    period_metadatas = []
    for period_key, period_label in formatted_periods:
        # Try to extract dates from the period key
        if period_key.startswith('instant_'):
            try:
                date_str = period_key.split('_')[1]
                date = parse_date(date_str)
                period_metadatas.append({
                    'key': period_key,
                    'label': period_label,
                    'type': 'instant',
                    'date': date,
                    'end_date': date,  # Use same date as end_date for comparison
                    'has_metadata': True
                })
                continue
            except (ValueError, TypeError, IndexError):
                pass
        elif '_' in period_key and len(period_key.split('_')) >= 3:
            try:
                parts = period_key.split('_')
                start_date_str = parts[1]
                end_date_str = parts[2]
                start_date = parse_date(start_date_str)
                end_date = parse_date(end_date_str)
                duration_days = (end_date - start_date).days
                period_metadatas.append({
                    'key': period_key,
                    'label': period_label,
                    'type': 'duration',
                    'start_date': start_date,
                    'end_date': end_date,
                    'duration_days': duration_days,
                    'has_metadata': True
                })
                continue
            except (ValueError, TypeError, IndexError):
                pass

        # If we get here, we couldn't extract meaningful metadata
        period_metadatas.append({
            'key': period_key,
            'label': period_label,
            'type': 'unknown',
            'has_metadata': False
        })

    # Calculate data density and prepare comparison data
    period_value_counts = {period_key: 0 for period_key, _ in formatted_periods}
    period_item_counts = {period_key: 0 for period_key, _ in formatted_periods}

    # Prepare comparison data if enabled and appropriate for statement type
    comparison_data = {}
    if show_comparisons and statement_type in COMPARISON_CONFIG['enabled_types']:
        # Sort periods by date for proper comparison
        sorted_periods = sorted(
            [m for m in period_metadatas if m['has_metadata']],
            key=lambda x: x['end_date'],
            reverse=True
        )

        # For each item, calculate comparisons between consecutive periods
        for item in statement_data:
            if item.get('is_abstract') or not item.get('has_values'):
                continue

            concept = item.get('concept')
            if not concept or concept in COMPARISON_CONFIG['excluded_concepts']:
                continue

            item_comparisons = {}
            for i in range(len(sorted_periods) - 1):
                current_period = sorted_periods[i]
                prev_period = sorted_periods[i + 1]

                current_value = item['values'].get(current_period['key'])
                prev_value = item['values'].get(prev_period['key'])

                comparison = _calculate_comparison(current_value, prev_value)
                if comparison:
                    item_comparisons[current_period['key']] = comparison

            if item_comparisons:
                comparison_data[item['concept']] = item_comparisons

    # Count non-empty values for each period
    for item in statement_data:
        # Skip abstract items as they typically don't have values
        if item.get('is_abstract', False):
            continue

        # Skip items with brackets in labels (usually axis/dimension items)
        if any(bracket in item['label'] for bracket in ['[Axis]', '[Domain]', '[Member]', '[Line Items]', '[Table]', '[Abstract]']):
            continue

        for period_key, _ in formatted_periods:
            # Count this item for the period
            period_item_counts[period_key] += 1

            # Check if it has a value
            value = item['values'].get(period_key)
            if value not in (None, "", 0):  # Consider 0 as a value for financial statements
                period_value_counts[period_key] += 1

    # Calculate percentage of non-empty values for each period
    for metadata in period_metadatas:
        period_key = metadata['key']
        count = period_item_counts.get(period_key, 0)
        if count > 0:
            data_density = period_value_counts.get(period_key, 0) / count
        else:
            data_density = 0

        metadata['data_density'] = data_density
        metadata['num_values'] = period_value_counts.get(period_key, 0)
        metadata['total_items'] = count

    # Get the PeriodData objects from _format_period_labels
    formatted_period_objects, fiscal_period_indicator = _format_period_labels(
        periods_to_display, entity_info, statement_type, show_date_range
    )

    # Create the RenderedStatement and its header
    header = StatementHeader(
        columns=[period.label for period in formatted_period_objects],
        period_keys=[period.key for period in formatted_period_objects],
        periods=formatted_period_objects,
        metadata={
            'dominant_scale': dominant_scale,
            'shares_scale': shares_scale,
            'is_monetary_statement': is_monetary_statement,
            'period_metadatas': period_metadatas
        }
    )

    # Extract footer information from XBRL and entity info
    footer_metadata = {}

    # Extract company name
    if hasattr(xbrl_instance, 'entity_name') and xbrl_instance.entity_name:
        footer_metadata['company_name'] = xbrl_instance.entity_name
    elif hasattr(xbrl_instance, 'company_name') and xbrl_instance.company_name:
        footer_metadata['company_name'] = xbrl_instance.company_name

    # Extract form type and periods
    if hasattr(xbrl_instance, 'form_type') and xbrl_instance.form_type:
        footer_metadata['form_type'] = xbrl_instance.form_type
    if hasattr(xbrl_instance, 'period_of_report') and xbrl_instance.period_of_report:
        footer_metadata['period_end'] = str(xbrl_instance.period_of_report)
    if entity_info and entity_info.get('fiscal_period'):
        footer_metadata['fiscal_period'] = entity_info.get('fiscal_period')

    rendered_statement = RenderedStatement(
        title=statement_title,
        header=header,
        rows=[],
        metadata={
            'standard': standard,
            'show_date_range': show_date_range,
            'entity_info': entity_info,
            'comparison_data': comparison_data,
            **footer_metadata  # Add footer metadata
        },
        statement_type=statement_type,
        fiscal_period_indicator=fiscal_period_indicator,
        units_note=units_note
    )

    # Issue #450: For Statement of Equity, track concept occurrences to determine beginning vs ending balances
    concept_occurrence_count = {}
    if statement_type == 'StatementOfEquity':
        for item in statement_data:
            concept = item.get('concept', '')
            if concept:
                concept_occurrence_count[concept] = concept_occurrence_count.get(concept, 0) + 1

    concept_current_index = {}

    # Detect if this statement has dimensional display (for Member filtering logic)
    has_dimensional_display = any(item.get('is_dimension', False) for item in statement_data)

    # Process and add rows
    for _index, item in enumerate(statement_data):
        # Skip rows with no values if they're abstract (headers without data)
        # But keep abstract items with children (section headers)
        has_children = len(item.get('children', [])) > 0 or item.get('has_dimension_children', False)
        if not item.get('has_values', False) and item.get('is_abstract') and not has_children:
            continue

        # Skip axis/dimension items (they contain brackets in their labels OR concept ends with these suffixes)
        # Issue #450: Also filter based on concept name to catch dimensional members without bracket labels
        concept = item.get('concept', '')
        if any(bracket in item['label'] for bracket in ['[Axis]', '[Domain]', '[Member]', '[Line Items]', '[Table]', '[Abstract]']):
            continue
        if any(concept.endswith(suffix) for suffix in ['Axis', 'Domain', 'Member', 'LineItems', 'Table']):
            # Issue #450: For Statement of Equity, Members are always structural (column headers), never data
            if statement_type == 'StatementOfEquity':
                continue
            # Issue #416: For dimensional displays, keep Members even without values (they're category headers)
            # For non-dimensional displays, only filter if no values
            if not has_dimensional_display and not item.get('has_values', False):
                continue

        # Track which occurrence of this concept we're on
        if concept:
            concept_current_index[concept] = concept_current_index.get(concept, 0) + 1

        # Remove [Abstract] from label if present
        label = item['label'].replace(' [Abstract]', '')
        level = item['level']

        # Issue #450: For Statement of Equity, add "Beginning balance" / "Ending balance"
        # to labels when concept appears multiple times (e.g., Total Stockholders' Equity)
        if statement_type == 'StatementOfEquity' and concept:
            total_occurrences = concept_occurrence_count.get(concept, 1)
            current_occurrence = concept_current_index.get(concept, 1)

            if total_occurrences > 1:
                if current_occurrence == 1:
                    label = f"{label} - Beginning balance"
                elif current_occurrence == total_occurrences:
                    label = f"{label} - Ending balance"

        # Create the row with metadata
        row = StatementRow(
            label=label,
            level=level,
            cells=[],
            metadata={
                'concept': item.get('concept', ''),
                'has_values': item.get('has_values', False),
                'children': item.get('children', []),
                'dimension_metadata': item.get('dimension_metadata', {}),
                'units': item.get('units', {}),  # Pass through unit_ref for each period
                'period_types': item.get('period_types', {})  # Pass through period_type for each period
            },
            is_abstract=item.get('is_abstract', False),
            is_dimension=item.get('is_dimension', False),
            has_dimension_children=item.get('has_dimension_children', False)
        )

        # Add values for each period
        for period in formatted_period_objects:
            period_key = period.key
            value = item['values'].get(period_key, "")

            # Issue #450: For Statement of Equity with duration periods, match instant facts
            # at the appropriate date based on position in roll-forward structure
            if value == "" and period.end_date and statement_type == 'StatementOfEquity':
                # Determine if this is beginning balance (first occurrence) or ending balance (later occurrences)
                is_first_occurrence = concept_current_index.get(concept, 1) == 1

                if is_first_occurrence and hasattr(period, 'start_date') and period.start_date:
                    # Beginning balance: Try instant at day before start_date
                    from datetime import datetime, timedelta
                    try:
                        start_dt = datetime.strptime(period.start_date, '%Y-%m-%d')
                        beginning_date = (start_dt - timedelta(days=1)).strftime('%Y-%m-%d')
                        instant_key = f"instant_{beginning_date}"
                        value = item['values'].get(instant_key, "")
                    except (ValueError, AttributeError):
                        pass  # Fall through to try end_date

                # If still no value, try instant at end_date (ending balance)
                if value == "":
                    instant_key = f"instant_{period.end_date}"
                    value = item['values'].get(instant_key, "")

            # Get comparison info for this item and period if available
            comparison_info = None
            if show_comparisons and item.get('concept') in comparison_data:
                comparison_info = comparison_data[item['concept']]

            # Create a format function to use when rendering - use a proper closure to avoid variable capture issues
            # Clone item at the time of creating this function to prevent it from changing later
            current_item = dict(item)
            current_period_key = period_key

            def format_func(value, item=current_item, pk=current_period_key):
                return _format_value_for_display_as_string(
                    value, item, pk,
                    is_monetary_statement, dominant_scale, shares_scale,
                    comparison_info, xbrl_instance
                )

            # Create a cell and add it to the row
            cell = StatementCell(
                value=value,  # Store the plain value
                formatter=format_func, # Set the format function to use when rendering
                style={},  # Style will be handled in renderer
                comparison=comparison_info
            )
            row.cells.append(cell)

        # Add the row to the statement
        rendered_statement.rows.append(row)

    return rendered_statement


def generate_rich_representation(xbrl) -> Union[str, 'Panel']:
    """
    Generate a clean, human-focused representation of the XBRL document.

    Args:
        xbrl: XBRL object

    Returns:
        Panel: A formatted panel focused on statement availability and usage
    """
    components = []

    # Header: Clean, crisp information hierarchy
    if xbrl.entity_info:
        entity_name = xbrl.entity_info.get('entity_name', 'Unknown Entity')
        ticker = xbrl.entity_info.get('ticker', '')
        cik = xbrl.entity_info.get('identifier', '')
        doc_type = xbrl.entity_info.get('document_type', '')
        fiscal_year = xbrl.entity_info.get('fiscal_year', '')
        fiscal_period = xbrl.entity_info.get('fiscal_period', '')
        period_end = xbrl.entity_info.get('document_period_end_date', '')

        # Company name with ticker (bold yellow) and CIK on same line
        from rich.text import Text as RichText
        company_line = RichText()
        company_line.append(entity_name, style="bold cyan")
        if ticker:
            company_line.append(" (", style="bold cyan")
            company_line.append(ticker, style="bold yellow")
            company_line.append(")", style="bold cyan")
        if cik:
            # Format CIK with leading zeros dimmed
            company_line.append(" • CIK ", style="dim")
            company_line.append(cik_text(cik))

        components.append(company_line)
        components.append(Text(""))  # Spacing

        # Filing information - crisp, key-value style
        filing_table = RichTable.grid(padding=(0, 2))
        filing_table.add_column(style="bold", justify="right")
        filing_table.add_column(style="default")

        if doc_type:
            filing_table.add_row("Form:", doc_type)

        # Combine fiscal period and end date on one line (they're related!)
        if fiscal_period and fiscal_year:
            period_display = f"Fiscal Year {fiscal_year}" if fiscal_period == 'FY' else f"{fiscal_period} {fiscal_year}"
            if period_end:
                # Format date more readably
                from datetime import datetime
                try:
                    date_obj = datetime.strptime(str(period_end), '%Y-%m-%d')
                    period_display += f" (ended {date_obj.strftime('%b %d, %Y')})"
                except:
                    period_display += f" (ended {period_end})"
            filing_table.add_row("Fiscal Period:", period_display)

        # Data volume
        filing_table.add_row("Data:", f"{len(xbrl._facts):,} facts • {len(xbrl.contexts):,} contexts")

        components.append(filing_table)

    # Period coverage - cleaner, more scannable format
    if xbrl.reporting_periods:
        components.append(Text(""))  # Spacing
        components.append(Text("Available Data Coverage:", style="bold"))

        # Parse periods into annual and quarterly
        annual_periods = []
        quarterly_periods = []
        other_periods = []

        for period in xbrl.reporting_periods[:10]:  # Show more periods
            label = period.get('label', '')
            if not label:
                continue

            # Categorize by label content
            if 'Annual:' in label or 'FY' in label.upper():
                # Extract just the fiscal year or simplified label
                if 'Annual:' in label:
                    # Extract dates and format as FY YYYY
                    try:
                        import re
                        year_match = re.search(r'to .* (\d{4})', label)
                        if year_match:
                            year = year_match.group(1)
                            annual_periods.append(f"FY {year}")
                        else:
                            annual_periods.append(label)
                    except:
                        annual_periods.append(label)
                else:
                    annual_periods.append(label)
            elif 'Quarterly:' in label or any(q in label for q in ['Q1', 'Q2', 'Q3', 'Q4']):
                # Remove "Quarterly:" prefix if present for cleaner display
                clean_label = label.replace('Quarterly:', '').strip()
                quarterly_periods.append(clean_label)
            else:
                other_periods.append(label)

        # Display periods in organized way
        if annual_periods:
            components.append(Text(f"  Annual: {', '.join(annual_periods[:3])}", style="default"))
        if quarterly_periods:
            components.append(Text(f"  Quarterly: {', '.join(quarterly_periods[:3])}", style="default"))

    statements = xbrl.get_all_statements()
    statement_types = {stmt['type'] for stmt in statements if stmt['type']}

    # Common Actions section - expanded and instructive
    components.append(Text(""))  # Spacing
    components.append(Text("Common Actions", style="bold"))
    components.append(Text("─" * 60, style="dim"))

    # Build actions list dynamically
    actions = [
        ("# List all available statements", ""),
        ("xbrl.statements", ""),
        ("", ""),
        ("# Access statements by name or index", ""),
        ("stmt = xbrl.statements['CoverPage']", ""),
        ("stmt = xbrl.statements[6]", ""),
        ("", ""),
        ("# View core financial statements", ""),
    ]

    # Add available core statements dynamically
    core_statement_methods = {
        'IncomeStatement': 'income_statement()',
        'BalanceSheet': 'balance_sheet()',
        'CashFlowStatement': 'cash_flow_statement()',
        'StatementOfEquity': 'statement_of_equity()',
        'ComprehensiveIncome': 'comprehensive_income()'
    }

    for stmt_type, method in core_statement_methods.items():
        if stmt_type in statement_types:
            actions.append((f"stmt = xbrl.statements.{method}", ""))

    # Continue with other actions
    actions.extend([
        ("", ""),
        ("# Get current period only", ""),
        ("current = xbrl.current_period", ""),
        ("stmt = current.income_statement()", ""),
        ("", ""),
        ("# Convert statement to DataFrame", ""),
        ("df = stmt.to_dataframe()", ""),
        ("", ""),
        ("# Query specific facts", ""),
        ("revenue = xbrl.facts.query().by_concept('Revenue').to_dataframe()", ""),
    ])

    for code, comment in actions:
        if not code and not comment:
            # Blank line for spacing
            components.append(Text(""))
        elif code.startswith("#"):
            # Comment line - bold
            components.append(Text(code, style="bold"))
        else:
            # Code line
            action_line = Text()
            action_line.append(f"  {code}", style="cyan")
            if comment:
                action_line.append(f"  {comment}", style="dim")
            components.append(action_line)

    # Add hint about comprehensive docs
    components.append(Text(""))
    components.append(Text("💡 Tip: Use xbrl.docs for comprehensive usage guide", style="dim italic"))

    return Panel(Group(*components), title="XBRL Document", border_style="blue")
