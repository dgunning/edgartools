import locale
import os
import re
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

# We used to monkeypatch HttpxThrottleCache._get_httpx_transport_params below this
# import, because it dropped the 'verify' parameter on the floor and users behind
# SSL-inspecting corporate proxies could not turn verification off. httpxthrottlecache
# now extracts 'verify' itself, so the patch was redundant — and worse than redundant,
# since shadowing an upstream method silently reverts any future fix to it.
# test_verify_reaches_the_transport_params pins the behaviour the patch protected.
from httpxthrottlecache import HttpxThrottleCache

from edgar.core import log, strtobool
from edgar.settings import get_edgar_data_directory, get_identity

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


def _host_key(url: str) -> str:
    """Build a cache-rule key that matches exactly one host.

    httpxthrottlecache keys its cache rules by a regex matched against
    ``request.url.host`` (``controller.get_rules``), and returns the FIRST key
    that matches. Two consequences shape this function:

    * **The only regex we want here is equality.** An unanchored key leaks across
      hosts: ``.*mirror\\.com`` also matches ``data.mirror.com``, so a base-host
      rule set would answer for the data host and the data rules would never be
      reached — the same shape as the bug this fixes, moved from sec.gov to
      mirrors.
    * **The host must come from the same parser that produces it at match time.**
      ``httpx.URL(...).host`` lowercases, drops ``user@`` and the port, and
      normalises IDNA; a hand-rolled ``https?://([^/]+)`` regex does none of
      those, so ``EDGAR_DATA_URL=https://DATA.mirror.example.org`` (or a URL
      carrying a port or credentials) yields a key no real request can match.

    An unparseable URL yields a key that matches nothing: a misconfigured mirror
    goes uncached, which is slow, rather than borrowing another host's rules,
    which would be wrong.
    """
    host = httpx.URL(url).host
    if not host:
        log.warning("No host in %r; requests to it will not be cached.", url)
        return r"(?!)"  # matches nothing
    return f"{re.escape(host)}$"


def _get_cache_rules() -> dict:
    """
    Get cache rules based on configured SEC base and data URLs.
    This allows caching to work with custom SEC mirrors.

    SEC serves two hosts: ``www.sec.gov`` (tickers, index, Archives) and
    ``data.sec.gov`` (``/submissions``, ``/api/xbrl/companyfacts``).
    httpxthrottlecache matches the request HOST against each top-level key
    before it ever looks at the path, so a rule filed under the base-URL host
    never applies to a request to the data host, whatever its path. Build one
    key per host actually used by ``edgar.urls`` and file each rule under the
    host that really serves it. A custom mirror pointing both at the same host
    merges into a single key.
    """
    from edgar.config import SEC_BASE_URL, SEC_DATA_URL

    base_domain = _host_key(SEC_BASE_URL)
    data_domain = _host_key(SEC_DATA_URL)

    base_rules = {
        r"/include/ticker\.txt.*": MAX_SUBMISSIONS_AGE_SECONDS,
        r"/files/company_tickers\.json.*": MAX_SUBMISSIONS_AGE_SECONDS,
        ".*index/.*": MAX_INDEX_AGE_SECONDS,
        "/Archives/edgar/data": True,  # cache forever
    }
    data_rules = {
        "/submissions.*": MAX_SUBMISSIONS_AGE_SECONDS,
        # companyfacts is invalidated by the same event as /submissions (a new
        # filing lands), so it takes the same freshness budget. Issue #471
        # deliberately tuned that budget down to 30s because a longer TTL
        # delayed visibility of same-day 8-Ks; a companyfacts-specific longer
        # TTL would reintroduce that staleness for a sibling endpoint.
        r"/api/xbrl/companyfacts/.*": MAX_SUBMISSIONS_AGE_SECONDS,
    }

    if base_domain == data_domain:
        return {base_domain: {**base_rules, **data_rules}}
    return {
        base_domain: base_rules,
        data_domain: data_rules,
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


# One-time cache-clear migrations (#457, #672).
#
# Marker files are kept in <edgar-data-dir>/.migrations — OUTSIDE the cache
# directory — so that clearing the cache for one migration can never delete
# another migration's marker (Issue #1051: both markers used to live inside
# _tcache, so each import wiped the cache twice, forever).
#
# Maps migration id (the marker filename in .migrations) to the legacy marker
# filename that older versions kept inside the cache directory. A legacy marker
# means the migration already ran under an older version, so it is recorded in
# the new location without clearing again.
_CACHE_CLEAR_MIGRATIONS = {
    "locale_fix_457": ".locale_fix_457_applied",
    "empty_response_fix_672": ".empty_response_fix_672_applied",
}


def _apply_cache_clear_migrations(migrations: dict) -> bool:
    """
    Clear the HTTP cache at most once for whichever of `migrations` are pending.

    All pending/satisfied decisions are made up front, then the cache directory
    is removed at most once, then every marker is written — so a single pass
    over multiple migrations performs one clear, not one per migration.

    Returns:
        bool: True if the cache directory was cleared, False otherwise
    """
    import logging
    import shutil
    from pathlib import Path

    try:
        cache_dir = Path(get_cache_directory())
        migrations_dir = cache_dir.parent / ".migrations"

        # Decide what is pending BEFORE touching anything. A legacy marker
        # inside the cache directory counts as already applied (#1051).
        pending, already_applied = [], []
        for migration, legacy_name in migrations.items():
            marker_file = migrations_dir / migration
            try:
                if marker_file.exists():
                    continue
            except (PermissionError, OSError):
                # If we can't check the marker file, assume we need to proceed
                pass
            if (cache_dir / legacy_name).exists():
                already_applied.append(marker_file)
            else:
                pending.append(marker_file)

        if not pending and not already_applied:
            return False

        migrations_dir.mkdir(parents=True, exist_ok=True)

        cleared = False
        if pending and cache_dir.exists():
            shutil.rmtree(cache_dir)
            cleared = True
        cache_dir.mkdir(parents=True, exist_ok=True)
        for marker_file in pending + already_applied:
            marker_file.touch()
        return cleared

    except Exception as e:
        # Log error but don't fail - worst case user still has cache issues
        logging.getLogger(__name__).warning(
            "Failed to clear stale cache entries: %s. "
            "You may need to manually delete ~/.edgar/_tcache directory.", e
        )
        return False


def _run_import_time_cache_migrations() -> bool:
    """Run all one-time cache-clear migrations as a single pass (at most one clear)."""
    return _apply_cache_clear_migrations(_CACHE_CLEAR_MIGRATIONS)


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
    return _apply_cache_clear_migrations(
        {"empty_response_fix_672": _CACHE_CLEAR_MIGRATIONS["empty_response_fix_672"]}
    )


def clear_locale_corrupted_cache():
    """
    One-time cache clearing function to remove locale-corrupted cache files from Issue #457.

    This function addresses a specific issue where cache files created with non-English locales
    (Chinese, Japanese, German, etc.) contain timestamps that cannot be deserialized after
    the locale fix was applied in v4.19.0.

    The function:
    1. Checks for a marker file (kept outside the cache directory) to avoid repeated clearing
    2. Clears the HTTP cache directory if the migration is pending
    3. Creates the marker file to prevent future clearing

    This is safe to call multiple times - it will only clear cache once per installation.

    Returns:
        bool: True if cache was cleared, False if already cleared previously
    """
    return _apply_cache_clear_migrations(
        {"locale_fix_457": _CACHE_CLEAR_MIGRATIONS["locale_fix_457"]}
    )
