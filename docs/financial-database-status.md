# Strategic Review: Financial Database & AI Concept Mapping

## What This Branch Is Building

This branch (`feature/ai-concept-mapping`) builds a **standardized financial database** on top of edgartools' existing XBRL parsing. The core problem: every company files XBRL using slightly different concept names for the same financial metric. Apple calls revenue `SalesRevenueNet`, Amazon calls it `Revenues`, insurance companies call it `PremiumsEarnedNet`. This branch creates a system to map all those variants to 24 standardized metrics (Revenue, NetIncome, TotalAssets, etc.) and store them in a queryable SQLite database.

The ambition is to cover the entire S&P 500 with comparable, cross-company financial data extracted directly from SEC filings.

---

## Architecture Overview

### The 3-Layer Extraction Pipeline

The heart of the system is a **multi-layer orchestrator** that maps XBRL concepts to standardized metrics:

```
Layer 1: Tree Parser (~85% coverage)
  → Parse XBRL calculation trees, match known_concepts list
  → Deterministic, fast, highest confidence (0.95)

Layer 2: Facts Search (~10% of remainder)
  → Search EntityFacts when concept isn't in calc linkbases
  → Handles company-specific prefixes (nvda_, tsla_)

Layer 3: AI Semantic Mapper (~5%)
  → LLM (Devstral on OpenRouter) for remaining gaps
  → Uses tree context (parent, siblings, weights) as prompt
```

Each layer validates against yfinance reference data before passing gaps to the next layer. This "validation-in-loop" design means invalid mappings are caught early and retried with more sophisticated methods.

**Key files:**
- `edgar/xbrl/standardization/orchestrator.py` — 3-layer pipeline coordinator
- `edgar/xbrl/standardization/layers/tree_parser.py` — Layer 1
- `edgar/xbrl/standardization/layers/facts_search.py` — Layer 2
- `edgar/xbrl/standardization/layers/ai_semantic.py` — Layer 3

### Configuration System (The Knowledge Base)

- **`config/metrics.yaml`** — 24 standardized metrics with priority-ordered `known_concepts` lists, tree hints, and dimensional handling rules
- **`config/companies.yaml`** — 96 company configs with per-company overrides, known divergences, stock splits, excluded metrics
- **`config/industry_metrics.yaml`** — Industry-specific exclusions based on SIC codes

### Accounting Archetypes

Companies are classified into 5 extraction archetypes:

| Archetype | Model | Coverage | Examples |
|-----------|-------|----------|----------|
| **A** Standard Industrial | Traditional P&L | ~60% | AAPL, CAT, PG, XOM |
| **B** Inverted Financial | Interest = Revenue | ~8% | JPM, WFC, GS (5 sub-types) |
| **C** Intangible Digital | High R&D / SaaS | ~15% | MSFT, CRM, NVDA |
| **D** Asset Passthrough | FFO replaces EPS | ~5% | REITs |
| **E** Probabilistic Liability | Underwriting model | ~5% | Insurance |

Banks (Archetype B) are the most developed, with 5 sub-archetypes (Commercial, Dealer, Custodial, Hybrid, Regional) and a banking golden set (`banking_bgs20.yaml`) with hand-verified ground truth from 10-K PDFs.

### Validation & Regression Protection

1. **yfinance Reference Snapshots** — 96 frozen JSON snapshots used as reference values (not copied, just validated against). Pinned so pass rates only change when extraction code changes.

2. **Golden Master System** — Metrics validated across 3+ periods get promoted to "golden master" status, creating a regression floor.

3. **Experiment Ledger** — SQLite-based tracking of every extraction attempt with full provenance (strategy fingerprint, value, variance, confidence).

4. **Cohort Reactor** — Tests whether a config change for one company regresses others in the same cohort (e.g., all GSIBs, all MAG7).

### The Pipeline Orchestrator (Automated Expansion)

A state machine that automates company onboarding:

```
PENDING → ONBOARDING → ANALYZING → RESOLVING → VALIDATING → PROMOTING → POPULATING → COMPLETE
                            ↑            |
                            └────────────┘  (retry, max 3 times)
```

Each step uses existing tools: `onboard_company()`, `resolve_gaps()`, `validate_multi_period()`, and `FinancialDatabase.populate()`.

---

## Current State (What Exists)

