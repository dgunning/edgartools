# Autonomous System Roadmap

*Where we've been, where we're going, and the strategic decisions that got us here.*
*See [architecture.md](architecture.md) for how the system works right now.*

---

## Origin

Synthesized from a structured multi-model consensus session (GPT-5.4, Gemini 3.1 Pro, Claude Opus 4.6) on March 21, 2026. All three models agreed on priority ordering and key architectural decisions. Four follow-up sessions (002-004) refined the approach. See Consensus Sessions below for details.

---

## Phase Completion Tracking

| Phase | Target | Started | Completed | CQS Before | CQS After | Key Findings |
|-------|--------|---------|-----------|------------|-----------|--------------|
| 1a: Fix min_periods | min_periods=3 | 2026-03-21 | 2026-03-21 | 0.9734 | 0.9111 | Changed call site to use default min_periods=3. CQS drop expected: stricter golden masters + 37 metrics (vs 19). |
| 1b: Unverified state | Replace exclusion | 2026-03-21 | 2026-03-21 | - | - | Replaced ADD_EXCLUSION with None return + log. |
| 1c: Metric tolerances | Per-metric thresholds | 2026-03-21 | 2026-03-21 | - | - | Added validation_tolerance field. 6/19 metrics have explicit tolerances. |
| 2a: Calc linkbase | Self-validation | 2026-03-21 | 2026-03-21 | - | - | 5 equations (4 accounting + 1 cross-statement). Internal override: trust extraction when equations pass but yfinance disagrees. |
| 2b: Cross-statement | Reconciliation | 2026-03-21 | 2026-03-21 | - | - | PretaxIncome >= NetIncome cross-statement equation. |
| 2c: Cross-company | Peer consistency | 2026-03-21 | 2026-03-21 | - | - | compute_concept_consensus() — informational for now. |
| 3a: Metric expansion | 19→37 metrics | 2026-03-22 | 2026-03-22 | 0.9734 | 0.9111 | 18 base + 3 derived + 15 yfinance mappings. CQS denominator grew 2x. |
| 3b: Historical | 3 annual + 4 quarterly | - | - | - | - | Deferred. Solver supports multi_period=True. |
| 3c: Applicability | Required/optional/forbidden | 2026-03-22 | 2026-03-22 | - | - | PPE, R&D added to banking forbidden list. |
| 4a: S&P 500 | 500 companies | - | - | - | - | EXPANSION_COHORT_500 ready. Needs yfinance snapshots for ~400 new. |
| 4b: SEC XBRL API | Second reference | 2026-03-22 | 2026-03-22 | 0.9111 | 0.9118 | 120 SEC facts matches. Banking sector primary beneficiary. |
| 4c: Event-driven | Real-time processing | - | - | - | - | Deferred. URL builders exist. |
| 5a: Honest EF | Concept correctness | 2026-03-22 | 2026-03-22 | EF=0.65 | EF=0.85 | EF now measures actual concept correctness. Was inflated by `ef_pass = is_mapped`. |
| 5b: Unverified state | No more "assume OK" | 2026-03-22 | 2026-03-22 | - | - | 16 metrics excluded from scoring. |
| 5c: Solver constraints | Prevent coincidences | 2026-03-22 | 2026-03-22 | - | - | max_components 4→2, statement family constraint. |
| 5d: Publish confidence | high/medium/low/unverified | 2026-03-22 | 2026-03-22 | - | - | Risk engine confidence levels on ValidationResult. |
| 5e: CQS rebalance | Reward stability | 2026-03-22 | 2026-03-22 | CQS=0.9936 | CQS=0.9957 | pass_rate 0.50→0.45, stability 0.10→0.15. |
| 5f: Coverage bug | Clamp to 1.0 | 2026-03-23 | 2026-03-23 | - | - | Was 198.4%, P0 fix. `8c4da67f` |
| 5g: Regression cleanup | clear_golden_master() API | 2026-03-23 | 2026-03-23 | - | - | For deactivating bad golden masters. `8c4da67f` |
| 5h: RFA/SMA routing | Gap classification | 2026-03-23 | 2026-03-23 | - | - | formula_needed / algebraic_coincidence / missing_concept. `8c4da67f` |
| 5i: Canonical provenance | Fact store fields | 2026-03-23 | 2026-03-23 | - | - | 6 fields wired through pipeline. `9c295b22` |
| 5j: Two-step architecture | Manifest + consult | 2026-03-24 | 2026-03-24 | - | - | GapManifest JSON, decoupled from SQLite. `a45e0a76` |
| 5k: Typed actions | Intent→compiler | 2026-03-24 | 2026-03-24 | - | - | 7 actions, 56 tests. `3ff69e2c` |
| 5l: Capability triage | C1/C2/C3 filtering | 2026-03-24 | 2026-03-24 | - | - | 66% waste eliminated. `f2473a05` |
| 5m: Live benchmark | 50-company harness | 2026-03-24 | 2026-03-24 | - | - | 2-arm: typed vs raw control. `1f8ff896` |
| 5n: OpenRouter AI | Gemini Flash via API | 2026-03-24 | 2026-03-24 | - | - | Replaced Agent Tool dispatch. `3ff69e2c`, `f2473a05` |

