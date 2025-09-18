"""
EdgarTools HTML Parser v2.0

A high-performance, semantically-aware HTML parser for SEC filings.
"""

from edgar.documents.config import ParserConfig
from edgar.documents.document import Document
from edgar.documents.exceptions import ParsingError
from edgar.documents.parser import HTMLParser
from edgar.documents.renderers import MarkdownRenderer, TextRenderer
from edgar.documents.search import DocumentSearch, SearchMode, SearchResult
from edgar.documents.types import NodeType, SemanticType, TableType

__version__ = "2.0.0"
__all__ = [
    'HTMLParser', 
    'Document', 
    'ParserConfig', 
    'ParsingError',
    'NodeType',
    'SemanticType', 
    'TableType',
    'DocumentSearch',
    'SearchResult',
    'SearchMode',
    'MarkdownRenderer',
    'TextRenderer',
    'parse_html'
]


def parse_html(html: str, config: ParserConfig = None) -> Document:
    """
    Convenience function for parsing HTML.

    Args:
        html: HTML content to parse
        config: Optional parser configuration

    Returns:
        Parsed Document object

    Example:
        >>> document = parse_html(html_content)
        >>> print(document.text()[:100])
    """
    parser = HTMLParser(config or ParserConfig())
    return parser.parse(html)
