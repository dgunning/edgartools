"""
Rendering pipeline for the text of a filing's primary document, as read from SGML.

This backs ``FilingSGML.text()`` — the offline path, used when the parsed submission is
already in hand and no network call is wanted. It implements:

1. Binary primary documents are detected *before* any decode, so a PDF is never
   returned as mojibake. A binary primary falls back to the SEC's ``TEXT-EXTRACT``
   sibling when the submission has one, and otherwise yields None.
2. Ownership XML (Forms 3/4/5) is rendered through the same ``Ownership.to_html()``
   the ownership data objects use, rather than leaking raw ``<ownershipDocument>``
   markup.
3. HTML is parsed and rendered to text; a parse failure degrades to the document's
   visible text rather than raising.
4. Anything else — plain text, and XML with no offline renderer — is returned as-is
   with SGML page-break markers removed.

SCOPE: ``Filing.text()`` is deliberately NOT routed through this module.
------------------------------------------------------------------------
``Filing.text()`` and ``Filing.html()`` carry many overlapping, load-bearing contracts
(``html()`` is None for old text-only filings; ``text()`` is "" for XML-only forms like
TA-1/A; UPLOAD correspondence resolves through its TEXT-EXTRACT sibling). An earlier
attempt to unify the two paths — f3b0bd9f, shipped in 5.39.0 — broke several of them
and was reverted wholesale in d216a934. The lesson recorded there is that changes to
this area must be *additive to FilingSGML* rather than a rerouting of ``Filing``.

So the two paths still diverge on some shapes, knowingly:

* Plain-text primaries: ``Filing.text()`` wraps them in HTML and parses (which strips
  the SGML ``<TABLE>``/``<S>``/``<C>`` tags historic filings embed); ``FilingSGML.text()``
  returns fixed-width text verbatim, preserving column layout. Neither is a superset of
  the other.
* Non-ownership XML (13F-HR, D/A, and the XML-native forms in
  ``edgar.xmlfiling.XML_FILING_FORMS``): ``Filing.text()`` can render these through the
  SEC's XSLT endpoint, which needs both a ``Filing`` and a network call. ``FilingSGML``
  has neither, so it returns the XML verbatim.
* Ownership XML with no ``<?xml`` declaration: ``Filing.html()``'s ownership branch
  fires on the declaration, so ``Filing.text()`` still returns a tag-stripped skeleton
  for these; this module detects the root element and renders them.
* ``<FILENAME>``-less primaries with malformed HTML: ``Filing.html()`` is None for
  them, so ``Filing.text()`` returns the raw ``<TEXT>`` body (markup and all), never
  reaching the hardened parser. ``FilingSGML.text()`` renders them.
* Binary primaries with no TEXT-EXTRACT sibling: ``Filing.text()`` returns the raw
  uuencoded ``<TEXT>`` body (pinned by test_correspondence); ``FilingSGML.text()``
  returns None.
"""

import logging
import re
from typing import Callable, Optional

__all__ = [
    'OWNERSHIP_FORMS',
    'is_ownership_form',
    'looks_like_ownership_xml',
    'ownership_xml_to_html',
    'decode_document_content',
    'html_to_text',
    'strip_html_tags',
    'primary_document_text',
]

log = logging.getLogger(__name__)

#: Ownership forms whose primary document is ``<ownershipDocument>`` XML.
OWNERSHIP_FORMS = frozenset({'3', '3/A', '4', '4/A', '5', '5/A'})

_TAG_RE = re.compile(r'<[^>]+>')
_OWNERSHIP_ROOT_RE = re.compile(r'<(?:[\w.-]+:)?ownershipDocument\b')


def is_ownership_form(form: Optional[str]) -> bool:
    """True when ``form`` is a Section 16 ownership form (3, 4, 5 and amendments)."""
    return bool(form) and form.strip().upper() in OWNERSHIP_FORMS


def looks_like_ownership_xml(content: Optional[str]) -> bool:
    """True when ``content`` is an ownership XML document.

    Checked in addition to the form code because the SGML header form and the
    document's own ``documentType`` disagree on some filings (e.g. a Form 4 filed
    under a 10-K accession), and because ``FilingSGML`` may have no form at all.
    """
    if not content:
        return False
    return bool(_OWNERSHIP_ROOT_RE.search(content[:4000]))


def ownership_xml_to_html(content: str, form: Optional[str] = None) -> Optional[str]:
    """Render ownership XML to HTML offline, or None if it cannot be parsed.

    Builds the same data object ``filing.obj()`` builds - Form3/Form4/Form5 when the
    form is known, plain ``Ownership`` otherwise - so this renders the Form 4 exactly
    as ``Filing.html()`` does when it reaches its own ownership branch.
    """
    try:
        from edgar.ownership import Form3, Form4, Form5, Ownership
        cls = {'3': Form3, '4': Form4, '5': Form5}.get(
            (form or '').strip().upper().replace('/A', ''), Ownership
        )
        return cls(**Ownership.parse_xml(content)).to_html()
    except Exception as e:  # malformed or unexpected ownership XML
        log.debug("Could not render ownership XML to HTML: %s", e)
        return None


