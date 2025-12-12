import pytest
from pathlib import Path

from edgar import httpclient
from edgar import Company
from edgar._filings import Filing, get_filings

import logging

logger = logging.getLogger(__name__)

# VCR configuration for recording/replaying HTTP interactions
CASSETTES_DIR = Path(__file__).parent / "cassettes"


@pytest.fixture(scope="module")
def vcr_config():
    """Configure VCR for recording SEC API responses.

    This enables tests to record real API responses once and replay them
    on subsequent runs, dramatically speeding up network-dependent tests.
    """
    return {
        "cassette_library_dir": str(CASSETTES_DIR),
        "record_mode": "once",  # Record only if cassette doesn't exist
        "match_on": ["method", "scheme", "host", "port", "path", "query"],
        "filter_headers": ["User-Agent", "Authorization"],
        "decode_compressed_response": True,
    }


@pytest.fixture(autouse=True)
def reset_http_client_state():
    """
    Reset HTTP client state between tests to ensure test isolation.

    This is especially important for SSL verification tests which modify
    HTTP_MGR.httpx_params["verify"] and need a clean state.
    """
    # Close any existing client to force fresh creation
    if httpclient.HTTP_MGR._client is not None:
        try:
            httpclient.HTTP_MGR._client.close()
        except Exception:
            pass
        httpclient.HTTP_MGR._client = None

    # Always reset to default (True) before each test
    # Don't restore to "original" as that might be False from a leaked previous test
    httpclient.HTTP_MGR.httpx_params["verify"] = True

    yield

    # Cleanup and reset to default after test
    if httpclient.HTTP_MGR._client is not None:
        try:
            httpclient.HTTP_MGR._client.close()
        except Exception:
            pass
        httpclient.HTTP_MGR._client = None

    # Always reset to default (True) to prevent state leaking to next test
    httpclient.HTTP_MGR.httpx_params["verify"] = True
# Base paths
FIXTURE_DIR = Path("tests/fixtures/xbrl")
DATA_DIR = Path("data/xbrl/datafiles")


def pytest_addoption(parser):
    parser.addoption("--enable-cache", action="store_true", help="Enable HTTP cache")


def pytest_configure(config):
    """
    - Disables caching for testing
    """
    if not config.getoption("--enable-cache"):
        logger.info("Cache disabled for test accuracy")    
        httpclient.HTTP_MGR = httpclient.get_http_mgr(cache_enabled=False)

    if hasattr(config, 'workerinput'):
        logger.info("pytest-xdist is enabled, enabling a distributed sqlite ratelimiter")
        from pyrate_limiter import Duration, limiter_factory
        # Use 8 requests per second (below SEC's 10/sec limit) with burst capacity
        # This provides more headroom for parallel tests while respecting rate limits
        httpclient.HTTP_MGR.rate_limiter = limiter_factory.create_sqlite_limiter(
            rate_per_duration=8,
            duration=Duration.SECOND,
            db_path="ratelimiter.sqlite",
            use_file_lock=True
        )


