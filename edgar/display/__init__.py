"""
EdgarTools Display Package

A cohesive design language for rich terminal output.
"""

from edgar.display.styles import (
    PALETTE,
    SYMBOLS,
    get_style,
    styled,
    label_value,
    company_title,
    identifier,
    get_statement_styles,
    source_text,
)

__all__ = [
    "PALETTE",
    "SYMBOLS",
    "get_style",
    "styled",
    "label_value",
    "company_title",
    "identifier",
    "get_statement_styles",
    "source_text",
]
