# Verification Guide

This guide covers how to write and run verification for EdgarTools. We use "verification" deliberately — it's outward-facing ("does this library deliver what we promised?") rather than inward-facing ("does my code work?").

**Governing document**: [Verification Constitution](verification-constitution.md)

**Transition note**: These standards apply to new work. The existing suite (~3,500 tests) predates the constitution and is being aligned incrementally per the [Verification Roadmap](verification-roadmap.md). Do not rewrite existing tests to match these standards unless explicitly asked — improve them when you're already touching them for a bug fix or feature.

---

## Quick Start

```bash
# Fast verification (no network) — run this often
hatch run test-fast

# Full suite
hatch run test-full

# With coverage
hatch run cov
```

## Commands

| Command | Description | When to use |
|---------|-------------|-------------|
| `hatch run test-fast` | Fast tests, no network | After every code change |
| `hatch run test-fast-parallel` | Fast tests, parallelized | For speed |
| `hatch run test-network` | Network tests (sequential) | Before pushing |
| `hatch run test-slow` | Slow tests | Before release |
| `hatch run test-regression` | Regression tests | After fixing bugs |
| `hatch run test-full` | Everything | Before release |
| `hatch run cov` | With coverage report | Periodically |

**Important**: Only parallelize fast tests (`-n auto`) to avoid SEC rate limits.

---

## Definition of Done

Every new user-facing feature must include:

### 1. Ground Truth Assertion

Assert a specific value from a real SEC filing, confirmed by hand against the source.

```python
# GOOD — verifies data correctness
def test_apple_2024_revenue():
    financials = Company("AAPL").get_financials()
    revenue = financials.income_statement.get_value("Revenues")
    assert revenue == 391035000000  # FY2024, verified against 10-K

# BAD — verifies existence only
def test_apple_has_revenue():
    financials = Company("AAPL").get_financials()
    revenue = financials.income_statement.get_value("Revenues")
    assert revenue is not None  # Could be any number
```

### 2. Verified Documented Example

If the feature has documentation, the documented code must be a runnable test. Add it to `tests/test_documented_examples.py`.

### 3. Silence Check

Verify that failure produces a useful signal, not silent `None`.

```python
def test_company_with_no_financials_raises():
    """Company with no XBRL financials should signal clearly."""
    company = Company("0000350001")  # Company with no financials
    result = company.get_financials()
    # Either raises an informative error OR returns empty with clear indication
    # Must NOT silently return None where data was expected
```

### 4. Solvability (for major features)

Update skill YAML files in `edgar/ai/skills/` so AI agents can discover and use the feature.

---

## Verification Tiers

| Tier | Cost | Frequency | What it covers |
|------|------|-----------|----------------|
| **0: Static** | Zero | Every keystroke | Types, imports, syntax |
| **1: Recorded** | Milliseconds | Every commit | Cassette-based, fixture-based. The bulk of verification. |
| **2: Live** | Rate-limited | PR / nightly | Real SEC API calls. Catches upstream drift. |
| **3: Evaluation** | LLM API cost | Weekly / milestone | Agent solvability testing |

Each tier protects the tier above it from running too often.

---

## Writing Verification

### Assert Values, Not Existence

```python
# GOOD: specific, falsifiable
assert df['2023-09-30'].item() == 96995000000.0
assert filing.form == "10-K"
assert len(filings) == 42

# WEAK: passes with wrong data
assert result is not None
assert len(filings) > 0
```

Use `pytest.approx()` only when floating-point arithmetic or unit conversions justify tolerance.

### Use VCR Cassettes for Network Tests

Cassettes record SEC responses and replay them on subsequent runs. This makes network tests fast, deterministic, and offline-capable.

```python
@pytest.mark.vcr
def test_current_filings():
    """First run records to cassette, subsequent runs replay."""
    filings = get_current_filings()
    assert len(filings) > 0
```

Cassettes are stored in `tests/cassettes/` and committed to git.

**To re-record**: Delete the cassette YAML file and run the test.

**Staleness**: Every cassette represents a frozen assumption. Add a recording date comment and periodically re-validate against live data.

