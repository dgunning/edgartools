# EdgarTools Financial Database Architecture Report

> **Version:** 5.7.4 | **Report Date:** 2026-03-02 | **Branch:** `feature/ai-concept-mapping`

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Core XBRL Parsing Pipeline](#2-core-xbrl-parsing-pipeline)
3. [Multi-Layer Standardization Architecture](#3-multi-layer-standardization-architecture)
4. [Configuration System](#4-configuration-system)
5. [Accounting Archetypes](#5-accounting-archetypes)
6. [Concept Mapping Core](#6-concept-mapping-core)
7. [Validation & Quality Assurance](#7-validation--quality-assurance)
8. [Experiment Tracking (ENE Ledger)](#8-experiment-tracking-ene-ledger)
9. [Cohort Reactor](#9-cohort-reactor)
10. [E2E Testing Infrastructure](#10-e2e-testing-infrastructure)
11. [Evolution Reports & Diagnosis System](#11-evolution-reports--diagnosis-system)
12. [Key Files Reference Table](#12-key-files-reference-table)

---

## 1. Executive Summary

### What EdgarTools Is

EdgarTools is a Python library for accessing and analyzing SEC Edgar filings. It provides a simple API (`Company("AAPL")`, `find(form="10-K")`) that hides the complexity of SEC's XBRL (eXtensible Business Reporting Language) behind intuitive Python objects. The library parses raw XBRL XML into structured financial statements, queryable facts, and exportable DataFrames.

### The Financial Database Vision

The financial database initiative extends EdgarTools beyond filing access into **standardized financial metric extraction** from 500+ SEC-reporting companies. The goal: extract 17+ key financial metrics (Revenue, NetIncome, OperatingCashFlow, TotalAssets, etc.) from any company's XBRL filings and validate them against external reference data.

### Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| **Layered Extraction** | 3-layer pipeline (Tree → Facts → AI) exhausts deterministic methods before LLM |
| **Validation-in-Loop** | After each extraction layer, validate against yfinance; invalid mappings retry with next layer |
| **Archetype-Aware** | 5 accounting archetypes (Standard Industrial, Inverted Financial, etc.) drive strategy selection |
| **Configuration-Driven** | YAML files define metrics, company overrides, and industry mappings; Python code implements extraction logic |
| **Experiment Tracking** | SQLite-based ledger records every extraction attempt with full provenance for reproducibility |
| **Cohort Testing** | Strategy changes tested across groups of similar companies to prevent regressions |

---

## 2. Core XBRL Parsing Pipeline

### Entry Points

**Filing → XBRL** (`edgar/_filings.py:1647`):
```python
filing = Company("AAPL").get_filings(form="10-K").latest()
xbrl = filing.xbrl()  # Returns parsed XBRL instance
```

**Company → EntityFacts** (`edgar/entity/core.py:60`):
```python
company = Company("AAPL")
facts = company.get_facts()  # Returns EntityFacts from SEC API
```

### Parser Coordinator Architecture

The XBRL parser (`edgar/xbrl/parsers/coordinator.py`) coordinates 6 specialized component parsers:

```
XBRLParser (Coordinator)
├── SchemaParser     → element_catalog (types, period_types, balance)
├── LabelsParser     → element labels (standard, terse, total roles)
├── PresentationParser → presentation_trees (statement hierarchy)
├── CalculationParser  → calculation_trees (validation weights)
├── DefinitionParser   → tables, axes, domains (dimensional structures)
└── InstanceParser     → facts, contexts, units, entity_info, periods
```

| Parser | Input | Output | Key Responsibility |
|--------|-------|--------|--------------------|
| SchemaParser | `*.xsd` | `ElementCatalog` entries | Element metadata extraction |
| LabelsParser | Label linkbase XML | Labels by role | Human-readable label resolution |
| PresentationParser | Presentation linkbase | `PresentationTree` | Statement structure hierarchy |
| CalculationParser | Calculation linkbase | `CalculationTree` | Validation trees with weights |
| DefinitionParser | Definition linkbase | Tables, Axes, Domains | Dimensional/segment structures |
| InstanceParser | Instance document | Facts, Contexts, Units | Actual financial data values |

### Fact Extraction and Context Handling

**Fact Model** (`edgar/xbrl/models.py:159`):
```
element_id    → "us-gaap_NetIncome"
context_ref   → "FY2024"
value         → "15000000000"
numeric_value → 15000000000.0 (parsed)
unit_ref      → "USD"
```

**Context Types**:
- **Instant**: Point in time (balance sheet dates). `period.instant = "2024-12-31"`
- **Duration**: Time range (income/cash flow). `period.startDate = "2024-01-01"`, `endDate = "2024-12-31"`

**Fact Key Format**: `{element_id}_{context_ref}[_{instance_id}]` — handles duplicate facts via instance_id suffix.

### Statement Resolution

The statement resolver (`edgar/xbrl/statement_resolver.py`) identifies financial statements using a multi-strategy approach:

1. **Concept Matching** — Primary concepts (e.g., `StatementOfFinancialPositionAbstract` for BalanceSheet)
2. **Alternative Concepts** — IFRS equivalents, company variations
3. **Role URI Matching** — Pattern matching against presentation role URIs
4. **Key Concept Validation** — Ensure essential line items exist

Recognized statements: BalanceSheet, IncomeStatement, CashFlowStatement, StatementOfEquity, ComprehensiveIncome.

### Period Selection Logic

Period selection (`edgar/xbrl/periods.py`) uses duration-based classification:

| Duration (days) | Classification | Use Case |
|-----------------|---------------|----------|
| 85-95 | Quarterly | 10-Q statements |
| 175-185 | Semi-Annual | Some foreign filers |
| 265-285 | Nine Months | YTD in 10-Q |
| 350-380 | Annual | 10-K statements |

Each statement type has preferences: BalanceSheet uses **instant** periods, IncomeStatement uses **duration** periods.

### FactsView Query Interface

The `FactsView` class (`edgar/xbrl/facts.py`) provides a fluent query builder:

```python
facts = xbrl.facts
revenue_df = facts.query() \
    .by_concept("Revenue") \
    .by_fiscal_year(2024) \
    .by_statement_type("IncomeStatement") \
    .to_dataframe()
```

Available filters: `by_concept()`, `by_label()`, `by_period_key()`, `by_period_type()`, `by_statement_type()`, `by_fiscal_year()`, `by_fiscal_period()`, `by_dimension()`, `by_value()`, `by_custom()`.

### Rendering and Export

The rendering system (`edgar/xbrl/rendering.py`) produces Rich-formatted terminal tables with:
- Color-coded headers (company name, statement title)
- Indented line items with abstract/total styling
- Year-over-year comparison indicators (▲/▼)
- DataFrame export for analysis

### Data Flow Diagram

```
Filing (SEC EDGAR)
    ↓
XBRL.from_filing()
    ├→ SchemaParser     → element_catalog
    ├→ LabelsParser     → element labels
    ├→ PresentationParser → statement structures
    ├→ CalculationParser  → validation trees
    ├→ DefinitionParser   → dimensional data
    └→ InstanceParser     → facts, contexts, periods
    ↓
XBRL Instance
    ├→ xbrl.facts → FactsView (query interface)
    ├→ xbrl.statements → Statement objects
    └→ Rendering → Rich tables / DataFrames
```

---

## 3. Multi-Layer Standardization Architecture

### Problem

XBRL concepts vary by company: Apple uses `RevenueFromContractWithCustomerExcludingAssessedTax`, Microsoft uses `Revenues`, Tesla uses `AutomotiveRevenue`. The standardization system maps these to a common set of financial metrics.

### 3-Layer Solution

```
Layer 1 (Tree Parser) → Validate → Layer 2 (Facts Search) → Validate → Layer 3 (AI Semantic) → Validate
```

**Design Principle**: Exhaust deterministic methods before AI. Validation after each layer enables invalid mappings to retry with the next layer.

#### Layer 1: Tree Parser (~85% coverage)

**File**: `edgar/xbrl/standardization/layers/tree_parser.py`

Extracts concept mappings from XBRL calculation trees using 4 strategies:

| Strategy | Priority | Method |
|----------|----------|--------|
| 0 | Highest | Company-specific `metric_overrides.preferred_concept` |
| 1 | High | Direct match against `known_concepts` from `metrics.yaml` |
| 2 | Medium | Tree structure hints (parent/weight matching) |
| 3 | Low | Facts-based fallback for concepts not in calc trees |

Confidence: HIGH (0.95+) for direct match, MEDIUM (0.80+) for tree hints.

#### Layer 2: Facts Search (~10% of remaining)

**File**: `edgar/xbrl/standardization/layers/facts_search.py`

Searches XBRL facts directly when concepts aren't in calculation trees. Key insight: calculation trees are just one way XBRL organizes data — facts can exist independently.

Search strategies:
1. Direct match with namespace prefix (`us-gaap:Revenue`)
2. Prefix-stripped match (handles company-specific prefixes like `nvda_`, `tsla_`)
3. Partial substring matching

#### Layer 3: AI Semantic Mapper (~5% of remaining)

**File**: `edgar/xbrl/standardization/layers/ai_semantic.py`

Uses LLM (via OpenRouter, model: `mistralai/devstral-2512:free`) for semantic concept matching:

1. Extracts keywords from metric name and known concepts
2. Scores candidate XBRL concepts by keyword match
3. Sends top 5 candidates to LLM with tree context
4. LLM returns: `{matches: bool, confidence: "high"/"medium"/"low", reasoning: str}`

Falls back to simple heuristics if API unavailable.

### Orchestrator Coordination

**File**: `edgar/xbrl/standardization/orchestrator.py`

The `Orchestrator` class runs all layers in sequence:

```python
orchestrator = Orchestrator()
results = orchestrator.map_company("AAPL", use_ai=True, use_facts=True)
# Returns: Dict[str, MappingResult]
```

**Validation-in-Loop**: After each layer, `_validate_layer()` checks results against yfinance. Invalid mappings are reset (concept=None, confidence=0.0) and re-added to the gaps list for the next layer to retry.

---

## 4. Configuration System

### metrics.yaml — Target Metric Definitions

**File**: `edgar/xbrl/standardization/config/metrics.yaml`

Defines 17+ target metrics with known XBRL concepts, tree hints, and extraction guidance.

**Structure per metric**:
```yaml
Revenue:
  description: "Total revenue from operations"
  known_concepts:
    - Revenues                    # First-match-wins priority
    - RevenueFromContractWithCustomerExcludingAssessedTax
    - SalesRevenueNet
    - PremiumsEarnedNet           # Insurance (Archetype E)
  tree_hints:
    statements: [INCOME, OPERATIONS]
    parent_pattern: OperatingIncome
    weight: 1.0
  universal: true                 # Present in all companies
```

**Key metrics defined**: Revenue, COGS, SGA, OperatingIncome, PretaxIncome, NetIncome, OperatingCashFlow, Capex, TotalAssets, CashAndEquivalents, ShortTermDebt, LongTermDebt, Goodwill, IntangibleAssets (composite), WeightedAverageSharesDiluted, StockBasedCompensation, DividendsPaid, DepreciationAmortization, Inventory, AccountsReceivable, AccountsPayable.

**Derived metrics**: FreeCashFlow = OperatingCashFlow - Capex, TangibleAssets, NetDebt.

### companies.yaml — Per-Company Configuration

**File**: `edgar/xbrl/standardization/config/companies.yaml`

Configures 50+ companies organized by sector:

| Section | Companies | Key Features |
|---------|-----------|-------------|
| MAG7 | AAPL, MSFT, GOOG, AMZN, NVDA, TSLA, META | Baseline reference group |
| Industrial Mfg | CAT, GE, HON, DE, MMM, EMR, RTX, ASTE | Standard Archetype A |
| Consumer Staples | PG, KO, PEP, WMT, COST, HSY | Standard with GAAP subtleties |
| Energy | XOM, CVX, COP, SLB, PBF | Preferred concepts for energy metrics |
| Healthcare/Pharma | JNJ, UNH, LLY, PFE | Industry-specific revenue |
| Transportation | UPS, FDX, BA | Standard industrial |
| Financial Services | JPM, BAC, C, WFC, GS, MS, BK, STT, USB, PNC | Bank sub-archetypes |

**Per-company fields**: `name`, `cik`, `exclude_metrics`, `metric_overrides`, `industry`, `archetype`, `bank_archetype`, `validation_tolerance_pct`, `known_divergences`, `stock_splits`, `fiscal_year_end`.

**Known divergences** track expected mismatches with remediation status:
```yaml
known_divergences:
  Capex:
    variance_pct: 40.0
    reason: "LLY uses OtherPP&E concept"
    remediation_status: "resolved"  # none|investigating|deferred|wont_fix|resolved
```

### industry_metrics.yaml — Industry-Specific Mappings

**File**: `edgar/xbrl/standardization/config/industry_metrics.yaml`

Maps standard metrics to industry counterparts:

| Industry | Standard Metric | Industry Counterpart |
|----------|----------------|---------------------|
| Banking | COGS | InterestExpense |
| Banking | GrossProfit | NetInterestIncome |
| Banking | OperatingIncome | PPNR (Pre-Provision Net Revenue) |
| Banking | SGA | NonInterestExpense |
| Insurance | COGS | LossesAndAdjustments |
| Insurance | OperatingIncome | UnderwritingIncome |
| REITs | COGS | PropertyOperatingExpenses |
| REITs | OperatingIncome | NOI (Net Operating Income) |

### Config Loader

**File**: `edgar/xbrl/standardization/config_loader.py`

`ConfigLoader` loads and merges YAML files into `MappingConfig`, accessed via singleton `get_config()`. Supports auto-detection of industry from SEC SIC codes with fallback to manual config.

---

## 5. Accounting Archetypes

### The 5 Archetypes

**File**: `edgar/xbrl/standardization/archetypes/definitions.py`

| Code | Name | Coverage | Examples | Key Difference |
|------|------|----------|----------|----------------|
| **A** | Standard Industrial | ~60% | AAPL, CAT, PG, XOM | Standard P&L structure |
| **B** | Inverted Financial | ~8% | JPM, GS, WFC | Interest income is revenue; inverted P&L |
| **C** | Intangible Digital | ~15% | MSFT, NVDA, LLY | High intangibles, R&D capitalization |
| **D** | Asset Passthrough | ~5% | REITs | FFO instead of EPS; property-based |
| **E** | Probabilistic Liability | ~5% | Insurance | Underwriting income, loss reserves |

Each archetype defines: SIC code ranges, GICS sectors, extraction strategies per metric, excluded metrics, and validation tolerance.

### Bank Sub-Archetypes (Archetype B)

| Sub-Archetype | Examples | ShortTermDebt Strategy | Key Characteristic |
|---------------|----------|----------------------|-------------------|
| **Commercial** | WFC, USB, PNC | Subtract repos from STB | High loan book, repos bundled |
| **Dealer** | GS, MS | Use UnsecuredShortTermBorrowings | High trading assets, repos separate |
| **Custodial** | BK, STT | Component sum only; never fuzzy match | Minimal STB |
| **Hybrid** | JPM, BAC, C | Check nesting before subtracting | Both commercial and dealer traits |
| **Regional** | (fallback) | Commercial rules | Smaller banks |

### Archetype Classification

**File**: `edgar/xbrl/standardization/archetypes/classifier.py`

Classification priority:
1. Config override (`companies.yaml` archetype field)
2. GICS sector/group
3. SIC code ranges
4. Default to Standard Industrial (A)

Bank sub-archetype detection uses balance sheet ratios:
- `trading_ratio > 0.15` → Dealer
- `stb < 1% of total_assets` → Custodial
- `trading_ratio > 0.05 && loan_ratio > 0.20` → Hybrid
- `loan_ratio > 0.30` → Commercial

---

## 6. Concept Mapping Core

### StandardConcept Enum

**File**: `edgar/xbrl/standardization/core.py:18`

60+ standardized financial concepts organized by statement:

- **Balance Sheet Assets** (9): Cash, Receivables, Inventory, Prepaid, Total Current, PP&E, Goodwill, Intangibles, Total Assets
- **Balance Sheet Liabilities** (7): Payables, Accrued, Short-Term Debt, Total Current, Long-Term Debt, Deferred Revenue, Total Liabilities
- **Balance Sheet Equity** (3): Common Stock, Retained Earnings, Total Equity
- **Revenue Hierarchy** (12): Revenue, Contract, Product, Service, Subscription, Leasing, Automotive, Energy, Software, Hardware, Platform
- **Income Expenses** (10): Cost of Revenue, COGS, Gross Profit, Operating Expenses, R&D, SGA, Operating Income, Interest, Tax, Net Income
- **Cash Flow** (4): Operating, Investing, Financing, Net Change

### MappingStore and ConceptMapper

**MappingStore** (`core.py:128`) provides persistent storage with priority-based resolution:
- Priority 1: Core mappings from `concept_mappings.json`
- Priority 2: Company-specific mappings from `company_mappings/` directory
- Priority 4: Entity-detected company matches (highest)

**ConceptMapper** (`core.py:464`) maps company concepts to standard concepts using:
- Direct store lookup (cached)
- Fuzzy string matching via `SequenceMatcher`
- Statement-type keyword filtering (BS keywords, IS keywords, CF keywords)

### Company-Specific JSON Mappings

**Directory**: `edgar/xbrl/standardization/company_mappings/`

Per-company JSON files (e.g., `tsla_mappings.json`):
```json
{
  "metadata": {"entity_identifier": "tsla", "company_name": "Tesla, Inc."},
  "concept_mappings": {
    "Automotive Revenue": ["tsla_AutomotiveRevenue", "tsla_VehicleRevenue"],
    "Energy Revenue": ["tsla_EnergyRevenue"]
  },
  "hierarchy_rules": {
    "Revenue": {"children": ["Automotive Revenue", "Energy Revenue", "Service Revenue"]}
  }
}
```

### MappingResult Data Model

**File**: `edgar/xbrl/standardization/models.py:54`

```
metric              → "Revenue"                    # Target metric name
company             → "AAPL"                       # Company ticker
fiscal_period       → "2024-FY"                    # Fiscal period
concept             → "RevenueFromContract..."     # Mapped XBRL concept (or None)
value               → 391035000000.0               # Extracted value (or None)
confidence          → 0.95                         # 0.0-1.0
confidence_level    → ConfidenceLevel.HIGH         # HIGH/MEDIUM/LOW/NONE/INVALID
source              → MappingSource.TREE           # TREE/AI/FACTS/CONFIG/INDUSTRY
validation_status   → "valid"                      # pending/valid/invalid
validation_notes    → "Matched yfinance within 2%"
```

**Key properties**:
- `is_mapped` = concept is not None AND confidence >= 0.7
- `is_resolved` = is_mapped AND validation_status == 'valid'

---

## 7. Validation & Quality Assurance

### Reference Validator

**File**: `edgar/xbrl/standardization/reference_validator.py`

Validates XBRL-extracted values against yfinance reference data. This does NOT copy values — it confirms mappings are correct.

**yfinance Mapping** (21 metrics):
```python
YFINANCE_MAP = {
    'Revenue': ('financials', 'Total Revenue'),
    'COGS': ('financials', 'Cost Of Revenue'),
    'OperatingIncome': ('financials', 'Total Operating Income As Reported'),  # GAAP field
    'NetIncome': ('financials', 'Net Income'),
    'OperatingCashFlow': ('cashflow', 'Operating Cash Flow'),
    'TotalAssets': ('balance_sheet', 'Total Assets'),
    # ... 15 more metrics
}
```

**Tolerance**: Default 15%. Company-specific overrides available (banks get 20%).

**"As Reported" Strategy**: Uses GAAP fields when available to match SEC filings exactly, with fallback to calculated fields.

### Quarterly Derivation for 10-Q Filings

10-Q XBRL reports YTD cumulative values, but yfinance provides quarterly values. The validator implements YTD-to-quarterly conversion for 11 flow metrics:

```python
QUARTERLY_DERIVABLE_METRICS = [
    'OperatingCashFlow', 'Capex', 'StockBasedCompensation', 'DividendsPaid',
    'DepreciationAmortization', 'NetIncome', 'Revenue', 'COGS', 'SGA',
    'OperatingIncome', 'PretaxIncome',
]
```

Formula: `Q_n = YTD_current - YTD_previous_quarter`

### Internal Consistency Validator

**File**: `edgar/xbrl/standardization/internal_validator.py`

Validates accounting equations BEFORE external validation:

| Equation | Formula | Tolerance |
|----------|---------|-----------|
| Balance Sheet | Assets = Liabilities + Equity | 5% |
| Gross Profit | GrossProfit = Revenue - COGS | 5% |
| Operating Income | OperatingIncome = GrossProfit - SGA - R&D | 5% |
| Free Cash Flow | FCF = OperatingCashFlow - Capex | 5% |

### Validation Manager — 3-Tier Trust System

**File**: `edgar/xbrl/standardization/validation_manager.py`

| Tier | Status | yfinance Check | Requirement |
|------|--------|---------------|-------------|
| 1 | Trusted | Skip | Verified across 3+ periods |
| 2 | Verifying | Required | New mapping, needs validation |
| 3 | Discrepancy | Skip | Known mismatch, documented & accepted |

Auto-promotion: Tier 2 → Tier 1 after 3 consecutive valid periods.

### Known Divergences Tracking

Configured in `companies.yaml` per-company, with fields:
- `form_types`: Which filing types affected
- `variance_pct`: Expected variance
- `reason`: Root cause explanation
- `remediation_status`: `none` | `investigating` | `deferred` | `wont_fix` | `resolved`
- `review_date`: When to re-evaluate

---

## 8. Experiment Tracking (ENE Ledger)

### Overview

**File**: `edgar/xbrl/standardization/ledger/schema.py`
**Database**: `edgar/xbrl/standardization/company_mappings/experiment_ledger.db` (SQLite)

The ENE Ledger provides persistent, auditable experiment tracking for every extraction attempt.

### Database Schema

#### extraction_runs Table

Records every extraction attempt with full provenance:

| Column | Type | Purpose |
|--------|------|---------|
| `run_id` | TEXT PK | SHA256 hash of `{ticker}_{metric}_{period}_{timestamp}` |
| `ticker` | TEXT | Company ticker |
| `metric` | TEXT | Financial metric |
| `fiscal_period` | TEXT | e.g., "2024-Q4" or "2024-FY" |
| `archetype` | TEXT | A/B/C/D/E |
| `sub_archetype` | TEXT | Bank sub-type (if applicable) |
| `strategy_name` | TEXT | Extraction strategy used |
| `strategy_fingerprint` | TEXT | Strategy version hash (SHA256 of params) |
| `extracted_value` | REAL | Value from XBRL |
| `reference_value` | REAL | Value from yfinance |
| `variance_pct` | REAL | Calculated variance |
| `is_valid` | INTEGER | variance_pct <= 20% |
| `components` | TEXT | JSON: component breakdown |

Indexes: `ticker`, `metric`, `fiscal_period`, `strategy_fingerprint`.

#### golden_masters Table

Verified stable configurations (3+ consecutive valid periods):

| Column | Type | Purpose |
|--------|------|---------|
| `golden_id` | TEXT PK | Unique golden master identifier |
| `ticker` | TEXT | Company ticker |
| `metric` | TEXT | Financial metric |
| `strategy_name` | TEXT | Strategy that achieved this |
| `strategy_fingerprint` | TEXT | Exact strategy version |
| `validated_periods` | TEXT | JSON list of validated periods |
| `validation_count` | INTEGER | Number of periods (>= 3) |
| `avg_variance_pct` | REAL | Average variance |
| `is_active` | INTEGER | Current golden master? |

**Golden Master Criteria**: 3+ consecutive fiscal periods with valid extractions (variance <= 20%).

#### cohort_tests Table

Results of Cohort Reactor tests:

| Column | Type | Purpose |
|--------|------|---------|
| `test_id` | TEXT PK | Unique test identifier |
| `cohort_name` | TEXT | e.g., "GSIB_Banks" |
| `strategy_name` | TEXT | Strategy being tested |
| `results` | TEXT | JSON: `{ticker → IMPROVED/NEUTRAL/REGRESSED}` |
| `is_passing` | INTEGER | No regressions AND variance didn't increase |

### Reproducibility

Every extraction is deterministic via:
1. **Strategy Fingerprinting**: SHA256(sorted params JSON)
2. **Run ID Generation**: SHA256(`{ticker}_{metric}_{period}_{timestamp}`)
3. **Complete Provenance**: Every run captures what, how, when, and why

---

## 9. Cohort Reactor

### Overview

**File**: `edgar/xbrl/standardization/reactor/cohort_reactor.py`

Tests whether a fix for one company works for similar companies, preventing regressions.

### Default Cohorts

| Cohort | Members | Archetype | Metrics |
|--------|---------|-----------|---------|
| GSIB_Banks | JPM, BAC, C, WFC, GS, MS, BK, STT | B | ShortTermDebt, CashAndEquivalents |
| Hybrid_Banks | JPM, BAC, C | B/hybrid | ShortTermDebt |
| Commercial_Banks | WFC, USB, PNC | B/commercial | ShortTermDebt |
| Dealer_Banks | GS, MS | B/dealer | ShortTermDebt |
| Custodial_Banks | BK, STT | B/custodial | ShortTermDebt |

### Impact Classification

| Impact | Condition | Meaning |
|--------|-----------|---------|
| IMPROVED | Variance decreased > 2% | Fix helped this company |
| NEUTRAL | Variance change within ±2% | No significant effect |
| REGRESSED | Variance increased > 2% | Fix hurt this company |

### Test Pass Criteria

A cohort test **passes** if:
- `regressed_count == 0` (no company got worse)
- `variance_delta <= 0` (total variance didn't increase)

### Usage

```python
reactor = CohortReactor()
summary = reactor.test_strategy_change(
    cohort_name='GSIB_Banks',
    strategy_name='hybrid_debt',
    strategy_params={'balance_guard': True},
    metric='ShortTermDebt',
    extractor_fn=my_extractor,
)

if summary.is_passing:
    print("Safe to merge")
else:
    print(f"{summary.regressed_count} regressions detected")
```

All results are recorded to the ENE Ledger for historical analysis.

---

## 10. E2E Testing Infrastructure

### Three Test Suites

| Suite | Companies | Scope | Location |
|-------|-----------|-------|----------|
| **Bank Sector** | 9 GSIBs (JPM, BAC, C, WFC, GS, MS, BK, STT, USB, PNC) | 2yr 10-K + 2qtr 10-Q | `.claude/skills/bank-sector-test/` |
| **Standard Industrial** | 33 companies, 6 sectors | 2yr 10-K + 2qtr 10-Q | `.claude/skills/standard-industrial-test/` |
| **S&P500 Multi-Period** | 25-50 companies | 2yr 10-K + 2qtr 10-Q | `.claude/skills/sp500-multiperiod-test/` |

### Bank Sector E2E

Tests banking-specific extraction logic (ShortTermDebt, CashAndEquivalents) across 5 bank sub-archetypes.

```bash
python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py --metrics ShortTermDebt
```

### Standard Industrial E2E

Tests 33 companies across 6 sectors: MAG7, Industrial Manufacturing, Consumer Staples, Energy, Healthcare/Pharma, Transportation.

```bash
python .claude/skills/standard-industrial-test/scripts/run_industrial_e2e.py --mode standard
```

Mode presets: `quick` (1yr+1qtr), `standard` (2yr+2qtr), `extended` (5yr+4qtr), `full` (10yr+4qtr).

### S&P500 Multi-Period

Large-scale testing with S&P25 (tech + finance + healthcare) and S&P50 (expanded) groups.

```bash
python .claude/skills/sp500-multiperiod-test/scripts/run_e2e.py --group sp25
```

### Report Format

Each test run produces:
- **JSON** (detailed): Full failure records with accession numbers, XBRL values, reference values, concepts used, suggested actions
- **Markdown** (summary): Pass rate tables, top failing metrics, per-company breakdowns

Reports are stored in `sandbox/notes/{suite}/reports/e2e_{suite}_{date}_{time}.{json|md}`.

### Divergence Statistics

Reports include automatic divergence handling:
- Known divergences (from `companies.yaml`) are skipped and tallied separately
- Unknown failures are flagged for investigation
- Pass rates calculated excluding known divergences

### Recent Results (2026-01-26)

**Standard Industrial (33 companies)**:
- 10-K Pass Rate: 93.0% (1,015/1,091)
- 10-Q Pass Rate: 94.3% (1,002/1,063)

**Banking Sector (9 GSIBs)**:
- Golden Masters: JPM, BAC, GS, MS, PNC all at 100% across all periods
- Remaining issues: WFC 10-K, STT 10-K (documented as known divergences)

---

## 11. Evolution Reports & Diagnosis System

### Extraction Evolution Reports

**Location**: `sandbox/notes/{suite}/extraction_evolution_report_*.md`

Comprehensive documents tracking quality progression across test runs. Structured as:

| Section | Content |
|---------|---------|
| **Executive Snapshot** | Pass rate tables, golden master count, strategy fingerprints |
| **Knowledge Increment** | New golden masters, validated archetype behaviors |
| **Graveyard** | Discarded hypotheses with evidence |
| **New XBRL Mappings** | Discovered concept mappings |
| **Cohort Transferability Matrix** | Impact analysis across cohort members |
| **Strategy Performance** | Per-strategy success rates |
| **Truth Alignment** | Structural mismatches vs yfinance |
| **Failure Analysis** | Detailed incident reports with components and history |
| **ADRs** | Architectural Decision Records |

### Diagnosis Response Documents

**Location**: `sandbox/notes/{suite}/diagnosis-response_*.md`

Evidence-based architectural investigations answering specific research questions:

Structure:
1. **Short Answer** — Direct conclusion
2. **Evidence** — Code locations, configuration, test data
3. **Analysis** — Pattern interpretation
4. **Implications** — What this means for architecture
5. **Recommendation** — Suggested next steps

### Divergence Investigation Scripts

**`sandbox/investigate_divergences.py`**: Downloads actual SEC filings and analyzes XBRL data for critical divergences.

**`scripts/review_divergences.py`**: Generates comprehensive report of all known divergences with remediation status tracking.

---

## 12. Key Files Reference Table

### Core XBRL Parsing

| File | Key Classes | Purpose |
|------|-------------|---------|
| `edgar/_filings.py` | `Filing` | Filing access, `xbrl()` entry point |
| `edgar/entity/core.py` | `Company`, `Entity` | Company data, `get_facts()` entry point |
| `edgar/xbrl/xbrl.py` | `XBRL` | Main XBRL parser and data container |
| `edgar/xbrl/parsers/coordinator.py` | `XBRLParser` | Parser coordinator (6 component parsers) |
| `edgar/xbrl/facts.py` | `FactsView`, `FactQuery` | Fluent query interface for facts |
| `edgar/xbrl/statements.py` | `Statement`, `Statements` | Financial statement abstraction |
| `edgar/xbrl/statement_resolver.py` | `StatementResolver` | Statement type identification |
| `edgar/xbrl/periods.py` | — | Period selection logic |
| `edgar/xbrl/rendering.py` | `RenderedStatement` | Rich table formatting, DataFrame export |
| `edgar/xbrl/models.py` | `Fact`, `Context`, `ElementCatalog` | XBRL data models |
| `edgar/entity/entity_facts.py` | `EntityFacts` | SEC Company Facts API integration |

### Standardization System

| File | Key Classes | Purpose |
|------|-------------|---------|
| `edgar/xbrl/standardization/core.py` | `StandardConcept`, `MappingStore`, `ConceptMapper` | 60+ standard concepts, mapping storage |
| `edgar/xbrl/standardization/models.py` | `MappingResult`, `MappingSource`, `ConfidenceLevel` | Data models and enums |
| `edgar/xbrl/standardization/orchestrator.py` | `Orchestrator` | 3-layer pipeline coordination |
| `edgar/xbrl/standardization/layers/tree_parser.py` | `TreeParser` | Layer 1: Calculation tree matching |
| `edgar/xbrl/standardization/layers/facts_search.py` | `FactsSearcher` | Layer 2: Facts-based fallback |
| `edgar/xbrl/standardization/layers/ai_semantic.py` | `AISemanticMapper` | Layer 3: LLM-based semantic mapping |
| `edgar/xbrl/standardization/layers/dimensional_aggregator.py` | `DimensionalAggregator` | Sum dimensional facts |

### Configuration

| File | Purpose |
|------|---------|
| `edgar/xbrl/standardization/config/metrics.yaml` | 17+ target metric definitions |
| `edgar/xbrl/standardization/config/companies.yaml` | 50+ company configs with overrides |
| `edgar/xbrl/standardization/config/industry_metrics.yaml` | Industry-specific concept mappings |
| `edgar/xbrl/standardization/config_loader.py` | Config loading and merging |
| `edgar/xbrl/standardization/company_mappings/*.json` | Per-company concept mappings |

### Archetypes & Strategies

| File | Key Classes | Purpose |
|------|-------------|---------|
| `edgar/xbrl/standardization/archetypes/definitions.py` | `AccountingArchetype`, `BankSubArchetype` | 5 archetypes + bank sub-types |
| `edgar/xbrl/standardization/archetypes/classifier.py` | `classify_company()` | SIC/GICS-based classification |
| `edgar/xbrl/standardization/strategies/base.py` | `BaseStrategy`, `StrategyResult` | Strategy framework |
| `edgar/xbrl/standardization/strategies/debt/` | `*DebtStrategy` | 5 debt extraction strategies |
| `edgar/xbrl/standardization/industry_logic/strategy_adapter.py` | — | Strategy adapter bridge |

### Validation

| File | Key Classes | Purpose |
|------|-------------|---------|
| `edgar/xbrl/standardization/reference_validator.py` | `ReferenceValidator`, `ValidationResult` | yfinance comparison |
| `edgar/xbrl/standardization/internal_validator.py` | `InternalConsistencyValidator` | Accounting equation checks |
| `edgar/xbrl/standardization/validation_manager.py` | — | 3-tier trust system |
| `edgar/xbrl/standardization/extraction_rules.py` | — | Extraction rule loading |

### Experiment Tracking & Testing

| File | Key Classes | Purpose |
|------|-------------|---------|
| `edgar/xbrl/standardization/ledger/schema.py` | `ExperimentLedger`, `ExtractionRun`, `GoldenMaster` | SQLite experiment tracking |
| `edgar/xbrl/standardization/reactor/cohort_reactor.py` | `CohortReactor`, `CohortTestSummary` | Transferability testing |
| `.claude/skills/bank-sector-test/scripts/run_bank_e2e.py` | — | Bank E2E test runner |
| `.claude/skills/standard-industrial-test/scripts/run_industrial_e2e.py` | — | Industrial E2E test runner |
| `.claude/skills/sp500-multiperiod-test/scripts/run_e2e.py` | — | S&P500 E2E test runner |

### Investigation & Analysis

| File | Purpose |
|------|---------|
| `scripts/review_divergences.py` | Divergence review and reporting |
| `sandbox/investigate_divergences.py` | Critical divergence investigation |
| `sandbox/notes/008_bank_sector_expansion/` | Banking evolution reports and diagnosis |
| `sandbox/notes/010_standard_industrial/` | Industrial evolution reports |
| `edgar/xbrl/standardization/config/DIVERGENCE_SCHEMA.md` | Divergence documentation schema |
