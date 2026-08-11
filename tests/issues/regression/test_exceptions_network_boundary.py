"""The network boundary: httpx failures become TransportError, once, at the edge.

Bead: edgartools-07lk.10, PR2 of 3. Design §5.

Before this, an httpx exception that survived every retry propagated verbatim
out of `get_with_retry` and friends, so `httpx.ReadTimeout` was part of our
public contract by accident — every user `except` clause naming it, and every
future call site, inherited a dependency's type. The wrap fixes that once at the
boundary rather than at each of the call sites.

The wrap is a 6.0 break (someone may be catching `httpx.HTTPError` around our
calls), so in 5.x it is gated on `EDGARTOOLS_STRICT_ERRORS`. That makes this
file's job two-sided: prove the wrap does the right thing when it is on, and
prove nothing at all changed when it is off.

WHAT THESE TESTS PROTECT, in order of how quietly each could break:

  1. **Retries still happen under strict.** The wrap must sit ABOVE `@retry`.
     Move it below and stamina sees `TransportError`, which is not in
     `RETRYABLE_EXCEPTIONS`, so every retried request silently becomes a
     single-shot one. Nothing about the raised type would look wrong; the
     library would just get worse at bad networks. `test_*_still_retries` is the
     only thing standing between us and that.
  2. **The generator boundary is entered.** `stream_with_retry` is a generator,
     and a decorator that treats it as a plain function returns the generator
     object without running a line of it — so the `except` never fires and the
     wrap silently does not apply to streaming.
  3. **`is_unreachable` excludes the deterministic failures.** SSL and identity
     errors carry no status, so a naive `status_code is None` check would let
     the offline-fallback paths swallow the two errors whose whole value is the
     message telling the user what to change.
  4. **The flag off is byte-for-byte the old behaviour.** That is what makes
     this shippable in 5.x.
"""
import asyncio

import httpx
import pytest
from stamina import retry

# Bound here, at module import time, ON PURPOSE. tests/conftest.py replaces this
# module attribute with a session-wide memoizing wrapper, and collection runs
# before session fixtures are set up — so this name is the real function while
# `submissions.download_entity_submissions_from_sec` is the wrapper. See
# test_the_submissions_tests_call_the_real_function for what goes wrong without it.
from edgar.entity.submissions import (
    download_entity_submissions_from_sec as _real_download_submissions,
)
from edgar.exceptions import (
    IdentityNotSetError,
    TooManyRequestsError,
    TransportError,
    http_status,
    strict_errors_enabled,
)
from edgar.httprequests import (
    RETRYABLE_EXCEPTIONS,
    TRANSPORT_ERRORS,
    UNREACHABLE_ERRORS,
    SSLVerificationError,
    inspect_response,
    is_unreachable,
    should_retry,
    wrap_transport_errors,
)

URL = "https://www.sec.gov/cgi-bin/browse-edgar"


@pytest.fixture
def strict(monkeypatch):
    monkeypatch.setenv("EDGARTOOLS_STRICT_ERRORS", "1")


@pytest.fixture
def lenient(monkeypatch):
    monkeypatch.delenv("EDGARTOOLS_STRICT_ERRORS", raising=False)


def _status_error(status: int, url: str = URL) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", url)
    return httpx.HTTPStatusError(
        f"{status}", request=request, response=httpx.Response(status, request=request)
    )


# Boundary doubles. Same decorator order as the real functions in
# httprequests.py: wrap_transport_errors OUTSIDE @retry.
def _retrying(fn):
    return wrap_transport_errors(
        retry(on=should_retry, attempts=3, wait_initial=0.001, wait_max=0.001)(fn)
    )


# ---------------------------------------------------------------------------
# The flag
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("1", True), ("true", True), ("TRUE", True), ("yes", True), ("on", True),
    (" 1 ", True), ("0", False), ("false", False), ("", False), ("maybe", False),
])
def test_strict_flag_reading(monkeypatch, value, expected):
    monkeypatch.setenv("EDGARTOOLS_STRICT_ERRORS", value)
    assert strict_errors_enabled() is expected


