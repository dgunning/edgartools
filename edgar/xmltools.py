"""XML element helpers shared by twelve SEC form parsers.

Every helper takes an ``lxml.etree`` element. Until 6.0 they also accepted a
BeautifulSoup ``Tag`` while the dependents moved off bs4 one at a time
(edgartools-07lk.11.2/.11.3); 6.0 deleted that half along with the dependency
(edgartools-07lk.11 phase 6).

bs4's behavior is still the contract, because ~350 call sites were written against
it. Reproducing it on lxml takes more than renaming methods — the two libraries
differ on four axes, and every difference fails *silently*, returning None or ""
where a value used to be:

  truthiness  ``bool(Tag)`` is True even for a childless ``<c/>``; ``bool(Element)``
              is False even for ``<b>text</b>``. Guards here test ``is not None``.
  find depth  ``Tag.find()`` searches all descendants; ``Element.find()`` searches
              direct children. ``_find`` uses ``.//`` to match bs4's reach.
  .text       ``Tag.text`` concatenates the whole subtree; ``Element.text`` stops at
              the first child element. ``_text`` walks the subtree.
  whitespace  bs4's XML treebuilder collapses a whitespace-ONLY text node to a
              single character. ``_collapse`` reproduces that exactly; it is the one
              place the port is more than a translation.

tests/core/test_xmltools_semantics.py pins each of those behaviors.
"""
from decimal import Decimal
from typing import Iterator, List, Optional, Tuple, Union

from lxml import etree

__all__ = [
    'XmlNode',
    'child_text',
    'child_value',
    'child_texts',
    'element_text',
    'find_all_elements',
    'find_element',
    'get_footnote_ids',
    'local_name',
    'optional_decimal',
    'parse_xml',
    'xml_parser',
    'add_safe_resolver',
    'value_or_footnote',
    'extract_child_text',
    'extract_child_value',
    'value_with_footnotes',
]

# The element type every helper takes. Kept as a name because dependents annotate
# with it; it was `Union[Tag, etree._Element]` until 6.0 dropped bs4.
XmlNode = etree._Element


# ---------------------------------------------------------------------------
# lxml adapter: bs4 semantics on lxml elements.
# ---------------------------------------------------------------------------

def _local_name(tag: str) -> str:
    """`{http://www.sec.gov/edgar}cik` -> `cik`."""
    return tag.rpartition('}')[2]


def _namespace_of(node) -> str:
    """The Clark-notation namespace prefix of a node's own tag, or `''`.

    Nearly every namespaced SEC document uses one default namespace throughout, so
    a child's namespace is its parent's. Trying that before the local-name scan is
    worth ~2.2x per lookup on such documents, measured on the Atom current-filings
    feed, where the fallback is the normal path rather than the exception.
    """
    tag = node.tag
    if isinstance(tag, str) and tag.startswith('{'):
        return tag[:tag.index('}') + 1]
    return ''


def _is_element(node) -> bool:
    """lxml comments and processing instructions are nodes too; their tag is a
    callable rather than a string. bs4 did not surface them from a name search."""
    return isinstance(node.tag, str)


def _find(node: XmlNode, name: str) -> Optional[XmlNode]:
    """The first DESCENDANT element named `name`, or None — bs4 `.find()` semantics."""
    found = node.find(f'.//{name}')
    if found is not None:
        return found
    # A default namespace makes `.//name` miss `{ns}name`, where bs4 matched on the
    # local name. Try this node's own namespace, then scan local names for the rare
    # document that mixes several. Only reached when the plain path found nothing.
    namespace = _namespace_of(node)
    if namespace:
        found = node.find(f'.//{namespace}{name}')
        if found is not None:
            return found
    for element in node.iter():
        if _is_element(element) and _local_name(element.tag) == name:
            return element
    return None


def _find_all(node: XmlNode, name: str) -> List[XmlNode]:
    """Every DESCENDANT element named `name`, in document order."""
    found = node.findall(f'.//{name}')
    if found:
        return found
    namespace = _namespace_of(node)
    if namespace:
        found = node.findall(f'.//{namespace}{name}')
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
    return ''.join(_collapse(chunk) for chunk in _iter_text(node))


def _attrib(node: XmlNode):
    """The attribute mapping, for the callers that require a key to be present."""
    return node.attrib


# ---------------------------------------------------------------------------
# Public helpers. Signatures unchanged — ~350 call sites depend on them.
# ---------------------------------------------------------------------------

class _NoExternalResources(etree.Resolver):
    """Answer every external lookup — a DTD, a parameter entity, a general entity — with nothing."""

    def resolve(self, system_url, public_id, context):
        return self.resolve_string("", context)


def xml_parser(**options) -> etree.XMLParser:
    """An lxml XMLParser that never reads a resource the document names.

    Filing XML is written by the filer. lxml's defaults block network access and
    external general entities, but libxml2 still loads an external *parameter*
    entity (``<!ENTITY % p SYSTEM "file:///...">`` in the internal subset) from the
    local filesystem, with or without ``recover``. The resolver answers every such
    lookup with an empty document, so nothing outside the bytes being parsed is
    read. Entities the document defines itself, and the predefined and character
    entities, still expand, so ordinary output is unchanged.

    Every lxml XML parse in edgartools goes through this; ``options`` are passed
    to ``etree.XMLParser``. Build a fresh parser per call: lxml parsers hold
    mutable state and must not be shared across threads. For ``etree.iterparse``,
    which takes no parser, add the resolver with ``add_safe_resolver``.
    """
    parser = etree.XMLParser(**options)
    parser.resolvers.add(_NoExternalResources())
    return parser


def add_safe_resolver(context):
    """Give an ``etree.iterparse`` context the resolver ``xml_parser`` installs; returns it."""
    context.resolvers.add(_NoExternalResources())
    return context


