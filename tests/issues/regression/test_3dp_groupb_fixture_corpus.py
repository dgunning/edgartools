"""20-F and 8-K fixture coverage for the parsers that had none (edgartools-3dp).

Group B deleted the ``__getitem__`` fallback to ``edgar.files`` from TenK, TenQ,
TwentyF and CurrentReport. The 10-K and 10-Q halves of that measurement could be
re-run from tracked fixtures. The 20-F and 8-K halves could NOT: there were no
20-F or 8-K fixtures in the tree at all, so those numbers came from filings
fetched over the network, which no CI job can repeat.

These fixtures close that hole, and they are small on purpose. A mega-cap 20-F
runs 6-24MB (Shell 9.8, Alibaba 11.2, Rio Tinto 23.6) against a fixture tree
already at 277MB, so these are ordinary foreign private issuers of 0.19-1.45MB,
which are also far more representative of the form than Shell is. The whole set
is 2.4MB.

The 8-K side spans 2001, 2004, 2008 and 2025 deliberately. ``CurrentReport``
ran the deleted fallback AHEAD of a text-based strategy that exists for pre-HTML
SGML filings (GH #462), so the filings most likely to have needed it are the
oldest, not the newest. Both item spellings are probed: the pre-2004 "Item 5" /
"Item 7" and the numbered events that replaced them.

WHAT THESE ASSERT, and what they deliberately do not. The obvious test -- parse
each fixture twice, once with ``_chunked_document`` nulled, and compare -- is
TAUTOLOGICAL now that the fallback is deleted: there is no longer a branch that
reads it, so the two runs are identical by construction and the test cannot
fail. That comparison was migration evidence and was only meaningful before the
deletion.

What is left worth pinning is two things a future change could actually break:
that these lookups still ANSWER from the modern parser, on forms that until now
had no fixture at all; and that nothing quietly reintroduces a read of
``edgar.files`` on this path, which ``_forbidding_legacy`` catches by raising
rather than returning None.

Lengths are asserted as floors rather than exact counts. Exact counts on item
text move whenever table rendering changes -- edgartools-kq2q and -3cis each
moved a batch of them -- and this file is about which parser answers, not about
how wide a table renders.
"""
import pathlib

import pytest

from edgar.company_reports.current_report import CurrentReport
from edgar.company_reports.twenty_f import TwentyF
from edgar.exceptions import SectionNotFoundError

pytestmark = pytest.mark.fast

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures" / "html"
TWENTY_F = sorted(FIXTURES.glob("*/20f/*.html"))
EIGHT_K = sorted(FIXTURES.glob("*/8k/*.html"))

# item -> minimum characters, measured on 2026-08-23 and rounded well down.
TWENTY_F_EXPECTED = {
    "1018735-20-f-2025-06-03": {"Item 3": 30000, "Item 4": 20000, "Item 5": 15000,
                                "Item 8": 90000, "Item 10": 34000, "Item 15": 4000},
    "1464165-20-f-2025-06-02": {"Item 3": 28000, "Item 4": 12000, "Item 5": 19000,
                                "Item 10": 19000, "Item 15": 3500, "Item 19": 500},
    "2026514-20-f-2025-06-11": {"Item 3": 900, "Item 4": 3000, "Item 7": 5000,
                                "Item 8": 1500, "Item 10": 5000, "Item 19": 8000},
}

EIGHT_K_EXPECTED = {
    "1013243-8-k-2001-03-30": {"Item 5": 900, "Item 7": 250},
    "1074269-8-k-2001-03-30": {"Item 5": 700, "Item 7": 700},
    "883787-8-k-2004-09-30": {"Item 1.01": 2500, "Item 9.01": 200},
    "1100748-8-k-2004-09-30": {"Item 1.01": 3800, "Item 5.02": 800, "Item 9.01": 100},
    "1434743-8-k-2008-06-30": {"Item 2.03": 1700, "Item 9.01": 40},
    "786947-8-k-2008-06-30": {"Item 8.01": 250, "Item 9.01": 200},
    "1442999-8-k-2025-06-30": {"Item 1.01": 13000, "Item 5.02": 500, "Item 9.01": 4000},
    "1998387-8-k-2025-06-30": {"Item 2.03": 900, "Item 3.02": 800, "Item 9.01": 250},
    "744452-8-k-2025-06-30": {"Item 2.05": 1400, "Item 5.02": 600, "Item 9.01": 300},
}


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

    def text(self):
        """CurrentReport's text strategy reads this."""
        return self._path.read_text(encoding="utf-8", errors="replace")


def _forbidding_legacy(cls):
    """A subclass where touching ``edgar.files`` is a loud failure.

    A throwaway subclass rather than patching and deleting on ``cls``:
    CurrentReport defines ``_chunked_document`` on itself, so ``del`` would
    destroy the real override and every later assertion would measure a
    different object.

    The property RAISES rather than returning None, which is the whole point --
    a None would be indistinguishable from the fallback being absent, and this
    needs to catch a read, not tolerate one.
    """

    def _forbidden(self):
        raise AssertionError(
            "_chunked_document was read — a fallback to edgar.files was "
            "reintroduced on this path, which edgartools-3dp Group B removed"
        )

    return type(f"NoLegacy{cls.__name__}", (cls,),
                {"_chunked_document": property(_forbidden)})


