# CQS Improvement Loop

The closed-loop workflow for autonomously improving XBRL extraction quality. This is the playbook an AI agent follows — overnight or in guided sessions — to systematically drive CQS toward subscription-grade.

## The Loop

```
MEASURE → DIAGNOSE → PRIORITIZE → FIX → VALIDATE → RECORD → loop
```

Each iteration: measure where we are, understand why gaps exist, fix the highest-impact ones safely, confirm improvement, and log everything for the next session.

## Phase 1: MEASURE

Establish ground truth before changing anything.

```python
from edgar.xbrl.standardization.tools.auto_eval import (
    compute_cqs, identify_gaps, EXPANSION_COHORT_100
)

baseline = compute_cqs(
    eval_cohort=EXPANSION_COHORT_100,
    snapshot_mode=True,
    max_workers=4
)
```

Record: CQS, pass_rate, regressions, worst-company score, per-company breakdown.

**Rule**: Never skip this step. The baseline is the rollback target if things go wrong.

## Phase 2: DIAGNOSE

Run gap analysis and classify each gap by root cause.

```python
gaps, cqs = identify_gaps(
    eval_cohort=EXPANSION_COHORT_100,
    snapshot_mode=True,
    max_workers=4
)
```

### Root Cause Taxonomy

Each gap has a root cause that determines the fix strategy. The existing `gap_type` and `hv_subtype` fields provide the detection signal, but the agent must think about *why* a gap exists, not just *what* type it is.

| Root Cause | Detection Signal | Fix Tier | Automated? |
|---|---|---|---|
| **Missing concept** | gap_type=unmapped, ref_value exists | 1A | Yes |
| **Wrong concept** | gap_type=validation_failure | 1A | Yes |
| **Industry-structural** | gap_type=unmapped, ref_value=None | 1A | Yes |
| **Extension concept** | unmapped, company uses non-standard taxonomy | 1B | Yes (company-scoped only) |
| **Partial composite** | hv_subtype=hv_missing_component | 1B | Yes (with multi-period validation) |
| **Sign/negation error** | value matches magnitude but wrong sign | 1B | Yes (known sign conventions) |
| **Scale/unit mismatch** | variance is ~1000x or ~1000000x | 2 | Needs investigation |
| **Reference data error** | yfinance value is wrong/stale | 2 | Needs human verification |
| **Period mismatch** | value extracted from wrong fiscal period | 3 | Needs Python fix |
| **Sector-specific logic** | banking/REIT/utility needs custom extraction | 3 | Needs Python fix |
| **Amended filing** | 10-K/A with missing/corrupt XBRL data | 3 | Needs Python fix |
| **Parser coverage** | fact exists in filing but parser missed it | 3 | Needs Python fix |

**Key insight**: At CQS > 0.97, most remaining gaps are hard edge cases. Simple config fixes are largely exhausted. The diagnosis step prevents wasting cycles on gaps that config can't solve.

## Phase 3: PRIORITIZE

Build an impact-ranked fix queue.

```
Sort by: estimated_impact DESC, graveyard_count ASC, fix_tier ASC
Filter out: graveyard dead-ends (count >= 6), explained variances
Group by: fix tier (1A first, then 1B, then 2, then 3)
```

**For overnight runs**: Process only Tier 1A and 1B gaps. Collect Tier 2-3 gaps into a report for the next human session.

**Magnitude matters**: Prioritize large monetary variances (factor-of-1000 misses indicate structural failures) over small percentage variances. A $50B miss on TotalAssets matters more than a 2% miss on SGA.

## Phase 4: FIX

### Tier 1A — Additive Mappings (safe, unattended)

These add information without removing or suppressing anything:

| Change Type | What It Does | Acceptance Gate |
|---|---|---|
| ADD_CONCEPT | Add known_concept to metrics.yaml | CQS non-negative, no regressions |
| SET_INDUSTRY | Map company to industry via SIC | CQS non-negative, no regressions |
| ADD_COMPANY_OVERRIDE | Add concept to {ticker}_mappings.json | Target company improves, no global regression |

**Validation strategy**: Test on target company first. If it passes, add to candidate batch. Run global CQS once per batch (10-20 candidates) to check cross-company regressions.

```python
# Local-first validation (fast)
local_cqs = compute_cqs(eval_cohort=[gap.ticker], snapshot_mode=True)
if local_cqs.pass_rate > baseline_company_pass_rate:
    candidate_batch.append(change)

# Batch validation (periodic)
if len(candidate_batch) >= 10:
    apply_all(candidate_batch)
    batch_cqs = compute_cqs(eval_cohort=EXPANSION_COHORT_100, ...)
    if batch_cqs.cqs >= baseline.cqs and batch_cqs.regressions == 0:
        commit_batch()
    else:
        revert_batch()
        # bisect to find the problematic change
```

