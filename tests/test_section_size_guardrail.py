"""
Tests for the section content-size guardrail (edgartools-9hwf).

The guardrail flags sections whose extracted content size is anomalous for their
item — too small (anchor landed on a heading) or too large (boundary overshoot) —
attaching a human-readable warning and reducing confidence, instead of returning
wrong content at 0.95 confidence (the GS/Citi silent-failure class).
"""
import json
from pathlib import Path

import pytest

from edgar.documents.section_size_bands import (
    SIZE_BANDS,
    band_for,
    evaluate_size,
)

HTML_ROOT = Path(__file__).parent / "fixtures" / "html"
CORPUS_BANDS = Path(__file__).parent / "fixtures" / "parser_corpus" / "size_bands.json"


# ---------------------------------------------------------------------------
# Unit: the band evaluator (fast, no parsing)
# ---------------------------------------------------------------------------

def test_evaluate_size_in_band_returns_none():
    band = band_for("10-K", "1A")
    mid = (band["low"] + band["high"]) // 2
    assert evaluate_size("10-K", "1A", mid) is None


def test_evaluate_size_too_large_flags_overshoot():
    warning = evaluate_size("10-K", "1", 668_343)  # GS Business
    assert warning is not None
    assert "above the expected maximum" in warning
    assert "over-captured" in warning


def test_evaluate_size_too_small_flags_truncation():
    warning = evaluate_size("10-K", "8", 268)  # NFLX Item 8 anchor-on-heading
    assert warning is not None
    assert "below the expected minimum" in warning
    assert "truncated" in warning


def test_library_bands_match_corpus():
    """Drift guard: the library's hardcoded SIZE_BANDS must match the enforced
    bands in the corpus (tests/fixtures/parser_corpus/size_bands.json). The two
    are maintained by hand-copying on corpus refresh; this catches a stale copy.
    """
    corpus = json.loads(CORPUS_BANDS.read_text())["bands"]
    for form, items in corpus.items():
        enforced = {k: v for k, v in items.items() if v.get("enforce")}
        lib = SIZE_BANDS.get(form, {})
        assert set(lib) == set(enforced), (
            f"{form}: library bands {sorted(lib)} != enforced corpus bands "
            f"{sorted(enforced)} — rerun build_corpus.py and update SIZE_BANDS"
        )
        for item, band in enforced.items():
            assert lib[item]["low"] == band["low_flag"], f"{form} Item {item} low drifted"
            assert lib[item]["high"] == band["high_flag"], f"{form} Item {item} high drifted"


def test_evaluate_size_silence_paths():
    # Unenforced item → no band → never flagged.
    assert evaluate_size("10-K", "1B", 50) is None
    # Unknown form → no band.
    assert evaluate_size("S-1", "1", 10) is None
    # Zero/unknown length is not a size anomaly (handled as "missing" upstream).
    assert evaluate_size("10-K", "1", 0) is None
    # None inputs.
    assert evaluate_size(None, "1", 100) is None
    assert evaluate_size("10-K", None, 100) is None


def test_guardrail_only_applies_to_toc_sections():
    """Only TOC sections carry a text-length in end_offset; pattern sections
    store a document char-position there (a different yardstick). The guardrail
    must skip non-TOC sections to avoid mis-flagging them on the wrong scale."""
    from edgar.documents.document import Section
    from edgar.documents.extractors.hybrid_section_detector import HybridSectionDetector
    from edgar.documents.nodes import SectionNode

    det = HybridSectionDetector.__new__(HybridSectionDetector)  # bypass heavy __init__
    det.form = "10-K"

    def mk(method):
        return Section(
            name="part_ii_item_1", title="x", node=SectionNode(section_name="x"),
            start_offset=0, end_offset=5_000_000,  # absurd: would trip the band
            detection_method=method, item="1",
        )

    sections = {"toc": mk("toc"), "pattern": mk("pattern"), "heading": mk("heading")}
    out = det._apply_size_guardrail(sections)

    assert out["toc"].warnings, "TOC section should be flagged"
    assert not out["pattern"].warnings, "pattern section must not be flagged (wrong length scale)"
    assert not out["heading"].warnings, "heading section must not be flagged"


# ---------------------------------------------------------------------------
# Integration: real filings through the detection pipeline (offline)
# ---------------------------------------------------------------------------

def _sections(rel: str, form: str):
    from edgar.documents.config import ParserConfig
    from edgar.documents.parser import HTMLParser
    html = (HTML_ROOT / rel).read_text()
    return HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(html).sections


@pytest.mark.slow
def test_gs_business_correctly_bounded():
    """Ground truth (edgartools-sldz): GS 10-K once mapped Business to a 668KB
    over-captured section (item structure lived only in a link-less TOC). The
    body-header detector now bounds it correctly to ~150KB, well within the
    Item 1 band — so it is no longer flagged and keeps full TOC confidence."""
    sections = _sections("gs/10k/gs-10-k-2025-02-27.html", "10-K")
    item1 = [s for s in sections.values() if s.item == "1"]
    assert item1, "GS Item 1 not detected"
    # Exactly one canonical Business section, correctly keyed under Part I.
    assert "part_i_item_1" in sections
    s = item1[0]
    length = (s.end_offset - s.start_offset) if (s.end_offset and s.start_offset is not None) else len(s.text() or "")
    assert 50_000 < length < 321_384, f"GS Item 1 length {length} outside the healthy band"
    assert not s.warnings, f"GS Item 1 unexpectedly flagged: {s.warnings}"
    assert s.confidence >= 0.9
    # The Business section starts with the real heading, not adjacent content.
    assert s.text().lstrip().lower().startswith("item 1")


@pytest.mark.slow
def test_nflx_undersized_item8_is_flagged():
    """Ground truth: NFLX 10-K Item 8 extracts to ~268 chars (anchor on the
    heading). The guardrail flags it as truncated."""
    sections = _sections("nflx/10k/nflx-10-k-2025-01-27.html", "10-K")
    item8 = [s for s in sections.values() if s.item == "8"]
    assert item8
    flagged = [s for s in item8 if s.warnings]
    assert flagged, "NFLX truncated Item 8 was not flagged"
    assert "truncated" in flagged[0].warnings[0]


@pytest.mark.slow
def test_healthy_filing_has_no_warnings():
    """Silence check: a healthy filing (NKE) produces no size warnings and keeps
    full TOC confidence."""
    sections = _sections("nke/10k/nke-10-k-2025-07-17.html", "10-K")
    warned = {n: s.warnings for n, s in sections.items() if s.warnings}
    assert not warned, f"healthy NKE filing produced unexpected warnings: {warned}"
    # Enforced content items retain high confidence.
    for s in sections.values():
        if s.item in ("1", "1A", "7"):
            assert s.confidence >= 0.9
