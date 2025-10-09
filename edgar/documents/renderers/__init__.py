"""
Document renderers for various output formats.
"""

from edgar.documents.renderers.markdown import MarkdownRenderer
from edgar.documents.renderers.text import TextRenderer
from edgar.documents.renderers.fast_table import FastTableRenderer

__all__ = [
    'MarkdownRenderer',
    'TextRenderer',
    'FastTableRenderer'
]