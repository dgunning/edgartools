# Consensus Session 016: Formula Engine Limitations & Auto-Solver Quality

**Date:** 2026-03-28
**Pattern:** Exploratory
**Models:** GPT-5.4 (neutral/practical), Gemini 3.1 Pro (neutral/robust), Claude Opus 4.6 (moderator)
**Continuation ID:** `73e496f4-f35c-4a18-bc02-09703b72814b`
**Trigger:** O47-O48 investigation uncovered that `_compute_sa_composite` uses `abs(val)` (addition only), 97/101 auto-solver overrides were garbage, and AI proposals are semantically correct but can't pass the evaluation gate.

## Context

After 10 runs with a 0% KEEP rate (runs 006-010), deep investigation for the O47-O48 plan revealed three interconnected problems blocking progress:

1. **Formula engine can only add**: `_compute_sa_composite` at `reference_validator.py:2391` uses `composite += abs(val)`, making subtraction-based metrics (GrossProfit = Revenue - COGS, FreeCashFlow, WorkingCapital, NetDebt) structurally impossible via config. These are handled by hardcoded `industry_logic` instead.

2. **Auto-solver produces 96% garbage**: 97 of 101 company_overrides in metrics.yaml were coincidental numeric matches from 5 auto-solver sessions (Mar 20-26), all failing validation ("0/3 companies"). Examples: `KO:TotalLiabilities = BeverageServingsConsumedPerDay + AdvertisingExpense`. All 97 were removed in O48.

3. **AI quality vs gate quality mismatch**: Run 010 confirmed AI proposals are 100% semantically correct (e.g., `Goodwill + IntangibleAssetsNetExcludingGoodwill` for CAT:IntangibleAssets). But the evaluation gate rejects them because the formula engine can't compute subtraction, and company-scoped overrides leak across tickers.

Current numbers: CQS 0.912, EF-CQS 0.635, SA-CQS 0.602 — all stuck across 10 runs.

## GPT-5.4 (Practical Stance)

- **Highest priority: signed SA formulas.** Support weighted components via objects like `{concept: X, weight: -1.0}`. Backward-compatible: bare strings default to `weight: +1.0`. Low risk, small surface area.
- **Kill brute-force subset-sum.** Replace with a **constrained candidate selector**: statement-family hard filter, concept-class filter, semantic blacklist/whitelist, peer-pattern prior, multi-period consistency, minimum evidence threshold. No evidence = no proposal.
- **Split company_overrides into 3 typed namespaces**: (a) `preferred_concept` for extraction overrides, (b) `standardization_overrides` for company-specific aggregation formulas, (c) `known_divergences` for "concept correct, vendor different" cases.
- **Industry perspective**: Bloomberg/FactSet use taxonomy-aware rules, not numeric matching. Current brute-force solver is opposite of best practice.
- **Don't optimize prompts against a broken evaluator** — Run 010 already proved AI quality is sufficient.
- **EF-CQS path**: Signed formulas → divergence exception → semantic solver → curated templates. Expects 0%→20-40% KEEP quickly, EF-CQS 0.63→0.72-0.78 in next phase. 0.80+ needs curated patterns, not just autonomous exploration.
- **Confidence: 9/10.**

## Gemini 3.1 (Robust Stance)

- **`abs(val)` violates fundamental accounting principles.** Replace with config-driven `composite += (val * weight)`. Notes that `metrics.yaml` already has `weight: -1.0` patterns in `tree_hints` (e.g., Capex).
- **Constrain auto-solver topologically**: Only sum items sharing a common parent in the SEC calculation linkbase, or same `statement_family`. Brute-force subset-sum "statistically guarantees coincidental matches."
- **Override isolation bug identified**: Company-scoped overrides causing cross-company regressions indicates the config compiler or ReferenceValidator is flattening definitions globally. Fix: strictly isolate per-ticker during LIS gate evaluation.
- **Graveyard replay strategy**: Once formula engine is fixed, replay recent AI proposals from the graveyard — the 100% semantically correct Run 010 proposals should now KEEP.
- **Three-phase path**: (1) Fix evaluator, (2) Apply topological constraints, (3) Implement DOCUMENT_DIVERGENCE exception mode.
- **Confidence: 9/10.**