### Diversify Test Companies

Don't default to AAPL for every test. Use companies from different industries:

| Industry | Tickers |
|----------|---------|
| Tech | AAPL, MSFT, NVDA |
| Finance | JPM, BRK |
| Healthcare | JNJ, PFE |
| Energy | XOM, CVX |
| Industrial | CAT, GE |
| International | NVO, TSM |

### Test Error Paths

```python
def test_invalid_form_type_raises():
    with pytest.raises(ValueError, match="Unknown form type"):
        company.get_filings(form="INVALID")

def test_empty_filings_filter():
    result = filings.filter(filing_date="1900-01-01")
    assert len(result) == 0  # Not None, not error — empty collection
```

---

## Directory Structure

```
tests/
├── conftest.py              # Fixtures, auto-marking, VCR config
├── test_*.py                # Main verification suite
├── test_documented_examples.py  # Docs-as-spec verification
├── cassettes/               # VCR recorded responses (committed)
├── fixtures/                # Static test data (HTML, XBRL)
├── data/                    # Additional test data
├── issues/
│   ├── regression/          # Bug regression tests (auto-marked)
│   └── reproductions/       # Issue reproduction tests
├── breadth/                 # SEC breadth matrix tests
└── harness/                 # Test infrastructure
```

Non-automated scripts belong in `scripts/`, not `tests/`.

---

## Auto-Marking System

Tests are automatically classified by filename pattern in `conftest.py`:

- **Fast** (no network): `test_html*`, `test_xbrl*`, `test_tables*`, `test_parsing*`, `test_reference*`, etc.
- **Network** (SEC API): `test_entity*`, `test_company*`, `test_filing*`, `test_ownership*`, etc.
- **Regression**: Any test in `tests/issues/regression/`

Explicit markers override auto-marking. When in doubt, add an explicit marker.

---

## Markers

| Marker | When to use |
|--------|-------------|
| `fast` | Pure logic, no network calls |
| `network` | Uses SEC API (Company(), get_filings(), etc.) |
| `slow` | Heavy processing (>10s) |
| `regression` | Auto-applied in regression/ folders |
| `vcr` | Uses VCR cassettes for recorded responses |

---

## Fixtures

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

---

## Coverage

Coverage is measured per test group and combined in CI to enforce a threshold.

| Group | Approximate coverage |
|-------|---------------------|
| Fast | ~52% |
| Network | ~55% |
| Slow | ~35% |
| **Combined** | **Target: 70%+** |

### CI Coverage Flow

1. `fast`, `network`, and `slow` tests run as separate CI jobs
2. Each uploads its `.coverage` artifact (Python 3.11 only)
3. `Combine Coverage` job merges all data
4. Combined coverage checked against threshold
5. Report uploaded to Codecov

---

## Regression Tests

When fixing a bug:

1. Create `tests/issues/regression/test_issue_NNN_description.py`
2. Include a ground-truth assertion that would have caught the bug
3. Reference the GitHub issue number in a docstring
4. The test is auto-marked as `regression` based on its path

```python
# tests/issues/regression/test_issue_451_expense_sign.py

def test_cost_of_goods_sold_positive():
    """Regression for #451: COGS must be positive in income statement."""
    filing = Filing(accession_number="0000320193-20-000096")
    xbrl = filing.xbrl()
    income = xbrl.statements.income_statement
    cogs = income.get_value("CostOfGoodsAndServicesSold", period="2020-09-26")
    assert cogs == pytest.approx(169559000000.0)
    assert cogs > 0  # Sign must be positive
```

---

## Troubleshooting

### Test fails in CI but passes locally
- Check if it needs `@pytest.mark.network` marker
- May be affected by rate limiting — add a VCR cassette
- Check for test ordering dependencies

### Test is flaky
- Add a VCR cassette to eliminate network variability
- Check for shared global state between tests
- The `reset_http_client_state` autouse fixture handles HTTP client cleanup

### Test is too slow
- Add a VCR cassette for network calls
- Use session-scoped or module-scoped fixtures
- Consider if it should be marked `@pytest.mark.slow`
