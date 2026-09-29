"""Regression: TOC-resolved section text keeps a table's cells apart.

Found while reviewing GH #1347 (PR #1355): section text for sections resolved
from the table of contents (``detection_method == 'toc'``) fused adjacent table
cells, while ``doc.text()`` on the same document did not. In the Regions
Financial 10-K, Item 5's share-repurchase table read ``November 1-30,
20217,294,800`` -- the year 2021 welded to the share count -- and Item 8 carried
``20181,724,723``-shaped tokens throughout. 106 such tokens across the 69
tracked 10-K/10-Q/20-F fixtures, every one on the TOC path.

Root cause: the TOC path builds text by walking the raw lxml tree and emitting
each element's text, breaking only at block elements. ``td``/``th`` are not
blocks, so a row's cells ran together. ``doc.text()`` instead builds a
``TableNode`` and renders it. The TOC walk now renders each whole table through
that same code (``TableProcessor`` + ``TextExtractor.render_table``), with the
alignment padding collapsed so section sizes stay where the size guardrail's
bands expect them.

Routing sections through the shared renderer exposed two places where it lost
data, both fixed at the source so ``doc.text()`` gains them too: a column whose
values were all one or two characters was scored as spacing and dropped (RF's
"$85" consumer-loan figure), and a cell holding more than one ``<div>`` kept
only the divs' text (Netflix's "Derivatives not designated as hedging
instruments:" row label).

The TOC path's missing SIGNATURES cutoff, reported in the same bead, lands with
PR #1355.

Offline (local fixtures).

Bead: edgartools-wzgu
GitHub Issue: https://github.com/dgunning/edgartools/issues/1347
"""
import re
from pathlib import Path

import pytest

from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser

_HTML = Path(__file__).resolve().parents[2] / "fixtures" / "html"
_RF_10K = _HTML / "rf" / "10k" / "rf-10-k-2022-02-24.html"
_NFLX_10Q = _HTML / "nflx" / "10q" / "nflx-10-q-2025-07-18.html"

# A four-digit year fused to a thousands-grouped count, or a doubled "U.S." --
# the two shapes cell-gluing produced.
_GLUED = re.compile(r"U\.S\.U\.S\.|\d{4}\d{1,3},\d{3},\d{3}")


@pytest.fixture(scope="module")
def rf_doc():
    """Parse the 9.5 MB RF 10-K once for the module (see test_issue_920 for why module scope)."""
    return HTMLParser(ParserConfig(form="10-K")).parse(_RF_10K.read_text())


def test_rf_sections_come_from_the_toc(rf_doc):
    """The fixture exercises the TOC path; if this changes, the tests below test nothing."""
    for name in ("part_ii_item_5", "part_ii_item_8"):
        assert rf_doc.sections[name].detection_method == "toc"


def test_item5_year_and_share_count_are_separate_tokens(rf_doc):
    item5 = rf_doc.sections["part_ii_item_5"].text()

    assert _GLUED.findall(item5) == []
    tokens = item5.split()
    assert "2021" in tokens
    assert "7,294,800" in tokens
    # The whole row, one cell after another.
    assert "November 1-30, 2021  7,294,800  $24.09  7,294,800  $2,129,712,326" in item5


def test_item8_has_no_glued_cells(rf_doc):
    item8 = rf_doc.sections["part_ii_item_8"].text()

    assert _GLUED.findall(item8) == []
    # Was "20181,724,723" -- the 2018 column header welded to the first figure.
    assert "20181,724,723" not in item8
    assert _GLUED.findall(rf_doc.text()) == []


def test_section_rows_match_doc_text_rows(rf_doc):
    """Same cells, same order as doc.text(); only the alignment padding differs."""
    item5 = rf_doc.sections["part_ii_item_5"].text()
    doc_row = next(line for line in rf_doc.text().splitlines()
                   if line.strip().startswith("November 1-30, 2021"))
    sec_row = next(line for line in item5.splitlines()
                   if line.startswith("November 1-30, 2021"))
    assert sec_row.split() == doc_row.split()


def test_short_figures_survive_table_rendering(rf_doc):
    """A column of two-digit values is data, not spacing: "$85" was dropped."""
    item8 = rf_doc.sections["part_ii_item_8"].text()
    row = next(line for line in item8.splitlines() if line.startswith("Total consumer loans"))
    assert row.split() == ["Total", "consumer", "loans",
                           "$", "7,774", "$", "7,515", "$", "2,743", "$", "1,679",
                           "$", "1,377", "$", "4,932", "$", "5,070", "$", "85",
                           "$", "273", "$", "31,448"]
    doc_row = next(line for line in rf_doc.text().splitlines()
                   if line.strip().startswith("Total consumer loans"))
    assert doc_row.split() == row.split()


def test_cell_text_outside_divs_is_kept():
    """A cell's own text is not discarded because it also holds empty <div>s."""
    doc = HTMLParser(ParserConfig(form="10-Q")).parse(_NFLX_10Q.read_text())
    item1 = doc.sections["part_i_item_1"]
    assert item1.detection_method == "toc"

    pattern = re.compile(r"Derivatives not designated as hedging instruments:\n"
                         r"\s*Foreign exchange contracts\s+1,285,612\s+1,432,136")
    assert pattern.search(item1.text())
    assert pattern.search(doc.text())
