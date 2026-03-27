# Consensus Session 013: Pipeline Architecture Flaws — Why Correct AI Proposals Produce Zero Score Movement

**Date:** 2026-03-27
**Pattern:** Exploratory
**Models:** GPT-5.4 (neutral/practical), Gemini 3.1 Pro (neutral/robust), Claude Opus 4.6 (moderator)
**Continuation ID:** `edb0fb8f-3b1e-4124-8021-f61b882a865c`
**Trigger:** End-to-end diagnostic proved that semantically correct AI proposals produce exactly zero CQS delta due to `MappingSource.CONFIG` overload masking improvements in the validator and scorer.

## Context

The autonomous XBRL extraction system has been stuck at EF-CQS=0.6349 (target: 0.95) for 4 consecutive runs (007-010), with zero proposals accepted. Run 010 proved AI proposals are now semantically correct, yet CQS evaluation shows no improvement.

A diagnostic script (`scripts/diagnose_pipeline.py`) traced HD:InterestExpense through the full pipeline and confirmed: Strategy 0 finds the proposed concept in calc trees, returns `source=MappingSource.CONFIG`, and the validator skips all validation (returns `is_valid=True, status="excluded"`). CQS delta: exactly 0.0000.

Three architectural flaws were identified:
1. `MappingSource.CONFIG` overload (excluded metrics + company overrides both skip validation)
2. Strategy 0 silent fallthrough (no warning when preferred_concept not found)
3. AI resolver duplicates deterministic solver work (same `discover_concepts()` candidate pool)

## GPT-5.4 (Practical Stance)

- Fix Flaw 1 first: add `MappingSource.OVERRIDE` enum. Treat overrides as normal extracted mappings, not exclusions. This is better than validator-only heuristics because it restores semantic clarity at the source.
- Strategy 0 already has facts fallback (line 154-166). The real problem is silent ambiguity, not narrowness. Fix: structured warning on miss + upstream preflight rejection.
- AI role: deterministic solver owns name similarity, fact lookup, reverse value search, subset algebra. AI owns only: semantic choice among ambiguous candidates, DOCUMENT_DIVERGENCE vs remap decisions, company-specific formula design, cross-statement business reasoning, extension concept routing.
- Practical change: stop sending AI the full candidate universe. Send only ambiguous survivors + why deterministic rejected them. Forbid pure re-routes of already-tried concepts.
- Two fundamental assumptions to revisit: (a) config-only autonomy may not reach 0.95 EF, (b) source enum conflates provenance, applicability, and validation mode — need orthogonal fields.
- Long-term: separate provenance, applicability, validation evidence tier, and publication confidence into independent axes.
- **Confidence: 9/10**

## Gemini 3.1 Pro (Robust Stance)

- Unanimous on `MappingSource.OVERRIDE` — "highly feasible and computationally trivial."
- Stronger position on Strategy 0: unmatched preferred_concept should return HARD FAILURE (`ConfidenceLevel.INVALID`), not silently cascade to Strategy 1. Falling back to generic matching when AI requested a specific concept is an anti-pattern.
- Calc trees are "notoriously incomplete" in SEC filings. Overrides should have absolute primacy — extract value from presentation linkbase, calculation linkbase, or raw facts. Don't require calc tree presence.
- AI should be restricted to: semantic judgment, DOCUMENT_DIVERGENCE classification, sign/scale nuances. "If the subset-sum deterministic solver fails to find a numeric match, the AI—constrained by the exact same numeric reality—cannot magically conjure one."
- Novel insight — **Decoupled Verification Track**: separate EF verification (correct GAAP concept?) from SA verification (matches yfinance aggregate?). Currently conflated — correct XBRL mappings can fail CQS gates because yfinance aggregates differently.
- yfinance variance bounds are still gating EF even with SEC-native primacy. Need to rethink the hierarchy.
- **Confidence: 9/10**

## Our Diagnosis

