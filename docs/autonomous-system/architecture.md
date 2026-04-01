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
| CQS | 0.8300 | 2026-04-01 |
| EF-CQS | 0.8577 | 2026-04-01 |
| SA-CQS | 0.7471 | 2026-04-01 |
| Companies | 100 | |
| Metrics | 37 base + 3 derived | |
| Reference | yfinance + SEC XBRL API (SEC-native primacy) | |
| AI | Deterministic solver + Lead Agent closed loop (`run_closed_loop()`) + Graveyard replay (`replay_graveyard_proposals()`) | |

**EF-CQS is the primary KPI** — CQS at 0.98+ is below noise floor for single-metric decisions.

**Note on CQS/EF-CQS values:** Numbers above are from 5-company QUICK_EVAL_COHORT with `use_sec_facts=True`. Post-Gap-Resolution-018: banking forbidden expanded (CurrentAssets, CurrentLiabilities), WMT R&D excluded, JNJ Capex and JPM ShareRepurchases documented as known_divergences. Gaps reduced 9→6. 100-company CQS is 0.9121 (last measured 2026-03-27).

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

**LIS (Localized Impact Score)** — target metric improved + zero regressions for that company. Implemented in `auto_eval_loop.py:compute_lis()`. CQS remains as monitoring metric, not a gate.

**Signed Formula Engine** — `_compute_sa_composite()` supports weighted components with positive and negative signs (e.g., GrossProfit = Revenue - COGS). Enabled by Consensus 016 (O49-O52). `6fda5fad`.

**Graveyard Replay** — `replay_graveyard_proposals()` re-evaluates previously rejected proposals after engine changes. Broke the 0% KEEP rate: 17/36 proposals flipped to KEEP with the signed engine.

