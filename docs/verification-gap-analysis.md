# EdgarTools Verification Gap Analysis

A principle-by-principle assessment of the current test suite against the Verification Constitution.

---

## How to Read This Document

Each principle is assessed with:
- **Current state** — what exists today (factual)
- **Gap** — where the current state falls short of the principle
- **Severity** — Critical / Significant / Moderate / Minor
- **Evidence** — specific numbers and examples

---

## I. Documentation is the Specification

> *"Every documented behavior is a verifiable claim."*

### Current State
- 100+ code examples across README.md, quickstart.md, guides, and skill YAML files
- 70+ documented code patterns in skill YAML files (core, financials, holdings, ownership, reports, xbrl)
- 32 doctest-style examples (`>>>`) in `edgar/offerings/formc.py` docstrings
- Zero doctest integration in pytest configuration
- Zero test files that execute documentation examples
- No `pytest --doctest-modules` or equivalent configured

### Gap
**Documentation and verification are completely decoupled.** Individual API methods are tested, but the documented examples — the actual promises to users — are never verified as a unit. A README example could break and no test would catch it.

The skill YAML files are particularly concerning. They guide AI agents to use specific API patterns. If those patterns break, agent solvability degrades silently — and the evaluation framework that could catch this isn't wired into CI.

### Severity: Critical
This is the foundational principle. Without it, every other principle is built on undocumented assumptions.

### Evidence
- `grep -r "doctest" tests/` → 0 results
- `grep -r ">>>" edgar/offerings/formc.py` → 32 examples, none executed
- pyproject.toml pytest config: no `addopts = "--doctest-modules"`

---

## II. Data Correctness is Existential

> *"Verification must assert not just that code runs, but that the data is right."*

### Current State
**Stronger than initially expected.** Deep analysis reveals:
- 3,839 exact equality assertions (`assert x == specific_value`) — 83.7% of all assertions
- 747 existence-only assertions (`is not None`) — 16.3%
- 5.1:1 ratio of value-specific to existence-only checks
- Regression tests contain strong ground truth: Apple's FY2023 net income ($96.99B), Pfizer's 2017 total assets ($171.797B), specific CUSIP numbers, share counts
- 5 files use `pytest.approx()` for floating-point tolerance
- Multi-period validation across fiscal years (AAPL 2021-2023)

### Gap
The ground truth is **embedded in test code, not externalized.** There is no reference data file (CSV/JSON) of known-correct values that could be:
- Audited independently
- Updated when SEC data changes
- Shared across tests
- Used to generate new tests

When a ground-truth value needs updating (e.g., a company restates earnings), every test file must be manually found and edited.

Additionally, the 747 existence-only assertions cluster in specific modules (BDC: 28, fund reference: 25, ten_d: 23, HTML edge cases: 20). These are areas where data correctness is untested — the code runs, but the values aren't verified.

### Severity: Moderate
The overall ratio is healthy (5:1 value-to-existence). The gap is structural (no external truth source) rather than pervasive.

### Evidence
- `test_xbrl_statements.py`: `assert df[net_income_filter]['2023-09-30'].item() == 96995000000.0`
- `test_issue_564_xbrl_precision_regression.py`: `assert value_2017 == pytest.approx(171797000000.0)`
- `test_bdc.py`: 28 `is not None` assertions with zero value checks

---

## III. The User's Experience is the Unit of Verification

> *"We verify what the user sees, not internals."*

### Current State
- Repr/display tests exist for major objects: Company, Filing, Filings, Statements, XBRL
- `test_xbrl_statement_display.py` verifies rich panel output and helpful hints (`.search()` method)
- `test_company.py` verifies repr shows ticker, CIK, industry, filer category
- Some tests verify formatted currency output (`assert '$25,500' in repr_`)

### Gap
**Internal implementation details leak into many tests.** Tests frequently assert on:
- Internal DataFrame column names and shapes
- Private method return types
- XBRL concept IDs (implementation detail, not user-facing)

This creates **refactoring friction** — changing internals requires rewriting tests, even when user-facing behavior hasn't changed. The auto-marking system in conftest.py classifies by filename pattern (implementation concern), not by what user behavior the test verifies.

