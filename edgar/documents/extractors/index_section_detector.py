"""Section detection for 10-K filings that publish a Cross Reference Index.

A handful of large filers (Citigroup, GE) do not label items in the body at all.
Instead the filing opens with a "Form 10-K Cross-Reference Index" table mapping
each item to the *printed page numbers* where its disclosure lives, and the body
carries only descriptive headings ("RISK FACTORS", "MANAGEMENT'S DISCUSSION...").

Every anchor-driven strategy fails on such a document, and correctly so: there
are no anchors and almost no "Item N" strings to key off (Citigroup's 16.7MB
10-K contains two). What is left is the index itself, which is authoritative —
the filer is telling the SEC exactly where each item is — plus the page-break
markers needed to turn a page range back into a slice of HTML.

This detector reads that index and emits canonically-keyed sections
(``part_ii_item_7``), so a caller asking for Item 7 gets the MD&A the filer
pointed at rather than whatever a keyword fallback guessed. It deliberately
emits *nothing* for items whose index row carries no page range — "Not
Applicable", "[Reserved]", or a bare incorporation-by-reference asterisk — since
for those there is no content in this document to return.
"""

import logging
from typing import Dict, Optional

from edgar.documents.document import Document, Section
from edgar.documents.nodes import SectionNode

logger = logging.getLogger(__name__)

# Only 10-K filings use this construct; the index heading names the form.
_SUPPORTED_FORMS = {'10-K', '10-K/A'}

# Confidence for an index-derived section. Below the TOC path's 0.95: the item
# mapping is authoritative (the filer wrote it) but the boundaries are only as
# precise as the printed page, and a filer can mis-cite its own pages — Citigroup
# cites 135-136 for Item 9A when the content is on page 134 (edgartools-4agg).
INDEX_CONFIDENCE = 0.85


class IndexSectionDetector:
    """Build sections from a 10-K Cross Reference Index.

    Example:
        >>> detector = IndexSectionDetector(document, '10-K')
        >>> sections = detector.detect()
        >>> sections['part_ii_item_7'].text()[:40]           # doctest: +SKIP
        "MANAGEMENT'S DISCUSSION AND ANALYSIS ..."
    """

    def __init__(self, document: Document, form: str):
        self.document = document
        self.form = form

    def detect(self) -> Optional[Dict[str, Section]]:
        """Detect sections from the cross-reference index.

        Returns:
            Sections keyed by canonical ``part_<part>_item_<item>`` name, or
            None when the filing has no usable index.
        """
        if self.form not in _SUPPORTED_FORMS:
            return None

        html_content = getattr(self.document.metadata, 'original_html', None)
        if not html_content:
            logger.debug("Index detection unavailable: original_html not in document metadata")
            return None

        try:
            from edgar.documents.cross_reference_index import CrossReferenceIndex

            index = CrossReferenceIndex(html_content)
            if not index.has_index():
                return None

            entries = index.parse()
            if not entries:
                return None

            sections: Dict[str, Section] = {}
            for item_id, entry in entries.items():
                # No page range means the item has no disclosure *here* (Not
                # Applicable, [Reserved], or incorporated by reference from the
                # proxy). Emitting an empty section would present absence as
                # content; leaving it out keeps the map honest.
                if not entry.pages:
                    continue

                part = self._part_roman(entry)
                if not part:
                    continue

                name = f"part_{part.lower()}_item_{item_id.lower()}"
                section = Section(
                    name=name,
                    title=entry.full_item_name,
                    node=SectionNode(section_name=name),
                    start_offset=0,
                    # Left at 0 rather than the extracted length: measuring it
                    # would mean slicing and re-parsing every item up front,
                    # which on a 16MB filing costs more than the whole parse.
                    # Text is fetched lazily instead.
                    end_offset=0,
                    confidence=INDEX_CONFIDENCE,
                    detection_method='index',
                    part=part,
                    item=item_id.upper(),
                    _text_extractor=_make_text_extractor(index, item_id),
                    _html_source=html_content,
                )
                sections[name] = section

            if sections:
                logger.info(
                    f"Cross-reference index detection found {len(sections)} sections "
                    f"from {len(entries)} index entries"
                )
                return sections

            return None

        except Exception as e:
            logger.warning(f"Cross-reference index detection failed: {e}", exc_info=True)
            return None

    @staticmethod
    def _part_roman(entry) -> Optional[str]:
        """Roman-numeral part for an index entry ('Part II' -> 'II').

        Falls back to the form schema when the index omits the Part header, so a
        row that appears before any "Part I" divider still lands on a canonical
        key rather than being dropped.
        """
        if entry.part:
            return entry.part.replace('Part ', '').strip().upper()

        from edgar.documents.form_schema import get_form_schema

        label = get_form_schema('10-K').part_for_item(f"Item {entry.item_number}")
        if label:
            return label.replace('Part ', '').strip().upper()
        return None


def _make_text_extractor(index, item_id: str):
    """Build the lazy text callback for one index entry.

    The index slices the *original HTML* by page range, so the result is markup
    and has to be converted before it reaches a caller who asked for text — the
    unconverted-HTML leak that GH #821 fixed on the TenK path. The conversion
    parses without a form so the inner parse does not re-enter section
    detection, and the result is memoised because a single item can be several
    megabytes of HTML (Citigroup's Item 8 is 9.3MB).
    """
    cache: Dict[bool, str] = {}

    def extract_text(section_name=None, **kwargs):
        clean = bool(kwargs.get('clean', True))
        if clean in cache:
            return cache[clean]

        from edgar.documents import parse_html

        item_html = index.extract_item_content(item_id)
        text = parse_html(item_html).text() if item_html else ""
        cache[clean] = text
        return text

    return extract_text
