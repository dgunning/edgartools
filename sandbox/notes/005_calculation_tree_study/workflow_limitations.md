# Concept Mapping Workflow - Limitations & Findings

**Date:** 2026-01-07  
**Session Result:** 99% mapping coverage achieved, value validation revealed issues

---

## Current Architecture Summary

```
Layer 1: Tree Parser     → 94% (calc tree matching)
Layer 2: AI Semantic     → +2% (custom concepts)
Layer 4: Facts Search    → +3% (concepts not in calc trees)
Reference Validator      → Value comparison with yfinance
```

---

## Limitations Identified

### 1. Calculation Trees Don't Contain All Concepts

**Problem:** Some XBRL concepts exist in facts but not in calculation linkbase.

**Examples:**
- AMZN Capex (`PaymentsToAcquirePropertyPlantAndEquipment`)
- AMZN ShortTermDebt (`ShortTermBorrowings`)
- AAPL Goodwill

**Current Solution:** Facts Search layer searches facts directly.

**Future Improvement:** Build a concept discovery tool that:
- Searches both calc trees AND facts
- Ranks by how close concept name matches target metric
- Returns candidates with confidence scores

---

### 2. Company-Specific Prefixes

**Problem:** Some companies use custom concept prefixes (e.g., `nvda_`, `tsla_`).

**Examples:**
- NVDA: `nvda_PaymentsForFinancedPropertyPlantAndEquipmentAndIntangibleAssetsFinancingActivities`
- TSLA: `tsla_LongTermDebtAndFinanceLeasesCurrent`

**Current Solution:** AI layer can find these, but needs LLM call.

**Future Improvement:** Build a prefix-aware concept matcher that:
- Strips company prefixes before matching
- Maps custom concepts to standard equivalents
- Stores discovered mappings for reuse

---

### 3. Multi-Concept Mapping (Same Metric, Different Names)

**Problem:** Same metric can have different XBRL names across companies.

**Examples:**
| Metric | GOOG | AMZN | NVDA |
|--------|------|------|------|
| Revenue | `RevenueFromContractWithCustomerExcludingAssessedTax` | Same | `Revenues` |
| COGS | `CostOfRevenue` | `CostOfGoodsAndServicesSold` | `CostOfRevenue` |
| SGA | `SellingAndMarketingExpense` | `GeneralAndAdministrativeExpense` | `SellingGeneralAndAdministrativeExpense` |

**Current Solution:** Config lists known_concepts variants.

**Future Improvement:** 
- Auto-expand known_concepts based on discovered mappings
- Use semantic similarity to suggest new variants

---

### 4. Value Validation Mismatches

**Problem:** Some mappings are correct but values don't match yfinance.

**Categories of Mismatches:**

#### a) Sign Conventions
- XBRL Capex is positive (payments), yfinance is negative (outflow)
- **Solution Implemented:** Compare absolute values

#### b) Consolidation Differences
- GOOG TotalAssets: XBRL=184B vs yfinance=450B
- XBRL may report parent-only; yfinance may report consolidated
- **Needs Investigation:** Verify which entity is being reported

#### c) Wrong Concept Fallback
- IntangibleAssets maps to `Assets` when better concept not found
- **Problem:** Medium-confidence fallback is wrong
- **Solution Needed:** Don't fallback to parent concepts; leave unmapped

#### d) Timing Differences
- LongTermDebt: XBRL=9B vs yfinance=10.88B (17% off)
- Could be different reporting dates
- **Tolerance:** Consider 15-20% for some metrics

---

### 5. Metrics Not Applicable to All Companies

**Problem:** Some metrics genuinely don't apply to certain companies.

**Examples:**
- META: No COGS (services company)
- META: No ShortTermDebt
- AAPL: No significant Goodwill (historically)

**Current Solution:** `exclude_metrics` in companies.yaml

**Future Improvement:** Auto-detect "not applicable" when:
- yfinance has no data
- XBRL facts have no matching concept
- Mark as "not_applicable" instead of "not_found"

---

## Tools to Build (Future Work)

### 1. Concept Discovery Tool
```
discover_concepts(metric_name, xbrl) -> List[CandidateConcept]
```
- Search calc trees + facts
- Rank by semantic similarity
- Return with confidence scores

### 2. Mapping Verifier Tool
```
verify_mapping(mapping, xbrl, yfinance) -> ValidationResult
```
- Extract XBRL value
- Compare with reference
- Return match/mismatch with reasoning

### 3. Fallback Quality Checker
```
check_fallback_quality(metric, concept, xbrl) -> QualityScore
```
- Verify concept is semantically correct for metric
- Flag parent-concept fallbacks (e.g., Assets for IntangibleAssets)
- Suggest better alternatives

### 4. Cross-Company Mapper
```
learn_mappings(metric, companies) -> Dict[company, concept]
```
- Run mapping on multiple companies
- Find patterns in concept names
- Update known_concepts automatically

---

## Files Modified This Session

| File | Purpose |
|------|---------|
| `config/metrics.yaml` | 14 target metrics + known concepts |
| `config/companies.yaml` | MAG7 company configs + exclusions |
| `models.py` | MappingResult, AuditLogEntry dataclasses |
| `config_loader.py` | YAML config loading |
| `layers/tree_parser.py` | Layer 1 calc tree matching |
| `layers/ai_semantic.py` | Layer 2 LLM mapping |
| `layers/facts_search.py` | Layer 4 direct facts search |
| `orchestrator.py` | Pipeline runner + XBRL caching |
| `reference_validator.py` | yfinance value comparison |

---

## Next Session Focus

1. Fix IntangibleAssets fallback issue
2. Investigate TotalAssets consolidation difference
3. Build reusable concept discovery tool
4. Improve fallback quality checking
