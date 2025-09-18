"""File processing utilities for SEC documents."""

from .page_breaks import PageBreakDetector, detect_page_breaks, mark_page_breaks

__all__ = [
    'detect_page_breaks',
    'mark_page_breaks', 
    'PageBreakDetector'
]