def test_strict_flag_is_read_per_call_not_captured_at_import(monkeypatch):
    """A test that sets the variable must be able to unset it again.

    Caching this at import would make the strict CI job the only way to
    exercise the wrapped paths, and make every test in this file order-dependent.
    """
    monkeypatch.delenv("EDGARTOOLS_STRICT_ERRORS", raising=False)
    assert strict_errors_enabled() is False
    monkeypatch.setenv("EDGARTOOLS_STRICT_ERRORS", "1")
    assert strict_errors_enabled() is True
    monkeypatch.delenv("EDGARTOOLS_STRICT_ERRORS")
    assert strict_errors_enabled() is False


# ---------------------------------------------------------------------------
# The wrap, on
# ---------------------------------------------------------------------------

def test_connect_failure_becomes_a_transport_error_with_no_status(strict):
    @_retrying
    def boundary(url):
        raise httpx.ConnectError("nodename nor servname provided")

    with pytest.raises(TransportError) as excinfo:
        boundary(URL)

    exc = excinfo.value
    assert exc.status_code is None, "no status means we never got an answer — the whole distinction"
    assert exc.url == URL
    assert isinstance(exc.__cause__, httpx.ConnectError), "the original must stay reachable"


def test_status_error_becomes_a_transport_error_carrying_the_status(strict):
    @_retrying
    def boundary(url):
        raise _status_error(503)

    with pytest.raises(TransportError) as excinfo:
        boundary(URL)

    exc = excinfo.value
    assert exc.status_code == 503
    assert http_status(exc) == 503
    assert "HTTP 503" in str(exc)
    assert isinstance(exc.__cause__, httpx.HTTPStatusError)


def test_the_url_comes_from_the_exception_when_it_has_one(strict):
    """After a redirect the call argument is stale; the exception is not."""
    redirected = "https://www.sec.gov/somewhere-else"

    @_retrying
    def boundary(url):
        raise _status_error(404, url=redirected)

    with pytest.raises(TransportError) as excinfo:
        boundary(URL)
    assert excinfo.value.url == redirected


def test_async_boundary_wraps(strict):
    @_retrying
    async def boundary(client, url):
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(TransportError) as excinfo:
        asyncio.run(boundary(None, URL))
    assert isinstance(excinfo.value.__cause__, httpx.ReadTimeout)
    assert excinfo.value.url == URL


def test_generator_boundary_wraps(strict):
    """The failure mode here is silent: a generator treated as a plain function
    returns without executing, so the except clause never sees anything."""
    @_retrying
    def boundary(url):
        yield b"first chunk"
        raise httpx.ReadTimeout("connection dropped mid-stream")

    with pytest.raises(TransportError) as excinfo:
        list(boundary(URL))
    assert isinstance(excinfo.value.__cause__, httpx.ReadTimeout)


def test_inspect_response_wraps_raise_for_status(strict):
    request = httpx.Request("GET", URL)
    response = httpx.Response(500, request=request)

    with pytest.raises(TransportError) as excinfo:
        inspect_response(response)
    assert excinfo.value.status_code == 500
    assert isinstance(excinfo.value.__cause__, httpx.HTTPStatusError)


@pytest.mark.parametrize("status", [200, 304])
def test_inspect_response_still_accepts_success_and_not_modified(strict, status):
    request = httpx.Request("GET", URL)
    assert inspect_response(httpx.Response(status, request=request)) is None


def test_our_own_transport_errors_pass_through_untouched(strict):
    """429 and SSL are already ours; the wrap must not re-wrap them."""
    @_retrying
    def rate_limited(url):
        raise TooManyRequestsError(url, retry_after=600)

    with pytest.raises(TooManyRequestsError) as excinfo:
        rate_limited(URL)
    assert excinfo.value.retry_after == 600
    assert excinfo.value.__cause__ is None


# ---------------------------------------------------------------------------
# The wrap, off — nothing changed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("original", [
    httpx.ConnectError("no route"),
    httpx.ReadTimeout("timed out"),
    _status_error(404),
])
def test_without_the_flag_httpx_propagates_verbatim(lenient, original):
    @_retrying
    def boundary(url):
        raise original

    with pytest.raises(type(original)) as excinfo:
        boundary(URL)
    assert excinfo.value is original, "not merely the same type — the same object"


def test_without_the_flag_inspect_response_still_raises_httpx(lenient):
    request = httpx.Request("GET", URL)
    with pytest.raises(httpx.HTTPStatusError):
        inspect_response(httpx.Response(500, request=request))


# ---------------------------------------------------------------------------
# Retries survive the wrap
# ---------------------------------------------------------------------------

