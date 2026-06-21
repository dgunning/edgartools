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


def get_edgar_use_system_certs() -> bool:
    """
    Returns True if using system certificate store via truststore.
    Set EDGAR_USE_SYSTEM_CERTS=true to enable.
    """
    return strtobool(os.environ.get("EDGAR_USE_SYSTEM_CERTS", "false"))


def get_edgar_use_http2() -> bool:
    """
    Returns True if the internal httpx client should negotiate HTTP/2.

    Defaults to False (HTTP/1.1). EdgarTools talks to SEC EDGAR with a small
    number of large, rate-limited (~9 req/s) requests, so HTTP/2's stream
    multiplexing buys little, while its single-connection model turns a
    transient reset into a correlated failure across every in-flight request.
    From cloud egress this surfaces as intermittent
    ``h2.exceptions.InvalidBodyLengthError`` (truncated body) and
    ``httpx.RemoteProtocolError: ConnectionTerminated`` mid-download, crashing
    long fan-out jobs. HTTP/1.1 isolates each request to its own connection so
    the retry layer can recover. Set EDGAR_USE_HTTP2=true to opt back into HTTP/2.

    See: https://github.com/dgunning/edgartools/issues (edgartools-x2tv)
    """
    return strtobool(os.environ.get("EDGAR_USE_HTTP2", "false"))


def get_truststore_context():
    """
    Get a truststore SSLContext that uses the OS native certificate store.
    """
    import ssl

    import truststore
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def get_edgar_http_timeout() -> Optional[float]:
    """
    Default request timeout in seconds for the internal httpx client.

    Without an explicit timeout, a stalled upstream or slow TLS handshake
    can cause a blocking socket read that never returns — the process is
    not interruptible until the syscall completes. Override via the
    EDGAR_HTTP_TIMEOUT environment variable (seconds); pass an explicit
    timeout to configure_http() to change it at runtime.

    Returns None for "unlimited" (no timeout set on the client), which is
    signalled by the env var being empty or one of "none"/"unlimited"/"0"
    (case-insensitive). Non-positive numerics also route through the
    unlimited path so EDGAR_HTTP_TIMEOUT=0 cannot configure httpx with
    a 0.0 read timeout (which httpx treats as immediate-timeout).
    """
    raw = os.environ.get("EDGAR_HTTP_TIMEOUT", "30.0")
    if raw.strip() == "" or raw.strip().lower() in ("none", "unlimited"):
        return None
    value = float(raw)
    if value <= 0:
        return None
    return value


def get_edgar_rate_limit_per_sec():
    """
    Returns the rate limit in requests per second.
    Defaults to 9 requests/sec (SEC's rate limit).
    Use higher values for custom mirrors with relaxed limits.
    """
    return int(os.environ.get("EDGAR_RATE_LIMIT_PER_SEC", "9"))


