# EdgarTools Verification Weaknesses

A factual assessment of structural weaknesses in the current test suite, informed by the Verification Constitution principles.

---

## Constitution Overview (for context)

The Verification Constitution establishes eleven principles. Three are most relevant to the weaknesses below:

- **V. Verification is continuous, not a gate** — but growing test times make this increasingly difficult
- **IX. Spend verification where it buys confidence** — but the current suite doesn't tier by value
- **II. Data correctness is existential** — but 719 assertions only check existence, not correctness

---

## 1. The Compounding Growth Problem

### The numbers

| Period | Test commits | Test files added | Pace |
|--------|-------------|-----------------|------|
| H1 2024 | 125 | — | baseline |
| H2 2024 | 143 | — | +14% |
| 2025 YTD (38 days) | 669 | 181 | ~5x acceleration |
| 2024 full year | 268 | 33 | — |

**181 test files added in 38 days of 2025, vs 33 in all of 2024.** The test suite is growing at nearly 5x the previous rate. This is a direct consequence of increasing feature velocity — every new capability adds tests, which adds CI time, which compounds.

### Current test inventory

| Category | Files | Functions | CI inclusion |
|----------|-------|-----------|-------------|
| Fast (no network) | ~130 | ~1,800 | Yes, parallel |
| Network (SEC API) | ~54 | ~900 | Yes, sequential |
| Slow | varies | varies | Yes, sequential |
| Regression | 77 | 450 | Separate workflow |
| Batch scripts | 28 | — | No |
| Manual scripts | 62 | — | No |
| **Total** | **~350+** | **~3,500** | **Partial** |

### The compounding mechanics

Each new feature typically adds:
- 1-3 test files
- 5-20 test functions
- At least some network tests (sequential, rate-limited)

Network tests are the bottleneck. They run sequentially to respect the SEC's 10 req/sec rate limit. Every new network test adds linear time to the slowest CI job. There is no mechanism to convert network tests to cached tests over time — they stay live forever.

**The retry tax**: Failed tests retry twice with a 4-second delay. A single network test failure adds 8 seconds. Across a suite of 900+ network tests, even a small flakiness rate creates significant overhead. No CI timeout is configured, so a bad run can extend indefinitely.

---

## 2. The Coverage Crisis

### Current state

**Combined coverage: ~64%, below the 65% threshold.**

No individual job meets the threshold alone:

| Job | Approximate coverage | Parallelism |
|-----|---------------------|-------------|
| Fast | ~52% | `-n auto` (full parallel) |
| Network | ~55% | Sequential |
| Slow | ~35% | Sequential |
| **Combined** | **~64%** | — |

Coverage has been declining as the `edgar/` source grows faster than test coverage expands. The 65% threshold was already modest; falling below it signals structural erosion.

### The split-job measurement problem

Coverage is measured across three separate CI jobs, then mechanically combined:

```
Job 1 (fast)    → .coverage.fast
Job 2 (network) → .coverage.network
Job 3 (slow)    → .coverage.slow
                → coverage combine
                → coverage report --fail-under=65
```

**Problems with this approach:**

1. **Only Python 3.11 coverage is uploaded.** The CI matrix runs 4 Python versions (3.10-3.13), but only 3.11 artifacts are combined. Coverage on other versions is measured and discarded.

2. **pytest-xdist + coverage is fragile.** The fast job runs with `-n auto` (parallel workers). Each worker generates a separate `.coverage.N` file. These are auto-combined by the pytest-cov plugin before upload — but this depends on plugin internals. If a worker crashes, its coverage data may be lost silently.

3. **No per-job threshold.** Individual jobs are not checked. A catastrophic drop in one job (say, slow tests break and contribute 0%) would only be caught at the combine step. There's no early warning.

4. **Regression tests don't contribute.** The 77 regression test files (450 functions) are excluded from CI coverage runs. They run in a separate workflow. Any code they exercise doesn't count toward the 65% threshold.

5. **Batch, manual, and perf tests don't contribute.** 90+ files of scripts and manual tests exist in the test directory but are never run by CI. They are not tests in any automated sense.

### Modules with zero CI coverage

These are explicitly excluded from coverage measurement:

| Excluded module | Reason given |
|----------------|--------------|
| `edgar/ai/mcp/*` (9 files) | Requires MCP runtime |
| `edgar/ai/formats.py` | Experimental |
| `edgar/ai/helpers.py` | Experimental |
| `edgar/diagnose_ssl/*` | CLI tool |
| `edgar/documents/migration.py` | One-time utility |
| `edgar/display/demo.py` | Demo code |
| `edgar/entity/training/*` | ML training |
| `edgar/__about__.py` | Version metadata |
| `edgar/**/examples.py` | Example code |

Additionally, `edgar/earnings.py` and `edgar/financials.py` have **no dedicated test files** and are not excluded — they simply aren't tested.

---

## 3. The Cassette Deficit

### 15 cassettes for 900+ network tests

The VCR infrastructure is configured and working. But only 15 cassette files exist, covering only 19 tests. The remaining ~880 network tests hit the live SEC API on every run.

**Consequences:**
- Network tests are slow (each makes real HTTP requests)
- Network tests are flaky (SEC can be slow, rate-limit, or change)
- Network tests can't run offline
- Network tests can't be parallelized (rate limit)
- Test results are non-deterministic (SEC data changes over time)

**Cassette sizes** range from 6 KB to 37 MB (MSFT financials). The total cassette directory is ~355 MB for just 15 files. At this ratio, comprehensive cassette coverage would require significant storage — but would eliminate the network bottleneck.

