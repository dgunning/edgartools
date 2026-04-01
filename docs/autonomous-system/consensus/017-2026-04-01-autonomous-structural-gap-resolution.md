# Consensus Session 017: Making the System Truly Autonomous — Resolving Structural Gaps

**Date:** 2026-04-01
**Pattern:** Exploratory
**Models:** GPT-5.4 (neutral/practical), Gemini 3.1 Pro (neutral/robust), Claude Opus 4.6 (moderator)
**Continuation ID:** `c91c90e7-8886-4df2-9893-d40f31a27958`
**Trigger:** Graveyard replay broke 0% KEEP rate (17/36 flipped), but 8 structural gaps remain that block full autonomy. Need architectural guidance on resolving all gap categories.

## Context

The autonomous XBRL extraction system broke the 0% KEEP rate via graveyard replay — 17/36 previously rejected proposals flipped to KEEP with the signed formula engine (Consensus 016). CQS improved from 0.8224 → 0.8237 after semantic review.

However, after exhausting both deterministic solvers and AI proposals on the 5-company eval cohort (AAPL, JPM, XOM, WMT, JNJ), 8 gaps remain in 4 categories: (1) missing XBRL concepts requiring computation (WMT:GrossProfit, WMT:TotalLiabilities, XOM:OperatingIncome, XOM:GrossProfit), (2) yfinance aggregation differences (JNJ:Capex, WMT:IntangibleAssets), (3) industry structural exclusions (JPM:CurrentAssets), and (4) gate blocking valid proposals (JPM:ShareRepurchases — EF-CQS regression blocks all JPM changes).

The AI pipeline works end-to-end (5 proposals generated at $0.008 cost) but proposals are rejected by the CQS gate. AI proposals are 100% semantically correct (Run 010) — the bottleneck has shifted entirely to the evaluation architecture.

## GPT-5.4 (Practical Approach)

- **Verdict:** 95% autonomous resolution is technically feasible, but requires Tier-2 architectural upgrades, not smarter AI. "The biggest blocker is not extraction logic; it is evaluation architecture."
- **Evidence Pack:** Extend pre-dispatch discovery so AI sees calc tree parents/children with weights/signs, facts, statement family, value matches, standard vs extension flag. AI ranks candidates; never invents names.
- **Derivation Planner:** Deterministic planner emitting formula candidates from accounting identities (GrossProfit = Revenue - COGS variants, TotalLiabilities = Assets - Equity). Output typed `ADD_STANDARDIZATION` actions.
- **Three Terminal States:** Every gap resolves to Mapped (EF pass), Derived (formula/identity), or Divergent/Inapplicable (documented, non-penalized SA). Make `DOCUMENT_DIVERGENCE` produce neutral SA outcome.
- **Gate Policy by Gap Class:** Universal gate too rigid. Policy branching: banks (suppress EF-CQS global regression unless affected cells changed), exclusions/divergences (KEEP on "problem count reduced"), single-company (impacted cell set comparison).
- **Industry Perspective:** Bloomberg/FactSet mark bank current assets as non-applicable, not "failed." Oil gross profit treated as unsupported. Stop conflating "correct XBRL extraction" with "matches vendor aggregate."
- **Architecture:** evidence pack → derivation planner → action compiler → class-aware gate → terminal outcome registry.
- **Confidence:** 8/10

## Gemini 3.1 (Robust Approach)

- **Verdict:** System is highly advanced but blocked by rigid, conflated evaluation gate (EF vs SA overlap) and single-shot AI paradigm. "The codebase contains all the hooks to resolve them."
- **Reward Divergences in LIS:** Modify `compute_lis()` to award points when gap transitions from "mismatch" to validated `DOCUMENT_DIVERGENCE` or `ADD_EXCLUSION`. LIS currently requires numerical proximity, which inherently fails structurally inapplicable metrics.
- **Iterative AI Discovery (ReAct):** Instead of 10-candidate snapshot, equip AI with `Query_Calculation_Tree` tool. Single-shot guessing will never work for unpredictable naming conventions (`CostOfRevenue`, `xom:ProductionAndManufacturingExpenses`).
- **Decouple EF and SA:** Stop rejecting proposals via EF-CQS when SA-CQS fails. If concept mapping is correct (EF=Pass), don't revert because yfinance disagrees (SA=Fail).
- **Industry Sandboxing:** Use `industry_metrics.yaml` to preemptively exclude inapplicable metrics BEFORE auto-eval loop.
- **Deterministic Tree Inference:** Enhance deterministic layer to perform subset-sum across hierarchical child nodes in calculation tree. If WMT has Revenue and CostOfRevenue as children, infer GrossProfit deterministically without LLM hallucination risk.
- **Long-term Warning:** If EF/SA coupling not resolved, KEEP rate will eventually drop to 0% again — "every semantic fix will be rejected for failing to hit a derived data provider's arbitrary target."
- **Confidence:** 9/10

## Our Diagnosis

### Agreements (all 3 parties)

