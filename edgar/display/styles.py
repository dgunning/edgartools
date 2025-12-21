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
from rich.style import Style
from rich.text import Text


# =============================================================================
# SEMANTIC COLOR PALETTE
# =============================================================================

PALETTE = {
    # Primary elements - high visibility
    "company_name": "bold green",
    "ticker": "bold gold1",
    "form_type": "bold",

    # Identifiers - distinctive but not overpowering
    "cik": "dodger_blue1",
    "accession": "dodger_blue1",

    # Structure
    "section_header": "bold",
    "subsection": "bold dim",

    # Labels and values
    "label": "grey70",
    "value": "",  # default terminal color
    "value_highlight": "bold",

    # Metadata - subtle
    "metadata": "dim",
    "hint": "dim italic",
    "date": "dim",

    # Borders and separators
    "border": "grey50",
    "separator": "grey50",

    # Status indicators
    "positive": "green",
    "negative": "red",
    "neutral": "dim",
    "warning": "yellow",
    "info": "cyan",

    # Financial specific
    "total_row": "bold",
    "subtotal_row": "bold dim",
    "abstract_item": "bold cyan",

    # Links and references
    "link": "blue underline",
    "reference": "cyan",
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