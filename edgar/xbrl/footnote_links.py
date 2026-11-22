"""
The rules that link XBRL facts to their footnotes, shared by every reader.

Three readers turn footnotes into the same ``Footnote`` objects and fact
``footnotes`` id lists: the instance parser's ``footnoteLink`` reader, its
fallback reader for the inline document (``ix:footnote`` + ``ix:relationship``),
and ``edgar.documents``' inline XBRL extractor. They see different trees -- an
XML tree with namespaced tags and camel-case attributes, or an HTML tree whose
attribute names are lower-cased -- so each reads its own attributes, but which
relationship is a footnote link, how a footnote's text is read and which
language applies are decided here once.
"""

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

FACT_FOOTNOTE_ARCROLE = "http://www.xbrl.org/2003/arcrole/fact-footnote"
FOOTNOTE_ROLE = "http://www.xbrl.org/2003/role/footnote"

# Elements whose content is a block: a break belongs after them, or the last
# word of one runs into the first word of the next.
_BLOCK_ELEMENTS = frozenset({
    'address', 'article', 'blockquote', 'br', 'div', 'dd', 'dl', 'dt',
    'fieldset', 'figcaption', 'figure', 'footer', 'form', 'h1', 'h2', 'h3',
    'h4', 'h5', 'h6', 'header', 'hr', 'li', 'main', 'nav', 'ol', 'p', 'pre',
    'section', 'table', 'tbody', 'tfoot', 'thead', 'tr', 'ul',
})

# Table cells sit side by side: a space keeps their text apart on one line.
_CELL_ELEMENTS = frozenset({'td', 'th'})


def is_fact_footnote_arcrole(arcrole: Optional[str]) -> bool:
    """
    Whether a relationship with this arcrole links a fact to an ordinary footnote.

    Inline XBRL 1.1 section 13.1 defaults an absent arcrole to fact-footnote;
    an absent arcrole on a ``footnoteArc`` is read the same way. Any other
    arcrole -- fact-explanatoryFact, or a filer's own -- is a different
    relationship, and presenting it as an ordinary footnote would misstate it.
    """
    return arcrole is None or arcrole == FACT_FOOTNOTE_ARCROLE


def fact_footnote_links(relationships: Iterable[Tuple[Optional[str], Optional[str], Optional[str]]],
                        footnote_ids) -> List[Tuple[List[str], List[str]]]:
    """
    ``(fact ids, footnote ids)`` for each fact-footnote ``ix:relationship``.

    ``relationships`` holds each relationship's ``(arcrole, fromRefs, toRefs)``
    as filed. A target that is not a known footnote id is dropped, so a
    relationship to another fact never becomes a footnote.
    """
    links: List[Tuple[List[str], List[str]]] = []
    for arcrole, from_refs, to_refs in relationships:
        if not is_fact_footnote_arcrole(arcrole):
            continue
        to_ids = [ref for ref in (to_refs or '').split() if ref in footnote_ids]
        from_ids = (from_refs or '').split()
        if to_ids and from_ids:
            links.append((from_ids, to_ids))
    return links


def collect_footnote_text(node, parts: List[str]) -> None:
    """Append this node's text, its children's, and their tails, in order."""
    if node.text:
        parts.append(node.text)

    for child in node:
        tag = child.tag
        name = tag.rsplit('}', 1)[-1].lower() if isinstance(tag, str) else ''

        collect_footnote_text(child, parts)

        if name in _BLOCK_ELEMENTS:
            parts.append('\n')
        elif name in _CELL_ELEMENTS:
            parts.append(' ')

        if child.tail:
            parts.append(child.tail)


def normalize_footnote_text(parts: Sequence[str]) -> str:
    """Collapse whitespace within each line and drop empty lines."""
    lines = []
    for raw_line in ''.join(parts).split('\n'):
        line = ' '.join(raw_line.split())
        if line:
            lines.append(line)
    return '\n'.join(lines)


def inline_footnote_text(footnote_elem, continuations: Dict[str, Any],
                         continued_at_attrs: Sequence[str] = ('continuedAt',)) -> str:
    """
    An ix:footnote's text, followed through its ``continuedAt`` chain.

    A continuation carries on the same run of text, so it is joined with no
    break -- the way SEC's extraction writes it into the footnoteLink.
    ``continued_at_attrs`` names the attribute as the tree spells it.
    """
    def continued_at(elem) -> Optional[str]:
        return next((elem.get(a) for a in continued_at_attrs if elem.get(a)), None)

    parts: List[str] = []
    collect_footnote_text(footnote_elem, parts)
    seen = set()
    next_id = continued_at(footnote_elem)
    while next_id and next_id not in seen and next_id in continuations:
        seen.add(next_id)
        continuation = continuations[next_id]
        collect_footnote_text(continuation, parts)
        next_id = continued_at(continuation)
    return normalize_footnote_text(parts)


def inherited_lang(elem, lang_attr: str) -> str:
    """The xml:lang in scope for an element, as XML inherits it from ancestors."""
    node = elem
    while node is not None:
        lang = node.get(lang_attr)
        if lang:
            return lang
        node = node.getparent()
    return 'en-US'
