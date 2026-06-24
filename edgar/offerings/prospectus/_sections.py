"""Section-scoped text access for prospectus-style filings (S-1, 424B*).

A data-object surface (edgartools-ybth / gh-866) over the shared title-based
section engine — not new parsing. The S-1/424B FormSchema title vocabulary and
the Phase 3 routing flip already produce anchor-bounded sections on the parsed
document; this mixin exposes them on the typed objects and pins the contract:

    s1.sections                  -> Sections (dict[str, Section])
    s1.section('risk_factors')   -> Section | None
    s1.section('risk_factors').text()

Contract: labelled sections when the title/TOC anchors resolve; otherwise a
single ``'full'`` section carrying the entire document text, so a caller asking
for section text never silently loses content (Verification Constitution #2).
"""
from __future__ import annotations

from functools import cached_property
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from edgar.documents.document import Section, Sections


class ProspectusSectionsMixin:
    """Adds ``.sections`` / ``.section()`` to a prospectus data object.

    Requires the host class to expose ``self._document`` (a parsed
    :class:`~edgar.documents.document.Document` or ``None``). ``filing.parse()``
    seeds the parser with the form, so title-based forms (S-1/424B) route through
    the TOC engine automatically.
    """

    @cached_property
    def sections(self) -> "Sections":
        """Named document sections, or a single ``'full'`` section as fallback.

        Returns a :class:`~edgar.documents.document.Sections` mapping (a dict
        subclass) of canonical section key -> :class:`Section`. Each section
        offers ``.text()`` / ``.markdown()`` / ``.tables()``.
        """
        from edgar.documents.document import Sections
        doc = self._document
        if doc is None:
            return Sections({})
        detected = doc.sections
        if detected:
            return detected
        return Sections(self._full_section_fallback(doc))

    def section(self, name: str) -> Optional["Section"]:
        """Return the section keyed by ``name``, or ``None`` if absent.

        When no labelled sections were detected, only ``'full'`` resolves — so
        ``section('risk_factors')`` returns ``None`` while ``section('full')``
        returns the whole-document fallback.
        """
        return self.sections.get(name)

    @staticmethod
    def _full_section_fallback(doc) -> dict:
        """One ``'full'`` section spanning the whole document (never lose content)."""
        from edgar.documents.document import Section
        from edgar.documents.nodes import SectionNode
        full = Section(
            name='full',
            title='Full Document',
            node=SectionNode(section_name='full'),
            confidence=1.0,
            detection_method='fallback',
            _text_extractor=lambda _name, **kwargs: doc.text(**kwargs),
        )
        return {'full': full}
