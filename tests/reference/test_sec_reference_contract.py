"""Contract tests for the SEC reference datasets edgartools depends on.

WHAT THIS IS FOR. SEC changes its own site and datasets on its own schedule.
The repo already has six ``test_*_contract.py`` files, but every one of them
pins a FILING parser; nothing watched the reference datasets. So when SEC turned
the investment-company dataset page into a 301 with a relative ``Location``,
nothing noticed: the fetch failed, the caller swallowed it, and every fund series
and class name silently degraded to its bare identifier. It surfaced days later
because two literal-value assertions in tests/test_funds.py happened to cover the
affected tickers.

This file is the detector that should have caught it on day one. Each test names
one external source, asserts a SPECIFIC value from it, and fails with a message
saying which source moved — so a red run points at SEC rather than at us.

WRITING TESTS HERE. Assert values, not existence: ``is not None`` passes on
exactly the degraded output this file exists to catch. Prefer a fact stable
across quarters (a class name, a floor on a row count) over one that drifts (an
exact row count, the current year's filing volume).

Marked ``network`` so it runs in the post-merge and nightly lanes, never on the
pull-request gate.
"""
import re

import pandas as pd
import pytest

pytestmark = pytest.mark.network


def _fail(source: str, detail: str) -> str:
    return (
        f"SEC reference source appears to have changed: {source}\n"
        f"  {detail}\n"
        "  This is a contract test — the likely cause is upstream, not a code change here."
    )


class TestFundReferenceData:
    """https://www.sec.gov/data-research/sec-markets-data/investment-company-series-class-information"""

    def test_landing_page_still_yields_a_csv_url(self):
        from edgar.funds.reference import _find_latest_fund_data_url

        url = _find_latest_fund_data_url()
        assert url.startswith("https://www.sec.gov/"), _fail(
            "investment-company series/class landing page",
            f"scrape returned a non-SEC url: {url!r}",
        )
        assert url.endswith(".csv"), _fail(
            "investment-company series/class landing page",
            f"scrape no longer resolves to a CSV: {url!r}",
        )

    def test_class_names_resolve_to_real_names_not_identifiers(self):
        """The exact degradation that went unnoticed: name falls back to class id."""
        from edgar.funds.reference import get_fund_reference_data

        ref = get_fund_reference_data()
        klass = ref.get_class("C000013712")
        assert klass is not None, _fail(
            "investment-company series/class CSV", "class C000013712 is missing from the dataset"
        )
        assert klass.name == "Advisor Class C", _fail(
            "investment-company series/class CSV",
            f"C000013712 resolved to {klass.name!r}, expected 'Advisor Class C' "
            "(a bare identifier here means the enrichment silently degraded)",
        )

    def test_find_fund_surfaces_the_name(self):
        """End to end through the public API, which is where users saw the bug."""
        from edgar.funds import find_fund

        fund_class = find_fund("KINCX")
        assert fund_class.name == "Advisor Class C", _fail(
            "fund lookup by ticker",
            f"find_fund('KINCX').name is {fund_class.name!r}, expected 'Advisor Class C'",
        )
        assert fund_class.class_id == "C000013712"


class TestBDCReference:
    """https://www.sec.gov/data-research/sec-markets-data/opendatasetsshtmlbdc"""

    def test_latest_report_year_is_not_the_stale_fallback(self):
        """Assert it moved PAST the fallback, not merely that it is >= it.

        get_latest_bdc_report_year() returns a hardcoded 2024 when every probe
        misses. A test asserting `>= 2024` would pass on exactly that failure,
        so the floor has to sit above the fallback to mean anything.
        """
        from edgar.bdc.reference import _BDC_REPORT_FALLBACK_YEAR, get_latest_bdc_report_year

        year = get_latest_bdc_report_year()
        assert year > _BDC_REPORT_FALLBACK_YEAR, _fail(
            "SEC BDC report",
            f"latest year is {year}, which is the hardcoded fallback "
            f"({_BDC_REPORT_FALLBACK_YEAR}) or older — every probe likely missed",
        )

    def test_report_lists_known_bdcs(self):
        """MAIN is a long-lived BDC; the yearly list churns, so pin on it."""
        from edgar.bdc.reference import get_bdc_list

        bdcs = get_bdc_list()
        assert len(bdcs) > 50, _fail("SEC BDC report", f"only {len(bdcs)} BDCs returned")
        ciks = {int(b.cik) for b in bdcs}
        assert 1396440 in ciks, _fail(
            "SEC BDC report", "Main Street Capital (CIK 1396440) is missing from the BDC list"
        )


