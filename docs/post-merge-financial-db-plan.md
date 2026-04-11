# Post-Merge Financial Database Plan

> **Branch**: `feature/ai-concept-mapping` | **Report Date**: 2026-03-03
> **Predecessor**: `docs/post-merge-financial-db-assessment.md`
> **Scope**: 3-phase roadmap to reach 99%+ extraction accuracy for 33 standard industrial companies

---

## 1. Executive Summary

### Where We Are

**Baseline (Jan 27):** 95.6% 10-K (518/542) / 96.4% 10-Q (516/535) across 33 standard industrial companies with 43 real failures.

**Since then (5 commits):**

| Commit | What It Built |
|--------|---------------|
| `df85d819` | GAAP expansion — expanded `known_concepts` using upstream GAAP mappings |
| `a5fc957e` | Wired ExperimentLedger into E2E script, recorded 1,104 extraction runs |
| `632676e6` | Regression detection system with golden master promotion + cohort testing |
| `743b7056` | Yfinance reference snapshot system for deterministic E2E validation |
| `956d7a35` | Generated initial yfinance snapshots for all 43 companies |

**Net progress:** 4 failures fixed (39 remain), but infrastructure is dormant:
- Ledger has 1,104 extraction runs (from a single E2E), but **0 golden masters** (promotion requires 3+ distinct periods per combo — current runs cover only 1 period)
- Cohort reactor code exists but has **0 cohort tests** recorded
- Snapshot system has reference data for 43 companies but has **never been used as E2E source**

**Mar 2 E2E shows 76%/78%** — this is yfinance reference drift, not code regression. The 217 "new failures" show 50-99% variance on stable metrics like Revenue and TotalAssets, confirming yfinance values shifted over the 5-week gap (Jan 27 → Mar 2). The snapshot system was built specifically to solve this.

### Where We're Going

```
Phase 1: Activate Infrastructure  →  Deterministic baseline + golden masters + cohort testing
Phase 2: Resolve Failures         →  Fix 39 structural failures using static concept discovery
Phase 3: Expansion                →  Archetype C, gaap_mappings fallback, new companies
```

**Target:** 99%+ pass rate on 33 industrial companies with full regression protection.

---

## 2. Phase 1: Activate Infrastructure

> **Goal**: Establish a deterministic, regression-protected baseline before touching any extraction logic.
>
> **Why first**: Every fix in Phase 2 risks breaking something. Without golden masters and cohort testing, regressions are invisible.

### 2.1 Fix E2E Baseline (Fresh Run with Snapshots)

Run a fresh E2E with `snapshot_mode=True` to use frozen yfinance reference data instead of live API calls. This eliminates the reference drift problem that inflated Mar 2 failures from 43 to 256.

**Expected outcome:** Pass rates return to ~95.6%/96.4% (baseline) plus the 4 GAAP expansion fixes, giving ~96.0%/96.8%.

**Action:**
```bash
python sandbox/notes/010_standard_industrial/run_e2e_industrial.py \
    --snapshot-mode --workers 8 --years 1 --quarters 1
```

### 2.2 Extended E2E Run (Multi-Period)

Run E2E in extended mode covering 5 fiscal years + 4 quarters per company. This generates the period diversity required for golden master promotion.

**Why:** Golden master promotion requires `COUNT(DISTINCT fiscal_period) >= 3` per (ticker, metric, strategy) combo. The current ledger has at most 2 distinct periods (1 annual + 1 quarterly from Jan 27 run). Extended mode produces up to 9 comparison points (5 annual + 4 quarterly).

**Action:**
```bash
python sandbox/notes/010_standard_industrial/run_e2e_industrial.py \
    --snapshot-mode --workers 8 --years 5 --quarters 4
```

### 2.3 Promote Golden Masters

After the extended run populates the ledger with multi-period data, run golden master promotion to lock in stable configurations.

**Promotion criteria** (from `ledger/schema.py:610-661`):
- `is_valid = 1` (variance <= 20%)
- `COUNT(DISTINCT fiscal_period) >= 3`
- `AVG(variance_pct) <= 20.0`

**Action:**
```python
from edgar.xbrl.standardization.ledger import ExperimentLedger
ledger = ExperimentLedger()
promoted = ledger.promote_golden_masters(min_periods=3, max_variance=20.0)
print(f"Promoted {len(promoted)} golden masters")
```

**Expected yield:** ~500-600 golden masters (33 companies x 21 direct metrics, minus structural failures and skipped divergences).

### 2.4 Validate Cohort Reactor

