# Concept Mapping Workflow - Complete Architecture Review

## High-Level Workflow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           STEP 1: PROGRAMMER RUNS STATIC                        │
│                                                                                 │
│  Run: orchestrator.map_companies(tickers=['AAPL', ...], use_ai=False)           │
│                                                                                 │
│  What happens:                                                                  │
│    Layer 1: Tree Parser     → Matches concepts from calculation trees           │
│    Layer 4: Facts Search    → Searches facts for concepts not in trees          │
│    Reference Validator      → Compares extracted values with yfinance           │
│                                                                                 │
│  Output: Dict[ticker, Dict[metric, MappingResult]]                              │
│    - Each MappingResult has: concept, confidence, validation_status             │
│    - Gaps flagged as: is_mapped=False OR validation_status="invalid"            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼ (Gaps identified)
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           STEP 2: AGENT RESOLVES GAPS                           │
│                                                                                 │
│  Who: concept-mapping-resolver agent (or /resolve-gaps command)                 │
│                                                                                 │
│  What happens:                                                                  │
│    1. Calculate "before" coverage                                               │
│    2. For each gap, invoke tools:                                               │
│       a) discover_concepts() → Find candidate concepts                          │
│       b) check_fallback_quality() → Reject parent-concept fallbacks             │
│       c) verify_mapping() → Compare XBRL value vs yfinance                      │
│    3. Accept if quality passes AND verification matches (<10% variance)         │
│    4. Calculate "after" coverage                                                │
│    5. Learn patterns from failures (learn_mappings)                             │
│    6. Auto-update metrics.yaml with new concepts                                │
│                                                                                 │
│  Output: ResolutionReport with before/after coverage, resolved gaps, failures   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Files & Components Map

| Component | File | Purpose |
|-----------|------|---------|
| **Orchestrator** | `edgar/xbrl/standardization/orchestrator.py` | Runs static layers, caches XBRL |
| **Layer 1: Tree Parser** | `layers/tree_parser.py` | Matches from calculation linkbase |
| **Layer 4: Facts Search** | `layers/facts_search.py` | Searches facts for missing concepts |
| **Reference Validator** | `reference_validator.py` | Compares XBRL values to yfinance |
| **Models** | `models.py` | MappingResult, ConfidenceLevel.INVALID |
| **Tool: discover_concepts** | `tools/discover_concepts.py` | Agent searches for candidates |
| **Tool: check_fallback_quality** | `tools/check_fallback_quality.py` | Agent validates concept quality |
| **Tool: verify_mapping** | `tools/verify_mapping.py` | Agent verifies value match |
| **Tool: learn_mappings** | `tools/learn_mappings.py` | Agent finds cross-company patterns |
| **Tool: resolve_gaps** | `tools/resolve_gaps.py` | Main orchestration for agent workflow |
| **Agent** | `.claude/agents/concept-mapping-resolver.md` | Agent instructions |
| **Command** | `.claude/commands/resolve-gaps.md` | Slash command to invoke agent |

---

## Where the Issue Is

### ✅ Step 1 (Static) Works Correctly

- Orchestrator runs all layers successfully
- **99% mapping success** at concept level (14/14 metrics mapped per company)
- Validation feedback loop works: correctly flags mismatches as `INVALID`

### ❌ Issue is in Step 2 (Agent Resolution) - Value Verification Fails

The agent **finds correct concepts** but `verify_mapping()` **rejects them** because XBRL values don't match yfinance:

| Issue | Example | Root Cause |
|-------|---------|------------|
| **TotalAssets** | AAPL: 14.59B (XBRL) vs 359.24B (yf) | Extracting parent-only, not consolidated |
| **IntangibleAssets** | AMZN: 7.44B (XBRL) vs 31.68B (yf) | Extracting one component, not sum |
| **LongTermDebt** | AAPL: 49.30B vs 78.33B | Missing current portion |

### The Bottleneck

```
discover_concepts() ─────▶ ✅ Finds correct concept (e.g., FiniteLivedIntangibleAssetsNet)
check_fallback_quality() ─▶ ✅ Passes quality check
verify_mapping() ─────────▶ ❌ FAILS - variance > 10%
```

The tool correctly finds `FiniteLivedIntangibleAssetsNet`, but:
- yfinance IntangibleAssets = Finite + Indefinite + GoodwillAndOther = 31.68B
- XBRL FiniteLivedIntangibleAssetsNet = 7.44B (only one component)

**Verification fails** because we're comparing apples to oranges.

---

## Options to Fix

### Option A: Fix Value Extraction (in `reference_validator.py`)

The `_extract_xbrl_value()` function currently picks:
- The first non-dimensioned fact
- May be getting parent-only instead of consolidated entity

**Fix:** Prefer facts with no explicit entity dimension (implies consolidated).

### Option B: Fix Metric Definitions (in `metrics.yaml`)

For metrics like IntangibleAssets, the yfinance definition includes multiple XBRL concepts:
```yaml
IntangibleAssets:
  composite: true  # NEW
  components:
    - FiniteLivedIntangibleAssetsNet
    - IndefiniteLivedIntangibleAssetsExcludingGoodwill
```

**Fix:** Add composite summing logic where needed.

### Option C: Adjust Verification Tolerance (in `verify_mapping.py`)

Currently uses 10% variance threshold. Some metrics have inherent definition differences.

**Fix:** Use metric-specific tolerances or accept "directionally correct" matches.

---

## Summary

| Step | Status | What Works | What Doesn't |
|------|--------|------------|--------------|
| Step 1: Static Mapping | ✅ Works | 99% concept mapping, validation flags issues | - |
| Step 2: discover_concepts | ✅ Works | Finds correct semantic candidates | - |
| Step 2: check_fallback_quality | ✅ Works | Rejects bad fallbacks | - |
| Step 2: verify_mapping | ❌ **Fails** | - | Value extraction mismatch |

**Bottom Line:** The architecture is correct. The issue is in **value extraction/comparison**, not concept discovery.
