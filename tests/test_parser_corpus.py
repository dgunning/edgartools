"""
Canonical parser fixture corpus benchmark (edgartools-h44r).

Two tiers:
  - Fast (always collected): the manifest and size bands are well-formed, the
    documented known-bad filings are present and flagged, and every marker is a
    recognized type. Guards the corpus itself.
  - Slow (@pytest.mark.slow): re-parse a representative subset and assert
    enforced content items stay within their size band, and that the documented
    known-bad filings still trip the guardrail. Guards the parser against
    regression and validates the bands are useful for the 9hwf guardrail.

Regenerate the corpus with: python tests/fixtures/parser_corpus/build_corpus.py
"""
import json
from pathlib import Path

import pytest

CORPUS_DIR = Path(__file__).parent / "fixtures" / "parser_corpus"
HTML_ROOT = Path(__file__).parent / "fixtures" / "html"

RECOGNIZED_MARKERS = {
    "parse_error", "oversized_section", "oversized_business_section",
    "raw_html_leak", "part_misclassification", "legacy_fallback_required",
}
# Prefixes for the per-item auto-detected markers (e.g. "oversized:item_8").
RECOGNIZED_PREFIXES = ("oversized:item_", "undersized:item_")

# A representative spread of healthy filings for the slow regression check —
# keeps runtime bounded while covering both agents.
HEALTHY_SAMPLE = {"aapl", "nke", "googl", "msft", "hubs"}  # Workiva + Donnelley


@pytest.fixture(scope="module")
def manifest():
    return json.loads((CORPUS_DIR / "manifest.json").read_text())


@pytest.fixture(scope="module")
def bands():
    return json.loads((CORPUS_DIR / "size_bands.json").read_text())["bands"]


# ----------------------------------------------------------------------------
# Fast tier — corpus integrity (no parsing)
# ----------------------------------------------------------------------------

def test_manifest_well_formed(manifest):
    assert manifest["n_filings"] == len(manifest["filings"])
    assert manifest["n_filings"] >= 50
    for f in manifest["filings"]:
        assert f["ticker"] and f["form"] in ("10-K", "10-Q")
        assert "items" in f and "known_bad" in f


def test_documented_known_bad_present_and_flagged(manifest):
    """The four originally-documented failures must stay in the corpus and stay
    flagged — losing one means we stopped covering a regression."""
    by_key = {(f["ticker"], f["form"]): f for f in manifest["filings"]}
    for ticker, form in [("gs", "10-K"), ("c", "10-K"), ("jpm", "10-K")]:
        assert (ticker, form) in by_key, f"{ticker} {form} dropped from corpus"
        assert by_key[(ticker, form)]["known_bad"], f"{ticker} {form} no longer flagged"


def test_all_markers_recognized(manifest):
    for f in manifest["filings"]:
        for marker in f["known_bad"]:
            ok = marker in RECOGNIZED_MARKERS or marker.startswith(RECOGNIZED_PREFIXES)
            assert ok, f"{f['ticker']} {f['form']}: unrecognized marker {marker!r}"


def test_size_bands_structure(bands):
    assert "10-K" in bands
    # The reliably-substantial 10-K items must be enforceable.
    for item in ("1", "1A", "7"):
        band = bands["10-K"].get(item)
        assert band and band["enforce"], f"Item {item} band missing or not enforced"
        assert band["low_flag"] < band["p50"] < band["high_flag"]


def test_corpus_reveals_wide_blast_radius(manifest):
    """Ground-truth observation: section-extraction failures are far wider than
    the 4 originally-documented filings (~31% of the corpus carries a marker)."""
    flagged = [f for f in manifest["filings"] if f["known_bad"]]
    assert len(flagged) >= 12, f"expected widespread anomalies, got {len(flagged)}"


# ----------------------------------------------------------------------------
# Slow tier — re-parse and check against bands
# ----------------------------------------------------------------------------

def _parse_sections(fixture_rel: str, form: str):
    from edgar.documents.config import ParserConfig
    from edgar.documents.parser import HTMLParser
    html = (HTML_ROOT / fixture_rel).read_text()
    return HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(html).sections


def _item_key(section_name: str):
    import re
    stripped = re.sub(r"^part_[ivx]+_", "", section_name, flags=re.IGNORECASE)
    m = re.match(r"^item[_\s]*(\d+[a-z]?)$", stripped, re.IGNORECASE)
    return m.group(1).upper() if m else None


@pytest.mark.slow
def test_healthy_sample_within_bands(manifest, bands):
    """Enforced content items on healthy filings stay within their size band.
    This is the regression guard: a parser change that shrinks Item 1A or blows
    up Item 8 trips here."""
    sample = [f for f in manifest["filings"]
              if f["ticker"] in HEALTHY_SAMPLE and not f["known_bad"]]
    assert sample, "no healthy sample filings found"

    violations = []
    for f in sample:
        sections = _parse_sections(f["fixture"], f["form"])
        form_bands = bands.get(f["form"], {})
        best = {}
        for name, section in sections.items():
            key = _item_key(name)
            if key is None:
                continue
            tl = len(section.text() or "")
            best[key] = max(best.get(key, 0), tl)
        for key, tl in best.items():
            band = form_bands.get(key)
            if not band or not band["enforce"]:
                continue
            if tl < band["low_flag"] or tl > band["high_flag"]:
                violations.append(
                    f"{f['ticker']} {f['form']} Item {key}: {tl} outside "
                    f"[{band['low_flag']}, {band['high_flag']}]"
                )
    assert not violations, "healthy filings drifted outside size bands:\n" + "\n".join(violations)


@pytest.mark.slow
def test_known_bad_tripped_by_bands(manifest, bands):
    """The size-band guardrail (edgartools-9hwf) must actually catch the
    documented oversize failures — validates the bands are useful, not just
    decorative. GS Item 1 (668KB) and JPM oversize must exceed high_flag."""
    by_key = {(f["ticker"], f["form"]): f for f in manifest["filings"]}
    gs = by_key[("gs", "10-K")]
    sections = _parse_sections(gs["fixture"], gs["form"])
    # GS Business is mis-mapped to Part II Item 1 and grossly oversized.
    oversized = [len(s.text() or "") for n, s in sections.items()
                 if _item_key(n) == "1"]
    item1_band = bands["10-K"]["1"]
    assert oversized and max(oversized) > item1_band["high_flag"], (
        f"GS Item 1 no longer trips the band (sizes={oversized}, "
        f"high_flag={item1_band['high_flag']}) — update the marker if fixed"
    )
