"""
EdgarTools Display Styles

Semantic color palette and styling utilities for consistent rich output.
Based on the design language defined in edgartools-wkka.

Design Principles:
- Professional appearance with balanced colors
- Card-based layout with single outer borders
- Weight-based typography hierarchy (bold/dim, no font size changes)
- Semantic colors with consistent meaning across all displays
- No emojis - use unicode symbols (arrows, bullets, checkmarks)
"""

from typing import Optional
from rich.console import Console
from rich.padding import Padding
from rich.style import Style
from rich.text import Text

# Shared console instance for styled output
_console = Console()


# =============================================================================
# SEMANTIC COLOR PALETTE
# =============================================================================

PALETTE = {
    # =========================================================================
    # PRIMARY ELEMENTS - high visibility
    # =========================================================================
    "company_name": "bold green",
    "ticker": "bold gold1",
    "form_type": "bold",

    # =========================================================================
    # IDENTIFIERS - distinctive but not overpowering
    # =========================================================================
    "cik": "dodger_blue1",
    "accession": "dodger_blue1",

    # =========================================================================
    # STRUCTURE
    # =========================================================================
    "section_header": "bold",
    "subsection": "bold dim",

    # =========================================================================
    # LABELS AND VALUES
    # =========================================================================
    "label": "grey70",
    "value": "",  # default terminal color
    "value_highlight": "bold",

    # =========================================================================
    # METADATA - subtle
    # =========================================================================
    "metadata": "dim",
    "hint": "dim italic",
    "date": "dim",
    "source": "dim italic",  # For "Source:" prefix
    "source_entity_facts": "cyan",  # EntityFacts API source
    "source_xbrl": "gold1",  # XBRL filing source
    "units": "dim",  # For "Amounts in millions USD"
    "period_range": "bold",  # For "Q3 2022 to Q3 2025" - high visibility

    # =========================================================================
    # BORDERS AND SEPARATORS
    # =========================================================================
    "border": "grey50",
    "separator": "grey50",

    # =========================================================================
    # STATUS INDICATORS
    # =========================================================================
    "positive": "green",
    "negative": "red",
    "neutral": "dim",
    "warning": "yellow",
    "info": "cyan",
    "foreign": "magenta",  # Foreign company indicator
    "canadian": "red",  # Canadian company indicator

    # =========================================================================
    # FINANCIAL STATEMENTS - Row Types
    # =========================================================================
    # Abstract items - section headers like "ASSETS", "Revenue"
    "stmt_abstract": "bold cyan",
    "stmt_abstract_top": "bold cyan",  # Top-level (ASSETS, LIABILITIES)
    "stmt_abstract_section": "bold",   # Section level (Current Assets)

    # Total rows - summary lines
    "stmt_total": "bold",
    "stmt_subtotal": "bold dim",

    # Regular line items
    "stmt_item": "",  # Default style
    "stmt_item_dim": "dim",  # Dimension items (italic/dim)
    "stmt_item_low_confidence": "dim italic",

    # =========================================================================
    # FINANCIAL STATEMENTS - Values
    # =========================================================================
    "stmt_value": "",  # Default value
    "stmt_value_positive": "",  # No special color - most values are positive
    "stmt_value_negative": "red",  # Highlight negatives (losses, deficits)
    "stmt_value_total": "bold",
    "stmt_value_empty": "dim",

    # =========================================================================
    # FINANCIAL STATEMENTS - Comparison Indicators
    # =========================================================================
    "stmt_increase": "green",
    "stmt_decrease": "red",
    "stmt_unchanged": "dim",

    # =========================================================================
    # LEGACY ALIASES (for backward compatibility during migration)
    # =========================================================================
    "total_row": "bold",
    "subtotal_row": "bold dim",
    "abstract_item": "bold cyan",

    # =========================================================================
    # LINKS AND REFERENCES
    # =========================================================================
    "link": "blue underline",
    "reference": "cyan",

    # =========================================================================
    # BADGES - Background fills for visual emphasis
    # =========================================================================
    # Form type badges
    "badge_10k": "bold white on dodger_blue1",
    "badge_10q": "bold white on green",
    "badge_8k": "bold white on dark_orange",
    "badge_proxy": "bold white on magenta",
    "badge_default": "bold white on grey50",

    # Source badges - distinguish data origin
    "badge_source_xbrl": "bold white on gold3",
    "badge_source_entity_facts": "bold white on cyan",
    "badge_ticker": "bold black on green",

    # Status badges
    "badge_error": "bold white on red",
    "badge_warning": "bold black on yellow",
    "badge_success": "bold white on green",
    "badge_info": "bold white on blue",
}


