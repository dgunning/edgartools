# Consensus Session 007: Value-Grounded AI Consultation Architecture

**Date:** 2026-03-26
**Pattern:** Champion (Option A vs Option B)
**Models:** GPT-5.4 (neutral/Option A), Gemini 3.1 Pro (neutral/Option B), Claude Opus 4.6 (moderator)
**Continuation ID:** f07f3c73-e055-445d-9008-66747eb90799
**Trigger:** 10-company E2E test showed 80% resolution rate but 0% KEEP rate. AI proposes real concepts that exist in filings but don't resolve the variance. Root cause: AI never sees what numerical value a concept extracts.

## Context

After implementing O1-O6 pipeline optimizations (Session 006), a 10-company E2E test revealed the core bottleneck: the AI is "concept-blind." It picks semantically plausible concepts (e.g., `us-gaap:IntangibleAssetsNetExcludingGoodwill` for GS:IntangibleAssets) but doesn't know whether that concept extracts $5B or $500M. All 4 proposals were pre-screen DISCARD with "CQS not improved." The 5th gap (XOM:GrossProfit) correctly ESCALATED because the concept genuinely doesn't exist in the filing.

The question: should we enrich the remote API prompt with extracted values (Option A), or deploy local agents with direct filing access for interactive hypothesis testing (Option B)?

## GPT-5.4 (Champion: Option A — Enriched Remote API)

- The 0% KEEP rate is an **information deficiency**, not a reasoning deficiency — AI picks semantically correct but numerically wrong concepts because it never sees extracted values
- Proposed a **precomputed evidence table**: `concept | extracted_value | delta_pct | evidence_tier | parent | children_count | tried_by_solver`
- Implementation estimate: **1-3 days** for Option A vs 1-2 weeks for Option B
- Option A **preserves the clean typed-action/deterministic-compiler architecture**
- Option B appropriate as **tier-2 escalation for C3 gaps** (extension concepts, dimensional nuance)
- Budget math: Option B at $0.10-0.50/gap would consume most of the $5/session budget
- Industry best practice: **constrained AI with grounded evidence** for 80% path, agentic for exceptions
- `CandidateConcept.tree_context` already exists but isn't included in prompts
- **Confidence: 8/10**

## Gemini 3.1 (Champion: Option B — Local Agents)

- XBRL alignment is an **empirical debugging problem**, not text classification — needs hypothesis testing
- **Reverse number search**: search `facts_df` for the target reference VALUE, not just concept names. This is the killer insight — Option A can't find concepts whose names don't match but whose values do
- Pre-computing values for ALL candidates in Option A is **wasteful** — runs the extraction engine heavily during prompt building
- Existing tool infrastructure (`discover_concepts`, `verify_mapping`) already exists for local agents
- Two-tier triage: **Option A for cheap first-pass, Option B only for remaining hard gaps**
- Strict **iteration caps (3-5 tool calls per gap)** to stay within budget
- Long-term: **extension concepts will permanently cap out semantic matching**
- **Confidence: 9/10**

## Our Diagnosis

### Agreements (all three perspectives converge)

1. **The AI is concept-blind** — the current prompt gives names without values, causing semantically correct but numerically wrong proposals
2. **Two-tier architecture is correct** — cheap API for standard gaps, expensive agents for hard residuals
3. **Budget/speed constraints favor API-first** — local agents cannot be the default path at $0.10-0.50/gap
4. **The typed action + CQS gate architecture stays** — neither option changes the safety model

### Disagreements + Resolution

**GPT-5.4 says** the evidence table (precomputed values) is sufficient for most gaps.
**Gemini says** precomputing is wasteful and reverse number search requires interactive agents.

**My resolution:** Both miss the optimal middle ground. The real answer is **improving the deterministic layer** — neither Option A nor Option B in isolation:

1. **Enhance `discover_concepts()` with value-aware ranking** — don't just match by name similarity; also run `verify_mapping()` on the top 3-5 candidates and include extracted values. This is ~2-3 seconds per candidate, not "running the full extraction engine." Total: ~30-45 seconds per gap for 5 candidates.

2. **Add reverse value search** (Gemini's killer insight) — search the facts DataFrame for concepts whose value is within 20% of the reference value. This catches obscure extension concepts that semantic matching would never find. This is a deterministic operation that belongs in `discover_concepts()`, not in an agent loop.

3. **Format as GPT-5.4's compact evidence table** in the prompt — the AI then ranks verified candidates, not blind guesses.

This creates a **three-tier dispatch**:
- **Tier 0** (deterministic): Value-aware `discover_concepts()` with reverse search. If a candidate matches within tolerance → auto-resolve without AI. Cost: ~0.
- **Tier 1** (enriched API): Gemini Flash with evidence table. Cost: ~$0.001/gap.
- **Tier 2** (local agent): For hard gaps after Tier 1 fails. Cost: ~$0.10-0.50/gap, max 5 iterations.

### What We Learned

- **Reverse number search is a deterministic operation, not an AI operation.** Searching facts for `|value - reference| < 20%` is a DataFrame filter, not something that needs interactive agents. This should be added to Layer 2 (Facts Search) of the multi-layer mapping engine.
- **The boundary between "enriched prompt" and "agent tool use" is actually "precomputed verification."** If we verify candidates before prompting, we get 80% of the agent benefit at API cost.
- **The deterministic solver hasn't actually reached its ceiling** — it reached the ceiling of *name-based* discovery. Value-based discovery is a new capability that could resolve gaps without any AI at all.

## Key Decisions

17. **Value-grounded prompts are mandatory** — AI must see `concept | extracted_value | delta_pct` for every candidate, not just name/confidence (Session 007)
18. **Reverse value search belongs in the deterministic layer** — search facts for concepts matching the reference value as a DataFrame filter in discover_concepts(), not as an agent operation (Session 007)
19. **Three-tier dispatch: deterministic → enriched API → local agent** — value-aware discovery first, Gemini Flash with evidence table second, local agents only for residuals (Session 007)

## Action Items

- [ ] **O7: Value-aware candidate enrichment** — In `_format_candidate_concepts()`, call `verify_mapping()` for each candidate and include extracted value + delta in the prompt table. ~1 day.
- [ ] **O8: Reverse value search in discover_concepts()** — Add a new search mode: find concepts in facts_df whose annual value is within 20% of the reference value. Return as additional CandidateConcept entries with source="value_match". ~1 day.
- [ ] **O9: Auto-resolve from value search** — If Tier 0 finds a concept with <2% variance from reference, skip AI entirely and emit a typed action directly. ~0.5 day.
- [ ] **Benchmark: 10-company E2E with enriched prompts** — Run the same 10 companies and measure KEEP rate improvement. Target: >25% KEEP rate (up from 0%).
- [ ] **Tier 2 design (deferred)** — If enriched prompts still have >50% DISCARD rate, design the local agent escalation path with 5-iteration cap.
