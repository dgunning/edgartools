# EdgarTools Verification Survey

A factual inventory of the current test suite — what exists, how it's organized, and how it runs.

---

## At a Glance

| Metric | Value |
|--------|-------|
| Test files | ~309 (286 test_*.py + 23 batch_*.py) |
| Test classes | 385 |
| Standalone test functions | 1,244 |
| Registered markers | 10 |
| Cassette files | 15 (~355 MB) |
| HTML fixture companies | 30+ |
| XBRL fixture companies | 20+ |
| Conftest files | 1 (root level) |
| CI matrix | 3 test groups x 4 Python versions |
| Coverage threshold | 65% combined |

---

## 1. Directory Structure

```
tests/
├── conftest.py                        # Single conftest: fixtures, VCR config, auto-marking
├── test_*.py                          # ~165 test files at root level
├── cassettes/                         # VCR recorded HTTP responses (15 YAML files, ~355 MB)
├── fixtures/
│   ├── html/{ticker}/{form}/          # HTML documents for 30+ companies
│   ├── xbrl/{ticker}/{form}_{year}/   # XBRL data for 20+ companies (2010-2024)
│   ├── entity/                        # Entity data
│   └── attachments/                   # Filing attachments
├── data/
│   ├── beneficial_ownership/
│   └── cross_reference_index/
├── batch/                             # 23 batch_*.py + 1 test_*.py
├── issues/
│   ├── regression/                    # ~80 test files for specific GitHub issues
│   ├── reproductions/
│   │   ├── data-quality/              # 6 files
│   │   ├── entity-facts/              # 4 files
│   │   ├── filing-access/             # 1 file
│   │   └── xbrl-parsing/             # 8 files
│   └── _templates/
├── manual/                            # 8 manual validation tests
├── thirteenf/                         # 1 test file
├── harness/                           # Test harness infrastructure
├── perf/                              # Performance tests
└── research/                          # Research/exploration tests
```

---

## 2. Test Framework Stack

| Package | Role |
|---------|------|
| `pytest` | Test runner |
| `pytest-cov` | Coverage reporting |
| `pytest-xdist` | Parallel execution |
| `pytest-asyncio` | Async test support (mode: auto) |
| `pytest-vcr` / `vcrpy` | HTTP interaction recording/replay |
| `pytest-retry` | Auto-retry flaky tests (2 retries, 4s delay) |
| `pytest-env` | Environment variable management |
| `pytest-mock` | Mocking utilities |
| `unittest.mock` | Also used directly (patch, MagicMock) |

---

## 3. Markers and Auto-Classification

Tests are auto-classified by filename pattern in `conftest.py`. No manual annotation required for most tests.

### Registered Markers

| Marker | Purpose |
|--------|---------|
| `fast` | No network, runs in < 0.1s |
| `slow` | Takes > 1s |
| `network` | Requires internet (SEC API) |
| `regression` | Tied to specific GitHub issues |
| `batch` | Batch processing |
| `performance` | Benchmarking |
| `reproduction` | Issue reproduction |
| `integration` | Integration tests |
| `data_quality` | Data quality validation |
| `vcr` | Uses recorded HTTP cassettes |

### Auto-Marking Patterns

**Fast (no network) — matched by filename prefix:**
`test_html`, `test_documents`, `test_xbrl`, `test_tables`, `test_markdown`, `test_richtools`, `test_xml`, `test_section`, `test_ranking`, `test_period`, `test_rendering`, `test_style`, `test_headings`, `test_cache`, `test_parsing`, `test_extraction`, `test_standardization`, `test_hierarchy`, `test_stitching`, `test_balance`, `test_statement`, `test_footnotes`, `test_ratios`, `test_hidden`, `test_reference`, `test_filesystem`, `test_sgml`, `test_harness_*`, `test_10q`, `test_10k`, `test_fast`, `test_cross_reference`, `test_issue`, `test_bug`, `test_revenue`, `test_net_income`, `test_sga`, `test_has_html`, `test_periodtype`, `test_fund_reference`

**Network (SEC API required) — matched by filename prefix:**
`test_entity`, `test_company`, `test_filing`, `test_ownership`, `test_funds`, `test_fundreports`, `test_thirteenf`, `test_eightk`, `test_proxy`, `test_effect`, `test_formc`, `test_formd`, `test_form144`, `test_muni`, `test_npx`, `test_ticker`, `test_datasearch`, `test_httprequests`, `test_attachments`, `test_local_storage`, `test_saving`, `test_ratelimit`, `test_storage`, `test_ai`, `test_mcp`, `test_etf`, `test_multi_entity`, `test_paper`, `test_harness_selectors`, `test_read_filing`, `test_form_upload`, `test_current`, `test_xbrl_stitching`

