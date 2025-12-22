"""
Configuration module for SEC EDGAR URLs and behavior settings.

This module allows users to configure:

URL Configuration (via environment variables):
- EDGAR_BASE_URL: Base URL for SEC website (default: https://www.sec.gov)
- EDGAR_DATA_URL: Base URL for SEC data API (default: https://data.sec.gov)
- EDGAR_XBRL_URL: Base URL for XBRL taxonomy (default: http://xbrl.sec.gov)

Behavior Configuration (via environment variables):
- EDGAR_VERBOSE_EXCEPTIONS: Enable verbose logging for caught exceptions (default: False)
  Set to 'true', '1', 'yes', or 'on' to enable detailed exception logging for debugging.
  By default, caught exceptions (like StatementNotFound) don't spam the console,
  following the Python idiom that caught exceptions should be silent.

Example:
    import os
    os.environ['EDGAR_BASE_URL'] = 'https://mysite.com'
    os.environ['EDGAR_VERBOSE_EXCEPTIONS'] = 'true'

    from edgar import Company
    company = Company('AAPL')  # Will use mysite.com instead of sec.gov
"""
import os

__all__ = ['SEC_BASE_URL', 'SEC_DATA_URL', 'SEC_XBRL_URL', 'SEC_ARCHIVE_URL', 'VERBOSE_EXCEPTIONS']

# Load configuration from environment variables at module import time
# These are constants and won't change during runtime

# URL Configuration
SEC_BASE_URL = os.environ.get('EDGAR_BASE_URL', 'https://www.sec.gov').rstrip('/')
SEC_DATA_URL = os.environ.get('EDGAR_DATA_URL', 'https://data.sec.gov').rstrip('/')
SEC_XBRL_URL = os.environ.get('EDGAR_XBRL_URL', 'http://xbrl.sec.gov').rstrip('/')
SEC_ARCHIVE_URL = f"{SEC_BASE_URL}/Archives/edgar"

# Behavior Configuration
def _parse_bool_env(env_var: str, default: bool = False) -> bool:
    """Parse boolean from environment variable."""
    value = os.environ.get(env_var, '').lower()
    if value in ('true', '1', 'yes', 'on'):
        return True
    elif value in ('false', '0', 'no', 'off', ''):
        return False
    return default

VERBOSE_EXCEPTIONS = _parse_bool_env('EDGAR_VERBOSE_EXCEPTIONS', default=False)
