from edgar_httpx import HttpClientManager
from edgar.core import get_identity, strtobool
import os
from contextlib import asynccontextmanager, contextmanager
import httpx
from typing import AsyncGenerator, Optional, Generator
from pathlib import Path
from .core import edgar_data_dir


def get_cache_directory() -> str:
    cachedir = Path(edgar_data_dir) / "_cache"
    cachedir.mkdir(exist_ok=True)

    return str(cachedir)


def get_edgar_verify_ssl():
    """
    Returns True if using SSL verification on http requests
    """

    if "EDGAR_VERIFY_SSL" in os.environ:
        return strtobool(os.environ["EDGAR_VERIFY_SSL"])
    else:
        return True


def get_http_mgr(cache_enabled: bool = True, request_per_sec_limit: int = 9) -> HttpClientManager:
    if cache_enabled:
        cache_dir = get_cache_directory()
    else:
        cache_dir = None

    http_mgr = HttpClientManager(
        user_agent=get_identity(), cache_dir=cache_dir, cache_enabled=cache_enabled, request_per_sec_limit=request_per_sec_limit
    )
    http_mgr.httpx_params["verify"] = get_edgar_verify_ssl
    return http_mgr


@asynccontextmanager
async def async_http_client(client: Optional[httpx.AsyncClient] = None, **kwargs) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with HTTP_MGR.async_http_client(client=client, **kwargs) as client:
        yield client


@contextmanager
def http_client(**kwargs) -> Generator[httpx.Client, None, None]:
    with HTTP_MGR.client(**kwargs) as client:
        yield client


def get_http_params():
    return HTTP_MGR.httpx_params


def close_clients():
    HTTP_MGR.close()


HTTP_MGR = get_http_mgr()
