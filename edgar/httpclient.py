"""

Exposes two function for creating HTTP Clients:
- http_client: Returns a global (technically a local in a closure) httpx.Client for synchronous use.
- async_http_client: Creates and destroys an HTTP client for each async caller. For best results, create once per group of operations

To close the global connection, call `close_client()`

To change the rate limit, call `update_rate_limiter(requests_per_second)`

## Caching
Caching is enabled by default, using the controller rules defined in httpclient_cache.

To disable the cache, set CACHE_ENABLED to False.

## HTTPX Parameters

HTTPX Parameters are assembled from three sources:
- edgar.httpclient.HTTPX_PARAMS
- get_edgar_verify_ssl: checks EDGAR_VERIFY_SSL environment variable
- edgar.core.get_identity: user_agent
- any kwargs passed to http_client or async_http_client


Implementation notes:
- In general, changing any settings / globals requires calling `close_client` to make sure the old settings aren't used.
- To use other storage backends, such as S3, override `get_transport` and `get_async_storage` and use hishel.S3Storage and hishel.AsyncS3Storage object. See https://hishel.com/ for usage.

"""

import logging
import os
import threading
from contextlib import asynccontextmanager, contextmanager, nullcontext
import httpx
import hishel
from typing import AsyncGenerator, Optional
from edgar.core import get_identity, edgar_mode, strtobool
from edgar.httpclient_cache import get_cache_controller
from edgar.httpclient_ratelimiter import RateLimitingTransport, AsyncRateLimitingTransport, create_rate_limiter
from pathlib import Path
from .core import edgar_data_dir

log = logging.getLogger(__name__)

try: 
    # enable http2 if h2 is installed
    import h2  # type: ignore  # noqa 
    http2 = True
except ImportError: 
    http2 = False

HTTPX_PARAMS = {"timeout": edgar_mode.http_timeout, "limits": edgar_mode.limits, "default_encoding": "utf-8", "http2": http2}

CACHE_ENABLED = True


def get_cache_directory():
    if CACHE_ENABLED:
        cachedir = Path(edgar_data_dir) / "_pcache"
        cachedir.mkdir(exist_ok=True)

        return str(cachedir)
    else:
        return None


_DEFAULT_REQUEST_PER_SEC_LIMIT = 9
_MAX_DELAY = 1000 * 60  # 1 minute

_RATE_LIMITER = create_rate_limiter(requests_per_second=_DEFAULT_REQUEST_PER_SEC_LIMIT, max_delay=_MAX_DELAY)


def update_rate_limiter(requests_per_second: int):
    global _RATE_LIMITER
    _RATE_LIMITER = create_rate_limiter(requests_per_second=requests_per_second, max_delay=_MAX_DELAY)

    close_clients()


def get_edgar_verify_ssl():
    """
    Returns True if using SSL verification on http requests
    """

    if "EDGAR_VERIFY_SSL" in os.environ:
        return strtobool(os.environ["EDGAR_VERIFY_SSL"])
    else:
        return True


def get_http_params():
    return {
        **HTTPX_PARAMS,
        "headers": {"User-Agent": get_identity()},
        "verify": get_edgar_verify_ssl(),
    }


def edgar_client_factory(bypass_cache: bool, **kwargs) -> httpx.Client:
    params = get_http_params()
    params.update(**kwargs)

    if "transport" not in params:
        params["transport"] = get_transport(bypass_cache=bypass_cache)

    return httpx.Client(**params)


def edgar_client_factory_async(bypass_cache: bool, **kwargs) -> httpx.AsyncClient:
    params = get_http_params()
    params.update(**kwargs)

    if "transport" not in params:
        params["transport"] = get_async_transport(bypass_cache=bypass_cache)

    return httpx.AsyncClient(**params)


def _http_client_manager():
    """
    Creates and reuses an HTTPX Client.

    This function is used for all synchronous requests.
    """

    @contextmanager
    def _get_client(bypass_cache: bool = False, **kwargs):
        log.info("Creating new HTTPX Client")
        yield edgar_client_factory(bypass_cache=bypass_cache, **kwargs)

    def _close_client():
        pass  # noop, to deprecate

    return _get_client, _close_client


@asynccontextmanager
async def async_http_client(
    client: Optional[httpx.AsyncClient] = None, bypass_cache: bool = False, **kwargs
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Async callers should create a single client for a group of tasks, rather than creating a single client per task.

    If a null client is passed, then this is a no-op and the client isn't closed. This (passing a client) occurs when a higher level async task creates the client to be used by child calls.
    """

    if client is not None:
        yield nullcontext(client)  # type: ignore # Caller is responsible for closing

    async with edgar_client_factory_async(bypass_cache=bypass_cache, **kwargs) as client:
        yield client


def get_transport(bypass_cache: bool) -> httpx.BaseTransport:
    cache_dir = get_cache_directory()
    if cache_dir and not bypass_cache:
        log.info(f"Cache is ENABLED, writing to {cache_dir}")
        storage = hishel.FileStorage(base_path=Path(cache_dir), serializer=hishel.PickleSerializer())
        controller = get_cache_controller()
        rate_limit_transport = RateLimitingTransport(_RATE_LIMITER)
        return hishel.CacheTransport(transport=rate_limit_transport, storage=storage, controller=controller)
    else:
        log.info("Cache is DISABLED, rate limiting only")
        return RateLimitingTransport(_RATE_LIMITER)


def get_async_transport(bypass_cache: bool) -> httpx.AsyncBaseTransport:
    cache_dir = get_cache_directory()
    if cache_dir and not bypass_cache:
        log.info(f"Cache is ENABLED, writing to {cache_dir}")
        storage = hishel.AsyncFileStorage(base_path=Path(cache_dir))
        controller = get_cache_controller()
        rate_limit_transport = AsyncRateLimitingTransport(_RATE_LIMITER)
        return hishel.AsyncCacheTransport(transport=rate_limit_transport, storage=storage, controller=controller)
    else:
        log.info("Cache is DISABLED, rate limiting only")
        return AsyncRateLimitingTransport(_RATE_LIMITER)


http_client, _close_client = _http_client_manager()


def close_clients():
    """Closes and invalidates existing client session, if created."""
    _close_client()