**Regression — matched by path:** Any test under `tests/issues/regression/`

---

## 4. Test Style

**~76% function-based, ~24% class-based.**

Function style (majority):
```python
def test_company_repr():
    company = get_test_company("NVDA")
    assert 'NVDA' in repr(company)
```

Class style (grouping related assertions):
```python
@pytest.mark.regression
class TestCostOfRevenueFix:
    def test_revenue_greater_than_cost(self):
        ...
    def test_all_companies_have_revenue(self):
        ...
```

---

## 5. Fixtures

### Shared Fixtures (conftest.py)

**Session-scoped** (one instance for entire test run):
- Companies: `aapl_company`, `tsla_company`, `nflx_company`
- Filings: `carbo_10k_filing`, `nflx_2012_10k_filing`, `nflx_2025_q3_10q_filing`
- 13F: `state_street_13f_filing`, `state_street_13f`, `state_street_13f_infotable`, `state_street_13f_holdings`
- Batches: `filings_2022_q3`, `filings_2021_q1`, `filings_2021_q1_xbrl`

**Module-scoped** (one instance per test file):
- Companies: `expe_company`, `nvda_company`, `snow_company`, `msft_company`, `amzn_company`
- Filings: `three_m_8k_filing`, `ten_x_genomics_10k_filing`, `orion_form4_filing`, `frontier_masters_10k_filing`, `apple_2024_10k_filing`
- Batches: `filings_2014_q4`

**Autouse** (applied to every test automatically):
- `reset_http_client_state` — closes HTTP connections, resets SSL verify to True

### File-Based Fixtures

- **HTML fixtures**: `tests/fixtures/html/{ticker}/{form}/` — 30+ companies, 10-K and 10-Q documents
- **XBRL fixtures**: `tests/fixtures/xbrl/{ticker}/{form}_{year}/` — 20+ companies, 2010-2024
- **Special cases**: `tests/fixtures/xbrl/special_cases/` — custom taxonomies, dimensional data, segments

### VCR Cassettes

