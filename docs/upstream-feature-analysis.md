# Upstream Feature Analysis Report

**Fork**: `sangicook/edgartools` (branch: `feature/ai-concept-mapping`)
**Upstream**: `dgunning/edgartools` (branch: `main`)
**Report Date**: 2026-03-02
**Analysis Range**: v5.7.4 → v5.19.1

---

## 1. Executive Summary

Our fork diverged from upstream at **v5.7.4** (2026-01-03). Upstream is now at **v5.19.1** (2026-02-28) — a span of ~2 months containing:

- **464 non-merge commits** across **33 releases** (v5.8.0 through v5.19.1)
- **620 files changed** with 677K insertions and 59K deletions
- Major new modules: TTM calculations, 8-K earnings parser, SGML rewrite, 7 new filing types

**Our fork's purpose**: Build a system that constructs and maintains a financial database using standardized XBRL extraction. Our unique contributions include a 3-layer standardization pipeline with AI-powered concept mapping, archetype-based extraction strategies, and yfinance-validated reference data.

### Top-Line Recommendations

| Category | Count | Action |
|----------|-------|--------|
| **MUST PULL** | 11 commits | Critical data accuracy bug fixes — wrong/missing financial data |
| **SHOULD PULL** | ~60 commits | High-value features for financial database (TTM, EntityFacts, earnings parser, performance) |
| **NICE TO HAVE** | ~40 commits | New filing types, compatibility, stitching improvements |
| **SKIP** | ~350 commits | Docs/SEO, MCP redesign, fund filings, skills architecture, notebooks |

---

## 2. CRITICAL: XBRL & Financial Data Accuracy Fixes

These bug fixes directly affect the correctness of extracted financial data. **Pull all of these regardless of other decisions.**

| Commit | Version | Date | Fix | Impact |
|--------|---------|------|-----|--------|
| `d4b7d5b9` | v5.10.1 | 2026-01-17 | Deterministic XBRL parsing (hash randomization) | Non-reproducible results when caching — same filing produces different output across runs |
| `362e358e` | v5.10.0 | 2026-01-15 | 10-K with `fiscal_period='Q4'` returns empty income statement | GE, CHTR, XOM, YUM broken — annual filings silently return no data |
| `429e1463` | v5.10.0 | 2026-01-15 | Expand annual form types for period selection | Companion fix for above — form type filter was too narrow |
| `ba1ea5be` | v5.13.1 | 2026-02-01 | `get_facts_by_fiscal_period()` always returns empty DataFrame | Core query API completely broken — all period-based queries affected |
| `3b9d35d5` | v5.10.2 | 2026-01-17 | Revenue deduplication drops parent items | GOOGL Revenue missing — dedup logic removes the parent revenue concept |
| `665be378` | v5.8.1 | 2026-01-04 | Income statement resolver picks tax disclosure note | MCHP income statement is a tax note instead of actual income statement |
| `7b4d0e7b` | v5.17.1 | 2026-02-23 | MTD balance sheet essential-concept validation | Multiple companies affected — validation skips cascade steps |
| `94fca8a9` | v5.17.0 | 2026-02-23 | STZ ComprehensiveIncome fallback filtering | STZ income statement broken — fallback to comprehensive income role fails |
| `b73e7094` | v5.11.1 | 2026-01-21 | Multiple ComprehensiveIncome roles confuse resolver | Resolver picks wrong role when company has multiple comprehensive income presentations |
| `f33d02ac` | v5.18.0 | 2026-02-25 | Period format normalization ("2023-FY" vs "FY 2023") | Silent query failures — `get_fact("Revenue", "FY 2023")` returns None |
| `6729f565` | v5.15.2 | 2026-02-11 | Standardization empty for all IFRS filers | All 20-F companies produce empty standardized output |
| `6705c12b` | v5.16.0 | 2026-02-13 | Disclosure note dataframes returning NaN | Instant-type notes produce NaN instead of values |

