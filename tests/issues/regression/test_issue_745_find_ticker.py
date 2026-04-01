"""Regression test for GitHub issue #745.

find_ticker() returned 'EP' (Empire Petroleum) for CIK 1506307 (Kinder Morgan)
because the heuristic stripped 'EP-PC' to 'EP' and picked it over 'KMI' by length.
"""
from edgar.reference.tickers import find_ticker


def test_kinder_morgan_returns_kmi():
    """CIK 1506307 should return KMI, not EP (from stripped EP-PC)."""
    assert find_ticker(1506307) == "KMI"


def test_berkshire_returns_real_ticker():
    """CIK 1067983 (BRK-A, BRK-B) should return a real ticker, not phantom 'BRK'."""
    result = find_ticker(1067983)
    assert result in ("BRK-A", "BRK-B")


def test_comcast_returns_cmcsa():
    """CIK 1166691 should return CMCSA (common stock), not CCZ (ETN)."""
    assert find_ticker(1166691) == "CMCSA"


def test_common_tickers_unaffected():
    """Verify the fix doesn't break standard single-ticker companies."""
    assert find_ticker(320193) == "AAPL"
    assert find_ticker(789019) == "MSFT"
    assert find_ticker(19617) == "JPM"
