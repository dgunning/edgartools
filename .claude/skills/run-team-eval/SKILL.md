---
name: run-team-eval
description: "Run the agent team auto-eval for large-scale (100+) company evaluation. Use when the user says 'run team eval', 'team auto-eval', 'scale auto-eval', or wants to launch multiple runner/evaluator agents."
---

# Run Team Auto-Eval

## Overview

The team-based auto-eval scales the single-agent `run-auto-eval` workflow to 100+ companies by splitting work across multiple parallel agents. The **team lead** (user) initializes a session, dispatches worker agents, monitors via checkpoints, and validates results.

## When to Use

- User says "run team eval" or "team auto-eval"
- User says "scale auto-eval to 100 companies"
- User wants to launch multiple runner/evaluator agents
- User says "agent team evaluation"

## Architecture

```
Team Lead (user)
  |
  +-- TeamSession.establish_baseline()     # Full-cohort baseline
  |
  +-- TeamSession.get_worker_assignments() # Dynamic sub-cohorts
  |
  +-- Launch N agents (via Agent tool)     # Each runs propose_and_evaluate_loop()
  |
  +-- print_team_dashboard()               # Monitor checkpoints anytime
  |
  +-- TeamSession.collect_results()        # Gather worker outputs
  |
  +-- TeamSession.validate_winners()       # Full-cohort validation
```

## Team Lead Workflow

### Step 1: Initialize Session

```python
from edgar.xbrl.standardization.tools.auto_eval_loop import TeamSession
from edgar.xbrl.standardization.tools.auto_eval import EXPANSION_COHORT_100

# Create session with 5 workers across 100 companies
session = TeamSession(eval_cohort=EXPANSION_COHORT_100, num_workers=5)
session.establish_baseline(max_workers=4)
assignments = session.get_worker_assignments()
```

### Step 2: Dispatch Workers

Launch each worker as an `auto-eval-runner` agent:

```python
# Each assignment dict contains:
# {
#     "worker_id": "worker_A",
#     "eval_cohort": ["AAPL", "MSFT", ...],  # ~20 companies
#     "cohort_size": 20,
#     "role": "combined",
# }

# Worker runs:
from edgar.xbrl.standardization.tools.auto_eval_loop import propose_and_evaluate_loop
evaluated = propose_and_evaluate_loop(
    eval_cohort=assignment["eval_cohort"],
    worker_id=assignment["worker_id"],
    max_workers=2,
    checkpoint_interval=1,
    role="combined",
)
```

### Step 3: Monitor

```python
from edgar.xbrl.standardization.tools.auto_eval_checkpoint import print_team_dashboard
print_team_dashboard()
```

Dashboard shows:
```
Worker       Role       Phase        Cohort  Gaps   K/D/V       CQS  Elapsed  Current Gap
worker_A     combined   eval_5           20    12   3/2/0    0.9812     120s  AAPL:IntangibleAssets
worker_B     combined   eval_3           20    10   1/2/0    0.9798      95s  JPM:CashAndEquivalents
...
```

### Step 4: Collect and Validate

```python
results = session.collect_results()
report = session.validate_winners(results)
```

## Role Modes

| Role | What It Does | When to Use |
|------|-------------|-------------|
| `"combined"` (default) | Proposes AND evaluates on sub-cohort | Standard mode |
| `"runner"` | Proposes changes only | When you have dedicated evaluators |
| `"evaluator"` | Evaluates pre-built proposals | When paired with runners |

### Runner + Evaluator Separation

```python
# Runners generate proposals
from edgar.xbrl.standardization.tools.auto_eval_loop import propose_only_loop, save_proposals_to_json
proposals = propose_only_loop(eval_cohort=subcohort, worker_id="runner_A")
save_proposals_to_json(proposals, output_path)

# Evaluators evaluate proposals
from edgar.xbrl.standardization.tools.auto_eval_loop import evaluate_proposals_in_memory
results = evaluate_proposals_in_memory(
    proposals=proposals,
    eval_cohort=eval_cohort,
    baseline_config=baseline_config,
    baseline_cqs=baseline_cqs,
    worker_id="evaluator_A",
)
```

## Dynamic Sub-Cohorts

```python
from edgar.xbrl.standardization.tools.auto_eval import generate_subcohorts

# Split any N companies into K balanced sub-cohorts
subcohorts = generate_subcohorts(tickers=EXPANSION_COHORT_100, k=5)
# Each subcohort has ~20 companies with sector diversity
```

Balancing criteria:
1. Sector diversity (round-robin by industry)
2. Hard gaps distributed evenly (using graveyard counts)
3. Roughly equal size (max diff = 1)

## Cohorts

| Cohort | Size | Purpose |
|--------|------|---------|
| `QUICK_EVAL_COHORT` | 5 | Fast iteration |
| `VALIDATION_COHORT` | 20 | Tournament 2nd stage |
| `EXPANSION_COHORT_50` | 50 | Full stress test |
| `EXPANSION_COHORT_100` | 100 | Production-scale team eval |

## Timing Expectations

| Operation | 50 companies | 100 companies |
|-----------|-------------|---------------|
| Baseline CQS (4 workers) | ~5 min | ~10 min |
| Gap identification | ~5 min | ~10 min |
| Per-proposal eval | ~2-5 min | ~3-7 min |
| Full session (30 gaps) | ~3 hours | ~5 hours |
| With 5 team workers | ~45 min | ~1.5 hours |

## Concurrency Safety

| Component | Multiple Workers | Coordinator |
|-----------|-----------------|-------------|
| Config (in-memory) | Safe (deepcopy) | Safe (single writer) |
| Config (disk YAML) | Never writes | ConfigLock serializes |
| SQLite ledger reads | Safe (WAL) | Safe |
| SQLite ledger writes | Never writes | Single writer only |
| Checkpoint files | Per-worker file | Read-only |

## File Locations

```
auto_eval.py         -- EXPANSION_COHORT_100, generate_subcohorts(), TimingBreakdown
auto_eval_loop.py    -- TeamSession, evaluate_proposals_in_memory(), EvaluatedProposal.from_dict()
auto_eval_checkpoint.py -- WorkerCheckpoint, write_checkpoint(), print_team_dashboard()
```