15 YAML files in `tests/cassettes/`. Configuration:
- Record mode: `once` (record only if cassette doesn't exist)
- Match on: method, scheme, host, port, path, query
- Filtered headers: User-Agent, Authorization
- 19 tests explicitly marked `@pytest.mark.vcr`
- Largest cassette: ~37 MB (MSFT financials), smallest: ~6 KB

---

## 6. Patterns In Use

### Parameterization
~25 parametrized tests. Typical pattern — same assertion across multiple companies:
```python
@pytest.mark.parametrize("company_fixture,min_revenue_billions", [
    ("aapl_company", 300),
    ("msft_company", 200),
    ("tsla_company", 80),
])
def test_companies_return_valid_annual_revenue(self, company_fixture, min_revenue_billions):
    ...
```

### Async Tests
~18 async tests, primarily in MCP/AI modules:
```python
class TestMCPIntentTools:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        result = await call_tool_handler("nonexistent_tool", {})
        assert result.success is False
```

### Mocking
~60 tests use mocks. Three patterns:

**Decorator patching:**
```python
@patch('edgar._filings.print_warning')
def test_warn_use_current_filings(self, mock_print_warning):
    ...
```

**Context manager patching:**
```python
with patch('edgar.funds.core.find_fund') as mock_find_fund:
    mock_find_fund.return_value = MagicMock()
    ...
```

**Monkeypatch (105+ tests):**
```python
def test_get_identity_not_set(monkeypatch):
    monkeypatch.delenv("EDGAR_IDENTITY", raising=False)
    ...
```

---

## 7. Test Run Commands

### Local Development

| Command | What runs | Parallelism |
|---------|-----------|-------------|
| `hatch run test-fast` | Fast tests only | Sequential |
| `hatch run test-fast-parallel` | Fast tests only | `-n auto` |
| `hatch run test-network` | Network tests only | Sequential |
| `hatch run test-slow` | Slow tests only | Sequential |
| `hatch run test-core` | Mixed (no slow/network/perf/batch) | Sequential |
| `hatch run test-regression` | Regression tests only | Sequential |
| `hatch run test-batch` | Batch tests | Sequential |
| `hatch run test-reproduction` | Reproduction tests | Sequential |
| `hatch run test-full` | All except manual and perf | Sequential |
| `hatch run cov` | With coverage report | Sequential |

### CI Pipeline

**Main workflow** (`python-hatch-workflow.yml`):
- Triggered on push/PR to main
- Matrix: Python 3.10, 3.11, 3.12, 3.13

| CI Job | Command | Parallelism |
|--------|---------|-------------|
| `test-ci-fast` | `-n auto -m 'fast and not regression'` | Full parallel |
| `test-ci-network` | `-m 'network and not slow and not regression'` | Sequential |
| `test-ci-slow` | `-m 'slow and not regression'` | Sequential |

Coverage from all three jobs is combined. 65% threshold enforced on the combined result.

**Regression workflow** (`regression-tests.yml`):
- Triggered: manually, weekly (Sundays 8 AM), or on changes to key paths
- Matrix: Python 3.11, 3.12 only
- Triggered paths: `tests/issues/regression/**`, `edgar/xbrl/**`, `edgar/entity/**`

### Rate Limiting

When `pytest-xdist` parallel mode is detected, a distributed SQLite rate limiter caps SEC requests at 8/sec (below SEC's 10/sec limit).

---

## 8. Test-to-Source Coverage Map

### Well-Covered Modules

| Source Module | Test Files | Approach |
|--------------|------------|----------|
| `_filings.py` | `test_edgar.py`, `test_filing.py`, `test_filing_sort.py`, `test_filing_metadata.py`, `test_filing_staleness_warnings.py` | Network + fixtures |
| `entity/` | `test_entity.py`, `test_entity_core.py`, `test_entity_filings.py`, `test_entity_statements.py`, `test_company.py` | Network |
| `entity/entity_facts.py` | `test_entity_facts.py`, `test_entity_facts_annual_periods.py`, `test_entity_facts_revenue_fixes.py` | Network + VCR |
| `xbrl/` | 15+ `test_xbrl_*.py` files | Primarily fixtures |
| `xbrl/statements.py` | `test_xbrl_statements.py`, `test_xbrl_statements_core.py`, `test_xbrl_statement_*.py` | Fixtures |
| `xbrl/standardization/` | `test_xbrl_standardization.py` | Fixtures |
| `xbrl/stitching/` | `test_xbrl_stitching.py` | Network |
| `documents/` | `test_html_parser.py`, `test_html_parser_edge_cases.py`, `test_html_parser_regressions.py`, `test_html_parser_integration.py`, `test_section_detection*.py` | Fixtures |
| `company_reports.py` | `test_company_reports.py`, `test_filing_reports.py`, `test_eightK.py` | Network |
| `ownership/` | `test_ownership.py`, `test_form3.py`, `test_form4.py` | Network |
| `beneficial_ownership/` | `test_beneficial_ownership.py` | Network |
| `funds/` | `test_funds.py`, `test_fund_wrapper.py`, `test_fund_reference.py`, `test_fundreports.py`, `test_etf_*.py` | Network + mocks |
| `reference/` | `test_reference.py`, `test_tickers.py`, `test_reference_company_dataset.py`, `test_company_subsets*.py` | Network + mocks |
| `search/` | `test_datasearch.py`, `test_textsearch.py`, `test_ranking_search.py` | Network + fixtures |
| `proxy/` | `test_proxy.py` | Network |
| `sgml/` | `test_filing_sgml.py`, `test_filing_summary.py` | Fixtures |
| `ai/mcp/` | `test_mcp_intent_tools.py`, `test_mcp_server.py` | Async + mocks |
| `ai/evaluation/` | `test_cc_runner.py`, `test_judge.py`, `test_constitution_diagnostics.py`, `test_skill_diagnostics.py` | Mixed |

### Modules Without Dedicated Tests

| Module | Notes |
|--------|-------|
| `earnings.py` | No test file |
| `financials.py` | No test file |
| `ai/formats.py` | Marked skip-coverage (experimental) |
| `ai/helpers.py` | Marked skip-coverage (experimental) |
| `documents/migration.py` | One-time migration utility |
| `standardization.py` | Legacy, superseded by `xbrl/standardization/` |

### Regression Tests (80+ files)

Stored in `tests/issues/regression/`. Each file corresponds to a specific GitHub issue. Automatically marked `@pytest.mark.regression`. Examples:
- `test_cost_of_revenue_fix.py`
- `test_entity_facts_annual_periods.py`
- `test_bug_408_annual_periods.py`

---

## 9. Pytest Configuration Details

```toml
# From pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
env = ["EDGAR_IDENTITY=Dev Gunning developer-gunning@gmail.com"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
retries = 2
retry_delay = 4
cumulative_timing = false
retry_outcome = "rerun"
```

Key behaviors:
- **Auto-retry**: Failed tests automatically retried twice with 4-second delay
- **Async auto-mode**: No need for explicit `@pytest.mark.asyncio` in most cases
- **Identity**: Tests run with a fixed EDGAR_IDENTITY environment variable
- **Autouse fixture**: HTTP client state reset between every test for isolation
