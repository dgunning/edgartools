"""Shared test utilities for XBRL standardization tests."""


def assert_within_tolerance(actual, expected, tolerance=0.01, label=""):
    """Assert actual value is within tolerance of expected. Tolerance is fractional (0.01 = 1%)."""
    assert actual is not None, f"{label}: actual value is None (expected {expected:,.0f})"
    if expected == 0:
        assert actual == 0, f"{label}: expected 0, got {actual}"
        return
    variance = abs(actual - expected) / abs(expected)
    assert variance <= tolerance, (
        f"{label}: variance {variance:.4%} exceeds {tolerance:.2%} tolerance. "
        f"actual={actual:,.0f}, expected={expected:,.0f}"
    )
