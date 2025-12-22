"""
Terminal-friendly color schemes for financial statement display.
Provides better contrast and readability in various terminal environments.
"""

from typing import Dict

# Default scheme - the current implementation
DEFAULT_SCHEME = {
    "abstract_item": "bold cyan",
    "total_item": "bold",
    "regular_item": "",
    "low_confidence_item": "dim",
    "positive_value": "green",
    "negative_value": "red",
    "total_value_prefix": "bold yellow",
    "separator": "dim",
    "company_name": "bold green",
    "statement_type": "bold blue",
    "panel_border": "blue",
    "empty_value": "dim",
}

# High contrast scheme - better for terminals with poor dim text support
HIGH_CONTRAST_SCHEME = {
    "abstract_item": "bold bright_cyan",
    "total_item": "bold bright_white",
    "regular_item": "white",
    "low_confidence_item": "bright_black",  # Usually renders as gray
    "positive_value": "bright_green",
    "negative_value": "bright_red",
    "total_value_prefix": "bold bright_yellow",
    "separator": "bright_black",
    "company_name": "bold bright_green",
    "statement_type": "bold bright_blue",
    "panel_border": "bright_blue",
    "empty_value": "bright_black",
}

# Professional scheme - emphasizes important items without dim text
PROFESSIONAL_SCHEME = {
    "abstract_item": "bold blue",
    "total_item": "bold bright_white",
    "regular_item": "",
    "low_confidence_item": "italic",  # Use italic instead of dim
    "positive_value": "green",
    "negative_value": "red", 
    "total_value_prefix": "bold",
    "separator": "blue",
    "company_name": "bold bright_white",
    "statement_type": "bold blue",
    "panel_border": "white",
    "empty_value": "bright_black",
}

# Minimal scheme - focuses on structure over color
MINIMAL_SCHEME = {
    "abstract_item": "bold",
    "total_item": "bold bright_white",
    "regular_item": "",
    "low_confidence_item": "italic",
    "positive_value": "",
    "negative_value": "red",  # Keep red for negative values
    "total_value_prefix": "bold",
    "separator": "white",
    "company_name": "bold",
    "statement_type": "bold",
    "panel_border": "white",
    "empty_value": "bright_black",
}

# Color-blind friendly scheme
ACCESSIBLE_SCHEME = {
    "abstract_item": "bold blue",
    "total_item": "bold bright_white underline",  # Use underline for emphasis
    "regular_item": "",
    "low_confidence_item": "italic",
    "positive_value": "blue",  # Avoid green/red
    "negative_value": "magenta",  # Avoid green/red
    "total_value_prefix": "bold underline",
    "separator": "white",
    "company_name": "bold bright_white",
    "statement_type": "bold blue",
    "panel_border": "white",
    "empty_value": "bright_black",
}

# SEC filing style - mimics actual printed filings
FILING_SCHEME = {
    "abstract_item": "bold",           # Major sections (ASSETS, LIABILITIES) - just bold
    "total_item": "bold",              # Subtotals - bold only
    "regular_item": "",                # Regular items - no styling
    "low_confidence_item": "dim",      # Low confidence items - dimmed
    "positive_value": "",              # Positive values - no color (like printed filings)
    "negative_value": "",              # Negative values - no color (parentheses show negative)
    "total_value_prefix": "bold",      # Total values - bold only
    "separator": "dim",                # Table separators - dimmed
    "company_name": "bold",            # Company name - just bold
    "statement_type": "bold",          # Statement title - just bold
    "panel_border": "white",           # Panel borders - white
    "empty_value": "dim",              # Empty values - dimmed
}

# Available schemes
SCHEMES: Dict[str, Dict[str, str]] = {
    "default": DEFAULT_SCHEME,
    "high_contrast": HIGH_CONTRAST_SCHEME,
    "professional": PROFESSIONAL_SCHEME,
    "minimal": MINIMAL_SCHEME,
    "accessible": ACCESSIBLE_SCHEME,
    "filing": FILING_SCHEME,
}

def get_color_scheme(scheme_name: str = "professional") -> Dict[str, str]:
    """
    Get a color scheme by name.

    Args:
        scheme_name: Name of the scheme (default, high_contrast, professional, minimal, accessible, filing)

    Returns:
        Dictionary of style mappings
    """
    return SCHEMES.get(scheme_name, PROFESSIONAL_SCHEME)

# Environment variable support
import os


def get_current_scheme() -> Dict[str, str]:
    """
    Get the current color scheme based on environment variable or default.

    Environment variable: EDGAR_FINANCIALS_COLOR_SCHEME
    Values: default, high_contrast, professional, minimal, accessible, filing
    """
    scheme_name = os.environ.get("EDGAR_FINANCIALS_COLOR_SCHEME", "professional")
    return get_color_scheme(scheme_name)
