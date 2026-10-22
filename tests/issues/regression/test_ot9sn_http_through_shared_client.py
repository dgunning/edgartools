"""Every SEC request goes through the shared client: the user's identity, the
rate limiter and (unless deliberately bypassed) the cache.

bead edgartools-ot9sn. Found by the benchmark panel (epic edgartools-qpjud),
which needed to count requests and found three that never passed the counter:

1. XmlFiling.to_html() called bare httpx2.get with the User-Agent
   'EdgarTools support@edgartools.io', so SEC saw the project instead of the
   user, and the request skipped the rate limiter.
2. FilingSGML's empty-cache retry (#672) opened its own httpx2.Client. The
   identity was right, but it skipped the rate limiter.
3. HTMLParser.parse_url() imported `requests`, which edgartools does not
   depend on, and sent no User-Agent at all.

And one flag that did nothing: stream_with_retry(bypass_cache=True) handed the
flag to the shared client, which httpxthrottlecache creates once and then
ignores the flag for.

Offline. HTTPTransport.handle_request is replaced, the layer under the rate
limiter, so a request that reaches it has passed through whatever the client
stack put in front of it.
"""
import ast
from pathlib import Path
from types import SimpleNamespace

import httpx2
import pytest

import edgar.httpclient as httpclient

IDENTITY = "Benchmark Panel panel@example.com"
EDGAR = Path(__file__).resolve().parents[3] / "edgar"


BODY = b"<html><body><p>ok</p></body></html>" + b" " * 64


class _Body(httpx2.SyncByteStream):
    """A response body that is still unread, as a real transport returns it.

    `httpx2.Response(text=...)` arrives already consumed, and the cache layer,
    which streams the raw body to disk, then raises StreamConsumed.
    """

    def __iter__(self):
        yield BODY


@pytest.fixture
def wire(monkeypatch):
    """Answer every request at the bottom transport and record what arrived.

    A fresh shared manager with the cache off, so nothing reaches a real cache
    directory and no earlier test's client or cached response can answer.
    """
    seen = []

    def handle_request(self, request, **kwargs):
        seen.append(request)
        return httpx2.Response(200, stream=_Body(), request=request)

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", handle_request)
    monkeypatch.setenv("EDGAR_IDENTITY", IDENTITY)
    monkeypatch.setattr(httpclient, "HTTP_MGR", httpclient.get_http_mgr(cache_enabled=False))
    yield seen
    httpclient.HTTP_MGR.close()


@pytest.fixture
def acquisitions(monkeypatch):
    """Count draws on the shared rate limiter."""
    count = {"n": 0}
    limiter = httpclient.HTTP_MGR.rate_limiter
    original = limiter.try_acquire

    def try_acquire(*args, **kwargs):
        count["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(limiter, "try_acquire", try_acquire)
    return count


def test_xml_filing_html_is_fetched_as_the_user(wire, acquisitions):
    from edgar.xmlfiling import XmlFiling

    filing = SimpleNamespace(form="X-17A-5", accession_no="0001234567-24-000001", cik=1234567)
    html = XmlFiling(filing, form_data={}, header_data={}).to_html()

    assert html.startswith("<html>")
    assert len(wire) == 1
    assert wire[0].headers["User-Agent"] == IDENTITY
    assert "edgartools.io" not in wire[0].headers["User-Agent"]
    assert str(wire[0].url).endswith("/Archives/edgar/data/1234567/000123456724000001/xslX-17A-5_X01/primary_doc.xml")
    assert acquisitions["n"] == 1


def test_the_empty_cache_retry_waits_on_the_rate_limiter(wire, acquisitions):
    from edgar.sgml.sgml_common import _fetch_url_directly

    _fetch_url_directly("https://www.sec.gov/Archives/edgar/data/1/0000000001-24-000001.txt")

    assert len(wire) == 1
    assert wire[0].headers["User-Agent"] == IDENTITY
    assert acquisitions["n"] == 1


def test_parse_url_needs_no_requests_package_and_sends_the_identity(wire, acquisitions, monkeypatch):
    import sys

    from edgar.documents.parser import HTMLParser

    monkeypatch.setitem(sys.modules, "requests", None)  # `import requests` raises ImportError
    doc = HTMLParser().parse_url("https://www.sec.gov/Archives/edgar/data/1/example.htm")

    assert "ok" in doc.text()
    assert wire[0].headers["User-Agent"] == IDENTITY
    assert acquisitions["n"] == 1


def test_bypass_cache_skips_the_cache_and_nothing_else():
    with httpclient.uncached_http_client() as client:
        transport = client._transport
    assert type(transport).__name__ == "RateLimitingTransport"
    assert transport.limiter is httpclient.HTTP_MGR.rate_limiter


def test_stream_with_retry_honours_bypass_cache(wire, monkeypatch):
    """The flag used to be dropped: the shared, cached client served the request."""
    from edgar import httprequests

    opened = []
    real = httpclient.uncached_http_client

    def spy(**kwargs):
        opened.append(True)
        return real(**kwargs)

    monkeypatch.setattr(httprequests, "uncached_http_client", spy)
    for _ in httprequests.stream_with_retry("https://www.sec.gov/x.txt", bypass_cache=True):
        pass
    assert opened == [True]
    for _ in httprequests.stream_with_retry("https://www.sec.gov/x.txt"):
        pass
    assert opened == [True]


# Direct HTTP outside edgar/httpclient.py, each with the reason it may stay.
ALLOWED = {
    # The SSL doctor compares a raw request with the configured one on purpose;
    # both send the user's identity.
    ("diagnose_ssl/checks.py", "httpx2.get"),
}
HTTP_CALLS = {"get", "post", "put", "head", "stream", "request", "Client", "AsyncClient"}


def test_no_module_makes_http_requests_around_the_shared_client():
    found = set()
    for path in sorted(EDGAR.rglob("*.py")):
        rel = path.relative_to(EDGAR).as_posix()
        if rel == "httpclient.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in ("requests", "urllib3"):
                        found.add((rel, f"import {alias.name}"))
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in ("requests", "urllib3"):
                found.add((rel, f"from {node.module}"))
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and isinstance(node.func.value, ast.Name)
                  and node.func.value.id in ("httpx2", "httpx") and node.func.attr in HTTP_CALLS):
                found.add((rel, f"{node.func.value.id}.{node.func.attr}"))
    unexpected = sorted(found - ALLOWED)
    assert not unexpected, (
        f"HTTP calls that bypass edgar.httpclient: {unexpected}. Use "
        f"edgar.httprequests (get_with_retry, stream_with_retry) or "
        f"edgar.httpclient.http_client / uncached_http_client, so SEC sees the "
        f"user's identity and the request waits on the rate limiter."
    )
    assert not ALLOWED - found, f"stale ALLOWED entries: {sorted(ALLOWED - found)}"
