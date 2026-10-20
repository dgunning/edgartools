"""Regression test for GitHub issue #1588.

find_company_cik() answered from the ticker table bundled at release before
SEC's live company_tickers.json, so a ticker that moved to a new registrant
after the bundle was taken kept resolving to the old CIK, with no warning:
Company("XOM") gave Exxon Mobil Corporation (CIK 34088) after SEC moved XOM to
ExxonMobil Holdings Corp (CIK 2115436). The 2026-06-01 bundle had 10 such tickers
by 2026-10-20 (XOM, NVRI, XPRO, CBAT among them).

GitHub Issue: https://github.com/dgunning/edgartools/issues/1588
"""
import pytest

from edgar import Company
from edgar.reference import tickers
from edgar.reference.tickers import find_cik, find_company_cik

# Captured at import: conftest swaps the module attribute out for offline tests
_live_lookup = tickers._get_live_company_cik_lookup.__wrapped__

BUNDLE = {"XOM": 34088, "OLDCO": 111}
LIVE = {"XOM": 2115436, "NEWCO": 222}


@pytest.fixture
def lookups(monkeypatch):
    def install(live):
        monkeypatch.setattr(tickers, "get_company_cik_lookup", lambda: BUNDLE)
        monkeypatch.setattr(tickers, "_get_live_company_cik_lookup", lambda: live)
    monkeypatch.delenv("EDGAR_USE_LOCAL_DATA", raising=False)
    return install


def test_live_sec_file_answers_before_the_bundle(lookups):
    lookups(LIVE)
    assert find_company_cik("XOM") == 2115436
    assert find_company_cik("newco") == 222


def test_bundle_answers_a_ticker_sec_no_longer_lists(lookups):
    lookups(LIVE)
    assert find_company_cik("OLDCO") == 111


def test_bundle_answers_offline(lookups):
    lookups(None)
    assert find_company_cik("XOM") == 34088
    assert find_company_cik("NEWCO") is None


def test_local_data_mode_keeps_the_bundle_first(lookups, monkeypatch):
    lookups(LIVE)
    monkeypatch.setenv("EDGAR_USE_LOCAL_DATA", "1")
    assert find_company_cik("XOM") == 34088
    assert find_company_cik("NEWCO") == 222


@pytest.mark.network
def test_xom_resolves_to_exxonmobil_holdings():
    # SEC's company_tickers.json maps XOM to CIK 2115436 (read 2026-10-20)
    assert find_cik("XOM") == 2115436
    assert Company("XOM").cik == 2115436


def test_live_fetch_makes_one_attempt_and_falls_back(monkeypatch):
    # Offline, get_with_retry spent ~16s retrying before the bundle could answer
    from httpx2 import ConnectError
    calls = []

    def unreachable(url, **kwargs):
        calls.append(url)
        raise ConnectError("offline")

    monkeypatch.setattr(tickers, "get_once", unreachable)
    assert _live_lookup() is None
    assert len(calls) == 1
