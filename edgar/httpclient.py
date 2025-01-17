import logging
import threading
import asyncio
from contextlib import asynccontextmanager, contextmanager
from weakref import WeakKeyDictionary
import httpx

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

def _async_client_factory(**kwargs) -> httpx.AsyncClient:
    params = DEFAULT_PARAMS.copy()
    params["headers"] = client_headers()
    
    params.update(**kwargs)

    return httpx.AsyncClient(**params)

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

def _async_client_manager():
    """When PERSISTENT_CLIENT, creates and reuses a single client per asyncio loop. Otherwise, creates a new client per invocation."""
    
    asynciolock = asyncio.Lock()
    threadlock = threading.Lock()

    clients = WeakKeyDictionary()  # store in a weakkeydictionary, to allow GC when out of scope

    @asynccontextmanager
    async def _get_client(**kwargs):
        loop = asyncio.get_running_loop()            

        client = clients.get(loop, None)
        if client is not None:
            yield client
        elif PERSISTENT_CLIENT:
            with threadlock: 
                async with asynciolock:
                    if client is None:
                        log.info("Creating new Async HTTPX Client")
                        client = _async_client_factory(**kwargs)
                    clients[loop] = (client)

                yield client
        else:
            # Create a new client per request
            async with _async_client_factory(**kwargs) as _client:
                yield _client

    def _clear_all_async_clients():
        """Clears clients, allows GC. Try to async run them, but this will fail in a nested asyncio loop."""

        for client in clients.values():
            try:
                asyncio.run(client.aclose())
            except Exception as e:
                log.debug("Couldn't close %s", e)

        clients.clear()
        
    return _get_client, _clear_all_async_clients


http_client, _close_client = _http_client_manager()
ahttp_client, _aclose_client = _async_client_manager()

def close_clients():
    """Closes and invalidates existing client sessions."""
    _close_client()
    _aclose_client()

