"""
13F Holdings Report Parser

Parses SEC Form 13F-HR (Quarterly Holdings Report) filings from institutional investment managers.
Supports both XML format (2013+) and TXT format (2012 and earlier).
"""

from edgar.thirteenf.models import (
    THIRTEENF_FORMS,
    CoverPage,
    FilingManager,
    HoldingsComparison,
    HoldingsHistory,
    HoldingsView,
    OtherManager,
    PrimaryDocument13F,
    Signature,
    SummaryPage,
    ThirteenF,
    format_date,
)

# For backward compatibility, also export parser functions
from edgar.thirteenf.parsers import (
    parse_infotable_txt,
    parse_infotable_xml,
    parse_primary_document_xml,
)

__all__ = [
    'ThirteenF',
    'THIRTEENF_FORMS',
    'FilingManager',
    'OtherManager',
    'CoverPage',
    'SummaryPage',
    'Signature',
    'PrimaryDocument13F',
    'HoldingsView',
    'HoldingsComparison',
    'HoldingsHistory',
    'format_date',
    'parse_primary_document_xml',
    'parse_infotable_xml',
    'parse_infotable_txt',
]
