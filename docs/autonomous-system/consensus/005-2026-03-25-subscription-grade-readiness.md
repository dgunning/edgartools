# Consensus Session 005: Subscription-Grade Readiness

**Date:** 2026-03-25
**Pattern:** Exploratory
**Models:** GPT-5.4 (neutral/practical), Gemini 3.1 Pro (neutral/robust), Claude Opus 4.6 (moderator)
**Continuation ID:** `58885999-a3b7-445c-91ca-346bfaeb0fdb`
**Trigger:** Strategic question — what does it take to make the autonomous XBRL extraction system a product customers would pay for?

## Context

The autonomous XBRL extraction quality system has reached CQS 0.9957 across 100 companies with 37 base + 3 derived metrics. However, the honest extraction fidelity score (EF-CQS) is only 0.8491 — roughly 15% of concept mappings are wrong or unverifiable. The system validates against yfinance snapshots and the SEC XBRL API, uses typed actions for AI-driven config improvements, and has safety invariants (hard veto on regressions, circuit breaker, graveyard). Pending milestones include LIS (Localized Impact Score) to replace the global CQS gate, multi-period validation, and scaling from 100 to 500 companies.

The question: what separates our current state from a subscription-grade data product, and what's the fastest path to close the gap?

## GPT-5.4 (Practical Stance)

- **Accuracy targets:** 97-98% weighted overall, 99%+ on core metrics. Proposed splitting EF into Raw Fact Accuracy (>=0.98) + Semantic Mapping Correctness (>=0.97). Current 0.85 is "useful internal research tool" territory.
- **Internal override is dangerous:** `reference_validator.py`'s "INTERNAL OVERRIDE" (trusting extraction when equations pass but yfinance disagrees) should NOT drive customer-facing publication.
- **missing_ref treated as valid is risky:** `is_valid=True` for missing reference data muddies product semantics.
- **Order:** LIS -> evidence+multi-period -> publish gating+confidence surfaces -> regression monitoring -> scale to 500. "Scaling first will just industrialize hidden error."
- **Customer table stakes:** Per-cell confidence badges, data dictionary (metric definitions, formulas, sign conventions), lineage/explainability (concept, accession number, period), freshness/SLA page, versioning/changelog.
- **Biggest risks:** (a) Definition drift — "Bloomberg wins by metadata, not just numbers," (b) Restatement/PiT errors, (c) False confidence from internal overrides, (d) No monitoring/alerting, (e) Long-tail sector complexity.
- **10-Q quarterly:** YTD-to-quarter derivation must be explicitly tested or quarterly data stays withheld.
- **Confidence:** 9/10 — architecture has the right primitives.

## Gemini 3.1 (Robust Stance)

- **Accuracy targets:** EF-CQS 0.95+ minimum overall, 0.99+ on headline metrics (Revenue, Operating Income, EPS, Total Assets). "At 0.85, a customer hits an error roughly once every 7 data points — for institutional finance, this is catastrophic."
- **Halt scaling:** Explicit "do not expand beyond 100 companies until EF-CQS hits 0.95+." Scaling a 15% failure rate dilutes focus.
- **SEC-native primacy:** "You cannot charge for a derivative of Yahoo Finance." SEC Company Facts + internal validator must be absolute arbiters.
- **Multi-period golden masters:** Must hold across 3 consecutive 10-Ks AND intermediate 10-Qs.
- **10-Q YTD trap:** Dedicated development cycle needed. Q2/Q3 YTD subtractions are "highly volatile" — if company restates Q1 in Q2 filing, direct math produces "disastrously skewed" quarterly values.
- **Reference poisoning:** Using yfinance to evaluate EF-CQS means bad Yahoo data can override structurally sound XBRL extractions. Circular dependency risk.
- **P-hacking configs:** AI discovering composite equations that mathematically match yfinance by coincidence without semantic truth.
- **PiT/restatement integrity:** 10-K/A amendments must override originals seamlessly; historical data remains immutable.
- **Customer features:** Click-through provenance, exposed publish_confidence, strict SLAs (24-48h remediation, 98% coverage within 5 mins of EDGAR publish).
- **Confidence:** 9/10.

## Our Diagnosis

### Agreements (unanimous across all three perspectives)

