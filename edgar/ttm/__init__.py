"""TTM (Trailing Twelve Months) calculations for EdgarTools.

This package provides:
- TTM calculations for financial metrics
- Q4 derivation from fiscal year and YTD data
- Stock split detection and adjustment

TTM functionality is integrated directly into the Company class:
    >>> from edgar import Company
    >>> company = Company("AAPL")
    >>> ttm_revenue = company.get_ttm_revenue()
    >>> print(f"TTM Revenue: ${ttm_revenue.value / 1e9:.1f}B")

For direct access to TTM calculation utilities:
    >>> from edgar.ttm import TTMCalculator, detect_splits

"""
from edgar.ttm.calculator import (
    DurationBucket,
    TTMCalculator,
    TTMMetric,
)
from edgar.ttm.splits import apply_split_adjustments, detect_splits
from edgar.ttm.statement import TTMStatement, TTMStatementBuilder

__all__ = [
    # Core TTM calculation
    "TTMCalculator",
    "TTMMetric",
    "DurationBucket",
    # Statement building
    "TTMStatement",
    "TTMStatementBuilder",
    # Stock splits
    "detect_splits",
    "apply_split_adjustments",
]
