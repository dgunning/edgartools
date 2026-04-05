# Consensus Session 022: Autonomous Loop Fate — Repurpose vs Extract & Mothball

**Date:** 2026-04-04
**Pattern:** Champion (Option A vs Option B)
**Models:** GPT-5.4 (champion Option A), Gemini 3.1 Pro (champion Option B), Claude Opus 4.6 (moderator)
**Continuation ID:** `fe9fc0a2-ad06-4ee8-8b38-80567f1cef11`
**Trigger:** Consensus 022 (deep-consensus) identified the autonomous loop's fate as the key unresolved question. The loop has produced zero net EF-CQS improvements since Run 011 (19 runs total). Strategic pivot from "improve CQS" to "ship quality signals" makes the improvement loop's purpose obsolete.

## Context

The autonomous XBRL extraction system has ~11,500 lines of infrastructure across 5 modules. The improvement loop (`auto_eval_loop.py` at 5,014 lines) was designed for overnight autonomous config-only optimization. It was productive in Runs 001-005 (CQS 0.9062→0.9957) but has produced zero net improvements since Run 011. Every meaningful quality gain (EF-CQS 0.65→0.87) came from manual investigation, measurement bug fixes, or consensus-driven architectural decisions.

The scoring engine (`auto_eval.py` at 2,447 lines) contains `compute_cqs()`, `identify_gaps()`, `compute_pure_ef()`, and `classify_company_tiers()` — these are always needed. The question is what to do with the 5k+ lines of improvement infrastructure that sits on top.

Two options debated: (A) Repurpose the existing infrastructure as a monitoring system, or (B) Build a new lightweight regression monitor using `auto_eval.py` functions directly, let improvement code bit-rot.

## GPT-5.4 (Champion Option A — Repurpose)

- Option A is the stronger choice: repurpose as monitor-only, hard-disable proposal/apply/AI paths
- `run_overnight()` has battle-tested operational complexity: session control, progress, circuit breakers, caching, manifests — a rewrite would recreate this
- Option B undersells monitoring complexity: cohort management, run metadata, failure accounting, golden-master comparison, timing, operator summaries are already encoded in the "dead" loop
- Industry pattern: mature data products retire autonomy but keep the harness (ML eval, data infra, scraping)
- Hybridized A: keep module as backbone, carve `monitoring.py` surface that delegates to internals
- Risk: dead autonomous semantics → maintenance confusion. Mitigate by explicit deprecation
- **Confidence: 8/10**

## Gemini 3.1 Pro (Champion Option B — Extract + Rebuild)

- Option B is strategically superior: paradigm shift from write/mutate to read/alert demands clean separation
- Production monitor is inherently read-only; mixing with config-mutation logic violates separation of concerns
- Implementation complexity is inverted: stripping mutation from 5k entangled lines is HARDER than building fresh 300-line harness on proven `compute_cqs`/`identify_gaps`
- "Sunk cost fallacy" — keeping 5k lines for "reuse" introduces tech debt; git history preserves if needed
- Industry practice (Great Expectations, Monte Carlo): monitoring aggressively decoupled from transformation/healing
- `compute_cqs()` and `identify_gaps()` already well-isolated in `auto_eval.py` — no extraction needed
- **Confidence: 9/10**

## Our Diagnosis

### Agreements
1. `auto_eval.py` (scoring engine) is the lasting value — both models agree
2. The improvement loop has plateaued — zero net improvements since Run 011, 19 runs of evidence
3. Quarterly ecosystem regression detection is required — CI tests can't catch XBRL taxonomy changes
4. Improvement code should not be actively maintained — propose_change, dispatch_ai_gaps, graveyard replay have no further value

### Resolution: Option B (with nuance)
Gemini's argument is stronger. The key insight: `auto_eval.py` is already a separate module from `auto_eval_loop.py`. No "extraction" is needed — the scoring functions already live in their own file. The operational complexity GPT values (session management, checkpointing, circuit breakers) exists because overnight experiments run for 7.5 hours and need recovery. A quarterly regression check calls `compute_cqs()` once (~50 min for 500 companies), diffs against golden masters, and generates a report. It doesn't need session recovery or graveyard management.

### What to build
A new `regression_monitor.py` (~200-300 lines) that:
- Imports `compute_cqs`, `identify_gaps`, `compute_pure_ef` from `auto_eval.py`
- Runs quarterly after filing season
- Compares current extraction against golden master baseline
- Generates regression report (which companies degraded, which metrics changed, which new gaps appeared)
- Flags ecosystem regressions (new XBRL structures) for human review

## Key Decisions

1. **Option B wins**: Build new lightweight regression monitor, let improvement code bit-rot
2. **`auto_eval.py` stays as-is** — it's already the standalone quality measurement engine
3. **`auto_eval_loop.py`, `auto_solver.py`, `consult_ai_gaps.py` — freeze, don't invest, don't delete**
4. **`auto_eval_dashboard.py` — keep** — useful for viewing results
5. **If operational features needed later** — pull specific functions from `auto_eval_loop.py` piecemeal, don't maintain the whole file

## Action Items

- [ ] Build `regression_monitor.py` (~200-300 lines) using `auto_eval.py` functions
- [ ] Add golden master comparison logic (diff baseline vs current per-company scores)
- [ ] Add ecosystem regression detection (flag companies where extraction changed)
- [ ] Update architecture.md to reflect loop deprecation
- [ ] Mark `auto_eval_loop.py`, `auto_solver.py`, `consult_ai_gaps.py` as deprecated in docstrings
