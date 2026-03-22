# Subscription-Grade Roadmap

*Derived from [Multi-Model Consensus](subscription-grade-consensus.md) -- March 21, 2026*

---

## Origin

This roadmap was synthesized from a structured consensus session between GPT-5.4, Gemini 3.1 Pro, and Claude Opus 4.6 on March 21, 2026. All three models agreed on the priority ordering and key architectural decisions. See the [full consensus document](subscription-grade-consensus.md) for the complete analysis, model arguments, and code-verified findings.

## Current State (Baseline -- 2026-03-21)

| Metric | Value |
|--------|-------|
| CQS | 0.9734 |
| Companies | 100 |
| Metrics | 19 |
| Pass rate | 96.0% |
| Reference source | yfinance (single, scraped) |
| Validation depth | Latest filing only |
| Golden master promotion | min_periods=1 (buggy) |
| Autonomy level | ~95% config-level, 0% code-level |

---

## Phase 1: Fix Governance (Immediate)

**Consensus backing:** All three models flagged these as trust-model inconsistencies that undermine data quality claims. GPT-5.4: "Fix governance bugs first." Gemini: "These are not subscription-grade-safe."

### 1a: Fix golden master promotion threshold

**Problem:** `promote_golden_masters(min_periods=1)` at `auto_eval.py:549` promotes single-period extractions as golden masters, contradicting the stated 3-period requirement.

**Fix:** Change the call site from `min_periods=1` to `min_periods=3`.

**File:** `edgar/xbrl/standardization/tools/auto_eval.py:549`

**Verification:**
```bash
# Before: golden masters created from single-period runs
grep "min_periods=1" edgar/xbrl/standardization/tools/auto_eval.py

# After: only stable multi-period extractions become golden
hatch run python -m pytest tests/xbrl/standardization/ -v -x
```

**Expected impact:** Fewer but more trustworthy golden masters. Short-term golden_master_rate may drop; long-term regression rate will decrease.

### 1b: Replace `reference_value=None` exclusion with "unverified" state

**Problem:** At `auto_eval_loop.py:1442-1452`, when yfinance returns None, the system proposes excluding the metric for that company. This institutionalizes reference gaps as product behavior.

**Fix:** Instead of `ADD_EXCLUSION`, introduce an `unverified` validation status. The metric remains in the pipeline but is marked as "extracted, not externally validated." The solver should still attempt to find formulas using SEC-native validation (Phase 2) or cross-company patterns.

**Files:**
- `edgar/xbrl/standardization/tools/auto_eval_loop.py:1442-1452` -- Replace exclusion with unverified status
- `edgar/xbrl/standardization/tools/auto_eval.py` -- CQS computation may need to handle unverified metrics (don't count as failures, don't count as passes)

**Verification:**
```bash
# Ensure no ADD_EXCLUSION for None reference values
grep -n "ADD_EXCLUSION" edgar/xbrl/standardization/tools/auto_eval_loop.py

# Run 100-company eval -- gaps should show as "unverified" not "excluded"
hatch run python -c "from edgar.xbrl.standardization.tools.auto_eval import compute_cqs, EXPANSION_COHORT_100; r = compute_cqs(eval_cohort=EXPANSION_COHORT_100, snapshot_mode=True); print(r.summary())"
```

**Expected impact:** More gaps become addressable by the solver and future validation layers. Coverage rate may temporarily decrease (unverified != valid), but the system stops hiding data gaps.

### 1c: Add metric-class tolerances

**Problem:** `ExtractionRun.__post_init__` at `schema.py:113` uses a hardcoded 20% tolerance for all metrics. Meanwhile, `metrics.yaml` already defines per-metric tolerances (Capex: 40%, DepreciationAmortization: 30%) that are used by the reference validator but NOT by the `is_valid` flag in the ledger.

**Fix:** Read the metric-specific `validation_tolerance` from `metrics.yaml` when computing `is_valid` in `ExtractionRun`. Fall back to 20% for metrics without a specific tolerance.

