"""
Parse the documents of one Inline XBRL Document Set together.

An Inline XBRL 1.1 Document Set is the group of inline documents filed in one
submission. Only one of them needs an ix:header, so a fact in an exhibit can
name a context, unit or continuation that only the primary document defines.
``parse_html`` reads one document and cannot resolve those references; this
reads them all first (GH #1753).
"""

import warnings
from collections.abc import Mapping
from typing import Dict, Optional

from lxml import etree

from edgar.documents.config import ParserConfig
from edgar.documents.document import Document
from edgar.documents.parser import HTMLParser, parse_xbrl_tree
from edgar.documents.strategies.xbrl_extraction import InlineXBRLSetIndex
from edgar.exceptions import ValidationError

__all__ = ['parse_inline_xbrl_set']

# Ambiguous IDs named in the warning before it summarises the rest.
_MAX_IDS_NAMED = 20


def parse_inline_xbrl_set(sources: Mapping[str, str],
                          config: Optional[ParserConfig] = None) -> Dict[str, Document]:
    """
    Parse the inline XBRL documents of one filing as a document set.

    The contexts, units and continuations of every supplied document are
    indexed before any fact is read, so a fact in one document resolves a
    reference defined in another. Each Document keeps only its own facts.

    An ID defined more than once, in one document or across several, is
    ambiguous: references to it resolve to None and a warning names the ID and
    the documents that define it. The result does not depend on the order of
    ``sources``.

    Args:
        sources: Attachment name -> HTML, for documents of the SAME filing.
            Nothing is fetched; supply every document the facts depend on.
        config: Optional parser configuration, applied to each document.

    Returns:
        One Document per key of ``sources``, in the same order.

    Raises:
        TypeError: ``sources`` is not a mapping, or a name or HTML is not a str.
        ValidationError: ``sources`` is empty (a ValueError).

    Example:
        >>> docs = parse_inline_xbrl_set({
        ...     "ibm-20241231.htm": primary_html,      # holds the ix:header
        ...     "ibm-20241231_d2.htm": exhibit_html,   # EX-13, no ix:header
        ... })
        >>> fact = docs["ibm-20241231_d2.htm"].xbrl_facts[0]
        >>> fact.context["period_type"]
    """
    _validate_sources(sources)
    parser = HTMLParser(config or ParserConfig())
    if not parser.config.extract_xbrl:
        return {name: parser.parse(html) for name, html in sources.items()}

    roots = {name: _xbrl_root(html) for name, html in sources.items()}
    index = InlineXBRLSetIndex.build(roots)
    if index.ambiguous:
        warnings.warn(_ambiguity_message(index), stacklevel=2)

    documents: Dict[str, Document] = {}
    for name, html in sources.items():
        parser._xbrl_set_input = (roots[name], index)
        try:
            documents[name] = parser.parse(html)
        finally:
            parser._xbrl_set_input = None
    return documents


def _validate_sources(sources: Mapping[str, str]) -> None:
    if not isinstance(sources, Mapping):
        raise TypeError(
            "parse_inline_xbrl_set expects a mapping of attachment name to HTML, "
            f"got {type(sources).__name__}")
    if not sources:
        raise ValidationError("parse_inline_xbrl_set needs at least one document; got an empty mapping",
                              parameter="sources", invalid_value=sources)
    for name, html in sources.items():
        if not isinstance(name, str):
            raise TypeError(f"Document names must be str, got {type(name).__name__}: {name!r}")
        if not isinstance(html, str):
            raise TypeError(f"HTML for {name!r} must be str, got {type(html).__name__}")


def _xbrl_root(html: str):
    """The document's inline XBRL tree, or None when it has no parseable root."""
    if not html.strip():
        return None
    try:
        return parse_xbrl_tree(html)
    except etree.ParserError:
        return None


def _ambiguity_message(index: InlineXBRLSetIndex) -> str:
    entries = [f"{kind} {node_id!r} in {', '.join(docs)}"
               for kind, ids in index.ambiguous.items()
               for node_id, docs in sorted(ids.items())]
    named = '; '.join(entries[:_MAX_IDS_NAMED])
    more = f"; and {len(entries) - _MAX_IDS_NAMED} more" if len(entries) > _MAX_IDS_NAMED else ''
    return (f"Inline XBRL document set defines {len(entries)} ID(s) more than once; "
            f"references to them resolve to None: {named}{more}")
