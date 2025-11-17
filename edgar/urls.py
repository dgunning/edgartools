"""
URL builder utilities for SEC EDGAR.

This module provides centralized URL construction functions that use the
configured SEC mirror URLs from edgar.config.
"""
from edgar.config import SEC_BASE_URL, SEC_DATA_URL, SEC_ARCHIVE_URL

__all__ = [
    'build_archive_url',
    'build_api_url',
    'build_submissions_url',
    'build_company_facts_url',
    'build_full_index_url',
    'build_daily_index_url',
    'build_feed_url',
    'build_ticker_url',
    'build_company_tickers_url',
    'build_mutual_fund_tickers_url',
    'build_company_tickers_exchange_url',
]


def build_archive_url(path: str) -> str:
    """Build a URL for the SEC Archives/edgar directory."""
    path = path.lstrip('/')
    return f"{SEC_ARCHIVE_URL}/{path}"


def build_api_url(path: str) -> str:
    """Build a URL for the SEC data API."""
    path = path.lstrip('/')
    return f"{SEC_DATA_URL}/api/{path}"


def build_submissions_url(cik: int) -> str:
    """Build a URL for company submissions data."""
    return f"{SEC_DATA_URL}/submissions/CIK{cik:010d}.json"


def build_company_facts_url(cik: int) -> str:
    """Build a URL for company facts data."""
    return f"{SEC_DATA_URL}/api/xbrl/companyfacts/CIK{cik:010d}.json"


def build_full_index_url(year: int, quarter: int, index_type: str, file_type: str) -> str:
    """Build a URL for full index files."""
    return f"{SEC_ARCHIVE_URL}/full-index/{year}/QTR{quarter}/{index_type}.{file_type}"


def build_daily_index_url(year: int, quarter: int, date_str: str, file_type: str) -> str:
    """Build a URL for daily index files."""
    return f"{SEC_ARCHIVE_URL}/daily-index/{year}/QTR{quarter}/{date_str}.{file_type}"


def build_feed_url(year: int, quarter: int) -> str:
    """Build a URL for SEC EDGAR feed directory."""
    return f"{SEC_ARCHIVE_URL}/Feed/{year}/QTR{quarter}/"


def build_ticker_url() -> str:
    """Build URL for ticker.txt reference file."""
    return f"{SEC_BASE_URL}/include/ticker.txt"


def build_company_tickers_url() -> str:
    """Build URL for company_tickers.json reference file."""
    return f"{SEC_BASE_URL}/files/company_tickers.json"


def build_mutual_fund_tickers_url() -> str:
    """Build URL for mutual fund tickers reference file."""
    return f"{SEC_BASE_URL}/files/company_tickers_mf.json"


def build_company_tickers_exchange_url() -> str:
    """Build URL for company tickers by exchange reference file."""
    return f"{SEC_BASE_URL}/files/company_tickers_exchange.json"