**Files:**
- `edgar/xbrl/standardization/ledger/schema.py:113` -- Use metric-specific tolerance
- `edgar/xbrl/standardization/config/metrics.yaml` -- Already has tolerances; ensure all 19 metrics have explicit values

**Verification:**
```bash
# Check that metrics.yaml has tolerances for all metrics
hatch run python -c "
import yaml
with open('edgar/xbrl/standardization/config/metrics.yaml') as f:
    m = yaml.safe_load(f)
for name, cfg in m['metrics'].items():
    tol = cfg.get('validation_tolerance', 'DEFAULT 20%')
    print(f'{name}: {tol}')
"

# Run tests
hatch run python -m pytest tests/xbrl/standardization/ -v -x
```

**Expected impact:** Tighter tolerances for high-confidence metrics (Revenue: 5-10%), looser for structurally variable ones (Capex: 40%). More accurate pass/fail signals.

---

## Phase 2: SEC-Native Self-Validation

**Consensus backing:** All three agreed yfinance is the existential bottleneck. GPT-5.4 proposed a "reference arbitration layer"; Gemini said "ditch yfinance." Claude's resolution: use SEC-native validation first (free, authoritative) before requiring licensed data.

### 2a: XBRL calculation linkbase arithmetic checks

**What:** XBRL filings include calculation linkbases that define arithmetic relationships between concepts (e.g., Assets = CurrentAssets + NoncurrentAssets). Use these to validate that extracted values are internally consistent.

**Why:** This is free, authoritative (defined by the filer), and doesn't require external reference data. It can validate metrics where yfinance returns None.

**Architecture:**
```
Filing XBRL → Parse calculation linkbase → Extract parent-child sums
→ For each extracted metric, check: does sum of children = parent?
→ If yes: mark as "self-validated"
→ If no: flag as "arithmetic inconsistency"
```

**Key files to create/modify:**
- New: `edgar/xbrl/standardization/internal_validator.py` (already exists as stub -- extend it)
- Modify: `edgar/xbrl/standardization/tools/auto_eval.py` -- Add self-validation as secondary check

### 2b: Cross-statement reconciliation

**What:** Verify that values appearing on multiple statements agree. Net Income appears on both the Income Statement and Cash Flow Statement. Total Assets appears on the Balance Sheet in multiple periods.

**Why:** A metric that matches across statements is more trustworthy than one validated only against yfinance.

### 2c: Cross-company consistency checks

**What:** If 90% of tech companies map Revenue to `us-gaap:Revenues`, flag the outlier that maps to `us-gaap:SalesRevenueNet`. Not necessarily wrong, but worth investigation.

**Why:** Statistical consensus across peers is a strong signal. The auto-eval loop can use this as a proposal heuristic for unmapped/high-variance gaps.

**Verification for all of Phase 2:**
```bash
# After implementation, re-run 100-company eval
# Self-validated metrics should appear even where yfinance=None
# Count of "unverified" gaps should decrease
```

---

## Phase 3: Metric Expansion (19 -> 50) + Historical Validation

**Consensus backing:** Both models agreed: expand ontology before scaling companies. GPT-5.4: "Do not scale universe first if ontology is shallow." Gemini: "Users will notice missing debt breakdowns and segment nuance before they care about eval-loop sophistication."

### 3a: Expand metric ontology

Target additions (organized by statement):

**Income Statement (add ~8):**
- GrossProfit, EBITDA, InterestExpense, IncomeTaxExpense, EarningsPerShareBasic, EarningsPerShareDiluted, ResearchAndDevelopment, OtherIncome

**Balance Sheet (add ~10):**
- CurrentAssets, CurrentLiabilities, TotalLiabilities, TotalEquity, RetainedEarnings, PropertyPlantEquipment, CurrentDebt, TotalDebt, CashFromInvestments, OtherLongTermAssets

**Cash Flow (add ~6):**
- FreeCashFlow (derived: OperatingCashFlow - Capex), NetChangeInCash, DebtRepayment, EquityIssuance, DebtIssuance, AcquisitionSpending

