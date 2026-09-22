"""Regression test for GitHub Issue #927 (edgartools-xrs0).

NVIDIA's FY2025 10-K answers Item 8 with a 207-char pointer — "The information
required by this Item is set forth in our Consolidated Financial Statements and
Notes thereto included in this Annual Report on Form 10-K" — and files the
statements under Item 15. The extraction is faithful to the document; the text
simply is not the financial statements.

The size guardrail (edgartools-9hwf) already flagged it, because 207 chars is far
below Item 8's floor of 26,136. But it flagged it with the wrong cause: "the
section anchor may point at a heading rather than the item body (extraction
likely truncated)". That sends a caller to debug a parser that did its job, and
it is wrong for every undersized Item 8 in the fixture corpus — NVDA, NFLX, IBM,
ORCL and CIK 915358 are all incorporation-by-reference filers, none are truncated
extractions.

Fix (warning path, per the maintainer's steer on #927): on the undersize side
only, ``is_cross_reference`` tests the section text for a deferral before the
warning is written. A pointer gets the incorporation-by-reference warning; a
section with no deferral keeps the truncation warning. Confidence still drops to
``ANOMALOUS_CONFIDENCE`` in both cases — a pointer is still not the item's
substance — so nothing about what callers receive changes, only what they are
told about it.
"""
from pathlib import Path

import pytest

from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser
from edgar.documents.section_size_bands import (
    ANOMALOUS_CONFIDENCE,
    band_for,
    is_cross_reference,
)

pytestmark = pytest.mark.regression

HTML_ROOT = Path(__file__).parents[2] / "fixtures" / "html"
NVDA_10K = HTML_ROOT / "nvda" / "10k" / "nvda-10-k-2025-02-26.html"
AAPL_10K = HTML_ROOT / "aapl" / "10k" / "aapl-10-k-2024-11-01.html"

# Ground truth, hand-verified against the filing (and against edgartools 5.44.1,
# where Item 8 returned exactly this text with the truncation warning).
NVDA_ITEM8_LENGTH = 207
NVDA_ITEM8_TEXT = (
    "Item\xa08. Financial Statements and Supplementary Data\n\n"
    "The information required by this Item is set forth in our Consolidated "
    "Financial Statements and Notes thereto included in this Annual Report on Form 10-K."
)


@pytest.mark.fast
def test_nvda_item8_stub_is_a_cross_reference():
    """Unit: the pointer text is recognised without parsing the filing."""
    assert is_cross_reference(NVDA_ITEM8_TEXT) is True
    # The heading alone — what a genuinely truncated extraction returns — is not.
    assert is_cross_reference("Item 8. Financial Statements and Supplementary Data") is False


@pytest.mark.fast
def test_item8_floor_is_far_above_the_stub():
    """The stub is undersize by two orders of magnitude, so it always reaches the
    cross-reference test rather than passing as normal variation."""
    band = band_for("10-K", "8")
    assert band is not None
    assert NVDA_ITEM8_LENGTH < band["low"]


@pytest.mark.slow
def test_nvda_item8_warns_about_incorporation_not_truncation():
    """End to end: parse the filing and check what the caller is told."""
    doc = HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(NVDA_10K.read_text())

    item8 = doc.sections.get_item("8")
    assert item8 is not None, "NVDA Item 8 not detected"
    assert len(item8.text()) == NVDA_ITEM8_LENGTH
    assert item8.text() == NVDA_ITEM8_TEXT

    # Flagged, and flagged with the right cause.
    assert item8.warnings, "NVDA Item 8 returned without a warning"
    warning = item8.warnings[0]
    assert "incorporation by reference" in warning
    assert "truncated" not in warning
    assert item8.confidence <= ANOMALOUS_CONFIDENCE

    # The statements are in the filing, under Item 15 — the caller is not being
    # told to go looking for something that is not there.
    item15 = doc.sections.get_item("15")
    assert item15 is not None
    assert len(item15.text()) > 50_000


@pytest.mark.slow
def test_healthy_filer_item8_is_unchanged():
    """Silence check: AAPL inlines its statements, so nothing about it changes —
    no warning, full confidence."""
    doc = HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(AAPL_10K.read_text())
    item8 = doc.sections.get_item("8")
    assert item8 is not None
    assert not item8.warnings
    assert item8.confidence >= 0.9
