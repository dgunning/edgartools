"""A TOC that lists most items is not a TOC that lists all of them (edgartools-dt1f).

When TOC detection succeeds, the hybrid detector augments the result with items
the TOC did not name — they are in the body as bold paragraphs, and the pattern
extractor finds them. A performance gate decided whether that pass was worth
running, and it asked the wrong question: *are the five Part III keys present?*

Part III is the block filers omit when they incorporate it by reference from
the proxy, so the question was reasonable for the filings it was written
against. It is also complete on most filings, which means the skip fired almost
always. Six tracked 10-Ks lost an item to it:

    axp, cvx, jnj                Item 16  (Form 10-K Summary)
    bac, jpm, tsla               Item 1C  (Cybersecurity)

On every one, the pattern extractor had already found the item and the result
was discarded before it ran. Item 1C has been mandatory since December 2023, so
this was most modern 10-Ks rather than a corner. The gate now asks whether the
TOC result is missing any item the form defines.

THE SECOND HALF MATTERS AS MUCH AS THE FIRST. The merge keys on
``Section.item``, not on the section key, because the two detectors name the
same section differently — the TOC path emits ``part_ii_item_7`` and the
pattern path emits ``mda``, and ``Section.item`` is ``'7'`` for both. Merging on
keys would have added 9-11 duplicate sections per filing, each a second span of
an item the TOC already had. That never bit before only because the Part III
gate kept this code away from the filings where the TOC succeeds; lifting the
gate without fixing the merge would have traded six missing items for hundreds
of duplicated ones.

Corpus effect: 10-K legacy_only 14 -> 7, 10-Q 3 -> 2 (10-Q was skipped by the
old gate entirely), 20-F and 8-K unchanged, no filing losing an item.
"""
import warnings
from unittest.mock import MagicMock

import pytest

from edgar.company_reports import TenK
from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser

warnings.filterwarnings("ignore")

# (ticker, the item its TOC omits). Every one of these was in BASELINE_GAPS.
CASES = [
    ("axp", "16"),
    ("cvx", "16"),
    ("jnj", "16"),
    ("bac", "1C"),
    ("jpm", "1C"),
    ("tsla", "1C"),
]

_PART_III = {"10", "11", "12", "13", "14"}


def _fixture(ticker, pytestconfig):
    paths = sorted((pytestconfig.rootpath / "tests/fixtures/html" / ticker / "10k").glob("*.html"))
    if not paths:  # pragma: no cover
        pytest.fail(f"tracked 10-K fixture missing for {ticker}")
    return paths[0].read_text(errors="ignore")


def _ten_k(html):
    filing = MagicMock()
    filing.form = "10-K"
    filing.html.return_value = html
    filing.accession_number = "0000000000-00-000000"
    filing.base_dir = None
    report = TenK.__new__(TenK)
    report._filing = filing
    return report


@pytest.fixture(scope="module")
def parsed(pytestconfig):
    """Each fixture parsed once — these are 2.6-12.9MB filings."""
    out = {}
    for ticker, _item in CASES:
        html = _fixture(ticker, pytestconfig)
        out[ticker] = (
            html,
            HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(html),
        )
    return out


@pytest.mark.regression
@pytest.mark.parametrize("ticker,item", CASES)
class TestTheOmittedItemIsRecovered:

    def test_the_section_exists(self, parsed, ticker, item):
        _html, doc = parsed[ticker]
        items = {s.item for s in doc.sections.values() if s.item}
        assert item in items, (
            f"{ticker} is still missing Item {item}; found {sorted(items)}"
        )

    def test_the_item_is_listed_on_the_report(self, parsed, ticker, item):
        """The user-level view: TenK.items, not just doc.sections."""
        html, _doc = parsed[ticker]
        assert f"Item {item}" in _ten_k(html).items

    def test_the_gate_that_used_to_skip_this_would_still_skip_it(self, parsed, ticker, item):
        """Pins the premise: Part III is complete on every one of these filings.

        If it stopped being complete, these six would start passing for a reason
        that has nothing to do with the fix, and the regression would be
        unguarded without anyone noticing.
        """
        _html, doc = parsed[ticker]
        items = {s.item for s in doc.sections.values() if s.item}
        assert _PART_III <= items, (
            f"{ticker} no longer has a complete Part III — this test no longer "
            f"exercises the gate it was written for"
        )


@pytest.mark.regression
class TestTheMergeDoesNotDuplicateItems:
    """One section per item. The failure mode lifting the gate would have caused."""

    @pytest.mark.parametrize("ticker,_item", CASES)
    def test_no_item_appears_under_two_keys(self, parsed, ticker, _item):
        _html, doc = parsed[ticker]
        by_item = {}
        for key, section in doc.sections.items():
            if section.item:
                by_item.setdefault(section.item, []).append(key)
        duplicates = {item: keys for item, keys in by_item.items() if len(keys) > 1}
        assert not duplicates, (
            f"{ticker} carries the same item under several keys — the two naming "
            f"vocabularies merged instead of deduplicating: {duplicates}"
        )

    @pytest.mark.parametrize("ticker,_item", CASES)
    def test_the_toc_sections_are_not_replaced(self, parsed, ticker, _item):
        """Augmentation adds; it never overrides. TOC spans are the better ones.

        Checked through the key vocabulary: a TOC-detected 10-K section is keyed
        structurally (``part_ii_item_7``), so an Item 7 that came back keyed
        ``mda`` would mean the pattern section displaced the TOC one.
        """
        _html, doc = parsed[ticker]
        structural = [k for k in doc.sections if k.startswith("part_")]
        assert len(structural) >= 15, (
            f"{ticker} lost its TOC-keyed sections: {sorted(doc.sections)}"
        )
