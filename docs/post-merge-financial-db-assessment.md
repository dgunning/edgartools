# Post-Merge Financial Database Assessment

> **Branch**: `feature/ai-concept-mapping` | **Upstream Version**: 5.19.1 | **Report Date**: 2026-03-02
> **Merge Scope**: v5.7.4 → v5.19.1 (478 commits, 33 releases)
> **Architecture Reference**: See `docs/edgartools-financial-database-report.md` for full architecture details.

---

## 1. Current Baseline

**Companies**: 43 total (33 Standard Industrial + 10 Banking)
**Metrics**: 24 target metrics (21 direct + 3 derived)
**Archetypes Active**: A (Standard Industrial), B (Inverted Financial / Banking)

### Pass Rates (Latest E2E)

| Sector | 10-K | 10-Q | Date | Status |
|--------|------|------|------|--------|
| Standard Industrial (33) | **95.6%** (518/542) | **96.4%** (516/535) | 2026-01-27 | Active |
| Banking (10) | **100.0%** (4/4 + 5 skipped) | **100.0%** (12/12 + 1 skipped) | 2026-01-25 | Golden Master |

### Component Health

| Component | Module | Status | Notes |
|-----------|--------|--------|-------|
| Tree Parser | `layers/tree_parser.py` | **Active** | Primary extraction layer |
| Facts Search | `layers/facts_search.py` | **Active** | Fallback layer |
| AI Semantic | `layers/ai_semantic.py` | **Active** | LLM-powered last resort |
| Dimensional Aggregator | `layers/dimensional_aggregator.py` | **Active** | Composite metric support |
| ENE Ledger | `ledger/schema.py` | **Inactive** | DB exists, 3 tables, 0 records |
| Cohort Reactor | `reactor/cohort_reactor.py` | **Untested** | Code exists, never run in production |
| Archetype Classifier | `archetypes/classifier.py` | **Active** | A and B only |

---

## 2. Merge Impact — What Changed

### 2a. Bug Fixes Now Active

The merge pulled 12 critical data-accuracy fixes. These were previously causing silent wrong output or empty results.

| Company/Area | Bug | Impact |
|-------------|-----|--------|
| GE, XOM, YUM, CHTR | 10-K with `fiscal_period='Q4'` returned empty income statement | Annual filings silently returned no data |
| GOOGL | Revenue dedup dropped parent items | Revenue concept missing entirely |
| All IFRS filers (20-F) | Standardization returned empty output | Zero data for all foreign filers |
| MCHP | Income statement resolver picked tax disclosure note | Wrong statement selected |
| All companies | Non-deterministic XBRL parsing (hash randomization) | Same filing, different output across runs |
| STZ | ComprehensiveIncome fallback filtering broken | Income statement unusable |
| Multiple | Multiple ComprehensiveIncome roles confused resolver | Wrong income statement role selected |
| All companies | `get_facts_by_fiscal_period()` always returned empty | Core query API completely broken |
| All companies | Period format mismatch ("2023-FY" vs "FY 2023") | Silent query failures, None returns |
| MTD companies | Balance sheet essential-concept validation broken | Validation skipped cascade steps |
| Disclosure notes | Instant-type notes returned NaN | NaN instead of values in note tables |

### 2b. New Capabilities Available

| Capability | Module | Our Use Case | Integration Status |
|-----------|--------|--------------|-------------------|
| TTM Calculator | `edgar/ttm/calculator.py` | Q4 derivation (FY − Q1−Q2−Q3), rolling 12-month trends | **Available** |
| Stock Split Detection | `edgar/ttm/splits.py` | Automatic per-share figure adjustment | **Available** |
| 8-K Earnings Parser | `edgar/earnings.py` | Quarterly data before 10-Q XBRL is filed | **Available** |
| `search_concepts()` | `edgar/entity/entity_facts.py:1140` | Discover what concepts a company actually reports | **Integrated** |
| `available_periods()` | `edgar/entity/entity_facts.py` | Find what periods have data before querying | **Integrated** |
| `annual=True` default | `edgar/entity/entity_facts.py` | Correct default for database construction | **Integrated** |
| Period format normalization | `edgar/entity/entity_facts.py` | "2023-FY" and "FY 2023" both work | **Integrated** |
| Silent-None warnings | `edgar/entity/entity_facts.py` | Warns when `get_fact()` returns None | **Integrated** |
| XBRL Validation | `edgar/xbrl/validation.py` | Balance sheet equation checks | **Available** |
| Currency Converter | `edgar/xbrl/currency.py` | IFRS foreign filer normalization | **Available** |
| SGML Parser (10x faster) | `edgar/sgml/sgml_parser.py` | Bulk filing processing (52ms → 5.5ms) | **Integrated** |
| EX-21 Subsidiaries | `edgar/company_reports/subsidiaries.py` | Corporate structure for parent/sub relationships | **Available** |
| Financial Scores | `edgar/financials.py` | Integrated scoring + TTM statements | **Available** |
| `is_dimensioned` column | `edgar/xbrl/facts.py` | Distinguish consolidated vs segment data | **Integrated** |
| `StatementView` enum | `edgar/xbrl/` | STANDARD/DETAILED/SUMMARY view control | **Integrated** |
| Lazy element_context_index | `edgar/xbrl/` | Avoids building reverse index when not needed | **Integrated** |