### Agreements (unanimous)
1. **Add `MappingSource.OVERRIDE`** — highest-impact, fastest unblock. All 3 perspectives agree.
2. **AI must not duplicate deterministic work** — refocus AI on semantic judgment, divergence classification, formula authoring.
3. **Strategy 0 failures must be observable** — no silent fallthrough.
4. **Calc tree dependency too narrow for overrides** — facts-based overrides should work.

### Disagreements + Resolutions
- **Strategy 0 failure mode**: GPT-5.4 favors warning + preflight rejection; Gemini favors hard failure.
  - **Resolution**: Hard failure when `preferred_concept` is explicitly set but not found in calc trees OR facts. This prevents silent no-ops. But: only for the override path — don't break the general Strategy 1→2→3 fallthrough for normal extraction.

- **Decoupled Verification Track** (Gemini): Separate "did we find the right GAAP concept?" from "does it match yfinance?"
  - **Resolution**: Correct long-term direction but Phase 2 work. The current EF/SA split in the two-score architecture was designed for this, but the code conflates them. Defer to after the OVERRIDE fix proves the pipeline works end-to-end.

### What We Learned
1. The `source` enum is doing too much work — it encodes provenance (where the mapping came from), policy (should it be validated?), and applicability (is the metric relevant?). These need to be separate axes eventually.
2. The AI's value is not in finding concepts — the deterministic solver already exhausted that search space. The AI's value is in making judgment calls the deterministic solver cannot: "is this the RIGHT concept semantically?" and "should we accept this divergence?"
3. Four runs of infrastructure debugging (007-010) without a single KEEP result is a clear signal that the measurement layer was broken, not the proposal layer.

## Key Decisions

39. **`MappingSource.OVERRIDE` is mandatory** — company overrides must be validated against reference data, not auto-passed. This is a Tier-2 Python change that unlocks Tier-1 config optimization. (Session 013)
40. **Strategy 0 hard failure on missing override** — if `preferred_concept` is set but not found in calc trees or facts, return `ConfidenceLevel.INVALID` with explicit reasoning. Do not silently fall through to Strategy 1. (Session 013)
41. **AI resolver role is semantic adjudication, not concept hunting** — deterministic solver owns discovery; AI owns judgment (DOCUMENT_DIVERGENCE, semantic choice among ambiguous candidates, formula design). AI prompt should include WHY deterministic rejected each candidate. (Session 013)
42. **Overrides should search facts, not just calc trees** — calc linkbases are notoriously incomplete. Override primacy means the concept is searched across all available data sources before declaring failure. (Session 013)
43. **EF and SA verification should be decoupled long-term** — "correct GAAP concept" (EF) and "matches yfinance aggregate" (SA) are different questions. Conflating them causes correct extractions to fail CQS gates. Defer to Phase 2. (Session 013)

## Action Items

- [ ] O33: Add `MappingSource.OVERRIDE` to `models.py` enum. Update TreeParser Strategy 0 (lines 143, 157) to use OVERRIDE instead of CONFIG.
- [ ] O34: Update `reference_validator.py` (line 851) to only skip validation for CONFIG (exclusions), not OVERRIDE. OVERRIDE flows through normal validation.
- [ ] O35: Update `auto_eval.py` `_compute_company_cqs()` (line 1034) to only auto-credit CONFIG (exclusions). OVERRIDE metrics scored normally.
- [ ] O36: Add Strategy 0 hard failure — if preferred_concept set but not found in calc trees or facts, return MappingResult with ConfidenceLevel.INVALID and explicit reasoning.
- [ ] O37: Add logging to Strategy 0 — warn when override falls through to facts, error when not found anywhere.
- [ ] O38: Re-run HD:InterestExpense diagnostic after O33-O35 to verify CQS now shows delta.
- [ ] O39: Refocus AI prompt — include deterministic rejection reasons, forbid re-proposing tried concepts, emphasize DOCUMENT_DIVERGENCE and semantic judgment.
- [ ] O40: Run closed-loop eval on 10-company cohort after fixes to verify >0 KEEP results.
