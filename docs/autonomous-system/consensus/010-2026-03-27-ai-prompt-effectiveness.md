# Consensus Session 010: AI Prompt Effectiveness — Why Proposals Are No-Ops

**Date:** 2026-03-27
**Pattern:** Exploratory
**Models:** GPT-5.4 (neutral), Gemini 3.1 Pro (neutral), Claude Opus 4.6 (moderator)
**Continuation ID:** aaee647d-238c-4be6-a755-5b455486d9bb
**Trigger:** Run 009 E2E showed 0% KEEP rate persists after O12-O14 compiler fixes. All 4 AI proposals are no-ops — they compile correctly but don't change extraction output.

## Context

After fixing two compiler bugs (O12: namespace normalization, O13: gap-aware routing), the pipeline correctly compiles and routes AI proposals. But all proposals are still no-ops at the extraction level. Investigation of the 4 actionable gaps revealed the problem has shifted from infrastructure to **AI prompt quality**.

The root cause is a conflicting optimization target: the prompt tells the AI to "Choose from candidates with the lowest Delta%" (numerical optimization) while the system evaluates proposals on semantic correctness and extraction improvement. This mismatch produces proposals that are numerically plausible but semantically absurd.

Evidence from E2E run (10 companies, 13 gaps, 4 actionable):

| Gap | Current Concept | AI Proposed | Failure Mode |
|-----|----------------|-------------|-------------|
| GS:IntangibleAssets | Goodwill | ReverseRepurchaseAgreements (0% delta) | Semantic nonsense — value match, not meaning match |
| HD:InterestExpense | InterestExpense | InterestExpense (same) | No-op — prompt doesn't show current mapping |
| MSFT:PPE | PropertyPlantAndEquipmentNet ($205B) | PropertyPlantAndEquipmentGross ($299B) | Worse delta — AI doesn't know current concept |
| CAT:AccountsReceivable | (unmapped) | ComprehensiveIncomeNetOfTax (2.9% delta) | Semantic nonsense — income != receivables |

## GPT-5.4 (Neutral — Practical Approach)

- **Core diagnosis**: This is a "candidate-ranking and escalation problem, not a freeform concept-picking problem." The biggest bug is the instruction at line 1735 ("lowest Delta%"), not missing prompt prose.
- **Four-part prompt redesign**: (1) Current State block with current concept/value/variance, (2) Semantic Contract requiring same financial meaning, (3) Gap-type interpretation explaining high_variance vs unmapped, (4) Decision rules including "never propose current concept" and "ESCALATE if no semantic match"
- **Pre-filtering is essential**: Two-stage ranker — deterministic semantic filter by statement family + token overlap, then LLM ranks surviving 3-5 candidates. Crude token rules (receivable → receivable/ar/trade) will eliminate 80%+ of noise.
- **Reference mismatch as terminal case**: MSFT PPE and HD InterestExpense are not prompt failures — they're cases where the correct concept IS already mapped but yfinance disagrees. Route to ESCALATE/DOCUMENT_DIVERGENCE as first-class terminal path.
- **Preflight strengthening**: Reject identical-to-current and variance-worsening proposals before CQS evaluation.
- **Industry perspective**: Mature extraction systems use taxonomy-aware generation and statement-family gating, never raw value-nearest concepts without ontology constraints.
- **Confidence**: 9/10

## Gemini 3.1 (Neutral — Robust Approach)

- **Core diagnosis**: "The AI is instructed to act as a greedy numerical optimizer rather than a semantic reasoning engine." The prompt optimizes for Delta% while evaluation measures Semantic Relevance — contradictory targets.
- **Hybrid approach**: (1) Deterministic pre-filtering by XBRL statement network — block mismatched statement families before AI sees candidates, (2) Prompt enrichment with current_concept from UnresolvedGap.
- **current_concept is the critical missing field**: Without it, high_variance gaps like HD:InterestExpense loop in permanent no-op state. The AI cannot avoid no-ops if blind to the baseline.
- **DOCUMENT_DIVERGENCE as explicit edge case**: For high_variance where current concept is semantically correct but reference disagrees, explicitly instruct AI to use DOCUMENT_DIVERGENCE — don't force remapping.
- **Pre-filter by statement network**: Modify discover_concepts.py to deterministically block candidates from mismatched XBRL statement networks (e.g., income statement concepts for balance sheet metrics).
- **Value assessment**: Current pipeline generates $0 value while consuming API budget. "The deterministic layer handles numbers; the AI must handle meaning."
- **Confidence**: 9/10

