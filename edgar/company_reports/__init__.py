"""
Company report filing classes for Form 10-K, 10-Q, 20-F, 40-F, 8-K, and 6-K.

This package provides structured access to company reports and their contents.
All classes are re-exported at the package level for backward compatibility.
"""

# Base class and structures
from edgar.company_reports._base import CompanyReport
from edgar.company_reports._structures import (
    FilingStructure,
    ItemOnlyFilingStructure,
    is_valid_item_for_filing,
)
from edgar.company_reports.current_report import CurrentReport, EightK, SixK
from edgar.company_reports.auditor import AuditorInfo
from edgar.company_reports.press_release import PressRelease, PressReleases
from edgar.company_reports.subsidiaries import Subsidiary, SubsidiaryList

# Filing classes
from edgar.company_reports.ten_k import TenK
from edgar.company_reports.ten_q import TenQ
from edgar.company_reports.twenty_f import TwentyF
from edgar.company_reports.forty_f import FortyF

# Import Financials for backward compatibility
from edgar.financials import Financials

__all__ = [
    # Base and structures
    'CompanyReport',
    'Financials',
    'FilingStructure',
    'ItemOnlyFilingStructure',
    'is_valid_item_for_filing',
    # Filing classes
    'TenK',
    'TenQ',
    'TwentyF',
    'FortyF',
    'CurrentReport',
    'EightK',
    'SixK',
    # Auditor
    'AuditorInfo',
    # Press releases
    'PressRelease',
    'PressReleases',
    # Subsidiaries
    'Subsidiary',
    'SubsidiaryList',
]
