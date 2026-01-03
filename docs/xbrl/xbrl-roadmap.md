# XBRL Roadmap

High-level plan for XBRL parsing, financial statement rendering, and related infrastructure.

## Executive Summary

The XBRL subsystem is the foundation for accurate financial statement extraction. The current critical path focuses on **dimension handling** - many filers report face values exclusively through dimensional XBRL, and without proper definition linkbase parsing, financial statements are incomplete or out-of-balance.

## Themes

### 1. Dimension Handling (Critical Priority)

**Problem**: Companies like Boeing, Carrier, General Dynamics, and others report face values ONLY through dimensional XBRL with no non-dimensional default. The current hardcoded dimension lists in `dimensions.py` fail for these cases.

**Root Cause**: The definition linkbase parser parses dimensional arcs but tables aren't being created due to a processing order bug.

**Epic**: `edgartools-445y` - Implement definition linkbase parsing for accurate dimension validation

| Phase | Issue | Title | Priority | Status |
|-------|-------|-------|----------|--------|
| 1 | edgartools-rqxi | Fix definition linkbase table creation bug | P1 | ✅ closed |
| 2 | edgartools-cf9o | Connect definition linkbase to dimension filtering | P1 | ✅ closed |
| 3 | edgartools-u649 | Enhanced heuristics for incomplete definition linkbase | P2 | ✅ closed |
| 4 | edgartools-68lp | Validate across GH-577 test cases | P1 | ✅ closed |

**Epic Status: ✅ COMPLETE** - All GH-577 test cases pass (68 tests)

**Related Issues**:
- GH-577: Dimensions redux (documents the problem extensively)
- GH-574 / edgartools-cuvy: Add structured dimension fields (axis, member, label)
- edgartools-03zg: UX - Hide abstract rows with NaN when children are dimensional

**Test Cases** (from GH-577):
- Income Statement: BA, CARR, GD, HII, INTU, NOC, RTX, SLB, WDAY
- Balance Sheet (Goodwill): BSX, IBM, JKHY
- Balance Sheet (PPE): BSX, CSX, HLT

### 2. XBRL Standardization Pipeline

Multi-phase effort to improve concept mapping, validation, and tag handling.

| Phase | Issue | Title | Priority | Description |
|-------|-------|-------|----------|-------------|
| 1 | edgartools-y3k | Balance Sheet Validation | P2 | Validate balance sheet totals match |
| 2 | edgartools-70b | Section Membership Dictionary | P2 | Standard concept-to-section mapping |
| 3 | edgartools-ys2 | Enhanced Context Threading | P3 | Better period/entity context handling |
| 4 | edgartools-3yx | Context-Aware Disambiguation | P3 | Resolve ambiguous tag mappings |
| 5 | edgartools-qcd | Unmapped Tag Logging | P3 | Track and report unmapped tags |

### 3. Statement Rendering & Display

Improvements to how financial statements are presented and exported.

| Issue | Title | Priority | Notes |
|-------|-------|----------|-------|
| edgartools-096c | Statement of Equity NaN values | P3 | GH-572 |
| edgartools-uqg7 | Matrix rendering for Statement of Equity | P3 | Target: v5.8.0 |
| edgartools-17ow | Ticker namespace bug in balance sheet | P2 | GH-570 |
| edgartools-4ep | Improve XBRL.__rich__() display | P2 | Better visual layout |
| edgartools-a8d | Extract TableTextBlock as DataFrames | P2 | Parse embedded tables |
| edgartools-5dn | Automatic Q4 derivation | P2 | Calculate Q4 from 10-K minus Q1-Q3 |
| edgartools-b5j | Clarify XBRL property names | P2 | API naming improvements |
| edgartools-krmq | Improve variable naming in fact selection | P3 | Code quality |

### 4. iXBRL Support (Future)

Modern SEC filings use inline XBRL. This track adds support for parsing and rendering iXBRL.

| Issue | Title | Priority | Description |
|-------|-------|----------|-------------|
| edgartools-pxi | Unified XBRL API | P3 | Single entry point for both formats |
| edgartools-9ge | iXBRL Bridge | P3 | Connect XBRLFact to parser infrastructure |
| edgartools-tez | Parse inline linkbases | P4 | Extract presentation/calculation from iXBRL |
| edgartools-bu8 | Statement assembly from iXBRL | P4 | Build statements from extracted facts |

