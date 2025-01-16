import logging
import threading
from asyncio import Lock
from contextlib import asynccontextmanager, contextmanager

import httpx

from edgar.core import client_headers, edgar_mode


log = logging.getLogger(__name__)

REUSE_CLIENT = False

def _http_client_closure():
    """When REUSE_CLIENT, creates and reuses a single client."""
    client = None

    @contextmanager
    def _get_client( **kwargs):
        if REUSE_CLIENT:

            nonlocal client
            if client is None:

                log.info("Creating new HTTP Client")

                client = httpx.Client(headers=client_headers(),
                                    timeout=edgar_mode.http_timeout,
                                    limits=edgar_mode.limits,
                                    default_encoding="utf-8",
                                    **kwargs)
            yield client
        else:
            # Create a new client per request
            with httpx.Client(headers=client_headers(),
                                    timeout=edgar_mode.http_timeout,
                                    limits=edgar_mode.limits,
                                    default_encoding="utf-8",
                                    **kwargs) as _client:
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
    lock = Lock()

    @asynccontextmanager
    async def _get_client(**kwargs):

        if REUSE_CLIENT:
            async with lock:
                tl = threading.local()

                client = getattr(tl, "edgar_httpclient_aclient", None)

                if client is None:
                    log.info("Creating new Async HTTP Client")
                    client = httpx.AsyncClient(
                        headers=client_headers(),
                        timeout=edgar_mode.http_timeout, 
                        limits=edgar_mode.limits,
                        **kwargs,
                    )
                tl.edgar_httpclient_aclient = client

            yield client

        else:
            # Create a new client per request
            async with httpx.AsyncClient(
                        headers=client_headers(),
                        timeout=edgar_mode.http_timeout,
                        limits=edgar_mode.limits,
                        **kwargs,
                    ) as _client:
                yield _client

    def _aclose_client():
        tl = threading.local()

        client = getattr(tl, "edgar_httpclient_aclient", None)

        if client is not None:
            try:
                client.close()
            except Exception:
                log.exception("Exception closing client")

            tl.edgar_httpclient_aclient = None
            client = None

    return _get_client, _aclose_client


http_client, _close_client = _http_client_closure()
ahttp_client, _aclose_client = _ahttp_client_closure()

def close_clients():
    """Closes and invalidates existing client sessions."""
    _close_client()
    _aclose_client()
