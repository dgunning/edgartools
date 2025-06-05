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
from edgar.richtools import repr_rich, rich_to_text
from edgar.xbrl import standardization
from edgar.xbrl.core import determine_dominant_scale, format_date, format_value, parse_date

# Default style configuration
DEFAULT_STYLES = {
    'header': {
        'top_level': {'style': 'bold', 'case': 'upper'},
        'section': {'style': 'bold', 'case': 'title'},
        'subsection': {'style': 'bold', 'case': 'title'}
    },
    'dimension': {
        'single': {'style': 'italic', 'case': 'title'},
        'multi': {'style': 'italic dim', 'case': 'title'}
    },
    'value': {
        'positive': {'style': 'none', 'color': 'default'},
        'negative': {'style': 'none', 'color': 'red'},
        'zero': {'style': 'dim', 'color': 'default'},
        'empty': {'style': 'dim', 'color': 'grey'}
    },
    'comparison': {
        'increase': {'symbol': '▲', 'color': 'green'},
        'decrease': {'symbol': '▼', 'color': 'red'},
        'unchanged': {'symbol': '•', 'color': 'grey'}
    }
}

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
        """Render as a rich table"""
        # Create the table
        table = RichTable(title=self.title, box=box.SIMPLE)

        # Add the fiscal period indicator and units note as a subtitle if available
        if self.header.columns:
            subtitles = []

            # Add fiscal period indicator if available
            if self.fiscal_period_indicator:
                subtitles.append(f"[bold]{self.fiscal_period_indicator}[/bold]")

            # Add units note
            if self.units_note:
                subtitles.append(self.units_note)

            # Apply subtitles to table title
            if subtitles:
                table.title = f"{self.title}\n{' '.join(subtitles)}"

        # Add columns with right-alignment for numeric columns
        table.add_column("", justify="left")
        for column in self.header.columns:
            table.add_column(column)

        # Add rows
        for row in self.rows:
            # Format the label based on level and properties
            if row.is_dimension:
                # Format dimension items with the appropriate style
                indent = "  " * row.level
                styled_label = f"{indent}[italic]{row.label}[/italic]"
            elif row.is_abstract:
                if row.level == 0:
                    # Top-level header - full caps, bold
                    styled_label = f"[bold]{row.label.upper()}[/bold]"
                elif row.level == 1:
                    # Section header - bold
                    styled_label = f"[bold]{row.label}[/bold]"
                else:
                    # Sub-section header - indented, bold
                    indent = "  " * (row.level - 1)  # Less aggressive indentation
                    styled_label = f"[bold]{indent}{row.label}[/bold]"
            else:
                # Regular line items - indented based on level
                indent = "  " * row.level
                # If this item has dimension children, make it bold and add a colon
                if row.has_dimension_children and row.cells:
                    styled_label = f"[bold]{indent}{row.label}:[/bold]"
                else:
                    styled_label = f"{indent}{row.label}"

            # Convert cells to their display representation as Rich Text objects
            cell_values = []
            for cell in row.cells:
                # Convert string values to Rich Text objects for console display
                if cell.value is None or cell.value == "":
                    cell_values.append("")
                else:
                    # Create a Rich Text object with right justification
                    cell_value = cell.formatter(cell.value)
                    cell_values.append(Text(str(cell_value), justify="right"))

            table.add_row(styled_label, *cell_values)

        return table

    def __repr__(self):
        return repr_rich(self.__rich__())

    def to_dataframe(self) -> Any:
        """Convert to a pandas DataFrame"""
        try:

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
    'us-gaap_CommonStockSharesIssued'
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
    
    # First, determine the fiscal period type (annual, quarterly, etc.) based on the first period
    if periods_to_display:
        first_period_key = periods_to_display[0][0]
        
        # For instant periods (Balance Sheet)
        if first_period_key.startswith('instant_'):
            date_str = first_period_key.split('_')[1]
            try:
                date = parse_date(date_str)
                
                # Determine if this is fiscal year end or interim period
                if ('fiscal_year_end_month' in entity_info and 
                    'fiscal_year_end_day' in entity_info and
                    'fiscal_period' in entity_info):
                    
                    fiscal_month = entity_info.get('fiscal_year_end_month')
                    fiscal_day = entity_info.get('fiscal_year_end_day')
                    fiscal_period = entity_info.get('fiscal_period')
                    
                    if fiscal_period == 'FY' or (
                            date.month == fiscal_month and 
                            abs(date.day - fiscal_day) <= 7):
                        fiscal_period_indicator = "Fiscal Year Ended"
                    else:
                        # For quarterly periods
                        if fiscal_period in ['Q1', 'Q2', 'Q3']:
                            month_names = {
                                'Q1': 'First Quarter Ended',
                                'Q2': 'Second Quarter Ended',
                                'Q3': 'Third Quarter Ended'
                            }
                            # Handle potential None value for fiscal_period
                            if fiscal_period is not None:
                                fiscal_period_indicator = month_names.get(fiscal_period, "Quarter Ended")
                            else:
                                fiscal_period_indicator = "Quarter Ended"
                        else:
                            fiscal_period_indicator = "As of"
                else:
                    fiscal_period_indicator = "As of"
            except (ValueError, TypeError):
                fiscal_period_indicator = "As of"
        
        # For duration periods (Income Statement, Cash Flow)
        else:
            start_date_str, end_date_str = first_period_key.split('_')[1], first_period_key.split('_')[2]
            try:
                start_date = parse_date(start_date_str)
                end_date = parse_date(end_date_str)
                duration_days = (end_date - start_date).days
                
                # Determine period type based on duration
                if 85 <= duration_days <= 95:
                    fiscal_period_indicator = "Three Months Ended"
                elif 175 <= duration_days <= 190:
                    fiscal_period_indicator = "Six Months Ended"
                elif 265 <= duration_days <= 285:
                    fiscal_period_indicator = "Nine Months Ended"
                elif 355 <= duration_days <= 375:
                    fiscal_period_indicator = "Year Ended"
                else:
                    # Use fiscal period information if available
                    if 'fiscal_period' in entity_info:
                        fiscal_period = entity_info.get('fiscal_period')
                        if fiscal_period == 'FY':
                            fiscal_period_indicator = "Year Ended"
                        elif fiscal_period == 'Q1':
                            fiscal_period_indicator = "Three Months Ended"
                        elif fiscal_period == 'Q2':
                            fiscal_period_indicator = "Six Months Ended"
                        elif fiscal_period == 'Q3':
                            fiscal_period_indicator = "Nine Months Ended"
                        else:
                            fiscal_period_indicator = "Period Ended"
                    else:
                        fiscal_period_indicator = "Period Ended"
            except (ValueError, TypeError, IndexError):
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
                elif end_date_obj:
                    final_label = format_date(end_date_obj)
                    
                    # Add quarter info if available
                    if q_num and statement_type in ['IncomeStatement', 'CashFlowStatement']:
                        final_label = f"{final_label} ({q_num})"
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
        return f"[italic](In {monetary_scale_text}, except shares in {shares_scale_text})[/italic]"
    elif monetary_scale_text:
        return f"[italic](In {monetary_scale_text}, except per share data)[/italic]"
    else:
        return ""


