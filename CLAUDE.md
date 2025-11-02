# EdgarTools - Agent Navigation Guide

**edgartools** is a Python library for navigating SEC Edgar filings

## Package Structure

The `edgar` package is organized into functional domains. Use this guide to efficiently navigate the codebase.

### Core Entry Points

**Top Level APIs** (`__init__.py`)
- Functions and members exposed for user interaction mainly through imports like `Filing`, `Filings`, `Company`
- Convenience functions for common tasks like `find` and `obj`

**Published Filings** (`_filings.py`)
- `Filing` - Core filing data model with metadata and document access
- `Filings` - Collection of filings with filtering and operations
- `get_filings()` - Primary filing retrieval function

**Current Filing Access** (`current_filings.py`)
- `CurrentFilings` - Access to the latest filings across companies
- `get_current_filings()` - Retrieve recent filings

---

## Functional Domains

### 1. Entity & Company Data (`entity/`)
**Purpose**: Company information, submissions, and financial facts from SEC API

**Key Files**:
- `core.py` - `Company`, `Entity`, `SecFiler` classes (main domain models)
- `entity_facts.py` - `EntityFacts` class for SEC Company Facts API
- `statement_builder.py` - Builds financial statements from facts
- `filings.py` - `EntityFilings` for company-specific filing access
- `search.py` - Company search functionality
- `tickers.py` - Ticker/CIK lookup utilities

**Common Patterns**:
```python
company = Company("AAPL")           # Get company by ticker
facts = company.get_facts()         # Financial facts API
filings = company.get_filings()     # Company filings
```

### 2. XBRL Processing (`xbrl/`)
**Purpose**: Parse XBRL data and generate financial statements

**Key Files**:
- `xbrl.py` - `XBRL` class, main parser and data container (66KB)
- `facts.py` - `FactsView`, `FactQuery` for querying XBRL facts (55KB)
- `statements.py` - `Statement`, `StitchedStatement` classes (46KB)
- `rendering.py` - Rich table rendering for statements (72KB)
- `period_selector.py` - Period selection logic for statements

**Subpackages**:
- `parsers/` - Instance, schema, presentation, calculation linkbase parsers
- `stitching/` - Multi-period statement stitching (`XBRLS` class)
- `analysis/` - Financial metrics, fraud detection, ratios

**Common Patterns**:
```python
xbrl = filing.xbrl()                # Get XBRL from filing
statements = xbrl.statements        # Get financial statements
facts = xbrl.facts                  # Query facts
```

### 3. Document Parsing (`documents/`)
**Purpose**: HTML/XML document parsing with semantic structure extraction

**Key Files**:
- `document.py` - `Document` class with node tree structure (33KB)
- `parser.py` - `HTMLParser` with caching (13KB)
- `search.py` - `DocumentSearch` with BM25 ranking (27KB)
- `nodes.py` - Node classes (Heading, Table, Text, etc.)
- `types.py` - `NodeType`, `SemanticType` enums

**Subpackages**:
- `extractors/` - Section detection (pattern, TOC, hybrid strategies)
- `processors/` - Pre/post-processing
- `renderers/` - Markdown, text, table rendering
- `ranking/` - Section ranking and caching

**Common Patterns**:
```python
doc = filing.document()             # Parse filing HTML
searcher = DocumentSearch(doc)      # Create searcher
results = searcher.ranked_search("revenue", algorithm="bm25")
```

### 4. Specialized Forms

**Investment Companies** (`funds/`)
- `FundCompany`, `FundClass` - Fund domain models
- `reports.py` - N-CSR, NPORT report forms

**Insider Trading** (`ownership/`)
- `Ownership` - Form 3/4/5 parsing
- `ownershipforms.py` - Insider transaction data

**Other Forms**:
- `form144.py` - Form 144 (insider sales)
- `thirteenf.py` - 13F (institutional holdings)
- `offerings/` - Form C, Form D (private offerings)

### 5. Infrastructure

**HTTP & Storage**:
- `httpclient.py` - SEC API HTTP client
- `storage.py` - Local filing cache management
- `core.py` - Configuration, identity, logging

