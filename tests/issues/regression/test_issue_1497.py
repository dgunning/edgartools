"""
Regression test for GitHub issue #1497: an EFTS error response was returned as 0 results

EFTS reports a failed query with HTTP 200 and an ``errorType``/``errorMessage``
body instead of ``hits``. ``_fetch_page`` read it with ``data.get("hits", {})``,
so ``search_filings("apple", start_date="2024-13-01")`` returned 0 results, and
the accession lookup returned None ("no filing at this accession"). The body
below is the one EFTS served for that query on 2026-10-08.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1497
"""

from types import SimpleNamespace

import pytest

from edgar.exceptions import TransportError
from edgar.search import efts

ERROR_BODY = (b'{"errorType":"ResponseError","errorMessage":"search_phase_execution_exception: '
              b'[date_time_exception] Reason: date_time_exception: Invalid value for MonthOfYear '
              b'(valid values 1 - 12): 13"}')
EMPTY_BODY = (b'{"took":5,"timed_out":false,"_shards":{"total":50,"successful":50,"skipped":0,"failed":0},'
              b'"hits":{"total":{"value":0,"relation":"eq"},"max_score":null,"hits":[]}}')


@pytest.fixture
def efts_body(monkeypatch):
    def serve(body):
        monkeypatch.setattr("edgar.httprequests.get_with_retry", lambda *args, **kwargs: SimpleNamespace(content=body))
    return serve


def test_error_body_raises_instead_of_returning_no_results(efts_body):
    efts_body(ERROR_BODY)
    with pytest.raises(TransportError, match="Invalid value for MonthOfYear"):
        efts.search_filings("apple", start_date="2024-13-01", end_date="2024-12-31")


def test_error_body_raises_in_accession_lookup(efts_body):
    efts_body(ERROR_BODY)
    with pytest.raises(TransportError):
        efts.resolve_accession("0000320193-24-000123")


def test_a_real_empty_result_is_still_empty(efts_body):
    efts_body(EMPTY_BODY)
    assert efts.search_filings("no such phrase anywhere", start_date="2024-01-01").total == 0
