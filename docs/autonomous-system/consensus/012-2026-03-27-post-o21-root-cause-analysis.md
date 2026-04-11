# Consensus Session 012: Post-O21 Root Cause Analysis — Why CQS Never Moves

**Date:** 2026-03-27
**Pattern:** Exploratory
**Models:** GPT-5.4 (neutral), Gemini 3.1 Pro (neutral), Claude Opus 4.6 (moderator + code verifier)
**Continuation ID:** `06acd7c0-fc3d-4945-8c81-a52b77a4eef5`
**Trigger:** 6 consecutive runs (007-012) with 0% KEEP rate despite fixing compiler (O12-O14), AI prompts (O15-O20), and in-memory config mutations (O21-O27). CQS stuck at 0.9121→0.9121.

## Context

After implementing Sessions 009-011 fixes, AI proposals compile correctly, apply to in-memory config correctly, and are semantically correct (100% as of Run 010). But when the modified config is passed to the Orchestrator for re-evaluation, the CQS score is **identically zero movement** — not even 0.0001 different.

Three failure modes observed in Run 012:
1. **ADD_STANDARDIZATION (formulas)** — GS:IntangibleAssets, HD:InterestExpense, CAT:AccountsReceivable all show 0.0000 CQS delta
2. **ADD_COMPANY_OVERRIDE (preferred_concept)** — MSFT:PropertyPlantEquipment causes PFE -100pp regression
3. **Cross-run inconsistency** — Same gaps, different proposals between runs

## GPT-5.4 (Practical Diagnosis)

- `_compute_sa_composite()` is extremely simplistic: sums absolute values of components only. No signs, weights, or required-component policy.
- Formulas are likely **being applied** but: (a) components missing in XBRL → composite=None, (b) abs-value sum similar to raw mismatch, (c) pass/fail unchanged
- Suspicious: `sa_pass = is_match` set before real SA computation. If SA compute fails, raw status persists — masking the failure
- MSFT→PFE: test for shallow-copy state bleed in `apply_change_to_config()` before blaming orchestrator logic
- Recommended: instrument 5 specific code locations with logging, run single-company A/B experiment
- Medium-term: formula model needs signs/weights to be useful

## Gemini 3.1 (Thorough Diagnosis)

- **CLAIMED** namespace prefix mismatch in `_compute_sa_composite()`: bare concept names fail `_extract_xbrl_value` lookup
- MSFT→PFE: SEC API rate limiting during full-cohort re-evaluation. New ReferenceValidator with empty cache → 429 → PFE validation fails
- Cross-run inconsistency: `_sec_facts_cache` permanently caches None on transient errors
- Recommended: add `us-gaap:` prefix fallback, global LRU cache for SEC facts, don't cache None on errors

## Our Diagnosis

### Agreements (all parties converge)

1. **The problem is in the evaluation layer, not the application layer.** Config changes ARE being applied correctly. The extraction engine receives the modified config. The issue is what happens during re-evaluation.
2. **`_compute_sa_composite()` is the primary failure point.** All parties agree this function needs instrumentation. It's a black box — we don't know if it returns None, computes a worse value, or computes a better value that doesn't cross a threshold.
3. **Diagnostic logging is the immediate next step.** Both models and our own analysis converge on adding logging to `_compute_sa_composite()`, the SA PROMOTE gate, and `_resolve_formula_components()`.

### Disagreements + Our Resolution

**Gemini's namespace hypothesis: WRONG (verified).** We read `_extract_xbrl_value` (reference_validator.py:1751) and `get_facts_by_concept` (facts.py:1240). The latter uses `re.compile(pattern, re.IGNORECASE)` — regex matching, not exact. Bare "Goodwill" WILL match "us-gaap:Goodwill". The namespace prefix is not the issue.

**Gemini's rate-limiting hypothesis for PFE: PLAUSIBLE but unverified.** The `evaluate_experiment_in_memory` code uses `compute_cqs_incremental` for company-scoped changes, which should only re-evaluate the target company. But we observed PFE being evaluated — this could be rate-limiting during the full pipeline, or a code path that falls through to full eval. Needs logging to confirm.

**GPT's shallow-copy concern: UNLIKELY.** `apply_change_to_config` uses `copy.deepcopy(config)` at the top — verified in the code. Deepcopy should prevent aliasing.

### Action Items

**O28 (P0): Diagnostic logging in `_compute_sa_composite()`**
- Log: components resolved, per-component extracted value (found/missing), composite value, ref value, variance, promotion decision
- This will instantly reveal whether formulas produce None, wrong values, or correct-but-not-better values

**O29 (P0): Diagnostic logging in SA PROMOTE gate**
- Log at reference_validator.py:1022: `variance_type`, whether SA PROMOTE fires, raw_variance vs formula_variance, promotion decision

**O30 (P1): Diagnostic logging in pre-screen path**
- Log which eval path (pre-screen only → DISCARD, incremental, full cohort)
- Log PFE-specific: why is PFE being re-evaluated for an MSFT-only change?

**O31 (P1): Fix whatever O28-O30 reveal**
- If components_found=0: the AI is proposing concepts that don't exist in filings → need existence validation in compile_action
- If composite computed but worse than raw: formula model needs improvement (signs/weights)
- If composite better but pass/fail unchanged: CQS weighting issue

**O32 (P2): Investigate PFE -100pp regression**
- Add logging to determine if incremental eval falls through to full eval
- If rate-limiting is confirmed: implement persistent SEC facts cache across evaluations

## Key Decisions

37. **Diagnostic-first approach for complex pipeline issues** — when CQS shows exactly zero movement, the root cause is not guessable from code reading alone. Instrument first, fix second (Session 012)
38. **`_compute_sa_composite()` is the next bottleneck** — formula pipeline is wired end-to-end on paper, but this function is a black box that needs transparency (Session 012)
39. **Gemini's namespace hypothesis was wrong** — `get_facts_by_concept()` uses regex matching, not exact. Bare names work. This validates the value of code verification over model speculation (Session 012)