# =============================================================================
# UNICODE SYMBOLS (replacing emojis)
# =============================================================================

SYMBOLS = {
    # Arrows
    "arrow_right": "\u2192",      # ->
    "arrow_left": "\u2190",       # <-
    "arrow_up": "\u2191",         # ^
    "arrow_down": "\u2193",       # v

    # Bullets and markers
    "bullet": "\u2022",           # *
    "diamond": "\u25C6",          # <>
    "triangle_right": "\u25B6",   # |>
    "triangle_down": "\u25BC",    # v

    # Status
    "check": "\u2713",            # checkmark
    "cross": "\u2717",            # x
    "warning": "\u26A0",          # /!\
    "info": "\u2139",             # (i)

    # Separators
    "pipe": "\u2502",             # |
    "dash": "\u2014",             # --
    "ellipsis": "\u2026",         # ...

    # Enclosures
    "lbracket": "\u3010",         # [
    "rbracket": "\u3011",         # ]

    # Financial comparisons
    "increase": "\u25B2",         # ▲
    "decrease": "\u25BC",         # ▼
    "unchanged": "\u2022",        # •

    # Confidence markers
    "low_confidence": "\u25E6",   # ◦ (hollow bullet)
}


# =============================================================================
# STYLE UTILITIES
# =============================================================================

def get_style(name: str) -> str:
    """Get a style string from the palette by semantic name."""
    return PALETTE.get(name, "")


def styled(text: str, style_name: str) -> Text:
    """Create a Rich Text object with the specified semantic style."""
    style = get_style(style_name)
    return Text(text, style=style)


def label_value(label: str, value: str,
                label_style: str = "label",
                value_style: str = "value") -> Text:
    """Create a label: value pair with consistent styling."""
    return Text.assemble(
        (label, get_style(label_style)),
        (" ", ""),
        (value, get_style(value_style))
    )


def company_title(name: str, ticker: Optional[str] = None) -> Text:
    """Create a styled company title with optional ticker."""
    parts = [(name, get_style("company_name"))]
    if ticker:
        parts.append((" ", ""))
        parts.append((ticker, get_style("ticker")))
    return Text.assemble(*parts)


def identifier(value: str, id_type: str = "cik") -> Text:
    """Create a styled identifier (CIK, accession number, etc.)."""
    style_name = id_type if id_type in PALETTE else "cik"
    return Text(value, style=get_style(style_name))


# =============================================================================
# FINANCIAL STATEMENT STYLES
# =============================================================================