def _create_rate_limiter(requests_per_second: int):
    """Create a rate limiter compatible with both pyrate-limiter 3.x and 4.x.

    pyrate-limiter 4.0 removed max_delay, raise_when_fail, and retry_until_max_delay
    parameters from Limiter.__init__(). This function handles both API versions.
    See: https://github.com/dgunning/edgartools/issues/640
    """
    from pyrate_limiter import Duration, InMemoryBucket, Limiter, Rate

    rate = Rate(requests_per_second, Duration.SECOND)
    bucket = InMemoryBucket([rate])
    try:
        # pyrate-limiter 3.x API
        return Limiter(bucket, max_delay=Duration.DAY, raise_when_fail=False, retry_until_max_delay=True)
    except TypeError:
        # pyrate-limiter 4.0+ removed these parameters
        return Limiter(bucket)


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
        rate_limiter=_create_rate_limiter(request_per_sec_limit),
        cache_rules = CACHE_RULES
    )
    # Determine SSL verification setting
    # Priority: system certs (truststore) > verify_ssl env var
    if get_edgar_use_system_certs():
        http_mgr.httpx_params["verify"] = get_truststore_context()
    else:
        http_mgr.httpx_params["verify"] = get_edgar_verify_ssl()

    # Default to HTTP/1.1 (http2=False). HTTP/2 multiplexes every request over a
    # single TCP connection, so a mid-stream reset from cloud egress fails all
    # in-flight requests at once (InvalidBodyLengthError / ConnectionTerminated).
    # SEC's ~9 req/s rate limit means HTTP/2's multiplexing offers no real upside
    # here. Override with EDGAR_USE_HTTP2=true or configure_http(http2=True).
    http_mgr.httpx_params["http2"] = get_edgar_use_http2()

    # Increase keepalive from default 5s to 30s for better connection reuse
    # This reduces TCP+TLS handshake overhead (~100ms) for interactive use
    http_mgr.httpx_params["limits"] = httpx.Limits(keepalive_expiry=30)

    # Set a non-None default timeout so a stalled upstream cannot wedge
    # a worker indefinitely. Override via EDGAR_HTTP_TIMEOUT env var or
    # configure_http(timeout=...). Set EDGAR_HTTP_TIMEOUT=none (or call
    # disable_http_timeout() at runtime) to opt out entirely.
    timeout = get_edgar_http_timeout()
    if timeout is not None:
        http_mgr.httpx_params["timeout"] = httpx.Timeout(timeout, connect=10.0)
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
    use_system_certs: Optional[bool] = None,
    proxy: Optional[str] = None,
    timeout: Optional[float] = None,
    http2: Optional[bool] = None,
) -> None:
    """
    Configure HTTP client settings at runtime.

    This function allows you to modify HTTP settings after importing edgar,
    which is useful when you can't set environment variables before import.

    Args:
        verify_ssl: Enable/disable SSL certificate verification.
                   Set to False if use_system_certs doesn't resolve your SSL issues.
                   WARNING: Disabling SSL verification reduces security.
        use_system_certs: Use the OS native certificate store via the truststore library.
                         This is the recommended approach for corporate networks with
                         SSL inspection, as it uses certificates managed by your OS.
        proxy: HTTP/HTTPS proxy URL (e.g., "http://proxy.company.com:8080").
               Supports authentication: "http://user:pass@proxy.company.com:8080"
        timeout: Request timeout in seconds (default: 30.0). Passing None
                 leaves the current timeout unchanged — to disable the
                 timeout entirely, call disable_http_timeout() instead.
        http2: Enable/disable HTTP/2 negotiation. Defaults to HTTP/1.1
               (http2=False) because HTTP/2 multiplexes all requests over one
               connection, so a mid-stream reset from cloud egress fails every
               in-flight request at once (InvalidBodyLengthError /
               ConnectionTerminated). Set to True to opt back into HTTP/2.

    Examples:
        # Use OS certificate store (recommended for corporate networks)
        from edgar import configure_http
        configure_http(use_system_certs=True)

        # Disable SSL verification (fallback if system certs don't work)
        configure_http(verify_ssl=False)

        # Disable system certs and SSL verification
        configure_http(use_system_certs=False, verify_ssl=False)

        # Configure proxy
        configure_http(proxy="http://proxy.company.com:8080")

        # Opt back into HTTP/2 (default is HTTP/1.1)
        configure_http(http2=True)

    Note:
        Changes take effect immediately for new requests.
        If an HTTP client was already created, it will be recreated with the new settings.
        use_system_certs=True takes precedence over verify_ssl when both are set.
    """
    global HTTP_MGR

    settings_changed = False

    if use_system_certs is not None:
        if use_system_certs:
            HTTP_MGR.httpx_params["verify"] = get_truststore_context()
            settings_changed = True
        else:
            # Disable system certs. If verify_ssl is also provided, use that.
            # Otherwise, only reset if currently using an SSLContext.
            import truststore
            current = HTTP_MGR.httpx_params.get("verify", True)
            if verify_ssl is not None:
                HTTP_MGR.httpx_params["verify"] = verify_ssl
            elif isinstance(current, truststore.SSLContext):
                HTTP_MGR.httpx_params["verify"] = get_edgar_verify_ssl()
            settings_changed = True
    elif verify_ssl is not None:
        HTTP_MGR.httpx_params["verify"] = verify_ssl
        settings_changed = True

    if proxy is not None:
        # Configure proxy for httpx
        HTTP_MGR.httpx_params["proxy"] = proxy
        settings_changed = True

    if http2 is not None:
        HTTP_MGR.httpx_params["http2"] = http2
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


def disable_http_timeout() -> None:
    """Remove the default HTTP timeout — requests will wait indefinitely.

    Use only when blocking reads on stalled upstreams is acceptable
    (for example, long-running batch jobs with external supervision).
    By default the client has a 30s read/write/pool timeout configured;
    that timeout exists to prevent a single stalled SEC request from
    wedging a worker forever, so removing it should be a deliberate choice.

    `configure_http(timeout=None)` is intentionally a no-op (matches the
    "leave unchanged" semantics of the other parameters), which is why
    opting out lives behind this dedicated function.
    """
    HTTP_MGR.httpx_params.pop("timeout", None)
    if HTTP_MGR._client is not None:
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
    verify = params.get("verify", True)

    # Detect if truststore SSLContext is in use
    using_system_certs = False
    try:
        import truststore
        using_system_certs = isinstance(verify, truststore.SSLContext)
    except ImportError:
        pass

    return {
        "verify_ssl": verify if not using_system_certs else True,
        "use_system_certs": using_system_certs,
        "proxy": params.get("proxy"),
        "timeout": params.get("timeout"),
        "http2": params.get("http2", False),
    }


HTTP_MGR = get_http_mgr(request_per_sec_limit=get_edgar_rate_limit_per_sec())


def clear_empty_cached_responses():
    """
    One-time cache clearing function to remove potentially stale empty responses (Issue #672).

    The cache-forever rule for /Archives/edgar/data could permanently cache empty or
    error responses from transient SEC outages. Since we cannot distinguish good from
    bad cached entries without inspecting each file, this performs a full cache clear
    once per installation when upgrading to the version with the fix.

    After clearing, the retry-with-bypass logic in FilingSGML.from_source() prevents
    future empty responses from being permanently cached.

    Returns:
        bool: True if cache was cleared, False if already cleared previously
    """
    import logging
    import shutil
    from pathlib import Path

    try:
        cache_dir = Path(get_cache_directory())
        marker_file = cache_dir / ".empty_response_fix_672_applied"

        # If marker exists, cache was already cleared
        try:
            if marker_file.exists():
                return False
        except (PermissionError, OSError):
            pass

        # Clear the cache directory if it exists
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            marker_file.touch()
            return True
        else:
            cache_dir.mkdir(parents=True, exist_ok=True)
            marker_file.touch()
            return False

    except Exception as e:
        logging.getLogger(__name__).warning(
            f"Failed to clear stale cache entries (Issue #672): {e}. "
            "You may need to manually delete ~/.edgar/_tcache directory."
        )
        return False


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
