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

from edgar.documents import HTMLParser, ParserConfig
from edgar.display import get_statement_styles, get_style, SYMBOLS
from edgar.display.formatting import cik_text
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


class CellFormatter:
    """Picklable callable that replaces the format_func closure in render_statement().

    Stores all parameters needed by ``_format_value_for_display_as_string``
    as instance attributes so pickle can serialize it.
    """
    __slots__ = ('item', 'period_key', 'is_monetary_statement',
                 'dominant_scale', 'shares_scale', 'comparison_info',
                 'currency_symbol')

    def __init__(self, item, period_key, is_monetary_statement,
                 dominant_scale, shares_scale, comparison_info,
                 currency_symbol):
        self.item = item
        self.period_key = period_key
        self.is_monetary_statement = is_monetary_statement
        self.dominant_scale = dominant_scale
        self.shares_scale = shares_scale
        self.comparison_info = comparison_info
        self.currency_symbol = currency_symbol

    def __call__(self, value):
        return _format_value_for_display_as_string(
            value, self.item, self.period_key,
            self.is_monetary_statement, self.dominant_scale,
            self.shares_scale, self.comparison_info, self.currency_symbol
        )


class PreformattedValue:
    """Picklable callable that returns a pre-computed formatted string.

    Used by ``RenderedStatement.from_dict()`` to replace the unpicklable
    lambda that was previously used.
    """
    __slots__ = ('formatted',)

    def __init__(self, formatted):
        self.formatted = formatted

    def __call__(self, value):
        return self.formatted


