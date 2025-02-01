"""
Implements a Hishel cache controller.

cache_directory defaults to `Path(core.edgar_data_dir) / "requestcache"`

Example 1: Using a heuristic cache
https://hishel.com/advanced/controllers/#allowing-heuristics
See get_freshness_lifetime and get_heuristic_freshness in https://github.com/karpetrosyan/hishel/blob/master/hishel/_controller.py

```
from edgar import httpclient_cache as hcc
hcc.install_cached_client(cache_directory = None, controller_args = {"allow_heuristics": True, "allow_stale": True, "always_revalidate": False})
For more info on Heuristics: https://www.rfc-editor.org/rfc/rfc9111.html#name-calculating-heuristic-fresh
```

Example 2: Implementing force_cache - caching everything
https://hishel.com/advanced/controllers/#force-caching
Note - Caching everything is not safe: you must manually clear the cache directory

```
from edgar import httpclient_cache as hcc
hcc.install_cached_client(cache_directory = None, controller_args = {"force_cache": True})
```

To enable logging:
```
import logging
logging.getLogger("hishel.controller").setLevel(logging.INFO)
```
"""
from edgar import httpclient, core, httprequests, httpclient_limitertransport
import logging
import hishel
import httpcore
from pathlib import Path
from functools import partial
from contextlib import asynccontextmanager

from limiter import Limiter 
import httpx

logger = logging.getLogger(__name__)

LIMITER = Limiter(rate=10, units=1)

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
    return f"{host}_{url_p}"

def _get_cache_controller(**kwargs):
    controller = hishel.Controller(
        cacheable_methods=["GET", "POST"],
        cacheable_status_codes=[200],
        key_generator=custom_key_generator,
        **kwargs
        # allow_stale=True, # Use the stale response if there is a connection issue and the new response cannot be obtained.
        # always_revalidate=False,
        # allow_heuristics=True 
    )

    return controller

class RateLimiterTransport(httpx.HTTPTransport):
    @LIMITER()
    def handle_request(
            self,
            request: httpx.Request,
        ) -> httpx.Response:
            return super().handle_request(request)
       
def cached_factory(cache_directory: Path | None = None, controller_args: dict | None = None, **kwargs):
    params = httpclient.DEFAULT_PARAMS.copy()
    params["headers"] = httpclient.client_headers()
    params.update(**kwargs)
    if controller_args is None:
        controller_args = {}

    client = hishel.CacheClient(
        transport=RateLimiterTransport(),
        controller=_get_cache_controller(**controller_args),
        storage=hishel.FileStorage(base_path = cache_directory),
        **params
    )

    return client
     
class AsyncRateLimiterTransport(httpx.AsyncHTTPTransport):
    @LIMITER()
    async def handle_async_request(
            self,
            request: httpx.Request,
        ) -> httpx.Response:
                return await super().handle_async_request(request)

@asynccontextmanager
async def asynccached_factory(cache_directory: Path | None = None, controller_args: dict | None = None, **kwargs):
    params = httpclient.DEFAULT_PARAMS.copy()
    params["headers"] = httpclient.client_headers()
    params.update(**kwargs)
    if controller_args is None:
        controller_args = {}

    client = hishel.AsyncCacheClient(
        transport=AsyncRateLimiterTransport(),
        controller=_get_cache_controller(**controller_args),
        storage=hishel.AsyncFileStorage(base_path = cache_directory),
        **params
    )
    async with client:
        yield client




def install_cached_client(cache_directory: Path | None, controller_args: dict | None = None):
    if cache_directory is None:
        cache_directory = Path(core.edgar_data_dir) / "requestcache"

    httprequests.throttle_disabled = True  # Use the RateLimiterTransport
    httpclient.client_factory_class = partial(cached_factory, cache_directory=cache_directory, controller_args=controller_args)
    httpclient.asyncclient_factory_class = partial(asynccached_factory, cache_directory=cache_directory, controller_args=controller_args)
