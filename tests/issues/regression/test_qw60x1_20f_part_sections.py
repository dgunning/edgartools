"""
Regression test for edgartools-qw60x.1: a 20-F Part section held only its own
divider line ('PART II', 7 chars) instead of the items under it.

Two defects, one per layer:

* ``SectionExtractor._find_section_end`` closed a section at the next header of
  the same or a higher level. A Part divider and its first item header often
  score the same level, so the Part ended at its first item. A Part now ends at
  the next Part divider (or SIGNATURES), never by level.
* ``HybridSectionDetector`` checked boundaries and duplicates over one flat list.
  Once a Part held its items, it overlapped them: the boundary pass cut the Part
  at its first item and the duplicate pass grouped the Part with the items it
  contains and kept one, so 0001144204-10-017467 lost item_3, item_4, item_19
  and all three Parts. Parts and items are now validated as separate layers.

Across the 128-filing parser corpus the change moved 26 Part sections on 9
20-Fs, and moved, added or removed nothing else. The three filings below are
tracked under tests/fixtures/parity_gate/20-F/; values read from the filings.
"""

import re

import pytest

from edgar.documents import HTMLParser, ParserConfig
from tests.paths import FIXTURES_DIR

GATE_20F = FIXTURES_DIR / "parity_gate" / "20-F"


def _sections(accession):
    html = (GATE_20F / f"{accession}.html").read_text(encoding="utf-8", errors="replace")
    return HTMLParser(ParserConfig(form="20-F", detect_sections=True)).parse(html).sections


def _flat(section):
    return " ".join(section.text().split())


@pytest.fixture(scope="module")
def flat_keys():
    # Items keyed item_N; the filing that lost items to the duplicate pass.
    return _sections("0001144204-10-017467")


@pytest.fixture(scope="module")
def flat_keys_2016():
    return _sections("0001062993-16-008650")


@pytest.fixture(scope="module")
def part_qualified():
    # Items keyed part_ii_item_N.
    return _sections("0001062993-21-003193")


@pytest.mark.parametrize("key, opening, closing", [
    ("part_i", "PART I ITEM 1. IDENTITY OF DIRECTORS, SENIOR MANAGEMENT AND ADVISERS",
     "OF SECURITIES OTHER THAN EQUITY SECURITIES ───────────────────────────────────────────── Not applicable."),
    ("part_ii", "PART II ITEM DEFAULTS, 13. DIVIDEND ARREARAGES AND DELINQUENCIES",
     "free of charge to shareholders upon request."),
    ("part_iii", "PART III ITEM 17. FINANCIAL STATEMENTS We have elected to provide financial statements",
     "incorporated by reference into any filing under the Securities Act or the Exchange Act."),
])
def test_part_spans_its_items(flat_keys, key, opening, closing):
    text = _flat(flat_keys[key])
    assert text.startswith(opening), text[:120]
    assert text.endswith(closing), text[-160:]


def test_part_holds_one_divider(flat_keys):
    # Each Part stops at the next divider rather than running through it.
    for key, label in (("part_i", "PART I"), ("part_ii", "PART II"), ("part_iii", "PART III")):
        assert re.findall(r"\bPART I+\b", _flat(flat_keys[key])) == [label]


def test_items_inside_a_part_survive(flat_keys):
    # Lost to the duplicate pass when the Parts first spanned their items.
    for key in ("item_3", "item_4", "item_15", "item_19"):
        assert key in flat_keys, f"{key} missing; got {sorted(flat_keys)}"
    assert _flat(flat_keys["item_19"]).startswith("ITEM 19. EXHIBITS")
    assert len(flat_keys) == 29


def test_parts_on_the_2016_filing(flat_keys_2016):
    part_ii = _flat(flat_keys_2016["part_ii"])
    assert part_ii.startswith("PART II Item 13. Defaults, Dividend Arrearages and Delinquencies.")
    assert part_ii.endswith("Item 16. H. H. Mine Safety ─────────────────────────────────── Not applicable.")
    part_iii = _flat(flat_keys_2016["part_iii"])
    assert part_iii.startswith("PART III Item 17. Financial Statements")
    assert part_iii.endswith("current report on Form 6-K filed with the SEC on July 13, 2012.")
    assert "item_16h" in flat_keys_2016


def test_parts_with_part_qualified_items(part_qualified):
    part_i = _flat(part_qualified["part_i"])
    assert part_i.startswith("PART I ITEM 1. IDENTITY OF DIRECTORS, SENIOR MANAGEMENT AND ADVISORS")
    assert part_i.endswith("Not applicable to Form 20-F filed as an Annual Report.")
    assert "PART II" not in part_i
    assert _flat(part_qualified["part_ii"]).startswith("PART II ITEM 13. DEFAULTS, DIVIDEND ARREARAGES")
    assert _flat(part_qualified["part_iii"]).endswith("Letter from Manning Elliott LLP per Item 16F ** Filed herewith.")