| Asset | Count | Status |
|-------|-------|--------|
| Standardized metrics | 24 | Defined in metrics.yaml |
| yfinance snapshots | 96 | Frozen reference data |
| Company configs | 96 | In companies.yaml |
| Onboarding reports | 40 | JSON reports in config/onboarding_reports/ |
| Company-specific mappings | 5 | BRKA, LLY, MSFT, NFLX, TSLA |
| Extraction layers | 3 | Tree, Facts, AI Semantic |
| Archetypes | 5 + 5 sub | Standard, Bank, SaaS, REIT, Insurance |
| E2E test suites | 3 | Industrial (33 co.), Banking (9 GSIBs), S&P multi-period |

**Latest E2E pass rates** (from evolution reports):
- Standard Industrial (33 companies): **95.6% 10-K / 96.4% 10-Q**
- Banking (9 GSIBs): **100%**
- MAG7 baseline: **~98%**

---

## The Systematic Expansion Strategy

### How It Works Today

The system is designed for **gradual, agent-driven expansion**:

1. **Add ticker** → Pipeline Orchestrator creates PENDING entry
2. **Onboard** → Auto-detect archetype, create yfinance snapshot, run 3-layer extraction
3. **Analyze** → Calculate pass rate vs yfinance reference
4. **Resolve gaps** → AI tools discover and validate new concepts
5. **Validate** → Multi-period validation confirms stability
6. **Promote** → Passing metrics become golden masters (regression floor)
7. **Populate** → Write to SQLite database

This is callable via CLI (`python -m edgar.xbrl.standardization.tools.pipeline_orchestrator`) or through Claude Code skills (`/expand-db`, `/resolve-gaps`).

### What's Systematic About It

- **Configuration-driven**: Adding a new company often requires zero code changes — just YAML config
- **Validation-gated**: No metric enters the database without passing yfinance cross-validation
- **Regression-protected**: Golden masters prevent config changes from breaking existing companies
- **Experiment-tracked**: Every extraction attempt is logged with full provenance
- **Archetype-aware**: The system automatically selects extraction strategy based on industry

### What's NOT Systematic Yet

- **No automated batch expansion**: The pipeline orchestrator exists but hasn't been run at S&P 500 scale
- **No CI/CD integration**: E2E tests are run manually, not in CI
- **No staleness detection**: yfinance snapshots are frozen but there's no schedule to refresh them
- **Limited archetype coverage**: Only Archetype A (Standard) and B (Banking) are mature; C/D/E need work

---

## Key Hurdles & Problems

### 1. The XBRL Concept Diversity Problem (Fundamental)

Every company can use different XBRL concepts for the same financial metric. The `known_concepts` lists in `metrics.yaml` need to grow as more companies are added. Current lists have 4-10 variants per metric, but the full XBRL taxonomy has thousands.

**Current mitigation**: GAAP mappings file (269KB, 11,444 entries) provides a reverse index from concepts to standard tags, used to auto-expand `known_concepts` at config load time.

**Remaining gap**: Composite metrics (FreeCashFlow = OCF - Capex) and industry-specific concepts (insurance premiums, bank repos) need manual curation.

### 2. The Dimensional Data Challenge

XBRL facts can have dimensions (by-segment, by-geography, by-product). When a company only reports Revenue broken into segments without a consolidated total, the system must aggregate. The `dimensional_aggregator.py` handles this, but:

- SaaS companies (CRM, ADBE) still have 3-4 dimensional failures each
- Banks report many metrics only under VIE or business-line dimensions
- Rules for which dimensions to include/exclude are per-concept and per-archetype

### 3. The yfinance Divergence Problem

yfinance is used as reference validation, but it applies its own normalizations:
- **KO OperatingIncome**: yfinance adds back $2.3B in impairments/restructuring charges (XBRL is correct GAAP)
- **Stock splits**: NVDA 10-for-1 split causes 900%+ variance in share counts
- **Debt classification**: TSLA DebtCurrent includes items yfinance classifies differently
- **Insurance/REIT**: yfinance normalization doesn't match GAAP reporting for these industries

**Current mitigation**: `known_divergences` in companies.yaml with `skip_validation: true` and `review_date` for periodic reassessment. 21 documented divergences, 3 marked "won't fix."

### 4. Missing Data for Fresh Clones

Since this repo was worked on locally, several data artifacts may be missing:
- **`experiment_ledger.db`** (4.7MB) — Experiment tracking SQLite. Present in repo but may have stale state.
- **`audit_log.jsonl`** (330KB) — Audit trail. Present.
- **`~/.edgar/financial_data.db`** — The actual FinancialDatabase lives in user home dir, NOT in repo.
- **SEC filing caches** — XBRL data cached locally under `~/.edgar/` storage. Fresh clone has none.
- **E2E result files** in `sandbox/notes/` — Reports and evolution documents are committed.

