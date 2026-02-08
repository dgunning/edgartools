# EdgarTools Verification Roadmap

The path from current state to constitutional compliance, executed in parallel with ongoing feature work.

**Governing documents:**
- [Verification Constitution](verification-constitution.md) — the 11 principles
- [Verification Survey](verification-survey.md) — what exists today
- [Verification Weaknesses](verification-weaknesses.md) — structural problems
- [Verification Gap Analysis](verification-gap-analysis.md) — principle-by-principle gaps

---

## Strategy: Two Tracks

**Track 1 — The Line in the Sand.** Starting now, every new feature follows the verification definition of done. No new verification debt accrues.

**Track 2 — Strategic Backfill.** Prioritized by leverage — how many problems each move solves simultaneously. Executed incrementally alongside feature work.

---

## Phase 0: Policy and Quick Wins

**Duration**: 1-2 weeks
**Goal**: Establish the rules; harvest free improvements

### 0.1 Update Verification Policy (Track 1)

Update all policy documents to reflect the new verification standards:

| Document | What changes |
|----------|-------------|
| `CLAUDE.md` | Replace test section with verification section; reference constitution |
| `docs/testing-guide.md` | Rewrite as `docs/verification-guide.md` with new standards |
| `.claude/agents/test-specialist.md` | Rewrite around verification principles, not just pytest mechanics |
| `.claude/agents/bug-hunter.md` | Add silence detection and ground-truth verification to workflow |
| `.claude/agents/issue-handler.md` | Update Phase 4 to require constitutional verification |
| `.claude/agents/edgartools-architect.md` | Add verification architecture awareness |
| `.claude/agents/docs-writer.md` | Add "every example must be verifiable" principle |

### 0.2 Reclassify Mismarked Tests

Audit tests auto-marked as `network` that don't actually make network calls. Reclassify ~30-40 tests to `fast`. Immediate CI speed gain.

**Deliverable**: Single PR reclassifying tests. Measurable reduction in network job time.

### 0.3 Organizational Cleanup

- Move `tests/batch/` scripts (28 files) → `scripts/batch/`
- Move `tests/manual/` scripts (62 files) → `scripts/manual/`
- Resolve skipped tests: fix, delete, or document why each is skipped
- Establish naming convention: all regression tests in `tests/issues/regression/`

**Deliverable**: Test directory contains only automated tests. Non-test file count in `tests/` drops from 90 to 0.

---

## Phase 1: Infrastructure

**Duration**: Weeks 3-8
**Goal**: Build the foundation that makes everything else possible

### 1.1 Cassette Expansion Campaign

The single highest-leverage move. Convert the most expensive network tests to cassette-based.

**Approach**:
1. Identify the 50 most time-consuming network tests (by runtime)
2. Record cassettes for each (first run records, subsequent runs replay)
3. Add cassette metadata: recording date, source filing accession numbers
4. Reclassify converted tests from `network` to `fast`

**Target**: 50 cassettes in first pass (up from 15). Network job time reduced by 40%+.

**Cassette staleness protocol** (Principle X):
- Each cassette YAML includes a `# Recorded: YYYY-MM-DD` header comment
- CI job (weekly) compares a random sample of cassettes against live SEC responses
- Divergences are flagged as issues, not auto-fixed

### 1.2 Coverage Threshold Recovery

Current: 64%. Target: 70%.