class TestBDCDatasets:
    """https://www.sec.gov/data-research/sec-markets-data/bdc-data-sets"""

    def test_quarters_are_discoverable(self):
        from edgar.bdc.datasets import get_available_quarters

        quarters = get_available_quarters()
        assert quarters, _fail(
            "BDC quarterly datasets",
            "no quarters discovered — an empty list here does not distinguish "
            "'SEC published none' from 'we could not reach SEC'",
        )
        assert len(quarters) >= 4, _fail(
            "BDC quarterly datasets", f"only {len(quarters)} quarters discovered"
        )
        assert all(1 <= q <= 4 for _, q in quarters)


class TestTickerReferenceData:
    """The ticker and CIK datasets under https://www.sec.gov/files/."""

    def test_company_tickers_has_plausible_volume_and_known_members(self):
        from edgar.reference.tickers import get_company_tickers

        tickers = get_company_tickers()
        assert len(tickers) > 9000, _fail(
            "company_tickers.json", f"only {len(tickers)} rows (expected roughly 10k+)"
        )
        by_ticker = set(tickers["ticker"])
        for expected in ("AAPL", "MSFT", "JPM"):
            assert expected in by_ticker, _fail(
                "company_tickers.json", f"{expected} is missing from the ticker dataset"
            )

    def test_mutual_fund_tickers_keeps_its_column_contract(self):
        from edgar.reference.tickers import get_mutual_fund_tickers

        mf = get_mutual_fund_tickers()
        assert list(mf.columns) == ["cik", "seriesId", "classId", "ticker"], _fail(
            "mutual fund tickers", f"columns changed to {list(mf.columns)}"
        )
        assert len(mf) > 10000, _fail("mutual fund tickers", f"only {len(mf)} rows")
        assert "KINCX" in set(mf["ticker"]), _fail(
            "mutual fund tickers", "KINCX is missing from the mutual fund ticker dataset"
        )

    def test_cik_lookup_data_parses(self):
        from edgar.httprequests import download_text

        text = download_text("https://www.sec.gov/Archives/edgar/cik-lookup-data.txt")
        assert text, _fail("cik-lookup-data.txt", "downloaded empty")
        lines = [ln for ln in text.split("\n") if ln.strip()]
        assert len(lines) > 500000, _fail(
            "cik-lookup-data.txt", f"only {len(lines)} lines (expected 500k+)"
        )
        # Every line is NAME:CIK:, and that holds for all 1,056,064 of them as of
        # 2026-08-22 — so assert all, not a sample. NAME is allowed to be empty:
        # four real rows begin with ':' and sort to the top of the file, which is
        # why this is `.*` rather than `.+`.
        malformed = [ln for ln in lines if not re.match(r"^.*:\d{10}:$", ln)]
        assert not malformed, _fail(
            "cik-lookup-data.txt",
            f"{len(malformed)} lines no longer match NAME:CIK:, e.g. {malformed[:3]}",
        )


class TestSubmissionsApi:
    """https://data.sec.gov — the other host, with its own cache rules."""

    def test_company_submissions_still_shapes_as_expected(self):
        from edgar import Company

        apple = Company("AAPL")
        assert apple.cik == 320193, _fail(
            "data.sec.gov submissions", f"AAPL resolved to CIK {apple.cik}, expected 320193"
        )
        filings = apple.get_filings(form="10-K")
        assert len(filings) > 10, _fail(
            "data.sec.gov submissions", f"only {len(filings)} 10-K filings for AAPL"
        )
        assert isinstance(filings.to_pandas(), pd.DataFrame)
