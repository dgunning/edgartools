"""
Issue #455: Wrong NET ASSET VALUE PER SHARE for Main Street Capital

**Problem**: NET ASSET VALUE PER SHARE showing $0.03 instead of $31.65

**Root Cause**:
- Balance sheet has dominant scale of -3 (thousands)
- NAV Per Share is in "dollars per share" (not scaled)
- The concept us-gaap_NetAssetValuePerShare was not in the eps_concepts list
- Therefore, dominant scale was applied incorrectly: 31.65 / 1000 = 0.03

**Solution**:
Added us-gaap_NetAssetValuePerShare to eps_concepts list in rendering.py
so it's formatted as a per-share value without statement-level scaling.

**GitHub Issue**: https://github.com/dgunning/edgartools/issues/455
**Company**: MAIN (Main Street Capital), CIK 1396440
**Filing**: 10-K for FY2024, accession 0001396440-25-000018, filed 2025-02-28

**Expected**: NET ASSET VALUE PER SHARE = 31.65
**Actual (before fix)**: NET ASSET VALUE PER SHARE = $0.03
**Actual (after fix)**: NET ASSET VALUE PER SHARE = 31.65

This test lived at `tests/issues/reproductions/data-quality/` under a name
pytest does not collect, so it had never run. It is a real test with a
hand-checked value, which is why it was promoted here rather than deleted with
the rest of that directory.

It is pinned to one accession on purpose. It previously read
`Company("MAIN").get_financials()`, which follows whichever 10-K is newest, and
then indexed a hardcoded `'2024-12-31'` column -- so it was one MAIN annual
filing away from a KeyError, and 31.65 is only the right answer for FY2024. The
scaling bug lives in `edgar/xbrl/rendering.py`, which a pinned filing reaches
the same way.
"""

import pytest

from tests._offline_filings import offline_filing

MAIN_FY2024_10K = "0001396440-25-000018"

# NAV per share reported on the FY2024 balance sheet, read from the filing.
EXPECTED_NAV_PER_SHARE = 31.65


@pytest.fixture(scope="module")
def main_balance_sheet():
    """Main Street Capital's FY2024 balance sheet, rendered through XBRL."""
    return offline_filing(MAIN_FY2024_10K).xbrl().statements.balance_sheet()


def test_main_nav_per_share_not_scaled(main_balance_sheet):
    """NET ASSET VALUE PER SHARE keeps dollars-per-share, not statement scale.

    Main Street Capital reports its balance sheet in thousands. NAV per share
    is already a per-share figure, so applying that scale turns 31.65 into 0.03.
    """
    df = main_balance_sheet.to_dataframe()

    nav_rows = df[df['concept'] == 'us-gaap_NetAssetValuePerShare']
    assert not nav_rows.empty, (
        "us-gaap_NetAssetValuePerShare should appear in MAIN's FY2024 balance "
        f"sheet; got concepts {sorted(df['concept'].unique())[:20]}"
    )

    period_col = '2024-12-31'
    assert period_col in nav_rows.columns, (
        f"MAIN's FY2024 10-K should carry a {period_col} column; got "
        f"{list(nav_rows.columns)}"
    )

    nav_value = nav_rows.iloc[0][period_col]
    assert abs(nav_value - EXPECTED_NAV_PER_SHARE) < 0.01, (
        f"Expected NAV per share ~{EXPECTED_NAV_PER_SHARE}, got {nav_value}. "
        f"A value near {EXPECTED_NAV_PER_SHARE / 1000:.2f} means the "
        f"statement's thousands scale was applied to a per-share figure."
    )


def test_main_nav_per_share_renders_unscaled(main_balance_sheet):
    """The rendered statement shows 31.65, which is what the reporter saw wrong."""
    rendered = str(main_balance_sheet)
    assert '31.65' in rendered or '31.6' in rendered, (
        "the rendered balance sheet should show NAV per share as 31.65; the bug "
        "in #455 was that it showed $0.03"
    )


def test_nav_per_share_concept_in_eps_list():
    """us-gaap_NetAssetValuePerShare is in eps_concepts, which is the fix itself.

    Runs offline: this is the guard that keeps the concept from being dropped
    out of the list again, independent of any filing.
    """
    from edgar.xbrl.rendering import eps_concepts

    assert 'us-gaap_NetAssetValuePerShare' in eps_concepts, (
        "us-gaap_NetAssetValuePerShare must be in eps_concepts, or statement-level "
        "scaling is applied to a per-share value again (issue #455)"
    )