### Tier 1B — Score-Sensitive Changes (unattended, stricter gate)

These can inflate CQS by suppressing signal rather than improving extraction:

| Change Type | What It Does | Acceptance Gate |
|---|---|---|
| ADD_EXCLUSION | Exclude metric for company/industry | CQS improves AND ref_value is None |
| ADD_KNOWN_VARIANCE | Document explained variance | Human-verified reason required |
| ADD_STANDARDIZATION | Add solver composite formula | Multi-period validated (2/3 filings) AND cross-company (2+ companies) |

**Stricter rules**:
- Reject if CQS gain comes primarily from exclusions/waivers
- Reject if improvement concentrated in one ticker but harms cohort median
- Extension concepts must be company-scoped (`{ticker}_mappings.json`) unless validated across 3+ companies

### Tier 2 — Investigation Required (AI-guided, not fully automated)

- Composite metric definition (marking `composite: true`, defining components)
- Subcomponent patterns (new entries in `_defaults.json` subcomponents)
- Scale/unit investigation
- Reference data verification (is yfinance wrong?)

**Output**: A structured investigation report for human review, or a Tier 1 fix if investigation resolves to a known pattern.

### Tier 3 — Python Changes (human review required)

- New extraction logic in reference_validator.py
- Industry-specific extractors
- Period selection fixes
- Architectural changes

**Output**: A detailed plan document with proposed code changes, test strategy, and expected impact.

## Phase 5: VALIDATE

After applying fixes, measure the actual improvement.

```python
new_cqs = compute_cqs(
    eval_cohort=EXPANSION_COHORT_100,
    snapshot_mode=True,
    max_workers=4,
    baseline_cqs=baseline.cqs  # enables regression detection
)
```

### Metrics to Compare

| Metric | What It Tells You |
|---|---|
| CQS delta | Overall improvement |
| Pass rate delta | Are more metrics passing? |
| Regression count | Did we break anything? |
| Worst-company CQS | Is the floor rising? (more important than average) |
| Sector balance | Did we improve one sector at the expense of another? |
| Diagnosis mix | Are we burning down config issues and surfacing architectural ones? |

### Regression Investigation

If regressions increased, investigate each one before proceeding:

1. Identify which (ticker, metric) regressed
2. Check if the regression is caused by this session's changes (revert and test)
3. If caused by our change: revert that specific fix
4. If pre-existing: document as known issue, do not block the session

## Phase 6: RECORD

Log everything for future sessions.

```python
# Already handled by evaluate_experiment() and log_experiment()
# Additional session-level recording:
```

### Session Summary (persisted to session_state.json)

```json
{
  "session_id": "2026-03-20-overnight",
  "baseline_cqs": 0.9709,
  "final_cqs": 0.9745,
  "experiments_total": 15,
  "experiments_kept": 8,
  "experiments_discarded": 5,
  "experiments_vetoed": 2,
  "regressions_found": 1,
  "regressions_resolved": 1,
  "tier1_gaps_remaining": 3,
  "tier2_gaps_remaining": 7,
  "tier3_gaps_remaining": 12,
  "worst_company": {"ticker": "D", "cqs": 0.777},
  "git_commit_baseline": "bb057ba8",
  "git_commit_final": "abc123de",
  "next_session_focus": "Investigate D (utility), PLD (REIT), VZ (telecom) structural gaps"
}
```

### What Gets Persisted Where

| Data | Storage | Purpose |
|---|---|---|
| Experiment results | ExperimentLedger (SQLite) | Track what was tried, kept, discarded |
| Failed attempts | Graveyard (SQLite) | Prevent re-trying the same fix |
| Stable extractions | Golden Masters (SQLite) | Regression detection |
| Session state | session_state.json | Resume after crash, cross-session learning |
| Config changes | Git commits | Rollback, audit trail |

## Loop Control

### Continue If
- CQS < automated ceiling (0.985) AND
- Tier 1A/1B gaps remain AND
- No circuit breaker triggered AND
- Within budget (max experiments, max wall-clock)

### Pause for Human If
- Only Tier 2-3 gaps remain
- 10 consecutive discards/vetoes across different metrics
- Marginal gain per accepted change drops below 0.0005 for 5 consecutive accepts
- CQS reaches automated ceiling (~0.985) — remaining improvement needs human-curated golden masters

