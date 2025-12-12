# Testing Guide

## Directory Structure

```
tests/
├── conftest.py           # Fixtures, hooks, config
├── fixtures/             # Test data
├── issues/
│   ├── regression/       # Auto-marked regression tests
│   └── reproductions/    # Issue reproductions by category
├── batch/                # Batch integration tests
├── perf/                 # Performance benchmarks
└── test_*.py             # Main test suite
```

## Test Commands

```bash
hatch run test-fast              # Fast tests only (no network)
hatch run test-network           # Network tests
hatch run test-fast-parallel     # Parallelized (safe for fast tests)
hatch run test-regression        # Regression only
hatch run test-full              # All tests
hatch run cov                    # With coverage
```

**Important**: Only parallelize fast tests (`-n auto`) to avoid SEC rate limits.

## Markers

| Marker | When to Use |
|--------|-------------|
| `fast` | Pure logic, no network calls |
| `network` | Uses `Company()`, `get_filings()`, etc. |
| `slow` | Heavy processing |
| `regression` | Auto-applied in `regression/` folders |
| `reproduction` | Issue reproduction tests |
| `batch` | Multi-company/filing tests |

## Key Configuration (conftest.py)

- **Auto-marking**: Tests in `regression/` auto-get `@pytest.mark.regression`
- **Fixtures**: `aapl_company`, `tsla_company`, etc. (session-scoped)
- **HTTP caching**: Disabled for tests (use `--enable-cache` to override)

## Writing Tests

### Best Practices

1. Use appropriate markers (`fast`, `network`, etc.)
2. Use fixtures (`aapl_company`) instead of creating objects
3. Regression tests: Place in `tests/issues/regression/` (auto-marked)
4. Reproductions: Place in `tests/issues/reproductions/<category>/`

### Example: Network Test

```python
@pytest.mark.network
def test_company_facts(aapl_company):
    """Use session fixture for performance"""
    facts = aapl_company.get_facts()
    assert facts.revenue is not None
```

### Example: Regression Test

```python
# File: tests/issues/regression/test_issue_429.py
# No marker needed - auto-applied based on location
def test_issue_429_period_selection():
    """Test specific bug fix"""
    pass
```

## Fixture Reference

| Fixture | Description |
|---------|-------------|
| `aapl_company` | Apple Company object (session-scoped) |
| `tsla_company` | Tesla Company object (session-scoped) |
| `msft_company` | Microsoft Company object (session-scoped) |