def decode_document_content(content, is_binary: bool = False) -> Optional[str]:
    """Decode primary-document content to text, or None when it is binary.

    Returning None rather than a lossy decode is the point: ``decode('utf-8', 'replace')``
    on a PDF produces a page of U+FFFD replacement characters that looks like text to
    every caller downstream.

    Args:
        content: ``str`` or ``bytes`` document content
        is_binary: the attachment's own verdict (extension based), which wins when set
    """
    if content is None:
        return None
    if isinstance(content, str):
        return None if is_binary else content
    if is_binary:
        return None
    # NUL bytes never appear in SEC text documents but are everywhere in PDFs.
    if b'\x00' in content[:8192]:
        return None
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        return None


def html_to_text(html: str, form: Optional[str] = None) -> str:
    """Parse HTML and render it as plain text.

    Returns "" for a document with no renderable content. If the HTML is malformed
    badly enough that the parser gives up, falls back to the document's visible text
    with tags stripped - a degraded answer, but never raw markup, because callers of
    ``text()`` are asking for text.

    Only ``HTMLParsingError`` is absorbed. ``DocumentTooLargeError`` is a deliberate
    guard rather than a malformed document, so it still propagates.
    """
    from edgar.documents import HTMLParser, ParserConfig
    from edgar.documents.exceptions import HTMLParsingError

    try:
        document = HTMLParser(ParserConfig(form=form)).parse(html)
    except HTMLParsingError as e:
        log.debug("HTML parse failed (%s); falling back to tag stripping", e)
        return strip_html_tags(html)

    if document.is_empty:
        return ""
    # Straight to the extractor, matching Filing.text(). Going via rich_to_text()
    # rendered the document through Document.__repr__, which hardcodes
    # table_max_col_width=200, so the 500 never reached the table renderer and
    # long cells were cut at 200 with no ellipsis. The comment that used to sit
    # here — "Wide enough that tables are not truncated" — described an intent
    # the code did not carry out.
    #
    # Both text paths must make this call the same way: they are asserted equal
    # by test_filing_text_baseline.test_both_paths_agree, and fixing only
    # Filing.text() is what broke it.
    return document.text(table_max_col_width=500)


def strip_html_tags(html: str) -> str:
    """Last-resort text extraction: drop tags and unescape entities."""
    import html as html_module

    without_scripts = re.sub(
        r'<(script|style)\b[^>]*>.*?</\1>', ' ', html, flags=re.IGNORECASE | re.DOTALL
    )
    text = _TAG_RE.sub('', without_scripts)
    text = html_module.unescape(text)
    # Collapse the runs of blank lines that tag removal leaves behind.
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def primary_document_text(
    form: Optional[str],
    content,
    *,
    is_binary: bool = False,
    text_extract: Optional[Callable[[], Optional[str]]] = None,
) -> Optional[str]:
    """Render a filing's primary document as text.

    Args:
        form: the filing's form type, used for form-aware rendering and parser config
        content: the primary document's content (``str`` or ``bytes``)
        is_binary: True when the attachment is known to be binary (e.g. a ``.pdf``)
        text_extract: called only for binary primaries, to supply the SEC's
            plain-text sibling (the ``TEXT-EXTRACT`` attachment) if the filing has one

    Returns:
        The document text, or None when there is no text to return - an absent or
        empty primary document, or a binary one with no text sibling. None is
        deliberate: for a PDF-only filing it is a truthful "no text here", where the
        previous behaviour returned replacement-character mojibake.
    """
    from edgar.core import is_probably_html

    text = decode_document_content(content, is_binary=is_binary)

    if text is None:
        # Binary or undecodable: the SEC often ships a plain-text rendering alongside.
        if text_extract is not None:
            extracted = text_extract()
            if extracted:
                return extracted
        return None

    if not text.strip():
        return None

    # Ownership XML renders through the ownership data object, not as raw markup.
    # The markup guard keeps pre-XML (2002-era) Forms 3/4/5, which are fixed-width
    # text, out of the XML parser.
    if text.lstrip().startswith('<') and (is_ownership_form(form) or looks_like_ownership_xml(text)):
        rendered = ownership_xml_to_html(text, form=form)
        if rendered:
            return html_to_text(rendered, form=form)

    if is_probably_html(text):
        return html_to_text(text, form=form)

    # Plain text (and XML with no offline renderer): return as-is, minus the SGML
    # page-break markers. Fixed-width layout is preserved, not reflowed.
    return text.replace("<PAGE>", "")
