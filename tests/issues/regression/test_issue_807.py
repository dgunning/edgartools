"""
Regression test for GH #807: viewer.concept_report.currency_scaling unreliable.

The original implementation derived ``ConceptReport.currency_scaling`` from a
narrow text match on the R*.htm ``<th class='tl'>`` header (``$ in millions``
/ ``$in millions``). Filers using variations (``In Millions``, ``(in
millions)``, ``USD ($) in Millions``, …) fell through to the default of 1,
producing inconsistent scaling across same-filing statements (e.g. ALGN
balance sheet vs income statement) and wrong values for whole multi-year
ranges (ABNB showing 1 for 2023/2024 when the actual scale is millions).

The first fix resolved ``ViewerReport.currency_scaling`` from the XBRL
``decimals`` attribute, on the issue's assumption that every statement in a
filing shares one scale. The SEC pages contradict that assumption (ABNB
0001559720-25-000010 shows its balance sheet in millions and its statement of
operations in whole dollars; AMGN 0000318154-26-000010 shows its income
statement in thousands and its balance sheet in millions), and the decimals
value was wrong by a factor of a million on such pages. ``currency_scaling``
now returns the scale each page declares, parsed from any
``<symbol> in <Scale>`` statement, and falls back to ``decimals`` only when a
report has no title cell.

What these tests pin:
1. ALGN balance sheet and income statement scaling agree (both in thousands)
2. ABNB scaling is the page-declared scale for each of four fiscal years
3. Canary 5-ticker subset reports the scale each page declares

GitHub Issue: https://github.com/dgunning/edgartools/issues/807
"""
from __future__ import annotations

import pytest

from edgar import Company, find


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


def _income_statement(viewer):
    return (
        _primary_statement(viewer, 'statements', 'of', 'operations')
        or _primary_statement(viewer, 'statements', 'of', 'income')
        or _primary_statement(viewer, 'income', 'statements')
    )


# (accession, balance-sheet scale, income-statement scale), each read from the
# "<symbol> in <Scale>" statement in the title cell of the filing's R pages.
# A page with no currency statement shows whole dollars, so its scale is 1.
ABNB_PAGE_SCALES = [
    # FY2025: R3 "$ in Millions"; R5 "shares in Millions, $ in Millions" (revenue "$ 12,241")
    ('0001559720-26-000004', 1_000_000, 1_000_000),
    # FY2024: R3 "$ in Millions" (cash "$ 6,864"); R5 "shares in Millions" only (revenue "$ 11,102,000,000")
    ('0001559720-25-000010', 1_000_000, 1),
    # FY2023: R3 "$ in Millions"; R5 "shares in Millions" only (revenue "$ 9,917,000,000")
    ('0001559720-24-000006', 1_000_000, 1),
    # FY2022: R3 "$ in Millions"; R5 "shares in Millions, $ in Millions" (revenue "$ 8,399.0")
    ('0001559720-23-000003', 1_000_000, 1_000_000),
]

CANARY_PAGE_SCALES = [
    # AAPL FY2026: R5 and R3 both "$ in Millions"
    ('AAPL', '0000320193-26-000026', 1_000_000, 1_000_000),
    # ABNB FY2025: R3 and R5 both "$ in Millions"
    ('ABNB', '0001559720-26-000004', 1_000_000, 1_000_000),
    # ALGN FY2025: R5 and R3 both "$ in Thousands"
    ('ALGN', '0001097149-26-000014', 1_000, 1_000),
    # ACN FY2026: R3 and R5 both "$ in Thousands"
    ('ACN', '0001467373-26-000049', 1_000, 1_000),
    # AMGN FY2025: R5 balance sheet "$ in Millions" (cash "$ 9,129");
    # R3 income statement "$ in Thousands" (revenues "$ 36,751,000")
    ('AMGN', '0000318154-26-000010', 1_000_000, 1_000),
]


@pytest.mark.network
@pytest.mark.parametrize('accession, bs_scale, is_scale', ABNB_PAGE_SCALES)
def test_abnb_scaling_is_the_page_declared_scale_each_year(accession, bs_scale, is_scale):
    """ABNB was the reporter's multi-year case. The issue assumed one filing
    never mixes scales, but ABNB's FY2023 and FY2024 statements of operations
    are rendered in whole dollars beside a balance sheet in millions, so the
    two pages legitimately differ. ``currency_scaling`` is the factor that
    turns a displayed value into the raw amount, which makes the page's own
    declaration the only correct answer: 11,102,000,000 x 1, not x 1,000,000."""
    viewer = find(accession).viewer
    bs = _primary_statement(viewer, 'balance', 'sheet')
    is_ = _income_statement(viewer)
    assert bs is not None and is_ is not None, f"ABNB {accession}: primary statements not found"
    assert bs.currency_scaling == bs_scale, (
        f"ABNB {accession}: BS scale {bs.currency_scaling}, page declares {bs_scale}"
    )
    assert is_.currency_scaling == is_scale, (
        f"ABNB {accession}: IS scale {is_.currency_scaling}, page declares {is_scale}"
    )


@pytest.mark.network
@pytest.mark.parametrize('ticker, accession, bs_scale, is_scale', CANARY_PAGE_SCALES)
def test_canary_tickers_report_page_declared_scales(ticker, accession, bs_scale, is_scale):
    """5-ticker subset from the reporter's table, pinned to the filing each
    value was read from. Every primary statement reports the scale its own
    page declares; AMGN shows that the balance sheet and income statement of
    one filing can differ (millions and thousands)."""
    viewer = find(accession).viewer
    bs = _primary_statement(viewer, 'balance', 'sheet')
    is_ = _income_statement(viewer)
    assert bs is not None and is_ is not None, f"{ticker} {accession}: primary statements not found"
    assert bs.currency_scaling == bs_scale, (
        f"{ticker} {accession}: BS scale {bs.currency_scaling}, page declares {bs_scale}"
    )
    assert is_.currency_scaling == is_scale, (
        f"{ticker} {accession}: IS scale {is_.currency_scaling}, page declares {is_scale}"
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
