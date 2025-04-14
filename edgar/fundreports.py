"""
Fund reports module for working with NPORT filings.

This module is DEPRECATED. Please use the edgar.funds.reports module instead.
"""
import warnings

warnings.warn(
    "The edgar.fundreports module is deprecated. Please use edgar.funds.reports instead. "
    "For example: from edgar.funds.reports import FundReport, CurrentMetric, NPORT_FORMS",
    PendingDeprecationWarning,
    stacklevel=2
)

# Import from the new location to maintain backward compatibility
from edgar.funds.reports import (
    FundReport,
    CurrentMetric,
    NPORT_FORMS,
    get_fund_portfolio_from_filing
)

__all__ = [
    "FundReport",
    "CurrentMetric",
    "NPORT_FORMS"
]