**Cherry-pick strategy**: These are individual, self-contained fixes. Apply in chronological order starting with `665be378` (v5.8.1, earliest).

---

## 3. HIGH VALUE: Features Directly Supporting Financial Database

### 3a. EntityFacts API Improvements

EntityFacts is the primary API for extracting multi-period financial data — the core of our financial database pipeline.

**Key changes** (in `edgar/entity/entity_facts.py`, 15 commits):

| Feature | Commits | Why It Matters |
|---------|---------|----------------|
| `annual=True` default on all getter methods | `25634e42`, `0eb90b5d` | Previously returned most recent period (could be quarterly), now defaults to annual — correct for database construction |
| `get_annual_fact()` method | Part of above | Explicit annual-only accessor |
| `search_concepts()` and `available_periods()` | `20ba29d9` | Discovery methods — find what concepts a company actually reports |
| Helpful warnings on silent None returns | `2837d4e6` | Prevents silent data gaps — warns when `get_fact()` returns None |
| Period format normalization | `f33d02ac` | "2023-FY" and "FY 2023" both work — prevents query failures |
| Strict unit matching fix | `d34cac17` | Explicit unit parameter now works correctly |
| `cash_flow()` → `cashflow_statement()` rename | `f799abf6` | API consistency (breaking change, needs migration) |

**Recommendation**: SHOULD PULL. These directly improve the reliability of our data extraction.

### 3b. TTM Module (`edgar/ttm/`)

Entirely new module (10 commits). Provides trailing twelve months calculations critical for financial analysis.

| Component | File | Purpose |
|-----------|------|---------|
| `TTMCalculator` | `edgar/ttm/calculator.py` | Derives Q4 = FY − (Q1+Q2+Q3), computes rolling TTM trends |
| Stock split detection | `edgar/ttm/splits.py` | Detects splits and adjusts per-share figures (EPS, dividends) |
| `TTMStatementBuilder` | Part of calculator | Builds complete TTM income/cashflow statements |
| Company integration | `edgar/financials.py` | `company.financials.ttm_income_statement()` etc. |

**No conflict risk** — entirely new directory, clean copy.

