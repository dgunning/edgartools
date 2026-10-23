"""Regression: extract_nonaccrual(BDCEntity) resolves the original 10-K, not a data-less 10-K/A.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1713

``BDCEntity.get_filings`` had no ``amendments`` argument, so ``_resolve_filing`` took the
newest filing, ARCC's 10-K/A 0001628280-26-020560 (filed 2026-03-23, adds Ivy Hill's
financial statements and has no investment facts). The original 10-K,
0001287750-26-000006 (filed 2026-02-04), carries the investment data.
"""
from unittest.mock import MagicMock

import pytest

from edgar.bdc.nonaccrual import _resolve_filing
from edgar.bdc.reference import BDCEntity


def test_get_filings_forwards_amendments_flag():
    entity = BDCEntity.__new__(BDCEntity)
    company = MagicMock()
    entity.get_company = lambda: company
    entity.get_filings(form="10-K", amendments=False)
    company.get_filings.assert_called_with(form="10-K", amendments=False)
    entity.get_filings(form="10-K")
    company.get_filings.assert_called_with(form="10-K", amendments=True)


def test_resolve_filing_excludes_amendments():
    entity = BDCEntity.__new__(BDCEntity)
    seen = {}

    def fake(form=None, amendments=True):
        seen.update(form=form, amendments=amendments)
        return []

    entity.get_filings = fake
    assert _resolve_filing(entity, "10-K") is None
    assert seen == {"form": "10-K", "amendments": False}


@pytest.mark.network
@pytest.mark.vcr
def test_arcc_resolves_original_10k():
    from edgar.bdc import get_bdc_list
    arcc = get_bdc_list().get_by_ticker("ARCC")
    filing = _resolve_filing(arcc, "10-K")
    assert filing.form == "10-K"
    assert filing.accession_no == "0001287750-26-000006"


def test_full_amendment_with_investment_data_supersedes_original(monkeypatch):
    from types import SimpleNamespace
    from decimal import Decimal
    import edgar.bdc.nonaccrual as na

    def filing(acc, form, date):
        return SimpleNamespace(accession_no=acc, form=form, filing_date=date, period_of_report="2025-12-31")

    original, amendment = filing("orig", "10-K", "2026-02-04"), filing("amend", "10-K/A", "2026-03-23")
    entity = BDCEntity.__new__(BDCEntity)
    class Rows(list):
        def latest(self, n):
            return self[0]

    def get_filings(form=None, amendments=True):
        return Rows([original] if not amendments else [amendment, original])

    entity.get_filings = get_filings

    def fake_extract(f, period=None):
        total = Decimal(100) if f.accession_no == "amend" else None
        return SimpleNamespace(source_filing=f.accession_no, total_portfolio_fair_value=total)

    monkeypatch.setattr(na, "_extract_nonaccrual_from_filing", fake_extract)
    assert na.extract_nonaccrual(entity).source_filing == "amend"
    monkeypatch.setattr(na, "_extract_nonaccrual_from_filing",
                        lambda f, period=None: SimpleNamespace(source_filing=f.accession_no,
                                                               total_portfolio_fair_value=None))
    assert na.extract_nonaccrual(entity).source_filing == "orig"


@pytest.mark.network
@pytest.mark.vcr
def test_arcc_data_less_amendment_warns():
    from edgar import find
    from edgar.bdc.nonaccrual import extract_nonaccrual

    amended = extract_nonaccrual(find("0001628280-26-020560"))  # 10-K/A, Ivy Hill statements only
    assert amended.extraction_method == "none"
    assert amended.nonaccrual_rate is None
    assert amended.warnings and "no investment data" in amended.warnings[0]
