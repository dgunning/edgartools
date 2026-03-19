---
name: run-auto-eval
description: "Run the auto-eval loop to autonomously improve XBRL extraction quality through config-only changes. Use when the user says 'run auto-eval', 'overnight eval', 'improve CQS', or 'auto-eval dashboard'."
---

# Run Auto-Eval

## Overview

This skill runs the autonomous evaluation loop that improves XBRL extraction quality by modifying only YAML configuration files. It applies the autoresearch pattern: the agent modifies "weights" (configs) while the eval harness (Orchestrator + ReferenceValidator + yf_snapshots) is fixed.

## When to Use

- User says "run auto-eval" or "start auto-eval"
- User says "run overnight evaluation"
- User says "improve CQS" or "optimize extraction"
- User says "show auto-eval dashboard" or "morning review"
- User says "what's the current CQS?"

## Commands

### Check Current Quality (CQS)

```python
from edgar.xbrl.standardization.tools.auto_eval import compute_cqs, print_cqs_report, QUICK_EVAL_COHORT

# Quick CQS measurement (5 companies, ~60s)
cqs = compute_cqs(eval_cohort=QUICK_EVAL_COHORT, snapshot_mode=True)
print_cqs_report(cqs)
```

### Identify Gaps

```python
from edgar.xbrl.standardization.tools.auto_eval import identify_gaps, print_gap_report

gaps, cqs = identify_gaps(snapshot_mode=True)
print_gap_report(gaps)
```

### Show Dashboard

```python
from edgar.xbrl.standardization.tools.auto_eval_dashboard import show_dashboard
show_dashboard()
```

### Run Experiments (Interactive)

```python
from edgar.xbrl.standardization.tools.auto_eval_loop import (
    evaluate_experiment, ConfigChange, ChangeType, log_experiment, Decision
)
from edgar.xbrl.standardization.tools.auto_eval import compute_cqs
from edgar.xbrl.standardization.ledger.schema import ExperimentLedger

ledger = ExperimentLedger()
baseline = compute_cqs(snapshot_mode=True, ledger=ledger)

# Propose a change
change = ConfigChange(
    file="metrics.yaml",
    change_type=ChangeType.ADD_CONCEPT,
    yaml_path="metrics.SomeMetric.known_concepts",
    new_value="SomeXBRLConcept",
    rationale="Discovered via calc tree analysis",
    target_metric="SomeMetric",
    target_companies="AAPL",
)

# Evaluate it
result = evaluate_experiment(change, baseline, ledger=ledger)
log_experiment(change, result, ledger)
print(f"Decision: {result.decision.value} — {result.reason}")
```

### Run Overnight Session

```python
from edgar.xbrl.standardization.tools.auto_eval_loop import run_overnight, propose_change
from edgar.xbrl.standardization.tools.auto_eval_dashboard import print_overnight_report

# With deterministic proposals (no AI)
report = run_overnight(
    duration_hours=7.5,
    focus_area=None,        # or "banking", "add_concept", specific metric
    use_tournament=True,    # 2-stage eval for overfitting protection
    dry_run=False,          # Set True to preview without applying
    propose_fn=propose_change,
)
print_overnight_report(report)
```

### Run on Large Cohort (50 companies) with GPT Escalation

```python
from edgar.xbrl.standardization.tools.auto_eval_loop import run_overnight, make_escalation_propose_fn
from edgar.xbrl.standardization.tools.auto_eval import EXPANSION_COHORT_50
from edgar.xbrl.standardization.tools.auto_eval_dashboard import print_overnight_report

report = run_overnight(
    duration_hours=24,
    eval_cohort=EXPANSION_COHORT_50,  # 50 companies across 7 sectors
    propose_fn=make_escalation_propose_fn(escalation_threshold=3),
    max_workers=1,
)
print_overnight_report(report)
```

When `eval_cohort` has >=20 companies, tournament mode is auto-disabled (direct eval on the full cohort is sufficient to prevent overfitting).

### Dry Run (Preview Only)

```python
report = run_overnight(duration_hours=1, dry_run=True, propose_fn=propose_change)
print_overnight_report(report)
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `duration_hours` | 7.5 | How long to run |
| `focus_area` | None | Filter: "banking", "add_concept", metric name, etc. |
| `use_tournament` | True | 2-stage eval (5-co fast + 20-co validation). Auto-disabled for cohorts >=20 |
| `dry_run` | False | Preview proposals without applying |
| `snapshot_mode` | True | Use cached yfinance data |
| `eval_cohort` | QUICK_EVAL_COHORT | List of tickers to evaluate. Use EXPANSION_COHORT_50 for broad coverage |
| `escalation_threshold` | 3 | Subtype failures before GPT-5.4 escalation |
| `propose_fn` | None | Proposal function. Use `propose_change` (deterministic) or `make_escalation_propose_fn()` (with GPT escalation) |

## Focus Areas

Schedule nightly focus to prevent wandering:

- **Mon**: Tech archetype (`focus_area="tech"`)
- **Tue**: Healthcare (`focus_area="healthcare"`)
- **Wed**: Financial (`focus_area="banking"`)
- **Thu**: Energy (`focus_area="energy"`)
- **Fri**: Consumer staples (`focus_area="consumer"`)

## Safety Invariants

1. Only Tier 1 configs are modified (metrics.yaml, companies.yaml, industry_metrics.yaml)
2. Regressions are a hard veto — CQS capped below baseline
3. No single company pass_rate drops >5 percentage points
4. Circuit breaker: 10 consecutive failures stops the session
5. All changes are git-recoverable (`git checkout`)

## Key Files

```
edgar/xbrl/standardization/tools/auto_eval.py           — CQS computation, gap analysis
edgar/xbrl/standardization/tools/auto_eval_loop.py       — Experiment loop, config changes
edgar/xbrl/standardization/tools/auto_eval_dashboard.py   — Morning review dashboard
edgar/xbrl/standardization/ledger/schema.py               — AutoEvalExperiment, Graveyard tables
.claude/agents/auto-eval-runner.md                         — Autonomous agent definition
```
