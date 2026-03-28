# Consensus Session 014: AI Prompt Benchmarking & Instruction Quality

**Date:** 2026-03-27
**Pattern:** Exploratory
**Models:** GPT-5.4 (neutral/practical), Gemini 3.1 Pro (neutral/robust), Claude Opus 4.6 (moderator)
**Continuation ID:** `10bcb2eb-98b7-4b0c-95c7-9e0d233ccf33`
**Trigger:** Run 010 achieved 100% semantically correct AI proposals but 0% KEEP rate. O33-O38 fixed pipeline blindness (MappingSource.OVERRIDE). User wants to benchmark prompt quality with hand-picked cases before iterating on prompt design.

## Context

The AI resolver (Gemini Flash via OpenRouter) receives a structured prompt with gap details, candidate concepts with extracted values, and returns TypedAction JSON. Run 010 showed a qualitative breakthrough — all proposals were semantically correct (e.g., Goodwill+IntangibleAssets for CAT, AccountsReceivableNet for HD) — but the CQS evaluation gate rejected every one (0% KEEP).

We identified six problems with the current prompt: semantic correctness repeated 3 times (signal fatigue), prescriptive gap_type_guidance (decision tree instead of guidance), generic role frame ("XBRL expert" not "semantic adjudicator"), missing solver-failure context per candidate, trivial worked example (XOM:GrossProfit), and pre-filtered candidates hiding information from the AI.

The question: should we benchmark prompt variants before rewriting, and what methodology should we use? Secondary: is this even a prompt problem, or is the CQS gate the real blocker?

## GPT-5.4 (Practical Approach)

