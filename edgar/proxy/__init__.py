"""
DEF 14A (Proxy Statement) support for SEC proxy statement filings.

This module provides the ProxyStatement class for extracting structured data
from DEF 14A filings, including executive compensation, pay vs performance
metrics, and governance information.

Main Classes:
    ProxyStatement: Main class for working with proxy statements via filing.obj()
    ExecutiveCompensation: Data model for annual compensation data
    PayVsPerformance: Data model for pay vs performance metrics
    NamedExecutive: Data model for individual executive data

Usage:
    >>> from edgar import Company
    >>> company = Company("AAPL")
    >>> filing = company.get_filings(form="DEF 14A").latest()
    >>> proxy = filing.obj()
    >>> print(f"CEO: {proxy.peo_name}")
    >>> print(f"CEO Compensation: ${proxy.peo_total_comp:,}")
    >>> df = proxy.executive_compensation  # 5-year DataFrame
"""

from .contest import ProxyContest
from .core import ProxyStatement
from .html_extractor import AuditFees, BeneficialOwner, CEOPayRatio, DirectorCompEntry, ExecutiveCompEntry, VotingProposal
from .models import (
    ANCHOR_FORMS,
    CONTEST_INDICATOR_FORMS,
    DISSIDENT_ONLY_FORMS,
    PROXY_FORMS,
    SeasonFiling,
    ExecutiveCompensation,
    NamedExecutive,
    PayVsPerformance,
    classify_proxy_tier,
)
from .season import ProxySeason

__all__ = [
    # Main classes
    'ProxyStatement',
    'ProxySeason',
    'ProxyContest',
    # Data models
    'ExecutiveCompensation',
    'PayVsPerformance',
    'NamedExecutive',
    'SeasonFiling',
    'VotingProposal',
    'CEOPayRatio',
    'ExecutiveCompEntry',
    'BeneficialOwner',
    'DirectorCompEntry',
    'AuditFees',
    # Functions
    'classify_proxy_tier',
    # Constants
    'PROXY_FORMS',
    'ANCHOR_FORMS',
    'CONTEST_INDICATOR_FORMS',
    'DISSIDENT_ONLY_FORMS',
]