**Integration Status Legend**:
- **Integrated**: Merged and active in our codebase — works out of the box
- **Available**: Code exists post-merge but not yet wired into our standardization pipeline
- **Pending**: Requires adaptation or configuration before use

### 2c. Supplementary Data

Two upstream data files were imported to `edgar/xbrl/standardization/config/`:

| File | Entries | Purpose | Status |
|------|---------|---------|--------|
| `upstream_gaap_mappings.json` | 11,444 lines | GAAP tag → standard concept hash lookup | **Not wired** into pipeline |
| `upstream_section_membership.json` | 96 concepts | Section → concept disambiguation | **Not wired** into pipeline |

These are supplementary reference data. Our Layer 1 (tree parser) and `metrics.yaml` remain the primary mapping source. The gaap_mappings represent pure upside as a fallback lookup.

---

## 3. Open Work Items

### 3a. Active Failures (43 total across industrial sector)

Grouped by root cause, not by company. **Delete rows when fixed.**

#### Metric: ShortTermDebt (14 failures — highest count)

| Company | Form | Variance | Root Cause | Next Action |
|---------|------|----------|------------|-------------|
| GE | 10-K, 10-Q | ~50% | Post-Vernova spin-off restructured balance sheet | Use `search_concepts()` to find GE Aerospace debt concepts |
| RTX | 10-K, 10-Q | varies | Complex defense/aerospace balance sheet | Investigate tree parser concept selection |
| DE | 10-K, 10-Q | varies | John Deere Financial subsidiary not separated | Same root cause as CAT — financial subsidiary |
| HSY | 10-K, 10-Q | varies | Multi-metric structural complexity | Full concept discovery needed |
| KO | 10-K | varies | Bottling subsidiary debt structure | Investigate dimensional data |
| PEP | 10-K | varies | Similar to KO — bottler structure | Investigate dimensional data |
| COST | 10-K | varies | Non-standard debt classification | Investigate tree parser selection |
| COP | 10-K | varies | E&P industry-specific balance sheet | Part of energy archetype gap |

#### Metric: Capex (8 failures)

| Company | Form | Variance | Root Cause | Next Action |
|---------|------|----------|------------|-------------|
| GE | 10-K, 10-Q | varies | Spin-off restructured cash flow | Use `search_concepts()` |
| RTX | 10-K, 10-Q | varies | Defense contractor capex classification | Investigate alternative concepts |
| DE | 10-K, 10-Q | varies | Financial subsidiary investing activities | Financial subsidiary root cause |
| HSY | 10-K, 10-Q | varies | Multiple investing line items | Full concept discovery |

#### Other Failing Metrics

| Company | Metric | Form | Root Cause | Next Action |
|---------|--------|------|------------|-------------|
| GE | COGS | 10-Q | Vernova spin-off (10-K skipped as known divergence) | Structural — monitor |
| HSY | AccountsPayable | 10-K, 10-Q | Structural complexity | Concept discovery |
| HSY | DepreciationAmortization | 10-K | Structural complexity | Concept discovery |
| RTX | DepreciationAmortization | 10-K | Defense sector D&A structure | Investigate preferred_concept |
| NVDA | WeightedAverageSharesDiluted | 10-K, 10-Q | 10:1 stock split (June 2024) | TTM split detection now available |
| KO | IntangibleAssets | 10-Q | Uses IndefiniteLivedTrademarks | Verify composite metric logic |
| PEP | AccountsPayable | 10-Q | AccruedLiabilities bundling | Investigate concept selection |
| COP | DepreciationAmortization | 10-K, 10-Q | E&P-specific DD&A concepts | Part of energy archetype gap |
| COST | DepreciationAmortization | 10-K | Warehouse depreciation structure | Investigate preferred_concept |

### 3b. Infrastructure Gaps

| Gap | Impact | Effort | Priority |
|-----|--------|--------|----------|
| **ENE Ledger: 0 records** | No experiment tracking, no regression detection, no provenance trail | 1 day | **Highest leverage** |
| **Cohort Reactor: never run** | Cannot test strategy changes across company groups; regression risk on every fix | 1 day | High |
| **Archetypes C/D/E: defined but untested** | C = Intangible Digital (MSFT/GOOG/META), D = Platform (AMZN), E = Insurance — no companies configured for C/D/E | 2-3 days | Medium |
| **gaap_mappings.json: not wired** | 11,444 entries sitting unused as fallback lookup in Layer 1 | 1 day | Medium |
| **upstream_section_membership.json: not wired** | 96 concept disambiguation entries not used | Half-day | Low |

