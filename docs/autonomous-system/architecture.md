# Autonomous System Architecture

*Single source of truth for how the autonomous extraction quality system works.*
*See [roadmap.md](roadmap.md) for history, progress, and active milestones.*

---

## System Overview

The autonomous system applies the [autoresearch](https://github.com/karpathy/autoresearch) pattern to XBRL extraction quality. AI agents modify Tier 1 YAML configs ("weights") while the evaluation harness (Orchestrator + ReferenceValidator + yf_snapshots) remains fixed. A **Composite Quality Score (CQS)** drives experiment decisions. The key constraint: agents never touch the extraction engine (Python code) — they only modify configuration. This is what makes overnight autonomy safe.

---

## Current State

| Metric | Value | Updated |
|--------|-------|---------|
| CQS | 0.9957 | 2026-03-24 |
| EF-CQS | 0.8491 | 2026-03-24 |
| SA-CQS | 0.8459 | 2026-03-24 |
| Companies | 100 | |
| Metrics | 37 base + 3 derived | |
| Reference | yfinance + SEC XBRL API | |
| AI | Gemini Flash via OpenRouter + typed actions | |

**EF-CQS is the primary KPI** — CQS at 0.98+ is below noise floor for single-metric decisions.

---

## Architecture

```
Gap Analysis → Propose Config Change → Apply → Measure
     ↑                                           |
     |    ┌─────────── Decision Gate ←────────────┘
     |    |  (LIS: target improved + zero regressions)
     |    |
     |    ├── KEEP → new baseline → next gap
     |    └── DISCARD → revert → graveyard
     |                              |
     └── (skip if graveyard count ≥ 6) ←──┘

Extraction Pipeline:
  Filing → Orchestrator (tree → facts → AI layers) → Extraction
    → Validation (internal equations + yfinance + SEC API)
    → Evidence tier (sec_confirmed > yfinance_confirmed > self_validated > unverified)
    → Experiment Ledger → Dashboard (EF-CQS headline)
```

---

## Key Components

### CQS Formula (current weights)

```
CQS = 0.45 * pass_rate
    + 0.20 * (1 - mean_variance / 100)
    + 0.15 * coverage_rate
    + 0.15 * stability_rate
    + 0.05 * (1 - regression_rate)
```

**Sub-scores:**
- **EF-CQS** (Extraction Fidelity) — Did we find the right XBRL concept? Passes only for known_concepts, tree-resolved, or reference-confirmed.
- **SA-CQS** (Standardization Alignment) — Can we reproduce yfinance's aggregated number? Uses composite formula evaluation.

### Multi-Layer Mapping Engine

| Layer | File | Method | Speed |
|-------|------|--------|-------|
| 1: Tree Parser | `layers/tree_parser.py` | Static calculation tree parsing | Fast |
| 2: Facts Search | `layers/facts_search.py` | Static facts database search | Fast |
| 3: AI Semantic | `layers/ai_semantic.py` | Dynamic AI semantic mapping | Slow |

### Validation Stack

1. **Internal Consistency** (`internal_validator.py`) — 5 accounting equations (e.g., Assets = Liabilities + Equity). Failures flag `EQUATION_CONFLICT`.
2. **Reference Validator** (`reference_validator.py`) — Compares against yfinance snapshots + SEC XBRL API. Computes per-metric variance.
3. **Evidence Tiers** — `sec_confirmed` > `yfinance_confirmed` > `self_validated` > `unverified`. Unverified metrics excluded from pass/fail scoring.
4. **Publish Confidence** — high / medium / low / unverified on each `ValidationResult`.

### Decision Gate

Currently: global CQS comparison (`new_cqs > baseline_cqs`).
Target (M1): **LIS (Localized Impact Score)** — target metric improved + zero regressions for that company. Key file: `auto_eval_loop.py:_apply_decision_gates()`.

Safety invariants:
- New regressions are a hard veto
- No single company drops >5pp in pass_rate
- Circuit breaker: 10 consecutive failures stops the session
- All changes are git-recoverable
- Graveyard prevents loops (6+ failed attempts → skip)

### Experiment Ledger

SQLite database (`ledger/schema.py`) with tables:
- `PipelineRun` — extraction run metadata
- `ExtractionRun` — per-metric extraction results
- `AutoEvalExperiment` — experiment decisions (KEEP/DISCARD/VETO)
- `AutoEvalGraveyard` — failed approaches with structured reasons
- Golden masters — stable multi-period extractions for regression detection

### Typed Actions

AI emits semantic intent via 7 finite action types. A deterministic compiler translates actions into YAML config changes. The AI never sees file paths or YAML structure.

| Action | What It Does |
|--------|-------------|
| `ADD_CONCEPT` | Add known_concept to metrics.yaml |
| `ADD_EXCLUSION` | Exclude metric for company/industry |
| `ADD_KNOWN_VARIANCE` | Document explained variance |
| `ADD_STANDARDIZATION` | Add solver composite formula |
| `ADD_COMPANY_OVERRIDE` | Company-specific concept mapping |
| `SET_INDUSTRY` | Map company to industry archetype |
| `SET_SIGN_CONVENTION` | Fix sign inversion |

### Evaluation Cohorts

| Cohort | Size | Time | Purpose |
|--------|------|------|---------|
| `QUICK_EVAL_COHORT` | 5 companies | ~50s | Per-experiment fast eval |
| `VALIDATION_COHORT` | 20 companies | ~200s | Tournament stage-2 |
| `EXPANSION_COHORT_50` | 50 companies | ~270s | Cross-sector quality |
| `EXPANSION_COHORT_100` | 100 companies | ~600s | Production stress test |
| `EXPANSION_COHORT_500` | 500 S&P 500 | ~50min | Full-index (pending) |

---

## File Map

### Config (Tier 1 — agent-modifiable)
| File | Contents |
|------|----------|
| `config/metrics.yaml` | Metric definitions, known_concepts, tree_hints, tolerances, composites |
| `config/companies.yaml` | Company overrides, exclusions, divergences |
| `config/industry_metrics.yaml` | Industry-specific concepts, forbidden/required metrics |
| `config/yf_snapshots/` | Cached yfinance reference data (frozen JSONs) |

### Tools (automation layer)
| File | Purpose |
|------|---------|
| `tools/auto_eval.py` | CQS computation, gap analysis, cohort definitions |
| `tools/auto_eval_loop.py` | Experiment loop, decision gates, `run_overnight()` |
| `tools/auto_eval_dashboard.py` | Morning review terminal dashboard |
| `tools/auto_solver.py` | Subset-sum formula discovery |
| `tools/consult_ai_gaps.py` | AI consultation pipeline, typed actions, OpenRouter caller |
| `tools/discover_concepts.py` | Search calc trees + facts for concept candidates |
| `tools/verify_mapping.py` | Value comparison against yfinance |
| `tools/learn_mappings.py` | Cross-company pattern discovery |
| `tools/auto_eval_checkpoint.py` | Checkpoint I/O and team dashboard |
| `tools/onboard_company.py` | Automated company onboarding |

### Core Engine (Tier 2-3 — human-reviewed)
| File | Purpose |
|------|---------|
| `orchestrator.py` | Main multi-layer orchestrator |
| `reference_validator.py` | Validation against yfinance + SEC API |
| `internal_validator.py` | Accounting equation consistency checks |
| `ledger/schema.py` | SQLite experiment ledger schema |
| `models.py` | MappingResult, MappingSource, ConfidenceLevel |
| `config_loader.py` | YAML config loading |

---

## Configuration Tiers

| Tier | Files | Who | Gate |
|------|-------|-----|------|
| **Tier 1** (agent-safe) | metrics.yaml, companies.yaml, industry_metrics.yaml | AI agents | CQS non-regression |
| **Tier 2** (human-reviewed) | Python tools layer, company_mappings/*.json | Developers | Code review + tests |
| **Tier 3** (architect) | Orchestrator, validator, ledger schema | Architects | Full E2E suite |

---

## Key Decisions

These persist across all sessions and guide all future work:

1. **Primary KPI is EF-CQS, not CQS** — CQS at 0.98+ is below noise floor for single-metric decisions (Session 002-004)
2. **LIS replaces CQS as decision gate** — Localized Impact Score: target improved + zero regressions (Session 004)
3. **SEC-native evidence is first-class** — yfinance is corroboration, not truth (Session 004)
4. **AI emits typed actions, never raw YAML** — 7 finite actions compiled by deterministic code (Session 004-benchmark)
5. **~90-95% autonomous ceiling** — tail 5-10% needs human review (all sessions agree)
6. **Scale order: scoring → metrics → companies** — fix measurement before expanding (Session 004)
7. **Single source of truth: these 2 docs** — `architecture.md` (how) + `roadmap.md` (what/when)

---

## AI Agent Guide

### The Loop

```
MEASURE → DIAGNOSE → PRIORITIZE → FIX → VALIDATE → RECORD → loop
```

1. **MEASURE** — `compute_cqs()` establishes baseline. Never skip this. The baseline is the rollback target.
2. **DIAGNOSE** — `identify_gaps()` classifies each gap by root cause and capability tier.
3. **PRIORITIZE** — Sort by impact DESC, graveyard_count ASC. Filter out graveyarded gaps. Process Tier 1 only overnight.
4. **FIX** — Generate typed action → compile to config → apply. Validate locally first, then globally.
5. **VALIDATE** — Re-measure CQS. Check: target improved, zero regressions, no company dropped >5pp.
6. **RECORD** — Log experiment (KEEP/DISCARD/VETO) to ledger. Update graveyard on failure.

### Gap Classification

| Tier | Gap Types | Approach |
|------|-----------|----------|
| **D0** (Deterministic) | sign_error, industry_structural | Rules engine, no AI |
| **H1** (Hybrid) | missing_concept, missing_component | AI diagnosis + typed action + deterministic compiler |
| **E** (Escalation) | extension_concept, engine limitation | Engineering backlog, not config patches |

### Capability Tiers (C1/C2/C3)

| Tier | Solvable By | % of Gaps |
|------|------------|-----------|
| **C1** | Deterministic solver (known patterns) | ~34% |
| **C2** | AI-assisted (concept discovery + typed action) | ~30% |
| **C3** | Human/engineering (extension concepts, parser gaps) | ~36% |

### Quick Start

```python
from edgar.xbrl.standardization.tools.auto_eval import (
    compute_cqs, identify_gaps, print_cqs_report, print_gap_report,
    QUICK_EVAL_COHORT, EXPANSION_COHORT_100,
)

# Measure current quality
cqs = compute_cqs(eval_cohort=QUICK_EVAL_COHORT, snapshot_mode=True)
print_cqs_report(cqs)  # Shows CQS, EF-CQS, SA-CQS

# Find gaps ranked by impact
gaps, cqs = identify_gaps(snapshot_mode=True, max_workers=4)
print_gap_report(gaps)
```

### Running Overnight

```python
from edgar.xbrl.standardization.tools.auto_eval_loop import run_overnight
from edgar.xbrl.standardization.tools.auto_eval_dashboard import show_dashboard

report = run_overnight(duration_hours=7.5, max_workers=4)
show_dashboard()
```
