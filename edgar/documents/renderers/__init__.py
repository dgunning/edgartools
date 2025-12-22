"""
Document renderers for various output formats.
"""

from edgar.documents.renderers.fast_table import FastTableRenderer
from edgar.documents.renderers.markdown import MarkdownRenderer
from edgar.documents.renderers.text import TextRenderer

__all__ = [
    'MarkdownRenderer',
    'TextRenderer',
    'FastTableRenderer'
]
