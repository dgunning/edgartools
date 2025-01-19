import logging
import threading
from contextlib import asynccontextmanager, contextmanager, nullcontext
import httpx
from typing import AsyncGenerator, Optional

from edgar.core import client_headers, edgar_mode

log = logging.getLogger(__name__)

PERSISTENT_CLIENT = True # When enabled, httpclient reuses httpx clients rather than creating a single request per client

DEFAULT_PARAMS = {
    "timeout": edgar_mode.http_timeout,
    "limits": edgar_mode.limits,
    "default_encoding": "utf-8",
}

def _client_factory(**kwargs)-> httpx.Client:
    params = DEFAULT_PARAMS.copy()
    params["headers"] = client_headers()
    
    params.update(**kwargs)
    
    return httpx.Client(**params)

def _http_client_manager():
    """When PERSISTENT_CLIENT, creates and reuses a single client. Otherwise, creates a new client per invocation."""
    client = None
    lock = threading.Lock()

    @contextmanager
    def _get_client( **kwargs):
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
async def async_http_client(client: Optional[httpx.AsyncClient] = None, **kwargs) -> AsyncGenerator[httpx.AsyncClient]:
    """Async callers do not reuse clients, and are expected to create / tear down the client via the contextmanager.
    
    The nullable client parameter is used for methods that may or may not be passed an AsyncClient. If an AsyncClient is passed, this is a noop... it returns the client and doesn't close it.
    """

    if client is not None:
        yield nullcontext(client) # type: ignore # caller responsible for closing

    params = DEFAULT_PARAMS.copy()
    params["headers"] = client_headers()
    
    params.update(**kwargs)
    async with httpx.AsyncClient(**params) as client:
        yield client

def close_clients():
    """Closes and invalidates existing client sessions."""
    _close_client()