def pytest_collection_modifyitems(items):
    """
    Automatically add markers to tests based on file patterns.

    This ensures consistent marker coverage without manual annotation:
    1. Tests in regression folders get @pytest.mark.regression
    2. Tests in parsing/processing files get @pytest.mark.fast (no network)
    3. Tests in entity/company/filings files get @pytest.mark.network

    Only adds markers to tests that don't already have fast/network/slow markers.
    """
    # Files that are definitely fast (no network calls - parsing, processing, rendering)
    FAST_PATTERNS = [
        'test_html', 'test_documents', 'test_xbrl', 'test_tables', 'test_table',
        'test_markdown', 'test_richtools', 'test_xml', 'test_section',
        'test_ranking', 'test_period', 'test_rendering', 'test_style',
        'test_headings', 'test_cache', 'test_parsing', 'test_extraction',
        'test_standardization', 'test_hierarchy', 'test_stitching',
        'test_balance', 'test_statement', 'test_footnotes', 'test_ratios',
        'test_hidden', 'test_reference', 'test_filesystem', 'test_sgml',
        'test_harness_storage', 'test_harness_reporter', 'test_harness_runner',
        'test_10q', 'test_10k', 'test_fast', 'test_cross_reference',
        'test_issue', 'test_bug', 'test_revenue', 'test_net_income', 'test_sga',
        'test_has_html', 'test_periodtype', 'test_fund_reference',
    ]

    # Files that need network (fetch from SEC)
    NETWORK_PATTERNS = [
        'test_entity', 'test_company', 'test_filing', 'test_ownership',
        'test_funds', 'test_fundreports', 'test_thirteenf', 'test_eightk',
        'test_proxy', 'test_effect', 'test_formc', 'test_formd', 'test_form144',
        'test_muni', 'test_npx', 'test_ticker', 'test_datasearch',
        'test_httprequests', 'test_attachments', 'test_local_storage',
        'test_saving', 'test_ratelimit', 'test_storage', 'test_ai',
        'test_mcp', 'test_etf', 'test_multi_entity', 'test_paper',
        'test_harness_selectors', 'test_read_filing', 'test_form_upload',
        'test_current',
    ]

    for item in items:
        test_path = str(item.fspath)
        test_file = Path(test_path).stem.lower()

        # Check if test is in any regression folder (supports nested paths)
        is_regression = "/regression/" in test_path or "\\regression\\" in test_path
        if is_regression:
            item.add_marker(pytest.mark.regression)
            logger.debug(f"Auto-marked regression test: {item.nodeid}")
            # Don't auto-mark regression tests with fast/network - they need explicit markers
            continue

        # Skip if test already has fast/network/slow marker
        existing_markers = {m.name for m in item.iter_markers()}
        if existing_markers & {'fast', 'network', 'slow'}:
            continue

        # Auto-mark based on file patterns
        if any(pattern in test_file for pattern in FAST_PATTERNS):
            item.add_marker(pytest.mark.fast)
            logger.debug(f"Auto-marked fast test: {item.nodeid}")
        elif any(pattern in test_file for pattern in NETWORK_PATTERNS):
            item.add_marker(pytest.mark.network)
            logger.debug(f"Auto-marked network test: {item.nodeid}")


# Session-scoped company fixtures for performance optimization
@pytest.fixture(scope="session")
def aapl_company():
    """Apple Inc. company fixture - cached for entire test session"""
    return Company("AAPL")


@pytest.fixture(scope="session") 
def tsla_company():
    """Tesla Inc. company fixture - cached for entire test session"""
    return Company("TSLA")


@pytest.fixture(scope="module")
def expe_company():
    """Expedia Group company fixture - cached per test module"""
    return Company("EXPE")


@pytest.fixture(scope="module")
def nvda_company():
    """NVIDIA Corporation company fixture - cached per test module"""
    return Company("NVDA")


@pytest.fixture(scope="module")
def snow_company():
    """Snowflake Inc. company fixture - cached per test module"""
    return Company("SNOW")


@pytest.fixture(scope="module")
def msft_company():
    """Microsoft Corporation company fixture - cached per test module"""
    return Company("MSFT")


@pytest.fixture(scope="module")
def amzn_company():
    """Amazon.com Inc. company fixture - cached per test module"""
    return Company("AMZN")


@pytest.fixture(scope="session")
def nflx_company():
    """Netflix Inc. company fixture - cached for entire test session"""
    return Company("NFLX")


# Filing fixtures for performance optimization
@pytest.fixture(scope="session")
def carbo_10k_filing():
    """CARBO CERAMICS INC 10-K filing - cached for entire test session"""
    return Filing(form='10-K', company='CARBO CERAMICS INC', cik=1009672,
                 filing_date='2018-03-08', accession_no='0001564590-18-004771')


