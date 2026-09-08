"""
Tests for URL builder utilities (edgar.urls).

Pure logic — string formatting, no network calls.
"""

from edgar.urls import (
    build_archive_url,
    build_api_url,
    build_submissions_url,
    build_company_facts_url,
    build_full_index_url,
    build_daily_index_url,
    build_feed_url,
    build_ticker_url,
    build_company_tickers_url,
    build_mutual_fund_tickers_url,
    build_company_tickers_exchange_url,
)


class TestBuildArchiveUrl:

    def test_basic_path(self):
        url = build_archive_url("data/some-file.txt")
        assert url.endswith("/data/some-file.txt")
        assert "Archives/edgar" in url

    def test_leading_slash_stripped(self):
        url = build_archive_url("/data/some-file.txt")
        assert "//" not in url.split("://", 1)[1]


class TestBuildApiUrl:

    def test_basic(self):
        url = build_api_url("xbrl/companyfacts/CIK0000320193.json")
        assert "api/xbrl/companyfacts" in url

    def test_leading_slash_stripped(self):
        url = build_api_url("/xbrl/stuff")
        assert "//" not in url.split("://", 1)[1]


class TestBuildSubmissionsUrl:

    def test_cik_padding(self):
        url = build_submissions_url(320193)
        assert "CIK0000320193.json" in url

    def test_cik_already_large(self):
        url = build_submissions_url(1234567890)
        assert "CIK1234567890.json" in url


class TestBuildCompanyFactsUrl:

    def test_cik_padding(self):
        url = build_company_facts_url(320193)
        assert "CIK0000320193.json" in url
        assert "companyfacts" in url


class TestBuildFullIndexUrl:

    def test_format(self):
        url = build_full_index_url(2024, 3, "company", "idx")
        assert "full-index/2024/QTR3/company.idx" in url


class TestBuildDailyIndexUrl:

    def test_format(self):
        url = build_daily_index_url(2024, 1, "form", "idx")
        assert "daily-index/2024/QTR1/form.idx" in url


class TestBuildFeedUrl:

    def test_format(self):
        url = build_feed_url(2023, 2)
        assert "Feed/2023/QTR2/" in url


class TestReferenceUrls:

    def test_ticker_url(self):
        url = build_ticker_url()
        assert "ticker.txt" in url

    def test_company_tickers_url(self):
        url = build_company_tickers_url()
        assert "company_tickers.json" in url

    def test_mutual_fund_tickers_url(self):
        url = build_mutual_fund_tickers_url()
        assert "company_tickers_mf.json" in url

    def test_company_tickers_exchange_url(self):
        url = build_company_tickers_exchange_url()
        assert "company_tickers_exchange.json" in url
