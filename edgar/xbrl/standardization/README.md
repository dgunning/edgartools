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
│   ├── auto_eval.py            CQS computation, gap analysis
│   ├── auto_eval_loop.py       Experiment loop, config changes, tournament eval
│   ├── auto_eval_dashboard.py  Morning review terminal dashboard
│   ├── discover_concepts.py    Search calc trees + facts for concept candidates
│   ├── verify_mapping.py       Value comparison against yfinance
│   ├── learn_mappings.py       Cross-company pattern discovery
│   ├── onboard_company.py      Automated single-company onboarding
│   ├── pipeline_orchestrator.py State machine for batch expansion
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

# Full 50-company evaluation
cqs = compute_cqs(eval_cohort=EXPANSION_COHORT_50, snapshot_mode=True)
print_cqs_report(cqs)

# Find gaps ranked by CQS impact
gaps, cqs = identify_gaps(snapshot_mode=True)
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
)
print_overnight_report(report)
```

### Tournament Evaluation

Prevents overfitting to the 5-company quick-eval cohort:

```
Proposal → Stage 1 (5 cos, ~3 min) → PASS? → Stage 2 (20 cos, ~10 min) → PASS? → KEEP
                                    → FAIL → DISCARD              → FAIL → DISCARD
```

### Proposal Pipeline

`propose_change()` tries three escalation levels:

1. **Structural detection** — if yfinance reference is `None`, add exclusion (company doesn't have this metric)
2. **Heuristic name variations** — try common XBRL concept name patterns (fast, no I/O)
3. **Concept discovery** — search the actual XBRL filing's calc trees and facts via `discover_concepts()`, then verify each candidate across **2-3 fiscal periods** to prevent false positives from coincidental single-period matches

### Dashboard

Morning review of overnight results:

```python
from edgar.xbrl.standardization.tools.auto_eval_dashboard import show_dashboard
show_dashboard()  # Rich terminal UI with experiment history, graveyard patterns, CQS trajectory
```

### Safety Invariants

1. **Regressions are a hard veto** — any regression caps CQS below baseline, no exceptions
2. **No single company drops >5pp** in pass_rate
3. **Circuit breaker** — 10 consecutive failures stops the session
4. **All changes are git-recoverable** — `git checkout` reverts any config
5. **Graveyard prevents loops** — metrics with 3+ failed attempts are skipped
6. **Multi-period verification** — discovered concepts must match across multiple fiscal years
