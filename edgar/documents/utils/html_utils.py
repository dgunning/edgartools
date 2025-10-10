"""
HTML utility functions for document parsing.

This module consolidates common HTML processing utilities used across
the parser, preprocessor, and simple parser implementations.
"""

import lxml.html
from typing import Optional


def remove_xml_declaration(html: str) -> str:
    """
    Remove XML declaration from HTML if present.

    SEC HTML documents sometimes include XML declarations like:
        <?xml version="1.0" encoding="UTF-8"?>

    These can interfere with HTML parsing and are safely removed since
    the encoding is handled separately by the parser.

    Args:
        html: HTML string that may contain XML declaration

    Returns:
        HTML string with XML declaration removed (if present)

    Examples:
        >>> html = '<?xml version="1.0"?><!DOCTYPE html><html>...'
        >>> remove_xml_declaration(html)
        '<!DOCTYPE html><html>...'

        >>> html = '<!DOCTYPE html><html>...'  # No XML declaration
        >>> remove_xml_declaration(html)
        '<!DOCTYPE html><html>...'
    """
    html_stripped = html.strip()
    if html_stripped.startswith('<?xml'):
        xml_end = html.find('?>') + 2
        return html[xml_end:]
    return html


def create_lxml_parser(
    remove_blank_text: bool = True,
    remove_comments: bool = True,
    recover: bool = True,
    encoding: Optional[str] = 'utf-8'
) -> lxml.html.HTMLParser:
    """
    Create a configured lxml HTMLParser.

    This factory function creates an lxml HTMLParser with consistent
    configuration settings used across the document parsing system.

    Args:
        remove_blank_text: Remove blank text nodes between tags.
            Default True for cleaner tree structure.
        remove_comments: Remove HTML comments from parsed tree.
            Default True since comments are rarely needed.
        recover: Enable error recovery mode to handle malformed HTML.
            Default True since SEC filings often have HTML issues.
        encoding: Character encoding for the parser.
            Default 'utf-8'. Set to None to disable encoding handling.

    Returns:
        Configured lxml.html.HTMLParser instance

    Examples:
        >>> # Standard parser (removes whitespace and comments, recovers from errors)
        >>> parser = create_lxml_parser()

        >>> # Parser that preserves all content (for XBRL)
        >>> parser = create_lxml_parser(
        ...     remove_blank_text=False,
        ...     remove_comments=False
        ... )

        >>> # Parser without encoding (auto-detect)
        >>> parser = create_lxml_parser(encoding=None)

    Note:
        The recover=True setting is critical for SEC documents which
        often contain non-standard HTML structures.
    """
    kwargs = {
        'remove_blank_text': remove_blank_text,
        'remove_comments': remove_comments,
        'recover': recover,
    }

    # Only add encoding if specified
    if encoding is not None:
        kwargs['encoding'] = encoding

    return lxml.html.HTMLParser(**kwargs)
