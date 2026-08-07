"""Regression: gh-878 — S-1 / 424B `.sections` boundary misattribution.

edgartools-ti82. On Airbnb's IPO prospectuses the TOC engine returned the right
section *keys* but the wrong *boundaries*:

  * S-1 ``mda`` was 105 chars — an out-of-order "Glossary of Terms" anchor, listed
    before MD&A in the TOC but anchored a few nodes into MD&A's body, truncated the
    section to a sliver. The real MD&A body landed nowhere.
  * S-1 ``experts`` / 424B4 ``dilution`` ran to end-of-document and swallowed the
    untitled financial-statements (F-pages) block — 200KB–900KB of statements
    wrongly attributed to a one-paragraph narrative section.
  * The 424B4 matched only 5 sections at all: the sparse 424B vocabulary left the
    narrative sections (MD&A, Business, Management, …) unmatched, the
    authoritative-TOC-span clustering split on the resulting gap, and ``dilution``
    (the last survivor) absorbed everything after it.

Three fixes: a TOC-declaration-order guard on the boundary selector (drops the
out-of-order glossary anchor), 424B sharing S-1's full prospectus vocabulary, and
a trailing-financials rescue that clamps the last narrative section at the F-pages
heading.

Offline (local fixtures — the primary prospectus document of each filing). Ground
truth verified by hand against the two Airbnb filings:
  S-1   0001193125-20-294801   424B4   0001193125-20-315318
"""
from functools import lru_cache
from pathlib import Path

from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "html" / "abnb"
_S1_HTML = _FIXTURES / "s1" / "abnb-s1-2020-11-16.html"
_424B4_HTML = _FIXTURES / "424b4" / "abnb-424b4-2020-12-09.html"


@lru_cache(maxsize=None)
def _sections(path: Path, form: str):
    doc = HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(path.read_text())
    return doc.sections


def _s1():
    return _sections(_S1_HTML, "S-1")


def _b4():
    return _sections(_424B4_HTML, "424B4")


# --- S-1: MD&A no longer truncated to a sliver -----------------------------------

def test_s1_mda_carries_the_real_body_not_a_sliver():
    mda = _s1()["mda"].text()
    # Was 105 chars; the real MD&A body is well over 100KB.
    assert len(mda) > 100_000, f"MD&A truncated (got {len(mda)} chars)"
    assert "Results of Operations" in mda


# --- S-1: Experts bounded, does not absorb the financial statements --------------

def test_s1_experts_does_not_swallow_financial_statements():
    experts = _s1()["experts"].text()
    # Was 247,817 chars (the entire F-pages tail); the real Experts section is a
    # single paragraph naming the auditor.
    assert len(experts) < 10_000, f"Experts over-extracted ({len(experts)} chars)"
    assert "PricewaterhouseCoopers" in experts          # its own content kept
    assert "Consolidated Balance Sheets" not in experts  # F-pages excluded


# --- 424B4: full prospectus section set + bounded sections -----------------------

def test_424b4_surfaces_full_prospectus_section_set():
    secs = _b4()
    # The sparse 424B vocabulary used to surface only 5 sections; a final IPO
    # prospectus repeats the whole S-1 body, so the narrative sections must appear.
    for key in ("mda", "business", "management", "experts", "dividend_policy"):
        assert key in secs, f"424B4 missing section {key!r}"


def test_424b4_dilution_bounded_not_900kb_blob():
    dilution = _b4()["dilution"].text()
    # Was 934,028 chars (MD&A + Business + … + the financial statements).
    assert len(dilution) < 50_000, f"Dilution over-extracted ({len(dilution)} chars)"
    assert "Consolidated Balance Sheets" not in dilution


def test_424b4_experts_does_not_swallow_financial_statements():
    experts = _b4()["experts"].text()
    assert len(experts) < 10_000, f"Experts over-extracted ({len(experts)} chars)"
    assert "Consolidated Balance Sheets" not in experts