**Deferred items:** 3b (historical validation), 4a (S&P 500 expansion), 4c (event-driven processing).

---

## Run Log

### Pre-Roadmap Sessions (2026-03-16 to 2026-03-20)

| Session | Date | Cohort | CQS Before | CQS After | Key Event |
|---------|------|--------|------------|-----------|-----------|
| 1 | 2026-03-16 | 5 companies | 0.9062 | 0.9265 | First auto-eval. 5/12 gaps resolved via config. |
| 2 | 2026-03-18 | 5 companies | 0.9265 | 0.9313 | Parallel scouts, 25GB bulk data download. |
| 3 | 2026-03-18 | 50 companies | 0.9016 | 0.9206 | First 50-co expansion. 47/64 gaps resolved. |
| 3.5 | 2026-03-18 | 50 companies | - | - | Code fixes: gap classification, per-metric tolerance, golden master pipeline. |
| 4-7 | 2026-03-18 to 2026-03-20 | Various | - | 0.9535 | Config tuning, concept additions, solver improvements. |
| 8 | 2026-03-20 | 100 companies | - | 0.9714 | First 100-co eval. Next-gen CQS loop plan created. |

### Post-Roadmap Runs

**Run 004 (2026-03-22)** — 3.1 hours, 100 companies, 37 metrics
- Result: 18/18 kept, 0 discards, 0 vetoes
- CQS: 0.9111→0.9118 (+0.0007), EF-CQS: 0.6569→0.6582
- Key: SEC facts `us-gaap:` prefix bug fixed. Banking sector (JPM, C, MS, GS, BLK) primary beneficiary.

**Run 005 (2026-03-22)** — 3 hours, 100 companies, honest scoring enabled
- Result: 14/42 kept, 28 discards, 0 vetoes, **0 EF-CQS gate rejections**
- CQS: 0.9936→0.9957, EF-CQS: 0.8458→0.8491, SA-CQS: 0.8422→0.8459
- Key: EF-CQS at 0.85 is the honest number. 682 golden masters promoted. Solver constraints prevent bad proposals upstream.

**Run 006 (2026-03-26)** — 50 companies, deterministic solver only, SEC-native primacy enabled
- Result: 0/0 kept, 0 discards, 0 vetoes. All 40 gaps exhausted (no viable deterministic proposals).
- EF-CQS: 0.6711 (5-co smoke test baseline, SEC-native primacy). CQS: 0.9073.
- Key: Deterministic solver has reached its ceiling. All remaining gaps require AI resolution. Confirms need for Lead Agent Closed Loop (Phase 7).
- Code fixes this session: `use_sec_facts` defaults → `True`, `reference_validator.py` variance bug fix, progress printing added to `run_overnight()`.