**Per-Share (add ~4):**
- BookValuePerShare, RevenuePerShare, DividendPerShare, TangibleBookValuePerShare

**Files:**
- `edgar/xbrl/standardization/config/metrics.yaml` -- Add metric definitions, known_concepts, tolerances
- `edgar/xbrl/standardization/config/industry_metrics.yaml` -- Add forbidden/required/alternative per industry
- May need new extraction strategies for derived metrics

### 3b: Historical / longitudinal validation

**What:** Validate across trailing 3 annual + 4 quarterly periods per company, not just the latest filing.

**Why:** A formula that works for one period may be coincidental. Multi-period stability is the strongest signal of correctness. The solver already supports `multi_period=True` for formula discovery; extend this to the validation layer.

### 3c: Industry applicability engine

**What:** Replace simple universal/non-universal flags with a structured model: required/optional/forbidden per metric per industry archetype.

**Example:**
- Revenue: required for all
- Inventory: required for retail/manufacturing, optional for tech, forbidden for banking
- NetInterestIncome: required for banking, forbidden for non-financial

**Files:**
- `edgar/xbrl/standardization/config/industry_metrics.yaml` -- Extend with required/optional/forbidden
- `edgar/xbrl/standardization/tools/auto_eval.py` -- CQS should not penalize missing forbidden metrics

---

## Phase 4: Company Scaling (100 -> 500) + Reference Diversification

**Consensus backing:** Both models agreed this comes AFTER metric expansion. GPT-5.4: scaling order is "truth model -> historical validation -> metric breadth -> company breadth -> freshness."

### 4a: S&P 500 coverage

Scale from 100 to 500 companies. The `EXPANSION_COHORT_500` already exists in `auto_eval.py`. Key challenges:
- More industry archetypes (REITs, utilities, insurance, biotech)
- More extension taxonomies (company-specific XBRL concepts)
- More edge cases in accounting treatments

### 4b: SEC EDGAR XBRL fact API as second reference

**What:** The SEC provides a free XBRL fact API (`data.sec.gov/api/xbrl/`) that returns reported values by concept. Use this as a second reference source alongside yfinance.

**Why:** Free, authoritative (direct from SEC filings), covers all XBRL filers. Doesn't have the "scraped/unreliable" problems of yfinance.

### 4c: Event-driven filing processing

**What:** Replace `run_overnight()` batch mode with event-driven architecture that processes new filings as they appear on EDGAR.

**Why:** Subscription services update within hours of filing. Batch mode introduces unacceptable latency for paid users.

**Architecture sketch:**
```
EDGAR RSS Feed → Filing Event Queue
  → Extract (single company, triggered by new filing)
  → Validate (self-check + external references)
  → Risk Score → Publish/Hold/Escalate
  → If Hold: route to exception queue for review
```

---

## Target Architecture (End State)

```
Filing Event (EDGAR RSS)
  -> Ingestion (accession-based, amendment detection)
  -> Canonical Fact Store (concept/context/unit/dimensions/period)
  -> Metric Resolver (5-layer: tree -> facts -> config -> industry -> composite)
  -> Validation Layer:
      |-- Self-check: XBRL calc linkbase arithmetic
      |-- Cross-check: cross-statement reconciliation
      |-- External check: yfinance + SEC XBRL API
      |-- Confidence score: high / medium / low / unverified
  -> Risk Engine:
      |-- High confidence -> auto-publish
      |-- Medium confidence -> publish with flag
      |-- Low confidence -> hold for review
      |-- Unverified -> publish as "extracted, unverified"
  -> Auto-Eval Loop (for low/unverified):
      |-- Solver proposes config changes
      |-- GPT escalation for novel concepts
      |-- Graveyard + circuit breakers
```

---

## Phase Completion Tracking

