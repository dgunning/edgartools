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

CORPUS NOTE. The 20-F asserted here lives in ``tests/fixtures/parity_gate``, which
is tracked, so this test runs in CI. Its 10-K twin (``0000927356-01-000369``) is
in ``tests/fixtures/text_boundary_corpus``, which is gitignored — asserting on
that one alone would make this test skip in CI while passing locally, which is how
parity evidence was lost before. It is checked opportunistically below.
"""
import pathlib

import pytest

from edgar.company_reports.ten_k import TenK
from edgar.company_reports.twenty_f import TwentyF

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures"
TRACKED_20F = FIXTURES / "parity_gate" / "20-F" / "0000928385-01-500187.html"
IGNORED_10K = (FIXTURES / "text_boundary_corpus" / "e1_1996_2001" / "10-K"
               / "0000927356-01-000369.html")


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

    assert TwentyF(filing).items == ["Item 7"]
    # The point of the fix: the same answer with the legacy path gone.
    assert TwentyF.__mro__ and _without_legacy(TwentyF)(filing).items == ["Item 7"]


def test_the_20f_document_really_has_no_block_structure():
    """Pins the precondition, so a parser change that starts emitting headings
    here does not leave this test passing for a different reason."""
    from edgar.documents.config import ParserConfig
    from edgar.documents.nodes import HeadingNode, ParagraphNode
    from edgar.documents.parser import HTMLParser

    doc = HTMLParser(ParserConfig(form="20-F", detect_sections=True)).parse(
        TRACKED_20F.read_text(encoding="utf-8", errors="replace")
    )
    nodes = list(doc.root.walk())
    assert not [n for n in nodes if isinstance(n, HeadingNode)]
    assert not [n for n in nodes if isinstance(n, ParagraphNode)]


@pytest.mark.skipif(
    not IGNORED_10K.exists(),
    reason="text_boundary_corpus is gitignored; present on developer machines only",
)
def test_2001_10k_finds_item_7_without_the_legacy_parser():
    filing = FixtureFiling(IGNORED_10K, "10-K")

    assert TenK(filing).items == ["Item 7"]
    assert _without_legacy(TenK)(filing).items == ["Item 7"]