@pytest.fixture
def lenient(monkeypatch):
    """Pin today's error behaviour for the two lookups that MISS.

    `report[item]` on an absent item warns now and raises under
    `EDGARTOOLS_STRICT_ERRORS` (edgartools-sx7y wired that up for CurrentReport
    and TwentyF, which had been answering None in silence). These two tests are
    about a different question -- that the miss path does not read
    `edgar.files` -- and that holds in either mode, so they name the mode they
    assert rather than inheriting whichever lane invoked them. Not naming it is
    exactly what left `test-strict-errors` red on main for five merges.
    """
    monkeypatch.delenv("EDGARTOOLS_STRICT_ERRORS", raising=False)


@pytest.fixture
def strict(monkeypatch):
    """The 6.0 error behaviour, asserted on the same offline fixtures."""
    monkeypatch.setenv("EDGARTOOLS_STRICT_ERRORS", "1")


def test_the_fixtures_are_present():
    """A glob that matches nothing would pass every parametrized test below."""
    assert len(TWENTY_F) >= 3, f"expected 20-F fixtures under {FIXTURES}, found {TWENTY_F}"
    assert len(EIGHT_K) >= 9, f"expected 8-K fixtures under {FIXTURES}, found {EIGHT_K}"


def test_the_eight_k_fixtures_span_four_eras():
    """The oldest filings are the ones the deleted fallback might have carried."""
    years = sorted({p.stem.rsplit("-", 3)[-3] for p in EIGHT_K})
    assert years == ["2001", "2004", "2008", "2025"], years


@pytest.mark.parametrize("path", TWENTY_F, ids=lambda p: p.stem)
def test_twenty_f_items_answer_from_the_modern_parser(path):
    report = _forbidding_legacy(TwentyF)(FixtureFiling(path, "20-F"))

    expected = TWENTY_F_EXPECTED[path.stem]
    for item, floor in expected.items():
        text = report[item]
        assert text is not None, f"{path.name} {item} returned None"
        assert len(text) >= floor, (
            f"{path.name} {item}: {len(text)} chars, expected at least {floor}"
        )


@pytest.mark.parametrize("path", EIGHT_K, ids=lambda p: p.stem)
def test_eight_k_items_answer_from_the_modern_parser(path):
    report = _forbidding_legacy(CurrentReport)(FixtureFiling(path, "8-K"))

    expected = EIGHT_K_EXPECTED[path.stem]
    for item, floor in expected.items():
        text = report[item]
        assert text is not None, f"{path.name} {item} returned None"
        assert len(text) >= floor, (
            f"{path.name} {item}: {len(text)} chars, expected at least {floor}"
        )


@pytest.mark.parametrize("path", TWENTY_F, ids=lambda p: p.stem)
def test_a_missing_twenty_f_item_returns_none_without_reading_legacy(path, lenient):
    """The lookup that actually EXERCISES the guard.

    Every item in TWENTY_F_EXPECTED is answered by the modern parser, so those
    tests never reach the fallback branch and would pass even if a fallback were
    reintroduced — verified by putting the deleted branch back and watching them
    stay green. An item no 20-F has is what walks off the end of the method,
    which is where a reintroduced read of ``edgar.files`` would sit.
    """
    report = _forbidding_legacy(TwentyF)(FixtureFiling(path, "20-F"))

    assert report["Item 99"] is None


@pytest.mark.parametrize("path", EIGHT_K[:3], ids=lambda p: p.stem)
def test_a_missing_eight_k_item_returns_none_without_reading_legacy(path, lenient):
    """The Group B behaviour change, on the forms that had no fixture for it.

    An item the filing does not have returns None. It used to fall through to
    ``ChunkedDocument`` first; ``_forbidding_legacy`` proves it no longer does.
    """
    report = _forbidding_legacy(CurrentReport)(FixtureFiling(path, "8-K"))

    assert report["Item 6.66"] is None


@pytest.mark.parametrize("path", TWENTY_F, ids=lambda p: p.stem)
def test_a_missing_twenty_f_item_raises_under_strict(path, strict):
    """The other half of the same lookup, on the same fixtures.

    TwentyF overrode ``__getitem__`` and reimplemented the miss path without
    ``report_lookup_miss``, so this raised nothing and answered None in silence
    until edgartools-sx7y. Asserted offline, on the committed corpus, so the fix
    is gated on every pull request rather than only in the post-merge network
    lane.
    """
    report = _forbidding_legacy(TwentyF)(FixtureFiling(path, "20-F"))

    with pytest.raises(SectionNotFoundError, match="Item 99"):
        report["Item 99"]


@pytest.mark.parametrize("path", EIGHT_K[:3], ids=lambda p: p.stem)
def test_a_missing_eight_k_item_raises_under_strict(path, strict):
    """CurrentReport had the same override gap as TwentyF (edgartools-sx7y)."""
    report = _forbidding_legacy(CurrentReport)(FixtureFiling(path, "8-K"))

    with pytest.raises(SectionNotFoundError, match="Item 6.66"):
        report["Item 6.66"]
