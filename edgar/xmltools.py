"""XML element helpers shared by twelve SEC form parsers.

Dual-backend for the duration of the bs4 to lxml migration (edgartools-07lk.11.2).
Every helper here accepts *either* a BeautifulSoup ``Tag`` or an ``lxml.etree``
element and behaves identically on both, so the twelve dependents can switch their
parse entry point one at a time (edgartools-07lk.11.3) instead of in one commit. The
bs4 half of each adapter below is deleted in the 6.0 window once the last dependent
has moved, along with the dependency itself (edgartools-07lk.11 phase 6).

bs4's behavior is the contract, because ~350 call sites were written against it.
Reproducing it on lxml takes more than renaming methods — the two libraries differ
on four axes, and every difference fails *silently*, returning None or "" where a
value used to be:

  truthiness  ``bool(Tag)`` is True even for a childless ``<c/>``; ``bool(Element)``
              is False even for ``<b>text</b>``. Guards here test ``is not None``.
  find depth  ``Tag.find()`` searches all descendants; ``Element.find()`` searches
              direct children. ``_find`` uses ``.//`` to match bs4's reach.
  .text       ``Tag.text`` concatenates the whole subtree; ``Element.text`` stops at
              the first child element. ``_text`` walks the subtree.
  whitespace  bs4's XML treebuilder collapses a whitespace-ONLY text node to a
              single character. ``_collapse`` reproduces that exactly; it is the one
              place the port is more than a translation.

tests/test_xmltools_semantics.py runs the whole contract against both backends and
asserts they agree, so a regression in either half is a failure, not a surprise.
"""
from decimal import Decimal
from typing import Iterator, List, Optional, Tuple, Union

from bs4 import BeautifulSoup, Tag
from lxml import etree

__all__ = [
    'child_text',
    'child_value',
    'child_texts',
    'find_element',
    'get_footnote_ids',
    'optional_decimal',
    'value_or_footnote',
    'extract_child_text',
    'extract_child_value',
    'value_with_footnotes',
]

# Either backend's element type. `BeautifulSoup` is a `Tag` subclass, so a whole
# parsed document is a valid node too.
XmlNode = Union[Tag, etree._Element]


# ---------------------------------------------------------------------------
# Backend adapter. Nothing below this block touches a backend directly.
# ---------------------------------------------------------------------------

def _is_bs4(node: XmlNode) -> bool:
    return isinstance(node, Tag)


def _local_name(tag: str) -> str:
    """`{http://www.sec.gov/edgar}cik` -> `cik`."""
    return tag.rpartition('}')[2]


def _is_element(node) -> bool:
    """lxml comments and processing instructions are nodes too; their tag is a
    callable rather than a string. bs4 does not surface them from a name search."""
    return isinstance(node.tag, str)


def _find(node: XmlNode, name: str) -> Optional[XmlNode]:
    """The first DESCENDANT element named `name`, or None — bs4 `.find()` semantics."""
    if _is_bs4(node):
        found = node.find(name)
        return found if isinstance(found, Tag) else None

    found = node.find(f'.//{name}')
    if found is not None:
        return found
    # A default namespace makes `.//name` miss `{ns}name`, where bs4 matched on the
    # local name. Only reached when the fast path found nothing.
    for element in node.iter():
        if _is_element(element) and _local_name(element.tag) == name:
            return element
    return None


def _find_all(node: XmlNode, name: str) -> List[XmlNode]:
    """Every DESCENDANT element named `name`, in document order."""
    if _is_bs4(node):
        return [el for el in node.find_all(name) if isinstance(el, Tag)]

    found = node.findall(f'.//{name}')
    if found:
        return found
    return [el for el in node.iter() if _is_element(el) and _local_name(el.tag) == name]


def _collapse(text: str) -> str:
    """Apply bs4's whitespace handling to one text node.

    Its XML treebuilder leaves any node with content untouched — `'  spaced  '` and
    `'a  b'` survive verbatim — but collapses a whitespace-ONLY node to a single
    character: a newline if it contained one, otherwise a space. That is what makes
    `<d>\\n  <e>Y</e>\\n  <f>Z</f>\\n</d>` read as `'\\nY\\nZ\\n'` rather than
    keeping every space of indentation.
    """
    if text.strip():
        return text
    return '\n' if '\n' in text or '\r' in text else ' '


def _iter_text(element: etree._Element) -> Iterator[str]:
    """Every text node under `element`, skipping comment and PI bodies as bs4 does.

    A comment's *tail* is ordinary text between elements and is kept.
    """
    if element.text:
        yield element.text
    for child in element:
        if _is_element(child):
            yield from _iter_text(child)
        if child.tail:
            yield child.tail


