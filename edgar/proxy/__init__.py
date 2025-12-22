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

from .core import ProxyStatement
from .models import (
    PROXY_FORMS,
    ExecutiveCompensation,
    NamedExecutive,
    PayVsPerformance,
)

__all__ = [
    # Main class
    'ProxyStatement',
    # Data models
    'ExecutiveCompensation',
    'PayVsPerformance',
    'NamedExecutive',
    # Constants
    'PROXY_FORMS',
]
