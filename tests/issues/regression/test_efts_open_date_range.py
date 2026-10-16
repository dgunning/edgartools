"""
search_filings(start_date=...) without end_date searched every year.

Bead: edgartools-329yu

EFTS applies ``dateRange=custom`` only when it receives both ``startdt`` and
``enddt``; with one of them it silently ignores the range. search_filings sent
only the bound the caller gave, so ``search_filings("tariff", forms="10-K",
start_date="2025-01-01")`` returned 10,000+ hits led by filings from 2010 and
2003, measured against raw EFTS on 2026-10-16. With ``enddt`` added, the same
query has 3,841 hits, all filed 2025-26. The documented example in the
search_filings docstring passed ``start_date`` alone. An open end is now closed:
a missing start becomes 2001-01-01 (the start of EFTS coverage) and a missing
end becomes tomorrow.
"""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from edgar.search import efts

EMPTY_BODY = (b'{"took":5,"timed_out":false,"_shards":{"total":50,"successful":50,"skipped":0,"failed":0},'
              b'"hits":{"total":{"value":0,"relation":"eq"},"max_score":null,"hits":[]}}')


@pytest.fixture
def sent_params(monkeypatch):
    requests = []

    def fake_get(url, params=None, **kwargs):
        requests.append(dict(params or {}))
        return SimpleNamespace(content=EMPTY_BODY)

    monkeypatch.setattr("edgar.httprequests.get_with_retry", fake_get)

    def search(**kwargs):
        efts.search_filings("tariff", forms="10-K", **kwargs)
        return requests[-1]

    return search


@pytest.mark.fast
def test_start_date_alone_also_sends_an_end_date(sent_params):
    params = sent_params(start_date="2025-01-01")
    assert params["dateRange"] == "custom"
    assert params["startdt"] == "2025-01-01"
    assert params["enddt"] == (date.today() + timedelta(days=1)).isoformat()


@pytest.mark.fast
def test_end_date_alone_also_sends_a_start_date(sent_params):
    params = sent_params(end_date="2003-12-31")
    assert params["startdt"] == "2001-01-01"
    assert params["enddt"] == "2003-12-31"


@pytest.mark.fast
def test_both_dates_are_sent_as_given(sent_params):
    params = sent_params(start_date="2024-02-01", end_date="2024-03-31")
    assert (params["startdt"], params["enddt"]) == ("2024-02-01", "2024-03-31")


@pytest.mark.fast
def test_no_dates_sends_no_range(sent_params):
    params = sent_params()
    assert not {"dateRange", "startdt", "enddt"} & set(params)


@pytest.mark.network
def test_start_date_alone_restricts_the_results():
    results = efts.search_filings("tariff", forms="10-K", start_date="2025-01-01")
    assert len(results) > 0
    early = [(r.company, r.filed) for r in results if str(r.filed) < "2025-01-01"]
    assert not early, f"filings from before the start date came back: {early[:3]}"
    # 3,841 on 2026-10-16 and only growing; unfiltered it is EFTS's 10,000 cap
    assert results.total < 10_000


@pytest.mark.network
def test_end_date_alone_restricts_the_results():
    results = efts.search_filings("tariff", forms="10-K", end_date="2003-12-31")
    late = [(r.company, r.filed) for r in results if str(r.filed) > "2003-12-31"]
    assert not late, f"filings from after the end date came back: {late[:3]}"
    assert results.total == 2117  # raw EFTS, startdt=2001-01-01&enddt=2003-12-31, 2026-10-16