### 5. EntityFacts + XBRL Integration

Bridge between the company-level facts API and filing-level XBRL.

| Issue | Title | Priority | Description |
|-------|-------|----------|-------------|
| edgartools-a0c | Multi-Tag Query API | P1 | Query multiple concepts at once |
| edgartools-ctb | Hybrid EntityFacts+XBRL Presentation | P2 | Combine both data sources |
| edgartools-bly | Time-series financial modeling | P2 | Support longitudinal analysis |
| edgartools-ijy | EntityFacts Extensibility | P2 | User-defined concept mappings |

## Dependency Graph

```
GH-577 (Problem Documentation)
    │
    ▼
edgartools-445y (Epic: Definition Linkbase Parsing) ✅ COMPLETE
    │
    ├──► edgartools-rqxi (Phase 1: Fix Table Creation) ✅ DONE
    │         │
    │         ▼
    ├──► edgartools-cf9o (Phase 2: Connect to Filtering) ✅ DONE
    │         │
    │         ▼
    ├──► edgartools-u649 (Phase 3: Fallback Heuristics) ✅ DONE
    │         │
    │         ▼
    └──► edgartools-68lp (Phase 4: Validation) ✅ DONE
              │
              ▼
      Accurate Financial Statements ✅ ACHIEVED
              │
    ┌─────────┴─────────┐
    ▼                   ▼
edgartools-cuvy     edgartools-03zg
(Dimension Fields)  (UX: Hide NaN rows)
              │
              ▼
      Statement Rendering (Theme 3)
              │
              ▼
      iXBRL Support (Theme 4)
```

## Key Files

| Area | Files |
|------|-------|
| Definition Linkbase | `edgar/xbrl/parsers/definition.py` |
| Dimension Filtering | `edgar/xbrl/dimensions.py` |
| XBRL Models | `edgar/xbrl/models.py` |
| Statement Rendering | `edgar/xbrl/statements.py`, `edgar/xbrl/rendering.py` |
| XBRL Parser | `edgar/xbrl/xbrl.py` |
| Fact Handling | `edgar/xbrl/facts.py` |

## Success Criteria

### Phase 1 Complete (edgartools-rqxi) ✅
- Boeing 10-K shows `StatementTable` with `ProductOrServiceAxis` for income statement role
- `xbrl.tables` dict populated for all statement roles
- Definition linkbase tables created correctly

### Phase 2 Complete (edgartools-cf9o) ✅
- `is_breakdown_dimension()` uses definition linkbase when available
- Boeing `ProductOrServiceAxis` correctly classified as FACE (not breakdown)
- Tiered approach: Definition linkbase → Heuristic fallback

### Phase 3 Complete (edgartools-u649) ✅
- FACE_AXES expanded to 11 axes (ProductOrServiceAxis, DebtInstrumentAxis, etc.)
- BREAKDOWN_AXES expanded to 39 axes (MajorCustomersAxis, RestatementAxis, etc.)
- `classify_dimension_with_confidence()` returns classification, confidence level, and reason
- 20 new regression tests covering axis lists, confidence scoring, and GH-577 cases

### Phase 4 Complete (edgartools-68lp) ✅
- All 14 GH-577 test companies validated (BA, CARR, GD, HII, INTU, NOC, RTX, SLB, WDAY, BSX, IBM, JKHY, CSX, HLT)
- Income statement COGS preserved for all dimensional-only filers
- Balance sheet Goodwill and PPE preserved
- Breakdowns (geographic, business segment) still correctly filtered
- 20 validation tests, all passing

### Dimension Epic Complete (edgartools-445y) ✅
- All GH-577 test cases show complete, balanced financial statements
- `CostOfGoodsAndServicesSold` shows correct values for dimensional-only filers
- No regression in non-dimensional filings

### Full XBRL Roadmap
- Consistent, accurate financial statements across all filer types
- Structured dimension metadata available via API
- iXBRL and traditional XBRL unified under single API
- EntityFacts and filing-level XBRL integrated for longitudinal analysis

## Related Documentation

- Research: `docs-internal/research/sec-filings/data-structures/xbrl-dimension-face-value-detection.md`
- Architecture: `docs/internal/knowledge/architecture/xbrl-standardization-pipeline.md`
- Patterns: `docs/internal/knowledge/patterns/xbrl-parsing-patterns.md`
