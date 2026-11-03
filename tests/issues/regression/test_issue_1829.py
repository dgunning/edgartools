"""Regression test for GitHub issue #1829.

Equity Residential renamed itself Vivmark Residential (VMRK) on 2026-08-12 and
kept CIK 906107. SEC's company_tickers.json lists current tickers only, so after
the bundled ticker data was refreshed (#1646), Company("EQR") raised
CompanyNotFoundError. A reviewed table of retired tickers now answers after the
live, bundled and fund lookups all miss, so a reused ticker still resolves to
its current owner.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1829
"""
import pytest

from edgar import Company
from edgar.entity import CompanyNotFoundError
from edgar.reference import tickers
from edgar.reference.tickers import find_cik, find_retired_ticker_cik

EQUITY_RESIDENTIAL = 906107


@pytest.fixture
def current_maps(monkeypatch):
    def install(company=None, fund=None):
        monkeypatch.setattr(tickers, "find_company_cik", lambda ticker: company)
        monkeypatch.setattr(tickers, "find_mutual_fund_cik", lambda ticker: fund)
    return install


def test_retired_ticker_keeps_its_cik():
    assert find_retired_ticker_cik("EQR") == EQUITY_RESIDENTIAL
    assert find_retired_ticker_cik("eqr") == EQUITY_RESIDENTIAL


def test_unknown_or_bad_ticker_is_not_retired():
    assert find_retired_ticker_cik("ZZZZQ") is None
    assert find_retired_ticker_cik(None) is None


def test_find_cik_falls_back_to_a_retired_ticker(current_maps):
    current_maps()
    assert find_cik("EQR") == EQUITY_RESIDENTIAL


def test_a_current_mapping_wins_over_a_retired_one(current_maps):
    # If SEC hands EQR to another registrant, that registrant is the answer
    current_maps(company=1234567)
    assert find_cik("EQR") == 1234567
    current_maps(fund=7654321)
    assert find_cik("EQR") == 7654321


def test_a_ticker_nobody_has_held_still_raises(current_maps):
    current_maps()
    with pytest.raises(CompanyNotFoundError):
        Company("ZZZZQ")


@pytest.mark.network
def test_eqr_resolves_to_equity_residential():
    company = Company("EQR")
    assert company.cik == EQUITY_RESIDENTIAL
    # SEC submissions for CIK 906107 (read 2026-11-03): renamed 2026-08-12
    assert company.name == "VIVMARK RESIDENTIAL"