@dataclass
class StatementRow:
    """A row in a financial statement."""
    label: str
    level: int  # Indentation/hierarchy level
    cells: List[StatementCell] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional info like concept name, type, etc.
    is_abstract: bool = False
    is_dimension: bool = False
    is_breakdown: bool = False  # True if dimension is breakdown (segment/geo), False if face value
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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dict.

        Pre-applies cell formatters so the resulting dict contains only
        plain Python types (strings, numbers, lists, dicts) and can be
        passed directly to ``json.dumps``.

        ``comparison_data`` is excluded from statement-level metadata
        because each cell already carries its own ``comparison`` field.
        """
        from datetime import date as _date

        from edgar.xbrl.models import ElementCatalog

        def _json_safe(obj):
            """Recursively convert non-JSON-safe types to primitives."""
            if isinstance(obj, dict):
                return {k: _json_safe(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_json_safe(v) for v in obj]
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, _date):
                return obj.isoformat()
            if isinstance(obj, ElementCatalog):
                return {"name": obj.name, "labels": obj.labels}
            return obj

        def _period_to_dict(p: PeriodData) -> Dict[str, Any]:
            return {
                'key': p.key,
                'label': p.label,
                'end_date': p.end_date,
                'start_date': p.start_date,
                'is_duration': p.is_duration,
                'quarter': p.quarter,
            }

        def _cell_to_dict(c: StatementCell) -> Dict[str, Any]:
            return {
                'value': c.value,
                'formatted_value': c.get_formatted_value(),
                'style': c.style,
                'comparison': _json_safe(c.comparison),
            }

        def _row_to_dict(r: StatementRow) -> Dict[str, Any]:
            return {
                'label': r.label,
                'level': r.level,
                'cells': [_cell_to_dict(c) for c in r.cells],
                'metadata': _json_safe(r.metadata),
                'is_abstract': r.is_abstract,
                'is_dimension': r.is_dimension,
                'is_breakdown': r.is_breakdown,
                'has_dimension_children': r.has_dimension_children,
            }

        def _header_to_dict(h: StatementHeader) -> Dict[str, Any]:
            return {
                'columns': h.columns,
                'period_keys': h.period_keys,
                'periods': [_period_to_dict(p) for p in h.periods],
                'metadata': _json_safe(h.metadata),
            }

        # Filter comparison_data out of metadata — it's redundant
        filtered_metadata = _json_safe({
            k: v for k, v in self.metadata.items()
            if k != 'comparison_data'
        })

        return {
            'title': self.title,
            'header': _header_to_dict(self.header),
            'rows': [_row_to_dict(r) for r in self.rows],
            'metadata': filtered_metadata,
            'statement_type': self.statement_type,
            'fiscal_period_indicator': self.fiscal_period_indicator,
            'units_note': self.units_note,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RenderedStatement':
        """Reconstruct a ``RenderedStatement`` from a dict produced by :meth:`to_dict`.

        Cell formatters are replaced with passthrough lambdas that return
        the pre-computed ``formatted_value`` stored during serialization.
        """
        periods = [
            PeriodData(
                key=p['key'],
                label=p['label'],
                end_date=p.get('end_date'),
                start_date=p.get('start_date'),
                is_duration=p.get('is_duration', False),
                quarter=p.get('quarter'),
            )
            for p in data['header'].get('periods', [])
        ]

        header = StatementHeader(
            columns=data['header'].get('columns', []),
            period_keys=data['header'].get('period_keys', []),
            periods=periods,
            metadata=data['header'].get('metadata', {}),
        )

        rows = []
        for rd in data.get('rows', []):
            cells = []
            for cd in rd.get('cells', []):
                fmt_val = cd.get('formatted_value', str(cd.get('value', '')))
                cell = StatementCell(
                    value=cd.get('value'),
                    style=cd.get('style', {}),
                    comparison=cd.get('comparison'),
                    formatter=PreformattedValue(fmt_val),
                )
                cells.append(cell)

            row = StatementRow(
                label=rd.get('label', ''),
                level=rd.get('level', 0),
                cells=cells,
                metadata=rd.get('metadata', {}),
                is_abstract=rd.get('is_abstract', False),
                is_dimension=rd.get('is_dimension', False),
                is_breakdown=rd.get('is_breakdown', False),
                has_dimension_children=rd.get('has_dimension_children', False),
            )
            rows.append(row)

        return cls(
            title=data.get('title', ''),
            header=header,
            rows=rows,
            metadata=data.get('metadata', {}),
            statement_type=data.get('statement_type', ''),
            fiscal_period_indicator=data.get('fiscal_period_indicator'),
            units_note=data.get('units_note'),
        )

    def __rich__(self) -> Panel:
        """Render as a rich panel with design language styling."""
        # Use unified design language styles
        styles = get_statement_styles()

        # Get company name and ticker for header
        company_name = self.metadata.get('company_name', '')
        ticker = self.metadata.get('ticker', '')

        # Clean up title - remove internal terminology and simplify
        clean_title = self.title.replace("(Standardized)", "").strip()

        # Build period range from columns
        columns = self.header.columns
        if len(columns) > 1:
            period_range = f"{columns[-1]} to {columns[0]}"
        elif len(columns) == 1:
            period_range = columns[0]
        else:
            period_range = ""

        # Build units note
        import re
        clean_units = ""
        if self.units_note:
            clean_units = re.sub(r'\[/?[^\]]+\]', '', self.units_note)

        # Build centered header like actual SEC filings:
        # Line 1: Company name (ticker) (bold)
        # Line 2: Statement name (bold)
        # Line 3: Period range (dim)
        header_lines = []
        if company_name:
            company_line = Text(company_name.upper(), style=styles["header"]["company_name"])
            if ticker:
                company_line.append("  ")
                company_line.append(f" {ticker.upper()} ", style=styles["header"]["ticker_badge"])
            header_lines.append(company_line)
        header_lines.append(Text(clean_title.upper(), style=styles["header"]["statement_title"]))
        if period_range:
            header_lines.append(Text(period_range, style="dim"))

        title = Text("\n").join(header_lines)

        # Create the main table
        table = RichTable(
            box=box.SIMPLE,
            show_header=True,
            padding=(0, 1),
        )

        # Add label column
        table.add_column("", justify="left")

        # Add period columns with bold styling
        for column in columns:
            table.add_column(column, justify="right", style="bold")

        # Add rows with semantic styling
        for row in self.rows:
            indent = "  " * row.level

            if row.is_dimension:
                # Dimension items - dim/italic
                label_text = f"{indent}{row.label}"
                styled_label = Text(label_text, style=styles["row"]["item_dim"])
            elif row.is_abstract:
                if row.level == 0:
                    # Top-level abstract - cyan bold (ASSETS, LIABILITIES)
                    label_text = row.label.upper()
                    styled_label = Text(label_text, style=styles["row"]["abstract"])
                elif row.level == 1:
                    # Section header - bold
                    styled_label = Text(row.label, style=styles["header"]["section"])
                else:
                    # Sub-section header
                    sub_indent = "  " * (row.level - 1)
                    styled_label = Text(f"{sub_indent}{row.label}", style=styles["header"]["subsection"])
            else:
                # Regular line items
                if row.has_dimension_children and row.cells:
                    # Items with dimension children get bold styling and colon
                    label_text = f"{indent}{row.label}:"
                    styled_label = Text(label_text, style=styles["row"]["total"])
                elif "Total" in row.label:
                    # Total rows - bold
                    label_text = f"{indent}{row.label}"
                    styled_label = Text(label_text, style=styles["row"]["total"])
                else:
                    # Regular line items - default style
                    label_text = f"{indent}{row.label}"
                    styled_label = Text(label_text, style=styles["row"]["item"])

            # Convert cells to display values with styling
            cell_values = []
            for cell in row.cells:
                if cell.value is None or cell.value == "":
                    cell_values.append(Text("", justify="right"))
                else:
                    cell_value = cell.formatter(cell.value)
                    cell_str = str(cell_value)

                    # Determine style based on value and row type
                    is_total = row.is_abstract or "Total" in row.label
                    is_negative = cell_str.startswith('(') or cell_str.startswith('-') or cell_str.startswith('$(')

                    if is_total and is_negative:
                        style = f"{styles['value']['total']} {styles['value']['negative']}"
                    elif is_total:
                        style = styles["value"]["total"]
                    elif is_negative:
                        style = styles["value"]["negative"]
                    else:
                        style = styles["value"]["default"]

                    cell_values.append(Text(cell_str, style=style, justify="right"))

            table.add_row(styled_label, *cell_values)

        # Build footer with source and units note
        footer_parts = [
            ("Source: ", styles["metadata"]["source"]),
            ("SEC XBRL", styles["metadata"]["source_xbrl"]),
        ]
        if clean_units:
            footer_parts.append(("  ", ""))
            footer_parts.append((SYMBOLS["bullet"], styles["structure"]["separator"]))
            footer_parts.append(("  ", ""))
            footer_parts.append((clean_units, styles["metadata"]["units"]))
        footer = Text.assemble(*footer_parts)

        # Wrap in Panel with design language styling
        # Header is centered like actual SEC filings
        from rich.align import Align
        content = Group(
            Align.center(title),
            table
        )

        return Panel(
            content,
            subtitle=footer,
            subtitle_align="left",
            border_style=styles["structure"]["border"],
            box=box.SIMPLE,
            padding=(0, 1),
            expand=False,
        )

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
                df_row['is_breakdown'] = row.is_breakdown

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
    parser = HTMLParser(ParserConfig())
    document = parser.parse(html)
    return rich_to_text(document, width=80)


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
            # Issue #601: Sort for deterministic ordering across Python processes
            unique_types = sorted(set(period_types))

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
    currency_symbol: Optional[str] = None
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
        currency_symbol: Pre-resolved currency symbol (e.g., "$", "EUR")

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

        # Apply preferred_sign from presentation linkbase for display
        # preferred_sign comes from preferredLabel in presentation linkbase
        # -1 = negate for display (e.g., expenses, dividends, outflows, contra accounts)
        # 1 = show as-is
        # None = no transformation specified
        #
        # Originally only applied to Income Statement and Cash Flow Statement (Issue #463)
        # Extended to Balance Sheet for contra accounts like Treasury Stock (Issue #568)
        # - APD, JPM, XOM use preferred_sign=-1 for Treasury Stock
        # - JPM uses preferred_sign=-1 for Allowance for Loan Losses
        if statement_type in ('IncomeStatement', 'CashFlowStatement', 'BalanceSheet'):
            preferred_sign = item.get('preferred_signs', {}).get(period_key)
            if preferred_sign is not None and preferred_sign != 0:
                value = value * preferred_sign

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
            # currency_symbol is pre-resolved at closure-creation time
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
    currency_symbol: Optional[str] = None
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
        currency_symbol: Pre-resolved currency symbol (e.g., "$", "EUR")

    Returns:
        Text: Formatted value as a Rich Text object
    """
    # Get the formatted string value
    formatted_str = _format_value_for_display_as_string(
        value, item, period_key, is_monetary_statement, dominant_scale, shares_scale, comparison_info, currency_symbol
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
    xbrl_instance: Optional[Any] = None,
    include_dimensions: bool = False,
    role_uri: Optional[str] = None,
    view: Optional['StatementView'] = None
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
        include_dimensions: Whether to include dimensional segment data (default: False).
            When False, only breakdown dimensions (geographic, segment) are filtered out.
            Classification dimensions (PPE type, equity components) are always shown.
        role_uri: Role URI for definition linkbase-based dimension filtering (optional)
        view: StatementView controlling dimensional filtering (STANDARD, DETAILED, SUMMARY).
            SUMMARY filters ALL dimensions, STANDARD filters breakdowns, DETAILED shows all.

    Returns:
        RenderedStatement: A structured representation of the statement that can be rendered
                           in various formats
    """
    from edgar.xbrl.presentation import StatementView
    from edgar.xbrl.statements import is_xbrl_structural_element

    if entity_info is None:
        entity_info = {}

    # Combined filtering: structural elements + dimension filtering in single pass
    # 1. Always filter XBRL structural elements (Axis, Domain, Member, Table, LineItems)
    #    These are metadata, not financial data (e.g., ProductMember, ServiceMember empty rows)
    # 2. Apply StatementView-based dimension filtering:
    #    - SUMMARY: Filter ALL dimensional items (non-dimensional totals only)
    #    - STANDARD: Filter BREAKDOWN dimensions only (keep face-level like Products/Services)
    #    - DETAILED: Show ALL dimensional data
    if view == StatementView.SUMMARY:
        # SUMMARY: Filter structural elements + ALL dimensional items
        statement_data = [
            item for item in statement_data
            if not is_xbrl_structural_element(item) and not item.get('is_dimension')
        ]
    elif not include_dimensions:
        # STANDARD: Filter structural elements + breakdown dimensions only
        # Issue #569: Keep classification dimensions (PPE type, equity components) on face
        # Issue #577/cf9o: Pass xbrl and role_uri for definition linkbase-based filtering
        from edgar.xbrl.dimensions import is_breakdown_dimension
        statement_data = [
            item for item in statement_data
            if not is_xbrl_structural_element(item) and (
                not item.get('is_dimension') or not is_breakdown_dimension(
                    item, statement_type=statement_type, xbrl=xbrl_instance, role_uri=role_uri
                )
            )
        ]
    else:
        # DETAILED: Filter structural elements only, keep all dimensional data
        statement_data = [item for item in statement_data if not is_xbrl_structural_element(item)]

    # Filter out periods with only empty strings (Fix for Issue #408)
    # Apply to all major financial statement types that could have empty periods
    if statement_type in ['CashFlowStatement', 'IncomeStatement', 'BalanceSheet']:
        periods_to_display = _filter_empty_string_periods(statement_data, periods_to_display)

    # Apply standardization if requested
    if standard:
        # Use XBRL instance's standardization cache if available (disable statement caching
        # since statement_data varies by view/period parameters)
        if xbrl_instance is not None and hasattr(xbrl_instance, 'standardization'):
            statement_data = xbrl_instance.standardization.standardize_statement_data(
                statement_data, statement_type, use_cache=False
            )
        else:
            # Fall back to module-level singleton mapper
            mapper = standardization.get_default_mapper()
            for item in statement_data:
                item['statement_type'] = statement_type
            statement_data = standardization.standardize_statement(statement_data, mapper)

        # Add standard_concept metadata to facts if XBRL instance is available
        entity_xbrl_instance = entity_info.get('xbrl_instance') if entity_info else None
        facts_xbrl_instance = xbrl_instance or entity_xbrl_instance
        if facts_xbrl_instance and hasattr(facts_xbrl_instance, 'facts_view'):
            facts_view = facts_xbrl_instance.facts_view
            facts = facts_view.get_facts()

            # Create a mapping of concept -> standard_concept from statement data
            standard_concept_map = {}
            for item in statement_data:
                if 'concept' in item and 'standard_concept' in item:
                    if item.get('is_dimension', False):
                        continue
                    standard_concept_map[item['concept']] = item['standard_concept']

            # Add standard_concept metadata to facts (don't change labels)
            for fact in facts:
                if 'concept' in fact and fact['concept'] in standard_concept_map:
                    fact['standard_concept'] = standard_concept_map[fact['concept']]

            # Clear the cache to ensure it's rebuilt with updated facts
            facts_view.clear_cache()

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

    # Extract ticker
    if hasattr(xbrl_instance, 'entity_info') and xbrl_instance.entity_info:
        ticker = xbrl_instance.entity_info.get('ticker', '')
        if ticker:
            footer_metadata['ticker'] = ticker

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

        # Determine if this is a breakdown dimension
        from edgar.xbrl.dimensions import is_breakdown_dimension
        is_dim = item.get('is_dimension', False)
        is_breakdown = is_breakdown_dimension(
            item, statement_type=statement_type,
            xbrl=xbrl_instance, role_uri=role_uri
        ) if is_dim else False

        # Create the row with metadata
        row = StatementRow(
            label=label,
            level=level,
            cells=[],
            metadata={
                'concept': item.get('concept', ''),
                'standard_concept': item.get('standard_concept'),  # Standard concept identifier for analysis
                'has_values': item.get('has_values', False),
                'children': item.get('children', []),
                'dimension_metadata': item.get('dimension_metadata', {}),
                'units': item.get('units', {}),  # Pass through unit_ref for each period
                'period_types': item.get('period_types', {})  # Pass through period_type for each period
            },
            is_abstract=item.get('is_abstract', False),
            is_dimension=is_dim,
            is_breakdown=is_breakdown,
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

            # Pre-resolve currency to avoid capturing xbrl_instance in the closure
            cell_currency_symbol = None
            if is_monetary_statement and period_key and xbrl_instance:
                from edgar.xbrl.core import get_currency_symbol
                element_name = current_item.get('name') or current_item.get('concept', '')
                if element_name:
                    currency_measure = xbrl_instance.get_currency_for_fact(element_name, period_key)
                    if currency_measure:
                        cell_currency_symbol = get_currency_symbol(currency_measure)

            format_func = CellFormatter(
                current_item, current_period_key,
                is_monetary_statement, dominant_scale, shares_scale,
                comparison_info, cell_currency_symbol
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

    Follows the EdgarTools design language (docs/internal/design-language.md):
    - Card-based layout with box.ROUNDED, expand=False
    - Semantic colors from edgar.display.styles
    - No emojis - uses unicode symbols from SYMBOLS
    - Data-first information hierarchy

    Args:
        xbrl: XBRL object

    Returns:
        Panel: A formatted panel showing XBRL document summary
    """
    from edgar.xbrl.statements import Statements

    components = []

    # Extract entity info
    entity_name = ''
    ticker = ''
    cik = ''
    doc_type = ''
    fiscal_year = ''
    fiscal_period = ''
    period_end = ''

    if xbrl.entity_info:
        entity_name = xbrl.entity_info.get('entity_name', 'Unknown Entity')
        ticker = xbrl.entity_info.get('ticker', '')
        cik = xbrl.entity_info.get('identifier', '')
        doc_type = xbrl.entity_info.get('document_type', '')
        fiscal_year = xbrl.entity_info.get('fiscal_year', '')
        fiscal_period = xbrl.entity_info.get('fiscal_period', '')
        period_end = xbrl.entity_info.get('document_period_end_date', '')

    # === Title ===
    # Composed like Filing: Form {type} {company} ({ticker}) • CIK {cik}
    title_parts = []
    if doc_type:
        title_parts.append((f"{doc_type} ", get_style("form_type")))
    title_parts.append((entity_name, get_style("company_name")))
    if ticker:
        title_parts.append((" ", ""))
        title_parts.append((f"({ticker})", get_style("ticker")))
    if cik:
        title_parts.append((f" {SYMBOLS['bullet']} CIK ", get_style("metadata")))
        title_parts.append(cik_text(cik))
    title = Text.assemble(*title_parts) if title_parts else Text("XBRL Document")

    # === Subtitle ===
    subtitle = Text.assemble(
        ("XBRL Data", get_style("metadata")),
        f" {SYMBOLS['bullet']} ",
        ("xbrl.statements", get_style("hint")),
        (" to browse", get_style("metadata")),
    )

    # === Section 1: Filing metadata ===
    details_table = RichTable(box=None, show_header=False, padding=(0, 2), expand=False)
    details_table.add_column("Label", style=get_style("label"), width=16)
    details_table.add_column("Value", style=get_style("value_highlight"))

    # Fiscal period + end date
    if fiscal_period and fiscal_year:
        period_display = f"Fiscal Year {fiscal_year}" if fiscal_period == 'FY' else f"{fiscal_period} {fiscal_year}"
        if period_end:
            try:
                date_obj = datetime.strptime(str(period_end), '%Y-%m-%d')
                period_display += f" (ended {date_obj.strftime('%b %d, %Y')})"
            except Exception:
                period_display += f" (ended {period_end})"
        details_table.add_row("Fiscal Period", period_display)

    # Data volume
    details_table.add_row("Data", f"{len(xbrl._facts):,} facts {SYMBOLS['bullet']} {len(xbrl.contexts):,} contexts")

    components.append(details_table)

    # === Section 2: Periods ===
    if xbrl.reporting_periods:
        from edgar.xbrl.period_selector import _filter_by_document_date

        document_end_date = xbrl.period_of_report
        all_periods_count = len(xbrl.reporting_periods)
        filtered_periods = _filter_by_document_date(xbrl.reporting_periods, document_end_date)
        filtered_count = len(filtered_periods)

        # 10-K filings contain quarterly periods that are SEC disclosure metadata
        # (e.g. Rule 10b5-1 trading arrangements), not quarterly financials.
        # 10-Q filings contain annual periods that are note metadata
        # (e.g. debt maturity dates), not annual financials.
        # Showing these would mislead users into thinking that data is available.
        is_annual_filing = doc_type.upper().startswith('10-K') if doc_type else False
        is_quarterly_filing = doc_type.upper().startswith('10-Q') if doc_type else False

        # Use the structured period_type field (from classify_duration) instead of
        # parsing label text — more robust across different filers.
        annual_periods = []
        quarterly_periods = []

        for period in filtered_periods:
            if period.get('type') != 'duration':
                continue
            period_type = period.get('period_type', '')
            end_year = period.get('end_date', '')[:4]

            if period_type == 'Annual' and not is_quarterly_filing:
                annual_periods.append(f"FY {end_year}")
            elif period_type == 'Quarterly' and not is_annual_filing:
                # Format as "Q{n} {year}" from the end date month
                end_date = period.get('end_date', '')
                if len(end_date) >= 7:
                    month = int(end_date[5:7])
                    quarter = (month - 1) // 3 + 1
                    quarterly_periods.append(f"Q{quarter} {end_year}")
                else:
                    quarterly_periods.append(period.get('label', '').replace('Quarterly:', '').strip())

        if annual_periods or quarterly_periods:
            components.append(Text(""))
            components.append(Text("Periods", style=get_style("section_header")))

            period_table = RichTable(box=None, show_header=False, padding=(0, 2), expand=False)
            period_table.add_column("Label", style=get_style("label"), width=16)
            period_table.add_column("Value")

            if annual_periods:
                period_table.add_row("Annual", ", ".join(annual_periods[:3]))
            if quarterly_periods:
                period_table.add_row("Quarterly", ", ".join(quarterly_periods[:4]))

            components.append(period_table)

            if document_end_date and filtered_count < all_periods_count:
                excluded_count = all_periods_count - filtered_count
                components.append(Text(
                    f"  ({excluded_count} future period{'s' if excluded_count > 1 else ''} after {document_end_date} excluded)",
                    style=get_style("hint")
                ))

    # === Section 3: Statements summary ===
    all_statements = xbrl.get_all_statements()
    if all_statements:
        from edgar.xbrl.statements import _extract_topic_summary

        # Group by category
        statements_by_category = {
            'statement': [], 'note': [], 'disclosure': [],
            'document': [], 'other': []
        }
        for stmt in all_statements:
            cat = Statements.classify_statement(stmt)
            statements_by_category[cat].append(stmt)

        total = len(all_statements)

        components.append(Text(""))
        components.append(Text(f"Statements ({total})", style=get_style("section_header")))

        # Category display order and labels
        category_display = [
            ('statement', 'Statements'),
            ('note', 'Notes'),
            ('disclosure', 'Disclosures'),
            ('document', 'Document'),
            ('other', 'Other'),
        ]

        # For core statements, list all available types
        core_names = {
            'IncomeStatement': 'Income',
            'BalanceSheet': 'Balance Sheet',
            'CashFlowStatement': 'Cash Flow',
            'StatementOfEquity': 'Equity',
            'ComprehensiveIncome': 'Compr. Income',
        }

        stmt_table = RichTable(box=None, show_header=False, padding=(0, 2), expand=False)
        stmt_table.add_column("Label", style=get_style("label"), min_width=14, no_wrap=True)
        stmt_table.add_column("Count", style=get_style("value_highlight"), width=5, justify="right")
        stmt_table.add_column("Detail", style=get_style("metadata"), no_wrap=True)

        for cat_key, cat_label in category_display:
            cat_stmts = statements_by_category[cat_key]
            count = len(cat_stmts)
            if count == 0:
                continue

            if cat_key == 'statement':
                # List all unique core statement types found
                found = []
                for stmt in cat_stmts:
                    stmt_type = stmt.get('type', '')
                    if stmt_type in core_names and core_names[stmt_type] not in found:
                        found.append(core_names[stmt_type])
                detail = ", ".join(found) if found else ""
            else:
                # Use topic extraction for notes/disclosures/other
                detail = _extract_topic_summary(cat_stmts, max_shown=4)

            stmt_table.add_row(cat_label, str(count), detail)

        components.append(stmt_table)

    return Panel(
        Group(*components),
        title=title,
        subtitle=subtitle,
        subtitle_align="right",
        border_style=get_style("border"),
        box=box.ROUNDED,
        padding=(0, 1),
        expand=False,
    )
