"""A 10-Q whose Part II marker is a bold-child paragraph keeps its Part II
(edgartools-dt1f.1, Defect D).

Goldman's 10-Q renders "PART II. OTHER INFORMATION" as a ``ParagraphNode`` whose
own style carries no font weight and whose child ``TextNode`` is bold. Only
Strategy 3b in the section extractor catches that shape, and it was gated to
10-K and 8-K.

The consequence was larger than one missing marker. ``_detect_10q_parts`` labels
each header with the last PART header seen, so with no Part II boundary every
header after it was still "Part I" — and ``_match_sections`` rejects a
``part_ii_*`` pattern whose candidate sits in Part I. Items 5 and 6 were found
(both are plain ``HeadingNode``s: "Item 5. Other Information", "Item 6.
Exhibits") and then thrown away on part context. ``doc.sections`` came back as
``part_i_item_1..4`` and nothing else, so four lookups fell through to the
legacy parser: ``tenq["Item 5"]``, ``tenq["Item 6"]`` and both
``get_item_with_part("Part II", ...)`` calls.

WHY THE GATE IS NARROW. Strategy 3b now runs for 10-Q, but takes only PART
boundaries and the terminal bare SIGNATURES line — not the rest of the
``_looks_like_section_header`` vocabulary that 10-K and 8-K use. Admitting all
of it was tried and reverted: across 31 fixtures it truncated four other filings,
one MD&A from 33,102 characters to 93, and left Goldman's own Item 6 at 16. A
bold "Exhibits" or "Item 6." inside a 10-Q body is ordinarily a cross-reference;
a bold "PART II" or a bare bold "SIGNATURES" is not. `test_the_gate_stays_narrow`
below pins that distinction, because widening it is the obvious "improvement"
someone will reach for.

SIGNATURES earns its place for the reason 8-K needed it (edgartools-papt): it is
what stops the last item, Item 6 Exhibits, running to the end of the document.
Three other fixtures gained a correctly-bounded Item 6 from it, which is asserted
below rather than left as an unexplained diff.

CORPUS NOTE. ``tests/fixtures/html/`` is TRACKED — 58 files, the gs and xom 10-Qs
among them, committed in df4ada0d — so every assertion here runs in CI and none
of them is conditional. Only ``tests/fixtures/text_boundary_corpus/`` is
gitignored (.gitignore line 81); nothing in this file depends on it. The dt1f.1
bead describes ``tests/fixtures/html/`` as gitignored too, which is not the case
— worth knowing before deciding a 10-Q assertion has to be optional.
"""
import pathlib

import pytest

from edgar.company_reports.ten_q import TenQ
from edgar.documents.config import ParserConfig
from edgar.documents.extractors.pattern_section_extractor import (
    _PART_HEADER,
    _SIGNATURES_HEADER,
)
from edgar.documents.parser import HTMLParser

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures"
GS_10Q = FIXTURES / "html" / "gs" / "10q" / "gs-10-q-2025-08-01.html"
XOM_10Q = FIXTURES / "html" / "xom" / "10q" / "xom-10-q-2025-08-04.html"


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


def _without_any_fallback(cls):
    """A subclass with BOTH of the stacked fallbacks unreachable.

    ``get_item_with_part`` tries the new parser, then ``ChunkedDocument``, then
    ``id_parse_document`` — and 6.0 deletes both of the latter along with
    ``edgar.files``. Nulling only the first would let a lookup pass through the
    second and prove nothing, so ``id_parse_document`` raises instead of being
    silently available.

    A throwaway subclass rather than patching and deleting the attribute on
    ``cls``: TenK, TenQ and CurrentReport each define ``_chunked_document`` on
    themselves, so ``del`` would destroy the real override.
    """

    def _no_id_parse(self, markdown=True):
        raise AssertionError(
            "id_parse_document was reached — the new parser did not answer, and "
            "this lookup is not actually closed"
        )

    return type(
        f"NoFallback{cls.__name__}",
        (cls,),
        {
            "_chunked_document": property(lambda self: None),
            "id_parse_document": _no_id_parse,
        },
    )


def test_the_fixtures_are_present():
    """Absent is not passing. These are tracked, so this must never skip."""
    for path in (GS_10Q, XOM_10Q):
        assert path.exists(), f"{path} is tracked and must be present"


def test_the_part_ii_marker_really_has_the_awkward_shape():
    """Pin the precondition.

    If a future parser change starts emitting a HeadingNode here, Strategy 1
    would pick the marker up on its own and every assertion below would pass for
    a reason unrelated to this fix, leaving the defect unguarded.
    """
    from edgar.documents.nodes import ParagraphNode, TextNode

    doc = HTMLParser(ParserConfig(form="10-Q")).parse(
        GS_10Q.read_text(encoding="utf-8", errors="replace")
    )
    markers = [
        n for n in doc.root.walk()
        if isinstance(n, ParagraphNode)
        and (n.text() or "").strip() == "PART II. OTHER INFORMATION"
    ]
    assert len(markers) == 1
    marker = markers[0]

    # The paragraph itself is unstyled — this is why Strategy 3's _is_bold() misses it.
    assert marker.style.font_weight is None
    # ...and the weight lives on the child TextNode, which is Strategy 3b's shape.
    children = [c for c in marker.children if isinstance(c, TextNode)]
    assert [c.style.font_weight for c in children] == ["700"]


