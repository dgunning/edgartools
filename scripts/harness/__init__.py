"""Edgar Test Harness - Comprehensive testing system for EdgarTools.

This package provides a persistent test harness system for validating EdgarTools
functionality across live SEC filings. It supports multiple test types, flexible
filing selection, SQLite-based result storage, and rich reporting capabilities.

Basic usage:
    >>> from scripts.harness import HarnessStorage, FilingSelector
    >>> storage = HarnessStorage()
    >>> session = storage.create_session("My Test Session")
    >>> # More functionality coming in subsequent phases
"""

from .models import Session, TestRun, TestResult, FilingMetadata
from .storage import HarnessStorage
from .selectors import FilingSelector
from .runner import (
    TestRunner,
    ComparisonTestRunner,
    ValidationTestRunner,
    PerformanceTestRunner,
    RegressionTestRunner
)
from .reporters import ResultReporter, TrendAnalyzer

__all__ = [
    'Session',
    'TestRun',
    'TestResult',
    'FilingMetadata',
    'HarnessStorage',
    'FilingSelector',
    'TestRunner',
    'ComparisonTestRunner',
    'ValidationTestRunner',
    'PerformanceTestRunner',
    'RegressionTestRunner',
    'ResultReporter',
    'TrendAnalyzer',
]

__version__ = '0.1.0'
