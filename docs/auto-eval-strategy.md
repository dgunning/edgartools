# Auto-Eval Strategy: Applying Autoresearch Ethos to EdgarTools

*Strategy Report — March 2026*

---

## 1. The Analogy — Mapping Autoresearch to EdgarTools

Karpathy's [autoresearch](https://github.com/karpathy/autoresearch) project demonstrates a powerful pattern: give an AI agent a single file to modify (`train.py`), a single eval metric (`val_bpb`), and a fixed time budget (5 min) — then let it run 100+ experiments overnight. Humans edit the "research org code" (`program.md`); agents execute tactical experiments.

EdgarTools' XBRL concept-mapping pipeline has a structurally identical shape. The extraction pipeline (`Orchestrator` in `edgar/xbrl/standardization/orchestrator.py`) maps XBRL concepts to standardized metrics, validates against yfinance reference data, and tracks results in an experiment ledger. The configuration files are the "weights" that determine extraction quality. The question is: can we close the loop and let agents optimize those configurations autonomously?

### The Complete Mapping

| Autoresearch Concept | EdgarTools Equivalent | Location | Status |
|---|---|---|---|
| `val_bpb` (single eval metric) | **CQS** (Composite Quality Score) — weighted blend of pass_rate, mean_variance, coverage, golden_master_rate, regression_rate | Needs building (~50 lines) | **New** |
| `train.py` (single modifiable file) | **metrics.yaml** + **companies.yaml** + **industry_metrics.yaml** (Tier 1 config) | `standardization/config/` | Exists |
| `program.md` (agent instructions) | **CLAUDE.md** + `.claude/agents/*.md` + `.claude/skills/*/SKILL.md` | Root + `.claude/` | Exists |
| 5-min time budget per experiment | **Quick eval tier**: 5 representative companies, snapshot mode, ~3 min | Needs building | **New** |
| `prepare.py` (fixed eval harness) | **Orchestrator** + **ReferenceValidator** + **yf_snapshots/** (96 frozen JSONs) | `standardization/` | Exists |
| Experiment log (`runs.jsonl`) | **ExperimentLedger** (`ledger/schema.py`) with `PipelineRun`, `ExtractionRun` tables | `standardization/ledger/` | Exists |
| Overnight autonomy (100 experiments) | **auto_eval_loop** with cron, graveyard, morning dashboard | Needs building | **New** |
| Experiment comparison & selection | **ExperimentLedger** + 2 new tables (`auto_eval_experiments`, `auto_eval_graveyard`) | `standardization/ledger/` | Partially exists |

**Key structural parallel:** In autoresearch, the agent never touches `prepare.py` (the eval harness) — it only modifies `train.py` (the model code). Similarly, our auto-eval agent never touches the Orchestrator or ReferenceValidator Python code — it only modifies Tier 1 YAML configs. This constraint is what makes overnight autonomy safe.

---

## 2. The Composite Quality Score (CQS)

The CQS collapses multiple quality dimensions into a single float in [0, 1], higher is better — directly analogous to autoresearch's `val_bpb`.

### Formula

```
CQS = 0.50 * pass_rate
    + 0.20 * (1 - mean_variance / 100)
    + 0.15 * coverage_rate
    + 0.10 * golden_master_rate
    + 0.05 * (1 - regression_rate)
```

### Sub-Metric Definitions

| Sub-Metric | Source | Computation |
|---|---|---|
| `pass_rate` | `OnboardingResult.pass_rate` (`onboard_company.py:91-96`) | `len(metrics_passed) / (len(metrics_passed) + len(metrics_failed))` |
| `mean_variance` | `ReferenceValidator` validation results | Average `variance_pct` across all validated metrics (capped at 100%) |
| `coverage_rate` | `RunStatistics.adjusted_coverage_pct` (`kpi_tracker.py:38`) | `mapped_metrics / (total_metrics - excluded_metrics)` |
| `golden_master_rate` | `ExperimentLedger.get_all_golden_masters()` | `golden_masters_held / total_golden_masters` (fraction of golden masters that still pass) |
| `regression_rate` | Cohort test results (`CohortTestResult` in `ledger/schema.py`) | Fraction of previously-passing metrics that now fail |

### Weight Rationale

| Weight | Sub-Metric | Rationale |
|---|---|---|
| **0.50** | pass_rate | Dominates, matching autoresearch's single-metric focus. A config that breaks pass_rate is immediately penalized regardless of other improvements. |
| **0.20** | mean_variance | Rewards precision. Two configs with 95% pass_rate differ meaningfully if one has 2% mean variance vs 12%. |
| **0.15** | coverage_rate | Rewards breadth. Incentivizes resolving structural gaps (58% of all gaps per concept-mapping-resolver findings at `.claude/agents/concept-mapping-resolver.md:717-788`). |
| **0.10** | golden_master_rate | Protects verified configurations. Golden masters are metrics validated across 3+ periods — regressions here are high-signal. |
| **0.05** | regression_rate | Penalty term. Small weight because regressions are rare when Tier 1 changes are scoped correctly, but catastrophic when they happen. Acts as a circuit breaker. |

### Validation Against Known Quality Levels

Using current E2E results from `docs/financial-database-status.md:96-99`:

**Banking cohort (100% pass rate, ~0% variance, full coverage):**
```
CQS = 0.50 * 1.00 + 0.20 * (1 - 0.00) + 0.15 * 1.00 + 0.10 * 1.00 + 0.05 * (1 - 0.00)
    = 0.50 + 0.20 + 0.15 + 0.10 + 0.05
    = 1.00
```

**Standard Industrial (95.6% pass rate, ~5% mean variance, 96% coverage):**
```
CQS = 0.50 * 0.956 + 0.20 * (1 - 0.05) + 0.15 * 0.96 + 0.10 * 0.95 + 0.05 * (1 - 0.02)
    = 0.478 + 0.190 + 0.144 + 0.095 + 0.049
    = 0.956
```

**New company at onboarding (86.4% pass rate, ~10% mean variance, 86% coverage, no golden masters):**
```
CQS = 0.50 * 0.864 + 0.20 * (1 - 0.10) + 0.15 * 0.86 + 0.10 * 0.00 + 0.05 * (1 - 0.00)
    = 0.432 + 0.180 + 0.129 + 0.000 + 0.050
    = 0.791
```

These values match intuition: banking is perfect, industrial is excellent, new companies need work.

### Implementation

```python
# standardization/tools/auto_eval.py

from dataclasses import dataclass
from typing import List, Dict

@dataclass
class CQSResult:
    """Composite Quality Score with component breakdown."""
    cqs: float
    pass_rate: float
    mean_variance: float
    coverage_rate: float
    golden_master_rate: float
    regression_rate: float
    company_scores: Dict[str, float]  # per-company CQS for drill-down

def compute_cqs(
    eval_cohort: List[str],
    snapshot_mode: bool = True,
    check_golden_masters: bool = True,
) -> CQSResult:
    """
    Compute CQS across an eval cohort.

    Uses existing infrastructure:
    - Orchestrator.map_companies() for extraction
    - ReferenceValidator for validation
    - ExperimentLedger for golden master checks

    Args:
        eval_cohort: List of tickers to evaluate
        snapshot_mode: Use frozen yf_snapshots (True) or live yfinance (False)
        check_golden_masters: Whether to verify golden master stability
    """
    # 1. Run orchestrator on cohort (reuses Orchestrator.map_companies)
    # 2. Collect ValidationResults from ReferenceValidator
    # 3. Query ExperimentLedger for golden master status
    # 4. Compute weighted CQS
    ...
```

---

## 3. The Modification Surface (What Agents Can Touch)

The safety of overnight autonomy depends on strictly bounding what agents can modify. We define three tiers, directly analogous to autoresearch's rule that agents modify `train.py` but never `prepare.py`.

### Tier 1 — Safe for Autonomous Modification (the "train.py")

These files are pure configuration. Mistakes are always recoverable via `git checkout`. Changes affect extraction behavior but cannot break the extraction engine itself.

| File | Location | What Agents Modify | Example Change |
|---|---|---|---|
| `metrics.yaml` | `standardization/config/metrics.yaml` | `known_concepts`, `tree_hints`, `exclude_patterns`, `composites` | Add `NetSalesOfProductsAndServices` to Revenue's known_concepts list |
| `companies.yaml` | `standardization/config/companies.yaml` | `known_divergences`, `exclude_metrics`, `metric_overrides` | Add `ShortTermDebt` to JPM's known_divergences with variance justification |
| `industry_metrics.yaml` | `standardization/config/industry_metrics.yaml` | Sector-specific concept lists, archetype strategies | Add insurance-specific `PremiumsWrittenNet` to Revenue alternatives |

**Why these are safe:** The Orchestrator (`orchestrator.py:108-140`) reads these configs at runtime. A bad config entry (e.g., a misspelled concept name) results in a failed mapping — it never crashes the pipeline or corrupts data. The ReferenceValidator (`reference_validator.py`) independently validates all extractions against yfinance, so a bad concept mapping is caught immediately.

**Format reference** (from `metrics.yaml:8-29`):
```yaml
Revenue:
  description: "Total revenue from operations"
  standard_tag: "Revenue"
  known_concepts:
    - Revenues                    # Parent total first
    - RevenueFromContractWithCustomerExcludingAssessedTax  # ASC 606
    - SalesRevenueNet
    - Revenue
  tree_hints:
    statements: [INCOME, OPERATIONS]
    parent_pattern: OperatingIncome
    weight: 1.0
  universal: true
```

### Tier 2 — Requires Cohort Validation

| File | Location | Risk | Gate |
|---|---|---|---|
| `company_mappings/*.json` | `standardization/company_mappings/` | Per-company extraction rules; changes affect only one company but may mask underlying config issues | CQS must improve AND cohort regression test passes |

### Tier 3 — Human Review Required

| File | Location | Risk |
|---|---|---|
| Python source in `standardization/` | `orchestrator.py`, `reference_validator.py`, `tree_parser.py`, etc. | Extraction engine logic; bugs affect all companies |
| Agent instructions | `.claude/agents/*.md` | Agent behavior changes; tested via task batteries (Section 5) |

**Decision record — Why Tier 1 only for overnight autonomy:**
The concept-mapping-resolver agent's real-world testing (`.claude/agents/concept-mapping-resolver.md:717-788`) showed that of 57 gaps across 10 S&P 500 companies, 58% were structural (addressable via config), 26% were validation failures (addressable via known_divergences), and only 16% were true unmapped (potentially requiring code changes). This means **84% of gaps are solvable within Tier 1 alone** — sufficient for meaningful overnight progress without code risk.

---

## 4. The Auto-Eval Loop

### Eval Cohort Definition

The quick-eval cohort uses 5 companies, one per accounting archetype, matching the pipeline's archetype system (`pipeline_orchestrator.py:103-143`):

| Company | Ticker | Archetype | Why This Company |
|---|---|---|---|
| Apple | AAPL | Standard (Tech Hardware) | MAG7 baseline, highest data quality |
| JPMorgan Chase | JPM | Bank (GSIB) | Most complex dimensional reporting |
| ExxonMobil | XOM | Standard (Energy) | Upstream/downstream segment complexity |
| Walmart | WMT | Standard (Retail) | Clean balance sheet, fiscal year mismatch (Jan 31) |
| Johnson & Johnson | JNJ | Standard (Healthcare) | Pharma/MedTech segments, recent spin-off (Kenvue) |

**Decision record — Why 5 companies, not 10 or 20:**
The Orchestrator's `map_company()` (`orchestrator.py:70-145`) runs 3 extraction layers sequentially per company. With snapshot mode (no network calls), each company takes ~30-40 seconds. Five companies fit within the 3-minute quick-eval budget while covering all major archetypes. The full-eval tier (all 96 companies) runs once at the end of the overnight session.

### The Loop — Overnight Operation (11 PM - 7 AM)

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTO-EVAL OVERNIGHT LOOP                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  23:00  ┌──────────────────────┐                                │
│         │ 1. BASELINE          │                                │
│         │    compute_cqs()     │  CQS_baseline = 0.956          │
│         │    on eval cohort    │                                 │
│         └──────────┬───────────┘                                │
│                    │                                             │
│  23:05  ┌──────────▼───────────┐                                │
│         │ 2. GAP ANALYSIS      │                                │
│         │    Identify top       │  "AMZN:IntangibleAssets,       │
│         │    failing metrics    │   HD:OperatingIncome,          │
│         │    across all cos     │   NVDA:SharesOutstanding"      │
│         └──────────┬───────────┘                                │
│                    │                                             │
│         ┌──────────▼───────────┐                                │
│         │ 3. EXPERIMENT LOOP   │  Repeat for each gap:          │
│  23:10  │    ┌───────────────┐ │                                │
│   to    │    │ a. PROPOSE    │ │  Agent suggests config change  │
│  06:30  │    │    config mod │ │  (add concept / divergence /   │
│         │    └───────┬───────┘ │   tree_hint / exclusion)       │
│         │    ┌───────▼───────┐ │                                │
│         │    │ b. APPLY      │ │  Write to Tier 1 YAML          │
│         │    │    change     │ │                                 │
│         │    └───────┬───────┘ │                                │
│         │    ┌───────▼───────┐ │                                │
│         │    │ c. EVAL       │ │  run quick-tier (5 cos, 3 min) │
│         │    │    CQS_new    │ │                                 │
│         │    └───────┬───────┘ │                                │
│         │    ┌───────▼───────┐ │                                │
│         │    │ d. DECIDE     │ │  if CQS_new > CQS_baseline    │
│         │    │              │ │     AND regressions == 0:       │
│         │    │  KEEP or     │ │     KEEP → new baseline         │
│         │    │  DISCARD     │ │  else:                          │
│         │    │              │ │     DISCARD → log to graveyard  │
│         │    └───────┬───────┘ │                                │
│         │    ┌───────▼───────┐ │                                │
│         │    │ e. LOG        │ │  Record in auto_eval_experiments│
│         │    └───────────────┘ │                                │
│         └──────────┬───────────┘                                │
│                    │                                             │
│  06:30  ┌──────────▼───────────┐                                │
│         │ 4. FULL-TIER EVAL    │                                │
│         │    All 96 companies  │  CQS_final = 0.963 (+0.007)   │
│         │    ~30 min           │                                 │
│         └──────────┬───────────┘                                │
│                    │                                             │
│  07:00  ┌──────────▼───────────┐                                │
│         │ 5. FINALIZE          │                                │
│         │    • Evolution report │                                │
│         │    • Git commit       │                                │
│         │    • Dashboard update │                                │
│         └──────────────────────┘                                │
│                                                                 │
│  07:00  ┌──────────────────────┐                                │
│         │ 6. MORNING DASHBOARD │  Human reviews results          │
│         └──────────────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

### Experiment Decision Logic

```python
# standardization/tools/auto_eval_loop.py (conceptual)

def evaluate_experiment(
    change: ConfigChange,
    baseline_cqs: CQSResult,
    eval_cohort: List[str],
) -> ExperimentDecision:
    """
    Apply a config change, measure CQS, decide KEEP or DISCARD.

    Decision rules:
    1. CQS must improve (CQS_new > CQS_baseline)
    2. Zero golden master regressions (regression_rate == 0)
    3. No single company's pass_rate drops by more than 5pp

    If all three pass → KEEP (update baseline)
    Otherwise → DISCARD (revert config, log to graveyard)
    """
    # Apply change to Tier 1 config
    apply_config_change(change)

    # Run quick-tier eval
    new_cqs = compute_cqs(eval_cohort, snapshot_mode=True)

    # Check decision criteria
    cqs_improved = new_cqs.cqs > baseline_cqs.cqs
    no_regressions = new_cqs.regression_rate == 0.0
    no_company_collapse = all(
        new_cqs.company_scores[t] >= baseline_cqs.company_scores[t] - 0.05
        for t in eval_cohort
    )

    if cqs_improved and no_regressions and no_company_collapse:
        return ExperimentDecision(action="KEEP", cqs_delta=new_cqs.cqs - baseline_cqs.cqs)
    else:
        revert_config_change(change)
        log_to_graveyard(change, reason=...)
        return ExperimentDecision(action="DISCARD", cqs_delta=0)
```

### Gap Prioritization

Gaps are ranked by estimated CQS impact to maximize overnight productivity:

```python
def prioritize_gaps(gaps: List[MetricGap], eval_cohort: List[str]) -> List[MetricGap]:
    """
    Rank gaps by expected CQS improvement.

    Priority = (companies_affected / total_companies) * metric_weight

    Where metric_weight reflects the CQS sub-metric most impacted:
    - Unmapped metric → affects coverage_rate (0.15 weight)
    - Validation failure → affects pass_rate (0.50 weight)
    - High variance → affects mean_variance (0.20 weight)

    Validation failures are prioritized over unmapped metrics
    because pass_rate has 3.3x the CQS weight of coverage_rate.
    """
    ...
```

### Morning Dashboard

```
╔══════════════════════════════════════════════════════════════════╗
║              AUTO-EVAL OVERNIGHT REPORT — 2026-03-18            ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  CQS Trajectory: 0.956 → 0.963 (+0.007)                        ║
║  ████████████████████████████████████████████████▓░░  96.3%      ║
║                                                                  ║
║  Experiments:  47 run │ 31 kept │ 12 discarded │ 4 errored      ║
║  Duration:     7h 42m │ Avg experiment: 3.2 min                 ║
║  Config diff:  +18 known_concepts, +3 divergences, +2 exclusions║
║                                                                  ║
╠════════════════════ TOP IMPROVEMENTS ════════════════════════════╣
║                                                                  ║
║  Metric               Companies    CQS Impact    Change         ║
║  ──────────────────────────────────────────────────────────────  ║
║  IntangibleAssets      HD,LOW,TGT   +0.0021      +concept       ║
║  OperatingIncome       XOM,CVX      +0.0018      +tree_hint     ║
║  DeprecAmort           AMZN,GOOG    +0.0012      +composite     ║
║  AccountsPayable       WMT,COST     +0.0009      +concept       ║
║                                                                  ║
╠════════════════════ GRAVEYARD (discarded) ═══════════════════════╣
║                                                                  ║
║  Metric               Attempt       Reason                      ║
║  ──────────────────────────────────────────────────────────────  ║
║  ShortTermDebt         +concept      JPM regressed (-3pp)        ║
║  Capex                 +composite    XOM variance +22%           ║
║  SharesOutstanding     +concept      NVDA split distortion       ║
║                                                                  ║
╠════════════════════ FLAGGED FOR REVIEW ══════════════════════════╣
║                                                                  ║
║  ⚠ ShortTermDebt failed 3 different approaches — may need       ║
║    Tier 3 (code) change for dimensional handling                 ║
║  ⚠ NVDA SharesOutstanding consistently fails due to stock       ║
║    split normalization — known yfinance divergence               ║
║                                                                  ║
╠════════════════════ GOLDEN MASTER STATUS ════════════════════════╣
║                                                                  ║
║  Total: 142 │ Held: 142 │ New: 8 │ Regressed: 0                ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## 5. Agent Optimization via Auto-Eval

The deeper insight from autoresearch: `program.md` (the agent instructions) is itself an optimizable parameter — just at a longer timescale than `train.py` (the model code).

In EdgarTools, the concept-mapping-resolver agent (`.claude/agents/concept-mapping-resolver.md`) contains a Resolution Decision Tree (lines 621-656) and Quality Standards (lines 669-675) that directly affect how mapping gaps are resolved. These parameters — confidence thresholds, variance limits, resolution strategies — are as much "configuration" as `metrics.yaml`.

### Task Battery Design

Each agent gets a fixed set of representative tasks (a "task battery") that exercise its core capabilities:

```yaml
# concept-mapping-resolver task battery
tasks:
  - name: "resolve_structural_gap"
    input: "AMZN IntangibleAssets unmapped"
    expected: "Add OtherIntangibleAssetsNet to known_concepts"
    metric: "correct_resolution"

  - name: "resolve_validation_failure"
    input: "JPM ShortTermDebt variance 18%"
    expected: "Add known_divergence with dimensional justification"
    metric: "correct_classification"

  - name: "reject_bad_mapping"
    input: "Force GoodwillAndIntangibleAssetsNet for Goodwill"
    expected: "Reject — parent concept, not standalone"
    metric: "no_parent_fallback"

  - name: "cross_company_pattern"
    input: "IntangibleAssets fails for HD, LOW, TGT"
    expected: "learn_mappings discovers shared retail concept"
    metric: "pattern_discovered"

  - name: "handle_dimensional"
    input: "MS OperatingIncome only in segment dimensions"
    expected: "Flag for dimensional enhancement, do not force"
    metric: "correct_escalation"
```

### Agent Instruction A/B Testing

```
Week N:
  1. Baseline: Run task battery with current agent instructions
     → Battery score: 8/10

  2. Variant A: Lower auto-apply confidence from 0.80 to 0.70
     → Battery score: 9/10 (more resolutions, but check regressions)

  3. Variant B: Add new resolution strategy for dimensional metrics
     → Battery score: 9/10 (handles MS case, no regressions)

  4. Compare: Both variants score 9/10, but Variant B has
     zero regression risk → KEEP Variant B

  5. Log to agent_instruction_experiments table
```

### Cadence

| Optimization Target | Cadence | Budget | Decision Gate |
|---|---|---|---|
| Tier 1 config (metrics.yaml, etc.) | Nightly | 3 min/experiment | CQS improvement + zero regressions |
| Agent instructions (.md files) | Weekly | Full task battery (~30 min) | Battery score improvement + CQS non-regression |
| Extraction engine (Python source) | Manual | Full E2E suite (~2 hours) | Human code review + all tests pass |

---

## 6. What Needs Building

### New Components

| Component | Location | Est. Lines | Purpose | Depends On |
|---|---|---|---|---|
| `auto_eval.py` | `standardization/tools/auto_eval.py` | ~300 | `compute_cqs()`, `run_experiment()`, `compare_experiments()` | Orchestrator, ReferenceValidator, ExperimentLedger |
| `auto_eval_loop.py` | `standardization/tools/auto_eval_loop.py` | ~500 | Overnight loop: propose → eval → keep/discard → log | auto_eval.py, config parsers |
| `auto_eval_dashboard.py` | `standardization/tools/auto_eval_dashboard.py` | ~200 | Morning review terminal dashboard (Rich-based) | auto_eval_loop.py results |
| `agent_battery.py` | `standardization/tools/agent_battery.py` | ~400 | Task batteries for agent instruction optimization | Agent definitions, eval harness |
| Ledger schema extension | `standardization/ledger/schema.py` | ~50 | 2 new tables: `auto_eval_experiments`, `auto_eval_graveyard` | Existing schema |
| `run-auto-eval` skill | `.claude/skills/run-auto-eval/SKILL.md` | ~100 | CLI invocation of auto-eval loop | auto_eval_loop.py |
| `auto-eval-runner` agent | `.claude/agents/auto-eval-runner.md` | ~200 | Agent constrained to Tier 1 config modifications only | auto_eval.py, Tier 1 configs |

**Total: ~1,750 net-new lines across 7 files, composing ~3,000 lines of existing infrastructure.**

### New Ledger Tables

```python
# Extension to standardization/ledger/schema.py

@dataclass
class AutoEvalExperiment:
    """Record of a single auto-eval experiment."""
    experiment_id: str           # UUID
    run_id: str                  # Links to parent overnight run
    timestamp: str               # ISO 8601
    target_metric: str           # e.g., "IntangibleAssets"
    target_companies: List[str]  # e.g., ["HD", "LOW", "TGT"]
    change_type: str             # "add_concept" | "add_divergence" | "add_tree_hint" | "add_exclusion"
    change_description: str      # Human-readable description
    config_diff: str             # Unified diff of YAML change
    cqs_before: float
    cqs_after: float
    cqs_delta: float
    decision: str                # "KEEP" | "DISCARD"
    duration_seconds: float
    golden_masters_checked: int
    golden_masters_regressed: int

@dataclass
class AutoEvalGraveyard:
    """Record of a discarded experiment — what didn't work and why."""
    experiment_id: str           # Links to AutoEvalExperiment
    target_metric: str
    change_description: str
    discard_reason: str          # "cqs_declined" | "regression" | "company_collapse" | "error"
    detail: str                  # Specific explanation (e.g., "JPM pass_rate dropped 95% → 92%")
    similar_attempts: int        # How many times this metric has been attempted
    timestamp: str
```

### Integration Points with Existing Code

`compute_cqs()` integrates with existing infrastructure at these specific points:

```python
# How CQS connects to existing code

from edgar.xbrl.standardization.orchestrator import Orchestrator
from edgar.xbrl.standardization.reference_validator import ReferenceValidator
from edgar.xbrl.standardization.ledger import ExperimentLedger
from edgar.xbrl.standardization.tools.kpi_tracker import RunStatistics
from edgar.xbrl.standardization.tools.onboard_company import OnboardingResult

def compute_cqs(eval_cohort, snapshot_mode=True):
    orch = Orchestrator()

    # 1. Extract: reuses Orchestrator.map_companies()
    #    (orchestrator.py:287-332)
    results = orch.map_companies(eval_cohort, use_ai=False, validate=True)

    # 2. Validate: reuses ReferenceValidator
    #    (reference_validator.py — validate_and_update_mappings)
    validator = ReferenceValidator(snapshot_mode=snapshot_mode)
    validation_results = {}
    for ticker, metrics in results.items():
        validation_results[ticker] = validator.validate_and_update_mappings(
            ticker, metrics, xbrl=..., filing_date=..., form_type=...
        )

    # 3. Golden masters: reuses ExperimentLedger
    #    (ledger/schema.py — GoldenMaster table)
    ledger = ExperimentLedger()
    golden_masters = ledger.get_all_golden_masters()

    # 4. Compute sub-metrics from existing data structures
    pass_rate = compute_aggregate_pass_rate(validation_results)       # OnboardingResult pattern
    mean_variance = compute_mean_variance(validation_results)         # From ValidationResult.variance_pct
    coverage_rate = compute_coverage(results)                         # RunStatistics pattern
    gm_rate = compute_golden_master_rate(golden_masters, results)     # Ledger query
    regression_rate = compute_regression_rate(golden_masters, results)# Cohort comparison

    # 5. Weighted combination
    cqs = (0.50 * pass_rate
         + 0.20 * (1 - mean_variance / 100)
         + 0.15 * coverage_rate
         + 0.10 * gm_rate
         + 0.05 * (1 - regression_rate))

    return CQSResult(
        cqs=cqs,
        pass_rate=pass_rate,
        mean_variance=mean_variance,
        coverage_rate=coverage_rate,
        golden_master_rate=gm_rate,
        regression_rate=regression_rate,
        company_scores={t: compute_cqs_single(t, results, validation_results) for t in eval_cohort},
    )
```

---

## 7. What This Enables

### Scaling Math

Current state (from `docs/financial-database-status.md`):
- 96 companies with snapshots, ~51 fully onboarded
- 24 standardized metrics per company
- 95-100% pass rates across mature archetypes
- Concept-mapping-resolver resolves ~2 metrics per session (`.claude/agents/concept-mapping-resolver.md:717-788`)

**With auto-eval overnight loop:**
- 47 experiments/night (from loop capacity estimate: 7.5 hours / ~10 min per propose+eval cycle)
- ~65% KEEP rate (conservative — autoresearch sees ~40-60%)
- ~31 kept changes/night × ~1 metric resolved each = **~30 metrics resolved per night**
- Each company has ~3-5 failing metrics on average
- **~6-10 companies fully onboarded per night**

**Projected timeline to S&P 500:**
- Current: 51 companies at high quality
- Remaining: ~450 companies
- At 8 companies/night: **~56 nights (~2 months)**
- Conservative (weeknights only, maintenance days): **~3 months**

### Self-Improving Agent Quality

Each overnight run generates data that improves future runs:

```
Night 1: Agent resolves IntangibleAssets for HD
  → Adds OtherIntangibleAssetsNet to known_concepts
  → Graveyard records: GoodwillAndIntangibleAssetsNet was a parent concept (rejected)

Night 2: Agent encounters IntangibleAssets for LOW
  → known_concepts already has OtherIntangibleAssetsNet → auto-resolves (Layer 1)
  → Graveyard prevents re-attempting parent concept

Night 5: Agent instruction update adds "check for Amortizable variants" heuristic
  → Task battery validates the new heuristic
  → Future IntangibleAssets gaps resolved faster
```

### Continuous Regression Protection

The pipeline state machine (`pipeline_orchestrator.py:334-344`) already enforces quality gates:

```
PENDING → ONBOARDING → ANALYZING → RESOLVING → VALIDATING → PROMOTING → POPULATING → COMPLETE
```

Auto-eval adds a pre-commit gate: every config change is validated against all golden masters before being kept. The `auto_eval_graveyard` table accumulates "what doesn't work" knowledge, preventing the agent from re-attempting failed approaches.

### Knowledge Accumulation

Three knowledge stores grow automatically:

1. **Evolution reports** (`.claude/skills/write-evolution-report/SKILL.md`): Generated after each overnight run, tracking CQS trajectory, new golden masters, and architectural decisions.

2. **Graveyard**: Discarded experiments with structured reasons. Over time, reveals patterns:
   - "ShortTermDebt has been attempted 12 times, always fails due to dimensional complexity → needs Tier 3 change"
   - "Insurance companies consistently fail on Revenue due to premium normalization → needs archetype-specific handling"

3. **Config evolution**: `git log` on Tier 1 YAML files shows the full history of what worked, when, and for which companies.

### Human-in-the-Loop

The morning dashboard (Section 4) keeps humans as **reviewers, not operators**:

- **Review scope**: CQS trajectory, flagged items, graveyard patterns
- **Decision scope**: Approve Tier 3 changes flagged by the loop, adjust CQS weights, update eval cohort
- **Time commitment**: ~15 minutes/morning vs ~2 hours/day of manual gap investigation

This matches autoresearch's model: humans edit `program.md` (strategy); agents execute `train.py` (tactics).

---

## Appendix A: Comparison with Autoresearch at Every Level

| Level | Autoresearch | EdgarTools Auto-Eval | Key Difference |
|---|---|---|---|
| **Eval metric** | `val_bpb` (bits per byte on validation set) | CQS (weighted composite of 5 sub-metrics) | CQS is a composite because SEC data quality has multiple dimensions; `val_bpb` is a single natural metric for language modeling |
| **Eval speed** | ~5 min (train small model + eval) | ~3 min quick-tier (5 companies, snapshot mode) | EdgarTools is faster because snapshots eliminate network calls |
| **Modifiable surface** | `train.py` (single Python file) | 3 YAML config files (metrics, companies, industry) | YAML is safer — syntax errors are caught by parser, never crash runtime |
| **Fixed harness** | `prepare.py` (data loading, eval loop) | Orchestrator + ReferenceValidator + yf_snapshots | Same pattern: the eval harness is never modified by the agent |
| **Agent instructions** | `program.md` (research strategy) | `.claude/agents/*.md` + `.claude/skills/*/SKILL.md` | EdgarTools has many specialized agents vs one general agent |
| **Experiment log** | `runs.jsonl` (flat file) | ExperimentLedger (SQLite with multiple tables) | EdgarTools needs richer provenance (ticker, metric, layer, strategy) |
| **Success criterion** | `val_bpb` strictly decreases | CQS strictly increases + zero golden master regressions | EdgarTools has an additional regression constraint |
| **Failure mode** | Bad experiment wastes 5 min | Bad config change caught by ReferenceValidator in <1 min | EdgarTools fails faster due to deterministic validation |
| **Knowledge retention** | `runs.jsonl` entries | Graveyard + evolution reports + git history | EdgarTools accumulates structured "what doesn't work" knowledge |
| **Human role** | Edit `program.md` occasionally | Review morning dashboard, approve Tier 3 changes | Same: humans set strategy, agents execute |

## Appendix B: Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Config change passes quick-tier but fails on full cohort | Medium | Low (caught in step 4) | Full-tier eval as final gate before commit |
| Agent proposes same failed change repeatedly | Medium | Low (wastes time) | Graveyard lookup before proposing; skip if >3 prior failures |
| CQS weights don't reflect true quality priorities | Low | Medium | Validate CQS against human quality rankings; adjust weights quarterly |
| Golden master set becomes stale or too conservative | Low | Medium | Review golden master set monthly; retire golden masters for companies with structural changes |
| Overnight run produces conflicting changes | Medium | Low | Sequential experiment application; each builds on previous baseline |
| Config file grows too large (too many known_concepts) | Low | Low | Periodic pruning of unused concepts (concepts that never matched) |

## Appendix C: Decision Records

### DR-1: Why 0.50 Weight on pass_rate

**Context:** CQS needs a dominant sub-metric to provide clear optimization signal, matching autoresearch's single-metric focus.

**Decision:** pass_rate gets 0.50 weight (50% of CQS).

**Rationale:** pass_rate is the most actionable and interpretable metric. A config change that improves coverage but breaks pass_rate is unambiguously bad. The 0.50 weight ensures pass_rate regressions always dominate CQS, preventing the optimizer from trading correctness for breadth.

**Alternatives considered:**
- Equal weights (0.20 each): Too ambiguous — coverage improvements could mask pass_rate regressions
- pass_rate only (1.00): Ignores important quality dimensions (variance, coverage)

### DR-2: Why Tier 1 Only for Overnight Autonomy

**Context:** The agent could theoretically modify Python source code (Tier 3) to resolve more gaps.

**Decision:** Overnight autonomy is restricted to Tier 1 (YAML configs) only.

**Rationale:** YAML changes are deterministic, parseable, and always recoverable (`git checkout`). Python changes can introduce subtle bugs that pass quick-tier eval but fail in production. The concept-mapping-resolver's real-world testing showed 84% of gaps are config-solvable — sufficient for meaningful overnight progress.

**Trade-off:** ~16% of gaps (true unmapped requiring code changes) cannot be resolved overnight. These are flagged in the morning dashboard for human investigation.

### DR-3: Why 3-Minute Quick Eval Budget

**Context:** Need to balance experiment throughput (more experiments = more CQS improvement) against eval reliability (more companies = higher confidence).

**Decision:** Quick-tier uses 5 companies in snapshot mode, targeting ~3 minutes per eval.

**Rationale:**
- 5 companies × ~30 seconds each = ~2.5 minutes extraction + ~30 seconds validation
- 7.5 hours overnight / (3 min eval + ~7 min propose+apply+decide) = ~45 experiments
- 45 experiments × 65% KEEP rate = ~29 kept changes — sufficient for 6-10 new companies/night
- Full-tier eval (96 companies, ~30 min) runs once at the end as a safety net

**Alternative considered:** 10 companies, ~6 min eval — only 25 experiments per night, roughly halving throughput. The full-tier final eval catches false positives from the smaller quick-tier cohort.