Execute the cohort reactor on the `Industrial_33` cohort with no strategy changes. This validates that the reactor produces a PASS result against the baseline — confirming it can detect regressions when Phase 2 introduces changes.

**Action:**
```python
from edgar.xbrl.standardization.reactor.cohort_reactor import CohortReactor
reactor = CohortReactor(ledger=ledger)
result = reactor.test_cohort("Industrial_33", strategy_change=None)
assert result.is_passing, f"Baseline should pass: {result.regressed_count} regressions"
```

### Success Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| E2E with snapshots matches baseline | >=96.0% 10-K, >=96.8% 10-Q | E2E report pass rates |
| Golden masters promoted | >=400 | `SELECT COUNT(*) FROM golden_masters WHERE is_active = 1` |
| Cohort reactor baseline | PASS (0 regressions) | `CohortTestResult.is_passing == True` |
| Ledger extraction runs | >=5,000 | `SELECT COUNT(*) FROM extraction_runs` |

---

## 3. Phase 2: Resolve Failures (Static-First)

> **Goal**: Fix the 39 remaining structural failures using `search_concepts()` for static concept discovery. Gate every batch of fixes with `ledger.check_regressions()` against Phase 1 golden masters.
>
> **Approach**: For each failure cluster, discover what XBRL concepts the company actually files, then categorize the fix:
> - **known_concepts expansion** (broad) — add concept to `metrics.yaml` for all companies
> - **preferred_concept override** (company-specific) — set in `companies.yaml`
> - **skip_validation** (structural divergence) — accept and document in `companies.yaml`

### 3.1 ShortTermDebt Cluster (14 failures)

The largest failure cluster. Root causes vary by company but share a common theme: non-standard debt classification that doesn't map to `ShortTermBorrowings`.

| Company | Forms | Root Cause | Likely Fix |
|---------|-------|------------|------------|
| GE | 10-K, 10-Q | Post-Vernova spin-off restructured balance sheet | `search_concepts("debt")` → preferred_concept |
| RTX | 10-K, 10-Q | Defense/aerospace complex balance sheet | preferred_concept or known_concepts |
| DE | 10-K, 10-Q | John Deere Financial subsidiary not separated | skip_validation (financial subsidiary) |
| HSY | 10-K, 10-Q | Multi-metric structural complexity | known_concepts expansion (GAAP fix resolved 10-K) |
| KO | 10-K | Bottling subsidiary debt structure | `search_concepts("debt")` → investigate dimensional |
| PEP | 10-K | Similar to KO — bottler structure | Same approach as KO |
| COST | 10-K | Non-standard debt classification | preferred_concept |
| COP | 10-K | E&P industry-specific balance sheet | preferred_concept or energy archetype |

**First action:** Run `search_concepts("debt")` on all 8 companies, categorize findings, batch-apply fixes, then regression-check.

### 3.2 Capex Cluster (8 failures)

All 4 companies (GE, RTX, DE, HSY) fail on both 10-K and 10-Q. Capex concepts vary significantly across industries — defense contractors, conglomerates, and consumer staples each use different cash flow line items.

| Company | Forms | Root Cause | Likely Fix |
|---------|-------|------------|------------|
| GE | 10-K, 10-Q | Spin-off restructured cash flow | preferred_concept |
| RTX | 10-K, 10-Q | Defense contractor capex classification | preferred_concept |
| DE | 10-K, 10-Q | Financial subsidiary investing activities | skip_validation |
| HSY | 10-K, 10-Q | Multiple investing line items | known_concepts expansion |

**First action:** Run `search_concepts("capital expenditure")` and `search_concepts("purchase of property")` on all 4 companies.

### 3.3 DepreciationAmortization Cluster (4 failures)

| Company | Forms | Root Cause | Likely Fix |
|---------|-------|------------|------------|
| HSY | 10-K | Structural complexity | known_concepts expansion |
| RTX | 10-K | Defense sector D&A structure | preferred_concept |
| COP | 10-K, 10-Q | E&P-specific DD&A concepts (depletion) | preferred_concept |

**First action:** Run `search_concepts("depreciation")` — energy companies often use "Depletion, Depreciation and Amortization" (DD&A) which is a different XBRL concept.

### 3.4 AccountsPayable Cluster (3 failures)

| Company | Forms | Root Cause | Likely Fix |
|---------|-------|------------|------------|
| HSY | 10-K, 10-Q | Structural complexity | known_concepts expansion |
| PEP | 10-Q | AccruedLiabilities bundling | preferred_concept |

**First action:** Run `search_concepts("payable")` on HSY and PEP.

