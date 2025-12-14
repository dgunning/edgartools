"""
Asset-Backed Securities (ABS) filing support.

This module provides data object classes for parsing and analyzing
ABS-related SEC filings, including Form 10-D distribution reports.
"""

from edgar.abs.ten_d import TenD

__all__ = ['TenD']
