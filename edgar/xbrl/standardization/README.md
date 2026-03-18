# XBRL Standardization

Maps company-specific XBRL concepts to standardized metrics, enabling cross-company financial comparisons. Uses a multi-layer architecture (Tree Parser → Facts Search → AI Semantic) with validation against yfinance reference data.

## Directory Structure

```
standardization/
├── config/                     Tier 1 configuration (YAML)
│   ├── metrics.yaml            Metric definitions, known_concepts, tree_hints
│   ├── companies.yaml          Company-specific overrides, exclusions, divergences
│   ├── industry_metrics.yaml   Industry-specific concept mappings
│   ├── yf_snapshots/           Cached yfinance reference data
│   └── onboarding_reports/     Per-company onboarding results
├── layers/                     Multi-layer mapping engine
│   ├── tree_parser.py          Layer 1: Static calculation tree parsing
│   ├── facts_search.py         Layer 2: Static facts database search
│   └── ai_semantic.py          Layer 3: Dynamic AI semantic mapping
├── ledger/
│   └── schema.py               SQLite experiment ledger (extraction runs, golden masters, auto-eval)
├── tools/                      Reusable tools for agents and automation
│   ├── auto_eval.py            CQS computation, gap analysis, DEFAULT_MAX_WORKERS
│   ├── auto_eval_loop.py       Experiment loop, config changes, tournament eval, solver integration
│   ├── auto_eval_dashboard.py  Morning review terminal dashboard (EF/SA scores)
│   ├── auto_solver.py          Subset-sum search for yfinance composite formulas
│   ├── discover_concepts.py    Search calc trees + facts for concept candidates
│   ├── verify_mapping.py       Value comparison against yfinance
│   ├── learn_mappings.py       Cross-company pattern discovery
│   ├── onboard_company.py      Automated single-company onboarding
│   ├── pipeline_orchestrator.py State machine for batch expansion
│   ├── test_solver_integration.py  Integration test for solver pipeline
│   └── ...
├── orchestrator.py             Main multi-layer orchestrator
├── reference_validator.py      Validation against yfinance snapshots
├── models.py                   MappingResult, MappingSource, ConfidenceLevel
└── config_loader.py            YAML config loading
```

## Auto-Eval: Autonomous Quality Measurement

