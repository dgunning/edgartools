"""``get_item_with_part`` answers from the modern parser (edgartools-yrrh).

This method had THREE paths and the last two both live in ``edgar.files``, which
6.0 deletes:

    1. the modern parser's ``sections[f'{part_prefix}_item_{num}']``
    2. ``self._chunked_document.get_item_with_part(...)``
    3. ``self.id_parse_document(...)``  (edgar/files/html_documents_id_parser.py)

So when path 1 missed there was no correct answer available after 6.0 — and path
3 is not a degraded path 2, it is actively wrong: it returned 222,536 characters
for pg/10q "Part II, Item 1", a section of under a thousand. Two filings reached
it, for two unrelated reasons.

WHY THE HARNESS BELOW NULLS BOTH FALLBACKS. Nulling ``_chunked_document`` alone
is not enough here and is actively misleading: the lookup then falls to
``id_parse_document`` and returns a plausible-looking 222,536 characters, which
reads as a pass to any assertion that only checks for text. ``_parser_only``
makes path 3 raise, so a test can tell "the parser answered" from "something
answered".

TWO DEFECTS, NOT ONE. They are in different subsystems and share no code.

xom/10q — Part I, Item 1 — THE STRATEGY GATE
    This filer writes six of its seven items as headings and puts ITEM 1.
    FINANCIAL STATEMENTS in a table. Strategy 4 of ``_find_section_headers`` is
    the one that reads item headers out of table cells, and it was gated on
    ``_item_structure_found`` — "have at least half this form's items turned
    up?". Six of seven satisfied that, so the gate was held closed by the very
    headers that could never contribute the missing one, and the only item that
    needed the table strategy was the one item it never ran for. The gate now
    asks whether the structure is COMPLETE, which is the right question for a
    strategy that can only add candidates.

pg/10q — Part II, Item 1 — AN ITEM NUMBER IS ONLY UNIQUE WITHIN ITS PART
    TOC detection succeeds here and returns eight sections, without Part II's
    Item 1. The augmentation that exists to add exactly that — items the TOC
    omitted, found by the pattern extractor — compared bare item numbers on both
    sides of two tests. A 10-Q has two Item 1s, Financial Statements in Part I
    and Legal Proceedings in Part II, so the TOC having named one was read as
    having named both:

      * the completeness gate found the two sets exactly equal, concluded "the
        TOC named everything the form defines", and never ran the pattern pass
      * the merge filter would have dropped the section anyway, as a duplicate
        of an item the TOC already had

    Both now compare ``(part, item)`` pairs. The 10-K dedup that item-keying was
    introduced for is unaffected, because 10-K pattern sections carry a part too
    — ``mda`` is part 'II' item '7', the same pair as ``part_ii_item_7`` — so
    they still collide and no duplicate spans return.

BLAST RADIUS, measured across every fixture available on 2026-08-22 by dumping
{section: len(text)} for all four item-based forms before and after: four
fixtures change and EVERY CHANGE IS AN ADDITION — no section shrank, moved or
was re-cut.

    10-Q  xom/10q                 part_i_item_1     None -> 138,607
    10-Q  pg/10q                  part_ii_item_1    None ->     975
    10-K  pg/10k                  part_ii_item_5    None ->   5,329  (legacy 5,339)
                                  part_iii_item_10  None ->   1,005  (legacy 1,004)
                                  part_iv_item_15   None ->  13,512
    10-K  0001047469-03-011363    part_iv_item_15   None -> 238,740

The 10-K additions are the part-aware gate working on that form too: those items
were missing outright, and the two with a close legacy counterpart agree with it
to within ten characters. 20-F and 8-K are unchanged (15 fixtures each).

FIXTURE NOTE. Both filings live in ``tests/fixtures/html``, which is TRACKED —
unlike the era corpus — so these assertions run in CI.
"""
import pathlib

import pytest

from edgar.company_reports.ten_q import TenQ

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures"


def _fixture(ticker: str) -> pathlib.Path:
    matches = sorted((FIXTURES / "html" / ticker / "10q").glob("*.html"))
    assert matches, f"no 10-Q fixture for {ticker}"
    return matches[0]


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


