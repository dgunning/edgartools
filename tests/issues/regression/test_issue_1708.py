"""
Regression test for GitHub issue #1708: EFTSResult.company kept SEC's display decoration

EFTS returns each filer as a display string, ``"NVIDIA CORP  (NVDA)  (CIK 0001045810)"``.
``resolve_accession()`` stripped the ticker and CIK with ``_clean_display_name``,
but ``_parse_hit`` (behind ``search_filings()``) copied the raw string into
``EFTSResult.company``, so the same filer had two names in one module.

The hit below is NVIDIA's FY2024 10-K, accession 0001045810-24-000029, as EFTS
served it on 2026-11-10 for ``q="0001045810-24-000029"``.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1708
"""

from types import SimpleNamespace

import pytest

from edgar.search import efts

NVDA_10K_HIT = (
    b'{"_id":"0001045810-24-000029:nvda-20240128.htm","_score":12.5,'
    b'"_source":{"ciks":["0001045810"],"form":"10-K","file_date":"2024-02-21",'
    b'"display_names":["NVIDIA CORP  (NVDA)  (CIK 0001045810)"],'
    b'"adsh":"0001045810-24-000029"}}'
)
BODY = b'{"hits":{"total":{"value":1,"relation":"eq"},"hits":[' + NVDA_10K_HIT + b']}}'


@pytest.fixture
def served(monkeypatch):
    monkeypatch.setattr("edgar.httprequests.get_with_retry",
                        lambda url, params=None, **kwargs: SimpleNamespace(content=BODY))


def test_search_result_company_is_the_bare_name(served):
    results = efts.search_filings('"0001045810-24-000029"')
    result = results[0]
    assert result.company == "NVIDIA CORP"
    assert result.cik == "0001045810"
    assert result.accession_number == "0001045810-24-000029"
    assert "NVDA" not in repr(result)


def test_search_and_accession_lookup_agree_on_the_name(served):
    assert efts.search_filings('"0001045810-24-000029"')[0].company == \
        efts.resolve_accession("0001045810-24-000029")["company"]


@pytest.mark.parametrize("names, expected", [([], None), ([""], "")])
def test_missing_and_empty_names_are_kept(names, expected):
    hit = {"_id": "x:y.htm", "_source": {"adsh": "0001045810-24-000029", "display_names": names}}
    assert efts._parse_hit(hit).company == expected
