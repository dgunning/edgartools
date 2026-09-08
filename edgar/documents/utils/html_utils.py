"""
HTML utility functions for document parsing.

This module consolidates common HTML processing utilities used across
the parser, preprocessor, and simple parser implementations.
"""

from typing import List, Optional

import lxml.html
from lxml.etree import ParserError, strip_elements


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
    remove_blank_text: bool = False,
    remove_comments: bool = True,
    recover: bool = True,
    encoding: Optional[str] = 'utf-8',
    huge_tree: bool = True
) -> lxml.html.HTMLParser:
    """
    Create a configured lxml HTMLParser.

    This factory function creates an lxml HTMLParser with consistent
    configuration settings used across the document parsing system.

    Args:
        remove_blank_text: Remove blank text nodes between tags.
            Default False: a whitespace-only text node between two tags is a word
            boundary, and libxml2 deletes it rather than collapsing it. Turn it on
            only for trees whose text is never extracted.
        remove_comments: Remove HTML comments from parsed tree.
            Default True since comments are rarely needed.
        recover: Enable error recovery mode to handle malformed HTML.
            Default True since SEC filings often have HTML issues.
        encoding: Character encoding for the parser.
            Default 'utf-8'. Set to None to disable encoding handling.
        huge_tree: Lift libxml2's hard-coded parser limits.
            Default True, and it should stay that way. Without it libxml2
            stops at a nesting depth of 256 and SILENTLY DISCARDS everything
            below -- no exception, no entry in the error log, just a shorter
            document. 2000s-era filings nest layout tables that deep: one 2003
            S-1 in the corpus reaches depth 284 and loses about 10% of its
            text, all of it the tail. BeautifulSoup never had this behaviour
            with either treebuilder -- html.parser has no depth limit, and
            bs4's own lxml treebuilder passes huge_tree=True -- so leaving it
            off makes every reader moved from bs4 to lxml quietly lossy.
            Measured over 282 fixtures, turning it on changes exactly one of
            them, and only by recovering text that was being dropped; parse
            time is unchanged.

    Returns:
        Configured lxml.html.HTMLParser instance

    Examples:
        >>> # Standard parser (keeps whitespace, drops comments, recovers from errors)
        >>> parser = create_lxml_parser()

        >>> # Parser that preserves all content (for XBRL)
        >>> parser = create_lxml_parser(remove_comments=False)

        >>> # Parser without encoding (auto-detect)
        >>> parser = create_lxml_parser(encoding=None)

    Note:
        The recover=True setting is critical for SEC documents which
        often contain non-standard HTML structures.

        huge_tree=True is equally critical and less obvious, because the
        failure is silent. See the argument description above.
    """
    kwargs = {
        'remove_blank_text': remove_blank_text,
        'remove_comments': remove_comments,
        'recover': recover,
        'huge_tree': huge_tree,
    }

    # Only add encoding if specified
    if encoding is not None:
        kwargs['encoding'] = encoding

    return lxml.html.HTMLParser(**kwargs)


# ---------------------------------------------------------------------------
# Text extraction -- bs4's three get_text behaviours, on lxml.
#
# The bs4 -> lxml migration (edgartools-07lk.11) grew one private copy of these
# per ported file, because each PR was kept small and self-contained. They are
# folded here now that the semantics are settled (edgartools-07lk.11.12).
#
# The distinction the copies exist to preserve: `text_content()` is only ONE of
# bs4's three behaviours, and reaching for it where bs4 used another is the
# word-gluing bug family this codebase keeps rediscovering -- "Note 5Inventories"
# for a label typeset across two cells.
#
#   bs4 call                          here
#   get_text()                        text_content(el)
#   get_text(strip=True)              text_stripped(el)
#   get_text(' ', strip=True)         text_joined(el, ' ')
#
# NONE of these excludes <script>, <style> or <template>, and bs4 excluded all
# three from ALL of its variants -- it classified their contents as Script,
# Stylesheet and TemplateString rather than as text. An element-level helper
# cannot strip them without mutating the caller's tree, so the caller strips
# once at parse time; `html_to_text` below, which owns its tree, does it itself.
# ---------------------------------------------------------------------------


