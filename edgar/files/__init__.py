"""File processing utilities for SEC documents."""

from .page_breaks import (
    detect_page_breaks,
    mark_page_breaks,
    PageBreakDetector
)

__all__ = [
    'detect_page_breaks',
    'mark_page_breaks', 
    'PageBreakDetector'
]