### 3c. Known Divergences (Accepted — Skip Validation)

These are structural mismatches where our extraction is correct but yfinance uses a different methodology. **Review dates set for Q2 2026.**

| Company | Metric | Form | Root Cause | Review Date |
|---------|--------|------|------------|-------------|
| WFC | ShortTermDebt | 10-K | Bottom-up (with CPLTD) vs yfinance (without CPLTD) | 2026-04-26 |
| STT | ShortTermDebt | 10-K, 10-Q | Custodial bank — no clean ShortTermBorrowings concept; tree fallback contaminated | 2026-04-26 |
| USB | ShortTermDebt | 10-K | yfinance annual data quality issue (their annual ≠ their quarterly) | 2026-04-26 |
| CAT | ShortTermDebt, LongTermDebt, AR | 10-K, 10-Q | Cat Financial subsidiary not separated from industrial segment | 2026-04-26 |
| DE | OperatingIncome | 10-K | John Deere Financial segment complicates aggregation | 2026-04-26 |
| XOM, CVX, COP, SLB | OperatingIncome | 10-K, 10-Q | Energy sector non-standard cost structure; needs dedicated archetype | 2026-04-26 |
| GE | Revenue, COGS | 10-K (FY2023) | Vernova spin-off: 2024 10-K restates FY2023 as Aerospace-only | Won't fix |
| NVDA | WeightedAverageSharesDiluted | 10-K, 10-Q | 10:1 stock split; XBRL pre-split vs yfinance post-split adjusted | Won't fix |
| FDX | COGS | 10-K, 10-Q | Expense-by-nature format — structurally no COGS concept | Won't fix |
| BA | OperatingIncome | 10-K, 10-Q | Non-recurring 737 MAX / 787 program charges | 2026-04-26 |
| JNJ | OperatingIncome | 10-K | Multi-segment + post-Kenvue spin-off complexity | 2026-04-26 |
| PFE | OperatingIncome | 10-K | COVID-related charges + R&D capitalization | 2026-04-26 |
| EMR | OperatingIncome | 10-K | Negative value bug — investigating | 2026-02-26 |

---

## 4. Prioritized Next Steps

### Step 1: Wire ENE Ledger + Run Cohort Reactor

**Goal**: Establish a regression floor before making any more extraction changes.

**Why Now**: The ledger DB has 3 tables and 0 records. Every fix we've made since January has no recorded provenance. The Cohort Reactor code exists but has never been exercised. Without these, every fix risks breaking something we can't detect.

**First Action**:
1. Run a full E2E test and pipe results into the ENE Ledger (`extraction_runs` table)
2. Snapshot current pass rates as `golden_masters` for all 43 companies
3. Execute Cohort Reactor on `Industrial_33` and `GSIB_Banks` cohorts
4. Verify the reactor can detect when a strategy change regresses a company

**Success Criteria**: Ledger has ≥1 extraction run recorded per company. Cohort Reactor produces a pass/fail report matching current E2E numbers.

### Step 2: Use `search_concepts()` on Every Open Failure

**Goal**: Diagnose all active failures using the new EntityFacts discovery API.

**Why Now**: The merge gave us `search_concepts()` — a tool that shows exactly what XBRL concepts a company actually files. This is the fastest path to understanding why GE/HSY/RTX/DE/COP are failing: we can see their real concept names instead of guessing.

**First Action**:
```python
from edgar import Company
for ticker in ['GE', 'HSY', 'RTX', 'DE', 'COP', 'KO', 'PEP', 'COST']:
    facts = Company(ticker).get_facts()
    for metric in ['ShortTermDebt', 'Capex', 'DepreciationAmortization']:
        results = facts.search_concepts(metric)
        print(f"{ticker}/{metric}: {results}")
```

