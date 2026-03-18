# Auto-Eval Results Log

Tracks the evolution of CQS (Composite Quality Score) across auto-eval sessions. Each entry records what changed, why, and the measured impact.

## CQS Formula

```
CQS = 0.50 * pass_rate
    + 0.20 * (1 - mean_variance / 100)
    + 0.15 * coverage_rate
    + 0.10 * golden_master_rate
    + 0.05 * (1 - regression_rate)
```

## Cohort

Quick-eval cohort (5 companies, diverse archetypes):
- **AAPL** (Tech), **JPM** (Banking), **XOM** (Energy), **WMT** (Consumer), **JNJ** (Healthcare)

---

## Session 1 — Initial Auto-Eval System (2026-03-16)

**Commit:** `bdd1d520` feat: implement autonomous auto-eval system

First auto-eval session. Resolved 5 of 12 gaps via config-only changes.

| Metric | Before | After |
|--------|--------|-------|
| CQS | 0.9062 | 0.9265 |
| Pass rate | 91.7% | 95.8% |
| Coverage | 93.8% | 95.8% |
| Gaps | 12 | 7 |

**Changes applied:**
- Added exclusions for structural gaps (banking companies missing Inventory, COGS, etc.)
- Added known_concepts for several metrics
- Multi-period verification prevented false positives

**Remaining gaps (7):**
- JPM:CashAndEquivalents (unmapped)
- XOM:LongTermDebt, WeightedAverageSharesDiluted (unmapped)
- JNJ:OperatingIncome (unmapped)
- JPM:IntangibleAssets, XOM:OperatingIncome, XOM:Inventory (high variance)

---

## Session 2 — Parallel Scouts + Foundation Fixes (2026-03-18)

**Commits:** `b9132531` through `9487b4b7` (5 commits)

Major infrastructure overhaul focused on speed and fixing broken tools.

### Foundation Fixes

| Fix | Impact |
|-----|--------|
| `FilingSGML.from_filing()` checks local storage before network | Enables offline mode |
| `discover_concepts._search_calc_trees()` uses `calculation_trees` API | Was silently returning empty — now finds calc tree concepts |
| `identify_gaps()` runs orchestrator once (was twice) | 300s → 49s (6x faster) |
| `strip_prefix()` handles `us-gaap_` underscore form | Concepts in calc trees were invisible to variation matching |
| `get_facts()` None-safety across pipeline | Layer 2 facts search was crashing silently |

### Parallel Scout Infrastructure

Replaced 3 Haiku LLM agents (concept-scout, period-verifier, cross-company-learner) with Python `ThreadPoolExecutor`:
- `parallel_scout_gaps()`: scouts N gaps in parallel using existing Python tools
- `batch_evaluate()`: applies non-conflicting changes, measures CQS once
- `cross_company_learn()`: verifies concept transfer across companies in parallel

Kept `haiku-gap-classifier` for reasoning-only gap classification (industry context).

### Results

| Metric | Session 1 End | Session 2 End |
|--------|---------------|---------------|
| CQS | 0.9265 | 0.9313 |
| Pass rate | 95.8% | 95.8% |
| Coverage | 95.8% | 99.0% |
| Gaps | 7 | 4 |
| `identify_gaps` time | ~300s | 49s |
| Scout proposals | N/A | 4/7 found |

**Key insight:** Downloading bulk company facts data (18GB, all SEC companies) unblocked Layer 2 facts search. JPM:CashAndEquivalents, XOM:LongTermDebt, and XOM:WeightedAverageSharesDiluted resolved automatically — no config changes needed, just data availability.

### Per-Company Breakdown (Session 2 End)

| Company | CQS | Pass | Coverage | Variance |
|---------|-----|------|----------|----------|
| AAPL | 0.989 | 100% | 100% | 0.0% |
| WMT | 0.986 | 100% | 100% | 0.0% |
| JNJ | 0.919 | 95.2% | 95.2% | 3.4% |
| XOM | 0.900 | 90.5% | 100% | 2.2% |
| JPM | 0.862 | 93.3% | 100% | 2.4% |

### Remaining Gaps (4)

| # | Company | Metric | Type | Notes |
|---|---------|--------|------|-------|
| 1 | JNJ | OperatingIncome | unmapped | JNJ uses `IncomeLossFromContinuingOperations`, not `OperatingIncomeLoss` |
| 2 | JPM | IntangibleAssets | high_variance | Mapped but value diverges from yfinance |
| 3 | XOM | OperatingIncome | high_variance | Mapped but 56.9% variance |
| 4 | XOM | Inventory | high_variance | Mapped but variance above threshold |

### Data Downloaded

| Data | Size | Purpose |
|------|------|---------|
| Submissions | 7.2 GB | Company metadata, filing indexes (all SEC companies) |
| Company Facts | 18 GB | Pre-processed financial facts (all SEC companies) |
| Reference | 2.6 MB | Ticker/CIK mappings |
| **Total** | **~25 GB** | Enables `Company()` and `get_facts()` without network |

---

## Architecture Notes

### What Worked
- **Autoresearch pattern**: config-only changes + fixed eval harness = safe autonomous operation
- **CQS as single metric**: clear decision signal (KEEP if improved, DISCARD if not, VETO on regression)
- **Bulk data > clever code**: downloading company facts resolved 3 gaps that concept discovery couldn't
- **Python parallel > LLM agents**: ThreadPoolExecutor for mechanical tasks is faster, free, deterministic

### What Didn't Work
- **Haiku agents for mechanical tasks**: no benefit over calling Python functions directly
- **verify_mapping with yfinance**: requires yfinance installed; orchestrator uses snapshots instead
- **Similarity-based concept matching alone**: too imprecise for XBRL concept names; needed known variations table

### Pipeline Speed Evolution

| Phase | `identify_gaps` | `parallel_scout` | Total |
|-------|----------------|-------------------|-------|
| Session 1 | ~300s | N/A | ~300s |
| Session 2 (no local data) | 145s | 38s | ~183s |
| Session 2 (with facts) | 49s | 17s | ~66s |