**Utilities**:
- `formatting.py` - Text formatting
- `richtools.py` - Rich terminal display
- `datatools.py` - Data structure utilities
- `xmltools.py` - XML parsing utilities

**Reference Data** (`reference/`)
- `tickers.py` - Ticker reference data
- `company_subsets.py` - Company filtering (SIC codes, exchanges)
- `forms.py` - Form type reference

---

## Navigation Patterns

### Finding Code by Task

**Task: Get company filings**
→ Start: `entity/core.py` (`Company` class)
→ Then: `entity/filings.py` (`EntityFilings`)
→ Or: `_filings.py` (`get_filings()`)

**Task: Parse financial statements**
→ Start: `xbrl/xbrl.py` (`XBRL.from_filing()`)
→ Then: `xbrl/statements.py` (`Statement` classes)
→ Build: `entity/statement_builder.py`

**Task: Extract text from documents**
→ Start: `documents/parser.py` (`HTMLParser`)
→ Then: `documents/document.py` (`Document` class)
→ Search: `documents/search.py` (`DocumentSearch`)

**Task: Work with specific form types**
→ Check: `company_reports.py` for 10-K/Q/8-K
→ Or: `ownership/`, `funds/`, `offerings/` for specialized forms
→ Or: `form144.py`, `thirteenf.py` for specific forms

**Task: Access reference data**
→ Use: `reference/` package
→ Tickers: `reference/tickers.py`
→ Companies: `reference/company_subsets.py`

---

## Data Flow Patterns

### Filing → Company Report
```
Filing → filing.obj() → TenK/TenQ/EightK (specialized report class)
```

### Filing → XBRL → Statements
```
Filing → filing.xbrl() → XBRL → xbrl.statements → Statement objects
```

### Company → Financial Data
```
Company → company.get_facts() → EntityFacts → statement_builder → Statement
```

### Filing → Document → Structured Data
```
Filing → filing.document() → Document (node tree) → extractors → sections
```

---

## Tests

**Location**: `tests/` directory (sibling to `edgar/`)

### Directory Structure

```
tests/
├── conftest.py                    # Pytest configuration, fixtures, and hooks
├── fixtures/                      # Sample filings and test data
│   └── xbrl2/                    # XBRL test fixtures
├── issues/
│   ├── regression/               # Regression tests (auto-marked)
│   └── reproductions/            # Issue reproduction tests
│       ├── data-quality/         # Data quality issues
│       ├── entity-facts/         # Entity facts API issues
│       ├── filing-access/        # Filing access issues
│       └── xbrl-parsing/         # XBRL parsing issues
├── batch/                        # Batch integration tests
├── perf/                         # Performance benchmarks
├── research/                     # Experimental tests
├── manual/                       # Manual investigation tests
└── test_*.py                     # Main test suite files
```

---

## Test Infrastructure

### Conftest.py (`tests/conftest.py`)

**Purpose**: Central test configuration with fixtures, hooks, and pytest customization

**Key Hooks**:

1. **`pytest_configure(config)`** - Disables HTTP caching for test accuracy
   - Use `--enable-cache` flag to override
   - Configures distributed SQLite rate limiter for pytest-xdist parallel testing