def _parser_only(cls):
    """A subclass where BOTH ``edgar.files`` paths are unavailable.

    A throwaway subclass rather than patching and deleting on ``cls``: TenQ
    defines ``_chunked_document`` on itself, so ``del`` would destroy the real
    override and every later assertion would measure a different object.

    ``id_parse_document`` raises rather than returning None, so that reaching it
    is a loud failure. It is the path that produced the 222,536-character answer,
    and a silent None here would be indistinguishable from a section that is
    genuinely absent.
    """
    def _no_id_parse(self, markdown: bool = True):
        raise AssertionError(
            "id_parse_document was reached — the modern parser did not answer, "
            "and this path is deleted in 6.0"
        )

    return type(
        f"ParserOnly{cls.__name__}",
        (cls,),
        {
            "_chunked_document": property(lambda self: None),
            "id_parse_document": _no_id_parse,
        },
    )


@pytest.mark.parametrize(
    "ticker,part,item,expected",
    [
        # The two rows this bead was filed for.
        # 138,607 before the fast_table 8-column cap was removed (edgartools-kq2q).
        # XOM's Item 1 is financial statements; the segment tables were rendering
        # without the columns the cap discarded. Verified non-lossy at the word
        # level: ZERO tokens lost, 570 gained, all of them column headers
        # ("Non-U.S.", "Total", "Segment", "Products"), and the section's first and
        # last 80 characters are unchanged, so the boundaries did not move.
        # 167,042 after kq2q, 170,430 after y0ri/3cis. The second move is again a
        # pure gain: ZERO tokens lost, 30 gained, all of them recovered label cells
        # ("Level", "Effect", "Counterparty"), with every number still in order.
        ("xom", "Part I", "Item 1", 170430),
        ("pg", "Part II", "Item 1", 975),
        # And the two that closed earlier with the 10-Q Part II boundary fix
        # (dt1f.1 Defect D), kept here so the whole method is covered by one
        # table rather than one filing's worth of it.
        ("gs", "Part II", "Item 1", 1222),
        ("gs", "Part II", "Item 6", 1188),
    ],
)
def test_get_item_with_part_answers_from_the_modern_parser(ticker, part, item, expected):
    path = _fixture(ticker)
    text = _parser_only(TenQ)(FixtureFiling(path, "10-Q")).get_item_with_part(part, item)

    assert text is not None, f"{ticker} {part} {item} returned None"
    assert len(text) == expected


def test_the_two_item_ones_are_different_sections():
    """The 10-Q collision, asserted as behaviour rather than as a count.

    Part I's Item 1 is Financial Statements and Part II's is Legal Proceedings.
    An item-only comparison anywhere in the pipeline makes one of them shadow the
    other, which is what happened on pg, so this pins that both resolve and that
    they are not the same text.
    """
    report = _parser_only(TenQ)(FixtureFiling(_fixture("pg"), "10-Q"))

    part_i = report.get_item_with_part("Part I", "Item 1")
    part_ii = report.get_item_with_part("Part II", "Item 1")

    assert part_i != part_ii
    assert len(part_i) == 41077
    assert len(part_ii) == 975
    assert "Legal Proceedings" in part_ii or "legal proceedings" in part_ii.lower()


def test_xom_part_i_item_1_is_the_financial_statements():
    """The table-cell header the strategy gate used to skip.

    Asserted on content as well as length: the span has to start at the item
    header, not at whatever the table happened to contain.
    """
    report = _parser_only(TenQ)(FixtureFiling(_fixture("xom"), "10-Q"))

    text = report.get_item_with_part("Part I", "Item 1")
    assert text.startswith("ITEM 1. FINANCIAL STATEMENTS")
    assert "CONDENSED CONSOLIDATED STATEMENT OF INCOME" in text
    # Legacy returned 198,191 characters over this same span — it renders tables
    # as markdown, which the parser's .text() does not, so the lengths differ
    # while the boundaries agree. Both end on the same sentence.
    assert "other smaller divestments" in text[-400:]