**Run 007 (2026-03-26)** — 19 min, 10 companies, value-grounded AI consultation (O7-O9)
- Result: 0/4 kept, 4 discards (3 pre-screened), 1 retry. **3 auto-resolved** (O9), 2 API calls, $0.006 total cost.
- CQS: 0.9121→0.9121, EF-CQS: 0.6349→0.6349.
- Key: O8+O9 correctly find value-matching concepts and skip API calls (60% budget saved). CQS gate rejects because auto-resolved concepts cause cross-company regressions (e.g., `us-gaap:GrossProfit` for XOM causes PFE to drop -100pp). Root cause: concepts need company-scoped application, not global. Value search works; scoping is the next blocker.

**Run 008 (2026-03-27)** — 5.6 min, 10 companies, manifest caching (O10) + deterministic downgrade (O11)
- Result: 0/3 kept, 3 discards (all pre-screened), 0 downgrade attempts. 2 auto-resolved (O9), 2 API calls, $0.003 total cost.
- CQS: 0.9121→0.9121, EF-CQS: 0.6349→0.6349.
- O10 cache: second run MEASURE 245s→0s (cache hit confirmed).
- Key: **All proposals are no-ops** — two compiler bugs prevent AI proposals from reaching extraction. (1) Namespace mismatch: `us-gaap:X` in config vs bare `X` in tree parser index. (2) Wrong action type: MAP_CONCEPT→ADD_CONCEPT for high_variance gaps (already mapped, need Strategy 0 preferred_concept override). Session 009 consensus: gap-aware compiler (O12-O14).

**Run 009 (2026-03-27)** — 1.8 min, 10 companies, gap-aware compiler (O12-O14)
- Result: 0/4 kept, 4 discards (all pre-screened), 0 auto-resolved, 4 API calls, $0.003 total cost.
- CQS: 0.9121→0.9121, EF-CQS: 0.6349→0.6349.
- O12-O14 confirmed working: proposals now compile to correct action types (`add_company_override` for high_variance, bare concept names). Compiler pipeline is end-to-end correct.
- Key: **0% KEEP rate persists — problem shifted from compiler to AI prompt quality**. Four failure modes identified: (1) Semantic nonsense: AI picks `ReverseRepurchaseAgreements` for IntangibleAssets because 0% delta. (2) No-op: AI proposes same concept already mapped (HD:InterestExpense). (3) Worse mapping: AI picks PPE Gross when Net is closer (MSFT). (4) Wrong statement family: AI picks `ComprehensiveIncomeNetOfTax` for AccountsReceivable. Root cause: prompt says "lowest Delta%" without semantic constraint, doesn't show current mapping. Session 010 consensus: prompt redesign (O15-O20).

