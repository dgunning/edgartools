"""Regression: REGIONS FINANCIAL 10-K Item 7A no longer duplicates Item 7.

GH #920 (REGIONS FINANCIAL CORP 10-K, accession 0001281761-22-000016). This
filing's linked TOC carries only page numbers — the "Item N." labels and titles
are plain (non-link) cells — so the generic TOC parser resolves each item to the
anchor of the page it starts on. Item 7 (MD&A) and Item 7A (Quantitative and
Qualitative Disclosures) both begin on page 41, so both item keys collided on
the single page-41 anchor.

The bug: two distinct items resolving to one anchor slice to the *identical*
span downstream, so ``obj['Item 7A']`` silently returned Item 7's 194KB MD&A
body (``obj['Item 7A'] == obj['Item 7']``) with no warning — real Item 7A is a
two-line incorporation-by-reference stub pointing at Item 7's Risk Management
section.

The fix: after the TOC parse, detect item keys that collide on one anchor and
re-resolve the displaced item from the body-header scan, which carries each
item's own heading behind its own anchor. Item 7 keeps the shared page anchor
(it owns the page it starts on); Item 7A is re-pointed at its real body heading.

Offline (local fixture).

GitHub Issue: https://github.com/dgunning/edgartools/issues/920
"""
from pathlib import Path

import pytest

from edgar.documents.config import ParserConfig
from edgar.documents.parser import HTMLParser

_FIXTURE = (Path(__file__).resolve().parents[2]
            / "fixtures" / "html" / "rf" / "10k" / "rf-10-k-2022-02-24.html")


@pytest.fixture(scope="module")
def sections():
    """Parse the RF 10-K once for the whole module.

    This was a plain `_sections()` helper that every test called, so the 9.5 MB
    fixture was parsed once per test. Measured 2026-08-10: 3 parses, 3.7s of
    them redundant — the largest single such cost in the offline regression
    tree (bead edgartools-07lk.24, Tier 3).

    Module scope rather than session scope so the parsed document is
    released when this file finishes; one parsed 10-K of this size costs
    ~0.3 GB resident, and `test-ci-fast` runs `-n auto`, which would multiply
    that across workers.
    """
    doc = HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(_FIXTURE.read_text())
    return doc.sections


def test_item7a_is_its_own_stub_not_item7(sections):
    """Item 7A resolves to its own incorporation-by-reference stub."""
    secs = sections
    item7 = secs["part_ii_item_7"].text()
    item7a = secs["part_ii_item_7a"].text()

    # The defect: 7A duplicated 7's 194KB MD&A body verbatim.
    assert item7a != item7, "Item 7A still duplicates Item 7's content"
    assert len(item7a) < 1000, f"Item 7A over-extracted ({len(item7a)} chars) — swallowed the MD&A"

    # 7A carries its own heading and the incorporation-by-reference pointer.
    assert "QUANTITATIVE AND QUALITATIVE" in item7a.upper()
    assert "incorporated herein by reference" in item7a
    # The MD&A's opening must NOT be present in 7A.
    assert "EXECUTIVE OVERVIEW" not in item7a.upper()


def test_item7_mda_stays_intact(sections):
    """Item 7's MD&A body is unchanged (it keeps the shared page anchor)."""
    item7 = sections["part_ii_item_7"].text()
    assert len(item7) > 150_000, f"Item 7 MD&A regressed ({len(item7)} chars)"
    assert "EXECUTIVE OVERVIEW" in item7.upper()


def test_item7a_does_not_overrun_into_later_items(sections):
    """The re-pointed 7A stops before Item 8 — no later item header bleeds in."""
    item7a = sections["part_ii_item_7a"].text().upper()
    for later in ("ITEM 8", "ITEM 9", "ITEM 9A"):
        assert later not in item7a, f"Item 7A overran into {later}"
