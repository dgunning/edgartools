import logging
import threading
import asyncio
from contextlib import asynccontextmanager, contextmanager

import httpx

from edgar.core import client_headers, edgar_mode


log = logging.getLogger(__name__)

REUSE_CLIENT = True

DEFAULT_PARAMS = {
    "timeout": edgar_mode.http_timeout,
    "limits": edgar_mode.limits,
    "default_encoding": "utf-8",
}

def _client_params(async_client: bool = False, **kwargs) -> dict:
    """Merges defaults and additional kw args for httpx Client initialization.

    Args:
        async_client (bool, optional): Indicates whether this is used for a httpx.AsyncClient, as some options 
        may be specific to particular modes, such as httpx Transports. Defaults to False.

    Returns:
        dict: _description_
    """

    params = DEFAULT_PARAMS.copy()
    params["headers"] =  client_headers()
    params.update(kwargs)

    return params

def _http_client_closure():
    """When REUSE_CLIENT, creates and reuses a single client."""
    client = None
    lock = threading.Lock()

    @contextmanager
    def _get_client( **kwargs):
        if REUSE_CLIENT:
            nonlocal client

            if client is None:
                with lock:
                    if client is None: 
                        log.info("Creating new HTTP Client")

                        client = httpx.Client(**_client_params(async_client = False, **kwargs))
            yield client
        else:
            # Create a new client per request
            with httpx.Client(**_client_params(async_client = False, **kwargs)) as _client:
                yield _client

    def _close_client():
        nonlocal client

        if client is not None:
            try:
                client.close()
            except Exception:
                log.exception("Exception closing client")

            client = None

    return _get_client, _close_client

def _ahttp_client_closure():
    """Creates a AsyncClient per thread. Necessary to avoid sharing across eventloops."""
    
    asynciolock = asyncio.Lock()
    threadlock = threading.Lock()

    tl = threading.local()  # Shared thread-local storage per thread

    def _local_client():
        return getattr(tl, "edgar_httpclient_asyncclient", None)

    def _set_client(client):
        tl.edgar_httpclient_asyncclient = client

    @asynccontextmanager
    async def _get_client(**kwargs):

        client = _local_client()
        if client is not None:
            yield client
        elif REUSE_CLIENT:
            with threadlock: 
                async with asynciolock:
                    if client is None:
                        log.info("Creating new Async HTTP Client")
                        client = httpx.AsyncClient(**_client_params(async_client = True, **kwargs)
                        )
                    _set_client(client)

                yield client
        else:
            # Create a new client per request
            async with httpx.AsyncClient(
                        **_client_params(async_client = True, **kwargs)
                    ) as _client:
                yield _client

    def _aclose_client():
        client = _local_client()

        if client is not None:
            try:
                client.close()
            except Exception:
                log.exception("Exception closing client")

            _set_client(None)
            client = None

    return _get_client, _aclose_client


http_client, _close_client = _http_client_closure()
ahttp_client, _aclose_client = _ahttp_client_closure()

def close_clients():
    """Closes and invalidates existing client sessions."""
    _close_client()
    _aclose_client()