**Recommendation**: SHOULD PULL. Q4 derivation and TTM calculations are essential for a complete financial database (many companies don't file separate Q4 10-Qs).

### 3c. 8-K Earnings Release Parser (`edgar/earnings.py`)

New module (10+ commits) that parses HTML press release tables from EX-99.1 attachments in 8-K filings.

| Feature | Why It Matters |
|---------|----------------|
| `EarningsRelease` class | Structured access to earnings press release data |
| `to_facts_dataframe()` | Output matching EntityFacts schema — directly ingestible |
| Income statement classification | Weighted keyword scoring to identify financial tables |
| Negative sign handling | Parenthesized values across HTML cells handled correctly |

**Recommendation**: SHOULD PULL. Critical for quarterly data availability — earnings releases appear weeks before 10-Q XBRL filings are available.

### 3d. XBRL Standardization (Upstream Approach)

Upstream took a **completely different standardization path** from ours:

| Aspect | Upstream | Our Fork |
|--------|----------|----------|
| Architecture | Flat hash-based lookup | 3-layer pipeline (YAML → company mappings → AI) |
| Mapping source | `gaap_mappings.json` (2,077 tags) | `metrics.yaml` + company-specific overrides |
| Lookup method | `ReverseIndex` for O(1) lookups | Layer cascade with AI fallback |
| Disambiguation | Section membership context | Industry archetype + extraction rules |
| Coverage tracking | `unmapped_logger.py` | `reference_validator.py` + yfinance comparison |

**Recommendation**: DO NOT merge their standardization over ours. Our approach is more sophisticated and purpose-built for database construction. However, selectively adopt:

1. **`gaap_mappings.json`** (2,077 entries) — use as supplementary lookup table in our Layer 1
2. **Section membership disambiguation** (`sections.py`, `section_membership.json`) — useful heuristic
3. **`standard_concept` metadata pattern** — add as a column to preserve mapping provenance
4. **`unmapped_logger.py`** — continuous improvement tool

### 3e. Stitching Improvements

Stitching combines multi-period data into cohesive statements.

| Feature | Commit | Impact |
|---------|--------|--------|
| `standard_concept` propagation through stitching | `cbf9d293` | Standardized labels survive stitching pipeline |
| Duplicate row merging for same `standard_concept` | `cbf9d293` | Prevents duplicate Revenue rows after standardization |
| `view` parameter (STANDARD/DETAILED/SUMMARY) | Multiple | User-controlled detail level |
| DIS cash flow stitching fix | `cbf9d293` | Aggregate vs continuing-operations switch |

**Recommendation**: SHOULD PULL selectively. The `standard_concept` propagation is directly relevant to our pipeline.

### 3f. Dimensional Data Improvements

| Feature | Impact |
|---------|--------|
| `StatementView` enum (STANDARD/DETAILED/SUMMARY) | Consistent view selection across all statements |
| `is_dimensioned` column on all fact queries | Identify segment breakdowns vs consolidated figures |
| `is_breakdown` field on StatementRow | Flag rows that are dimensional breakdowns |
| `view` parameter on Financials statement methods | User-facing control |

**Recommendation**: NICE TO HAVE. The `is_dimensioned` column helps distinguish consolidated from segment data in our database.

---

## 4. PERFORMANCE: Infrastructure Improvements

### 4a. SGML Parser Rewrite (Highest Impact, No Conflict)

**Commit**: `e1a763b1` + follow-ups (5 commits in `edgar/sgml/`)

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Speed | 52ms | 5.5ms | **10x faster** |
| Memory | ~275x baseline | ~1x baseline | **275x reduction** |

**How**: Lazy content references with zero-copy document extraction. Documents are referenced by byte offsets, not loaded into memory.

**Recommendation**: MUST PULL. No conflicts (new files), massive performance gain for bulk filing processing.

### 4b. XBRL Pipeline Optimization

| Optimization | Impact |
|-------------|--------|
| Lazy `element_context_index` (reverse index for fact lookups) | Avoids building index when not needed |
| Merged presentation-tree loops in `facts.py` | Reduces iteration overhead |
| Pre-resolved currency symbols in rendering closures | 4-11MB memory savings per statement |

**Recommendation**: SHOULD PULL. Meaningful for batch processing hundreds of filings.

### 4c. XML Parser Rewrites

| Parser | Change | Speedup |
|--------|--------|---------|
| N-PORT | BeautifulSoup → lxml | **10x** |
| 13F | BeautifulSoup → lxml | **11.5x** |
| CUSIP ticker resolution | Dict lookup | **7.5x** |
| HTTP keepalive | 5s → 30s | Reduces connection overhead |

**Recommendation**: SHOULD PULL for N-PORT and 13F if we use those filing types. Otherwise NICE TO HAVE.

---

## 5. NEW FILING TYPES

| Filing Type | Module | Relevance to Financial DB | Recommendation |
|-------------|--------|--------------------------|----------------|
| **EX-21 Subsidiaries** | `edgar/company_reports/subsidiaries.py` | HIGH — corporate structure for parent/sub relationships | SHOULD PULL |
| **20-F Improvements** | `edgar/company_reports/twenty_f.py` | HIGH — foreign filer financials (IFRS companies) | SHOULD PULL |
| **FortyF (40-F)** | `edgar/company_reports/forty_f.py` | MEDIUM — Canadian cross-listed filers | NICE TO HAVE |
| **BDC** | `edgar/bdc/` (new package) | LOW — niche business development companies | SKIP |
| **FundShareholderReport** | `edgar/funds/ncsr.py` | LOW — fund reporting | SKIP |
| **FundCensus** | `edgar/funds/ncen.py` | LOW — fund census data | SKIP |
| **MoneyMarketFund** | `edgar/funds/nmfp3.py` | LOW — money market funds | SKIP |
| **TenD (10-D ABS)** | `edgar/abs/ten_d.py` | LOW — asset-backed securities | SKIP |
| **FormC (Crowdfunding)** | `edgar/offerings/formc.py` | LOW — crowdfunding filings | SKIP |

---

## 6. COMPATIBILITY & DEPENDENCIES

Changes to `pyproject.toml` that affect our fork:

| Change | Impact | Urgency |
|--------|--------|---------|
| `pandas >=2.0` (removed upper bound) | Enables pandas 3.0 compatibility | HIGH — pandas 3.0 released |
| `pytz` → stdlib `zoneinfo` | Removes pytz dependency | MEDIUM — modernization |
| `truststore>=0.9.0` added | Corporate VPN/proxy support | LOW — unless behind corporate proxy |
| `pyrate-limiter>=3.0.0` replaces `hishel==0.1.3` | New rate limiting approach | MEDIUM — hishel pinned version is fragile |
| `httpxthrottlecache>=0.3.0` (bumped from 0.1.6) | Updated HTTP caching | LOW |
| `zstandard>=0.20.0` (optional) | Datamule tar decompression | LOW — only needed for datamule integration |

**Recommendation**: Pull pandas 3.0 compat and pyrate-limiter changes in Phase 4 to avoid breaking when pandas 3.0 becomes default.

---

## 7. OTHER CHANGES (Lower Priority)

| Area | Description | Recommendation |
|------|-------------|----------------|
| **MCP Server Redesign** | Intent-based tools, moved to `edgar/ai/mcp/` package | SKIP — conflicts with our custom MCP tools |
| **Storage Package Restructure** | `storage.py` → `edgar/storage/` package + datamule integration | NICE TO HAVE — adopt structure when convenient |
| **Skills Architecture** | YAML-based skill files | SKIP — we have our own skill system |
| **Documentation/SEO** | 50+ notebook/doc commits, keyword optimization | SKIP — marketing focus |
| **LLM-as-Judge Evaluation** | AI evaluation framework | SKIP — we have our own validation |
| **VCR Cassette Tests** | 40 network → fast test conversions | NICE TO HAVE — improves test speed |
| **XBRL Validation** | `edgar/xbrl/validation.py` — balance sheet validation | NICE TO HAVE — useful QA layer |
| **Currency Converter** | `edgar/xbrl/currency.py` — IFRS foreign filers | NICE TO HAVE — needed for international companies |
| **Search Module** | `edgar/search/efts.py` — EDGAR full-text search | LOW — not core to database pipeline |
| **Entity Classification** | `is_individual` improvements | LOW |
| **RenderedStatement Serialization** | pickle, JSON, to_dict/from_dict | NICE TO HAVE — useful for caching |
| **Filing.obj_type, Filing.parse()** | Type introspection and parsing | LOW |
| **Auditor Property** | `CompanyReport.auditor` | LOW |

---

## 8. MERGE CONFLICT ZONES

Areas where upstream and our fork have deep divergence:

| Area | Conflict Level | Our Files | Upstream Files | Strategy |
|------|---------------|-----------|----------------|----------|
| `edgar/xbrl/standardization/` | **SEVERE** | 20+ files (layers/, archetypes/, config/, industry_logic/, reactor/, ledger/, strategies/, tools/) | 14 files (flat structure + gaap_mappings.json) | **Keep ours entirely**. Cherry-pick `gaap_mappings.json` and `sections.py` as supplementary data |
| `edgar/storage/` | MODERATE | `storage.py` (single file) | `storage/` package (3+ files) | Restructure ours to match their package layout when convenient |
| `edgar/ai/mcp/` | MODERATE | Custom MCP tools | Redesigned intent-based server | Keep our custom tools, potentially adopt their server base |
| `edgar/xbrl/rendering.py` | LOW-MODERATE | Minimal changes | Performance optimizations | Cherry-pick perf fixes carefully |
| `edgar/xbrl/statements.py` | LOW-MODERATE | Minimal changes | Bug fixes + features | Cherry-pick bug fixes |
| `edgar/xbrl/facts.py` | LOW | Minimal changes | `is_dimensioned` column + perf | Cherry-pick `is_dimensioned` column |
| `edgar/entity/entity_facts.py` | LOW-MODERATE | Minimal changes | 15 commits of improvements | Cherry-pick carefully — API changes may propagate |

### Our Unique Files (No Upstream Equivalent)

These exist only in our fork and have zero conflict risk:

```
edgar/xbrl/standardization/archetypes/
edgar/xbrl/standardization/config/
edgar/xbrl/standardization/industry_logic/
edgar/xbrl/standardization/layers/
edgar/xbrl/standardization/ledger/
edgar/xbrl/standardization/reactor/
edgar/xbrl/standardization/strategies/
edgar/xbrl/standardization/tools/
edgar/xbrl/standardization/ai_mapper.py
edgar/xbrl/standardization/config_loader.py
edgar/xbrl/standardization/coverage.py
edgar/xbrl/standardization/extraction_rules.py
edgar/xbrl/standardization/internal_validator.py
edgar/xbrl/standardization/models.py
edgar/xbrl/standardization/orchestrator.py
edgar/xbrl/standardization/reference_validator.py
edgar/xbrl/standardization/review_cli.py
edgar/xbrl/standardization/validation_manager.py
```

---

## 9. Recommended Pull Strategy

### Phase 1: Critical Bug Fixes (Cherry-Pick)
**Effort**: Low | **Risk**: Low | **Impact**: HIGH

Cherry-pick all 11 data accuracy fixes from Section 2 in chronological order:

```bash
# Chronological order by version
git cherry-pick 665be378   # v5.8.1  - Income stmt resolver / tax disclosure
git cherry-pick 362e358e   # v5.10.0 - 10-K fiscal_period='Q4' empty
git cherry-pick 429e1463   # v5.10.0 - Expand annual form types
git cherry-pick d4b7d5b9   # v5.10.1 - Deterministic XBRL parsing
git cherry-pick 3b9d35d5   # v5.10.2 - Revenue dedup parent items
git cherry-pick b73e7094   # v5.11.1 - Multiple ComprehensiveIncome roles
git cherry-pick ba1ea5be   # v5.13.1 - get_facts_by_fiscal_period() empty
git cherry-pick 6729f565   # v5.15.2 - Standardization empty for IFRS
git cherry-pick 6705c12b   # v5.16.0 - Disclosure note NaN
git cherry-pick 94fca8a9   # v5.17.0 - STZ ComprehensiveIncome fallback
git cherry-pick 7b4d0e7b   # v5.17.1 - MTD balance sheet validation
git cherry-pick f33d02ac   # v5.18.0 - Period format normalization
```

**Test after each cherry-pick**: `hatch run test-fast` to verify no regressions.

### Phase 2: Performance (Cherry-Pick / Port)
**Effort**: Low-Medium | **Risk**: Low | **Impact**: MEDIUM-HIGH

1. **SGML parser rewrite** — Copy entire `edgar/sgml/` directory from upstream (clean, no conflicts)
2. **XBRL pipeline optimizations** — Cherry-pick rendering/facts performance commits
3. **lxml parser rewrites** — Cherry-pick N-PORT and 13F commits if relevant

### Phase 3: High-Value Features (Selective Merge/Port)
**Effort**: Medium | **Risk**: Medium | **Impact**: HIGH

1. **TTM module** — Copy entire `edgar/ttm/` directory (new, no conflicts)
2. **EntityFacts API improvements** — Careful cherry-pick (15 commits, some API changes)
3. **Earnings release parser** — Copy `edgar/earnings.py` (new file, no conflicts)
4. **Dimensional data** — Cherry-pick `is_dimensioned`, `is_breakdown`, `StatementView`
5. **Stitching improvements** — Cherry-pick `standard_concept` propagation
6. **Supplementary data** — Copy `gaap_mappings.json`, `sections.py`, `section_membership.json`

### Phase 4: Compatibility (Merge When Ready)
**Effort**: Medium | **Risk**: Medium | **Impact**: MEDIUM

1. **pandas 3.0 compatibility** — Review all pandas-related changes
2. **pytz → zoneinfo** — Systematic replacement
3. **pyrate-limiter 4.0+** — Update rate limiting
4. **Storage package restructure** — Reorganize when convenient

### Phase 5: Nice-to-Haves (Defer)
**Effort**: Variable | **Risk**: Low | **Impact**: LOW

- New filing types (BDC, FortyF, Funds) — only if needed
- MCP redesign — only if our tools need updating
- Skills architecture — we have our own
- VCR cassette tests — useful for CI speed
- XBRL validation module — useful QA layer

---

## 10. Key Files Reference

Quick reference of the most important upstream files to examine when cherry-picking:

| File | Content | Phase |
|------|---------|-------|
| `edgar/xbrl/standardization/gaap_mappings.json` | 2,077 GAAP tag → standard concept mappings | 3 |
| `edgar/xbrl/standardization/reverse_index.py` | O(1) concept lookup via reverse index | 3 |
| `edgar/xbrl/standardization/sections.py` | Section membership disambiguation | 3 |
| `edgar/xbrl/standardization/section_membership.json` | Section → concept mapping data | 3 |
| `edgar/ttm/calculator.py` | TTM calculation engine | 3 |
| `edgar/ttm/splits.py` | Stock split detection and adjustment | 3 |
| `edgar/earnings.py` | 8-K earnings release parser | 3 |
| `edgar/sgml/sgml_parser.py` | Rewritten SGML parser (10x speed) | 2 |
| `edgar/xbrl/validation.py` | Balance sheet validation checks | 5 |
| `edgar/xbrl/currency.py` | Currency converter for IFRS filers | 5 |
| `edgar/entity/entity_facts.py` | EntityFacts API improvements (15 commits) | 3 |
| `edgar/financials.py` | Financials class + TTM integration | 3 |
| `edgar/xbrl/period_selector.py` | Period selection fixes | 1 |
| `edgar/xbrl/statement_resolver.py` | Statement resolver bug fixes | 1 |
| `edgar/xbrl/deduplication_strategy.py` | Revenue deduplication fix | 1 |
| `edgar/xbrl/rendering.py` | Performance optimizations | 2 |
| `edgar/xbrl/facts.py` | `is_dimensioned` column, perf | 3 |

---

## Appendix A: Version Timeline

| Version | Date | Commits | Highlights |
|---------|------|---------|------------|
| v5.8.0 | 2026-01-04 | 11 | Income stmt resolver fix, MCHP |
| v5.8.1-v5.8.3 | 2026-01-04+ | patches | Bug fixes |
| v5.9.0 | 2026-01-12 | 28 | SGML rewrite, N-PORT/13F lxml, EntityFacts annual default |
| v5.9.1 | 2026-01-12+ | patch | |
| v5.10.0 | 2026-01-15 | 9 | 10-K Q4 fix, period selection, standardization layer |
| v5.10.1-v5.10.2 | 2026-01-17 | patches | Deterministic parsing, revenue dedup |
| v5.11.0 | 2026-01-20 | 20 | ComprehensiveIncome roles, dimensional data |
| v5.11.1-v5.11.2 | patches | | |
| v5.12.0 | 2026-01-23 | 29 | TTM module, stitching improvements |
| v5.12.1-v5.12.3 | patches | | |
| v5.13.0 | 2026-01-29 | 15 | Earnings parser, `get_facts_by_fiscal_period` fix |
| v5.13.1 | patch | | |
| v5.14.0 | 2026-02-03 | 23 | 8-K classification, BDC module |
| v5.14.1 | patch | | |
| v5.15.0 | 2026-02-08 | 36 | IFRS standardization fix, storage restructure, datamule |
| v5.15.1-v5.15.3 | patches | | |
| v5.16.0 | 2026-02-14 | 54 | Disclosure NaN fix, MCP redesign, FortyF, FormC |
| v5.16.1-v5.16.3 | patches | | |
| v5.17.0 | 2026-02-23 | 21 | MTD balance sheet, STZ fix, EX-21 subsidiaries |
| v5.17.1 | patch | | |
| v5.18.0 | 2026-02-26 | 20 | Period normalization, search module |
| v5.19.0 | 2026-02-28 | 11 | Currency converter, 20-F improvements |
| v5.19.1 | 2026-02-28 | patch | |

## Appendix B: Commit Hash Verification

All commit hashes referenced in this report were verified against `upstream/main` on 2026-03-02:

```
d4b7d5b9 ✓  fix: Ensure deterministic XBRL parsing across Python processes (#601)
362e358e ✓  fix: Income statements empty for 10-K filings with fiscal_period='Q4' (#600)
429e1463 ✓  fix: Expand annual form types for period selection (#600)
ba1ea5be ✓  Fix get_facts_by_fiscal_period() always returning empty DataFrame (Issue #622)
3b9d35d5 ✓  fix: Preserve parent items during revenue deduplication (#604)
665be378 ✓  fix: Income statement resolver selects tax disclosure instead of main statement (Issue #581)
7b4d0e7b ✓  Fix MTD balance sheet: apply essential-concept validation across all cascade steps (#659)
94fca8a9 ✓  Fix STZ income statement resolution when ComprehensiveIncome fallback is filtered
b73e7094 ✓  fix: Resolve correct income statement when multiple ComprehensiveIncome roles exist
f33d02ac ✓  Normalize period formats so either "2023-FY" or "FY 2023" works everywhere
6729f565 ✓  Fix standardization layer returning empty for all IFRS filers (#637)
6705c12b ✓  Fix disclosure note dataframes returning NaN for instant-type notes (#635)
```

All 25 referenced file paths verified to exist in `upstream/main`.

## Appendix C: File Path Verification

All key file paths referenced in this report were verified to exist in `upstream/main`:

```
edgar/xbrl/standardization/gaap_mappings.json     ✓
edgar/xbrl/standardization/reverse_index.py        ✓
edgar/xbrl/standardization/sections.py             ✓
edgar/ttm/calculator.py                            ✓
edgar/ttm/splits.py                                ✓
edgar/earnings.py                                  ✓
edgar/sgml/sgml_parser.py                          ✓
edgar/xbrl/validation.py                           ✓
edgar/xbrl/currency.py                             ✓
edgar/entity/entity_facts.py                       ✓
edgar/financials.py                                ✓
edgar/xbrl/period_selector.py                      ✓
edgar/xbrl/statement_resolver.py                   ✓
edgar/xbrl/deduplication_strategy.py               ✓
edgar/company_reports/subsidiaries.py              ✓
edgar/company_reports/twenty_f.py                  ✓
edgar/company_reports/forty_f.py                   ✓
edgar/bdc/                                         ✓
edgar/funds/ncsr.py                                ✓
edgar/funds/ncen.py                                ✓
edgar/funds/nmfp3.py                               ✓
edgar/abs/ten_d.py                                 ✓
edgar/offerings/formc.py                           ✓
edgar/search/efts.py                               ✓
edgar/storage/                                     ✓
```
