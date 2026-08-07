"""Regression: Chevron 10-K MD&A/financials recovered, Item 14 not over-extracted.

edgartools-gegs (surfaced by the llmp.5 scoring harness). Chevron defers its MD&A
and financial statements to a 'Financial Section' and leaves Item 7/8 as pointer
stubs — but its pointer wording ("The index to Management's Discussion and
Analysis ... is presented in the Financial Table of Contents") wasn't matched by
the incorporation-by-reference recovery's ``_INCORP_RE``. So the recovery never
fired: Item 7 stayed a 242-char stub, Item 8 a 158-char stub, and Item 14
(Principal Accountant Fees) absorbed the entire ~310KB financial body that
physically sits after its anchor.

Broadening ``_INCORP_RE`` to the Chevron phrasing lets the existing rv86 recovery
re-attribute the deferred MD&A/financials and clamp the trailing bucket.

Offline (local fixture); asserts ranges + content, not exact recovery lengths.
"""
from pathlib import Path

from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "html" / "cvx" / "10k" / "cvx-10-k-2025-02-21.html"


def _sections():
    doc = HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(_FIXTURE.read_text())
    return doc.sections


def test_cvx_mda_recovered_not_a_pointer_stub():
    """Item 7 carries the real MD&A, not the 242-char incorporation pointer."""
    item7 = _sections()["part_ii_item_7"].text()
    assert len(item7) > 50_000, f"Item 7 MD&A not recovered (got {len(item7)} chars)"
    assert "Management" in item7 and "Discussion" in item7


def test_cvx_financials_recovered():
    """Item 8 carries the financial statements, not the 158-char stub."""
    item8 = _sections()["part_ii_item_8"].text()
    assert len(item8) > 50_000, f"Item 8 financials not recovered (got {len(item8)} chars)"


def test_cvx_item14_not_over_extracted():
    """Item 14 (Principal Accountant Fees) no longer absorbs the financial body."""
    item14 = _sections()["part_iii_item_14"].text()
    assert len(item14) < 50_000, f"Item 14 over-extracted ({len(item14)} chars) — clamp failed"