### 3.5 Remaining Failures (10)

| Company | Metric | Forms | Root Cause | Likely Fix |
|---------|--------|-------|------------|------------|
| GE | COGS | 10-Q | Vernova spin-off (10-K already skipped) | skip_validation |
| NVDA | WeightedAverageSharesDiluted | 10-K, 10-Q | 10:1 stock split (June 2024) | Already skip_validation — won't fix |
| KO | IntangibleAssets | 10-Q | Uses IndefiniteLivedTrademarks | known_concepts expansion |
| COST | DepreciationAmortization | 10-K | Warehouse depreciation structure | preferred_concept |
| CAT | multiple | already skipped | Cat Financial subsidiary | Already skip_validation |

### Regression Protocol

Every batch of fixes follows this protocol:

1. **Apply changes** to `metrics.yaml` (known_concepts) or `companies.yaml` (preferred_concept / skip_validation)
2. **Run E2E** with `snapshot_mode=True` on affected companies
3. **Check regressions** against golden masters:
   ```python
   report = ledger.check_regressions(strategy_fingerprint=current_fingerprint)
   assert not report.has_regressions, f"{len(report.regressions)} regressions detected"
   ```
4. **Record results** to ledger for provenance
5. **If regression detected**: revert change, investigate, try narrower fix

### Target Metrics

| Metric | Baseline Failures | Target After Phase 2 | Path |
|--------|-------------------|---------------------|------|
| ShortTermDebt | 14 | <=4 | Fix 8 via concepts, skip 2 (DE, structural) |
| Capex | 8 | <=2 | Fix 4 via concepts, skip 2 (DE, structural) |
| DepreciationAmortization | 4 | 0 | Fix 3 via concepts, 1 via preferred_concept |
| AccountsPayable | 3 | <=1 | Fix 2 via concepts |
| Other | 10 | <=3 | Mix of concept fixes and skip_validation |
| **Total** | **39** | **<=10** | **~75% reduction** |

**Overall target:** >=98% 10-K / >=98.5% 10-Q (up from 95.6%/96.4%)

---

## 4. Phase 3: Expansion

> **Goal**: Extend coverage to new company archetypes, wire remaining infrastructure, and establish continuous regression testing.

### 4.1 Archetype C Validation (SaaS Companies)

Current MAG7 companies (MSFT, GOOG, META, NVDA) pass as Archetype A (Standard Industrial). Archetype C (Intangible Digital) was designed to handle tech/SaaS companies differently — particularly around intangible assets, R&D capitalization, and stock-based compensation.

**New companies to add:**

| Ticker | Name | Why |
|--------|------|-----|
| CRM | Salesforce | Pure SaaS, heavy intangible assets |
| ADBE | Adobe | SaaS transition, subscription revenue |
| SNOW | Snowflake | Cloud-native, non-standard revenue recognition |
| NOW | ServiceNow | Enterprise SaaS, high SBC-to-revenue ratio |

**Action:**
1. Define Archetype C extraction rules in `archetypes/definitions.py`
2. Add company configs to `companies.yaml` with `archetype: "C"`
3. Generate yfinance snapshots for new companies
4. Run E2E on SaaS cohort with Archetype C active
5. Compare pass rates vs Archetype A baseline

**Success criteria:** Archetype C pass rate >= Archetype A for the same companies. No regressions on existing companies.

### 4.2 gaap_mappings Fallback Layer

11,444 upstream GAAP tag mappings sit in `config/upstream_gaap_mappings.json`, unwired. These represent pure upside as a fallback lookup after our `known_concepts` matching in `facts_search.py`.

**Integration plan:**
1. Load `upstream_gaap_mappings.json` in `config_loader.py`
2. Add fallback step in `layers/facts_search.py`: after `known_concepts` fail, check gaap_mappings
3. Wire `upstream_section_membership.json` (96 concepts) as disambiguation signal
4. Run E2E to measure coverage delta
5. Gate with regression check against golden masters

**Risk mitigation:** gaap_mappings have not been reconciled against our 24-metric `metrics.yaml` definitions. Before wiring as fallback, verify that gaap_mappings concepts for each metric produce valid extractions on at least 3 test companies.

**Success criteria:** >=5 previously-failing metrics now pass. Zero regressions on existing passes.

### 4.3 Continuous Regression Testing

Create a pytest test that loads the production ledger and checks for regressions against golden masters. This becomes a CI gate — any PR that regresses a golden master is blocked.