- **Two-layer benchmark**: Score (a) model decision quality (human-adjudicated) and (b) system acceptance quality (CQS delta) separately.
- **10-15 stratified cases**: 3 unmapped-resolvable, 2 true divergence, 2 ESCALATE, 1-2 formula. Include easy and hard cases.
- **Graded correctness**: Fully correct / acceptable alternate / wrong but defensible / unsafe. Binary scoring hides signal.
- **Composite ranking**: 40% action accuracy + 25% concept accuracy + 20% CQS acceptance + 10% unsafe error penalty + 5% parse validity.
- **Five A/B tests in priority order**: (1) Add solver-failure reasons per candidate, (2) Remove prescriptive decision tree, (3) Reframe role as adjudicator, (4) Replace trivial worked example, (5) De-duplicate semantic warnings.
- **Critical first step**: Re-run Run 010 outputs through O33-O38 fixed pipeline. Some proposals may now KEEP without any prompt changes.
- **Pitfalls**: Overfitting to small set (keep holdout), benchmark gaming (weight outcomes not prose), conflating prompt and gate quality, selection bias (don't only test MAP_CONCEPT cases), candidate pre-filtering caps prompt performance.
- **DOCUMENT_DIVERGENCE**: Both prompt issue (prescriptive usage) AND architecture issue (CQS can't reward valid divergence). Benchmark separately with TP/FP adjudicated cases.
- **Confidence**: 9/10.

## Gemini 3.1 (Robust Approach)

- **"Fix CQS first"**: If 100% semantic correctness produces 0% KEEP, the prompt is already succeeding. The CQS gate is broken. Do not rewrite a winning prompt to satisfy a broken evaluator.
- **20-30 stratified cases**: Larger set needed for statistical validity. 5-10 cases risk overfitting.
- **Ground truth independent of CQS**: Define "correct" as exact match to intended TypedAction + concept. Do NOT use CQS delta as proxy for prompt quality while CQS is broken.
- **Attention dilution**: Triple semantic correctness warning causes over-indexing on caution rather than reasoning. De-noising is high priority.
- **Three A/B variants**: (A) De-noising (remove redundant warnings), (B) Context addition (solver failure reasons), (C) Complex few-shot example.
- **DOCUMENT_DIVERGENCE is fundamentally architectural**: CQS needs a state machine update — "relative exception" scoring mode when divergence is justified. A rigid gate will ALWAYS penalize divergence.
- **Don't optimize against broken evaluator**: Using CQS delta to score prompts when CQS is broken forces the LLM to learn the evaluator's flaws.
- **Confidence**: 9/10.

## Our Diagnosis

### Agreements (all 3 parties converge)
1. **Build a benchmark harness immediately** — no dissent from any model.
2. **Decouple prompt quality from CQS acceptance** — they are different questions that must be measured separately.
3. **Add solver-failure reasons to prompt** — both models rate this as the highest-value context addition.
4. **Replace trivial worked example** — XOM:GrossProfit teaches nothing about hard cases.
5. **DOCUMENT_DIVERGENCE has an evaluation architecture component** — CQS must handle justified divergence.
6. **Both at 9/10 confidence** — high agreement, high conviction.

### Disagreements + Resolution

**Fix prompt or fix gate first?**
- GPT: "Do both in parallel. Include CQS at 20% weight in benchmark."
- Gemini: "Fix CQS first. Don't contaminate prompt optimization with broken evaluator."
- **Resolution**: Gemini is more correct on sequencing. Step 0 is: re-run Run 010 outputs through O33-O38 fixed pipeline. This is free — we already have the outputs. If some proposals now KEEP, the gate was the primary blocker and prompt work becomes lower priority. Build the harness with human-adjudicated scoring ONLY (no CQS weight) until CQS is verified.

**Benchmark size?**
- GPT: 10-15 cases (fast iteration).
- Gemini: 20-30 cases (statistical validity).
- **Resolution**: Start with 12 cases (10 test + 2 holdout). Getting any harness running is more valuable than waiting for perfect coverage. Expand to 20+ after the first iteration proves the harness works and we have more adjudicated ground truth.

**Is CQS "broken"?**
- Gemini claims the evaluator is broken because it rejects correct proposals.
- Reality is more nuanced. CQS is working correctly for what it measures (EF + SA combined). The issue is that SA (does it match yfinance?) and EF (is it the right concept?) are conflated. A correct concept (EF pass) that yfinance aggregates differently (SA fail) gets a negative CQS delta. This is Key Decision #43 from Session 013: "EF and SA should be decoupled long-term." CQS isn't broken — it's measuring the wrong composite for this use case.

## Key Decisions

44. **Do not optimize prompts against a broken evaluator** — verify evaluator behavior first (re-run through fixed pipeline), then iterate on prompts with human-adjudicated ground truth.
45. **Benchmark harness scores semantic correctness independently of CQS** — action accuracy and concept accuracy measured against human ground truth, not CQS delta.
46. **DOCUMENT_DIVERGENCE needs a CQS exception mode** — if AI proposes justified divergence with valid rationale, CQS must not penalize under strict matching. This is an evaluation architecture change, not a prompt change.

## Action Items

- [ ] **O39: Re-run Run 010 outputs through fixed pipeline** — verify whether O33-O38 gate fix alone converts any 0% KEEP to positive KEEP.
- [ ] **O40: Build benchmark harness** — 12 human-adjudicated gold cases (10 test + 2 holdout), stratified by action type: 4 MAP_CONCEPT, 3 DOCUMENT_DIVERGENCE, 2 ESCALATE, 2 ADD_FORMULA, 1 FIX_SIGN. Score: action accuracy + concept accuracy + graded correctness. No CQS weight initially.
- [ ] **O41: CQS DOCUMENT_DIVERGENCE scoring mode** — when AI proposes justified divergence (known_divergences in config), CQS scores it as "explained" rather than "failed."
- [ ] **O42: Prompt A/B — solver-failure annotation** — add per-candidate "why deterministic solver couldn't use this" column to evidence table.
- [ ] **O43: Prompt A/B — remove prescriptive tree + reframe role** — replace gap_type_guidance decision tree with softer tradeoff description. Reframe role as "semantic adjudicator."
- [ ] **O44: Prompt A/B — replace worked example + de-duplicate warnings** — hard case example (DOCUMENT_DIVERGENCE or ADD_FORMULA). Collapse 3x semantic warnings to 1.
