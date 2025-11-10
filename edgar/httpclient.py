import locale
import os
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import AsyncGenerator, Generator, Literal, Optional

import httpx

# Fix for issue #457: Force C locale for httpxthrottlecache to avoid locale-dependent date parsing
# httpxthrottlecache uses time.strptime() which is locale-dependent. On non-English systems
# (Chinese, Japanese, German, etc.), HTTP date headers fail to parse because month/day names
# are in the local language. Setting LC_TIME to 'C' ensures English date parsing.
# See: https://github.com/dgunning/edgartools/issues/457
try:
    locale.setlocale(locale.LC_TIME, 'C')
except (locale.Error, ValueError):
    # If 'C' locale is not available, try to continue anyway
    # This shouldn't happen on most systems, but better safe than sorry
    pass

from httpxthrottlecache import HttpxThrottleCache

from edgar.core import get_identity, strtobool

from .core import edgar_data_dir

MAX_SUBMISSIONS_AGE_SECONDS = 30  # Check for submissions every 30 seconds (reduced from 10 min for Issue #471)
MAX_INDEX_AGE_SECONDS = 30 * 60  # Check for updates to index (ie: daily-index) every 30 minutes

# rules are regular expressions matching the request url path: 
# The value determines whether it is cached or not:
# - int > 0: how many seconds it'll be considered valid. During this time, the cached object will not be revalidated.
# - False or 0: Do not cache
# - True: Cache forever, never revalidate
# - None: Determine cachability using response cache headers only. 
#
# Note that: revalidation consumes rate limit "hit", but will be served from cache if the data hasn't changed.


def _get_cache_rules() -> dict:
    """
    Get cache rules based on configured SEC base URL.
    This allows caching to work with custom SEC mirrors.
    """
    from edgar.config import SEC_BASE_URL
    import re

    # Extract domain pattern from base URL (e.g., "sec.gov" or "mysite.com")
    domain_match = re.match(r'https?://([^/]+)', SEC_BASE_URL)
    if domain_match:
        domain = domain_match.group(1).replace('.', r'\.')
    else:
        domain = r'.*\.sec\.gov'  # Fallback to default

    return {
        f".*{domain}": {
            "/submissions.*": MAX_SUBMISSIONS_AGE_SECONDS,
            r"/include/ticker\.txt.*": MAX_SUBMISSIONS_AGE_SECONDS,
            r"/files/company_tickers\.json.*": MAX_SUBMISSIONS_AGE_SECONDS,
            ".*index/.*": MAX_INDEX_AGE_SECONDS,
            "/Archives/edgar/data": True,  # cache forever
        }
    }

# Cache rules evaluated at module load time
CACHE_RULES = _get_cache_rules()

def get_cache_directory() -> str:
    cachedir = Path(edgar_data_dir) / "_tcache"
    cachedir.mkdir(parents=True, exist_ok=True)

    return str(cachedir)


def get_edgar_verify_ssl():
    """
    Returns True if using SSL verification on http requests
    """
    return strtobool(os.environ.get("EDGAR_VERIFY_SSL", "true"))


def get_edgar_rate_limit_per_sec():
    """
    Returns the rate limit in requests per second.
    Defaults to 9 requests/sec (SEC's rate limit).
    Use higher values for custom mirrors with relaxed limits.
    """
    return int(os.environ.get("EDGAR_RATE_LIMIT_PER_SEC", "9"))


def get_http_mgr(cache_enabled: bool = True, request_per_sec_limit: int = 9) -> HttpxThrottleCache:
    cache_mode: Literal[False, "Disabled", "Hishel-S3", "Hishel-File", "FileCache"]
    if cache_enabled:
        cache_dir = get_cache_directory()
        cache_mode = "Hishel-File"
    else:
        cache_dir = None
        cache_mode = "Disabled"

    http_mgr = HttpxThrottleCache(
        user_agent_factory=get_identity, cache_dir=cache_dir, cache_mode=cache_mode, request_per_sec_limit=request_per_sec_limit,
        cache_rules = CACHE_RULES
    )
    http_mgr.httpx_params["verify"] = get_edgar_verify_ssl()
    return http_mgr


@asynccontextmanager
async def async_http_client(client: Optional[httpx.AsyncClient] = None, **kwargs) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with HTTP_MGR.async_http_client(client=client, **kwargs) as client:
        yield client


@contextmanager
def http_client(**kwargs) -> Generator[httpx.Client, None, None]:
    with HTTP_MGR.http_client(**kwargs) as client:
        yield client


def get_http_params():
    return HTTP_MGR._populate_user_agent(HTTP_MGR.httpx_params.copy())


def close_clients():
    HTTP_MGR.close()


HTTP_MGR = get_http_mgr(request_per_sec_limit=get_edgar_rate_limit_per_sec())


def clear_locale_corrupted_cache():
    """
    One-time cache clearing function to remove locale-corrupted cache files from Issue #457.

    This function addresses a specific issue where cache files created with non-English locales
    (Chinese, Japanese, German, etc.) contain timestamps that cannot be deserialized after
    the locale fix was applied in v4.19.0.

    The function:
    1. Checks for a marker file to avoid repeated clearing
    2. Clears the HTTP cache directory if marker doesn't exist
    3. Creates a marker file to prevent future clearing

    This is safe to call multiple times - it will only clear cache once per installation.

    Returns:
        bool: True if cache was cleared, False if already cleared previously
    """
    import logging
    import shutil
    from pathlib import Path

    try:
        cache_dir = Path(get_cache_directory())
        marker_file = cache_dir / ".locale_fix_457_applied"

        # If marker exists, cache was already cleared
        try:
            if marker_file.exists():
                return False
        except (PermissionError, OSError):
            # If we can't check marker file, assume we need to proceed
            pass

        # Clear the cache directory if it exists
        if cache_dir.exists():
            # Remove all cache files
            shutil.rmtree(cache_dir)
            # Recreate the directory
            cache_dir.mkdir(parents=True, exist_ok=True)
            # Create marker file
            marker_file.touch()
            return True
        else:
            # No cache exists, just create marker
            cache_dir.mkdir(parents=True, exist_ok=True)
            marker_file.touch()
            return False

    except Exception as e:
        # Log error but don't fail - worst case user still has cache issues
        logging.getLogger(__name__).warning(
            f"Failed to clear locale-corrupted cache: {e}. "
            "You may need to manually delete ~/.edgar/_tcache directory."
        )
        return False
