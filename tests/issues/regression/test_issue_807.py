"""
Regression test for GH #807: viewer.concept_report.currency_scaling unreliable.

The original implementation derived ``ConceptReport.currency_scaling`` from a
narrow text match on the R*.htm ``<th class='tl'>`` header (``$ in millions``
/ ``$in millions``). Filers using variations (``In Millions``, ``(in
millions)``, ``USD ($) in Millions``, …) fell through to the default of 1,
producing inconsistent scaling across same-filing statements (e.g. ALGN
balance sheet vs income statement) and wrong values for whole multi-year
ranges (ABNB showing 1 for 2023/2024 when the actual scale is millions).

The fix resolves ``ViewerReport.currency_scaling`` from the XBRL ``decimals``
attribute on monetary facts mapped to the report's role in the presentation
linkbase (filer-mandated, uniform). Falls back to the text-match value when
XBRL is unavailable.

Acceptance criteria from the issue:
1. ALGN balance sheet and income statement scaling agree
2. ABNB scaling consistent across years
3. Canary 5-ticker subset shows only ``{1, 1_000, 1_000_000}``
"""
from __future__ import annotations

import pytest

from edgar import Company


VALID_MONETARY_SCALES = {1, 1_000, 1_000_000, 1_000_000_000}


def _primary_statement(viewer, *needles: str, exclude=("Parenthetical",)):
    """Return the first non-parenthetical statement whose short_name contains
    all the needle substrings (case-insensitive)."""
    needles_lower = [n.lower() for n in needles]
    for vr in viewer.financial_statements:
        name = (vr.short_name or '').lower()
        if any(ex.lower() in name for ex in exclude):
            continue
        if all(n in name for n in needles_lower):
            return vr
    return None


@pytest.mark.network
def test_algn_balance_sheet_and_income_statement_scaling_agree():
    """ALGN was the reporter's canonical same-filing mismatch example
    (BS=0, IS=1_000 in the issue text). The two primary statements MUST
    report identical currency scaling within a single filing."""
    f = Company('ALGN').get_filings(form='10-K').latest()
    viewer = f.viewer
    bs = _primary_statement(viewer, 'balance', 'sheet')
    is_ = _primary_statement(viewer, 'statements', 'of', 'operations')
    assert bs is not None and is_ is not None, "ALGN primary statements not found"
    assert bs.currency_scaling == is_.currency_scaling, (
        f"ALGN scaling mismatch: BS={bs.currency_scaling}, "
        f"IS={is_.currency_scaling}"
    )
    assert bs.currency_scaling in VALID_MONETARY_SCALES


@pytest.mark.network
def test_abnb_scaling_consistent_across_years():
    """ABNB was the reporter's multi-year inconsistency case. The text-match
    parser produced different values across years (1, 1_000, 1_000_000) for
    the same logical scale. Post-fix, the BS and IS of each year should
    agree, and the values should all be valid monetary scales."""
    filings = Company('ABNB').get_filings(form='10-K').head(4)
    results = []
    for f in filings:
        viewer = f.viewer
        bs = _primary_statement(viewer, 'balance', 'sheet')
        is_ = _primary_statement(viewer, 'statements', 'of', 'operations')
        if bs is None or is_ is None:
            continue
        results.append((f.filing_date, bs.currency_scaling, is_.currency_scaling))

    assert len(results) >= 3, f"Need >=3 ABNB filings; got {len(results)}"

    for fdate, bs_scale, is_scale in results:
        assert bs_scale == is_scale, (
            f"ABNB {fdate}: BS={bs_scale} but IS={is_scale} (must match)"
        )
        assert bs_scale in VALID_MONETARY_SCALES, (
            f"ABNB {fdate}: scale {bs_scale} is not a valid monetary scale"
        )


@pytest.mark.network
def test_canary_tickers_show_only_valid_monetary_scales():
    """5-ticker subset from the reporter's table. Acceptance: every primary
    statement on the most recent 10-K shows a scale in {1, 1_000, 1_000_000}
    (the reporter's stated valid set) and BS/IS agree within each filing."""
    tickers = ['AAPL', 'ABNB', 'ALGN', 'ACN', 'AMGN']
    for ticker in tickers:
        f = Company(ticker).get_filings(form='10-K').latest()
        viewer = f.viewer
        bs = _primary_statement(viewer, 'balance', 'sheet')
        is_ = _primary_statement(
            viewer, 'statements', 'of', 'operations'
        ) or _primary_statement(
            viewer, 'statements', 'of', 'income'
        ) or _primary_statement(
            viewer, 'income', 'statements'
        )
        if bs is None or is_ is None:
            continue
        assert bs.currency_scaling in VALID_MONETARY_SCALES, (
            f"{ticker} BS scale {bs.currency_scaling} not in valid set"
        )
        assert is_.currency_scaling in VALID_MONETARY_SCALES, (
            f"{ticker} IS scale {is_.currency_scaling} not in valid set"
        )
        assert bs.currency_scaling == is_.currency_scaling, (
            f"{ticker}: BS={bs.currency_scaling} != IS={is_.currency_scaling}"
        )


@pytest.mark.network
def test_aapl_matches_canonical_million_scale():
    """AAPL is the control: its R*.htm headers DO match the original
    ``$ in Millions`` text pattern, so both the XBRL-derived path and the
    text-match fallback path return the same answer. This pins the
    no-regression baseline."""
    f = Company('AAPL').get_filings(form='10-K').latest()
    viewer = f.viewer
    stmt = viewer.financial_statements[0]
    assert stmt.currency_scaling == 1_000_000


@pytest.mark.network
def test_xbrl_unavailable_falls_back_to_text_match():
    """Force the XBRL path off by stubbing ``_get_xbrl`` to None; verify
    the resolver returns the text-match value from ConceptReport (AAPL's
    is 1_000_000 because its header matches the original pattern)."""
    f = Company('AAPL').get_filings(form='10-K').latest()
    viewer = f.viewer
    # Disable XBRL lazy-load so _resolve_currency_scaling takes the fallback.
    viewer._xbrl = None
    viewer._xbrl_loaded = True
    stmt = viewer.financial_statements[0]
    # The text-match value on AAPL is 1_000_000 (it matches "$ in Millions").
    assert stmt.currency_scaling == stmt.concept_report.currency_scaling
    assert stmt.currency_scaling == 1_000_000