1. **EF-CQS 0.85 is not subscription-grade.** Minimum viable threshold: **0.95+ overall, 0.99+ on headline metrics** (Revenue, Net Income, Total Assets, Operating Income, EPS).
2. **LIS must replace global CQS gate immediately** — it's the #1 blocker preventing the autonomous loop from making correct single-metric improvements.
3. **SEC-native evidence must be primary truth.** yfinance is corroboration only. "You cannot charge for a derivative of Yahoo Finance."
4. **Multi-period validation (3+ annual periods) is non-negotiable** before selling data. Single-period matches can be algebraic coincidences.
5. **Do NOT scale to 500 until accuracy is proven on 100.** Premature scaling industrializes hidden error.
6. **Customer metadata is table stakes** — provenance, confidence badges, data dictionary, lineage, changelog.
7. **10-Q quarterly derivation needs a dedicated development cycle** — too error-prone with YTD subtraction and restatement edge cases.
8. **Publish gating:** Withhold unverified/low-confidence data. Silent wrongness is worse than visible gaps.

### Disagreements + Our Resolution

**Accuracy target specifics:** GPT-5.4 proposes splitting EF into Raw Fact Accuracy (>=0.98) + Semantic Mapping Correctness (>=0.97). Gemini uses a simpler EF-CQS >= 0.95 floor with 0.99 on headlines.

**Resolution:** Adopt the split. The two-score architecture (EF + SA) already exists in our `ValidationResult`. Refine EF to separately track "did we find the right XBRL concept?" (semantic) vs "did we extract the correct value from that concept?" (raw fact). This decomposition helps diagnose whether failures are mapping errors or extraction bugs.

**Scaling stance:** Gemini says "halt" explicitly; GPT says "only after."

**Resolution:** Practically the same — don't scale until EF-CQS >= 0.95 on the base 100. The difference is rhetorical.

**Internal override:** GPT flags the `INTERNAL OVERRIDE` pattern as dangerous for publication. I agree strongly — internal equations passing does NOT mean the customer should trust a number that disagrees with external references. This override is useful for diagnostic prioritization but must never set `publish_confidence="high"`.

### What We Learned

1. **"Error once every 7 data points"** — Gemini's framing makes the 0.85 gap visceral. This should be our internal pitch for why accuracy comes before everything else.
2. **Bloomberg wins by metadata, not just numbers** — The data dictionary and lineage layer is not a "nice to have." It's what separates a data product from a data dump.
3. **Reference poisoning is a circular dependency** — If yfinance is both the training signal (for EF-CQS evaluation) and the truth source, bad yfinance data becomes our truth. SEC-native primacy breaks this loop.
4. **PiT/restatement is a product contract** — Not just a technical feature. Customers need to know what "as-reported" means in our system.
5. **The EF split (Raw Fact + Semantic Mapping) is actionable** — We already have the `rfa_pass` and `sma_pass` fields on `ValidationResult`. Wire them into separate sub-scores.

## Key Decisions

1. **Subscription-grade threshold: EF-CQS >= 0.95 overall, >= 0.99 on 8 headline metrics** (Revenue, NetIncome, TotalAssets, TotalLiabilities, Equity, OperatingIncome, OperatingCashFlow, EPS).
2. **No scaling past 100 until EF-CQS >= 0.95** on the base cohort with multi-period validation.
3. **SEC-native evidence becomes primary** — yfinance demoted to corroboration signal.
4. **Internal override must never set publish_confidence="high"** — useful for diagnostics, not publication.
5. **Quarterly data (10-Q) is a separate product milestone** — do not bundle with annual data readiness.
6. **Customer metadata (provenance, data dictionary, confidence API) is a pre-launch requirement**, not a post-launch enhancement.

## Action Items

- [ ] **M1.1-M1.2: Implement LIS + wire into decision gates** — Unblocks autonomous loop from CQS noise floor. Critical path.
- [ ] **M2.1: SEC-native primacy** — Promote SEC XBRL API to primary reference; demote yfinance to corroboration. Audit `reference_validator.py` internal override behavior.
- [ ] **M2.2: Multi-period validation** — `compute_lis()` checks 3 annual periods. Mapping must hold across FY2022-2024.
- [ ] **Wire RFA/SMA sub-scores into dashboard** — Already have `rfa_pass`/`sma_pass` fields. Surface as separate accuracy dimensions.
- [ ] **Audit publish_confidence gating** — Ensure internal override never produces `publish_confidence="high"`. Add guardrail.
- [ ] **Run autonomous loop on 100 companies until EF-CQS >= 0.95** — Only then consider M3 scaling.
- [ ] **Design data dictionary schema** — Metric definition, statement family, units, sign convention, source concept(s), composite formula, exclusions.
- [ ] **Scope 10-Q quarterly derivation** — Dedicated design session for YTD subtraction + restatement handling. Separate milestone from annual data product.
- [ ] **Define SLA framework** — Accuracy targets per metric tier, freshness guarantees, error remediation timeline.
