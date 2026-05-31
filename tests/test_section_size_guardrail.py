"""
Tests for the section content-size guardrail (edgartools-9hwf).

The guardrail flags sections whose extracted content size is anomalous for their
item — too small (anchor landed on a heading) or too large (boundary overshoot) —
attaching a human-readable warning and reducing confidence, instead of returning
wrong content at 0.95 confidence (the GS/Citi silent-failure class).
"""
from pathlib import Path

import pytest

from edgar.documents.section_size_bands import (
    ANOMALOUS_CONFIDENCE,
    band_for,
    evaluate_size,
)

HTML_ROOT = Path(__file__).parent / "fixtures" / "html"


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


# ---------------------------------------------------------------------------
# Integration: real filings through the detection pipeline (offline)
# ---------------------------------------------------------------------------

def _sections(rel: str, form: str):
    from edgar.documents.config import ParserConfig
    from edgar.documents.parser import HTMLParser
    html = (HTML_ROOT / rel).read_text()
    return HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(html).sections


@pytest.mark.slow
def test_gs_oversized_business_is_flagged():
    """Ground truth: GS 10-K maps Business to an oversized (668KB) section; the
    guardrail must flag it and drop its confidence below 0.95 — not return it
    silently as high-confidence wrong content."""
    sections = _sections("gs/10k/gs-10-k-2025-02-27.html", "10-K")
    item1 = [s for s in sections.values() if s.item == "1"]
    assert item1, "GS Item 1 not detected"
    flagged = [s for s in item1 if s.warnings]
    assert flagged, "GS oversized Item 1 was not flagged by the guardrail"
    assert flagged[0].confidence <= ANOMALOUS_CONFIDENCE
    assert "over-captured" in flagged[0].warnings[0]


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