def test_gs_10q_resolves_its_part_ii_sections():
    """Four sections that did not exist at all before, with their boundaries.

    Character counts rather than `is not None`: the failure this area actually
    has is a section that starts or stops in the wrong place, which presence
    checks pass. Item 6 is the one to watch — at 1,188 it ends at the SIGNATURES
    line; without that boundary it ran on to 2,017 and swallowed the signature
    block.
    """
    doc = HTMLParser(ParserConfig(form="10-Q")).parse(
        GS_10Q.read_text(encoding="utf-8", errors="replace")
    )
    sections = doc.sections

    assert {k: len(v.text()) for k in ("part_ii_item_1", "part_ii_item_2",
                                       "part_ii_item_5", "part_ii_item_6")
            for v in [sections[k]]} == {
        "part_ii_item_1": 1222,
        # 1,976 before edgartools-3cis. This is the one Part II section with a
        # table in it (issuer purchases of equity securities), and it SHRANK by 96
        # characters because "$" and "526.80" merged into "$526.80", deleting the
        # affix column and its padding. The "$" CHARACTER count is unchanged at 8,
        # all 21 numbers are still present in order, and the first and last 60
        # characters are byte-identical. The other three Part II sections are pure
        # prose and are untouched.
        "part_ii_item_2": 1880,
        "part_ii_item_5": 535,
        "part_ii_item_6": 1188,
    }

    # Part I is untouched — the fix adds a boundary, it does not move one.
    #
    # These two counts have moved twice for table-rendering work, in OPPOSITE
    # directions, which is why neither is asserted on its size alone.
    #
    # edgartools-kq2q (the 8-column cap) grew both: these sections carry GS's
    # financial statements and their wide tables were rendering without columns the
    # cap had discarded.
    #
    # edgartools-3cis then SHRANK part_i_item_1, from 632,360 to 627,444. Merging an
    # affix column into its figure deletes a whole column and its padding: "100" and
    # a lone "%" two columns over become "100%". 263 standalone "$" tokens and 109
    # "%" merge that way here. A section getting SMALLER is the shape of content
    # loss, so it was checked rather than assumed:
    #   - the "$" character count is unchanged at 2,217 and "%" rises 259 -> 741,
    #     so no marker was dropped, they moved;
    #   - every number in the old text is still present IN ORDER, with 2 added;
    #   - the first and last 80 characters are byte-identical, so no boundary moved;
    #   - part_ii_item_1 and part_ii_item_6 are byte-identical, as prose should be.
    assert len(sections["part_i_item_1"].text()) == 627444
    assert len(sections["part_i_item_2"].text()) == 397582

    assert sections["part_ii_item_1"].text().startswith("Item 1. Legal Proceedings")
    assert sections["part_ii_item_6"].text().startswith("Item 6. Exhibits")
    # The signature block is on the far side of the boundary, not inside Item 6.
    assert "Chief Accounting Officer" not in sections["part_ii_item_6"].text()


def test_gs_10q_lookups_answer_without_any_legacy_fallback():
    """The four lookups on the dt1f.1 work list, with both fallbacks removed.

    Legacy returned 484 / 1194 / 1222 / 1192 for these. Two of the four are
    `get_item_with_part`, which is the method the bead calls out as having no
    working path at all once `edgar.files` goes: its second fallback,
    `id_parse_document`, returns 0 characters for Part II Item 6 here.
    """
    report = _without_any_fallback(TenQ)(FixtureFiling(GS_10Q, "10-Q"))

    assert len(report["Item 5"]) == 535
    assert len(report["Item 6"]) == 1188
    assert len(report.get_item_with_part("Part II", "Item 1")) == 1222
    assert len(report.get_item_with_part("Part II", "Item 6")) == 1188

    # Part I still answers from the new parser too — get_item_with_part must not
    # have started depending on the Part II marker to resolve anything.
    # Count re-pinned for edgartools-kq2q and again for -3cis; see the note in the
    # test above for why this number went up and then back down.
    assert len(report.get_item_with_part("Part I", "Item 1")) == 627444


def test_signatures_bounds_the_last_item_on_other_filings_too():
    """The SIGNATURES half of the fix, on a filing that already had its Part II.

    ExxonMobil's Item 6 ran to 1,794 characters and ended inside the signature
    block; it now ends at the exhibit list's footnotes. Asserted rather than left
    as an unexplained diff, because it is a behaviour change on a filing this
    bead was not about.
    """
    doc = HTMLParser(ParserConfig(form="10-Q")).parse(
        XOM_10Q.read_text(encoding="utf-8", errors="replace")
    )
    item_6 = doc.sections["part_ii_item_6"].text()

    assert len(item_6) == 1221
    assert item_6.rstrip().endswith("** Furnished herewith.")


def test_the_gate_stays_narrow():
    """10-Q takes PART and bare SIGNATURES from Strategy 3b, and nothing else.

    Widening this to the full `_looks_like_section_header` vocabulary is the
    obvious next "improvement" and it is measurably wrong — see the module
    docstring. These are the two patterns that encode the distinction.
    """
    assert _PART_HEADER.match("PART II. OTHER INFORMATION")
    assert _PART_HEADER.match("  Part I - Financial Information")
    assert _SIGNATURES_HEADER.match("SIGNATURES")
    assert _SIGNATURES_HEADER.match("  Signature  ")

    # A word that merely begins with "part" is not a part boundary.
    assert not _PART_HEADER.match("Participants in the plan may elect")
    assert not _PART_HEADER.match("Partial redemption of the notes")
    # Prose that begins with the word "Signatures" is not the signature block.
    assert not _SIGNATURES_HEADER.match(
        "Signatures of the undersigned officers appear below"
    )
    # The vocabulary 10-K keeps and 10-Q must not take.
    for excluded in ("Item 6. Exhibits", "Exhibits", "Risk Factors",
                     "FINANCIAL STATEMENTS"):
        assert not _PART_HEADER.match(excluded)
        assert not _SIGNATURES_HEADER.match(excluded)
