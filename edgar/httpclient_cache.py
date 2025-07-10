"""
Implements a Hishel cache controller over the HTTPX connections in httpclient. 

The default pyrate_limiter is set to 10 requests per second. This can be modified by passing a custom limiter: 
```
limiter = httpclient_cache._init_pyrate_limiter(1)  # 1 request per second
httpclient_cache.install_cached_client(limiter = limiter, cache_directory = Path(r"."), controller_args = {"allow_heuristics": True, "allow_stale": True, "always_revalidate": False})
```

If you need to control rate limit across multiple processes, see https://pyratelimiter.readthedocs.io/en/latest/#backends

---

A custom cache controller, EdgarController, is implemented in _get_cache_controller(**kwargs).

This cache controller caches, by default:
- /submissions URLs for up to 10 minutes by default, set in `MAX_SUBMISSIONS_AGE_SECONDS`
- .*index/.* URLs for up to 30 minutes by default, set in `MAX_INDEX_AGE_SECONDS`
- /Archives/edgar/data URLs indefinitely (forever)


Different storage backends can be used. See https://hishel.com/ for usage. To use S3, for instance, create a hishel.S3Storage and hishel.AsyncS3Storage object, and pass to install_cached_client.

Example:
```
from edgar import httpclient_cache, set_identity, Company
from pathlib import Path
import logging

logging.basicConfig(
    format='%(asctime)s %(name)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

logging.getLogger("hishel.controller").setLevel(logging.DEBUG)

httpclient_cache.install_cached_client(cache_directory = Path(r"."), controller_args = {"allow_heuristics": True, "allow_stale": True, "always_revalidate": False})

# set_identity("your@email.com")

filings = Company('MS').get_filings(form="10-Q")
```

Alternate rate limiters
"""
from edgar import httpclient, core, httprequests
import logging
import hishel
import httpcore
from pathlib import Path
from functools import partial
from contextlib import asynccontextmanager
from typing import Callable

logger = logging.getLogger(__name__)

def custom_key_generator(request: httpcore.Request, body: bytes | None) -> str:
    """ Generates a stable, readable key for a given request.

    Args:
        request (httpcore.Request): _description_
        body (bytes): _description_

    Returns:
        str: Persistent key for the request
    """

    host = request.url.host.decode()
    url = request.url.target.decode()

    url_p = url.replace("/", "__")

    key = f"{host}_{url_p}"
    return key

MAX_SUBMISSIONS_AGE_SECONDS = 10*60 # Check for submissions every 10 minutes
MAX_INDEX_AGE_SECONDS = 30*60 # Check for updates to index (ie: daily-index) every 30 minutes

def _get_cache_controller(**kwargs):    

    class EdgarController(hishel.Controller):
        def is_cachable(self, request: httpcore.Request, response: httpcore.Response) -> bool:

            if request.url.host.decode().endswith("sec.gov"):
                target = request.url.target.decode()
                if target.startswith("/submissions") or target.startswith("/include/ticker.txt") or target.startswith("/files/company_tickers.json"):
                    # /submissions are marked "no-store", but we're going to override this and allow it to be cached for MAX_SUBMISSIONS_AGE_SECONDS
                    return True
                elif "index/" in target:
                    # /Archives are immutable are marked "no-cache"
                    return True
                elif target.startswith("/Archives/edgar/data"):
                    # /Archives data are immutable are marked "no-cache"
                    return True

            super_is_cachable = super().is_cachable(request, response)
            logger.debug("%s is cacheable %s", request.url, super_is_cachable)
            return super_is_cachable
        

        def construct_response_from_cache(
            self, request: httpcore.Request, response: httpcore.Response, original_request: httpcore.Request
        ) -> httpcore.Request | httpcore.Response | None:

            if request.url.host.decode().endswith("sec.gov"):
                target = request.url.target.decode()

                if target.startswith("/submissions") or target.startswith("/include/ticker.txt") or target.startswith("/files/company_tickers.json"):
                    max_age = MAX_SUBMISSIONS_AGE_SECONDS
                elif "index/" in target:
                    max_age = MAX_INDEX_AGE_SECONDS
                elif target.startswith("/Archives/edgar/data"):
                    # Cache forever, never recheck
                    logger.debug("Cache hit for %s", target)
                    return response 
                else:
                    max_age = None # Fall through default cache handler

                if max_age:
                    #logger.debug("Max age is %d", max_age)
                    age_seconds = hishel._controller.get_age(response, self._clock)

                    logger.debug("Submissions age is %d, max_age is %d", age_seconds, max_age)
                    if age_seconds > max_age:
                        logger.debug("Request needs to be validated before using %s", target)
                        return request
                    else: 
                        logger.debug("Cache hit for %s", target)
                        return response
                    
            logger.debug("Falling through to default cache policy for %s", target)
            return super().construct_response_from_cache(request, response, original_request)

    controller = EdgarController(
        cacheable_methods=["GET", "POST"],
        cacheable_status_codes=[200],
        key_generator=custom_key_generator,
        **kwargs
    )

    return controller

