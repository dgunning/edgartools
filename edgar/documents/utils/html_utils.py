"""
HTML utility functions for document parsing.

This module consolidates common HTML processing utilities used across
the parser, preprocessor, and simple parser implementations.
"""

from typing import Optional

import lxml.html


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


def terminate_unclosed_comments(html: str) -> str:
    """
    Close any ``<!--`` that is never followed by ``-->``.

    lxml treats an unterminated comment as running to the end of the input, so a
    single stray ``<!--`` swallows the whole document and parsing yields an empty
    tree. Two shapes show up in 1990s/2000s SEC filings:

        <!--DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2//EN">   (typo for <!DOCTYPE)
        <!-- HTML (c)2001 Some Author, email:someone@example.com  (never closed)

    In both the author meant the construct to end at the end of its line, so an
    unterminated comment is closed at the next newline (or at end of input when
    there is none). Comments that are already terminated are left untouched, so
    normal documents are unaffected.

    Args:
        html: HTML string that may contain an unterminated comment

    Returns:
        HTML string in which every ``<!--`` has a matching ``-->``

    Examples:
        >>> terminate_unclosed_comments('<!-- note\\n<p>hi</p>')
        '<!-- note-->\\n<p>hi</p>'

        >>> terminate_unclosed_comments('<!-- note --><p>hi</p>')  # already closed
        '<!-- note --><p>hi</p>'
    """
    if '<!--' not in html:
        return html

    out = []
    pos = 0
    while True:
        start = html.find('<!--', pos)
        if start == -1:
            out.append(html[pos:])
            break
        end = html.find('-->', start + 4)
        if end != -1:
            # Properly terminated - copy through the closing marker untouched.
            out.append(html[pos:end + 3])
            pos = end + 3
            continue
        # Unterminated: close it at the end of its line, then keep scanning -
        # a document can contain more than one stray comment.
        newline = html.find('\n', start + 4)
        if newline == -1:
            out.append(html[pos:])
            out.append('-->')
            break
        out.append(html[pos:newline])
        out.append('-->')
        pos = newline

    return ''.join(out)


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
