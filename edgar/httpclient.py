import httpx
import logging

from contextlib import contextmanager, asynccontextmanager

from edgar.core import edgar_mode

log = logging.getLogger(__name__)

@contextmanager
def http_client():
    """
    Context manager for synchronous HTTP client usage.
    
    This design is intended to make it easy to swap in and override the httpxclient initialization.
    """
    with httpx.Client(timeout=edgar_mode.http_timeout) as client:
        yield client



@asynccontextmanager
async def ahttp_client():
    """
    Async context manager for the HTTP client.

    This design is intended to make it easy to swap in and override the httpxclient initialization.
    """
    async with httpx.AsyncClient(timeout=edgar_mode.http_timeout) as client:
        yield client