2. **`pytest_collection_modifyitems(items)`** - Auto-marks regression tests
   - Any test in a `regression/` folder automatically gets `@pytest.mark.regression`
   - Works cross-platform (handles both `/` and `\` paths)
   - **No manual marker needed** for regression tests!

**Available Fixtures**:

#### Session-Scoped Company Fixtures (cached for entire test run)
```python
@pytest.fixture(scope="session")
def aapl_company():
    """Apple Inc. - use for consistent test data"""
    return Company("AAPL")

@pytest.fixture(scope="session")
def tsla_company():
    """Tesla Inc. - use for consistent test data"""
    return Company("TSLA")
```

#### Module-Scoped Company Fixtures (cached per test module)
```python
@pytest.fixture(scope="module")
def expe_company():    # Expedia Group
def nvda_company():    # NVIDIA Corporation
def snow_company():    # Snowflake Inc.
def msft_company():    # Microsoft Corporation
def amzn_company():    # Amazon.com Inc.
```

#### Filing Fixtures
```python
@pytest.fixture(scope="session")
def carbo_10k_filing():
    """CARBO CERAMICS INC 10-K from 2018"""

@pytest.fixture(scope="module")
def three_m_8k_filing():
    """3M CO 8-K filing"""

@pytest.fixture(scope="module")
def ten_x_genomics_10k_filing():
    """10x Genomics 10-K filing"""

@pytest.fixture(scope="module")
def apple_2024_10k_filing():
    """Apple Inc. 2024 10-K filing"""
```

#### Cached Filings Collections
```python
@pytest.fixture(scope="session")
def filings_2022_q3():
    """2022 Q3 filings - expensive network call cached"""

@pytest.fixture(scope="session")
def filings_2021_q1():
    """2021 Q1 filings"""

@pytest.fixture(scope="session")
def filings_2021_q1_xbrl():
    """2021 Q1 XBRL index filings"""
```

**Why Use Fixtures?**
- **Performance**: Company/filing objects cached across tests
- **Consistency**: Same test data across test suite
- **DRY**: Avoid repeated setup code
- **Network Efficiency**: Reduces SEC API calls

---

## Test Markers

All markers are configured in `pyproject.toml` under `[tool.pytest.ini_options]`.

| Marker | Purpose | Use When | Example |
|--------|---------|----------|---------|
| `@pytest.mark.fast` | Fast unit tests (< 0.1s) | No network calls, pure logic | `@pytest.mark.fast` |
| `@pytest.mark.slow` | Slow tests (> 1s) | Heavy processing, large data | `@pytest.mark.slow` |
| `@pytest.mark.network` | Requires internet | Uses `Company()`, `get_filings()`, `find()` | `@pytest.mark.network` |
| `@pytest.mark.regression` | Regression test | **AUTO-MARKED** in `regression/` folders | *(auto-applied)* |
| `@pytest.mark.batch` | Batch processing | Tests across many filings/companies | `@pytest.mark.batch` |
| `@pytest.mark.performance` | Performance tests | Benchmarking, profiling | `@pytest.mark.performance` |
| `@pytest.mark.reproduction` | Issue reproduction | Reproduces a specific bug | `@pytest.mark.reproduction` |
| `@pytest.mark.integration` | Integration tests | Multi-component testing | `@pytest.mark.integration` |
| `@pytest.mark.data_quality` | Data validation | Validates data correctness | `@pytest.mark.data_quality` |

**Marker Guidelines**:
- Tests without network calls → `@pytest.mark.fast`
- Tests with `Company("AAPL")` or `get_filings()` → `@pytest.mark.network`
- Regression tests in `tests/issues/regression/` → **no marker needed** (auto-applied)

---

## Test Commands

Configured in `pyproject.toml` under `[tool.hatch.envs.default.scripts]`.

### Basic Test Commands
```bash
# Run all tests (excludes manual and perf)
hatch run test-full

# Run with coverage
hatch run cov

# Run without coverage
hatch run no-cov
```

### Category-Based Testing (Sequential)
```bash
# Fast tests only
hatch run test-fast

# Network tests only
hatch run test-network

# Slow tests only
hatch run test-slow

# Core tests (excludes slow, network, performance, batch)
hatch run test-core
```

### Parallel Test Commands (Optimized for Speed)
```bash
# Fast tests with full parallelization (SAFE - no network calls)
hatch run test-fast-parallel

# Core tests with limited parallelization
hatch run test-core-parallel

# Alias for safe parallel execution
hatch run test-parallel-safe
```

**Important**: Only fast tests should be parallelized with `-n auto` to avoid SEC rate limit issues. Network and slow tests must run sequentially.

### CI Testing (excludes regression for faster feedback)
```bash
# Fast CI tests
hatch run test-ci-fast

# Network CI tests (not slow)
hatch run test-ci-network

# Slow CI tests
hatch run test-ci-slow

# Core CI tests
hatch run test-ci-core

# All CI tests (excludes regression, manual, perf)
hatch run test-ci-all
```

### Regression Testing (comprehensive bug prevention)
```bash
# Run only regression tests
hatch run test-regression

# Run all tests including regression
hatch run test-full
```

### Other Test Categories
```bash
# Batch tests
hatch run test-batch

# Issue reproduction tests
hatch run test-reproduction

# Lint code
hatch run lint

# Smoke test filings
hatch run smoke-filings
```

---

## Automatic Test Marking System

EdgarTools uses a **hybrid exclusion strategy** for regression tests:

1. **Marker-based**: `-m 'not regression'` excludes marked tests
2. **Path-based**: `--ignore=tests/issues/regression` excludes folder
3. **Auto-marking**: `conftest.py` automatically marks tests in regression folders

**How Auto-Marking Works**:
```python
# In conftest.py
def pytest_collection_modifyitems(items):
    for item in items:
        test_path = str(item.fspath)
        if "/regression/" in test_path or "\\regression\\" in test_path:
            item.add_marker(pytest.mark.regression)
```

**Benefits**:
- Prevents forgetting to add `@pytest.mark.regression`
- Works for humans and AI agents
- Ensures CI exclusion works reliably
- Based on directory structure, not manual markers

---

## Writing Tests - Best Practices

### 1. Choose Appropriate Markers
```python
import pytest

@pytest.mark.fast
def test_datatools_listify():
    """Pure logic, no network - use @pytest.mark.fast"""
    assert listify("AAPL") == ["AAPL"]

@pytest.mark.network
def test_company_get_facts():
    """Network call - use @pytest.mark.network"""
    company = Company("AAPL")
    facts = company.get_facts()
    assert facts is not None
```

### 2. Use Fixtures for Common Setup
```python
@pytest.mark.network
def test_apple_filings(aapl_company):
    """Use session-scoped fixture instead of creating Company"""
    filings = aapl_company.get_filings(form="10-K")
    assert len(filings) > 0
```

### 3. Regression Test Location
**Place in**: `tests/issues/regression/`
**Naming**: `test_issue_<number>_<description>.py`
**Marker**: **NOT NEEDED** (auto-applied)

```python
# tests/issues/regression/test_issue_429_statement_period_regression.py
"""
Regression test for GitHub issue #429: Statement period selection

GitHub Issue: https://github.com/dgunning/edgartools/issues/429
"""
# No @pytest.mark.regression needed - automatic!

def test_issue_429_period_selection():
    # Test the specific bug that was fixed
    pass
```

### 4. Issue Reproduction Tests
**Place in**: `tests/issues/reproductions/<category>/`
**Categories**: `data-quality/`, `entity-facts/`, `filing-access/`, `xbrl-parsing/`
**Marker**: `@pytest.mark.reproduction`

```python
@pytest.mark.reproduction
@pytest.mark.network
def test_issue_332_6k_financials():
    """Reproduce issue where 6-K filings couldn't access financials"""
    # Reproduction code
    pass
```

### 5. Batch Tests for Edge Case Discovery
```python
@pytest.mark.batch
@pytest.mark.slow
def test_xbrl_parsing_across_sp500():
    """Test XBRL parsing across S&P 500 companies"""
    companies = get_sp500_companies()
    for company in companies:
        # Test each company
        pass
```

---

## Test Directory Guide

| Directory | Purpose | Marker | CI Behavior |
|-----------|---------|--------|-------------|
| `tests/` | Main test suite | Various | Included |
| `tests/issues/regression/` | Regression tests | **Auto: `regression`** | Excluded (run separately) |
| `tests/issues/reproductions/` | Issue reproductions | `reproduction` | Included |
| `tests/batch/` | Batch tests | `batch` | Excluded |
| `tests/perf/` | Performance tests | `performance` | Excluded (ignored path) |
| `tests/manual/` | Manual investigation | `manual` | Excluded (ignored path) |
| `tests/research/` | Experimental tests | None | Included |
| `tests/fixtures/` | Test data | N/A | Not tests |

---

## Pytest Configuration

**Key Settings** (from `pyproject.toml`):

```toml
[tool.pytest.ini_options]
env = [
    "EDGAR_IDENTITY=Dev Gunning developer-gunning@gmail.com"
]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
retries = 2              # Auto-retry flaky tests
retry_delay = 4          # 4 second delay between retries
```

**Installed Plugins**:
- `pytest-cov` - Coverage reporting
- `pytest-env` - Environment variable injection
- `pytest-xdist` - Parallel test execution
- `pytest-asyncio` - Async test support
- `pytest-retry` - Auto-retry flaky tests

---

## Common Testing Patterns

### Pattern 1: Test Company Data Access
```python
@pytest.mark.network
def test_company_facts(aapl_company):
    """Use session fixture for performance"""
    facts = aapl_company.get_facts()
    assert facts.revenue is not None
```

### Pattern 2: Test Filing Access
```python
@pytest.mark.network
def test_get_filings():
    filings = get_filings(2022, 3, form="10-K")
    assert len(filings) > 0
    assert all(f.form == "10-K" for f in filings)
```

### Pattern 3: Test XBRL Parsing
```python
@pytest.mark.network
def test_xbrl_statements(aapl_company):
    filing = aapl_company.get_filings(form="10-K")[0]
    xbrl = filing.xbrl()
    assert xbrl.statements.income is not None
```

### Pattern 4: Test Document Parsing (Fast)
```python
@pytest.mark.fast
def test_document_node_creation():
    """No network needed - pure logic"""
    node = Heading(text="Revenue", level=2)
    assert node.text() == "Revenue"
    assert node.level == 2
```

### Pattern 5: Regression Test (Auto-Marked)
```python
# File: tests/issues/regression/test_issue_429_regression.py
# NO marker needed - automatic!

def test_issue_429_statement_period_selection():
    """Test that comparative periods are selected correctly"""
    # Test specific to issue #429
    pass
```


---

## Common Operations

### Search for filings
```python
from edgar import find
filings = find(form="10-K", ticker="AAPL", amendments=False)
```

### Get company data
```python
from edgar import Company
company = Company("AAPL")
facts = company.get_facts()
```

### Parse XBRL
```python
filing = filings[0]
xbrl = filing.xbrl()
statements = xbrl.statements
income_stmt = statements.income
```

### Search documents
```python
from edgar.documents import DocumentSearch
doc = filing.document()
searcher = DocumentSearch(doc)
results = searcher.ranked_search("revenue growth", algorithm="bm25")
```

---

## Architecture Layers

```
┌─────────────────────────────────────────┐
│  User API Layer                         │
│  find(), Company(), get_filings()       │
└─────────────────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│  Domain Models                          │
│  Filing, Entity, XBRL, Statement, Doc   │
└─────────────────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│  Processing Layer                       │
│  Parsers, Builders, Extractors          │
└─────────────────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│  Data Access Layer                      │
│  HTTP Client, Storage, Reference Data   │
└─────────────────────────────────────────┘
```

---

## File Size Reference

Large files that may need context management:
- `_filings.py` (72KB) - Core filing API
- `xbrl/xbrl.py` (66KB) - XBRL parser
- `xbrl/rendering.py` (72KB) - Statement rendering
- `entity/entity_facts.py` (63KB) - Facts API
- `xbrl/facts.py` (55KB) - Fact queries
- `files/html.py` (65KB) - Legacy HTML parsing
- `company_reports.py` (37KB) - Report classes
- `documents/document.py` (33KB) - Document model
- `documents/search.py` (27KB) - Search interface

---

## Quick Reference

| Need | Go To |
|------|-------|
| Filing search/access | `_filings.py` |
| Company information | `entity/core.py` |
| Financial statements | `xbrl/statements.py` |
| XBRL parsing | `xbrl/xbrl.py` |
| Document parsing | `documents/parser.py` |
| Text search | `documents/search.py` |
| 10-K/10-Q reports | `company_reports.py` |
| Insider trading | `ownership/` |
| Investment funds | `funds/` |
| Reference data | `reference/` |
| Configuration | `core.py` |
| Storage/caching | `storage.py` |

---

**Version**: Check `edgar/__about__.py` for current version
**Documentation**: See `docs/` directory for detailed guides