def get_statement_styles() -> dict:
    """
    Get a structured style dictionary for financial statements.

    This provides a migration path from the old style systems
    (terminal_styles.py and get_xbrl_styles()) to the unified palette.

    Returns:
        Dictionary with organized style groups for statement rendering.
    """
    return {
        # Header styles
        "header": {
            "company_name": PALETTE["company_name"],
            "statement_title": PALETTE["section_header"],
            "top_level": PALETTE["stmt_abstract_top"],
            "section": PALETTE["stmt_abstract_section"],
            "subsection": PALETTE["subsection"],
            "ticker_badge": PALETTE["badge_ticker"],
        },
        # Row styles
        "row": {
            "abstract": PALETTE["stmt_abstract"],
            "total": PALETTE["stmt_total"],
            "subtotal": PALETTE["stmt_subtotal"],
            "item": PALETTE["stmt_item"],
            "item_dim": PALETTE["stmt_item_dim"],
            "low_confidence": PALETTE["stmt_item_low_confidence"],
        },
        # Value styles
        "value": {
            "default": PALETTE["stmt_value"],
            "positive": PALETTE["stmt_value_positive"],
            "negative": PALETTE["stmt_value_negative"],
            "total": PALETTE["stmt_value_total"],
            "empty": PALETTE["stmt_value_empty"],
        },
        # Structure styles
        "structure": {
            "border": PALETTE["border"],
            "separator": PALETTE["separator"],
        },
        # Metadata styles
        "metadata": {
            "source": PALETTE["source"],
            "source_entity_facts": PALETTE["source_entity_facts"],
            "source_xbrl": PALETTE["source_xbrl"],
            "units": PALETTE["units"],
            "date": PALETTE["date"],
            "hint": PALETTE["hint"],
            "period_range": PALETTE["period_range"],
        },
        # Comparison indicators
        "comparison": {
            "increase": {"symbol": SYMBOLS["increase"], "style": PALETTE["stmt_increase"]},
            "decrease": {"symbol": SYMBOLS["decrease"], "style": PALETTE["stmt_decrease"]},
            "unchanged": {"symbol": SYMBOLS["unchanged"], "style": PALETTE["stmt_unchanged"]},
        },
    }


def source_text(source: str) -> Text:
    """
    Create a styled source attribution text.

    Args:
        source: Source name (e.g., "EntityFacts", "SEC XBRL")

    Returns:
        Rich Text object like "Source: EntityFacts" in source style.
    """
    return Text(f"Source: {source}", style=get_style("source"))


# =============================================================================
# STATUS MESSAGE UTILITIES
# =============================================================================

def print_warning(message: str, details: str = None):
    """
    Print a styled warning message with optional details.

    Args:
        message: The main warning message (displayed with yellow background)
        details: Optional additional context (displayed in dim style below)

    Example:
        >>> print_warning("Invalid quarter specified", "Quarter must be 1-4")
    """
    warning_text = f"  {SYMBOLS['warning']} {message}  "
    status = Padding(warning_text, (0, 0), style=PALETTE["badge_warning"], expand=False)
    _console.print(status)
    if details:
        _console.print(f"[dim]{details}[/dim]")


def print_error(message: str, details: str = None):
    """
    Print a styled error message with optional details.

    Args:
        message: The main error message (displayed with red background)
        details: Optional additional context (displayed in dim style below)
    """
    error_text = f"  {SYMBOLS['cross']} {message}  "
    status = Padding(error_text, (0, 0), style=PALETTE["badge_error"], expand=False)
    _console.print(status)
    if details:
        _console.print(f"[dim]{details}[/dim]")


def print_info(message: str, details: str = None):
    """
    Print a styled info message with optional details.

    Args:
        message: The main info message (displayed with blue background)
        details: Optional additional context (displayed in dim style below)
    """
    info_text = f"  {SYMBOLS['info']} {message}  "
    status = Padding(info_text, (0, 0), style=PALETTE["badge_info"], expand=False)
    _console.print(status)
    if details:
        _console.print(f"[dim]{details}[/dim]")


def print_success(message: str, details: str = None):
    """
    Print a styled success message with optional details.

    Args:
        message: The main success message (displayed with green background)
        details: Optional additional context (displayed in dim style below)
    """
    success_text = f"  {SYMBOLS['check']} {message}  "
    status = Padding(success_text, (0, 0), style=PALETTE["badge_success"], expand=False)
    _console.print(status)
    if details:
        _console.print(f"[dim]{details}[/dim]")