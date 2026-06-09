"""Regression test for GitHub issue #843 (series-level ticker resolution).

An ETF ticker resolves to the umbrella registrant (e.g. VOO -> VANGUARD INDEX
FUNDS, CIK 36405), which files one NPORT-P per series. So
company.get_filings(form="NPORT-P") returns every Vanguard index series, not just
VOO's. Fund(ticker).get_filings(series_only=True) is meant to isolate the one
series via an EFTS full-text search on the series ID, but the path was dead code:
it checked `hasattr(results, "filings")`, and EFTSSearch has no such attribute, so
it always silently fell through and returned all series.

The fix adds EFTSSearch.to_filings() and rewrites the series_only path to page
through the EFTS hits and convert them to a Filings index.
"""
from datetime import date

import pytest

from edgar.search.efts import EFTSResult, EFTSSearch


def _result(accession, form="NPORT-P", filed="2025-03-31", company="Vanguard 500 Index Fund", cik="1752724"):
    return EFTSResult(accession_number=accession, form=form, filed=filed, company=company, cik=cik)


# --------------------------------------------------------------------------- #
# EFTSSearch.to_filings() (fast, no network)
# --------------------------------------------------------------------------- #

@pytest.mark.fast
def test_to_filings_builds_filings_index():
    search = EFTSSearch(
        query='"S000002839"',
        total=2,
        results=[
            _result("0001752724-25-126250", filed="2025-03-31"),
            _result("0001752724-24-100000", filed="2024-12-31"),
        ],
    )
    filings = search.to_filings()

    assert len(filings) == 2
    # Columns match the global Filings schema and values round-trip.
    assert set(filings.data.column_names) >= {"form", "company", "cik", "filing_date", "accession_number"}
    accessions = filings.data["accession_number"].to_pylist()
    assert "0001752724-25-126250" in accessions
    assert filings.data["cik"].to_pylist()[0] == 1752724
    assert filings.data["filing_date"].to_pylist()[0] == date(2025, 3, 31)


@pytest.mark.fast
def test_to_filings_empty_results():
    search = EFTSSearch(query="x", total=0, results=[])
    assert len(search.to_filings()) == 0


@pytest.mark.fast
def test_to_filings_tolerates_bad_cik_and_date():
    search = EFTSSearch(
        query="x", total=1,
        results=[_result("0001-25-1", filed="not-a-date", cik=None)],
    )
    filings = search.to_filings()
    assert len(filings) == 1
    assert filings.data["cik"].to_pylist()[0] == 0
    assert filings.data["filing_date"].to_pylist()[0] is None


# --------------------------------------------------------------------------- #
# End-to-end series isolation (network)
# --------------------------------------------------------------------------- #

@pytest.mark.network
def test_fund_series_only_isolates_etf_series():
    import edgar
    from edgar.funds import Fund
    edgar.set_identity("research@example.com")

    fund = Fund("VOO")
    assert fund._target_series_id == "S000002839"

    series_filings = fund.get_filings(series_only=True, form="NPORT-P")
    all_series_filings = fund.get_filings(form="NPORT-P")

    # series_only must be a strict, non-empty subset of the registrant's filings.
    assert 0 < len(series_filings) < len(all_series_filings)

    # Every returned report belongs to VOO's series.
    for filing in series_filings.head(4):
        report = filing.obj()
        assert report.series_id == "S000002839"
        assert report.matches_ticker("VOO")
