"""
lxml.html helpers for parsing SEC filing index pages.

Part of the bs4 -> lxml migration (#931, #1102). These helpers adapt lxml's
API to the find/text idioms the attachment index parser was written against,
while preserving bs4-compatible behaviour on class attributes and whitespace.

The house rules from edgar/documents/parser.py apply:

- parse with recover=True so broken SEC HTML still yields a tree
- never remove blank text: a whitespace-only node between two tags is a
  word boundary ("Yes ☒", "three reportable")
- strip any XML declaration first: lxml raises ValueError on a str that
  starts with one (gotcha 4 in the #931 porting guide)
- empty or unparseable input raises ParserError where bs4 returned an empty
  soup; callers here translate that to IndexError, matching what the old
  bs4-based code produced on those inputs
"""

from typing import List, Optional

import lxml.html
from lxml.etree import ParserError

from edgar.documents.utils.html_utils import create_lxml_parser, remove_xml_declaration

__all__ = [
    'parse_index_html',
    'find_all',
    'find_one',
    'element_text',
    'class_tokens',
]


def parse_index_html(html: str) -> lxml.html.HtmlElement:
    """
    Parse an SEC filing index page into an lxml tree.

    Uses the house parser settings (recover=True, remove_blank_text=False)
    so that malformed filings still parse and whitespace-only text nodes
    survive as word boundaries.
    """
    if html is None:
        raise IndexError("No HTML content to parse")

    cleaned = remove_xml_declaration(html)

    # Whitespace-only input parsed fine under bs4 (empty soup) and then blew
    # up downstream with IndexError when nothing could be found. Raise the
    # same error directly rather than failing later with a ParserError.
    if not cleaned or not cleaned.strip():
        raise IndexError("No HTML content to parse")

    try:
        tree = lxml.html.fromstring(
            cleaned,
            parser=create_lxml_parser(remove_comments=False),
        )
    except ParserError as e:
        # bs4 returned an empty soup for unparseable documents and the
        # callers surfaced that as IndexError on the first lookup.
        raise IndexError(f"Could not parse index page HTML: {e}") from e

    return tree


def _css_escape(value: str) -> str:
    """Escape a string for use inside an XPath string literal."""
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat('" + "', \"'\", '".join(parts) + "')"


def _match_predicate(tag: Optional[str], attrs: dict) -> str:
    """Build an XPath predicate matching tag/attribute constraints."""
    clauses = []
    if attrs.get('id') is not None:
        clauses.append(f"@id={_css_escape(attrs['id'])}")
    classes = attrs.get('class_')
    if classes is not None:
        wanted = classes.split()
        for cls in wanted:
            # token test, not substring: class="infoHead" must not match "info"
            clauses.append(
                f"contains(concat(' ', normalize-space(@class), ' '), "
                f"' {_css_escape(cls)[1:-1]} ')"
                .replace("' '", "' '")  # keep quoting readable
            )
    return ' and '.join(clauses)


def _xpath_for(tag: Optional[str], attrs: dict) -> str:
    tag_test = tag if tag else '*'
    predicate = _match_predicate(tag, attrs)
    return f".//{tag_test}[{predicate}]" if predicate else f".//{tag_test}"


def find_all(element, tag: Optional[str] = None, recursive: bool = True, **attrs) -> List:
    """
    Find descendant elements, matching class tokens exactly.

    Mirrors soup.find_all(tag, class_=..., id=..., recursive=...). Class
    matching is on whole tokens: class="infoHead" does NOT match class_='info'.
    """
    xpath = _xpath_for(tag, attrs)
    if not recursive:
        xpath = xpath.replace('.//', './', 1)
    matches = element.xpath(xpath)
    return list(matches)


def find_one(element, tag: Optional[str] = None, **attrs):
    """
    Find the first matching descendant element, or None.

    Mirrors soup.find(tag, class_=..., id=...).
    """
    matches = find_all(element, tag, **attrs)
    return matches[0] if matches else None


def element_text(element) -> str:
    """
    All text under the element, comment nodes excluded.

    Equivalent to soup .text: bs4's .text walks the tree and joins each
    node's text with the separator between its children preserved as-is,
    which for HTML tables means the whitespace between cells' inline
    children is kept. text_content() concatenates raw, so rebuild that
    join: this element's text, then for every non-comment child its own
    full subtree text, then the child's tail.
    """
    parts = []
    if element.text:
        parts.append(element.text)
    for child in element.iterchildren():
        if not isinstance(child.tag, str):
            # Comment / PI nodes: skip the payload but keep the tail, which
            # is real document text sitting after the comment.
            if child.tail:
                parts.append(child.tail)
            continue
        # Recurse rather than text_content(): text_content() would swallow
        # comment payloads (their text counts) and drop nothing else, but
        # recursing lets us skip comments exactly like bs4 does.
        parts.append(element_text(child))
        if child.tail:
            parts.append(child.tail)
    return ''.join(parts)


def class_tokens(element) -> List[str]:
    """
    The element's class attribute as a list of tokens.

    bs4 hands back a list; lxml hands back the raw string. Splitting on
    whitespace restores list semantics so membership tests stay exact
    ('info' must not match inside 'infoHead').
    """
    value = element.get('class')
    if not value:
        return []
    return value.split()


# Aliases used by attachments.py to make call sites read like the old bs4 code
_find_all = find_all
_find_one = find_one
_text = element_text
_class_tokens = class_tokens