No systematic verification of the user's journey: "I have a Company object — what can I do next?" The objects are tested in isolation, not as a connected experience.

### Severity: Moderate
Display tests exist for key objects but the overall orientation is implementation-inward, not user-outward.

---

## IV. The SEC is the Upstream We Can't Control

> *"Our verification must distinguish between 'our code is broken' and 'the upstream data changed.'"*

### Current State
- 900+ network tests hit the live SEC API on every run
- 15 VCR cassettes capture historical responses for 19 tests
- Cassettes use `record_mode: "once"` — recorded on first run, never updated
- No cassette metadata (creation date, expected refresh date)
- Regression tests (77 files) are often tied to specific SEC filing data

### Gap
**No mechanism exists to distinguish an EdgarTools bug from an SEC data change.** When a network test fails, the developer must manually investigate whether:
1. The library code broke (our fault)
2. The SEC changed its data format (upstream change)
3. The SEC is temporarily unavailable (transient)
4. The specific filing data was amended or restated (data change)

The retry mechanism (2 retries, 4s delay) handles transient failures but masks the distinction — a test that passes on retry might have revealed an intermittent upstream issue.

The 15 cassettes that do exist have **no expiry tracking**. They represent frozen assumptions about SEC responses that may have diverged from reality months ago. There is no process to re-validate them.

### Severity: Critical
This is an operational blindspot. Every CI failure requires manual triage that could be automated.

---

## V. Verification is Continuous, Not a Gate

> *"A verification that only runs in CI is a verification that lies to you between pushes."*

### Current State
- CI runs on every push/PR to main: fast (parallel), network (sequential), slow (sequential)
- Local commands available: `hatch run test-fast`, `test-network`, `test-regression`, etc.
- No CI timeout configured — a bad run can extend indefinitely
- Regression tests run on a separate schedule (weekly, manual, or on key path changes)
- Evaluation framework (solvability) is manual-only — never runs in CI

### Gap
**The suite is becoming too slow for continuous use.**

The growth curve is unsustainable:
- 181 test files added in 38 days of 2025 (vs 33 in all of 2024)
- Network tests add linear time with no conversion path to cached tests
- Each failed network test adds 8 seconds of retry overhead
- No test graduation mechanism (live → cassette → fixture)

Developers likely skip `test-network` locally because it's slow and requires internet. This means network-dependent code changes are only verified in CI — exactly the "gate" pattern this principle rejects.

The evaluation framework (Tier 3 in the constitution) has never run in CI. Skill quality is a manual checkpoint.

### Severity: Critical
Compounding growth without a speed strategy will make continuous verification impossible.

---

## VI. Silence is the Worst Failure Mode

> *"Returning None where a user expected data is worse than raising an error."*

### Current State
- 747 assertions check `is not None` (value exists)
- 352 assertions check `is None` (value correctly absent)
- 2.12:1 asymmetry — tests are biased toward "happy path returns something"
- 148 tests use `pytest.raises` (4.1% of all tests)
- 0 tests use `pytest.warns` — no warning verification
- ~35 tests check empty result behavior (<1% of total)
- 262 tests have error/empty/invalid in their name (7.2%)

### Gap
**The suite is heavily biased toward verifying that data appears, not that errors surface.**

Critical silence scenarios with no or minimal testing:
- Company with zero filings → what does `get_facts()` return?
- Filing with no XBRL → does `.xbrl()` return `None` silently or raise?
- Search returning zero results → does pagination break?
- Malformed XBRL → does parsing return partial results silently?
- SEC returns unexpected HTML → does the parser return empty content?

The warning system is untested entirely. `print_warning` is called in production code but `pytest.warns` is never used. Warnings could disappear or change text without detection.

Degradation paths are untested: "if the primary extraction method fails, does the fallback work?" These are precisely the paths where silence is most dangerous.

### Severity: Significant
The 2.12:1 asymmetry and 0% warning verification reveal a systematic gap. Silent failures in a data library erode trust invisibly.

### Evidence
- `grep -rc "pytest.warns" tests/` → 0
- `grep -rc "pytest.raises" tests/` → 148
- `grep -rc "is not None" tests/` → 747
- `grep -rc "is None" tests/` → 352

---

## VII. Coverage Means Breadth of the SEC, Not Lines of Code

