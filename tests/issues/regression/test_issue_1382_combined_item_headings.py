"""Regression: two items filed under one heading keep both items (GH #1382, #1383).

GitHub Issues: https://github.com/dgunning/edgartools/issues/1382
               https://github.com/dgunning/edgartools/issues/1383
Bead: edgartools-644g

Energy filers combine items under one heading: "Items 1 and 2. Business and
Properties", "Items 1. and 2.", "Items&#160;1. and 2.", "Items 7. and 7A.".
When that heading is the TOC link text, every TOC parser rejected it: the item
label regex needs "Item" followed by whitespace, so the plural's "s" failed it,
and the row was dropped. Part I then started at Item 1A, ``tenk.business`` was
None and the Business and Properties text sat in no section (Viper and Devon
regressed in 5.29.0 / 5.34.0; the #710 test injected ready-made keys and never
ran detection). Freeport's "Items 7. and 7A." kept Item 7 and lost 7A.

On Talos the TOC puts "Items 1 and 2." and the link in separate cells, so Item 1
survived, but Item 2 looked missing and the pattern pass admitted a bare
"Properties" sub-heading from inside Item 1 as a 1,311-character Item 2 (#1383).

The fix reads a combined label as its first item and records both on
``Section.covered_items`` from the section's own heading; ``TenK`` resolves the
second item to that section and the pattern pass counts it as found.

Offline (local fixtures, parsed end to end):
  Viper Energy 10-K      0002074176-26-000010  tests/fixtures/html/vnom/10k/
  Cheniere Energy 10-K   0000003570-26-000005  tests/fixtures/html/lng/10k/
  Freeport-McMoRan 10-K  0000831259-25-000006  tests/fixtures/html/fcx/10k/
  Talos Energy 10-K      0001193125-26-067807  tests/fixtures/html/talo/10k/
"""
import pathlib

import pytest

from edgar.company_reports.ten_k import TenK
from edgar.documents.utils.toc_analyzer import TOCAnalyzer

FIXTURES = pathlib.Path(__file__).resolve().parents[2] / "fixtures" / "html"

VIPER = FIXTURES / "vnom" / "10k" / "vnom-10-k-2026-02-25.html"
CHENIERE = FIXTURES / "lng" / "10k" / "lng-10-k-2026-02-26.html"
FREEPORT = FIXTURES / "fcx" / "10k" / "fcx-10-k-2025-02-14.html"
TALOS = FIXTURES / "talo" / "10k" / "talo-10-k-2026-02-25.html"


class FixtureFiling:
    """The minimum surface TenK touches, backed by a local file."""

    filing_date = None
    form = "10-K"
    company = "fixture"

    def __init__(self, path: pathlib.Path):
        self._path = path
        self.accession_number = path.stem
        self.base_dir = str(path.parent)

    def html(self):
        return self._path.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module", params=[VIPER, CHENIERE, FREEPORT, TALOS], ids=lambda p: p.parts[-3])
def tenk(request):
    return TenK(FixtureFiling(request.param))


@pytest.mark.fast
def test_the_fixtures_are_present():
    """Absent is not passing."""
    for path in (VIPER, CHENIERE, FREEPORT, TALOS):
        assert path.exists(), path


@pytest.mark.fast
def test_combined_items_1_and_2_are_one_section(tenk):
    part_i = [key for key in tenk.sections if key.startswith("part_i_")]
    assert part_i[:2] == ["part_i_item_1", "part_i_item_1a"]

    section = tenk.sections["part_i_item_1"]
    assert section.covered_items == ("1", "2")
    assert section.detection_method == "toc"

    business = tenk.business
    assert business
    assert tenk["Item 2"] == business
    assert "Item 2" in tenk.items


@pytest.mark.fast
def test_business_opens_on_the_combined_heading():
    """Each variant of the heading resolves, including '1.' and a nbsp after 'Items'."""
    assert TenK(FixtureFiling(CHENIERE)).business.startswith("ITEMS 1. AND 2.\xa0\xa0\xa0\xa0BUSINESS AND PROPERTIES")
    assert TenK(FixtureFiling(FREEPORT)).business.startswith("Items 1. and 2. Business and Properties.")
    # Viper's TOC link lands on a preamble paragraph ahead of its heading
    viper = TenK(FixtureFiling(VIPER)).business
    assert viper.startswith("On November 13, 2023, Viper Energy Partners LP converted")
    assert "ITEMS 1 and 2.  BUSINESS AND PROPERTIES" in viper[:3000]


@pytest.mark.fast
def test_combined_items_7_and_7a_resolve_7a():
    """Freeport's 'Items 7. and 7A.' used to leave Item 7A unreachable."""
    freeport = TenK(FixtureFiling(FREEPORT))
    section = freeport.sections["part_ii_item_7"]
    assert section.covered_items == ("7", "7A")
    assert "part_ii_item_7a" not in freeport.sections
    assert freeport["Item 7A"] == freeport["Item 7"]
    # A running header precedes the heading
    assert freeport["Item 7A"].startswith(
        "Table of Contents\n\nItems 7. and 7A.\xa0\xa0Management’s Discussion and Analysis")


@pytest.mark.fast
def test_properties_subheading_inside_item_1_is_not_a_second_item_2():
    """Talos: no 'properties' fragment claims Item 2 (GH #1383)."""
    talos = TenK(FixtureFiling(TALOS))
    assert "properties" not in talos.sections
    assert [key for key, s in talos.sections.items() if s.item == "2"] == []
    assert talos["Item 2"] == talos.business


@pytest.mark.fast
def test_ordinary_items_cover_nothing():
    """A one-item section records no combined coverage."""
    viper = TenK(FixtureFiling(VIPER))
    assert viper.sections["part_i_item_1a"].covered_items == ()
    assert viper.sections["part_ii_item_7"].covered_items == ()


@pytest.mark.fast
@pytest.mark.parametrize("text,expected", [
    ("Items 1 and 2. Business and Properties", ("1", "2")),
    ("Items 1. and 2. Business and Properties", ("1", "2")),
    ("Items\xa01. and 2. Business and Properties", ("1", "2")),
    ("ITEMS 1. AND 2.\xa0\xa0\xa0\xa0BUSINESS AND PROPERTIES", ("1", "2")),
    ("Items 7. and 7A. Management's Discussion and Analysis", ("7", "7A")),
    ("Items 1 & 2 Business", ("1", "2")),
    # Not two items under one heading
    ("Item 1. Business", None),
    ("Items 10, 11 and 12", None),
    ("Items 1, 1A and 2", None),
    ("See Items 1 and 2", None),
])
def test_combined_item_numbers(text, expected):
    assert TOCAnalyzer.combined_item_numbers(text) == expected