def _text(node: XmlNode) -> str:
    """All descendant text, concatenated — bs4 `.text` semantics."""
    if _is_bs4(node):
        return node.text
    return ''.join(_collapse(chunk) for chunk in _iter_text(node))


def _attrib(node: XmlNode):
    """The attribute mapping, for the callers that require a key to be present."""
    return node.attrs if _is_bs4(node) else node.attrib


# ---------------------------------------------------------------------------
# Public helpers. Signatures unchanged — ~350 call sites depend on them.
# ---------------------------------------------------------------------------

def find_element(
        xml_tag_or_string: Union[str, XmlNode],
        element_name: str) -> Optional[XmlNode]:
    """
    Find the element with that name in the string or element
    :param xml_tag_or_string: either an xml element or a string containing xml
    :param element_name: The name of the element to find
    :return: An element
    """
    if isinstance(xml_tag_or_string, str):
        # A raw string is still parsed with bs4, so this returns the same backend it
        # always has. Its one caller (thirteenf/parsers/primary_xml.py) moves to
        # parsing with lxml itself under edgartools-07lk.11.3.
        if "<" not in xml_tag_or_string:
            return None
        return _find(BeautifulSoup(xml_tag_or_string, features="xml"), element_name)
    return _find(xml_tag_or_string, element_name)


def get_footnote_ids(tag: XmlNode,
                     sep: str = ',') -> str:
    """Get the footnotes from the tag as a string"""
    return sep.join([
        str(el.get('id', '')) for el in _find_all(tag, "footnoteId") if el.get('id')
    ])


def value_with_footnotes(tag: XmlNode,
                         footnote_sep: str = ",") -> str:
    """Get the value from the tag, including footnotes if there are any
    Example: Given this xml
        <underlyingSecurityTitle>
            <value>Class B Common Stock</value>
            <footnoteId id="F2"/>
            <footnoteId id="F3"/>
        </underlyingSecurityTitle>

        return "Class B Common Stock [F2,F3]"
    """
    value_tag = _find(tag, 'value')
    value = _text(value_tag) if value_tag is not None else ""

    footnote_ids = get_footnote_ids(tag, footnote_sep)
    footnote_str = f"[{footnote_ids}]" if footnote_ids else ""
    if value:
        return f"{value} {footnote_str}" if footnote_str else value
    return footnote_str


def value_or_footnote(el: XmlNode) -> Optional[str]:
    value_el = _find(el, 'value')
    if value_el is not None:
        return _text(value_el).strip()
    else:
        footnote = _find(el, 'footnote')
        if footnote is None:
            footnote = _find(el, "footnoteId")
        if footnote is not None:
            return str(_attrib(footnote)['id'])


def child_text(parent: XmlNode,
               child: str) -> Optional[str]:
    """
    Get the text of the child element if it exists or None
    :param parent: The parent element
    :param child: The name of the child element
    :return: the text of the child element if it exists or None
    """
    el = _find(parent, child)
    if el is not None:
        return _text(el).strip()


def child_value(parent: XmlNode,
                child: str,
                default_value: Optional[str] = None) -> Optional[str]:
    """
    Get the text of the value tag within the child tag if it exists or None

    :param parent: The parent element
    :param child: The name of the child element
    :param default_value: The default value to return if the value is None
    :return: the text of the child element if it exists or None
    """
    el = _find(parent, child)
    if el is not None:
        return value_with_footnotes(el)
    return default_value


def child_texts(parent: XmlNode,
                child: str) -> List[str]:
    """
    Get the text of the value tag within the child tag if it exists or None

    :param parent: The parent element
    :param child: The name of the child element
    :return: the text of the child element if it exists or None
    """
    return [_text(el) for el in _find_all(parent, child)]


def optional_decimal(parent: XmlNode,
                     child: str) -> Optional[Decimal]:
    text = child_text(parent, child)
    if text:
        if text == "N/A":
            return None
        return Decimal(text)


def extract_child_text(tag: XmlNode,
                       key: str,
                       child_tag_name: str) -> Tuple[str, Optional[str]]:
    """Get the child text from the tag and return a Tuple (key, child_value)
      Useful for populating dicts

      :param tag The element
      :param key The dict key to use to pupulate the dict or DataFrame
      :param child_tag_name The child tag name
    """
    return key, child_text(tag, child_tag_name)


def extract_child_value(tag: XmlNode,
                        key: str,
                        child_tag_name: str) -> Tuple[str, Optional[str]]:
    """Get the child value from the tag and return a Tuple (key, child_value)
      Useful for populating dicts
      :param tag The element
      :param key The dict key to use to pupulate the dict or DataFrame
      :param child_tag_name The child tag name
    """
    return key, child_value(tag, child_tag_name)
