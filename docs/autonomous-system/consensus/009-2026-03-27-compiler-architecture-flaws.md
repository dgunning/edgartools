# Consensus Session 009: Architectural Flaws in AI-to-Extraction Pipeline

**Date:** 2026-03-27
**Pattern:** Exploratory
**Models:** GPT-5.4 (neutral/practical), Gemini 3.1 Pro (neutral/robust), Claude Opus 4.6 (moderator)
**Continuation ID:** `35d790f6-7f49-482f-b4a9-abb07d076867`
**Trigger:** Run 008 achieved 0% KEEP rate — AI discovers correct concepts but 100% of proposals have zero effect on extraction due to compiler layer bugs.

## Context

After implementing O10 (manifest caching) and O11 (deterministic downgrade) from Session 008, Run 008 showed the caching works (245s → 0s on cache hit) but the AI pipeline is completely broken: 3/3 proposals discarded with "target CQS not improved (X → X)" — scores IDENTICAL before and after applying AI proposals.

Investigation revealed two compiler-layer bugs and one filter bug:
1. **Namespace mismatch**: AI emits `us-gaap:GrossProfit`, compiler writes verbatim to `known_concepts`, but tree parser strips namespaces and matches bare names — the namespaced entry never matches.
2. **Wrong action type for high_variance gaps**: `MAP_CONCEPT` always compiles to global `ADD_CONCEPT`, but high_variance gaps already have a mapped concept. Adding another to the global list is a no-op because the tree parser returns the first match. Need company-scoped `ADD_COMPANY_OVERRIDE` with `preferred_concept` (Strategy 0).
3. **Actionability filter too restrictive**: 9 of 13 gaps (all unmapped) filtered as non-actionable, starving the AI pipeline of its best targets.

## GPT-5.4 (Practical Approach)

- Confirms these are compiler/schema alignment bugs, NOT model-quality problems — "technically easy to fix with low risk"
- **Canonical normalization helper**: Create shared utility used everywhere. Store bare names in `metrics.yaml`. Normalize at both compiler write and parser comparison boundaries.
- **Gap-aware compiler**: Extend `compile_action()` to accept optional gap context, or add wrapper `compile_action_for_gap(action, gap)`. Keep `TypedAction` unchanged.
- **Routing**: `MAP_CONCEPT` + unmapped → `ADD_CONCEPT` (global), `MAP_CONCEPT` + high_variance → `ADD_COMPANY_OVERRIDE` with `preferred_concept`
- **No new typed actions**: Adding `FIX_CONCEPT` would increase prompt complexity and failure surface. Compiler-owned scoping is more robust.
- **Actionability fix**: Default unmapped to actionable unless explicitly `engineering_backlog`. Current filter is starving the AI pipeline.
- **Implementation order**: (1) normalize → (2) routing → (3) filter → (4) tests
- **Long-term**: Add one canonicalization utility and enforce at all boundaries to prevent representation drift. Store both `raw_concept` and `canonical_concept` in logs for auditability.
- **Confidence**: 9/10

## Gemini 3.1 (Robust Approach)

- Calls this a **"Gap-Aware Smart Compiler"** architecture — AI expresses semantic intent, compiler handles namespace normalization and strategy routing
- **Compiler signature change**: `compile_action(action: TypedAction, gap: UnresolvedGap)` — this is "the crux of the architectural fix"
- **Namespace fix**: `.split(':')[-1]` at compiler edge, strictly. "Config must remain standard taxonomy-agnostic."
- **Same routing logic**: high_variance → `ADD_COMPANY_OVERRIDE`, unmapped → `ADD_CONCEPT`
- **Explicitly rejects dumb compiler alternative**: "Prompting LLMs to strictly adhere to formatting nuances is an anti-pattern — burns context tokens, invites hallucinations, and couples AI to engine internals"
- **Future-proofing**: If new strategies are introduced (e.g., Strategy -1), only compiler needs updating. AI vocabulary stays stable.
- **Actionability**: Unmapped gaps with missing `xbrl_value` are "prime targets for AI discovery", not unsolvable
- **Confidence**: 9/10

## Our Diagnosis

### Agreements (unanimous across all 3 perspectives)

1. **These are compiler bugs, not AI bugs** — the AI correctly identifies concepts. The pipeline breaks downstream.
2. **Keep `MAP_CONCEPT` as the single AI intent** — no new typed actions needed.
3. **Make compiler gap-aware** — pass gap context to `compile_action()` so it can route by gap type.
4. **Namespace normalization at compiler edge** — `.split(':')[-1]` before writing to config. Store bare names.
5. **Gap-type routing**: unmapped → `ADD_CONCEPT` (global), high_variance → `ADD_COMPANY_OVERRIDE` (Strategy 0).
6. **Fix actionability filter** — unmapped gaps are prime AI targets, not unsolvable.
7. **P0 priority** — this unblocks the entire AI autonomy pipeline.

### Disagreements

**None.** This is the most unanimous session in our history. Both GPT-5.4 and Gemini 3.1 independently arrived at the same architecture (gap-aware compiler), same fix (namespace strip + routing), same rejection of alternatives (no new actions, no dumb compiler), and same confidence (9/10).

### What We Learned

1. **The compiler is a semantic translation layer, not a pass-through** — it must understand the gap context to generate the correct config change. The old assumption (compiler = simple action→YAML mapping) was wrong.
2. **Representation boundaries cause silent failures** — the namespace mismatch produced zero errors, zero warnings, just a no-op. This class of bug needs boundary tests.
3. **The AI pipeline was never actually tested end-to-end through extraction** — we tested AI → config and config → CQS gate separately, but never verified that AI-written config changes actually alter extraction output. The namespace bug reveals this gap.
4. **O11 deterministic downgrade solves a real problem but couldn't activate** — it's designed for peer regression, which requires the proposal to at least help the target. These bugs prevented even that. O11 should become effective once the compiler bugs are fixed.

## Key Decisions

23. **Compiler must be gap-aware** — `compile_action(action, gap)` signature. AI emits semantic intent, compiler owns scope + namespace translation (Session 009)
24. **Namespace normalization at compiler boundary** — strip `us-gaap:` prefix via `.split(':')[-1]` before writing to any config. Bare names are the canonical form (Session 009)
25. **MAP_CONCEPT routes by gap type** — unmapped → global ADD_CONCEPT, high_variance → company-scoped ADD_COMPANY_OVERRIDE with preferred_concept (Session 009)
26. **Unmapped gaps are actionable by default** — only filter out engineering_backlog / forbidden-by-industry (Session 009)

## Action Items

- [ ] **O12: Namespace normalization** — Add `normalize_concept()` helper. Wire into `compile_action()` for MAP_CONCEPT. Strip `us-gaap:` prefix before writing to config.
- [ ] **O13: Gap-aware compiler routing** — Extend `compile_action(action, gap)` signature. Route MAP_CONCEPT: unmapped → ADD_CONCEPT, high_variance → ADD_COMPANY_OVERRIDE with preferred_concept.
- [ ] **O14: Actionability filter fix** — Update `capability_registry.py` to treat unmapped gaps as actionable when reference data exists.
- [ ] **O15: End-to-end extraction test** — Add test that verifies AI-written config changes actually alter extraction output (not just CQS gate). Prevent silent no-op regression.
- [ ] **Run 009** — Re-run E2E 10-company benchmark after O12-O14 to validate KEEP rate > 0%.
