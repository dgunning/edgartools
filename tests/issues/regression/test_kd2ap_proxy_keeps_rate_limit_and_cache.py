"""configure_http(proxy=...) keeps every request on the cache and the rate limiter.

Bead: edgartools-kd2ap (attack-surface audit, 2026-10-22).

configure_http put the proxy into the client params. httpx2 turns a client-level
proxy into an ``all://`` mount that takes precedence over the transport passed in,
so after the call every request went to a bare HTTPTransport through the proxy,
skipping the CachingTransport and the RateLimitingTransport, while
get_http_config() looked normal. The documented corporate-proxy recipe therefore
sent unthrottled traffic to SEC. The proxy now goes on httpxthrottlecache's
innermost transport, under both.

Read structurally (no request is sent): the transport each client would use for
an SEC URL, and the connection pool at the bottom of it.
"""
import asyncio

import httpx2
import pytest

from edgar import configure_http, get_http_config, httpclient
from edgar.httpclient import uncached_http_client

PROXY = "http://proxy.example.com:3128"
SEC_URLS = ["https://www.sec.gov/Archives/edgar/data/320193/x.txt", "https://data.sec.gov/submissions/CIK0000320193.json"]


def _chain(transport):
    """Transport class names from the outside in, and the innermost transport."""
    names = []
    while transport is not None and len(names) < 6:
        names.append(type(transport).__name__)
        inner = getattr(transport, "transport", None) or getattr(transport, "_transport", None)
        if inner is None:
            break
        transport = inner
    return names, transport


def _sync_chains():
    with httpclient.HTTP_MGR.http_client() as client:
        return [_chain(client._transport_for_url(httpx2.URL(url))) for url in SEC_URLS]


def _async_chains():
    async def collect():
        async with httpclient.HTTP_MGR.async_http_client() as client:
            return [_chain(client._transport_for_url(httpx2.URL(url))) for url in SEC_URLS]
    return asyncio.run(collect())


def _uncached_chains():
    with uncached_http_client() as client:
        return [_chain(client._transport_for_url(httpx2.URL(url))) for url in SEC_URLS]


@pytest.fixture
def manager(monkeypatch):
    """Restore the shared manager's proxy, params and client around each test.

    Read through the module every time: tests/conftest.py swaps in a fresh
    httpclient.HTTP_MGR, so a reference imported at module load goes stale.
    """
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    saved_proxy, saved_params = httpclient.HTTP_MGR.proxy, httpclient.HTTP_MGR.httpx_params.copy()
    httpclient.HTTP_MGR.close()
    httpclient.HTTP_MGR.proxy = None
    httpclient.HTTP_MGR.httpx_params.pop("proxy", None)
    yield
    httpclient.HTTP_MGR.close()
    httpclient.HTTP_MGR.proxy = saved_proxy
    httpclient.HTTP_MGR.httpx_params.clear()
    httpclient.HTTP_MGR.httpx_params.update(saved_params)


@pytest.mark.parametrize("chains", [_sync_chains, _async_chains, _uncached_chains], ids=["shared", "async", "uncached"])
def test_a_proxy_changes_only_the_connection_under_the_chain(manager, chains):
    direct = chains()
    assert all(any("RateLimitingTransport" in name for name in names) for names, _ in direct)

    configure_http(proxy=PROXY)
    httpclient.HTTP_MGR.close()
    proxied = chains()

    for (direct_names, direct_inner), (proxy_names, proxy_inner) in zip(direct, proxied, strict=True):
        assert proxy_names == direct_names  # cache (when on) and rate limiter still in front
        assert type(direct_inner._pool).__name__ in ("ConnectionPool", "AsyncConnectionPool")
        assert type(proxy_inner._pool).__name__ in ("HTTPProxy", "AsyncHTTPProxy")
        assert proxy_inner._pool._proxy_url.host == b"proxy.example.com"


def test_cache_stays_in_front_when_enabled(manager, tmp_path, monkeypatch):
    """With the file cache on (the default outside tests), it stays outermost behind a proxy."""
    monkeypatch.setattr(httpclient.HTTP_MGR, "cache_mode", "FileCache")
    monkeypatch.setattr(httpclient.HTTP_MGR, "cache_dir", tmp_path)
    configure_http(proxy=PROXY)
    httpclient.HTTP_MGR.close()
    for names, inner in _sync_chains():
        assert names[:2] == ["CachingTransport", "RateLimitingTransport"], names
        assert type(inner._pool).__name__ == "HTTPProxy"


def test_the_proxy_is_reported_and_not_a_client_param(manager):
    configure_http(proxy=PROXY)
    assert "proxy" not in httpclient.HTTP_MGR.httpx_params
    assert httpclient.HTTP_MGR.proxy == PROXY
    assert get_http_config()["proxy"] == PROXY
