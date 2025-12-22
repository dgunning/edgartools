"""
N-PX Filing support - SEC Form N-PX (Annual Report of Proxy Voting Record).

This module provides classes for parsing and working with N-PX filings,
which are filed by registered investment companies to report their proxy voting records.

Main Classes:
    NPX: Main class for working with N-PX filings via filing.obj()
    ProxyVotes: Container for proxy voting records with analysis methods
    PrimaryDoc: Raw form data from the primary document
    ProxyTable: Individual proxy vote matter
    VoteRecord: Individual vote record within a proxy table

Usage:
    >>> from edgar import Company
    >>> filing = Company("VANGUARD").get_filings(form="N-PX")[0]
    >>> npx = filing.obj()
    >>> npx.fund_name
    'Vanguard Index Funds'
    >>> df = npx.proxy_votes.to_dataframe()
"""

from .models import (
    ClassInfo,
    IncludedManager,
    PrimaryDoc,
    ProxyTable,
    ProxyVoteTable,
    ReportSeriesClassInfo,
    SeriesReport,
    VoteCategory,
    VoteRecord,
)
from .npx import NPX, ProxyVotes
from .parsing import (
    PrimaryDocExtractor,
    ProxyVoteTableExtractor,
)

__all__ = [
    # Main classes
    'NPX',
    'ProxyVotes',
    # Data classes
    'PrimaryDoc',
    'ProxyTable',
    'ProxyVoteTable',
    'VoteRecord',
    'VoteCategory',
    'IncludedManager',
    'ClassInfo',
    'ReportSeriesClassInfo',
    'SeriesReport',
    # Extractors (for advanced use)
    'PrimaryDocExtractor',
    'ProxyVoteTableExtractor',
]
