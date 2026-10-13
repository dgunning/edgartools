"""The four request functions share one implementation of each response branch (bead edgartools-fx90).

`get_with_retry`, `get_with_retry_async`, `post_with_retry` and `post_with_retry_async`
route the 429, redirect and SSL branches through the same helpers in edgar.httprequests,
and the identity decorators through one resolver. A shared helper is only proven shared
if every caller is checked, so each branch here is asserted once per caller: breaking a
helper, or unhooking one caller from it, fails the row for that caller.

Offline: the httpx2 client methods are patched, so no request leaves the process.
"""

import ssl
from unittest.mock import AsyncMock, patch

import httpx2
import pytest

from edgar.httprequests import (
    IdentityNotSetError,
    SSLVerificationError,
    TooManyRequestsError,
    get_with_retry,
    get_with_retry_async,
    post_with_retry,
    post_with_retry_async,
)

pytestmark = pytest.mark.fast

URL = "https://www.sec.gov/about/opendatasets"
RESOLVED = "https://www.sec.gov/data-research/investment-company"


async def _call_async(fn, method, response=None, side_effect=None, **kwargs):
    # A bare AsyncClient rather than async_http_client(): building the managed client
    # asks get_identity() for a User-Agent, which prompts on stdin when none is set.
    async with httpx2.AsyncClient() as client:
        with patch(f"httpx2.AsyncClient.{method}", return_value=response, side_effect=side_effect):
            return await fn(client, URL, **kwargs)


def _call(caller, response=None, side_effect=None, **kwargs):
    """Run one of the four request functions against a canned response or exception."""
    import asyncio

    if caller == "get":
        with patch("httpx2.Client.get", return_value=response, side_effect=side_effect):
            return get_with_retry(URL, **kwargs)
    if caller == "post":
        with patch("httpx2.Client.post", return_value=response, side_effect=side_effect):
            return post_with_retry(URL, data={"k": "v"}, **kwargs)
    if caller == "get_async":
        return asyncio.run(_call_async(get_with_retry_async, "get", response, side_effect, **kwargs))
    if caller == "post_async":
        return asyncio.run(_call_async(post_with_retry_async, "post", response, side_effect, data={"k": "v"}, **kwargs))
    raise AssertionError(caller)


CALLERS = ["get", "get_async", "post", "post_async"]


@pytest.mark.parametrize("caller", CALLERS)
def test_a_429_raises_too_many_requests_with_the_retry_after_header(caller):
    response = httpx2.Response(429, headers={"Retry-After": "7"})
    with pytest.raises(TooManyRequestsError) as exc_info:
        _call(caller, response)
    message = str(exc_info.value)
    assert "Retry-After: 7 seconds" in message
    assert URL in message


@pytest.mark.parametrize("caller", CALLERS)
def test_a_final_response_is_returned_unchanged(caller):
    response = httpx2.Response(200, text="ok")
    assert _call(caller, response) is response


@pytest.mark.parametrize("status_code", [301, 302])
@pytest.mark.parametrize(
    "caller,module_name",
    [
        ("get", "get_with_retry"),
        ("get_async", "get_with_retry_async"),
        ("post", "post_with_retry"),
        ("post_async", "post_with_retry_async"),
    ],
)
def test_a_redirect_is_followed_through_the_module_name_to_the_resolved_location(caller, module_name, status_code):
    # Patching the module attribute must intercept the follow-up request: tests across
    # the suite rely on the redirect recursing through the public name.
    response = httpx2.Response(status_code, headers={"Location": "/data-research/investment-company"})
    followed = httpx2.Response(200, text="followed")
    target = f"edgar.httprequests.{module_name}"
    if caller.endswith("_async"):
        with patch(target, new_callable=AsyncMock, return_value=followed) as follow:
            result = _call(caller, response)
    else:
        with patch(target, return_value=followed) as follow:
            result = _call(caller, response)
    assert result is followed
    follow.assert_called_once()
    called = follow.call_args
    # get passes url= by keyword; post passes it positionally (after the client, for async).
    followed_url = called.kwargs.get("url") or next(a for a in called.args if isinstance(a, str))
    assert followed_url == RESOLVED
    if caller.startswith("post"):
        assert called.kwargs["data"] == {"k": "v"}


@pytest.mark.parametrize("caller", CALLERS)
def test_an_ssl_connect_error_becomes_ssl_verification_error(caller):
    connect_error = httpx2.ConnectError("SSL error")
    connect_error.__cause__ = ssl.SSLCertVerificationError("certificate verify failed")
    with pytest.raises(SSLVerificationError) as exc_info:
        _call(caller, side_effect=connect_error)
    assert exc_info.value.__cause__ is connect_error
    assert URL in str(exc_info.value)


@pytest.mark.parametrize("caller", CALLERS)
def test_a_missing_identity_raises_before_any_request(caller, monkeypatch):
    monkeypatch.delenv("EDGAR_IDENTITY", raising=False)
    with pytest.raises(IdentityNotSetError):
        _call(caller, httpx2.Response(200))


@pytest.mark.parametrize("caller,method", [("get_async", "get"), ("post_async", "post")])
def test_the_async_pair_sends_the_resolved_identity_as_user_agent(caller, method):
    import asyncio

    async def go():
        async with httpx2.AsyncClient() as client:
            with patch(f"httpx2.AsyncClient.{method}", return_value=httpx2.Response(200)) as sent:
                fn = get_with_retry_async if method == "get" else post_with_retry_async
                await fn(client, URL, identity_callable=lambda: "fx90 probe probe@example.com")
                return sent

    sent = asyncio.run(go())
    assert sent.call_args.kwargs["headers"]["User-Agent"] == "fx90 probe probe@example.com"