The VCR config uses `record_mode: "once"` — cassettes are recorded on first run and never updated. There is no mechanism to detect stale cassettes or re-record them when SEC data changes. (Constitution Principle X: "Recorded verification must have an expiry.")

---

## 4. Assertion Quality

### 719 existence-only assertions

Across 131 test files, `assert ... is not None` appears 719 times. Additionally, 1,368 uses of `assert len(...)` test non-emptiness without verifying correctness.

**Top files by weak assertions:**

| File | `is not None` count | What it tests |
|------|---------------------|---------------|
| `test_bdc.py` | 28 | Business development companies |
| `test_fund_reference.py` | 25 | Fund reference data |
| `test_ten_d.py` | 23 | Asset-backed securitizations |
| `test_html_parser_edge_cases.py` | 20 | HTML parsing edge cases |
| `test_entity_facts.py` | 14 | Entity financial facts |
| `test_beneficial_ownership.py` | 14 | Schedule 13D/13G |

**What this means**: These tests verify that the code *runs* and returns *something*, but not that the data is *correct*. A test like `assert revenue is not None` passes whether revenue is $394B or $1. For a data provider where correctness is existential (Principle II), this is a significant blind spot.

---

## 5. Global State and Test Isolation

### The `reset_http_client_state` autouse fixture

Every single test in the suite runs through an autouse fixture that:
1. Closes the existing HTTP client
2. Sets `HTTP_MGR._client = None`
3. Resets `HTTP_MGR.httpx_params["verify"] = True`
4. Wraps cleanup in try/except (suggesting it can fail)

**This fixture exists because tests mutate global state.** The HTTP manager is module-level and mutable. Tests that modify SSL verification settings, connection parameters, or client state can corrupt subsequent tests. The autouse fixture is a band-aid over a shared-mutable-state problem.

### Session-scoped fixtures make real network calls

Three session-scoped fixtures (`aapl_company`, `tsla_company`, `nflx_company`) call `Company(ticker)` at session startup. This means:
- The test session blocks on SEC API calls before any test runs
- If the SEC is slow or down, the entire session is delayed or fails
- These fixtures are shared across all tests in the session — a failed fixture cascades to all dependents

---

## 6. The Skipped Test Debt

### 40 permanently skipped tests across 10 files

| Category | Count | Status |
|----------|-------|--------|
| Performance regression tests | 16 | "Enable as needed" — never enabled |
| HTML cache tests | 6 | "Work in progress" — incomplete feature |
| Flaky tests (XBRL precision, rate limit) | 6 | "Flaky. Will investigate" — no follow-up |
| AI feature tests | 6 | Conditional on optional imports |
| Other | 6 | Various reasons |

**Notable cases:**
- `test_local_storage.py` has `@pytest.mark.skipif(True, ...)` with the comment "The directory browsing issue is fixed" — the skip condition is hardcoded `True` despite claiming the issue is resolved
- `test_xbrl_ratios.py` skips 2 tests with "The ratio implementation will be revamped" — future work blocking current verification
- Rate limit tests marked "Flaky. Will investigate" — investigation never happened

Skipped tests are verification promises that were made and then abandoned. Each one is a gap that compounds silently.

---

## 7. Organizational Confusion

### 180 files at root level with no hierarchy

The `tests/` root contains 180 test files with no subdirectory organization. Finding the right test file for a given module requires knowing the naming convention — and the convention isn't consistent.

### Mixed content in the test directory

| What's there | Count | Actually tests? |
|-------------|-------|----------------|
| Automated test files | ~286 | Yes |
| Batch scripts (print, don't assert) | 28 | No — manual scripts |
| Manual/debug scripts | 62 | No — exploration tools |
| Performance scripts | ~27 | No — benchmarks, all skipped |

**90 files in the test directory are not automated tests.** They are scripts, demos, investigations, and benchmarks that happen to live alongside real tests. They don't run in CI, don't contribute to coverage, and make the test directory harder to navigate.

### Naming inconsistencies

- Issue tests appear both at root (`test_issue_*.py`, `test_bug_*.py`) and in `tests/issues/regression/`
- One file uses `test_bug_` prefix, everything else uses `test_issue_`
- No clear convention for when to place a regression test at root vs in the `issues/` subdirectory
- HTML-related tests spread across 11 files with overlapping scope

---

## 8. The Auto-Marking Brittleness

Tests are classified as `fast` or `network` by filename pattern matching in `conftest.py`. This is convenient but fragile:

- A test file named `test_filing_format.py` would be auto-marked as `network` (matches `test_filing*`) even if it only parses local fixtures
- A new test file that doesn't match any pattern gets **no marker** — it falls through to no category and may not run in any CI job
- The pattern lists must be manually maintained as new test files are added
- There's no validation that the auto-assigned marker is correct for the test's actual behavior

---

## Summary: The Five Structural Weaknesses

| # | Weakness | Impact | Constitution principle violated |
|---|----------|--------|-------------------------------|
| **1** | **Test growth compounds CI time** | Network tests add linear time; no conversion to cached tests | V (continuous), IX (spend wisely) |
| **2** | **Coverage is fragile and declining** | 64% combined, fragile combination, 90+ files excluded | II (correctness), XI (feature completeness) |
| **3** | **Cassettes are underutilized** | 15 cassettes for 900 network tests; live API on every run | IX (spend wisely), X (expiry) |
| **4** | **Assertions test existence, not correctness** | 719 `is not None` checks; data accuracy not verified | II (correctness), III (user experience) |
| **5** | **Organizational debt** | 90 non-test files in test dir; no hierarchy; inconsistent naming | — (operational, not principled) |
