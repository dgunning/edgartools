"""A 10-Q's two Item 1s are not the same item (edgartools-xhmd).

The section size guardrail flags a section whose extracted length falls outside
the band expected for its item, warns, and drops its confidence to 0.5. The
bands were keyed on the bare item number, which is not a key on a 10-Q: Part I's
Item 1 is Financial Statements (~90,000 chars) and Part II's is Legal
Proceedings (a few hundred, often a pointer into Part I's notes). Part II was
therefore judged against Part I's floor of 18,009 and told it was truncated.

It was not a rare misfire. Across the 115-fixture corpus of the four item-based
forms, 65 sections carried a size warning and 38 of them — 58% — were 10-Q Part
II Items 1 and 2, every one a correct extraction of a legitimately short item.
A guardrail that is wrong more often than right teaches callers to ignore it,
which costs more than having no guardrail at all: the GS/Citi silent-wrong-
content class it exists to catch is exactly what gets ignored with it.

WHAT CHANGED. A band may now be written Part-qualified — ``"II:6"`` — and
matches only in that Part; a bare key still matches in any Part, which is right
for a 10-K, whose item numbers are unique across parts. The 10-Q's three bands
become ``I:1`` (Financial Statements), ``I:2`` (MD&A) and ``II:6`` (Exhibits),
with the values unchanged: they were Part I's measurements all along, since the
corpus derivation collapsed both Item 1s into one bucket by keeping the larger.

Part II's Items 1 and 2 are left unenforced rather than given a band of their
own. They are legitimately high-variance — 74 chars at Tesla, 12,718 at
Coca-Cola — and no floor can separate "the filer said nothing" from "the anchor
missed the body". Nothing is lost by not enforcing them: a Part II over-capture
runs to tens of KB and never reached Part I's ceiling of 720,376 either. The
corpus cannot express a per-Part band today; edgartools-d64d regenerates it.

ALSO FIXED, because a warning must be reproducible: the char count in the
message came from ``end_offset`` while the caller reads ``section.text()``, and
the two differ by a few characters (nflx's 10-Q Item 1: 227 vs 223). A flagged
section is now re-measured on the text the caller will actually see, and only
sections the offset proxy already flagged pay for that extraction.

BLAST RADIUS, measured across all 115 fixtures of 10-K, 10-Q, 8-K and 20-F by
dumping {section: (len, confidence, warnings)} before and after:

    65 -> 27 flagged sections; 38 warnings removed, NONE added
    those 38 sections' confidence: 0.5 -> 0.95
    25 surviving warnings changed text only — the Part label, and the
    reconciled char count on six of them
    no section's boundaries or length changed
"""
import pathlib
import re

import pytest

from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.section_size_bands import band_for, evaluate_size

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures" / "html"


def _sections(rel: str, form: str):
    html = (FIXTURES / rel).read_text(encoding="utf-8", errors="replace")
    return HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(html).sections


# ---------------------------------------------------------------------------
# Unit: the band lookup
# ---------------------------------------------------------------------------

def test_ten_q_item_1_band_belongs_to_part_i():
    assert band_for("10-Q", "1", part="I") == {"low": 18_009, "high": 720_376}
    # Part II's Item 1 is a different item and is not enforced.
    assert band_for("10-Q", "1", part="II") is None
    assert band_for("10-Q", "2", part="II") is None
    # Part II's Exhibits has no twin in Part I and keeps its band.
    assert band_for("10-Q", "6", part="II") == {"low": 518, "high": 20_720}
    assert band_for("10-Q", "6", part="I") is None


def test_a_caller_without_part_context_gets_no_ten_q_band():
    """Silence beats guessing: with no Part, either Item 1 is possible."""
    assert band_for("10-Q", "1") is None
    assert evaluate_size("10-Q", "1", 500) is None


def test_ten_k_bands_are_unchanged_by_the_part_key():
    """10-K item numbers are unique across parts, so its bands stay bare and
    match with or without a Part — this fix must not touch that form."""
    assert band_for("10-K", "1") == {"low": 8_034, "high": 321_384}
    assert band_for("10-K", "1", part="I") == {"low": 8_034, "high": 321_384}
    assert band_for("10-K", "8", part="II") == {"low": 26_136, "high": 1_045_472}


@pytest.mark.parametrize("part,expected", [("I", "Part I"), ("Part II", "Part II")])
def test_the_warning_names_the_part(part, expected):
    """"Item 1 content is …" is ambiguous on a 10-Q; the Part disambiguates it."""
    warning = evaluate_size("10-K", "8", 250, part=part)
    assert warning.startswith(f"{expected} Item 8 content is 250 chars")


# ---------------------------------------------------------------------------
# Integration: the filings that were being flagged
# ---------------------------------------------------------------------------

# (fixture, Part II Item 1 length, Part II Item 2 length) — hand-checked against
# the filings: each is a complete, correctly-extracted section.
TEN_Q_GROUND_TRUTH = [
    ("aapl/10q/aapl-10-q-2025-08-01.html", 5_534, 1_475),   # real litigation prose
    ("ibm/10q/ibm-10-q-2025-07-24.html", 80, 1_302),        # a one-line pointer
    ("ko/10q/ko-10-q-2025-07-24.html", 12_718, 1_652),      # the corpus maximum
    ("tsla/10q/tsla-10-q-2025-07-24.html", 237, 74),        # the corpus minimum
]


@pytest.mark.parametrize("rel,len_item_1,len_item_2", TEN_Q_GROUND_TRUTH)
def test_ten_q_part_ii_items_are_not_judged_by_part_i_bands(rel, len_item_1, len_item_2):
    sections = _sections(rel, "10-Q")

    for key, expected in (("part_ii_item_1", len_item_1), ("part_ii_item_2", len_item_2)):
        section = sections[key]
        assert len(section.text()) == expected, f"{key} length drifted from ground truth"
        assert not section.warnings, f"{key} flagged: {section.warnings}"
        assert section.confidence == 0.95, f"{key} confidence reduced to {section.confidence}"


@pytest.mark.parametrize("rel,expected", [
    ("aapl/10q/aapl-10-q-2025-08-01.html", 24_903),
    ("ibm/10q/ibm-10-q-2025-07-24.html", 115_487),
    ("ko/10q/ko-10-q-2025-07-24.html", 100_831),
    ("tsla/10q/tsla-10-q-2025-07-24.html", 63_949),
])
def test_part_i_item_1_is_still_enforced(rel, expected):
    """The guardrail still guards: these are healthy and in-band, and a Part I
    Item 1 that fell to a few hundred chars would still be flagged."""
    section = _sections(rel, "10-Q")["part_i_item_1"]

    assert len(section.text()) == expected
    assert not section.warnings
    assert evaluate_size("10-Q", "1", 1_903, part="I") is not None


def test_a_flagged_section_reports_the_length_the_caller_reads():
    """The nit that made the warnings unassertable: the message quoted
    ``end_offset`` while the caller reads ``section.text()``."""
    sections = _sections("ibm/10k/ibm-10-k-2025-02-25.html", "10-K")

    flagged = {k: s for k, s in sections.items() if s.warnings}
    assert flagged, "IBM's 10-K should still flag its incorporated-by-reference items"
    for key, section in flagged.items():
        match = re.search(r"content is ([\d,]+) chars", section.warnings[0])
        assert match, f"{key}: warning has no char count — {section.warnings[0]!r}"
        assert int(match.group(1).replace(",", "")) == len(section.text()), key

    # And it still says which item, now with its Part.
    assert sections["part_ii_item_8"].warnings[0].startswith("Part II Item 8 content is 250 chars")
