"""Tests for edgar.config module - SEC URL configuration"""
import os
import pytest
import importlib


@pytest.fixture
def clean_env():
    """Clean environment variables before and after tests"""
    env_vars = ['EDGAR_BASE_URL', 'EDGAR_DATA_URL', 'EDGAR_XBRL_URL', 'EDGAR_RATE_LIMIT_PER_SEC']
    # Store original values
    original = {k: os.environ.get(k) for k in env_vars}

    # Clean before test
    for var in env_vars:
        os.environ.pop(var, None)

    yield

    # Restore after test
    for var in env_vars:
        os.environ.pop(var, None)
        if original[var] is not None:
            os.environ[var] = original[var]


@pytest.mark.fast
class TestConfig:
    """Test configuration module"""

    def test_default_urls(self, clean_env):
        """Test default SEC URLs are returned when no env vars set"""
        # Need to reload module to pick up environment changes
        import edgar.config
        importlib.reload(edgar.config)

        assert edgar.config.SEC_BASE_URL == "https://www.sec.gov"
        assert edgar.config.SEC_DATA_URL == "https://data.sec.gov"
        assert edgar.config.SEC_XBRL_URL == "http://xbrl.sec.gov"
        assert edgar.config.SEC_ARCHIVE_URL == "https://www.sec.gov/Archives/edgar"

    def test_custom_base_url(self, clean_env):
        """Test custom base URL from environment variable"""
        os.environ['EDGAR_BASE_URL'] = "https://mysite.com"

        import edgar.config
        importlib.reload(edgar.config)

        assert edgar.config.SEC_BASE_URL == "https://mysite.com"
        assert edgar.config.SEC_ARCHIVE_URL == "https://mysite.com/Archives/edgar"

    def test_custom_data_url(self, clean_env):
        """Test custom data URL from environment variable"""
        os.environ['EDGAR_DATA_URL'] = "https://data.mysite.com"

        import edgar.config
        importlib.reload(edgar.config)

        assert edgar.config.SEC_DATA_URL == "https://data.mysite.com"

    def test_url_strips_trailing_slash(self, clean_env):
        """Test that trailing slashes are stripped from URLs"""
        os.environ['EDGAR_BASE_URL'] = "https://mysite.com/"

        import edgar.config
        importlib.reload(edgar.config)

        assert edgar.config.SEC_BASE_URL == "https://mysite.com"

    def test_rate_limit_default(self, clean_env):
        """Test default rate limit is 9 req/sec"""
        import edgar.httpclient
        importlib.reload(edgar.httpclient)

        assert edgar.httpclient.get_edgar_rate_limit_per_sec() == 9

    def test_rate_limit_custom(self, clean_env):
        """Test custom rate limit from environment"""
        os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = '20'

        import edgar.httpclient
        importlib.reload(edgar.httpclient)

        assert edgar.httpclient.get_edgar_rate_limit_per_sec() == 20


@pytest.mark.fast
class TestURLBuilders:
    """Test URL builder utilities"""

    def test_build_archive_url_default(self, clean_env):
        """Test archive URL building with defaults"""
        import edgar.config
        import edgar.urls
        importlib.reload(edgar.config)
        importlib.reload(edgar.urls)

        from edgar.urls import build_archive_url
        url = build_archive_url("data/12345/file.txt")
        assert url == "https://www.sec.gov/Archives/edgar/data/12345/file.txt"

    def test_build_archive_url_custom(self, clean_env):
        """Test archive URL building with custom base"""
        os.environ['EDGAR_BASE_URL'] = "https://mysite.com"

        import edgar.config
        import edgar.urls
        importlib.reload(edgar.config)
        importlib.reload(edgar.urls)

        from edgar.urls import build_archive_url
        url = build_archive_url("data/12345/file.txt")
        assert url == "https://mysite.com/Archives/edgar/data/12345/file.txt"

    def test_build_api_url(self, clean_env):
        """Test API URL building"""
        import edgar.config
        import edgar.urls
        importlib.reload(edgar.config)
        importlib.reload(edgar.urls)

        from edgar.urls import build_api_url
        url = build_api_url("xbrl/companyfacts/CIK0000320193.json")
        assert url == "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"

    def test_build_submissions_url(self, clean_env):
        """Test submissions URL building"""
        import edgar.config
        import edgar.urls
        importlib.reload(edgar.config)
        importlib.reload(edgar.urls)

        from edgar.urls import build_submissions_url
        url = build_submissions_url(320193)
        assert url == "https://data.sec.gov/submissions/CIK0000320193.json"

    def test_build_company_facts_url(self, clean_env):
        """Test company facts URL building"""
        import edgar.config
        import edgar.urls
        importlib.reload(edgar.config)
        importlib.reload(edgar.urls)

        from edgar.urls import build_company_facts_url
        url = build_company_facts_url(320193)
        assert url == "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"

    def test_build_full_index_url(self, clean_env):
        """Test full index URL building"""
        import edgar.config
        import edgar.urls
        importlib.reload(edgar.config)
        importlib.reload(edgar.urls)

        from edgar.urls import build_full_index_url
        url = build_full_index_url(2024, 1, "form", "idx")
        assert url == "https://www.sec.gov/Archives/edgar/full-index/2024/QTR1/form.idx"

    def test_url_path_normalization(self, clean_env):
        """Test that paths are normalized (no double slashes)"""
        import edgar.config
        import edgar.urls
        importlib.reload(edgar.config)
        importlib.reload(edgar.urls)

        from edgar.urls import build_archive_url

        # Path with leading slash should work
        url1 = build_archive_url("/data/12345/file.txt")
        url2 = build_archive_url("data/12345/file.txt")
        assert url1 == url2
        assert "//" not in url1.replace("https://", "")