def parse_xml(xml: Union[str, bytes]) -> etree._Element:
    """Parse a whole XML document with lxml and return its root element.

    The entry point for the `from_xml(xml: str)` classmethods the dependents expose
    (EFFECT, Form D, Form C, Form 144, muni advisors, ...). It exists so the two
    things `BeautifulSoup(xml, "xml")` absorbed silently are handled once here
    rather than nine times, each time slightly differently:

      leading space  bs4 accepts whitespace or a BOM before the XML declaration;
                     lxml raises `XMLSyntaxError: XML declaration allowed only at
                     the start of the document`. Documents that reach us through a
                     template, a heredoc or a test fixture routinely carry one.
      encoding       a `str` has already been decoded, but re-encoding it to UTF-8
                     leaves any `encoding="ISO-8859-1"` declaration standing, and
                     lxml believes the declaration over the bytes: an entity named
                     `Café` comes back as `CafÃ©`. Forcing the parser's encoding
                     overrides the declaration, which is correct because the `str`
                     was decoded by whoever produced it.

      recovery     SEC's own XML is not always well-formed, and bs4 hid that for
                   years: `BeautifulSoup(xml, "xml")` builds its parser with
                   `recover=True`, so a document carrying an attribute like
                   `<nonDerivativeTable ativeTable>` parsed fine. A strict parser
                   rejects it outright. That is not hypothetical — AAR CORP's
                   2004-02-04 Form 4 (0000001750-04-000011) is exactly this shape,
                   and strictness turned it from a rendered Form 4 into a dump of
                   raw markup. Recovery is what makes bs4's behavior the contract
                   rather than an aspiration.

    `bytes` are passed through with their declaration intact — those came off the
    wire undecoded, so the declaration is the only encoding information there is.

    A document that is not XML at all is still an error, just a different one. An
    HTML error page recovers to an `<html>` root, which every caller's root check
    rejects with a clear "expected <edgarSubmission>" — a better message than a
    parse error at this level. Content with no markup at all recovers to nothing,
    and lxml signals that by returning None from `fromstring`; that is re-raised
    here as `XMLSyntaxError`, because a caller handed None fails several frames
    later with an AttributeError naming the wrong thing.
    """
    if isinstance(xml, str):
        # A fresh parser per call: lxml parsers hold mutable state and must not be
        # shared across threads, and edgartools parses on worker threads.
        root = etree.fromstring(xml.lstrip('\ufeff \t\r\n').encode('utf-8'),
                                parser=xml_parser(encoding='utf-8', recover=True))
    else:
        root = etree.fromstring(xml.lstrip(), parser=xml_parser(recover=True))
    if root is None:
        raise etree.XMLSyntaxError("Document is not XML: nothing recoverable", None, 1, 1)
    return root


def _parse_string(xml: str) -> Optional[XmlNode]:
    """The root of a raw XML string, or None when there is no markup to recover.

    `find_element` and `find_all_elements` have always accepted a string and
    returned None or [] for one that is not XML; they parsed it with bs4 until 6.0.
    In-tree callers parse once with `parse_xml` and pass the element.
    """
    if "<" not in xml:
        return None
    try:
        return parse_xml(xml)
    except etree.XMLSyntaxError:
        return None


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
        root = _parse_string(xml_tag_or_string)
        if root is None:
            return None
        # bs4 searched the whole document, so the root itself could match; `_find`
        # starts below the element it is given.
        if _local_name(root.tag) == element_name:
            return root
        return _find(root, element_name)
    return _find(xml_tag_or_string, element_name)


def find_all_elements(
        xml_tag_or_string: Union[str, XmlNode],
        element_name: str) -> List[XmlNode]:
    """
    Find every descendant element with that name, in document order.

    The plural of `find_element`, and the backend-neutral replacement for a direct
    `.find_all()`. Dependents migrating under edgartools-07lk.11.3 should route
    through this rather than reaching for a backend: it is what makes a default
    namespace a non-event. SEC serves the current-filings feed as Atom, so its
    elements are `{http://www.w3.org/2005/Atom}entry` and a plain lxml `.//entry`
    matches nothing at all — silently, returning an empty feed rather than raising.

    :param xml_tag_or_string: either an xml element or a string containing xml
    :param element_name: The name of the elements to find
    :return: A list of elements, empty if there are none
    """
    if isinstance(xml_tag_or_string, str):
        root = _parse_string(xml_tag_or_string)
        if root is None:
            return []
        found = _find_all(root, element_name)
        return [root] + found if _local_name(root.tag) == element_name else found
    return _find_all(xml_tag_or_string, element_name)


def local_name(node: XmlNode) -> str:
    """This element's tag without its namespace — the neutral form of `.tag`.

    For checking that a parsed document is the one you expected, which is the only
    thing `bs4`'s `soup.find("ownershipDocument")` was doing at a parse entry point.
    A namespaced document's root reads as `{http://www.sec.gov/edgar}ownershipDocument`
    on lxml, so comparing `.tag` directly is a name check that fails on exactly the
    documents the local-name matching elsewhere in this module exists to handle.
    """
    return _local_name(node.tag)


def element_text(node: XmlNode) -> str:
    """All of this element's descendant text, concatenated — bs4 `.text` semantics.

    The backend-neutral replacement for reading `.text` off an element you already
    hold. It is the difference most likely to survive review unnoticed: lxml's
    `.text` stops at the first CHILD ELEMENT, so a footnote reading
    `<footnote>see <i>note</i> below</footnote>` comes back as `'see '` — a
    plausible string rather than an error.

    `child_text(parent, name)` covers the common case of reading a *named child*
    and strips the result. Reach for this one only when the element in hand is
    already the one whose text you want.
    """
    return _text(node)


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