def _format_value_for_display_as_string(
    value: Any, 
    item: Dict[str, Any], 
    period_key: str, 
    is_monetary_statement: bool,
    dominant_scale: int,
    shares_scale: Optional[int],
    comparison_info: Optional[Dict[str, Any]] = None
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
    
    # Fast check for common share concepts (avoid dict lookup when possible)
    is_share_value = concept in share_concepts
    
    # Only perform expensive label operations if needed for monetary determination
    is_monetary = is_monetary_statement
    if concept in ('us-gaap_EarningsPerShareBasic', 'us-gaap_EarningsPerShareDiluted'):
        is_monetary = False
    elif is_share_value:
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
    
    # Format numeric values efficiently
    if value_type in (int, float):
        # Handle share values with a specialized path
        if is_share_value:
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
            return format_value(value, is_monetary, dominant_scale, fact_decimals)
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
    comparison_info: Optional[Dict[str, Any]] = None
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
        value, item, period_key, is_monetary_statement, dominant_scale, shares_scale, comparison_info
    )
    
    # Convert to Rich Text object with right justification
    return Text(formatted_str, justify="right")


def render_statement(
    statement_data: List[Dict[str, Any]],
    periods_to_display: List[Tuple[str, str]],
    statement_title: str,
    statement_type: str,
    entity_info: Optional[Dict[str, Any]] = None,
    standard: bool = True,
    show_date_range: bool = False,
    show_comparisons: bool = True
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
        xbrl_instance = entity_info.get('xbrl_instance')
        if xbrl_instance and hasattr(xbrl_instance, 'facts_view'):
            facts_view = xbrl_instance.facts_view
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
    
    # Filter the PeriodData objects by data density
    filtered_periods = []
    for period_obj in formatted_period_objects:
        # Find matching metadata
        metadata = next((m for m in period_metadatas if m['key'] == period_obj.key), None)
        if metadata and metadata.get('data_density', 0) > 0.3:
            filtered_periods.append(period_obj)
    
    # Create the RenderedStatement and its header
    header = StatementHeader(
        columns=[period.label for period in filtered_periods],
        period_keys=[period.key for period in filtered_periods],
        periods=filtered_periods,
        metadata={
            'dominant_scale': dominant_scale,
            'shares_scale': shares_scale,
            'is_monetary_statement': is_monetary_statement,
            'period_metadatas': period_metadatas
        }
    )
    
    rendered_statement = RenderedStatement(
        title=statement_title,
        header=header,
        rows=[],
        metadata={
            'standard': standard,
            'show_date_range': show_date_range,
            'entity_info': entity_info,
            'comparison_data': comparison_data
        },
        statement_type=statement_type,
        fiscal_period_indicator=fiscal_period_indicator,
        units_note=units_note
    )
    
    # Process and add rows
    for index, item in enumerate(statement_data):
        # Skip rows with no values if they're abstract (headers without data)
        # But keep abstract items with children (section headers)
        has_children = len(item.get('children', [])) > 0 or item.get('has_dimension_children', False)
        if not item.get('has_values', False) and item.get('is_abstract') and not has_children:
            continue
            
        # Skip non-abstract items without values (missing data)
        if not item.get('has_values', False) and not item.get('is_abstract') and not item.get('children'):
            continue
            
        # Skip axis/dimension items (they contain brackets in their labels)
        if any(bracket in item['label'] for bracket in ['[Axis]', '[Domain]', '[Member]', '[Line Items]', '[Table]', '[Abstract]']):
            continue
            
        # Remove [Abstract] from label if present
        label = item['label'].replace(' [Abstract]', '')
        level = item['level']
        
        # Create the row with metadata
        row = StatementRow(
            label=label,
            level=level,
            cells=[],
            metadata={
                'concept': item.get('concept', ''),
                'has_values': item.get('has_values', False),
                'children': item.get('children', []),
                'dimension_metadata': item.get('dimension_metadata', {})
            },
            is_abstract=item.get('is_abstract', False),
            is_dimension=item.get('is_dimension', False),
            has_dimension_children=item.get('has_dimension_children', False)
        )
        
        # Add values for each period
        for period in filtered_periods:
            period_key = period.key
            value = item['values'].get(period_key, "")
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
                    comparison_info
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
    Generate a rich representation of the XBRL document.
    
    Args:
        xbrl: XBRL object
        
    Returns:
        Panel: A formatted panel with XBRL document information
    """
    components = []
    
    # Entity information
    if xbrl.entity_info:
        if RichTable is None or box is None:
            return "Rich rendering not available - install 'rich' package"
        entity_table = RichTable(title="Entity Information", box=box.SIMPLE)
        entity_table.add_column("Property")
        entity_table.add_column("Value")
        
        for key, value in xbrl.entity_info.items():
            entity_table.add_row(key, str(value))
        
        components.append(entity_table)
    
    # Statements summary
    statements = xbrl.get_all_statements()
    if statements:
        if RichTable is None or box is None:
            return "Rich rendering not available - install 'rich' package"
        statement_table = RichTable(title="Financial Statements", box=box.SIMPLE)
        statement_table.add_column("Type")
        statement_table.add_column("Definition")
        statement_table.add_column("Elements")
        
        for stmt in statements:
            statement_table.add_row(
                stmt['type'] or "Other",
                stmt['definition'],
                str(stmt['element_count'])
            )
        
        components.append(statement_table)
    
    # Facts summary
    if RichTable is None or box is None:
        return "Rich rendering not available - install 'rich' package"
    fact_table = RichTable(title="Facts Summary", box=box.SIMPLE)
    fact_table.add_column("Category")
    fact_table.add_column("Count")
    
    fact_table.add_row("Total Facts", str(len(xbrl._facts)))
    fact_table.add_row("Contexts", str(len(xbrl.contexts)))
    fact_table.add_row("Units", str(len(xbrl.units)))
    fact_table.add_row("Elements", str(len(xbrl.element_catalog)))
    
    components.append(fact_table)
    
    # Reporting periods
    if xbrl.reporting_periods:
        period_table = RichTable(title="Reporting Periods", box=box.SIMPLE)
        period_table.add_column("Type")
        period_table.add_column("Period")
        
        for period in xbrl.reporting_periods:
            if period['type'] == 'instant':
                period_table.add_row("Instant", period['date'])
            else:
                period_table.add_row("Duration", f"{period['start_date']} to {period['end_date']}")
        
        components.append(period_table)
    
    return Panel(Group(*components), title="XBRL Document", border_style="green")
