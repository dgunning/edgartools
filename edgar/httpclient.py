from httpxthrottlecache import HttpxThrottleCache
from edgar.core import get_identity, strtobool
import os
from contextlib import asynccontextmanager, contextmanager
import httpx
from typing import AsyncGenerator, Optional, Generator
from pathlib import Path
from .core import edgar_data_dir


MAX_SUBMISSIONS_AGE_SECONDS = 10 * 60  # Check for submissions every 10 minutes
MAX_INDEX_AGE_SECONDS = 30 * 60  # Check for updates to index (ie: daily-index) every 30 minutes

CACHE_RULES = {
    r".*\.sec\.gov": {
        "/submissions.*": MAX_SUBMISSIONS_AGE_SECONDS,
        r"/include/ticker\.txt.*": MAX_SUBMISSIONS_AGE_SECONDS,
        r"/files/company_tickers\.json.*": MAX_SUBMISSIONS_AGE_SECONDS,
        ".*index/.*": MAX_INDEX_AGE_SECONDS,
        "/Archives/edgar/data": True,  # cache forever
    }
}

def get_cache_directory() -> str:
    cachedir = Path(edgar_data_dir) / "_pcache"
    cachedir.mkdir(parents=True, exist_ok=True)

    return str(cachedir)


def get_edgar_verify_ssl():
    """
    Returns True if using SSL verification on http requests
    """

    if "EDGAR_VERIFY_SSL" in os.environ:
        return strtobool(os.environ["EDGAR_VERIFY_SSL"])
    else:
        return True


def get_http_mgr(cache_enabled: bool = True, request_per_sec_limit: int = 9) -> HttpxThrottleCache:
    if cache_enabled:
        cache_dir = get_cache_directory()
    else:
        cache_dir = None

    http_mgr = HttpxThrottleCache(
        user_agent=get_identity(), cache_dir=cache_dir, cache_enabled=cache_enabled, request_per_sec_limit=request_per_sec_limit,
        cache_rules = CACHE_RULES
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