def test_transport_error_is_not_retryable_which_is_why_order_matters():
    """The mechanism behind the bug the next two tests exist to catch."""
    assert not isinstance(TransportError("boom"), RETRYABLE_EXCEPTIONS)
    assert should_retry(httpx.ReadTimeout("x")) is True
    assert should_retry(TransportError("x")) is False


@pytest.mark.parametrize("flag", [True, False])
def test_the_boundary_still_retries(monkeypatch, flag):
    """Wrapping inside @retry would make this 1 instead of 3, and nothing else
    would look wrong."""
    if flag:
        monkeypatch.setenv("EDGARTOOLS_STRICT_ERRORS", "1")
    else:
        monkeypatch.delenv("EDGARTOOLS_STRICT_ERRORS", raising=False)

    attempts = []

    @_retrying
    def boundary(url):
        attempts.append(1)
        raise httpx.ReadTimeout("timed out")

    with pytest.raises((TransportError, httpx.ReadTimeout)):
        boundary(URL)
    assert len(attempts) == 3, (
        "the boundary stopped retrying — wrap_transport_errors is almost "
        "certainly applied below @retry instead of above it"
    )


def test_the_async_boundary_still_retries(strict):
    attempts = []

    @_retrying
    async def boundary(client, url):
        attempts.append(1)
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(TransportError):
        asyncio.run(boundary(None, URL))
    assert len(attempts) == 3


# ---------------------------------------------------------------------------
# TRANSPORT_ERRORS and is_unreachable
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("exc_type", [
    httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError,
    TransportError, TooManyRequestsError, SSLVerificationError, IdentityNotSetError,
])
def test_transport_errors_catches_both_eras(exc_type):
    """One `except TRANSPORT_ERRORS:` must mean the same thing before and after
    the flip, or every call site written against it needs revisiting in 6.0."""
    assert issubclass(exc_type, TRANSPORT_ERRORS)


@pytest.mark.parametrize("not_transport", [ValueError, AttributeError, KeyError, TypeError])
def test_transport_errors_stays_narrow(not_transport):
    assert not issubclass(not_transport, TRANSPORT_ERRORS)


@pytest.mark.parametrize("exc,expected", [
    (httpx.ConnectError("no route"), True),
    (httpx.ReadTimeout("timed out"), True),
    (httpx.TimeoutException("timed out"), True),
    (TransportError("could not reach"), True),
    (TransportError("SEC said no", status_code=404), False),
    (_status_error(500), False),
    (TooManyRequestsError(URL), False),
    (IdentityNotSetError(), False),
])
def test_is_unreachable(exc, expected):
    assert is_unreachable(exc) is expected


def test_ssl_failure_is_never_treated_as_unreachable():
    """It carries no status, so a `status_code is None` check would swallow it.

    The offline-fallback paths call is_unreachable to decide whether to give up
    quietly. An expired or intercepted certificate is deterministic and
    user-fixable, and the diagnostic message is the entire point of raising it —
    degrading it to "you seem to be offline" throws that away.
    """
    ssl_error = SSLVerificationError(httpx.ConnectError("certificate verify failed"), URL)
    assert ssl_error.status_code is None
    assert is_unreachable(ssl_error) is False


def test_unreachable_errors_are_all_retryable():
    """These are the transient ones; if one were not retryable, a caller falling
    back on it would be giving up on the first blip."""
    for exc_type in UNREACHABLE_ERRORS:
        assert issubclass(exc_type, RETRYABLE_EXCEPTIONS), exc_type


# ---------------------------------------------------------------------------
# The internal call sites, in both eras
#
# These are what the strict CI job is for. Each site sits above the boundary and
# translates a status it understands into a domain answer; each must give the
# same answer whichever era raised. A site that only handles the httpx type
# keeps passing today and starts falling through to its `raise` in 6.0 — the
# 404-becomes-None handling would simply stop existing, and no test naming httpx
# would notice.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raised", [_status_error(404), TransportError("gone", status_code=404)])
def test_company_facts_404_becomes_the_domain_error_in_both_eras(monkeypatch, raised):
    from edgar.entity import entity_facts
    from edgar.exceptions import CompanyFactsNotFoundError

    def fail(_url):
        raise raised

    monkeypatch.setattr(entity_facts, "download_json", fail)
    with pytest.raises(CompanyFactsNotFoundError) as excinfo:
        entity_facts.download_company_facts_from_sec(99999999)
    assert excinfo.value.cik == 99999999


