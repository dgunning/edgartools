# Testing Guide

## Quick Start

```bash
# Fast tests only (~2 min, no network)
hatch run test-fast

# Full test suite
hatch run test-full

# With coverage
hatch run cov
```

## Directory Structure

```
tests/
├── conftest.py           # Fixtures, hooks, auto-marking config
├── cassettes/            # VCR recorded responses (committed)
├── fixtures/             # Test data files
├── issues/
│   ├── regression/       # Auto-marked regression tests
│   └── reproductions/    # Issue reproductions by category
├── batch/                # Batch integration tests
├── perf/                 # Performance benchmarks
└── test_*.py             # Main test suite
```

## Test Commands

| Command | Description | Runtime |
|---------|-------------|---------|
| `hatch run test-fast` | Fast tests (no network) | ~2 min |
| `hatch run test-network` | Network tests only | varies |
| `hatch run test-slow` | Slow tests only | varies |
| `hatch run test-regression` | Regression tests | varies |
| `hatch run test-fast-parallel` | Fast tests parallelized | ~1 min |
| `hatch run test-full` | All tests | ~15 min |
| `hatch run cov` | With coverage report | varies |

**Important**: Only parallelize fast tests (`-n auto`) to avoid SEC rate limits.

## Markers

| Marker | When to Use |
|--------|-------------|
| `fast` | Pure logic, no network calls |
| `network` | Uses `Company()`, `get_filings()`, SEC API |
| `slow` | Heavy processing (>10s) |
| `regression` | Auto-applied in `regression/` folders |
| `vcr` | Uses VCR cassettes for recorded responses |
| `reproduction` | Issue reproduction tests |
| `batch` | Multi-company/filing tests |

## Auto-Marking System

Tests are **automatically marked** based on file name patterns in `conftest.py`:

### Fast Patterns (no network)
Files matching these patterns get `@pytest.mark.fast`:
- `test_html`, `test_documents`, `test_xbrl`, `test_tables`
- `test_markdown`, `test_xml`, `test_section`, `test_period`
- `test_reference`, `test_parsing`, `test_rendering`
- And more (see `FAST_PATTERNS` in conftest.py)

### Network Patterns (SEC API)
Files matching these patterns get `@pytest.mark.network`:
- `test_entity`, `test_company`, `test_filing`, `test_ownership`
- `test_funds`, `test_thirteenf`, `test_current`
- `test_xbrl_stitching` (special case - needs Company API)
- And more (see `NETWORK_PATTERNS` in conftest.py)

### Regression Tests
Tests in `tests/issues/regression/` are auto-marked with `@pytest.mark.regression`.

**Note**: Explicit markers on tests override auto-marking.

## VCR Cassettes

For slow network tests, use VCR to record and replay HTTP responses:

```python
@pytest.mark.network
@pytest.mark.vcr
def test_current_filings():
    """First run records to cassette, subsequent runs replay."""
    filings = get_current_filings()
    assert len(filings) > 0
```

Cassettes are stored in `tests/cassettes/` and should be committed.

**To re-record**: Delete the cassette file and run the test.

## Writing Tests

### Best Practices

1. **Use fixtures** instead of creating objects:
   ```python
   def test_company_filings(aapl_company):  # Use session fixture
       filings = aapl_company.get_filings(form="10-K")
   ```

2. **Markers are usually automatic** - only add explicit markers when:
   - Your test has special requirements
   - You need to override auto-marking

3. **Regression tests**: Place in `tests/issues/regression/test_issue_NNN.py`
   - Auto-marked, no explicit marker needed

4. **Use VCR for slow network tests** to speed up CI

### Example: Fast Test

```python
# File: tests/test_html_parser.py
# Auto-marked as 'fast' based on filename

def test_parse_table():
    """No explicit marker needed - auto-detected as fast."""
    html = "<table><tr><td>Value</td></tr></table>"
    result = parse_html_table(html)
    assert result is not None
```

### Example: Network Test

```python
# File: tests/test_company.py
# Auto-marked as 'network' based on filename

def test_company_facts(aapl_company):
    """Uses session fixture for performance."""
    facts = aapl_company.get_facts()
    assert facts.revenue is not None
```

### Example: Regression Test

```python
# File: tests/issues/regression/test_issue_429.py
# Auto-marked as 'regression' based on path

def test_issue_429_period_selection():
    """Verifies bug fix for issue #429."""
    # Test implementation
    pass
```

## Fixture Reference

### Session-Scoped (shared across all tests)
| Fixture | Description |
|---------|-------------|
| `aapl_company` | Apple Company object |
| `tsla_company` | Tesla Company object |
| `nflx_company` | Netflix Company object |
| `state_street_13f_filing` | State Street 13F filing |

### Module-Scoped (shared within test file)
| Fixture | Description |
|---------|-------------|
| `msft_company` | Microsoft Company object |
| `nvda_company` | NVIDIA Company object |
| `expe_company` | Expedia Company object |

See `tests/conftest.py` for the complete list.

## Test Suite Statistics

| Category | Count | Description |
|----------|-------|-------------|
| Fast | ~1,168 | No network, run in ~2 min |
| Network | ~1,154 | SEC API calls |
| Slow | ~104 | Heavy processing |
| Regression | ~372 | Bug fix verification |
| **Total** | ~2,547 | All tests |

## Troubleshooting

### Test fails in CI but passes locally
- Check if it needs `@pytest.mark.network` marker
- May be affected by rate limiting - add VCR cassette

### Test is flaky (sometimes fails)
- Check for shared state between tests
- Consider using session-scoped fixtures
- Add explicit markers to control test ordering

### Test is too slow
- Use session-scoped fixtures to avoid repeated setup
- Add VCR cassette for network calls
- Consider if it should be marked `@pytest.mark.slow`
