import locale
import os
from contextlib import asynccontextmanager, contextmanager
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

from typing import Any

from httpxthrottlecache import HttpxThrottleCache


# =============================================================================
# WORKAROUND for httpxthrottlecache bug: SSL verify parameter not passed to transport
#
# Bug: httpxthrottlecache v0.2.1 (and possibly earlier versions) fails to pass the
# 'verify' parameter to the HTTP transport, causing SSL verification to remain enabled
# even when configure_http(verify_ssl=False) is called.
#
# Impact: Users behind corporate VPNs/proxies with SSL inspection cannot disable
# SSL verification, making edgartools unusable in those environments.
#
# Upstream issue: https://github.com/paultiq/httpxthrottlecache/issues/XXX (TODO: create)
#
# TODO: Remove this monkey patch once httpxthrottlecache releases a fix (check for v0.3.0+)
# =============================================================================
def _patched_get_httpx_transport_params(self, params: dict[str, Any]) -> dict[str, Any]:
    """
    Patched version that includes the 'verify' parameter for SSL configuration.

    This fixes a bug where httpxthrottlecache._get_httpx_transport_params() only
    extracts 'http2' and 'proxy' parameters, ignoring 'verify'.
    """
    http2 = params.get("http2", False)
    proxy = self.proxy
    verify = params.get("verify", True)  # Extract verify parameter (defaults to True for security)

    return {"http2": http2, "proxy": proxy, "verify": verify}


# Apply the monkey patch at module import time
HttpxThrottleCache._get_httpx_transport_params = _patched_get_httpx_transport_params
# =============================================================================

from edgar.core import get_identity, strtobool

from .core import get_edgar_data_directory

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
    import re

    from edgar.config import SEC_BASE_URL

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
    """Get the HTTP cache directory, respecting EDGAR_LOCAL_DATA_DIR env var."""
    cachedir = get_edgar_data_directory() / "_tcache"
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
    # Increase keepalive from default 5s to 30s for better connection reuse
    # This reduces TCP+TLS handshake overhead (~100ms) for interactive use
    http_mgr.httpx_params["limits"] = httpx.Limits(keepalive_expiry=30)
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


def configure_http(
    verify_ssl: Optional[bool] = None,
    proxy: Optional[str] = None,
    timeout: Optional[float] = None,
) -> None:
    """
    Configure HTTP client settings at runtime.

    This function allows you to modify HTTP settings after importing edgar,
    which is useful when you can't set environment variables before import.

    Args:
        verify_ssl: Enable/disable SSL certificate verification.
                   Set to False for corporate networks with SSL inspection.
                   WARNING: Disabling SSL verification reduces security.
        proxy: HTTP/HTTPS proxy URL (e.g., "http://proxy.company.com:8080").
               Supports authentication: "http://user:pass@proxy.company.com:8080"
        timeout: Request timeout in seconds (default: 30.0)

    Examples:
        # Disable SSL verification for corporate VPN
        from edgar import configure_http
        configure_http(verify_ssl=False)

        # Configure proxy
        configure_http(proxy="http://proxy.company.com:8080")

        # Multiple settings at once
        configure_http(verify_ssl=False, proxy="http://proxy:8080", timeout=60.0)

    Note:
        Changes take effect immediately for new requests.
        If an HTTP client was already created, it will be recreated with the new settings.
    """
    global HTTP_MGR

    settings_changed = False

    if verify_ssl is not None:
        HTTP_MGR.httpx_params["verify"] = verify_ssl
        settings_changed = True

    if proxy is not None:
        # Configure proxy for httpx
        HTTP_MGR.httpx_params["proxy"] = proxy
        settings_changed = True

    if timeout is not None:
        from httpx import Timeout
        HTTP_MGR.httpx_params["timeout"] = Timeout(timeout, connect=10.0)
        settings_changed = True

    # Force client recreation if settings changed and client already exists
    # This ensures new settings take effect even if client was already created
    if settings_changed and HTTP_MGR._client is not None:
        HTTP_MGR._client.close()
        HTTP_MGR._client = None


def get_http_config() -> dict:
    """
    Get current HTTP client configuration.

    Returns:
        dict: Current configuration including verify_ssl, proxy, and timeout settings.

    Example:
        >>> from edgar import get_http_config
        >>> config = get_http_config()
        >>> print(f"SSL verification: {config['verify_ssl']}")
    """
    params = HTTP_MGR.httpx_params
    return {
        "verify_ssl": params.get("verify", True),
        "proxy": params.get("proxy"),
        "timeout": params.get("timeout"),
    }


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