## Our Diagnosis

### Agreements (all 3 models converge)

1. **Fix `_compute_sa_composite` immediately** — Replace `composite += abs(val)` with `composite += (val * weight)`. This is the single highest-leverage change. Unanimous, 9/10 confidence.
2. **Kill brute-force subset-sum solver** — Replace with semantically constrained candidate selection. No evidence → no proposal. Unanimous.
3. **Don't optimize prompts — fix the evaluator** — Run 010 proved AI quality is sufficient. The bottleneck is a broken evaluation pipeline. Unanimous.
4. **DOCUMENT_DIVERGENCE exception needed** — Semantically correct concepts that differ from yfinance methodology shouldn't penalize scores. Unanimous.
5. **0.80+ EF-CQS requires evaluator fixes AND curated patterns** — Autonomous exploration alone won't get there. Unanimous.

### Disagreements + Resolutions

**Override abstraction**: GPT-5.4 says split into 3 typed namespaces; Gemini says keep but fix isolation.
- **Resolution**: Gemini is right for the short term — the per-ticker isolation bug is the urgent fix. GPT's 3-type split is the correct long-term target but can wait. We already have `known_divergences`, so the split is underway.

**Solver constraints**: Gemini suggests topological (calc linkbase parents); GPT suggests broader semantic constraints.
- **Resolution**: Both are correct at different layers. Use `statement_family` from `tree_hints` as the hard filter now (simpler, already available in metrics.yaml), add calc-tree adjacency later as a refinement.

### What We Learned

1. **Safety measures become structural limitations** — `abs(val)` was a safety guard against negative composites that became the primary blocker. When adding safety constraints, ask: "Will this prevent correct behavior too?"
2. **Brute-force numeric matching is anti-pattern** — The auto-solver finding `BeverageServingsConsumedPerDay` as a TotalLiabilities component proves that numeric coincidence is meaningless without semantic context. Financial data systems MUST use taxonomy-aware rules.
3. **Evaluation pipeline correctness gates AI pipeline progress** — No amount of AI prompt tuning helps when the evaluator can't recognize a correct answer. Fix the judge before coaching the student.
4. **Graveyard contains value** — After fixing the evaluator, previously rejected proposals may now be valid. Don't just fix forward; replay the recent graveyard.

## Key Decisions

- **#46**: Signed components in `_compute_sa_composite` — add `weight` field to component config, `composite += (val * weight)`, backward-compatible bare strings default to +1.0. (UNANIMOUS)
- **#47**: Kill brute-force auto-solver — replace with semantically constrained selector using statement_family hard filter. No evidence threshold met → emit no proposal. (UNANIMOUS)
- **#48**: Fix evaluator before further prompt tuning — AI quality is proven sufficient (Run 010). (UNANIMOUS)
- **#49**: Graveyard replay after formula engine fix — re-evaluate Run 010 proposals. (Gemini-originated, all agree)

## Action Items

- [ ] **Signed formula engine**: Add `weight` field to component config in metrics.yaml, update `_resolve_formula_components()` and `_compute_sa_composite()` to use `val * weight`. Preserve backward compatibility.
- [ ] **Fix override isolation**: Ensure per-ticker isolation during LIS evaluation — overrides for ticker A must not affect ticker B's validation.
- [ ] **DOCUMENT_DIVERGENCE exception mode**: Semantically correct concepts that differ from yfinance shouldn't penalize CQS.
- [ ] **Solver semantic constraints**: Add `statement_family` hard filter to auto-solver. Disable brute-force subset-sum.
- [ ] **Graveyard replay**: After formula engine fix, re-evaluate Run 010 AI proposals that were previously rejected.
- [ ] **(Later) Split override types**: Evolve `company_overrides` into `preferred_concept` / `standardization_overrides` / `known_divergences` as separate config namespaces.