def cached_factory(limiter: Callable, cache_directory: Path | None = None, controller_args: dict | None = None, storage: hishel.BaseStorage | None = None, **kwargs):
    params = httpclient.DEFAULT_PARAMS.copy()
    params["headers"] = httpclient.client_headers()
    params.update(**kwargs)
    if controller_args is None:
        controller_args = {}

    controller = _get_cache_controller(**controller_args)

    if storage is None:
        storage = hishel.FileStorage(base_path = cache_directory)

    client = hishel.CacheClient(
        controller=controller,
        storage=storage,
        **params
    )

    handler = client._transport.handle_request
    
    @limiter
    def decorated_request(req):
        return handler(req)
    client._transport.handle_request = decorated_request

    return client

@asynccontextmanager
async def asynccached_factory(limiter: Callable, cache_directory: Path | None = None, controller_args: dict | None = None, async_storage: hishel.AsyncBaseStorage | None = None, **kwargs):
    params = httpclient.DEFAULT_PARAMS.copy()
    params["headers"] = httpclient.client_headers()
    params.update(**kwargs)
    if controller_args is None:
        controller_args = {}
    
    if async_storage is None:
        async_storage = hishel.AsyncFileStorage(base_path = cache_directory)

    controller = _get_cache_controller(**controller_args)
    client = hishel.AsyncCacheClient(
        controller=controller,
        storage=async_storage,
        **params
    )
        
    handler = client._transport.handle_async_request

    @limiter
    async def decorated_async_request(req):
        return await handler(req)
    client._transport.handle_async_request = decorated_async_request

    async with client:
        yield client


def _init_pyrate_limiter(limit_per_sec: int = 10):
    from pyrate_limiter import Limiter, Rate, Duration
    rate = Rate(limit_per_sec, Duration.SECOND)
    limiter = Limiter(rate, raise_when_fail=False, max_delay=3600)
    return limiter.as_decorator()(lambda *_: ('constant-key', 1))

def install_cached_client(cache_directory: Path | None, controller_args: dict | None = None, limiter: Callable | None = None, async_storage: hishel.AsyncBaseStorage | None = None, storage: hishel.BaseStorage | None = None):

    if cache_directory is None:
        cache_directory = core.get_edgar_data_directory() / "requestcache"

    if limiter is None:
        limiter = _init_pyrate_limiter()

    httprequests.throttle_disabled = True  # Use the RateLimiterTransport
    httpclient.client_factory_class = partial(cached_factory, limiter=limiter, cache_directory=cache_directory, controller_args=controller_args, storage = storage)
    httpclient.asyncclient_factory_class = partial(asynccached_factory, limiter=limiter, cache_directory=cache_directory, controller_args=controller_args, async_storage = async_storage)

    httpclient.close_clients()