**Key takeaway**: The configuration (metrics.yaml, companies.yaml, yfinance snapshots) is all in the repo. The runtime data (database, caches) needs to be regenerated. The pipeline orchestrator is designed to handle this — `populate-all` rebuilds the database from scratch.

### 5. Silent Failure Modes (Partially Solved)

Several bugs were discovered and fixed during development:
- **Read-only cache dirs**: `filing.xbrl()` threw `OSError` silently → Fixed with retry logic
- **Stale SGML submissions**: Pre-2009 filings weren't cached properly → Fixed
- **`is_dimensioned` validation bug**: Was checking wrong column → Fixed

The pattern: when `xbrl=None` due to caught errors, the system reported "extraction_error" instead of surfacing the actual problem. Fix: active error detection in onboarding.

### 6. Industry Coverage Gaps

| Industry | Status | Key Challenge |
|----------|--------|--------------|
| Standard Industrial | Mature (~96%) | GE/DE/RTX post-spinoff structures |
| Banking | Mature (100%) | Complex but well-modeled with 5 sub-archetypes |
| SaaS / Digital | Partial | Dimensional revenue, no traditional COGS |
| Energy | Partial (~88%) | Non-standard OperatingIncome (XOM, CVX, COP) |
| Healthcare / Pharma | Partial (~95%) | One-time charges in OperatingIncome (JNJ, PFE) |
| Insurance | Early | UnderwritingIncome not systematized |
| REITs | Early | NOI methodology not defined |
| Utilities | Not started | Regulatory assets/liabilities |
| Retail | Not started | Comparable store metrics |

### 7. Specific Metric Pain Points

From the latest E2E results, the hardest metrics to map universally:

| Metric | Failures | Root Cause |
|--------|----------|------------|
| ShortTermDebt | 14 | Companies classify current debt differently; financial subsidiaries |
| Capex | 8 | Energy companies use non-standard concepts; requires sign inversion |
| OperatingIncome | 6 | Conglomerates and energy companies use non-standard structures |
| DepreciationAmortization | 4 | Some companies split D from A; some only report one |
| AccountsPayable | 4 | Composite vs standalone reporting |
| IntangibleAssets | 3 | Goodwill inclusion/exclusion varies |

---

## Strategic Assessment

### What's Working Well

1. **The 3-layer architecture is sound** — Deterministic first (tree parser), then broader search, then AI. Each layer has clear boundaries and validation.

2. **Configuration-driven expansion** — Adding a company is mostly YAML editing, not code changes. This scales.

3. **yfinance as external validator** — Not copying values, just cross-checking. The snapshot system makes it deterministic.

4. **Banking deep-dive proves the archetype model** — 5 bank sub-archetypes with hand-verified golden masters show the approach works for complex industries.

5. **Experiment tracking is comprehensive** — Full provenance for every extraction attempt enables systematic debugging.

### What Needs Attention

1. **Archetype C/D/E maturity** — SaaS, REIT, and Insurance archetypes need the same depth of treatment that Banking received. This is the biggest blocker to S&P 500 coverage.

2. **Batch automation at scale** — The pipeline orchestrator exists but hasn't been stress-tested at 100+ company scale. Rate limiting, error recovery, and parallel processing need hardening.

3. **CI integration** — E2E tests are manual. Without CI, regressions can creep in undetected between development sessions.

4. **The "long tail" of concepts** — The first 85% of metrics map easily. The last 15% requires per-company investigation. As you expand to 500 companies, this long tail becomes a staffing/automation challenge.

5. **yfinance dependency risk** — yfinance is an unofficial Yahoo Finance API. If Yahoo changes their data format, all snapshots would need regeneration. The snapshots mitigate this (frozen), but new company onboarding needs live yfinance.

---

## Recommended Path Forward

### Phase 1: Stabilize & Validate Current State
- Regenerate the FinancialDatabase from scratch using `populate-all`
- Run all 3 E2E test suites to establish a current baseline
- Verify all 96 yfinance snapshots are current and valid

### Phase 2: Deepen Archetype Coverage
- Invest in Archetype C (SaaS/Digital) — biggest gap relative to S&P 500 representation
- Document Insurance and REIT extraction rules at the same depth as Banking
- Create golden sets for each archetype (currently only Banking has one)

### Phase 3: Scale to S&P 500
- Run pipeline orchestrator in batches of 10-20 companies
- Use concept-mapping-resolver agent to systematically close remaining gaps
- Build CI pipeline that runs E2E tests on every config change

### Phase 4: Production API
- Expose FinancialDatabase through the public edgartools API
- Add time-series queries, cross-company comparisons, sector aggregations
- Consider whether the SQLite backend should be replaceable (PostgreSQL, etc.)