| Phase | Target | Started | Completed | CQS Before | CQS After | Key Findings |
|-------|--------|---------|-----------|------------|-----------|--------------|
| 1a: Fix min_periods | min_periods=3 | 2026-03-21 | 2026-03-21 | 0.9734 | 0.9111 | Changed call site to use default min_periods=3. CQS drop expected: stricter golden masters + 37 metrics (vs 19). |
| 1b: Unverified state | Replace exclusion | 2026-03-21 | 2026-03-21 | - | - | Replaced ADD_EXCLUSION with None return + log. Kept AI scout exclusion path (line 2655). |
| 1c: Metric tolerances | Per-metric thresholds | 2026-03-21 | 2026-03-21 | - | - | Added validation_tolerance field to ExtractionRun. 6/19 metrics have explicit tolerances; rest use 20% default. |
| 2a: Calc linkbase | Self-validation | 2026-03-21 | 2026-03-21 | - | - | Wired InternalConsistencyValidator into validate_and_update_mappings. 5 equations (4 accounting + 1 cross-statement). Internal override: if equations pass but yfinance disagrees, trust extraction. |
| 2b: Cross-statement | Reconciliation checks | 2026-03-21 | 2026-03-21 | - | - | Added PretaxIncome >= NetIncome cross-statement equation. |
| 2c: Cross-company | Peer consistency | 2026-03-21 | 2026-03-21 | - | - | Added compute_concept_consensus() method. Informational for now — becomes proposal heuristic in later phases. |
| 3a: Metric expansion | 19 -> 50 metrics | 2026-03-22 | 2026-03-22 | 0.9734 | 0.9111 | Added 18 base metrics (37 total) + 3 derived (EBITDA, WorkingCapital, TotalDebt) + 15 yfinance mappings. CQS denominator grew 2x; new metrics not yet tuned. |
| 3b: Historical | 3 annual + 4 quarterly | - | - | - | - | Deferred — requires orchestrator changes. Solver already supports multi_period=True. |
| 3c: Applicability | Required/optional/forbidden | 2026-03-22 | 2026-03-22 | - | - | Added PropertyPlantEquipment, R&D to banking forbidden list. ShareRepurchases re-enabled for banks (they do buybacks). |
| 4a: S&P 500 | 500 companies | - | - | - | - | EXPANSION_COHORT_500 ready (500 companies). Needs yfinance snapshots for ~400 new companies (runtime task). |
| 4b: SEC XBRL API | Second reference source | 2026-03-22 | 2026-03-22 | 0.9111 | 0.9118 | SEC facts fallback enabled. 120 SEC facts matches in overnight run. 18/18 experiments kept (0 discards). Banking sector (JPM, C, MS, GS, BLK) primary beneficiary — 17 solver formulas for previously unreachable gaps. |
| 4c: Event-driven | Real-time processing | - | - | - | - | Deferred. URL builders exist but no RSS parser/monitor. |

### Overnight Run 004 Summary (2026-03-22)

- **Duration:** 3.1 hours on 100 companies, 37 metrics
- **Result:** 18/18 experiments kept, 0 discards, 0 vetoes
- **CQS:** 0.9111 -> 0.9118 (+0.0007)
- **EF-CQS:** 0.6569 -> 0.6582, **SA-CQS:** 0.6539 -> 0.6552
- **Key bugs fixed this session:**
  - `us-gaap:` prefix missing in SEC facts lookup (all lookups silently returned None)
  - Fast-path gap derivation dropped `reference_value` (solver blocked after every KEEP)
- **Companies solved:** JPM (3 metrics), C (3), MS (5), GS (5), BLK (1), PLD (1)
- **Stop reason:** 3-hour time limit (natural end, not circuit breaker)

---

## Related Documents

- [Multi-Model Consensus](subscription-grade-consensus.md) -- Full analysis from GPT-5.4, Gemini 3.1, and Claude
- [Auto-Eval Strategy](auto-eval-strategy.md) -- Technical architecture of the CQS loop
- [Verification Roadmap](verification-roadmap.md) -- Parallel track for test/verification quality
