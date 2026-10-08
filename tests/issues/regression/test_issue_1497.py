"""
Regression test for GitHub issue #1497: an EFTS error response was returned as 0 results

EFTS reports a failed query with HTTP 200 and an ``errorType``/``errorMessage``
body instead of ``hits``. ``_fetch_page`` read it with ``data.get("hits", {})``,
so ``search_filings("apple", start_date="2024-13-01")`` returned 0 results, and
the accession lookup returned None ("no filing at this accession").

Two bodies are covered, both as EFTS served them on 2026-10-08:
- a malformed date (``Invalid value for MonthOfYear``), now rejected before the
  request as ``InvalidDateError``;
- a page past the 10,000-hit window (``Result window is too large``). EFTS serves
  100 hits per request whatever ``size`` says, so ``from=9950`` is refused even
  with ``size=50``. ``next()`` and ``fetch_more()`` stop at ``from=9900``.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1497
"""

from types import SimpleNamespace

import pytest

from edgar.exceptions import InvalidDateError, TransportError
from edgar.search import efts

DATE_ERROR_BODY = (b'{"errorType":"ResponseError","errorMessage":"search_phase_execution_exception: '
                   b'[date_time_exception] Reason: date_time_exception: Invalid value for MonthOfYear '
                   b'(valid values 1 - 12): 13"}')
WINDOW_ERROR_BODY = (b'{"errorType":"ResponseError","errorMessage":"search_phase_execution_exception: '
                     b'[illegal_argument_exception] Reason: Result window is too large, from + size must be '
                     b'less than or equal to: [10000] but was [10050]."}')
EMPTY_BODY = (b'{"took":5,"timed_out":false,"_shards":{"total":50,"successful":50,"skipped":0,"failed":0},'
              b'"hits":{"total":{"value":0,"relation":"eq"},"max_score":null,"hits":[]}}')
HIT = (b'{"_id":"0000320193-24-000123:aapl-20240928.htm","_source":{"ciks":["0000320193"],"form":"10-K",'
       b'"file_date":"2024-11-01","display_names":["Apple Inc. (AAPL)"],"adsh":"0000320193-24-000123"}}')
BROAD_BODY = (b'{"hits":{"total":{"value":10000,"relation":"gte"},"hits":[' + b','.join([HIT] * 100) + b']}}')


@pytest.fixture
def efts_body(monkeypatch):
    requests = []

    def serve(body):
        def fake_get(url, params=None, **kwargs):
            requests.append(dict(params or {}))
            return SimpleNamespace(content=body)
        monkeypatch.setattr("edgar.httprequests.get_with_retry", fake_get)
        return requests
    return serve


def test_error_body_raises_instead_of_returning_no_results(efts_body):
    efts_body(WINDOW_ERROR_BODY)
    with pytest.raises(TransportError, match="Result window is too large"):
        efts._fetch_page({"q": "revenue"}, offset=0, limit=100)


def test_error_body_raises_in_accession_lookup(efts_body):
    efts_body(DATE_ERROR_BODY)
    with pytest.raises(TransportError):
        efts.resolve_accession("0000320193-24-000123")


def test_a_real_empty_result_is_still_empty(efts_body):
    efts_body(EMPTY_BODY)
    assert efts.search_filings("no such phrase anywhere", start_date="2024-01-01").total == 0


@pytest.mark.parametrize("bad", [{"start_date": "2024-13-01"}, {"end_date": "2024/12/31"}, {"start_date": "yesterday"}])
def test_malformed_date_is_rejected_before_the_request(efts_body, bad):
    requests = efts_body(DATE_ERROR_BODY)
    with pytest.raises(InvalidDateError, match="YYYY-MM-DD"):
        efts.search_filings("apple", **bad)
    assert requests == []


def test_next_stops_before_the_page_efts_refuses(efts_body):
    requests = efts_body(BROAD_BODY)
    page = efts.search_filings("revenue", limit=50)
    assert page.total == 10_000

    last = efts.EFTSSearch(query="revenue", total=10_000, results=page.results, _params=page._params, _offset=9_900)
    assert last.next() is None
    assert [r.get("from") for r in requests] == [None]

    allowed = efts.EFTSSearch(query="revenue", total=10_000, results=page.results, _params=page._params, _offset=9_850)
    assert allowed.next() is not None
    assert requests[-1]["from"] == 9_900


def test_fetch_more_stops_at_the_window(efts_body):
    requests = efts_body(BROAD_BODY)
    page = efts.search_filings("revenue", limit=50)
    near_end = efts.EFTSSearch(query="revenue", total=10_000, results=page.results, _params=page._params, _offset=9_800)

    more = near_end.fetch_more(1_000)

    assert [r["from"] for r in requests[1:]] == [9_850]
    assert len(more.results) == 150