1. **Gate architecture is the #1 blocker**, not AI quality or extraction logic. The evaluation conflates "correct XBRL extraction" (EF) with "matches yfinance aggregate" (SA), systematically rejecting semantically correct proposals.
2. **Divergence and exclusion must be first-class terminal outcomes** with positive LIS scoring. Currently they're dead on arrival because the gate requires numerical improvement.
3. **AI must never invent concept names.** Filing-aware discovery (calc trees + facts + reverse value search) must precede any proposal.
4. **A derivation planner using accounting identities** is needed as a deterministic engine — GrossProfit = Revenue - COGS, TotalLiabilities = Assets - Equity.
5. **EF and SA must be decoupled in the gate** — a correct EF mapping should not be rejected because SA disagrees with yfinance.
6. **Industry auto-exclusion should happen before the eval loop**, not as a proposal that fails the gate.

### Disagreements + Our Resolution

**GPT-5.4: "Evidence pack" (enrich prompts)** vs **Gemini 3.1: "ReAct loop" (interactive tools)**

GPT-5.4 proposes pre-computing a rich evidence pack (calc tree edges, value matches, statement family) and feeding it to the AI upfront. Gemini proposes giving the AI interactive tools to query the calculation linkbase dynamically.

**Our resolution: Start with evidence pack, evolve toward ReAct.** The evidence pack is implementable in 1 session and solves 80% of the discovery problem. The ReAct loop is architecturally better for 500-company scale but requires more engineering (tool creation, sandbox environment). Do evidence pack now (O56), add ReAct as M4.x milestone.

**GPT-5.4: "Deterministic derivation planner"** vs **Gemini 3.1: "Tree inference engine"**

Both converge on deterministic accounting identity resolution but frame it differently. GPT-5.4 envisions a standalone planner; Gemini envisions enhancing the existing tree parser with subset-sum across child nodes.

**Our resolution: Both are the same thing.** Implement as an extension to the tree parser that recognizes missing parent nodes and computes them from children when an accounting identity applies. This is already partially present in `auto_solver.py` — extend it with identity-aware search.

### Action Items (Priority-Ordered)

These are the O53-O58 action items from this consensus:

- [ ] **O53: Decouple EF/SA in gate** — In `auto_eval_loop.py`, stop using combined EF-CQS for regression checks. If a proposal improves EF (correct concept), don't reject it because SA (yfinance match) regressed. Use EF-only regression check for concept changes, SA-only for formula changes.
- [ ] **O54: LIS rewards divergence/exclusion** — Modify `compute_lis()` to return positive delta when a gap transitions from "mismatch/unmapped" to "documented divergence" or "valid exclusion." This unblocks JNJ:Capex, WMT:IntangibleAssets, JPM:CurrentAssets.
- [ ] **O55: Derivation planner** — Deterministic engine that emits formula candidates from accounting identities using the company's actual XBRL concepts. GrossProfit = [company's Revenue concept] - [company's COGS concept]. Discovers concepts from calc tree, not from guessing. Unblocks WMT:GrossProfit, WMT:TotalLiabilities.
- [ ] **O56: Evidence pack for AI prompts** — Enrich gap manifest with calc tree parents/children/weights/signs, nearest facts, statement family, value matches, standard-vs-extension flag. Replaces concept name guessing.
- [ ] **O57: Industry pre-exclusion** — Before gaps enter the auto-eval loop, check `industry_metrics.yaml` and auto-exclude structurally inapplicable metrics (GrossProfit for energy, CurrentAssets for banks). Avoids gate evaluation entirely.
- [ ] **O58: Per-metric gate isolation** — Replace global EF-CQS regression check with impacted-cell regression check. Only re-evaluate the target metric and its dependents, not all 37 metrics. Unblocks JPM proposals.

### What We Learned

1. **The system's primary failure mode shifted from "wrong AI proposals" to "correct proposals rejected by rigid gates."** This is a sign of system maturity — the AI side works, the evaluation side needs to catch up.
2. **Resolution is not binary (match/fail).** A mature financial data system has 4 terminal states: mapped, derived, divergent, inapplicable. All 4 must be scored positively.
3. **yfinance is corroboration, not truth.** The system should extract correct XBRL data and *explain* any yfinance differences, not force-fit to yfinance.
4. **The "weights not code" constraint still holds** — all 6 action items are config/gate changes, no extraction engine modifications needed.

## Key Decisions

1. **D17.1:** EF and SA are decoupled in the decision gate. EF correctness is not gated on SA proximity. (Unanimous)
2. **D17.2:** Divergence and exclusion are first-class terminal outcomes with positive LIS scoring. (Unanimous)
3. **D17.3:** Filing-aware concept discovery precedes AI proposals — AI ranks candidates, never invents names. (Unanimous)
4. **D17.4:** Evidence pack approach first (immediate), ReAct loop later (500-company scale). (Moderator resolution)
5. **D17.5:** Derivation planner uses accounting identities with company-specific concepts discovered from calc trees. (Unanimous)
6. **D17.6:** Industry pre-exclusion happens before the eval loop, not as a proposal action. (Unanimous)

## Action Items

- [ ] **O53:** Decouple EF/SA in decision gate
- [ ] **O54:** LIS rewards divergence/exclusion actions
- [ ] **O55:** Derivation planner (accounting identity engine)
- [ ] **O56:** Evidence pack for AI prompt context
- [ ] **O57:** Industry pre-exclusion before eval loop
- [ ] **O58:** Per-metric gate isolation (impacted-cell regression)
