---
name: expand-cohort
description: Onboard new companies, apply known patterns, measure quality (inner loop). Run in worktrees for parallel cohorts.
---

# /expand-cohort — Inner Loop

Onboard new companies and get them to 80%+ EF-CQS using known patterns.

## Usage

```
/expand-cohort AAPL,MSFT,GOOG
/expand-cohort SP500-batch-3
```

## What it does

1. **ONBOARD** — Run `onboard_company()` for each ticker (resolve CIK, detect archetype, fetch yfinance snapshot, run orchestrator)
2. **MEASURE** — `compute_cqs()` on the cohort
3. **DIAGNOSE** — `identify_gaps()` to find unresolved metrics
4. **FIX** — Apply deterministic fixes: industry exclusions, known concepts, composite formulas
5. **VALIDATE** — Re-measure. Per-company gate: EF-CQS >= 0.80
6. **REPORT** — Write cohort report to `edgar/xbrl/standardization/cohort-reports/`

## Entry Point

```python
from edgar.xbrl.standardization.tools.expand_cohort import run_expand_cohort

report_path = run_expand_cohort(
    tickers=["HD", "LOW", "MCD"],
    cohort_name="retail-batch-1",
)
```

## Output

Markdown cohort report at `cohort-reports/cohort-YYYY-MM-DD-{name}.md` with:
- Company results table (ticker, EF-CQS, status, gaps)
- Fixes applied table
- Unresolved gaps table (for `/investigate-gaps`)

## Worktree Usage

Run in a worktree for parallel cohorts:
```
Agent(isolation: "worktree", prompt: "/expand-cohort HD,LOW,MCD")
```
