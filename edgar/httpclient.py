import logging
import os
import threading
from contextlib import asynccontextmanager, contextmanager, nullcontext
import httpx
from typing import AsyncGenerator, Optional

from edgar.core import client_headers, edgar_mode

log = logging.getLogger(__name__)

PERSISTENT_CLIENT = True  # When enabled, httpclient reuses httpx clients rather than creating a single request per client


def get_edgar_verify_ssl():
    """
    Returns True if using SSL verification on http requests
    """
    falsy = {"0", "false", "no", "n", "off"}
    value = os.environ.get("EDGAR_VERIFY_SSL", "true").lower()
    return value not in falsy


DEFAULT_PARAMS = {
    "timeout": edgar_mode.http_timeout,
    "limits": edgar_mode.limits,
    "default_encoding": "utf-8",
    "verify": get_edgar_verify_ssl(),
}

client_factory_class = httpx.Client
asyncclient_factory_class = httpx.AsyncClient


def _client_factory(**kwargs) -> httpx.Client:
    params = DEFAULT_PARAMS.copy()
    params["headers"] = client_headers()

    params.update(**kwargs)

    return client_factory_class(**params)


def _http_client_manager():
    """When PERSISTENT_CLIENT, creates and reuses a single client. Otherwise, creates a new client per invocation."""
    client = None
    lock = threading.Lock()

    @contextmanager
    def _get_client(**kwargs):
        if PERSISTENT_CLIENT:
            nonlocal client

            if client is None:
                with lock:
                    if client is None:
                        client = _client_factory(**kwargs)
                        log.info("Creating new HTTPX Client")

            yield client
        else:
            # Create a new client per request
            with _client_factory(**kwargs) as _client:
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


http_client, _close_client = _http_client_manager()


@asynccontextmanager
async def async_http_client(client: Optional[httpx.AsyncClient] = None, **kwargs) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Async callers should create a single client for a group of tasks, rather than creating a single client per task.

    Client: Optional parameter to allow code paths that accept optional clients: if a client is passed, this is a no-op and the client isn't closed.
    """

    if client is not None:
        yield nullcontext(client)  # Caller is responsible for closing

    params = DEFAULT_PARAMS.copy()
    params["headers"] = client_headers()

    params.update(**kwargs)
    async with asyncclient_factory_class(**params) as client:
        yield client


def close_clients():
    """Closes and invalidates existing client sessions."""
    _close_client()
