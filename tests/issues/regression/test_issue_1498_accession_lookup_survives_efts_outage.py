"""Regression: an EDGAR full-text search outage must not break ``find(accession)``.

GitHub PR: https://github.com/dgunning/edgartools/pull/1498

Opening a filing from an accession asks EFTS first (~2 KB) and falls back to the
quarterly filing index (bead edgartools-vx29). EFTS often fails on its own while
the archive answers: on 2026-10-14 and 10-15 it returned HTTP 200 with
``{"errorType": "ConnectionError", "errorMessage": "getaddrinfo EBUSY vpc-efts-prod-..."}``.

#1498 made that body raise ``TransportError`` instead of reading as "no hits",
and ``resolve_accession`` re-raises transport errors (edgartools-07lk.10), so
``find(accession)`` raised for filings the index would have found. Five
regression tests failed that way across three PRs in two days.

``resolve_accession`` still raises; ``_filing_from_efts``, the caller that has
a correct fallback, now logs a warning and returns None so the index is asked.
"""

import logging

import pytest

from edgar import _filings
from edgar._filings import _filing_from_efts, get_filing_by_accession
from edgar.exceptions import TransportError
from edgar.search.efts import resolve_accession

pytestmark = pytest.mark.fast

EFTS_ERROR_BODY = {
    "errorType": "ConnectionError",
    "errorMessage": "getaddrinfo EBUSY vpc-efts-prod-opensearchservice-example.us-east-1.es.amazonaws.com",
}


def _efts_response(payload):
    """Minimal stand-in for the object get_with_retry returns."""
    import orjson

    class _Response:
        content = orjson.dumps(payload)

    return _Response()


@pytest.fixture
def efts_error_body(monkeypatch):
    monkeypatch.setattr("edgar.httprequests.get_with_retry", lambda *a, **k: _efts_response(EFTS_ERROR_BODY))


def test_resolve_accession_still_raises_on_the_error_body(efts_error_body):
    with pytest.raises(TransportError, match="getaddrinfo EBUSY"):
        resolve_accession("0000746601-18-000009")


@pytest.mark.parametrize("failure", ["error-body", "transport-error"])
def test_filing_from_efts_is_a_miss_with_a_warning(monkeypatch, caplog, failure):
    if failure == "error-body":
        monkeypatch.setattr("edgar.httprequests.get_with_retry", lambda *a, **k: _efts_response(EFTS_ERROR_BODY))
    else:
        def fail(*_args, **_kwargs):
            raise TransportError("could not reach efts.sec.gov")
        monkeypatch.setattr("edgar.httprequests.get_with_retry", fail)

    with caplog.at_level(logging.WARNING):
        assert _filing_from_efts("0000746601-18-000009") is None
    assert "0000746601-18-000009" in caplog.text
    assert "quarterly filing index" in caplog.text


def test_accession_lookup_falls_back_to_the_quarterly_index(efts_error_body, monkeypatch):
    # A made-up accession: get_filing_by_accession caches what it returns, and
    # this stand-in must never answer for a real filing in a later test.
    accession = "0009999999-18-000001"
    found = object()
    asked = []

    class _QuarterIndex:
        def __init__(self, quarter):
            self.quarter = quarter

        def get(self, wanted):
            return found if wanted == accession and self.quarter == 2 else None

    def cached_filings(year, quarter):
        asked.append((year, quarter))
        return _QuarterIndex(quarter)

    monkeypatch.setattr(_filings, "_get_cached_filings", cached_filings)

    assert get_filing_by_accession(accession, 2018) is found
    assert asked == [(2018, 1), (2018, 2)]
