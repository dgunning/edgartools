"""
Exposes two function for creating HTTP Clients:
- http_client: Returns a global (technically a local in a closure) httpx.Client for synchronous use.
- async_http_client: Creates and destroys an HTTP client for each async caller. For best results, create once per group of operations

To close the global connection, call `close_client()`

Implementation notes:
- New "kwargs" and changes to HTTPX_PARAMS to http_client are ignored after the first creation, until close_client.
- Any additional HTTPX parameters may be added to DEFAULT_PARAMS. Preferably before the first connection is made. For example, one might want to use http2 connections by adding 'httpx': True.
"""

import logging
import os
import threading
from contextlib import asynccontextmanager, contextmanager, nullcontext
import httpx
from typing import AsyncGenerator, Optional

from edgar.core import client_headers, edgar_mode

log = logging.getLogger(__name__)

HTTPX_PARAMS = {"timeout": edgar_mode.http_timeout, "limits": edgar_mode.limits, "default_encoding": "utf-8"}


def get_edgar_verify_ssl():
    """
    Returns True if using SSL verification on http requests
    """
    falsy = {"0", "false", "no", "n", "off"}
    value = os.environ.get("EDGAR_VERIFY_SSL", "true").lower()
    return value not in falsy


def get_default_params():
    return {
        **HTTPX_PARAMS,
        "verify": get_edgar_verify_ssl(),
    }


def edgar_client_factory(**kwargs) -> httpx.Client:
    params = get_default_params()
    params["headers"] = client_headers()

    params.update(**kwargs)
    return httpx.Client(**params)


def edgar_client_factory_async(**kwargs) -> httpx.AsyncClient:
    params = get_default_params()
    params["headers"] = client_headers()

    params.update(**kwargs)
    return httpx.AsyncClient(**params)


def _http_client_manager():
    """
    Creates and reuses an HTTPX Client.

    This function is used for all synchronous requests.
    """
    client = None
    lock = threading.Lock()

    @contextmanager
    def _get_client(**kwargs):
        nonlocal client

        if client is None:
            with lock:
                # Locking: not super critical, since worst case might be extra httpx clients created,
                # but future proofing against TOCTOU races in free-threading world
                if client is None:
                    client = edgar_client_factory(**kwargs)
                    log.info("Creating new HTTPX Client")

        yield client

    def _close_client():
        nonlocal client

        if client is not None:
            try:
                client.close()
            except Exception:
                log.exception("Exception closing client")

            client = None

    return _get_client, _close_client


http_client, _close_client = _http_client_manager()


@asynccontextmanager
async def async_http_client(client: Optional[httpx.AsyncClient] = None, **kwargs) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Async callers should create a single client for a group of tasks, rather than creating a single client per task.

    If a null client is passed, then this is a no-op and the client isn't closed. This (passing a client) occurs when a higher level async task creates the client to be used by child calls.
    """

    if client is not None:
        yield nullcontext(client)  # type: ignore # Caller is responsible for closing

    async with edgar_client_factory_async(**kwargs) as client:
        yield client


def close_clients():
    """Closes and invalidates existing client session, if created."""
    _close_client()
