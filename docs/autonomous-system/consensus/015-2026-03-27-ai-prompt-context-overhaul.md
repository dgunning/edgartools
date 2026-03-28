# Consensus Session 015: AI Prompt & Context Overhaul — Fixing the 25% Compile Rate

**Date:** 2026-03-27
**Pattern:** Exploratory
**Models:** GPT-5.4 (neutral/practical), Gemini 3.1 Pro (neutral/robust), Claude Opus 4.6 (moderator)
**Continuation ID:** 5b47500e-0e10-4f75-878a-5a2a079c284e
**Trigger:** Benchmark harness (O40) revealed that only 25% of AI responses would actually resolve gaps through the pipeline, despite 75% having the correct action type. Three systemic failures: scope hallucination, formula component bloat, and escalation blindness.

## Context

The prompt benchmark harness (O40, Consensus 014) was built and run E2E against Gemini Flash with 8 human-adjudicated gold cases. With the addition of compile validation — checking whether AI responses would actually produce valid config through `compile_action()` — the "fully correct" rate dropped from the naive 62.5% to just 25%. Three specific failure modes account for all failures:

1. **Scope hallucination (3 cases):** ADD_FORMULA responses invent scope values like `"balance_sheet"` or `"income_statement"` instead of the only valid values `"company"` or `"global"`. The prompt never tells the AI what scope values are valid.

2. **Formula component bloat (1 case):** XOM:GrossProfit gets 4 components summed together. The engine only sums; the AI doesn't understand this means subtraction formulas are impossible. The prompt says "formulas sum their components" but the AI ignores or misinterprets this.

3. **Escalation blindness (2 cases):** JPM (banking, null reference value) and GS (4 graveyard regressions) both get MAP_CONCEPT at 0.95 confidence. The prompt has no explicit escalation criteria.

## GPT-5.4 (Practical Approach)

- Architecture is NOT fundamentally flawed — targeted fixes at the action contract layer suffice (9/10 confidence)
- **Scope fix:** Dual defense — add enum constraint in `ACTION_VOCABULARY` description AND hard validation in `parse_typed_action()`. Don't rely on prompt wording alone.
- **Formula fix:** Update engine capabilities text to say "additive only, subtraction not inferred". Recommend <=2 components, hard reject >3.
- **Escalation fix:** Explicit rules in prompt, not hints. Escalate when: null `reference_value`, banking forbidden metrics, `graveyard_count >= 4` with semantic regressions.
- **Candidates:** Add solver-failure annotations — why deterministic solver rejected each candidate. Architecture docs already say "AI should judge, not rediscover."
- **Industry:** Add industry constraints section when `company_industry == "banking"`.
- **Two-pass:** Defer. Action type accuracy already 75%; bottleneck is param correctness, not classification.
- **Novel suggestion:** Parser should validate param *values* not just param *presence*. Current parser at `parse_typed_action()` only checks required params exist.
- 5 changes target 60%+: (1) vocab descriptions, (2) parser validation, (3) prompt examples+rules, (4) candidates annotations, (5) industry section.

## Gemini 3.1 Pro (Robust Approach)

- Scope hallucination is a "solved problem in the industry" — use enum constraints in JSON schemas (9/10 confidence)
- **Scope fix:** Show enum values directly IN the JSON response template: `"scope": "company" | "global"`. This is where the model looks when generating.
- **Formula fix:** Aggressive wording: "Formulas ONLY sum components. Maximum 2 components. If subtraction needed, DOCUMENT_DIVERGENCE or ESCALATE." Stronger than GPT's suggestion.
- **Escalation fix:** Same as GPT — explicit "Escalation Triggers" section with hard rules. Add negative examples (when to ESCALATE) as a proven technique.
- **Solver annotations:** Adopt the `context_enriched` variant's approach for production.
- **Two-pass:** Reject. Contemporary models handle single-pass correctly with robust JSON schemas.
- **Prompt bloat risk:** Acknowledged but manageable if rules are formatted as concise bullets.

## Our Diagnosis

### Agreements (all 3 perspectives converge)

All parties agree at 9/10 confidence on every major point — this is unusually strong convergence:

1. **The prompt is not broken — the action contract is.** The AI picks the right action 75% of the time. It just doesn't know how to fill in the params correctly because we never told it the constraints.

2. **Enum enforcement is the highest-ROI fix.** Showing `"scope": "company" | "global"` in the JSON template + parser validation = scope hallucination eliminated.

3. **Explicit escalation rules, not hints.** Three triggers: null `reference_value`, banking forbidden metrics, `graveyard_count >= 4`.

4. **Single-pass maintained.** Two-pass rejected unanimously — not worth the latency/cost for 75% action accuracy.

5. **Solver-failure annotations needed.** The AI is doing the solver's job of evaluating candidates. Tell it why the solver already rejected each candidate.

### Disagreements + Resolutions

**Component count limit:** Gemini says max 2, GPT says max 3 (hard reject >3). **Resolution: max 3.** Real patterns like `Goodwill + IntangiblesNet + OtherIntangibles` exist. But 4+ is always suspicious. Parser rejects >4 (already implemented in benchmark validator).

**Parser vs prompt emphasis:** GPT emphasizes parser enforcement as safety net. Gemini emphasizes JSON schema in prompt. **Resolution: both.** For the benchmark, prompt quality is what we measure. For production, parser validation is the safety net. They're complementary, not competing approaches.

### What We Learned

The benchmark harness proved its value immediately — it caught failures that 14 prior consensus sessions missed. The "semantic correctness" measurement from Consensus 010 was misleading because it didn't include compile validation. The real metric is "would this response actually fix the gap?" — and the answer was 25%, not the 100% we thought.

This is the exact pattern Consensus 014 predicted: "separate prompt quality measurement from CQS gate evaluation." The harness works.

## Key Decisions

- **Decision #46:** Keep single-pass prompt architecture. Reject two-pass. (Unanimous)
- **Decision #47:** Enforce ADD_FORMULA scope as enum `{"company", "global"}` in both prompt template AND `parse_typed_action()`. (Unanimous)
- **Decision #48:** Add explicit "Escalation Triggers" section with 3 hard rules: null reference, banking forbidden, graveyard >= 4. (Unanimous)
- **Decision #49:** Add ADD_FORMULA and ESCALATE worked examples to production prompt. (Unanimous)
- **Decision #50:** Add solver-failure annotations to candidates table in production. (Unanimous)
- **Decision #51:** Component count limit: 3 in prompt guidance, 4 hard reject in parser. (Compromise: GPT=3, Gemini=2)

## Action Items

- [ ] **O41: Tighten ACTION_VOCABULARY** — Update ADD_FORMULA description to include `scope: "company" or "global" only; formulas sum components only; max 3 components`
- [ ] **O42: Parser param validation** — In `parse_typed_action()`, add enum check for ADD_FORMULA.scope and component-count sanity (reject >4)
- [ ] **O43: Prompt overhaul** — In `build_typed_action_prompt()`:
  - Show scope enum in JSON template
  - Replace engine capabilities with explicit formula constraints
  - Add ADD_FORMULA worked example (scope="company", 2 components)
  - Add ESCALATE worked example (banking case)
  - Add "Escalation Triggers" section
- [ ] **O44: Industry constraints** — Add `_build_industry_constraints()` helper; inject when `company_industry == "banking"`
- [ ] **O45: Solver annotations** — Add solver-failure reason to candidates table in `_build_candidates_context()`
- [ ] **O46: Benchmark re-run** — After O41-O45, re-run benchmark with `--no-cache` to measure improvement. Target: 60%+ compile-valid, 50%+ fully correct.