@pytest.fixture(scope="module")
def three_m_8k_filing():
    """3M CO 8-K filing - cached per test module"""
    return Filing(form='8-K', filing_date='2024-03-08', company='3M CO',
                 cik=66740, accession_no='0000066740-24-000023')


@pytest.fixture(scope="module")
def ten_x_genomics_10k_filing():
    """10x Genomics, Inc. 10-K filing - cached per test module"""
    return Filing(form='10-K', company='10x Genomics, Inc.',
                 cik=1770787, filing_date='2020-02-27', accession_no='0001193125-20-052640')


@pytest.fixture(scope="module")
def orion_form4_filing():
    """Orion Engineered Carbons S.A. Form 4 filing - cached per test module"""
    return Filing(form='4', company='Orion Engineered Carbons S.A.',
                 cik=1609804, filing_date='2022-11-04', accession_no='0000950142-22-003095')


# Cached get_filings() results for performance
@pytest.fixture(scope="session")
def filings_2022_q3():
    """2022 Q3 filings - cached for entire test session"""
    return get_filings(2022, 3)


@pytest.fixture(scope="session") 
def filings_2021_q1():
    """2021 Q1 filings - cached for entire test session"""
    return get_filings(2021, 1)


@pytest.fixture(scope="session")
def filings_2021_q1_xbrl():
    """2021 Q1 XBRL filings - cached for entire test session"""
    return get_filings(2021, 1, index="xbrl")


@pytest.fixture(scope="module")
def filings_2014_q4():
    """2014 Q4 filings - cached per test module"""
    return get_filings(2014, 4)


# Company Reports fixtures for test_company_reports.py
@pytest.fixture(scope="module")
def frontier_masters_10k_filing():
    """Frontier Masters Fund 10-K filing - cached per test module"""
    return Filing(form='10-K', filing_date='2023-04-06', company='Frontier Masters Fund', 
                 cik=1450722, accession_no='0001213900-23-028058')


@pytest.fixture(scope="module")
def apple_2024_10k_filing():
    """Apple Inc. 2024 10-K filing - cached per test module"""
    return Filing(company='Apple Inc.', cik=320193, form='10-K',
                 filing_date='2024-11-01', accession_no='0000320193-24-000123')


@pytest.fixture(scope="session")
def nflx_2012_10k_filing(nflx_company):
    """Netflix 2012 10-K filing (fiscal 2011) - cached for entire test session"""
    return nflx_company.get_filings(form="10-K", accession_number="0001065280-13-000008").latest()


@pytest.fixture(scope="session")
def nflx_2025_q3_10q_filing(nflx_company):
    """Netflix Q3 2025 10-Q filing - cached for entire test session"""
    return nflx_company.get_filings(form="10-Q", accession_number="0001065280-25-000406").latest()


# 13F fixtures for performance optimization (Issue edgartools-lza)
# State Street multi-manager filing used by multiple test files
@pytest.fixture(scope="session")
def state_street_13f_filing():
    """State Street Corp 13F-HR filing - cached for entire test session.

    This filing is used by:
    - tests/thirteenf/test_holdings_aggregation.py
    - tests/issues/regression/test_issue_512_13f_manager_assignment.py
    """
    return Filing(form='13F-HR', filing_date='2024-11-14',
                  company='STATE STREET CORP', cik=70858,
                  accession_no='0001102113-24-000030')


@pytest.fixture(scope="session")
def state_street_13f(state_street_13f_filing):
    """Parsed ThirteenF object - cached for entire test session."""
    return state_street_13f_filing.obj()


@pytest.fixture(scope="session")
def state_street_13f_infotable(state_street_13f):
    """State Street infotable (disaggregated holdings) - cached for entire test session."""
    return state_street_13f.infotable


@pytest.fixture(scope="session")
def state_street_13f_holdings(state_street_13f):
    """State Street holdings (aggregated) - cached for entire test session."""
    return state_street_13f.holdings
