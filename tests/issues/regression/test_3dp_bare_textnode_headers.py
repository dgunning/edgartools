"""Pre-2002 filings with no block structure still yield their items (edgartools-3dp).

Filings from before roughly 2002 are preformatted text wrapped in minimal HTML.
They parse to ``ContainerNode > TextNode`` with **zero** ``HeadingNode`` and
**zero** ``ParagraphNode``, and every header strategy in the pattern extractor
drew its candidates from headings, section nodes, bold paragraphs or table cells.
On those documents the header list was not merely short — there was no candidate
source at all, so section detection returned nothing no matter how good the
patterns were, and the report classes fell through to the legacy
``ChunkedDocument``.

Strategy 5c reads bare ``TextNode``s, using each node's first line as the header:
in a preformatted filing one TextNode carries both the heading and the body that
follows it, so the untrimmed text is a thousand characters of prose that
``_looks_like_section_header`` rejects on length alone.

This was the last thing keeping the legacy fallback load-bearing. Measured across
121 corpus fixtures, it was the only remaining behavioural difference between
``.items`` with the legacy path and without it.

Strategy 5c could only see a heading that STARTS a TextNode, so each filing
yielded Item 7 alone; every other heading sat mid-node. Since edgartools-llmp.12.1
the builder makes each blank-line block of preformatted text a paragraph, and
both filings yield their full item lists.

CORPUS NOTE. Both filings asserted here live in ``tests/fixtures/parity_gate``,
which is tracked, so this test runs in CI. The 10-K twin (``0000927356-01-000369``)
was copied there from the gitignored ``text_boundary_corpus`` on 2026-10-02: while
it lived only there its test skipped in CI, and a sibling test on that corpus went
stale for five days without anyone seeing it.
"""
import pathlib

import pytest

from edgar.company_reports.ten_k import TenK
from edgar.company_reports.twenty_f import TwentyF

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures"
TRACKED_20F = FIXTURES / "parity_gate" / "20-F" / "0000928385-01-500187.html"
TRACKED_10K = FIXTURES / "parity_gate" / "10-K" / "0000927356-01-000369.html"


class FixtureFiling:
    """The minimum surface the report classes touch, backed by a local file."""

    filing_date = None

    def __init__(self, path: pathlib.Path, form: str):
        self._path = path
        self.form = form
        self.company = "fixture"
        self.accession_number = path.stem
        self.base_dir = str(path.parent)

    def html(self):
        return self._path.read_text(encoding="utf-8", errors="replace")


def _without_legacy(cls):
    """A subclass whose legacy fallback is unavailable.

    Deliberately a throwaway subclass rather than patching and deleting the
    attribute on ``cls``: TenK, TenQ and CurrentReport each define
    ``_chunked_document`` on themselves, so ``del cls._chunked_document`` would
    destroy the real override instead of restoring it, and every later assertion
    in the session would silently measure a different object.
    """
    return type(
        f"NoLegacy{cls.__name__}",
        (cls,),
        {"_chunked_document": property(lambda self: None)},
    )


def test_the_tracked_fixture_is_present():
    """Absent is not passing — guard the fixture this test rests on."""
    assert TRACKED_20F.exists(), (
        f"{TRACKED_20F} is tracked and must be present; without it the "
        f"assertions below would vacuously skip"
    )


def test_2001_20f_finds_item_7_without_the_legacy_parser():
    filing = FixtureFiling(TRACKED_20F, "20-F")

    items = ["Item 1", "Item 2", "Item 3", "Item 4", "Item 5", "Item 6", "Item 7", "Item 8",
             "Item 9", "Item 10", "Item 11", "Item 12", "Item 13", "Item 14", "Item 16", "Item 18"]
    assert TwentyF(filing).items == items  # ["Item 7"] before llmp.12.1
    # The point of the fix: the same answer with the legacy path gone.
    assert TwentyF.__mro__ and _without_legacy(TwentyF)(filing).items == items


def test_the_20f_document_has_paragraphs_but_no_headings():
    """Pins the precondition, so a parser change that starts emitting headings
    here does not leave this test passing for a different reason.

    It had no ParagraphNode at all until llmp.12.1 split preformatted text at
    blank lines; it still has no HeadingNode, and no text node holds two items'
    headings, which is what kept every heading but Item 7 out of reach."""
    import re
    from edgar.documents.config import ParserConfig
    from edgar.documents.nodes import HeadingNode, ParagraphNode
    from edgar.documents.parser import HTMLParser

    doc = HTMLParser(ParserConfig(form="20-F", detect_sections=True)).parse(
        TRACKED_20F.read_text(encoding="utf-8", errors="replace")
    )
    nodes = list(doc.root.walk())
    assert not [n for n in nodes if isinstance(n, HeadingNode)]
    assert len([n for n in nodes if isinstance(n, ParagraphNode)]) > 1000
    heading = re.compile(r"^\s*Item\s+\d+", re.IGNORECASE | re.MULTILINE)
    assert not [n for n in nodes
                if type(n).__name__ == "TextNode" and len(heading.findall(n.text() or "")) > 1]


def test_2001_10k_finds_item_7_without_the_legacy_parser():
    filing = FixtureFiling(TRACKED_10K, "10-K")

    # Items 1 and 2 are titled "DESCRIPTION OF BUSINESS" and "DESCRIPTION OF
    # PROPERTY", which the 10-K title patterns do not match.
    items = ["Item 3", "Item 4", "Item 5", "Item 6", "Item 7", "Item 8", "Item 9",
             "Item 10", "Item 11", "Item 12", "Item 13", "Item 14"]
    assert TenK(filing).items == items  # ["Item 7"] before llmp.12.1
    assert _without_legacy(TenK)(filing).items == items
