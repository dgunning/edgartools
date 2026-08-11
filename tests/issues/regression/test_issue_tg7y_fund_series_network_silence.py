"""Regression test: a network failure must not look like a fund with no filings.

Bead: edgartools-tg7y. Related: edgartools-07lk.10 (unified error policy).

``Fund.get_filings(series_only=True)`` returned an EMPTY ``Filings`` when the SEC
could not be reached. Two layers collaborated to produce it:

  edgar/funds/data.py   direct_get_fund_with_filings caught Exception, logged a
                        warning and returned None
  edgar/funds/core.py   _get_series_filings saw None, returned None, and
                        get_filings turned that into Filings([])

Nothing downstream could notice, because this path deliberately has no fallback:
returning the unfiltered trust would hand back a sibling series' data (GH #888).
So an outage told the user the series had filed nothing, and the only trace was a
log line.

Found by running the offline audit harness over the network-marked regression
tests. 626 of 631 failed with an explicit connection error; six failed on
``assert None is not None`` instead, which is the signature of a transport error
that something converted into a missing value.

These tests inject the failure at the transport boundary (``download_text``)
rather than by blocking sockets, for two reasons: it runs offline in the PR gate,
and the socket-level harness raises a RuntimeError that httpx never wraps, so it
would not exercise the httpx-keyed guard that the real failure goes through.
"""

import httpx
import pytest

from edgar.funds.core import Fund
from edgar.httprequests import (
    TRANSPORT_ERRORS,
    IdentityNotSetError,
    SSLVerificationError,
    TooManyRequestsError,
)

# Vanguard Long-Term Corporate Bond ETF (VCLT). Any real series ID works; the
# lookup never completes in these tests because the transport is made to fail.
VCLT_SERIES = "S000026864"


@pytest.fixture
def fund_with_series():
    """A Fund pinned to a series, without touching the network to build it."""
    fund = Fund.__new__(Fund)
    fund._target_series_id = VCLT_SERIES
    fund._series = None
    fund._company = None
    fund._entity = None
    fund._series_resolution = "test"
    return fund


def _fail_with(exc):
    def _raise(*args, **kwargs):
        raise exc
    return _raise


@pytest.mark.parametrize("exc", [
    httpx.ConnectError("connection refused"),
    httpx.ReadTimeout("timed out"),
    TooManyRequestsError("https://www.sec.gov/cgi-bin/browse-edgar", retry_after=60),
])
def test_transport_failure_raises_instead_of_reporting_an_empty_series(
    monkeypatch, fund_with_series, exc
):
    """The failure reaches the caller rather than becoming zero filings."""
    monkeypatch.setattr("edgar.funds.data.download_text", _fail_with(exc))

    with pytest.raises(type(exc)):
        fund_with_series.get_filings(series_only=True)


def test_the_old_behaviour_is_gone_specifically_an_empty_filings(
    monkeypatch, fund_with_series
):
    """Pin the exact regression: not just 'raises', but 'does not return empty'.

    Written separately from the parametrized test above because the bug was never
    an exception of the wrong type — it was a perfectly well-formed empty result,
    which no `pytest.raises` on its own distinguishes from a fix that returns
    empty for a different reason.
    """
    monkeypatch.setattr(
        "edgar.funds.data.download_text",
        _fail_with(httpx.ConnectError("connection refused")),
    )

    try:
        result = fund_with_series.get_filings(series_only=True)
    except httpx.ConnectError:
        return  # correct: the outage surfaced

    pytest.fail(
        "get_filings(series_only=True) returned "
        f"{type(result).__name__} with len={len(result)} during a connection "
        "failure. An empty result here is indistinguishable from a series that "
        "has filed nothing, and this path has no fallback that could correct it."
    )


def test_a_genuine_miss_is_still_an_empty_result_not_an_error(
    monkeypatch, fund_with_series
):
    """The fix must not turn 'no such series' into an exception.

    browse-edgar answers an unknown identifier with a page containing
    "No matching". That is an answer, and it must keep producing an empty
    Filings — otherwise the guard has traded one wrong behaviour for another.
    """
    monkeypatch.setattr(
        "edgar.funds.data.download_text",
        lambda *a, **k: "<html><body>No matching Ticker Symbol.</body></html>",
    )

    result = fund_with_series.get_filings(series_only=True)
    assert len(result) == 0, (
        f"expected an empty Filings for an unresolvable series, got {len(result)}"
    )


def test_a_parse_failure_is_still_swallowed_to_empty(monkeypatch, fund_with_series):
    """Scope check: only transport errors were promoted, not everything.

    Schema drift in browse-edgar's HTML still degrades to an empty result rather
    than raising. That is the pre-existing contract and this change deliberately
    left it alone — widening it is a separate decision (edgartools-07lk.10).
    """
    monkeypatch.setattr(
        "edgar.funds.data.download_text",
        _fail_with(ValueError("unexpected table shape")),
    )

    result = fund_with_series.get_filings(series_only=True)
    assert len(result) == 0


def test_transport_errors_tuple_covers_what_the_http_layer_actually_raises():
    """A guard keyed on the wrong types is not a guard.

    httpx.HTTPError is the base of ConnectError/ReadTimeout/HTTPStatusError, so
    naming it covers that family without enumerating it. TransportError covers
    ours the same way — 429, SSL and identity are all subclasses of it, and so
    is everything the boundary wrap raises under EDGARTOOLS_STRICT_ERRORS. Both
    bases stay listed through 6.0 so this tuple means the same thing in either
    era (bead edgartools-07lk.10).
    """
    assert issubclass(httpx.ConnectError, TRANSPORT_ERRORS)
    assert issubclass(httpx.ReadTimeout, TRANSPORT_ERRORS)
    assert issubclass(httpx.HTTPStatusError, TRANSPORT_ERRORS)
    assert issubclass(TooManyRequestsError, TRANSPORT_ERRORS)
    assert issubclass(SSLVerificationError, TRANSPORT_ERRORS)
    assert issubclass(IdentityNotSetError, TRANSPORT_ERRORS)

    # And it must NOT swallow ordinary bugs into the transport bucket.
    assert not issubclass(ValueError, TRANSPORT_ERRORS)
    assert not issubclass(AttributeError, TRANSPORT_ERRORS)
