"""
Asset-Backed Securities (ABS) filing support.

This module provides data object classes for parsing and analyzing
ABS-related SEC filings, including Form 10-D distribution reports.

Current support:
- TenD: Form 10-D data object for CMBS filings with XML asset data
- CMBSAssetData: Parser for CMBS EX-102 XML asset-level data (loans, properties)
- AutoLeaseAssetData: Parser for Form ABS-EE auto lease XML data (BMW, etc.)

Note: TenD only returns a data object for CMBS filings (with EX-102 XML).
Non-CMBS 10-D filings return None from filing.obj() since they lack
structured data worth extracting.

Note: HTML distribution report parsing (DistributionReport) is deferred due to
format variability across issuers (~42% extraction accuracy). The code is
preserved in distribution.py for future work.
"""

from edgar.abs.abs_ee import AutoLeaseAssetData, AutoLeaseSummary
from edgar.abs.cmbs import CMBSAssetData, CMBSSummary
from edgar.abs.ten_d import TenD

__all__ = [
    'TenD',
    'CMBSAssetData',
    'CMBSSummary',
    'AutoLeaseAssetData',
    'AutoLeaseSummary',
]