**EF/SA Gate Decoupling (O53)** — Decision gates are now change-type-aware via `_GATE_APPLICABILITY`. Concept changes check EF only; formula changes check SA only; divergence/exclusion changes skip both EF/SA (they don't affect extraction). Hard veto and per-company drop checks always apply.

**Forbidden Metrics in CQS (O57)** — Industry-forbidden metrics (e.g., GrossProfit for energy companies) are excluded from CQS scoring, not just the gap list. `_build_forbidden_by_ticker()` computes exclusions from `industry_metrics.yaml`.

**Divergence Guardrail** — `_should_allow_divergence()` requires >= 2 prior concept-level graveyard attempts before allowing ADD_DIVERGENCE proposals. Reference-changed regressions are exempt.

Safety invariants:
- New regressions are a hard veto
- No single company drops >5pp in pass_rate
- Circuit breaker: 10 consecutive failures stops the session
- All changes are git-recoverable
- Graveyard prevents loops (6+ failed attempts → skip)
- Divergence requires prior concept attempts (prevents CQS inflation)

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
| `tools/derivation_planner.py` | Derive computed metrics from accounting identities (GrossProfit = Revenue - COGS) |
| `tools/discover_concepts.py` | Search calc trees + facts + reverse value search for concept candidates |
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
| `models.py` | MappingResult, MappingSource (CONFIG=exclusion, OVERRIDE=company override), ConfidenceLevel |
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
8. **Subscription-grade threshold: EF-CQS >= 0.95 overall, >= 0.99 on headline metrics** — Revenue, NetIncome, TotalAssets, TotalLiabilities, Equity, OperatingIncome, OperatingCashFlow, EPS (Session 005)
9. **No scaling past 100 until EF-CQS >= 0.95** with multi-period validation on base cohort (Session 005)
10. **Internal override must never set publish_confidence="high"** — useful for diagnostics, not customer-facing publication (Session 005)
11. **Quarterly data (10-Q) is a separate product milestone** — do not bundle with annual data readiness (Session 005)
12. **Customer metadata (provenance, data dictionary, confidence API) is pre-launch requirement** — not post-launch enhancement (Session 005)
13. **Per-company circuit breaker replaces global** — one unmapped company must never block evaluation of others (Session 006)
14. **AI prompts must include filing evidence** — run `discover_concepts()` pre-dispatch, include top 3-5 candidates. AI ranks, not guesses (Session 006)
15. **Retry-with-feedback over upfront multi-proposal** — 1 proposal + 1 feedback retry beats 3 blind guesses. VALIDATE cost dominates AI cost (Session 006)
16. **In-memory pre-screen before full CQS gate** — `evaluate_experiment_in_memory()` as fast filter; only survivors pay full ~85s measurement (Session 006)
17. **Value-grounded prompts are mandatory** — AI must see `concept | extracted_value | delta_pct` for every candidate, not just name/confidence (Session 007)
18. **Reverse value search belongs in the deterministic layer** — search facts for concepts matching the reference value as a DataFrame filter, not as an agent operation (Session 007)
19. **Three-tier dispatch: deterministic → enriched API → local agent** — value-aware discovery first, Gemini Flash with evidence table second, local agents only for residuals (Session 007)
20. **Cache gap manifest when config fingerprint unchanged** — don't re-run 250s MEASURE for DISCARD iterations. Invalidate only on KEEP (Session 008)
21. **Global-first, scoped-fallback for concept mappings** — try MAP_CONCEPT globally, auto-downgrade to ADD_COMPANY_OVERRIDE on peer regression at pre-screen level (Session 008)
22. **Deterministic Downgrade at pre-screen, not full CQS gate** — fast enough (~1s) to try both scopes without significant validation cost (Session 008)
23. **Compiler must be gap-aware** — `compile_action(action, gap)` signature. AI emits semantic intent, compiler owns scope + namespace translation (Session 009)
24. **Namespace normalization at compiler boundary** — strip `us-gaap:` prefix via `.split(':')[-1]` before writing to any config. Bare names are the canonical form (Session 009)
25. **MAP_CONCEPT routes by gap type** — unmapped → global ADD_CONCEPT, high_variance → company-scoped ADD_COMPANY_OVERRIDE with preferred_concept (Session 009)
26. **Unmapped gaps are actionable by default** — only filter out engineering_backlog / forbidden-by-industry (Session 009)
27. **Semantic correctness over numerical match** — AI must choose concepts by financial meaning, not lowest Delta%. Coincidental numeric matches across unrelated line items are common (Session 010)
28. **Prompt must show current mapping** — `current_concept` field on UnresolvedGap, extracted from `ExtractionEvidence.components_used[0]`. AI needs to know what's already mapped to avoid no-ops (Session 010)
29. **Statement family constraint is enforced at 3 layers** — prompt context (O17), candidate pre-filter (O18), and preflight validation (O20). A balance sheet concept cannot resolve an income statement metric (Session 010)
30. **DOCUMENT_DIVERGENCE is the correct terminal action for verified-concept high-variance gaps** — when the current concept IS semantically correct but the value differs from yfinance, the filing simply reports differently (Session 010)
31. **Preflight catches no-ops before CQS evaluation** — reject proposals identical to current mapping or from wrong statement family. Saves ~85s per rejected proposal (Session 010)
32. **In-memory config mutations use `target_metric` as canonical key** — not `yaml_path` parsing. Matches TreeParser consumption at line 131 (Session 011)
33. **`compile_action` is the strict contract boundary** — all action types emit well-formed dict payloads; in-memory/disk consumers are dumb writers (Session 011)
34. **`setdefault().update()` for metric_overrides** — preserves existing keys (sign_negate) when adding new override properties (Session 011)
35. **Divergences get their own CompanyConfig field** — `known_divergences: Dict[str, Dict]` separates extraction hints from evaluation bypasses (Session 011)
36. **Round-trip consumption tests are mandatory for config mutation code** — prevents future drift between in-memory and disk paths (Session 011)
37. **Diagnostic-first for complex pipeline issues** — when CQS shows exactly zero movement, instrument first, fix second. Code reading alone is insufficient for multi-layer pipeline bugs (Session 012)
38. **`_compute_sa_composite()` is the evaluation bottleneck** — formula pipeline is wired end-to-end but this function is a black box. Needs logging for components found/missing, composite value, promotion decision (Session 012)
39. **`MappingSource.OVERRIDE` is mandatory** — company overrides must be validated against reference data, not auto-passed. `CONFIG` is reserved for excluded metrics only (Session 013)
40. **Strategy 0 hard failure on missing override** — if `preferred_concept` is set but not found in calc trees or facts, return `ConfidenceLevel.INVALID`. Do not silently fall through to Strategy 1 (Session 013)
41. **AI resolver role is semantic adjudication, not concept hunting** — deterministic solver owns discovery; AI owns judgment (DOCUMENT_DIVERGENCE, semantic choice, formula design). AI prompt must include WHY deterministic rejected each candidate (Session 013)
42. **Overrides search facts, not just calc trees** — calc linkbases are notoriously incomplete. Override primacy means search across all data sources before declaring failure (Session 013)
43. **EF and SA verification should be decoupled long-term** — "correct GAAP concept" (EF) and "matches yfinance aggregate" (SA) are different questions. Conflating them causes correct extractions to fail CQS gates. Phase 2 work (Session 013)
44. **Do not optimize prompts against a broken evaluator** — verify evaluator behavior first (re-run through fixed pipeline), then iterate on prompts with human-adjudicated ground truth (Session 014)
45. **Benchmark harness scores semantic correctness independently of CQS** — action accuracy and concept accuracy measured against human ground truth, not CQS delta (Session 014)
46. **DOCUMENT_DIVERGENCE needs a CQS exception mode** — if AI proposes justified divergence, CQS must not penalize under strict matching. Evaluation architecture change, not prompt change (Session 014)
47. **EF and SA must be decoupled in the decision gate** — a correct EF mapping (right XBRL concept) should not be rejected because SA (yfinance match) regressed. EF-only regression check for concept changes, SA-only for formula changes (Session 017)
48. **Divergence and exclusion are first-class terminal outcomes** — LIS must award positive delta when gap transitions from "mismatch/unmapped" to "documented divergence" or "valid exclusion" (Session 017)
49. **AI must never invent concept names** — filing-aware discovery (calc trees + facts + reverse value search) must precede any proposal. AI ranks discovered candidates (Session 017)
50. **Derivation planner uses accounting identities** — GrossProfit = Revenue - COGS, TotalLiabilities = Assets - Equity. Deterministic engine discovers company-specific concepts from calc tree, not AI guessing (Session 017)
51. **Industry pre-exclusion before eval loop** — structurally inapplicable metrics (GrossProfit for energy, CurrentAssets for banks) excluded via industry_metrics.yaml before entering auto-eval, avoiding gate evaluation entirely (Session 017)
52. **Per-metric gate isolation** — replace global EF-CQS regression check with impacted-cell regression. Only re-evaluate target metric and dependents, not all 37 metrics (Session 017)
53. **Scoring integrity reform needed** — `exclude_metrics` conflates "not applicable" (legitimate) with "extraction failed" (hides real failures). 4-component reform: (1) Raw CQS as transitional diagnostic, (2) mandatory `reason` field on exclude_metrics, (3) classification tiers with differentiated scoring (`extraction_failed` counts as failure), (4) Data Completeness Rate. 22 of 49 COGS exclusions are suspected extraction failures. (Consensus 018)

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

### Lead Agent Closed Loop

The expansion workflow for scaling to 500 companies. The lead Claude Code agent orchestrates deterministic + AI resolution in batches.

```
For each 50-company batch:
  1. DETERMINISTIC: run_overnight(propose_fn=propose_change)
     → Resolves C1 gaps (known patterns, solver formulas)
     → Produces GapManifest JSON with all unresolved gaps

  2. AI RESOLUTION: Three-tier dispatch (O7-O9) + semantic prompt (O15-O20)
     Tier 1: Auto-resolve — reverse value search finds us-gaap: concepts
             with <2% variance, emits typed action without API call
     Tier 2: Enriched API — Gemini Flash with semantic prompt:
             - Statement family constraint + concept class (O17)
             - Current mapping context (O16)
             - Pre-filtered candidates (cross-statement removed, O18)
             - Gap-type guidance (DOCUMENT_DIVERGENCE for high_variance, O19)
     Tier 3: Local agents — gap-solver / gap-investigator for residuals
     → All tiers produce TypedAction JSON
     → parse_typed_action() → compile_action() → preflight (O20) → CQS gate

  3. GRADUATE: If batch EF-CQS >= 0.80, promote and move to next batch
```

**Key files:**
- `auto_eval_loop.py` — `run_closed_loop()` (orchestrator), `run_batch_expansion()` (scaling), `run_overnight()` (deterministic solver)
- `consult_ai_gaps.py` — `dispatch_ai_gaps()` (AI dispatch), `evaluate_ai_proposals_live()` (AI CQS gate), `build_typed_action_prompt()`, `collect_typed_proposals()`

**Rules:**
- AI proposals go through the same CQS/LIS gate as deterministic proposals — no bypass
- Each batch must reach EF-CQS >= 0.80 before expanding to the next 50
- Gaps with 6+ graveyard entries are skipped (dead-end filtering)
- TypedAction vocabulary is finite (7 actions) — AI cannot invent new action types

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
from edgar.xbrl.standardization.tools.auto_eval_loop import run_overnight, propose_change
from edgar.xbrl.standardization.tools.auto_eval import EXPANSION_COHORT_50
from edgar.xbrl.standardization.tools.auto_eval_dashboard import show_dashboard

report = run_overnight(
    duration_hours=5.0,
    eval_cohort=EXPANSION_COHORT_50,
    propose_fn=propose_change,
    max_workers=2,
)
show_dashboard()
```

Progress is printed to stdout with structured markers. Monitor with:
```bash
grep -E "ITERATION|KEEP|DISC|VETO|BASELINE|SESSION|TARGET" overnight_run.log
```
