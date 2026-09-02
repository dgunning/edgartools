"""Structural chunking — what `Filing.sections()` and `Filing.search()` stand on.

Bead: edgartools-07lk.3 leg C. `Filing.sections()` used to call
`edgar.files.htmltools.html_sections`, whose `HtmlDocument` backend 6.0 deletes.
It is public, and it backs `Filing.search()` through `BM25Search` and
`RegexSearch`, so it needed a replacement rather than a deprecation — there was
nothing to deprecate it toward.

HOW THE REPLACEMENT WAS GATED, so the numbers below can be re-derived rather
than believed. Two measurements over 41 era-stratified fixtures (1996-2026,
10-K / 10-Q / 20-F / 8-K), legacy chunker as the reference because that is what
users' searches have been hitting:

  1. COVERAGE, compared as WORD MULTISETS rather than lengths. Two chunkers can
     agree on total characters while one dropped a table and the other doubled a
     heading. Result: 1,295 of 1,339,255 word occurrences lost, 0.10%. Among the
     most-lost words are `jurisdictionof`, `commissionfile` and
     `employeridentification` — legacy's own glued words, which the new parser
     separates correctly, so the real loss is smaller than 0.10%.

  2. RECALL, because coverage alone is satisfied by one chunk containing the
     whole document. 25 distinctive six-word phrases per filing, drawn from the
     LEGACY chunks so every query is one the old index could answer, run through
     the same BM25 index `Filing.search()` builds:

         chunker        mean R@1   mean R@5
         legacy             92.2       99.2
         new, no cap        89.5       99.2
         new, cap 3000      91.8       99.2

The middle row is why `max_chars` exists: without a cap a filing whose markup
the parser labels few headings in produces chunks tens of thousands of
characters long, which BM25 both dilutes and hides distinct passages inside. The
cap is a search-quality parameter, not tidiness.

TWO BUGS THIS FILE WAS WRITTEN AFTER, both of which produced plausible numbers:

  * The walk filtered to HEADING/PARAGRAPH/LIST/TABLE, and pre-2009 filings
    parse to bare TEXT nodes and nothing else — so every one of them chunked to
    the empty list. Corpus word loss read 28.01%, which looks like a tuning
    problem rather than a third of the fixtures returning nothing.
  * The walk then stopped at paragraphs, but the parser nests headings INSIDE
    paragraphs — all 71 headings of the 1999 fixture are children of a
    ParagraphNode — so no heading cut ever fired and the chunker was running on
    its size cap alone. Chunk counts and recall both looked fine; only counting
    chunks that carry a heading exposed it.
"""
import pathlib
import re

import pytest

