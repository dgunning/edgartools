# Banking GAAP Extraction: E2E Progress Tracking
## Comprehensive Comparison Across All Runs

**Date:** 2026-01-24
**Current Branch:** feature/ai-concept-mapping

---

## Executive Summary: Pass Rate Evolution

| Run Date | Commit | 10-K | 10-Q | Total Failures | Key Changes |
|----------|--------|------|------|----------------|-------------|
| 2026-01-21 23:22 | Before fixes | 33.3% (5/15) | 73.7% (14/19) | 15 | Baseline - many CashAndEquivalents failures |
| 2026-01-22 21:29 | 35a2ae90 | **81.8% (18/22)** | **90.0% (27/30)** | 7 | GAAP remediation for dealers, maturity schedules |
| 2026-01-23 12:09 | aff18492 | 72.7% (16/22) | 93.3% (28/30) | 8 | Architect Directives (regression in 10-K) |
| **2026-01-24 00:04** | **Current** | **81.8% (18/22)** | **80.0% (24/30)** | **10** | Phase 2 archetype-driven extraction |

---

## What Got Better (Phase 2 vs Previous Best)

### 1. GS 10-K: FIXED
| Metric | Before (01-23) | After (01-24) | Change |
|--------|----------------|---------------|--------|
| Extracted | $69.7B | $90.6B | ✅ **PASS** |
| Reference | $90.6B | $90.6B | - |
| Variance | 23.1% | <1% | **-22.1 pp** |

**Reason:** Dealer extraction now correctly adds CPLTD (~$21B) to UnsecuredSTB.

### 2. USB 10-Ks: FIXED (Both Years)
| Filing | Before (01-23) | After (01-24) | Change |
|--------|----------------|---------------|--------|
| 2024 10-K | $15.5B (103.5% variance) | $7.6B | ✅ **PASS** |
| 2023 10-K | $15.3B (33.4% variance) | $11.5B | ✅ **PASS** |

**Reason:** Commercial archetype now uses bottom-up extraction (CP + FHLB + OtherSTB + CPLTD) which finds correct components.

### 3. WFC 10-K Variance Massively Improved
| Filing | Before (01-23) | After (01-24) | Improvement |
|--------|----------------|---------------|-------------|
| 2024 10-K | $108.8B (701.8%) | $6.6B (51.3%) | **-650 pp variance** |
| 2023 10-K | $89.6B (653.7%) | $14.6B (23.2%) | **-630 pp variance** |

**Reason:** Archetype-driven top-down extraction now subtracts repos ($54B) and trading liabilities ($48B). Still not perfect but dramatically improved.

### 4. CashAndEquivalents: 100% Pass Rate Maintained
All 9 banks pass CashAndEquivalents extraction - no regressions from previous fixes.

---

## What Got Worse (Phase 2 Regressions)

### 1. JPM: NEW Failures (3 filings)
| Filing | Before (01-22) | After (01-24) | Issue |
|--------|----------------|---------------|-------|
| 2024 10-K | ✅ PASS | ❌ $49.7B vs $64.5B (22.9%) | Under-extracting |
| 2025 Q3 10-Q | ✅ PASS | ❌ $0 vs $69.4B (100%) | Returns $0 |
| 2025 Q2 10-Q | ✅ PASS | ❌ $0 vs $65.3B (100%) | Returns $0 |

**Root Cause:** Hybrid extraction method (`_extract_hybrid_stb`) uses `stb + cpltd` but:
- 10-K: ShortTermBorrowings is $0 or missing, falls back incorrectly
- 10-Q: No ShortTermBorrowings found at all in quarterly filings

**Why It Happened:** Before Phase 2, JPM was using a different code path that found values. The refactored archetype dispatch routes to `_extract_hybrid_stb()` which has stricter logic.

### 2. USB 10-Q: NEW Failures (1 additional)
| Filing | Before (01-22) | After (01-24) | Issue |
|--------|----------------|---------------|-------|
| 2025 Q3 10-Q | ✅ PASS | ❌ $0 vs $15.4B (100%) | Returns $0 |
| 2025 Q2 10-Q | ❌ FAIL | ❌ $2.2B vs $15.0B (85.5%) | Still failing |

**Root Cause:** Bottom-up extraction finds no components in 10-Q filings. Top-down fallback doesn't trigger or finds wrong values.

### 3. Overall 10-Q Pass Rate Declined
- **Before (01-22):** 90.0% (27/30)
- **After (01-24):** 80.0% (24/30)
- **Delta:** -10.0 pp (3 additional failures)

**Root Cause:** The archetype-driven refactoring was optimized for 10-K (annual) filings. 10-Q filings have:
- Different XBRL structure (less detail)
- Period filtering issues (`_get_fact_value()` may select wrong period)
- Missing components (banks report less granularly in quarterly filings)