@pytest.mark.parametrize("raised", [_status_error(503), TransportError("outage", status_code=503)])
def test_company_facts_outage_is_not_reported_as_missing_facts(monkeypatch, raised):
    """The distinction the transport branch exists for: a 503 is not "no facts"."""
    from edgar.entity import entity_facts
    from edgar.exceptions import CompanyFactsNotFoundError

    def fail(_url):
        raise raised

    monkeypatch.setattr(entity_facts, "download_json", fail)
    with pytest.raises(type(raised)) as excinfo:
        entity_facts.download_company_facts_from_sec(320193)
    assert not isinstance(excinfo.value, CompanyFactsNotFoundError)


@pytest.mark.parametrize("raised", [_status_error(404), TransportError("gone", status_code=404)])
def test_submissions_404_returns_none_in_both_eras(monkeypatch, raised):
    from edgar.entity import submissions

    def fail(_url):
        raise raised

    monkeypatch.setattr(submissions, "download_json", fail)
    assert _real_download_submissions(99999999) is None


@pytest.mark.parametrize("raised", [
    httpx.ConnectError("no route"),
    TransportError("could not reach SEC"),
])
def test_submissions_outage_is_not_reported_as_an_unknown_cik(monkeypatch, raised):
    """`None` here means "SEC has no such CIK". An outage returning None tells
    the user their company does not exist."""
    from edgar.entity import submissions

    def fail(_url):
        raise raised

    monkeypatch.setattr(submissions, "download_json", fail)
    with pytest.raises(type(raised)):
        _real_download_submissions(320193)


def test_the_submissions_tests_call_the_real_function():
    """Guard the two tests above against the wrapper that already broke them.

    `tests/conftest.py` memoizes `download_entity_submissions_from_sec` for the
    whole session by replacing the module attribute. For a CIK some earlier test
    already fetched — 320193 appears hundreds of times in this suite — the
    wrapper answers from its cache and never reaches the `except` clause under
    test. That is a green test that verifies nothing, and it is exactly what
    happened: both tests passed run alone and failed in the full regression run.

    Binding the function at module import time gets the real one, because
    collection finishes before session fixtures are set up. This asserts that
    binding still holds, so the day the import moves the test says so.
    """
    assert _real_download_submissions.__name__ == "download_entity_submissions_from_sec", (
        "the submissions tests are calling conftest's memoizing wrapper, which "
        "short-circuits on a cache hit and never exercises the code under test"
    )


@pytest.mark.parametrize("raised", [
    httpx.ConnectError("no route"),
    TransportError("could not reach SEC"),
])
def test_efts_accession_lookup_surfaces_the_outage(monkeypatch, raised):
    """Closes the tg7y sibling. `None` from this function means "EFTS has no
    filing at this accession", which routes the caller to the quarterly index —
    the wrong destination entirely when the real answer was an outage."""
    from edgar import httprequests
    from edgar.search import efts

    def fail(*_args, **_kwargs):
        raise raised

    monkeypatch.setattr(httprequests, "get_with_retry", fail)
    with pytest.raises(type(raised)):
        efts.resolve_accession("0000320193-23-000106")


def test_efts_accession_lookup_still_swallows_schema_drift(monkeypatch):
    """The other half of the same change: a malformed response is still None.

    Narrowing the transport case out of `except Exception` must not turn every
    parse hiccup into a raise — a pre-2001 accession legitimately answers None.
    """
    from edgar import httprequests
    from edgar.search import efts

    def garbage(*_args, **_kwargs):
        return httpx.Response(200, content=b"<html>not json</html>")

    monkeypatch.setattr(httprequests, "get_with_retry", garbage)
    assert efts.resolve_accession("0000320193-23-000106") is None


# ---------------------------------------------------------------------------
# http_status reads either era
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("exc,expected", [
    (_status_error(404), 404),
    (_status_error(403), 403),
    (TransportError("x", status_code=500), 500),
    (TransportError("x"), None),
    (httpx.ConnectError("no route"), None),
    (TooManyRequestsError(URL), 429),
    (ValueError("not a transport failure at all"), None),
])
def test_http_status(exc, expected):
    assert http_status(exc) == expected
