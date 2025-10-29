"""
13F Holdings Report Parser

Parses SEC Form 13F-HR (Quarterly Holdings Report) filings from institutional investment managers.
Supports both XML format (2013+) and TXT format (2012 and earlier).
"""

from edgar.thirteenf.models import (
    ThirteenF,
    THIRTEENF_FORMS,
    FilingManager,
    OtherManager,
    CoverPage,
    SummaryPage,
    Signature,
    PrimaryDocument13F,
    format_date,
)

# For backward compatibility, also export parser functions
from edgar.thirteenf.parsers import (
    parse_primary_document_xml,
    parse_infotable_xml,
    parse_infotable_txt,
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
    'format_date',
    'parse_primary_document_xml',
    'parse_infotable_xml',
    'parse_infotable_txt',
]