The auto-eval system applies the [autoresearch](https://x.com/kaboroevich/status/1928862789851525568) pattern to XBRL extraction quality. An autonomous agent modifies only YAML configuration files ("weights") while the evaluation harness (Orchestrator + ReferenceValidator + yf_snapshots) remains fixed. A single **Composite Quality Score (CQS)** drives all experiment decisions.

### Architecture

```
Gap Analysis → Propose Config Change → Apply → Measure CQS → Keep/Revert
                     ↑                                            |
                     └── Graveyard (skip after 3 failures) ←──────┘
```

**Key constraint**: the agent never touches the extraction engine (Python code). It only modifies Tier 1 configs:

| Config File | Contents |
|---|---|
| `config/metrics.yaml` | Metric definitions, known_concepts, tree_hints |
| `config/companies.yaml` | Company-specific overrides, exclusions, divergences |
| `config/industry_metrics.yaml` | Industry-specific concept mappings |

### Evaluation Cohorts

| Cohort | Size | Time | Purpose |
|---|---|---|---|
| `QUICK_EVAL_COHORT` | 5 companies (AAPL, JPM, XOM, WMT, JNJ) | ~50s | Fast iteration during development |
| `VALIDATION_COHORT` | 20 companies | ~200s | Tournament stage-2 validation |
| `EXPANSION_COHORT_50` | 50 companies across 8 sectors | ~270s | Full cross-sector quality measurement |

Current 50-company results: **CQS 0.9206**, 95.9% pass rate, 98.9% coverage, 0 regressions.

### CQS Formula

```python
if regression_rate > 0:
    return CQS_baseline - 0.01  # Hard veto — regressions always fail

cqs = (0.50 * pass_rate           # Fraction of metrics passing validation
     + 0.20 * (1 - variance/100)  # Lower variance is better
     + 0.15 * coverage_rate       # Fraction of metrics mapped
     + 0.10 * golden_master_rate  # Fraction with golden masters
     + 0.05 * (1 - regression_rate))
```

### Quick Start

```python
from edgar.xbrl.standardization.tools.auto_eval import (
    compute_cqs, identify_gaps, print_cqs_report, print_gap_report,
    QUICK_EVAL_COHORT, VALIDATION_COHORT, EXPANSION_COHORT_50,
)

# Measure current quality (defaults to 5-company quick eval)
cqs = compute_cqs(snapshot_mode=True)
print_cqs_report(cqs)
# Reports CQS, EF-CQS (Extraction Fidelity), SA-CQS (Standardization Alignment)

# Full 50-company evaluation with parallelism
cqs = compute_cqs(eval_cohort=EXPANSION_COHORT_50, snapshot_mode=True, max_workers=4)
print_cqs_report(cqs)

# Find gaps ranked by CQS impact
gaps, cqs = identify_gaps(snapshot_mode=True, max_workers=4)
print_gap_report(gaps)
```

### Running Experiments

Each experiment is a single config change, measured before and after:

```python
from edgar.xbrl.standardization.tools.auto_eval_loop import (
    ConfigChange, ChangeType, evaluate_experiment, log_experiment
)
from edgar.xbrl.standardization.ledger.schema import ExperimentLedger

ledger = ExperimentLedger()
baseline = compute_cqs(snapshot_mode=True, ledger=ledger)

change = ConfigChange(
    file="metrics.yaml",
    change_type=ChangeType.ADD_CONCEPT,
    yaml_path="metrics.COGS.known_concepts",
    new_value="CrudeOilAndProductPurchases",
    rationale="Energy sector COGS variant",
    target_metric="COGS",
    target_companies="XOM",
)

result = evaluate_experiment(change, baseline, ledger=ledger)
log_experiment(change, result, ledger)
# Decision: KEEP (CQS +0.003) or DISCARD/VETO
```

### Parallel Scouting

Scout gaps in parallel using ThreadPoolExecutor (no LLM calls):

```python
from edgar.xbrl.standardization.tools.auto_eval_loop import (
    parallel_scout_gaps, scout_result_to_change,
    select_non_conflicting, batch_evaluate,
)

# Scout top gaps in parallel
scout_results = parallel_scout_gaps(gaps[:20], max_workers=5)

# Convert to config changes and batch evaluate
proposals = [scout_result_to_change(r, g) for r, g in zip(scout_results, gaps[:20]) if r.has_proposal]
batch = select_non_conflicting([p for p in proposals if p])
result = batch_evaluate(batch, baseline_cqs=cqs)
```

### Overnight Loop

Run unattended for hours with built-in safety:

```python
from edgar.xbrl.standardization.tools.auto_eval_loop import run_overnight, propose_change
from edgar.xbrl.standardization.tools.auto_eval_dashboard import print_overnight_report

report = run_overnight(
    duration_hours=7.5,
    focus_area="banking",    # optional: limit scope
    use_tournament=True,     # 2-stage eval (5-co fast + 20-co validation)
    propose_fn=propose_change,
    max_workers=4,           # parallel company evaluation (2.2x speedup on 20 cos)
)
print_overnight_report(report)
# Report includes EF-CQS/SA-CQS trajectory and solver statistics
```

### Tournament Evaluation

Prevents overfitting to the 5-company quick-eval cohort:

```
Proposal → Stage 1 (5 cos, ~3 min) → PASS? → Stage 2 (20 cos, ~10 min) → PASS? → KEEP
                                    → FAIL → DISCARD              → FAIL → DISCARD
```

### Proposal Pipeline

`propose_change()` tries escalation levels in order:

1. **Structural detection** — if yfinance reference is `None`, add exclusion (company doesn't have this metric)
2. **Heuristic name variations** — try common XBRL concept name patterns (fast, no I/O)
3. **Concept discovery** — search the actual XBRL filing's calc trees and facts via `discover_concepts()`, then verify each candidate across **2-3 fiscal periods** to prevent false positives from coincidental single-period matches
4. **Auto-Solver** — for `high_variance` and `validation_failure` gaps (after first-line proposals are graveyarded), performs bounded subset-sum search over XBRL facts to discover composite formulas that match yfinance

### Auto-Solver

When standard proposals fail, the solver reverse-engineers yfinance's composite formulas:

```python
from edgar.xbrl.standardization.tools.auto_solver import AutoSolver

solver = AutoSolver(snapshot_mode=True)
candidates = solver.solve_metric("ABBV", "DepreciationAmortization")
# Returns FormulaCandidate(components=[...], variance_pct=0.3%)

# Cross-company validation
validation = solver.validate_formula(candidates[0], ["SLB", "GE", "HD"])

# Multi-period validation (checks last 3 annual filings)
mp = solver.validate_formula_multi_period(candidates[0], "ABBV", num_periods=3)
# mp["periods_passed"]=3, mp["periods_checked"]=3 → formula is stable
```

**Validation gates** (both must pass to write `ADD_STANDARDIZATION`):
1. **Multi-period**: formula holds for >=2 of last 3 annual filings (catches coincidental matches)
2. **Cross-company**: formula works for >=2 other companies (sector pattern) or company-specific override

When both gates pass, the solver writes `ADD_STANDARDIZATION` to metrics.yaml, which `_compute_sa_composite()` evaluates during validation to produce actual composite values.

### Dashboard

Morning review of overnight results:

```python
from edgar.xbrl.standardization.tools.auto_eval_dashboard import show_dashboard
show_dashboard()  # Rich terminal UI with CQS, EF-CQS, SA-CQS, experiment history, graveyard
```

The dashboard displays:
- **CQS** (composite), **EF-CQS** (extraction fidelity), **SA-CQS** (standardization alignment)
- **Explained Gaps** — variances with documented reasons
- Experiment history, graveyard patterns, golden master status

### Two-Score Architecture

CQS is the overall composite. Two sub-scores separate extraction quality from standardization understanding:

| Score | Measures | Tolerance |
|-------|----------|-----------|
| **EF-CQS** (Extraction Fidelity) | Did we find the right XBRL concept? | ~0% (concept correctness) |
| **SA-CQS** (Standardization Alignment) | Can we reproduce yfinance's aggregated number? | 5% (after composite formula) |

`_compute_sa_composite()` in `reference_validator.py` evaluates standardization formulas from config against XBRL data. When a metric has an `ADD_STANDARDIZATION` formula, SA scoring uses the composite value instead of the raw extraction.

### Parallelization

Company evaluation is parallelized via `ProcessPoolExecutor` (bypasses GIL for CPU-bound XBRL parsing). Each subprocess gets its own Orchestrator instance to avoid shared-state issues.

```python
# 2.2x speedup on 20 companies (147s → 67s), scores identical
cqs = compute_cqs(eval_cohort=VALIDATION_COHORT, snapshot_mode=True, max_workers=4)
```

Set `max_workers` on `compute_cqs()`, `identify_gaps()`, `run_overnight()`, or `Orchestrator.map_companies()`.

### Safety Invariants

1. **Regressions are a hard veto** — any regression caps CQS below baseline, no exceptions
2. **No single company drops >5pp** in pass_rate
3. **Circuit breaker** — 10 consecutive failures stops the session
4. **All changes are git-recoverable** — `git checkout` reverts any config
5. **Graveyard prevents loops** — metrics with 3+ failed attempts are skipped
6. **Multi-period verification** — discovered concepts and solver formulas must match across multiple fiscal years
7. **Solver candidate cap** — subset-sum search limited to 50 most relevant facts (prevents combinatorial explosion)