> *"100% line coverage with one company's filings is weaker than 60% across diverse filers."*

### Current State

**Company concentration:**

| Company | Test occurrences | Share |
|---------|-----------------|-------|
| AAPL | 280+ | ~40% |
| MSFT | 72+ | ~10% |
| TSLA | 40+ | ~6% |
| EXPE | 25+ | ~4% |
| NVDA | 20+ | ~3% |
| All others | ~260 | ~37% |

**Industry concentration:**
- Technology: ~70% of company-specific tests
- Finance: ~8%
- Travel: ~5%
- Pharma: ~1%
- All other industries: untested

**Form type coverage:**

| Status | Forms |
|--------|-------|
| Well-tested | 10-K, 10-Q, 8-K, Form 3/4/5, 13F-HR |
| Lightly tested | DEF 14A, Form C, NPORT-P, 424B5 |
| Untested | 20-F, 6-K, S-1, S-3, SC 13D, SC 13G, N-1A, Form 35-D |

**Edge cases:**

| Covered | Not covered |
|---------|------------|
| Amended filings | Non-US filers (20-F, 6-K) |
| Dimensional data | Pre-2010 filings |
| Currency conversions | Companies in bankruptcy |
| Zero-division edge cases | Delisted companies |
| Multi-entity filings | Small-cap / micro-cap filers |
| | Chinese ADR / VIE structures |

### Gap
**The test suite reflects the development team's filing diet, not the SEC's diversity.** Apple alone is 40% of test references. Technology is 70% of industry coverage. The forms that are tested are the forms the developers use most often.

This means EdgarTools is verified to work well for large-cap US tech companies filing standard forms. Its behavior with smaller companies, international filers, unusual form types, and edge-case industries is essentially unverified.

### Severity: Critical
For a library claiming to be "the premier open source data provider," breadth is the promise. Testing only Apple is testing only the happy path.

---

## VIII. The API Must Be Solvable

> *"A user — human or agent — should be able to go from question to answer."*

### Current State
- 25 task-based test cases (TC001-TC025) in `edgar/ai/evaluation/test_cases.py`
  - Easy: single-company lookups
  - Medium: multi-metric financial analysis
  - Hard: multi-company comparisons, multi-step workflows
- Evaluation framework (runner, judge, harness) is complete and battle-tested
- Repr/display tests exist for Company, Filing, Statements
- Some error message tests for validation errors and deprecation warnings

### Gap
**The solvability infrastructure exists but is disconnected from CI.** The 25 task-based tests and LLM judge never run automatically. Skill YAML changes could regress agent performance without detection.

Error message testing is sparse. When a user makes a mistake (wrong ticker format, invalid form type, calling methods in wrong order), the test suite doesn't verify that the error message guides them to the correct path. Only a handful of `ValueError` messages are tested.

No tests verify the discovery experience: "Given a Company object, can I find `get_financials()` through `__repr__`, tab completion cues, or docstrings?"

### Severity: Significant
The investment in the evaluation framework is wasted if it never runs. Solvability could be regressing undetected.

---

## IX. Spend Verification Where It Buys the Most Confidence

> *"Structure verification in tiers so that cheap verification runs constantly, expensive verification runs deliberately."*

### Current State

| Current tier | Basis | CI frequency |
|-------------|-------|-------------|
| Fast | Filename pattern → no network | Every push, parallel |
| Network | Filename pattern → has network | Every push, sequential |
| Slow | Filename pattern → slow | Every push, sequential |
| Regression | Directory path | Weekly / manual |
| Evaluation | Manual only | Never |

### Gap
**Tiering is by execution speed, not by verification value.** The distinction between "fast" and "network" is about I/O requirements, not about what confidence each test provides.

Concrete problems:

1. **30-40 network tests could be fast.** Tests using pre-constructed `Filing(...)` fixtures don't actually call the SEC API, but are auto-marked as `network` because their filename matches `test_filing*`. They run sequentially instead of in parallel, wasting CI time.

2. **No "recorded" tier.** The constitution defines Tier 1 as cassette-based (milliseconds, every commit). Only 15 cassettes exist. There's no systematic effort to graduate live tests to recorded tests.

