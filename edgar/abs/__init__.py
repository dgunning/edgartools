"""
Asset-Backed Securities (ABS) filing support.

This module provides data object classes for parsing and analyzing
ABS-related SEC filings, including Form 10-D distribution reports.

Current support:
- AssetData: Form ABS-EE EX-102 asset-level data for every ABS-EE schema, streamed
  and typed from SEC's XSDs (auto loan, auto lease and CMBS curated; RMBS and
  debt securities raw). `filing.obj()` on an ABS-EE filing returns one.
- TenD: Form 10-D data object for CMBS filings with XML asset data
- CMBSAssetData: CMBS loans and properties under TenD's column names
- AutoLeaseAssetData: deprecated, use AssetData

Note: TenD only returns a data object for CMBS filings (with EX-102 XML).
Non-CMBS 10-D filings return None from filing.obj() since they lack
structured data worth extracting.
"""

from edgar.abs.abs_ee import AutoLeaseAssetData, AutoLeaseSummary
from edgar.abs.asset_data import ABS_EE_FORMS, AssetData, AssetDataInfo, AssetDataSummary
from edgar.abs.cmbs import CMBSAssetData, CMBSSummary
from edgar.abs.ten_d import TenD

__all__ = [
    'AssetData',
    'AssetDataInfo',
    'AssetDataSummary',
    'ABS_EE_FORMS',
    'TenD',
    'CMBSAssetData',
    'CMBSSummary',
    'AutoLeaseAssetData',
    'AutoLeaseSummary',
]
