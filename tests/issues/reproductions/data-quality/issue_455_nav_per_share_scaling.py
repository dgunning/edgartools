"""
Issue #455: Wrong NET ASSET VALUE PER SHARE for MainStreet Capital

**Problem**: NET ASSET VALUE PER SHARE showing $0.03 instead of $31.65

**Root Cause**:
- Balance sheet has dominant scale of -3 (thousands)
- NAV Per Share is in "dollars per share" (not scaled)
- The concept us-gaap_NetAssetValuePerShare was not in the eps_concepts list
- Therefore, dominant scale was applied incorrectly: 31.65 / 1000 = 0.03

**Solution**:
Added us-gaap_NetAssetValuePerShare to eps_concepts list in rendering.py
so it's formatted as a per-share value without statement-level scaling.

**Reporter**: GitHub user (via issue #455)
**Company**: MAIN (MainStreet Capital)
**Form**: 10-K
**Period**: 2024
**Filing Date**: 2025-02-28

**Expected**: NET ASSET VALUE PER SHARE = 31.65
**Actual (before fix)**: NET ASSET VALUE PER SHARE = $0.03
**Actual (after fix)**: NET ASSET VALUE PER SHARE = 31.65
"""

from edgar import Company


def test_main_nav_per_share_not_scaled():
    """
    Verify that NET ASSET VALUE PER SHARE is not incorrectly scaled.

    MainStreet Capital's balance sheet is in thousands, but NAV per share
    should be shown in dollars per share without scaling.
    """
    company = Company("MAIN")
    balance_sheet = company.get_financials().balance_sheet()

    # Convert to dataframe for inspection
    df = balance_sheet.to_dataframe()

    # Find NAV Per Share row
    nav_rows = df[df['concept'] == 'us-gaap_NetAssetValuePerShare']

    # Verify we found the row
    assert not nav_rows.empty, "NET ASSET VALUE PER SHARE not found in balance sheet"

    # Get the value for Dec 31, 2024
    nav_value = nav_rows.iloc[0]['2024-12-31']

    # Verify the value is correct (31.65, not 0.03)
    # Use approximate comparison for floating point
    assert abs(nav_value - 31.65) < 0.01, f"Expected NAV Per Share ~31.65, got {nav_value}"

    # Verify the value is NOT incorrectly scaled
    assert nav_value > 10.0, f"NAV Per Share appears to be incorrectly scaled: {nav_value}"

    # Verify rendering shows correct value (not $0.03)
    rendered = str(balance_sheet)
    assert '31.65' in rendered or '31.6' in rendered, \
        f"Rendered balance sheet should show NAV Per Share as 31.65, not 0.03"
    assert '$0.03' not in rendered or 'NET ASSET VALUE PER SHARE' not in rendered.split('$0.03')[0].split('\n')[-1], \
        f"Rendered balance sheet should not show NAV Per Share as $0.03"


def test_nav_per_share_concept_in_eps_list():
    """
    Verify that us-gaap_NetAssetValuePerShare is in the eps_concepts list
    to ensure it receives proper per-share formatting.
    """
    from edgar.xbrl.rendering import eps_concepts

    assert 'us-gaap_NetAssetValuePerShare' in eps_concepts, \
        "us-gaap_NetAssetValuePerShare must be in eps_concepts to prevent incorrect scaling"


if __name__ == '__main__':
    test_main_nav_per_share_not_scaled()
    test_nav_per_share_concept_in_eps_list()
    print("All tests passed!")
