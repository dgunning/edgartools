"""
What a concept is: its type, balance, period type, abstract status, FASB
documentation and Accounting Standards Codification references (GH #1426).

Three sources, each answering for what it holds:

1. The filing's own schema declares its extension concepts.
2. The bundled FASB element table (edgar/xbrl/data/taxonomy_elements.parquet)
   declares every us-gaap and srt concept the filing imports.
3. The SEC's MetaLinks.json for the filing carries documentation and ASC
   references, plus type and balance for every concept the filing uses. It is
   read on the first ``XBRL.element_metadata()`` call, never while parsing.

A declaration wins over MetaLinks for the same field, and no field is guessed
from a concept's name.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, Tuple

from edgar.core import log
from edgar.sgml.metalinks import AuthRef, MetaLinks
from edgar.xbrl.parsers.concepts import get_standard_declaration

if TYPE_CHECKING:
    from edgar.xbrl.models import ElementCatalog

METALINKS_FILE = 'MetaLinks.json'
_STANDARD_NAMESPACES = ('us-gaap', 'srt', 'dei', 'ecd', 'ifrs-full', 'country', 'stpr', 'currency', 'exch', 'naics', 'sic')

__all__ = ['ElementMetadata', 'METALINKS_FILE']


@dataclass(frozen=True)
class ElementMetadata:
    """
    Metadata for one concept, from ``XBRL.element_metadata()``.

    Every field is None when no source states it: a None ``balance`` means no
    source declares one, which is the case for share counts and for the
    cash-flow totals. ``documentation`` and ``references`` come from the
    filing's MetaLinks.json and are None when that file is not available (a
    filing before about 2012, or an XBRL object built from local files with no
    MetaLinks.json beside them). An empty ``references`` tuple means MetaLinks
    was read and lists none, which is usual for company extensions.

    Attributes:
        concept: The element id, e.g. 'us-gaap_Assets'.
        prefix: The namespace prefix, e.g. 'us-gaap'.
        name: The local name, e.g. 'Assets'.
        is_standard: True for a standard taxonomy concept (us-gaap, srt, dei, ...).
        data_type: The declared type as its source spells it, e.g.
            'xbrli:monetaryItemType' (or 'monetaryItemType' from MetaLinks).
        balance: 'debit', 'credit' or None.
        period_type: 'instant', 'duration' or None.
        abstract: The declared abstract flag, or None when no declaration was read.
        documentation: The FASB (or filer) definition text.
        references: The ASC references, as ``edgar.sgml.AuthRef`` records.
    """
    concept: str
    prefix: str
    name: str
    is_standard: bool
    data_type: Optional[str]
    balance: Optional[str]
    period_type: Optional[str]
    abstract: Optional[bool]
    documentation: Optional[str]
    references: Optional[Tuple[AuthRef, ...]]

    def __repr__(self) -> str:
        refs = 'unavailable' if self.references is None else len(self.references)
        return (f"ElementMetadata({self.concept}, type={self.data_type}, balance={self.balance}, "
                f"period_type={self.period_type}, abstract={self.abstract}, references={refs})")


def concept_id(concept: str) -> str:
    """'us-gaap:Assets' or 'us-gaap_Assets' -> 'us-gaap_Assets'."""
    if not isinstance(concept, str):
        raise TypeError(f"concept must be a string like 'us-gaap:Assets', not {type(concept).__name__}")
    concept = concept.strip()
    prefix, colon, name = concept.partition(':')
    if colon:
        concept = f"{prefix}_{name}"
    prefix, underscore, name = concept.partition('_')
    if not (underscore and prefix and name):
        from edgar.exceptions import ValidationError
        raise ValidationError(f"concept {concept!r} needs a namespace prefix, like 'us-gaap:Assets' or 'us-gaap_Assets'",
                              parameter='concept', invalid_value=concept)
    return concept


class MetaLinksSource:
    """
    Reads MetaLinks.json once, on first use.

    ``load`` returns the file's text, or None when the filing has no
    MetaLinks.json. That answer is kept; an error (a dropped connection, say)
    propagates and is not, so a later call tries again.
    """

    _UNREAD = object()

    def __init__(self, load: Callable[[], Optional[str]], description: str):
        self._load = load
        self._description = description
        self._metalinks = self._UNREAD

    def get(self) -> Optional[MetaLinks]:
        if self._metalinks is self._UNREAD:
            text = self._load()
            self._metalinks = MetaLinks.parse(text) if text else None
            if self._metalinks is None:
                log.debug("No %s for %s", METALINKS_FILE, self._description)
        return self._metalinks


class _FilingMetaLinks:
    """MetaLinks.json for a filing: from its submission if loaded, else the filing folder."""

    def __init__(self, filing):
        self._filing = filing

    def __call__(self) -> Optional[str]:
        from edgar.httprequests import TransportError, download_file

        filing = self._filing
        if getattr(filing, '_sgml', None) is not None:
            content = filing.sgml().get_content(METALINKS_FILE)
            return content or None
        try:
            content = download_file(f"{filing.base_dir}/{METALINKS_FILE}", as_text=True)
        except TransportError as e:
            if getattr(e, 'status_code', None) == 404:
                return None
            raise
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        return content or None


def filing_metalinks_source(filing) -> MetaLinksSource:
    return MetaLinksSource(_FilingMetaLinks(filing), f"filing {filing.accession_no}")


def directory_metalinks_source(directory: Path) -> Optional[MetaLinksSource]:
    path = Path(directory) / METALINKS_FILE
    if not path.is_file():
        return None
    return MetaLinksSource(path.read_text, str(path))


def build_element_metadata(concept: str,
                           element: Optional['ElementCatalog'],
                           metalinks: Optional[MetaLinks]) -> Optional[ElementMetadata]:
    """
    Combine the three sources for one concept, or None when none of them knows it.

    ``element`` is the concept's element-catalog entry. The catalog holds a
    declaration only when ``data_type`` is set; an entry without one came from
    a label, with a period type read from the concept's facts at most.
    """
    concept = concept_id(concept)
    prefix, _, name = concept.partition('_')
    declared = element if element is not None and element.data_type is not None else None
    standard = get_standard_declaration(concept)
    tag = metalinks.get_tag(concept) if metalinks is not None else None
    if element is None and standard is None and tag is None:
        return None

    def first(*values):
        return next((v for v in values if v is not None and v != ''), None)

    if declared is not None:
        abstract = bool(declared.abstract)
    elif standard is not None:
        abstract = bool(standard['abstract'])
    else:
        abstract = None

    return ElementMetadata(
        concept=concept,
        prefix=prefix,
        name=name,
        is_standard=prefix in _STANDARD_NAMESPACES,
        data_type=first(declared.data_type if declared else None,
                        standard['type'] if standard else None,
                        tag.xbrltype if tag else None),
        balance=first(declared.balance if declared else None,
                      standard['balance'] if standard else None,
                      tag.crdr if tag else None),
        # An undeclared catalog entry's period type was read from its facts:
        # the declaration in the table comes first.
        period_type=first(declared.period_type if declared else None,
                          standard['period_type'] if standard else None,
                          element.period_type if element is not None else None),
        abstract=abstract,
        documentation=(tag.documentation or None) if tag else None,
        references=(tuple(metalinks.get_auth_refs_for_tag(tag)) if tag
                    else (() if metalinks is not None else None)),
    )