**Success Criteria**: Root cause identified for ≥80% of the 43 active failures. Each root cause has a documented next action (preferred_concept override, archetype change, or won't-fix decision).

### Step 3: Expand to Archetype C Test Group

**Goal**: Validate extraction for Intangible Digital companies (tech/SaaS).

**Why Now**: MSFT, GOOG, META, NVDA are already in `companies.yaml` and passing as Archetype A. Reclassifying them as Archetype C tests whether the archetype system adds value for tech companies. AAPL and TSLA serve as controls (they should stay Archetype A — hardware/manufacturing).

**First Action**:
1. Define Archetype C extraction rules in `archetypes/definitions.py`
2. Add `archetype: "C"` to MSFT, GOOG, META configs
3. Run E2E on `Software_SaaS` cohort with Archetype C active
4. Compare pass rates vs current Archetype A baseline

**Success Criteria**: Archetype C pass rate ≥ Archetype A for the same companies. No regressions on other companies.

### Step 4: Integrate gaap_mappings.json into Layer 1

**Goal**: Add 11,444 GAAP tag mappings as a fallback lookup in the tree parser.

**Why Now**: The data is already in `config/upstream_gaap_mappings.json`. It's a pure read-only lookup — zero risk if wired as a last-resort fallback after our existing `known_concepts` matching. Any concept that our `metrics.yaml` doesn't cover but gaap_mappings does is free coverage improvement.

**First Action**:
1. Load `upstream_gaap_mappings.json` in `config_loader.py`
2. Add a fallback step in `tree_parser.py` Strategy chain: after known_concepts fail, check gaap_mappings
3. Run E2E to measure coverage delta
4. Wire `upstream_section_membership.json` as a disambiguation signal

**Success Criteria**: ≥5 previously-failing metrics now pass. Zero regressions on existing passes.

---

## 5. Risks and Technical Debt

| Risk | Severity | Mitigation |
|------|----------|------------|
| **yfinance as sole reference source** | High | yfinance data quality issues (USB annual) and methodology differences (WFC debt) create false failures. Add second reference source (SEC EDGAR XBRL viewer, Bloomberg terminal spot checks). |
| **gaap_mappings provenance gap** | Medium | `upstream_gaap_mappings.json` (11,444 lines) and our `metrics.yaml` (24 metrics × ~5 concepts each ≈ 120 entries) overlap but aren't reconciled. Need to verify gaap_mappings concepts against our known_concepts before wiring as fallback. |
| **ENE Ledger never exercised** | High | Every extraction change since January has no recorded provenance. Regressions are invisible. **This is the highest-leverage fix.** |
| **Archetypes C/D/E untested** | Medium | MAG7 companies pass as Archetype A today, but the archetype system was designed to handle them differently. Untested archetypes are dead code until validated. |
| **Upstream drift** | Medium | 478 commits merged in ~2 months. Schedule quarterly merges (next: ~2026-06-01) to prevent divergence from becoming unmanageable. |
| **Stock split handling** | Low | Only NVDA affected currently. TTM split detection module is now available but not wired into reference_validator. Wire when expanding share metrics. |

---

## 6. Key Files Quick Reference

Only files relevant to open work items — see `docs/edgartools-financial-database-report.md` for full architecture map.

### Configuration

| File | Purpose |
|------|---------|
| `edgar/xbrl/standardization/config/companies.yaml` | Company configs, known divergences, metric overrides (43 companies) |
| `edgar/xbrl/standardization/config/metrics.yaml` | 24 metric definitions with known_concepts |
| `edgar/xbrl/standardization/config/upstream_gaap_mappings.json` | 11,444 upstream GAAP tag mappings (not wired) |
| `edgar/xbrl/standardization/config/upstream_section_membership.json` | 96 concept section memberships (not wired) |

### Extraction Pipeline

| File | Purpose |
|------|---------|
| `edgar/xbrl/standardization/layers/tree_parser.py` | Primary extraction — calc tree traversal |
| `edgar/xbrl/standardization/layers/facts_search.py` | Fallback — direct fact lookup |
| `edgar/xbrl/standardization/layers/ai_semantic.py` | Last resort — LLM-powered concept matching |
| `edgar/xbrl/standardization/reference_validator.py` | yfinance comparison and quarterly derivation |

### Infrastructure (Needs Activation)

| File | Purpose |
|------|---------|
| `edgar/xbrl/standardization/ledger/schema.py` | ENE Ledger schema (3 tables, 0 records) |
| `edgar/xbrl/standardization/reactor/cohort_reactor.py` | Cohort-level regression testing |
| `edgar/xbrl/standardization/archetypes/definitions.py` | Archetype A-E definitions (C/D/E untested) |

### New Upstream Capabilities (Available)

| File | Purpose |
|------|---------|
| `edgar/ttm/calculator.py` | TTM calculation, Q4 derivation |
| `edgar/ttm/splits.py` | Stock split detection and adjustment |
| `edgar/earnings.py` | 8-K earnings release parser |
| `edgar/entity/entity_facts.py` | `search_concepts()`, `available_periods()` |
| `edgar/xbrl/validation.py` | Balance sheet equation validation |
| `edgar/xbrl/currency.py` | Currency conversion for IFRS filers |

### E2E Test Reports

| File | Purpose |
|------|---------|
| `sandbox/notes/010_standard_industrial/reports/e2e_industrial_2026-01-27_1610.md` | Latest industrial E2E (95.6%/96.4%) |
| `sandbox/notes/008_bank_sector_expansion/reports/e2e_banks_2026-01-25_0922.md` | Latest banking E2E (100%/100%) |