**Run 010 (2026-03-27)** — 42s, 10 companies, semantic AI prompt redesign (O15-O20)
- Result: 0/3 kept, 3 discards (all pre-screened), 0 preflight rejected, 4 API calls, $0.004 total cost.
- CQS: 0.9121→0.9121, EF-CQS: 0.6349→0.6349.
- Key: **Qualitative breakthrough — 100% of proposals are now semantically correct**. Before: `ReverseRepurchaseAgreements` for IntangibleAssets, `ComprehensiveIncomeNetOfTax` for AccountsReceivable. After: `Goodwill + IntangibleAssetsNetExcludingGoodwill` (correct formula), `AccountsReceivableNetCurrent + FinanceReceivablesNetCurrent` (correct composite for CAT's financial services division). MSFT:PPE proposes Gross with valid Net vs Gross reasoning. HD:InterestExpense proposes `InterestExpense` (different from current `InterestExpenseNonoperating`). **Bottleneck shifted from prompt quality to CQS evaluation layer** — proposals are semantically right but CQS pre-screen shows no improvement. Next steps: ADD_FORMULA `scope` param fix, company-scoped formula compilation, DOCUMENT_DIVERGENCE as terminal action.

**Run 011 (2026-03-31)** — ~90 min, 5 companies, graveyard replay + signed formula engine
- Result: 17/36 graveyard proposals flipped DISCARD→KEEP. After semantic review: 3 applied, 2 false positives reverted.
- CQS: 0.8224→0.8237, Pass Rate: 94.7%→94.7%
- Key: **Broke the 0% KEEP rate.** Signed formula engine (Consensus 016, O49-O52) unlocked 17 previously rejected proposals. Applied: WMT:InterestExpense (company formula), WMT:PropertyPlantEquipment (known_divergences), JPM:GrossProfit (bank exclusion). Reverted: WMT:IntangibleAssets (AccruedLiabilitiesCurrent — semantic false positive), GrossProfit:NetCashProvidedByUsedInOperatingActivities (cash flow ≠ gross profit). Commit: `6fda5fad`.

**Run 012 (2026-03-31)** — ~25 min, 5 companies, direct AI dispatch via OpenRouter
- Result: 0/5 kept, 5 discards (2 pre-screened, 3 full eval), 0 vetoes. 5 AI proposals from 8 gaps, $0.008 cost.
- CQS: 0.8237→0.8237, EF-CQS: 0.8425→0.8425.
- Key: AI proposals semantically reasonable but gate rejected all. 8 structural gaps identified across 4 categories: missing XBRL concepts (4), yfinance aggregation differences (2), industry exclusions (2). Deep-consensus review (Claude Code agent team: advocate/critic/deepthinker) conducted to design resolution architecture. See `017-2026-04-01-autonomous-structural-gap-resolution.md`.

**Run 013 (2026-04-01)** — 168s, 5 companies, post-consensus-017 verification eval
- Result: Verification only (no experiment loop). 9 gaps identified.
- CQS: 0.8237→0.8293 (+0.0056), EF-CQS: 0.8425→0.8558 (+0.0133), SA-CQS: 0.7633→0.7588.
- Key: **O57 forbidden metrics fix confirmed** — XOM down from 3 gaps to 1 (LongTermDebt explained_variance only). XOM:GrossProfit/OperatingIncome no longer penalize CQS. O55 derivation planner wired (`company_results=True` on all WMT gaps) but WMT:GrossProfit/TotalLiabilities still unmapped — component metrics (Revenue, COGS) need resolution first. Divergence guardrail active (no premature divergence proposals).

---

## Consensus Sessions

| # | Date | Models | Focus | Status |
|---|------|--------|-------|--------|
| 001 | 2026-03-21 | GPT-5.4 + Gemini 3.1 + Claude | Initial consensus: roadmap phases 1-4, yfinance bottleneck | All implemented |
| 002 | 2026-03-22 | GPT-5.4 + Gemini 3.1 | CQS masking: EF/SA at 0.65 is honest, EF definition too loose | All implemented |
| 003 | 2026-03-23 | GPT-5.4 + Gemini 3.1 | P0: coverage_rate 198.4%, regression cleanup, RFA/SMA routing | All implemented |
| 004 | 2026-03-24 | GPT-5.4 + Gemini 3.1 | Autonomous architecture: LIS, evidence tiers, two-tier AI | Phase 6 created |
| 005 | 2026-03-25 | GPT-5.4 + Gemini 3.1 | Subscription-grade readiness: accuracy thresholds, SEC-native primacy, product requirements | Action items created |
| 006 | 2026-03-26 | GPT-5.4 + Gemini 3.1 | Closed-loop pipeline optimization: prompt enrichment, per-company circuit breaker, retry-with-feedback, in-memory pre-screen | All implemented |
| 007 | 2026-03-26 | GPT-5.4 + Gemini 3.1 | Value-grounded AI consultation: reverse value search, evidence table prompts, three-tier dispatch | All implemented |
| 008 | 2026-03-26 | GPT-5.4 + Gemini 3.1 | Manifest caching & cross-company regression: fingerprint-gated cache, deterministic downgrade (global-first, auto-scope on regression) | Action items created |
| 009 | 2026-03-27 | GPT-5.4 + Gemini 3.1 | Compiler architecture flaws: namespace mismatch, gap-aware routing, actionability filter fix | All implemented |
| 010 | 2026-03-27 | GPT-5.4 + Gemini 3.1 | AI prompt effectiveness: semantic-first ranking, current mapping context, candidate pre-filtering, divergence path | All implemented |
| 011 | 2026-03-27 | GPT-5.4 + Gemini 3.1 | In-memory config bugs: ADD_COMPANY_OVERRIDE flattening, ADD_FORMULA format mismatch, ADD_DIVERGENCE wrong field, round-trip tests | All implemented |
| 012 | 2026-03-27 | GPT-5.4 + Gemini 3.1 | Post-O21 root cause: _compute_sa_composite black box, PFE -100pp cross-company regression, diagnostic-first approach | Action items created |
| 013 | 2026-03-27 | GPT-5.4 + Gemini 3.1 | Pipeline architecture flaws: MappingSource.CONFIG overload, Strategy 0 silent fallthrough, AI resolver duplication. Diagnostic-confirmed root causes for 0% KEEP rate. | O33-O38 implemented |
| 014 | 2026-03-27 | GPT-5.4 + Gemini 3.1 | AI prompt benchmarking: two-layer eval (semantic vs CQS), fix evaluator before prompt, DOCUMENT_DIVERGENCE exception mode, 12-case gold set | Action items created |
| 015 | 2026-03-27 | GPT-5.4 + Gemini 3.1 | AI prompt & context overhaul: scope enum enforcement, explicit escalation triggers, formula constraints, solver annotations. 25%→60%+ compile-valid target. | O41-O46 planned |
| 016 | 2026-03-28 | GPT-5.4 + Gemini 3.1 | Formula engine limitations & auto-solver quality: signed components in _compute_sa_composite, kill brute-force solver, override isolation bug, graveyard replay strategy | Action items created |
| 017 | 2026-04-01 | Claude Code deep-consensus (advocate/critic/deepthinker) | Autonomous structural gap resolution: EF/SA decoupling, divergence as terminal outcome, derivation planner, evidence pack, industry pre-exclusion, per-metric gate isolation | O53-O58 implemented |

### Session 004 Unanimous Agreements

1. **Stop using CQS as decision gate** — at 0.98+, a correct fix produces ~0.0003 delta, below noise floor. Use localized evaluation.
2. **SEC-native evidence is first-class** — yfinance is corroboration, not truth. SEC XBRL API as primary.
3. **Two-tier AI** — Gemini Flash (fast, 80% of gaps) + Sonnet/Opus (deep, 20%).
4. **Scale order: scoring → metrics → companies** — don't expand to 500 until LIS + evidence model are correct.
5. **~90-95% autonomous ceiling** — tail 5-10% needs human review or hold/escalate.

### Scoring Proposals

- **GPT-5.4: NRGS** (Net Resolved Gap Score) — per-cell weighted evidence delta
- **Gemini 3.1: LIS** (Localized Impact Score) — target improved + zero regressions
- **Synthesis:** Start with LIS (implementable now), evolve toward NRGS as evidence model matures.

### Continuation IDs

| Session | Date | Models | ID |
|---------|------|--------|----|
| 001 | 2026-03-21 | GPT-5.4 + Gemini 3.1 + Claude | `db9007c4-dab5-4929-88da-7f0a2ad2bfd8` |
| 002 | 2026-03-22 | GPT-5.4 + Gemini 3.1 | `1b53864e-ee5d-4f49-b18d-fec70a1b73cc` |
| 003 | 2026-03-23 | GPT-5.4 + Gemini 3.1 | (same as 002) |
| 004-GPT | 2026-03-24 | GPT-5.4 | `b84ffab5-ef22-4e65-ab1b-c0c36bb795e5` |
| 004-Gemini | 2026-03-24 | Gemini 3.1 | `79a6b8e7-d662-4bd8-86d0-79a499d81ee5` |
| Benchmark-GPT | 2026-03-24 | GPT-5.4 | `44f18ec8-2f57-4279-90f0-1482f322a72e` |
| Benchmark-Gemini | 2026-03-24 | Gemini 3.1 | `261ad1fa-b6a3-421a-949e-a760cb93bac9` |
| 005 | 2026-03-25 | GPT-5.4 + Gemini 3.1 | `58885999-a3b7-445c-91ca-346bfaeb0fdb` |
| 006 | 2026-03-26 | GPT-5.4 + Gemini 3.1 | `0ad231f4-2c76-4211-a617-aacf2486f61d` |
| 008 | 2026-03-26 | GPT-5.4 + Gemini 3.1 | `043aa8af-8c71-4f85-b496-15066abb64d3` |
| 009 | 2026-03-27 | GPT-5.4 + Gemini 3.1 | `35d790f6-7f49-482f-b4a9-abb07d076867` |
| 010 | 2026-03-27 | GPT-5.4 + Gemini 3.1 | `aaee647d-238c-4be6-a755-5b455486d9bb` |
| 011 | 2026-03-27 | GPT-5.4 + Gemini 3.1 | `ba2f82ae-e8f2-4d1c-bd01-29e40d721c42` |
| 012 | 2026-03-27 | GPT-5.4 + Gemini 3.1 | `06acd7c0-fc3d-4945-8c81-a52b77a4eef5` |
| 013 | 2026-03-27 | GPT-5.4 + Gemini 3.1 | `edb0fb8f-3b1e-4124-8021-f61b882a865c` |
| 014 | 2026-03-27 | GPT-5.4 + Gemini 3.1 | `10bcb2eb-98b7-4b0c-95c7-9e0d233ccf33` |
| 015 | 2026-03-27 | GPT-5.4 + Gemini 3.1 | `5b47500e-0e10-4f75-878a-5a2a079c284e` |
| 016 | 2026-03-28 | GPT-5.4 + Gemini 3.1 | `73e496f4-f35c-4a18-bc02-09703b72814b` |
| 017 | 2026-04-01 | GPT-5.4 + Gemini 3.1 | `c91c90e7-8886-4df2-9893-d40f31a27958` |

---

## Phase 6: Autonomous System Architecture

*Derived from Session 004 consensus. Goal: transform the overnight loop from a CQS-gated experiment engine into a localized evidence-based autonomous system.*

### Milestone 1: Replace CQS Gate with Localized Evaluation (M1)

**Goal**: A correct single-metric fix is accepted based on local evidence, not global CQS movement.
**Priority**: Highest — unblocks all other improvements.

- [x] **M1.1: Implement LIS** — Completed 2026-03-25. `cd4f310d`. `compute_lis()` in `auto_eval_loop.py`.

- [x] **M1.2: Wire LIS into decision gates** — Completed 2026-03-25. `cd4f310d`. LIS replaces global CQS check.

- [x] **M1.3: Wire AI into overnight loop** — Lead Agent Closed Loop: `run_closed_loop()` orchestrates deterministic → AI resolution. `dispatch_ai_gaps()` + `evaluate_ai_proposals_live()`. Completed 2026-03-26 (Phase 7).
  - Verification: 50-company run, AI resolves gaps that deterministic solver cannot.

- [x] **M1.4: Switch dashboard to EF-CQS** — Completed 2026-03-25. `cd4f310d`. EF-CQS is headline with color coding.

### Milestone 2: Evidence Model + Validation Depth (M2)

**Goal**: SEC-native evidence as primary truth source. Multi-period validation prevents one-shot coincidences.
**Priority**: Medium-high. **Depends on**: M1.

- [x] **M2.1: Evidence tiers in scoring** — Completed 2026-03-25. `cd4f310d`. `sec_confirmed > yfinance_confirmed > self_validated > unverified`.

- [x] **M2.2: Multi-period validation** — Completed 2026-03-25. `cd4f310d`. LIS checks 3 annual periods.

- [ ] **M2.3: Internal validator as gate** — Accounting equation failures (Assets != Liabilities + Equity) → hard veto.
  - Verification: Apply balance-sheet-breaking change, assert VETO.

- [ ] **M2.4: SEC API as secondary reference** — Full integration of SEC Company Facts API for yfinance=None gaps.
  - Verification: BLK:BookValuePerShare gets SEC reference value.

### Milestone 3: Scaled Autonomous Pipeline (M3)

**Goal**: Two-tier overnight pipeline on 500 companies.
**Priority**: Lower. **Depends on**: M1+M2.

- [ ] **M3.1: Two-tier dispatch** — Gemini Flash (D0/H1 gaps) + Sonnet/Opus (E gaps, Flash failures). Extend C1/C2/C3 capability registry.
  - Verification: 50-company manifest, Flash handles >80%.

- [ ] **M3.2: Industry-batch expansion** — 100→500 in 4 batches: Tech+Consumer (150), Financial (100), Industrial+Energy (150), Healthcare+Utility+REIT (100).
  - Verification: Each batch EF-CQS > 0.80 before promotion.

- [ ] **M3.3: NRGS evolution** — Per-cell weighted evidence delta scoring (replaces binary LIS).
  - Verification: Compare NRGS vs LIS on 100 historical experiments.

- [ ] **M3.4: Gemini Batch API** — GitHub issue #1. Batch gap consultation for 50% cost reduction.
  - Verification: Cost comparison on same 50-company run.

- [ ] **M3.5: Model comparison benchmark** — GitHub issue #2. Gemini Flash vs Sonnet vs Opus vs GPT-5.4.
  - Verification: Per-model accuracy, cost, latency report.

---

## Phase 7: Lead Agent Closed Loop

*Derived from Run 006 finding: deterministic solver exhausted, all remaining gaps need AI. The lead Claude Code agent orchestrates the full resolution pipeline.*

### Architecture

```
For each 50-company batch:
  Step 1: run_overnight(propose_fn=propose_change)  [deterministic]
    → Resolves known patterns, solver formulas
    → Outputs GapManifest JSON with unresolved gaps

  Step 2: Lead agent reads GapManifest, spawns subagents  [AI]
    → gap-solver agent (standard: semantic_mapper, reference_auditor)
    → gap-investigator agent (hard: pattern_learner, regression_investigator)
    → TypedAction responses → compile_action() → evaluate_experiment()

  Step 3: Graduate batch if EF-CQS >= 0.80, move to next 50
```

### Rules

1. AI proposals go through the same CQS/LIS gate — no bypass
2. Each batch must reach EF-CQS >= 0.80 before expanding
3. Dead-end filtering: 6+ graveyard entries → skip
4. TypedAction vocabulary is finite (7 actions) — AI cannot invent new types
5. Lead agent logs all decisions for morning review

### Milestones

- [x] **M7.1: Wire GapManifest → AI dispatch** — `dispatch_ai_gaps()` reads manifest, filters dead-ends, caches responses, builds prompts via `build_typed_action_prompt()`, returns ProposalRecords. Completed 2026-03-26.
- [x] **M7.2: AI response → CQS gate** — `evaluate_ai_proposals_live()` evaluates proposals in-memory through same CQS/LIS gate with circuit breaker (10 consecutive failures). Completed 2026-03-26.
- [x] **M7.3: Closed-loop orchestration** — `run_closed_loop()` orchestrates deterministic solver (40% budget) → AI resolution (60% budget) in sequence. Completed 2026-03-26.
- [x] **M7.4: Batch expansion to 500** — `run_batch_expansion()` splits large cohorts into batches, runs closed loop on each, graduates at EF-CQS threshold. Completed 2026-03-26.
- [x] **M7.5: Reverse value search (O8)** — `_search_by_value()` in `discover_concepts.py` finds concepts by matching extracted value to reference. `CandidateConcept` extended with `extracted_value` and `delta_pct`. Completed 2026-03-26. `f1fe3e91`.
- [x] **M7.6: Value-enriched prompts (O7)** — `_build_candidates_context()` returns evidence table (`concept | value | ref | delta% | source`) + enriched candidate list. AI sees numerical evidence, not just concept names. Completed 2026-03-26. `f1fe3e91`.
- [x] **M7.7: Auto-resolve from value search (O9)** — `_try_auto_resolve()` emits typed action for `us-gaap:` concepts with <2% variance, skipping API call. `auto_resolved` field on `AIDispatchReport`. Completed 2026-03-26. `f1fe3e91`.
- [x] **M7.8: Semantic prompt mandate (O15)** — Replace "lowest Delta%" instruction with semantic correctness requirement. DOCUMENT_DIVERGENCE fallback for no semantic match. Completed 2026-03-27. `93acf55b`.
- [x] **M7.9: Current mapping context (O16)** — `current_concept` field on `UnresolvedGap`, populated from `ExtractionEvidence.components_used[0]`, displayed in AI prompt. Completed 2026-03-27. `93acf55b`.
- [x] **M7.10: Statement family constraint (O17)** — `_build_metric_context()` adds statement family, concept class, and constraint to prompt. 42 metrics covered by `_METRIC_CONCEPT_CLASS` dict. Completed 2026-03-27. `93acf55b`.
- [x] **M7.11: Candidate pre-filter (O18)** — Cross-statement candidates removed before AI sees them. Unknown-statement candidates kept (don't over-filter). Completed 2026-03-27. `93acf55b`.
- [x] **M7.12: DOCUMENT_DIVERGENCE guidance (O19)** — `_build_gap_type_guidance()` for high_variance (current concept may be correct) vs unmapped (find new concept). Completed 2026-03-27. `93acf55b`.
- [x] **M7.13: Preflight no-op rejection (O20)** — `validate_action_preflight(action, gap)` rejects proposals identical to current mapping or from wrong statement family. Completed 2026-03-27. `93acf55b`.
- [x] **M7.14: In-memory config bug fixes (O21-O23)** — Three bugs in `apply_change_to_config()`: ADD_COMPANY_OVERRIDE wrote to wrong dict key (fixed with `setdefault(target_metric, {}).update()`), ADD_FORMULA compiled as list not dict (fixed in `compile_action()`), ADD_DIVERGENCE wrote to `metric_overrides` instead of `known_divergences` (new `CompanyConfig.known_divergences` field). Completed 2026-03-27.
- [x] **M7.15: Hardening (O24-O25)** — Warning on empty ticker in ADD_KNOWN_VARIANCE. ValueError (not warning) on unsupported in-memory change types. Completed 2026-03-27.
- [x] **M7.16: Round-trip consumption tests (O26)** — 6 tests verifying compile → apply_in_memory → config structure matches consumer expectations. Completed 2026-03-27.
- [x] **M7.17: Stale cache invalidation (O27)** — Deleted pre-O16 `measure_cache.json` with `current_concept=None` entries. Completed 2026-03-27.
- [x] **M7.18: MappingSource.OVERRIDE + Strategy 0 hard failure (O33-O38)** — New `OVERRIDE` enum value separates company overrides from exclusions. Strategy 0 returns OVERRIDE (not CONFIG), so validator and CQS process overrides normally instead of auto-passing. Strategy 0 hard failure returns `ConfidenceLevel.INVALID` when preferred_concept not found (no silent fallthrough to Strategy 1). Completed 2026-03-27.
- [x] **M7.19: Signed formula engine (O49-O52)** — `_compute_sa_composite()` supports weighted components with positive/negative signs. Enables subtraction formulas (GrossProfit = Revenue - COGS). Solver constraints updated. Completed 2026-03-28. `36f1c763`.
- [x] **M7.20: Dead MCP/GPT escalation path removal** — Removed unreachable MCP/GPT code from auto-eval loop. Completed 2026-03-31. `74da0e6f`.
- [x] **M7.21: Graveyard replay** — `replay_graveyard_proposals()` re-evaluates previously rejected proposals after engine changes. Broke 0% KEEP rate: 17/36 flipped. Completed 2026-03-31. `6fda5fad`.
- [x] **M7.22: Consensus 017 + post-review fixes (O53-O58)** — EF/SA gate decoupling (`_GATE_APPLICABILITY`), forbidden metrics excluded from CQS scoring (`_build_forbidden_by_ticker()`), derivation planner wired into `propose_change()` via `MetricGap.company_results`, divergence guardrail (`_should_allow_divergence()`). CQS 0.8237→0.8293, EF-CQS 0.8425→0.8558. Completed 2026-04-01. `514fea2f`.

---

## Future Phases (Not Yet Planned)

- **Phase 8: Scale (500→5000)** — Full S&P 500, then Russell 1000, then all XBRL filers
- **Phase 9: Event-driven** — EDGAR RSS feed → single-company extraction within hours of filing
- **Phase 10: Multi-product** — Separate reported data product (SEC-derived) from standardized cross-company data