**Implementation:**
```python
# tests/regression/test_golden_masters.py
def test_no_golden_master_regressions():
    """Ensure no golden master regressions exist."""
    ledger = ExperimentLedger()
    fingerprint = get_current_strategy_fingerprint()
    report = ledger.check_regressions(strategy_fingerprint=fingerprint)
    assert not report.has_regressions, (
        f"{len(report.regressions)} regressions: "
        + ", ".join(f"{r.ticker}/{r.metric}" for r in report.regressions)
    )
```

### 4.4 New Company Onboarding

After Phase 2 proves the concept mapping workflow, onboard companies from additional sectors:

| Sector | Candidates | Archetype |
|--------|------------|-----------|
| Insurance | BRK, MET, AIG | E (Insurance) |
| Utilities | NEE, DUK, SO | A (Standard) with sector overrides |
| Real Estate | AMT, PLD, SPG | D (Platform) |

Each onboarding follows the same workflow: add to `companies.yaml`, generate snapshots, run E2E, fix failures, promote golden masters.

---

## 5. Risk Register

| Risk | Severity | Mitigation | Owner |
|------|----------|------------|-------|
| **Snapshot staleness** | Medium | Snapshots freeze yfinance values at generation time. If a company restates financials, snapshots become inaccurate. Regenerate snapshots quarterly. | Phase 1 |
| **Golden master threshold too loose** | Medium | 20% variance threshold may promote configurations that are technically "passing" but meaningfully wrong. Review promoted masters manually for first batch. | Phase 1 |
| **GAAP expansion false positives** | Medium | Expanded `known_concepts` (e.g., Revenue 10→81 concepts) may match wrong concepts for some companies. Monitor per-company variance after expansion. | Phase 2 |
| **Financial subsidiary contamination** | High | DE, CAT have captive financial subsidiaries whose debt/receivables inflate consolidated totals. Skip_validation is correct for now, but long-term needs dimensional filtering. | Phase 2 |
| **Archetype C definition risk** | Low | If Archetype C rules don't improve over Archetype A for tech companies, the archetype system adds complexity without value. Fall back to Archetype A with metric overrides. | Phase 3 |
| **Upstream drift** | Medium | 478 commits merged in ~2 months. Schedule quarterly merges (next: ~2026-06-01) to prevent divergence. | Ongoing |

---

## 6. Key Files Reference

### Configuration

| File | Purpose | Phase |
|------|---------|-------|
| `edgar/xbrl/standardization/config/companies.yaml` | Company configs, known divergences, metric overrides (43 companies) | 1, 2 |
| `edgar/xbrl/standardization/config/metrics.yaml` | 24 metric definitions with known_concepts | 2 |
| `edgar/xbrl/standardization/config/upstream_gaap_mappings.json` | 11,444 upstream GAAP tag mappings (not wired) | 3 |
| `edgar/xbrl/standardization/config/upstream_section_membership.json` | 96 concept section memberships (not wired) | 3 |

### Infrastructure

| File | Purpose | Phase |
|------|---------|-------|
| `edgar/xbrl/standardization/ledger/schema.py` | ExperimentLedger — extraction runs, golden masters, regression detection | 1 |
| `edgar/xbrl/standardization/reactor/cohort_reactor.py` | Cohort-level regression testing | 1 |
| `edgar/xbrl/standardization/reference_validator.py` | Yfinance comparison and quarterly derivation | 1, 2 |
| `edgar/xbrl/standardization/archetypes/definitions.py` | Archetype A-E definitions (C/D/E untested) | 3 |

### Extraction Pipeline

| File | Purpose | Phase |
|------|---------|-------|
| `edgar/xbrl/standardization/layers/tree_parser.py` | Primary extraction — calc tree traversal | 2 |
| `edgar/xbrl/standardization/layers/facts_search.py` | Fallback — direct fact lookup | 2, 3 |
| `edgar/xbrl/standardization/layers/ai_semantic.py` | Last resort — LLM-powered concept matching | 2 |

### E2E & Reports

| File | Purpose |
|------|---------|
| `sandbox/notes/010_standard_industrial/reports/e2e_industrial_2026-01-27_1610.md` | Baseline report: 95.6%/96.4%, 43 failures |
| `sandbox/notes/010_standard_industrial/reports/e2e_industrial_2026-03-02_1840.md` | Latest report: 76.1%/77.6% (yfinance drift, not regression) |
| `sandbox/notes/010_standard_industrial/reports/gaap_expansion_assessment_2026-03-02.md` | GAAP expansion impact: 4 fixes, 39 remaining |
| `docs/post-merge-financial-db-assessment.md` | Full post-merge assessment (predecessor document) |