def text_content(element) -> str:
    """All descendant text, concatenated with nothing between -- bs4 ``get_text()``.

    Strips nothing, which is the one variant lxml has natively. Use it only where
    the source is prose whose whitespace is already correct; for anything laid out
    in table cells, adjacent strings need a separator or their words run together.
    """
    return element.text_content()


def text_stripped(element) -> str:
    """Each string stripped, joined with NOTHING -- bs4 ``get_text(strip=True)``.

    The empty separator is the point rather than an oversight: bs4 strips every
    string and concatenates, so ``<span> 1,234 </span><span> </span>`` gives
    ``"1,234"`` where :func:`text_content` keeps the padding and gives
    ``" 1,234  "``. Comments contribute no text, in either library.
    """
    return ''.join(chunk.strip() for chunk in element.itertext())


def text_joined(element, separator: str = ' ') -> str:
    """Each string stripped, empties dropped, the rest joined by ``separator``.

    bs4's ``get_text(separator, strip=True)``, which lxml has no equivalent for.
    This is the variant to reach for on anything laid out in cells: it is what
    keeps a label typeset as ``<td>Note 5</td><td>Inventories</td>`` from reading
    as ``"Note 5Inventories"``.
    """
    return separator.join(chunk.strip() for chunk in element.itertext() if chunk.strip())


def text_skipping_tables(element, separator: str = ' ') -> str:
    """:func:`text_joined` over everything outside a nested ``<table>``.

    The narrative lead-in of a cell that also carries a table. bs4 did this by
    copying the element, calling ``decompose()`` on each nested table and taking
    ``get_text(' ', strip=True)`` of the rest.

    Two traps, which is why this walks rather than removes. Removing an element in
    lxml deletes its tail; splicing that tail onto the previous sibling to save it
    MERGES two of bs4's separate strings into one text node, and a single node is
    separated from nothing, so ``"Lead-in.<table/>Trailing."`` comes back as
    ``"Lead-in.Trailing."``. Both mistakes produce the same symptom -- run-together
    words -- which is the edgartools-vfwp/hxtd/2h2s family again, reached here from
    the opposite direction, while fixing tail loss.

    So walk, and keep each of bs4's strings its own chunk. Document order is an
    element's own text, then each child's text and tail in turn, which is exactly
    the order bs4 yielded them in. A non-``str`` tag is a comment or PI, whose body
    bs4's ``get_text`` skipped -- but whose tail is ordinary text either way.
    """
    chunks: List[str] = []

    def walk(el):
        if el.text and el.text.strip():
            chunks.append(el.text.strip())
        for child in el.iterchildren():
            tag = child.tag
            if isinstance(tag, str) and tag.lower() != 'table':
                walk(child)
            if child.tail and child.tail.strip():
                chunks.append(child.tail.strip())

    walk(element)
    return separator.join(chunks)


def html_to_text(html, *, separator: Optional[str] = None,
                 remove_comments: bool = True) -> str:
    """Plain text of a whole HTML document, as ``BeautifulSoup(html).get_text()`` gave it.

    The parse-and-extract wrapper. ``separator`` selects the variant, spelled the
    way bs4 spelled it: ``None`` for ``get_text()`` (:func:`text_content`), a string
    for ``get_text(separator, strip=True)`` (:func:`text_joined`).

    Owning its own tree, this is the one place that can strip ``<script>``,
    ``<style>`` and ``<template>`` itself, and it must -- an exhibit carrying an
    inline stylesheet, which filer-agent HTML routinely does, would otherwise open
    with a block of CSS source, and a stylesheet that happens to mention a form
    name gets read as the cover page. ``with_tail=False`` keeps the ordinary text
    that FOLLOWS the closing tag, which bs4 kept.

    ``remove_comments=False`` where a caller needs bs4's node boundaries preserved:
    dropping a comment at parse time merges the text either side of it into a
    single node, and a single node is stripped once rather than twice, so
    ``A <!--c--> B`` comes back as ``"A   B"`` where bs4 gave ``"A B"``.

    An unparseable document returns ``""`` -- bs4's ``get_text()`` on an empty soup.
    """
    if isinstance(html, str):
        html = html.encode('utf-8', errors='replace')
    try:
        root = lxml.html.fromstring(
            html, parser=create_lxml_parser(remove_comments=remove_comments))
    except ParserError:
        return ''
    strip_elements(root, 'script', 'style', 'template', with_tail=False)
    return text_content(root) if separator is None else text_joined(root, separator)