3. **Evaluation is Tier 3 but runs at Tier ∞ (never).** The LLM-based evaluation framework is the only way to verify solvability. It costs real money to run, which is why it's manual. But it could run on a schedule or on skill-file changes — it doesn't.

4. **No per-test cost awareness.** The suite doesn't track which tests are expensive (slow, flaky, high-retry). There's no data to inform "which tests should we cache next?"

### Severity: Significant
The wrong tests are running at the wrong frequency. Fast tests that could parallelize are stuck in the sequential network queue. Expensive evaluation that should run weekly never runs.

---

## X. Recorded Verification Must Have an Expiry

> *"A cassette that hasn't been refreshed is a verification that's slowly becoming a lie."*

### Current State
- 15 VCR cassettes, totaling ~355 MB
- `record_mode: "once"` — cassettes are created on first run and never re-recorded
- No creation date metadata in cassette files
- No staleness detection mechanism
- No process to refresh or validate cassettes against live data
- Cassette sizes range from 6 KB to 37 MB

### Gap
**Every cassette is a frozen assumption with no expiry date.** The VCR configuration records once and replays forever. There is no mechanism to:
- Know when a cassette was recorded
- Flag a cassette as potentially stale
- Compare a cassette's data against current SEC responses
- Schedule cassette refresh

The 37 MB MSFT financials cassette could contain data from a year ago. If Microsoft restated earnings or the SEC changed its response format, the cassette would continue passing tests with stale data — a verified lie.

This is slightly mitigated by the fact that only 15 cassettes exist. Most tests hit the live API, so staleness isn't their problem (speed and flakiness are). But as the suite moves toward more cassettes (which it must, per Principle IX), the staleness problem will scale.

### Severity: Moderate (today), Critical (as cassettes scale)
With 15 cassettes, this is manageable. With 500 cassettes (the target for Principle IX), it becomes the central risk.

---

## XI. A Feature Without Verification is Incomplete

> *"Every new capability ships with verification proportional to the breadth of its promise."*

### Current State
- No enforced definition of done for new features
- No CI check that verifies new code has corresponding tests
- No mechanism to link features to their verification
- No coverage diff enforcement on PRs (only aggregate 65% threshold)
- The 65% threshold is below industry standard and currently failing (64%)

### Gap
**There is no structural enforcement that new features include verification.** The only gate is the 65% aggregate coverage threshold — and it's currently failing. A developer can add a new user-facing method with zero tests, and if the aggregate coverage stays above 65%, nothing catches it.

The definition of done from the constitution (ground truth assertion + documented example + silence check + solvability for user-facing features) is not encoded anywhere. It's a principle, not a gate.

### Severity: Significant
Without enforcement, the principle is aspirational. As development velocity increases (5x in 2025), the gap between features and verification will widen.

---

## Summary: Gap Severity Matrix

| Principle | Gap | Severity |
|-----------|-----|----------|
| **I. Docs = Spec** | 100+ code examples, zero verified | Critical |
| **II. Data Correctness** | Strong values (5:1 ratio) but no external truth source | Moderate |
| **III. User Experience** | Tests oriented inward, not toward user journey | Moderate |
| **IV. SEC Upstream** | No distinction between our bugs and SEC changes | Critical |
| **V. Continuous** | Growth compounding; network tests add linear time | Critical |
| **VI. Silence** | 2:1 asymmetry; 0% warning tests; <1% empty-result tests | Significant |
| **VII. SEC Breadth** | 40% AAPL, 70% tech, ~50% of common forms | Critical |
| **VIII. Solvable** | Evaluation framework exists but disconnected from CI | Significant |
| **IX. Tiered Spending** | Tiering by speed not value; 30-40 misclassified tests | Significant |
| **X. Cassette Expiry** | 15 cassettes with no staleness tracking | Moderate (scaling risk) |
| **XI. Definition of Done** | No enforcement mechanism | Significant |

### The Four Critical Gaps

1. **Documentation is unverified** (I) — the promises we make to users are never tested as stated
2. **SEC changes are invisible** (IV) — no way to know if a failure is ours or theirs
3. **Growth is unsustainable** (V) — 5x test velocity with linear network time
4. **Breadth is an illusion** (VII) — we test Apple thoroughly and call it coverage