from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.extractors.chunk_extractor import (
    ChunkExtractor,
    StructuralChunker,
    chunk_html,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
# Tracked fixtures. The era corpus this was measured on is gitignored, and
# anchoring only on that would make this file skip in CI while passing locally.
MODERN_10K = FIXTURES / "parity_gate" / "10-K" / "0001376474-16-000635.html"
ARCHAIC_10K = FIXTURES / "parity_gate" / "10-K" / "0000950153-99-001234.html"

WORD = re.compile(r"[A-Za-z][A-Za-z'\-]+")

# Fixture-backed end to end: no filing is fetched, and this was confirmed by
# running the file under `tests._offline_harness` (sockets blocked, edgar caches
# cleared per test) rather than by reading the filename.
pytestmark = pytest.mark.fast


def _doc(path, form="10-K"):
    return HTMLParser(ParserConfig(form=form)).parse(
        path.read_text(encoding="utf-8", errors="replace"))


# --------------------------------------------------------------------------
# The bare-TEXT era. This is the failure the first implementation shipped with.
# --------------------------------------------------------------------------

def test_pre_2009_filings_chunk_at_all():
    """Filings with no paragraph or heading markup must still chunk.

    The first version filtered the node walk to HEADING/PARAGRAPH/LIST/TABLE.
    Modern filings were fine. Pre-2009 filings parse to bare TEXT nodes and
    nothing else — a 2001 10-K gives 23 TEXT nodes, 22 tables, zero headings and
    zero paragraphs — so every one of them chunked to the EMPTY LIST, and
    `filing.search()` on a 1999 filing would have returned nothing at all while
    every test on a modern fixture passed.

    Coverage measured as a percentage hid this: the corpus average stayed
    respectable while a third of the fixtures were at 100% loss.
    """
    chunks = StructuralChunker().chunks(_doc(ARCHAIC_10K))
    assert len(chunks) > 20, "a 1999 10-K must produce real chunks, not an empty list"
    body = "\n".join(c.text for c in chunks)
    assert len(body) > 50_000


def test_archaic_filings_cut_on_real_headings():
    """The 1999 fixture's headings must actually reach the chunker."""
    chunks = StructuralChunker().chunks(_doc(ARCHAIC_10K))
    headings = [c.heading for c in chunks if c.heading]
    assert len(headings) > 50, (
        "headings nested inside paragraphs are invisible to a walk that stops at "
        "paragraphs; when that happened every chunk carried heading=None"
    )
    assert any(re.match(r"(?i)item\s+\d", h) for h in headings), headings[:10]


# --------------------------------------------------------------------------
# Shape
# --------------------------------------------------------------------------

def test_no_chunk_swallows_the_document():
    """The cap holds, so BM25 scores passages rather than whole Items."""
    for path in (MODERN_10K, ARCHAIC_10K):
        chunks = StructuralChunker(max_chars=3000).chunks(_doc(path))
        prose = [c for c in chunks if c.kind == "text"]
        assert prose, path.name
        # Prose is cut at the next paragraph boundary AFTER the cap, so a single
        # very long paragraph legitimately overshoots; nothing should approach
        # the 76k chunks the uncapped version produced.
        assert max(len(c) for c in prose) < 40_000, path.name


def test_tables_are_their_own_chunks_and_render_as_tables():
    """`SearchResults` decides to draw a result as a table by testing
    `doc.startswith("|  |")`. A table chunk that does not start that way renders
    as a wall of pipes, so the prefix is a display contract, not cosmetics."""
    chunks = StructuralChunker().chunks(_doc(MODERN_10K))
    tables = [c for c in chunks if c.kind == "table"]
    assert len(tables) > 10
    assert all(t.text.startswith("|  |") or "\n|  |" in t.text for t in tables)


def test_uncapped_chunking_is_still_reachable():
    """`max_chars=0` disables the cap — the shape the sweep measured at 86.2 R@1.
    Kept because retrieval callers may want whole sections."""
    capped = StructuralChunker(max_chars=3000).chunks(_doc(MODERN_10K))
    uncapped = StructuralChunker(max_chars=0).chunks(_doc(MODERN_10K))
    assert len(uncapped) < len(capped)


# --------------------------------------------------------------------------
# Coverage against the legacy chunker, while it still exists to compare against
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", [MODERN_10K, ARCHAIC_10K], ids=["2016", "1999"])
def test_indexes_the_same_words_as_the_legacy_chunker(path):
    """Word multisets, not lengths — see the module docstring."""
    from edgar.files.htmltools import html_sections

    html = path.read_text(encoding="utf-8", errors="replace")
    legacy = collections_counter(html_sections(html))
    new = collections_counter(chunk_html(html, form="10-K"))

    lost = legacy - new
    lost_n, total = sum(lost.values()), sum(legacy.values())
    assert total > 10_000, "fixture is too small to say anything"
    assert lost_n / total < 0.01, (
        f"{lost_n}/{total} word occurrences lost; most common: {lost.most_common(10)}"
    )


def collections_counter(chunks):
    import collections
    c = collections.Counter()
    for chunk in chunks:
        c.update(w.lower() for w in WORD.findall(chunk or ""))
    return c


# --------------------------------------------------------------------------
# Document.chunks() — the public method that never worked
# --------------------------------------------------------------------------

def test_document_chunks_returns_chunks():
    """`Document.chunks()` imported `edgar.documents.extractors.chunk_extractor`,
    a module that was never written, so this public retrieval API raised
    `ModuleNotFoundError` for every caller since the parser rewrite
    (bead edgartools-vwtb)."""
    chunks = list(_doc(MODERN_10K).chunks(chunk_size=256, overlap=64))
    assert chunks
    assert all(c.content.strip() for c in chunks)
    assert all(c.token_count > 0 for c in chunks)


def test_token_budget_is_respected():
    chunks = list(_doc(MODERN_10K).chunks(chunk_size=200, overlap=50))
    assert max(len(c.content.split()) for c in chunks) <= 200


def test_overlap_must_advance_the_window():
    """`overlap >= chunk_size` advances by zero and loops forever on any chunk
    over the budget. It raises rather than hanging.

    `ValidationError` rather than a raw `ValueError`: it IS-A `ValueError`, so
    nothing that catches the plain one breaks, and it carries the `parameter`
    and `suggestions` the caller needs. The raw-`ValueError` ratchet in
    tests/issues/regression/ enforces this, and it caught these two.
    """
    from edgar.exceptions import ValidationError

    with pytest.raises(ValidationError) as exc:
        ChunkExtractor(chunk_size=100, overlap=100)
    assert exc.value.parameter == "overlap"
    assert exc.value.suggestions

    with pytest.raises(ValidationError):
        ChunkExtractor(chunk_size=100, overlap=150)
    with pytest.raises(ValidationError):
        ChunkExtractor(chunk_size=0)

    # Still a ValueError to anyone catching the old shape.
    assert issubclass(ValidationError, ValueError)


# --------------------------------------------------------------------------
# Failure behaviour
# --------------------------------------------------------------------------

def test_unparseable_html_searches_as_empty_rather_than_raising():
    assert chunk_html("") == []
    assert chunk_html(None) == []