## Our Diagnosis

### Agreements (Unanimous — All Three Parties)

1. **The "lowest Delta%" instruction is the primary bug** — it actively steers the AI toward numerically-matching but semantically-wrong concepts. This single instruction at line 1735 of `_build_candidates_context()` is responsible for the majority of failures.

2. **Current mapping context is critical** — the AI must know what concept is already mapped, what value it extracts, and what variance it produces. Without this, it cannot detect no-ops or judge whether a proposal improves the situation.

3. **Pre-filtering candidates is necessary** — the AI should never see `ComprehensiveIncomeNetOfTax` as a candidate for `AccountsReceivable`. Deterministic statement-family filtering before the AI sees candidates removes 80%+ of noise.

4. **Reference mismatch is a terminal case** — when the current concept is semantically correct but yfinance reports a structurally different number (gross vs net, different aggregation), the correct action is DOCUMENT_DIVERGENCE, not forced remapping. This should be a first-class routing decision.

5. **The AI is the right tool, but for semantic reasoning, not numerical optimization** — the deterministic layers handle numbers. The AI's unique value is understanding accounting semantics, statement families, and concept relationships.

### Disagreements + Resolution

No material disagreements between any parties. GPT-5.4 provided more specific prompt section examples; Gemini 3.1 provided a crisper architectural framing ("deterministic = numbers, AI = meaning"). Both complement each other.

Minor nuance: GPT-5.4 suggested token-overlap heuristics for pre-filtering (receivable → receivable/ar/trade); Gemini 3.1 suggested statement-network gating. **Resolution**: Both are complementary layers. Statement-network gating is the coarser, more reliable filter; token-overlap is a finer secondary filter. Implement statement-network first.

### What We Learned

1. **Optimization target alignment is everything** — if the prompt optimizes X but the system evaluates Y, the AI will reliably produce X-optimal, Y-terrible results. This is a general principle for any AI-in-the-loop system.

2. **Context the AI needs = context a human expert would need** — a human XBRL expert asked to fix a gap would want to know: (a) what's currently mapped, (b) what statement this belongs to, (c) what the semantic expectation is. Our prompt gave none of this.

3. **Value-matching without semantic filtering is an anti-pattern** — `discover_concepts` value_match returns ANY concept with a similar numerical value. For large companies ($B scale), hundreds of unrelated concepts will match any given reference value. Semantic pre-filtering is not optional.

## Key Decisions

1. **Remove "lowest Delta%" instruction** — replace with semantic-first ranking requirement (O15)
2. **Add current_concept to UnresolvedGap and prompt** — the AI must see what's already mapped (O16)
3. **Add semantic contract and statement context to prompt** — metric belongs to balance_sheet/income/cashflow, expected concept class (O17)
4. **Pre-filter candidates by statement family** — deterministic filter before AI sees candidates (O18)
5. **Explicit DOCUMENT_DIVERGENCE path for reference mismatches** — gap-type-specific instructions in prompt (O19)

## Action Items

- [ ] **O15: Remove numerical mandate** — Replace "Choose from candidates with lowest Delta%" with semantic-first instruction in `_build_candidates_context()` line 1735
- [ ] **O16: Add current mapping context** — Add `current_concept` + `current_value` fields to `UnresolvedGap`, include in `build_typed_action_prompt()`
- [ ] **O17: Semantic contract + statement context** — Add metric's statement family, expected concept class, and "concept MUST represent same financial meaning" to prompt
- [ ] **O18: Pre-filter candidates** — Add statement-family gating to `_build_candidates_context()` before formatting the table. Block candidates from mismatched statement networks.
- [ ] **O19: DOCUMENT_DIVERGENCE path** — Add gap-type-specific instructions: high_variance + semantically correct current concept → DOCUMENT_DIVERGENCE, not forced MAP_CONCEPT
- [ ] **O20: Preflight no-op rejection** — Add preflight check rejecting proposals identical to current mapping or worsening variance
