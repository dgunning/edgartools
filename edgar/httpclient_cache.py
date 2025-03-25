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
from edgar import httpclient, core, httprequests
import logging
import hishel
import httpcore
from pathlib import Path
from functools import partial
from contextlib import asynccontextmanager
from limiter import Limiter 

logger = logging.getLogger(__name__)

LIMITER = Limiter(rate=10, capacity=10, units=1)

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

def _get_cache_controller(**kwargs):
    controller = hishel.Controller(
        cacheable_methods=["GET", "POST"],
        cacheable_status_codes=[200],
        key_generator=custom_key_generator,
        **kwargs
    )

    return controller

def cached_factory(cache_directory: Path | None = None, controller_args: dict | None = None, **kwargs):
    params = httpclient.DEFAULT_PARAMS.copy()
    params["headers"] = httpclient.client_headers()
    params.update(**kwargs)
    if controller_args is None:
        controller_args = {}

    controller = _get_cache_controller(**controller_args)
    client = hishel.CacheClient(
        controller=controller,
        storage=hishel.FileStorage(base_path = cache_directory),
        **params
    )

    handler = client._transport.handle_request

    @LIMITER
    def decorated_request(req):
        return handler(req)
    client._transport.handle_request = decorated_request

    return client

@asynccontextmanager
async def asynccached_factory(cache_directory: Path | None = None, controller_args: dict | None = None, **kwargs):
    params = httpclient.DEFAULT_PARAMS.copy()
    params["headers"] = httpclient.client_headers()
    params.update(**kwargs)
    if controller_args is None:
        controller_args = {}

    controller = _get_cache_controller(**controller_args)
    client = hishel.AsyncCacheClient(
        controller=controller,
        storage=hishel.AsyncFileStorage(base_path = cache_directory),
        **params
    )
        
    handler = client._transport.handle_async_request
    @LIMITER
    async def decorated_async_request(req):
        return await handler(req)
    client._transport.handle_async_request = decorated_async_request

    async with client:
        yield client




def install_cached_client(cache_directory: Path | None, controller_args: dict | None = None):
    if cache_directory is None:
        cache_directory = core.get_edgar_data_directory() / "requestcache"

    httprequests.throttle_disabled = True  # Use the RateLimiterTransport
    httpclient.client_factory_class = partial(cached_factory, cache_directory=cache_directory, controller_args=controller_args)
    httpclient.asyncclient_factory_class = partial(asynccached_factory, cache_directory=cache_directory, controller_args=controller_args)

    httpclient.close_clients()