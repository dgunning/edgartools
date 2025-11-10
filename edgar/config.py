"""
Configuration module for SEC EDGAR URLs.

This module allows users to configure custom SEC mirror URLs via environment variables:
- EDGAR_BASE_URL: Base URL for SEC website (default: https://www.sec.gov)
- EDGAR_DATA_URL: Base URL for SEC data API (default: https://data.sec.gov)
- EDGAR_XBRL_URL: Base URL for XBRL taxonomy (default: http://xbrl.sec.gov)

Example:
    import os
    os.environ['EDGAR_BASE_URL'] = 'https://mysite.com'

    from edgar import Company
    company = Company('AAPL')  # Will use mysite.com instead of sec.gov
"""
import os

__all__ = ['SEC_BASE_URL', 'SEC_DATA_URL', 'SEC_XBRL_URL', 'SEC_ARCHIVE_URL']

# Load configuration from environment variables at module import time
# These are constants and won't change during runtime
SEC_BASE_URL = os.environ.get('EDGAR_BASE_URL', 'https://www.sec.gov').rstrip('/')
SEC_DATA_URL = os.environ.get('EDGAR_DATA_URL', 'https://data.sec.gov').rstrip('/')
SEC_XBRL_URL = os.environ.get('EDGAR_XBRL_URL', 'http://xbrl.sec.gov').rstrip('/')
SEC_ARCHIVE_URL = f"{SEC_BASE_URL}/Archives/edgar"