---

## Unchanged Failures (Persistent Issues)

### WFC 10-Qs: Still Failing
| Filing | 01-21 | 01-22 | 01-24 | Status |
|--------|-------|-------|-------|--------|
| 2025 Q3 | $230.6B (533%) | $79.7B (119%) | $79.7B (119%) | Improved but still failing |
| 2025 Q2 | $188.0B (453%) | $78.6B (131%) | $78.6B (131%) | Improved but still failing |

**Root Cause:** Commercial extraction still not subtracting repos/trading in 10-Q filings. The suffix matching for `wfc:SecuritiesSoldUnderAgreementsToRepurchase` may not be finding the concept in quarterly data.

### STT 10-K: Persistent Failure
| Filing | All Runs | Issue |
|--------|----------|-------|
| 2023 10-K | ~$1.9-2.7B vs $4.6B (42-60% variance) | Custodial extraction incomplete |

**Root Cause:** STT has no `ShortTermBorrowings` tag. Custodial extraction finds partial components but not all. This is expected behavior per architect directive (return partial rather than fuzzy match).

---

## Commit Timeline Analysis

```
01-21 23:22  Baseline: 15 failures (5/15 10-K, 14/19 10-Q)
     │
     ├── 35a2ae90 fix(banking): Remediate GAAP extraction for dealers, maturity schedules
     │   - Fixed BK/MS/PNC CashAndEquivalents
     │   - Added CashAndDueFromBanks hierarchy
     │   - Removed maturity schedule fallback (was over-extracting)
     │
01-22 21:29  Best 10-Q: 7 failures (18/22 10-K, 27/30 10-Q)
     │
     ├── aff18492 feat(banking): Implement Architect Directives for GAAP extraction
     │   - Added _is_concept_nested_in_stb() linkbase check
     │   - Added _get_dimensional_sum() fallback
     │   - Added archetype config to companies.yaml
     │   - REGRESSION: USB 10-Ks started failing
     │
01-23 12:09  Architect Directives: 8 failures (16/22 10-K, 28/30 10-Q)
     │
     ├── [Current Changes] Phase 2 Implementation
     │   - Added ARCHETYPE_EXTRACTION_RULES dictionary
     │   - Added _get_repos_value() with suffix matching
     │   - Refactored to archetype-driven dispatch
     │   - Added _extract_custodial_stb, _extract_commercial_stb, etc.
     │   - FIXED: GS 10-K, USB 10-Ks
     │   - REGRESSION: JPM 10-K/10-Qs, USB 10-Q
     │
01-24 00:04  Phase 2: 10 failures (18/22 10-K, 24/30 10-Q)
```

---

## Root Cause Summary

| Issue | Root Cause | Affected | Fix Priority |
|-------|------------|----------|--------------|
| JPM returns $0 | Hybrid extraction doesn't find STB in JPM filings | JPM 10-K, 10-Qs | P0 |
| 10-Q period filtering | `_get_fact_value()` may select wrong quarter | USB, JPM 10-Qs | P0 |
| WFC 10-Q repos not subtracted | Suffix matching not finding wfc: concepts in 10-Q | WFC 10-Qs | P1 |
| STT incomplete components | No STB tag, partial component detection | STT 10-K | P2 (expected) |

---

## Recommended Actions

### Immediate (P0)
1. **Debug JPM extraction path** - Add logging to see why STB returns $0
2. **Add 10-Q period targeting** - Explicitly filter for 90-day periods in `_get_fact_value()`
3. **Test hybrid extraction fallback** - If STB is $0, try component sum

### Short-term (P1)
1. **Debug WFC 10-Q repos detection** - Verify suffix matching works on quarterly XBRL
2. **Add extraction strategy logging** - Track which code path is used

### Accepted (P2)
1. **STT incomplete extraction** - Expected per architect directive (safe_fallback=false)

---

## Net Assessment

| Metric | Verdict |
|--------|---------|
| **10-K Extraction** | ✅ **Improved** (72.7% → 81.8%) - GS and USB fixed |
| **10-Q Extraction** | ⚠️ **Regressed** (93.3% → 80.0%) - JPM/USB quarterly failures |
| **WFC Variance** | ✅ **Dramatically Improved** (700% → 50%) |
| **Archetype Design** | ✅ **Sound** - dealer/commercial separation working |
| **Quarterly Handling** | ❌ **Needs Work** - period filtering and fallback logic |

**Overall:** The archetype-driven design is correct, but the implementation needs refinement for quarterly filings. The 10-K improvements validate the approach; the 10-Q regressions indicate missing fallback logic.

---

*Report generated: 2026-01-24*
*Comparing: e2e_banks_2026-01-21 through e2e_banks_2026-01-24*