**Approach**:
- Cassette conversions naturally increase fast-test coverage
- Test reclassification ensures more tests contribute to the right coverage bucket
- Focus new tests on modules with zero coverage: `earnings.py`, `financials.py`
- Include regression tests in coverage measurement (they currently don't count)

### 1.3 Fix Coverage Combination Fragility

- Add per-job coverage floor (e.g., fast ≥ 45%, network ≥ 45%)
- Add coverage diff check on PRs: new code must have ≥ 80% coverage
- Verify pytest-xdist + coverage combination works reliably by adding a CI step that validates the merge

---

## Phase 2: Constitutional Alignment

**Duration**: Weeks 6-12 (overlaps Phase 1)
**Goal**: Close the four critical gaps

### 2.1 Documentation as Specification (Gap I)

Create `tests/test_documented_examples.py` that runs every code example from published documentation.

**Phase A — Core examples** (13 tests):
- 6 examples from README.md
- 7 examples from docs/quickstart.md

**Phase B — Guide examples** (30-50 tests):
- Code blocks from `docs/guides/*.md`
- Each test is literally the documented code, executed and asserted

**Phase C — Skill YAML verification**:
- For each skill YAML code pattern, verify it produces a non-error result
- Wire into evaluation CI (see 2.4)

**Policy**: Going forward, every new documented example must have a corresponding entry in `test_documented_examples.py`. The docs-writer agent enforces this.

### 2.2 SEC Breadth Diversification (Gap VII)

Establish a **breadth matrix** and fill it systematically.

```
                10-K  10-Q  8-K  13F  DEF14A  Form4  20-F  S-1  SC13D
Large-cap tech   ✓     ✓    ✓    ✓     ✓      ✓
Large-cap fin
Large-cap health
Mid-cap
Small-cap
International
```

**Approach**:
- Create `tests/breadth/` directory with matrix-organized tests
- Each cell is one test file testing that form type for that company category
- Start with 5 new company categories × the most-used form types
- Every new feature PR should fill at least one empty cell
- Track matrix coverage as a metric

**Starter companies** (non-AAPL, non-tech):
- Finance: JPM, BRK
- Healthcare: JNJ, PFE
- Energy: XOM, CVX
- Industrial: CAT, GE
- International: NVO (20-F), TSM (20-F)

### 2.3 Silence and Error-Path Hardening (Gap VI)

For each major user-facing method, add three tests:

1. **Empty input**: What happens when there's no data to return?
2. **Invalid input**: What happens with wrong arguments?
3. **Error message quality**: Is the error message helpful?

**Priority methods**:
- `Company(ticker).get_financials()` — no financials available
- `Company(ticker).get_filings(form=X)` — no filings of that type
- `Company(ticker).get_facts()` — no facts available
- `filing.xbrl()` — filing has no XBRL
- `filing.obj()` — unsupported form type
- `Filings.filter()` — filter produces empty result

**Target**: 30 silence/error tests covering the top 10 user-facing methods.

### 2.4 Evaluation CI Integration (Gap VIII)

Wire the existing evaluation framework into CI.

**Approach**:
- Select 5 canary test cases from the existing 25 (TC001, TC004, TC005, TC009, TC013)
- Create `.github/workflows/evaluation.yml` running weekly + on skill YAML changes
- Threshold: canary average score ≥ 0.7
- Full 25-case evaluation runs at milestones

---

## Phase 3: Sustainability

**Duration**: Week 10+ (ongoing)
**Goal**: Make constitutional compliance self-maintaining

### 3.1 Definition of Done Enforcement

Encode the verification definition of done as a CI check:

For every PR that adds new user-facing methods:
- ≥ 1 ground truth assertion (specific value from a real filing)
- ≥ 1 verified documented example (or update to existing docs)
- ≥ 1 silence check (error path test)
- Coverage on new code ≥ 80%

**Implementation**: Custom CI step that detects new public methods and checks for corresponding test additions.

### 3.2 Cassette Refresh Schedule

- Weekly CI job: sample 10% of cassettes, compare against live SEC responses
- Flag divergences as issues (not auto-record — divergence might reveal a real change)
- Dashboard: cassette age distribution, oldest cassette date

### 3.3 Breadth Matrix Tracking

- Monthly metric: % of breadth matrix cells filled
- Target: 50% within 6 months, 80% within 12 months
- Each release notes which cells were added

### 3.4 Upstream Change Detection (Gap IV)

Build the mechanism to distinguish "our bug" from "SEC changed":
- Nightly job runs a small set of "canary filings" against live SEC
- If responses diverge from recorded cassettes, create an issue tagged `upstream-change`
- Separate from test failures — this is monitoring, not testing

---

## Metrics Dashboard

| Metric | Baseline (now) | Phase 0 target | Phase 1 target | Phase 2 target |
|--------|---------------|----------------|----------------|----------------|
| Cassette count | 15 | 15 | 65+ | 100+ |
| CI network job time | Unknown | -10% | -40% | -50% |
| Combined coverage | 64% | 65% | 70% | 75% |
| Doc examples verified | 0/100+ | 0 | 0 | 50+ |
| Breadth: unique companies | ~15 | ~15 | ~20 | ~30 |
| Breadth: form types tested | ~10 | ~10 | ~12 | ~18 |
| Silence/error tests | ~35 | ~35 | ~35 | ~65 |
| Skipped tests | 40 | <15 | <10 | <5 |
| Non-test files in tests/ | 90 | 0 | 0 | 0 |

---

## What This Does NOT Include

- Rewriting existing tests (too disruptive, low ROI)
- 100% line coverage (not the goal — breadth over lines)
- Eliminating all network tests (some must stay live to detect upstream changes)
- Automated cassette re-recording (divergence should be investigated, not auto-fixed)