### Stop If
- CQS >= target
- All gaps exhausted or graveyarded
- Budget exceeded (max experiments or max wall-clock)
- CQS drops below baseline for 2 consecutive batch validations (something is wrong)

### The yfinance Ceiling

yfinance is our reference benchmark, but it has errors — especially in complex composites, banking metrics, and edge cases. The automated loop should target ~0.985 against yfinance. The push from 0.985 to 0.995+ requires human-curated golden masters where we verify the *correct* value independently, not just match what yfinance reports.

## Session Persistence

The agent's context window will be exhausted during overnight runs. All state must live outside the context:

### session_state.json

Written after every batch validation. If the agent crashes and restarts:
1. Read session_state.json
2. Check git log for last committed batch
3. If uncommitted changes exist, revert to last known-good commit
4. Resume from the recorded gap queue position

### Recovery Protocol

```
1. Read session_state.json → last known state
2. git log --oneline -5 → verify commit matches recorded state
3. If mismatch: git reset --hard {git_commit_baseline}
4. compute_cqs() → re-establish baseline
5. Resume from gap queue
```

## Implementation Status

### What Exists Today

| Component | Status | Location |
|---|---|---|
| CQS computation | Done | auto_eval.py: compute_cqs() |
| Gap identification | Done | auto_eval.py: identify_gaps() |
| Gap classification (basic) | Done | auto_eval.py: _classify_gap() |
| Proposal generation | Done | auto_eval_loop.py: propose_change() |
| Experiment evaluation | Done | auto_eval_loop.py: evaluate_experiment() |
| Graveyard | Done | schema.py: auto_eval_graveyard |
| Golden masters | Done | schema.py: golden_masters |
| Local-first validation | Partial | auto_eval.py: compute_cqs_incremental() exists but not integrated into loop |
| Batch validation | Partial | auto_eval.py: compute_cqs_incremental_batch() exists |
| Config-driven composite | Done | reference_validator.py: _is_composite_metric() |
| Subcomponent extraction | Done | extraction_rules.py: get_subcomponents() |
| AutoSolver | Done | auto_solver.py |

### What Needs to Be Built

| Component | Priority | Description |
|---|---|---|
| **Session state persistence** | P0 | session_state.json read/write, crash recovery protocol |
| **Root cause classifier** | P0 | Expand _classify_gap() with sign/scale/reference/parser detection |
| **Batch fix pipeline** | P1 | Local-first → batch → global validation flow |
| **Tier-aware proposal routing** | P1 | Route gaps to Tier 1A/1B/2/3 based on root cause |
| **Distribution metrics** | P1 | Worst-company floor, sector balance, magnitude-of-miss tracking |
| **Regression investigation** | P2 | Per-regression root cause analysis and auto-revert |
| **Session summary generator** | P2 | Write session_state.json with next-session recommendations |
| **Marginal gain tracker** | P2 | Track gain-per-change to detect diminishing returns |
| **Graveyard semantic clustering** | P3 | Prevent structurally identical re-proposals |

## Example: One Iteration

```
Session start: CQS = 0.9709

MEASURE: compute_cqs() → 0.9709, 8 regressions, worst = D at 0.777
DIAGNOSE: identify_gaps() → 31 gaps
  - 4 missing concept (Tier 1A)
  - 3 industry-structural (Tier 1A)
  - 5 partial composite (Tier 1B)
  - 2 extension concept (Tier 1B, company-scoped)
  - 4 wrong concept (Tier 1A)
  - 5 period mismatch (Tier 3, skip)
  - 8 sector-specific (Tier 3, skip)

PRIORITIZE: 18 Tier 1 gaps, sorted by impact
FIX: Process 18 gaps in batches of 10
  Batch 1: 10 proposals → 7 pass local validation → apply batch
    → global CQS: 0.9735, 0 new regressions → KEEP
  Batch 2: 8 proposals → 5 pass local validation → apply batch
    → global CQS: 0.9748, 1 new regression → investigate
    → regression caused by concept collision → revert 1 change
    → global CQS: 0.9745 → KEEP

VALIDATE: CQS 0.9709 → 0.9745 (+0.0036)
RECORD: 12 kept, 4 discarded, 2 vetoed
  Remaining: 13 Tier 2-3 gaps → pause for human

Session end: CQS = 0.9745
```

## History

| Date | CQS | Delta | Method | Key Changes |
|---|---|---|---|---|
| 2026-03-19 | 0.9652 | — | Team eval (5 agents, 100 companies) | Baseline measurement |
| 2026-03-20 | 0.9709 | +0.0057 | Tier 3 Python fixes | Composite routing, IntangibleAssets subcomponents, D&A composite, industry exclusions |
