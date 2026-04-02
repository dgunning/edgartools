# ADR-002: EdgarTools Data Trust Analysis and SEC API Path Strategy

**Status:** Open for Discussion
**Date:** 2026-04-02
**Context:** Subscription-grade financial database — ensuring data integrity from SEC to our standardization layer

## Problem

Our standardization layer sits on top of EdgarTools, which sits on top of SEC EDGAR. Before we can claim "subscription-grade" accuracy, we need to answer two questions:

1. **Is EdgarTools a transparent passthrough?** Or does it apply transformations that could produce wrong financial numbers?
2. **Are we using the right SEC data path?** The SEC offers two ways to get financial data — are we using the best one for our needs?

## Finding 1: EdgarTools Applies 26 Transformations

EdgarTools is **not** a transparent passthrough. Between downloading a filing from SEC and surfacing facts to consumers, it applies 26 identifiable transformations across 6 pipeline stages.

### Transformation Summary

| Stage | Transforms | Nature |
|-------|-----------|--------|
| 1. Raw Parsing (`instance.py`) | T1–T4 | Float coercion, duplicate renaming, fiscal classification, date derivation |
| 2. Facts Enrichment (`facts.py`) | T5–T9 | Label override, sign metadata, statement type, `.scale()`, `.aggregate()` |
| 3. Statement Construction (`xbrl.py`) | T10–T14 | Multi-context selection, revenue dedup, sign negation, reordering |
| 4. Period Selection (`period_selector.py`) | T15–T17 | Date filtering, sparse period removal, annual/quarterly classification |
| 5. Rendering (`rendering.py`, `core.py`) | T18–T24 | Structural filtering, dimension filtering, display scaling, label standardization |
| 6. Current Period (`current_period.py`) | T25–T26 | XBRL/SGML date reconciliation, instant vs duration routing |

### The 4 Danger Zones (High Risk for Wrong Numbers)

**T10 — Multi-Context Fact Selection** (`xbrl.py:1183`)
When multiple XBRL contexts map to the same period for the same concept, EdgarTools picks the fact with fewest dimensions and highest precision. All others are silently dropped from the statement view. Restatements or corrections that produce multiple valid contexts may lose the correct value.

**T11 — Revenue Deduplication** (`xbrl.py:971`, `deduplication_strategy.py`)
For income statements, if two revenue concepts have the same dollar value in the same period, the lower-precedence concept is silently removed. Precedence: `RevenueFromContractWithCustomer...` > `Revenues` > `SalesRevenueNet` > `Revenue` > `TotalRevenuesAndGains`. Two semantically different concepts with coincidentally equal values get collapsed.

**T12/T21 — Display vs Raw Value Asymmetry** (`rendering.py:1293, :1549`)
`str(statement)` shows sign-negated, scaled values. `statement.to_dataframe()` returns raw un-negated, unscaled values. Same fact, different numbers depending on how you read it.

**T16 — Silent Period Dropping** (`period_selector.py:720`)
Periods with fewer facts than 40% of the richest period's count are silently excluded from rendered statements. Older comparative periods or partial restatements may disappear.

### Full Transformation Catalog

| ID | Location | What It Does | Lossy? | Risk |
|---|---|---|---|---|
| T1 | `instance.py:431` | Float coercion of text values | No | Low |
| T2 | `instance.py:443` | Duplicate instance key renaming | No | None |
| T3 | `instance.py:805` | Fiscal period classification (350-380d = FY) | No | Low |
| T4 | `instance.py:631` | `reporting_end_date` = max instant date | No | Low-Moderate |
| T5 | `facts.py:1150` | Label overwritten with dimension member label | No (original preserved) | Moderate |
| T6 | `facts.py:1171` | `preferred_sign` metadata derived from presentation | No | Low |
| T7 | `facts.py:1122` | `statement_type` = first-tree match | No | Moderate |
| T8 | `facts.py:700` | `.scale()` divides numeric values | **Yes** | High |
| T9 | `facts.py:718` | `.aggregate()` collapses dimensional facts | **Yes** | High |
| T10 | `xbrl.py:1183` | Multi-context: fewest-dim / highest-precision fact wins | **Yes** | High |
| T11 | `xbrl.py:971` | Revenue dedup removes lower-precedence concepts | **Yes** | High |
| T12 | `rendering.py:1293` | `preferred_sign` negates display value only | No (raw in cell.value) | Moderate |
| T13 | `xbrl.py:978` | Balance sheet line item reordering | No | None |
| T14 | `xbrl.py:982` | Level adjustment by calculation parent | No | None |
| T15 | `period_selector.py:93` | Periods after document date filtered out | **Yes (display)** | Low-Moderate |
| T16 | `period_selector.py:720` | Sparse periods filtered by fact count threshold | **Yes (display)** | Moderate |
| T17 | `period_selector.py:386` | Annual = 300-400 days classification | No | Low |
| T18 | `rendering.py:1466` | Structural XBRL elements removed | No (metadata only) | None |
| T19 | `rendering.py:1479` | Dimensional breakdowns hidden in STANDARD view | **Yes (display)** | Moderate |
| T20 | `rendering.py:1372` | Empty-only periods removed | **Yes (display)** | Low |
| T21 | `rendering.py:1549` | Values divided by dominant scale for display | **Yes (display string)** | Moderate |
| T22 | `rendering.py:1501` | `standard_concept` metadata added | No | None |
| T23 | `rendering.py:1791` | Equity labels get "Beginning/Ending balance" suffix | No | None |
| T24 | `rendering.py:1838` | Equity beginning balance from day-before instant | No | Low |
| T25 | `xbrl.py:300` | `period_of_report` SGML may override XBRL DEI fact | No | Moderate |
| T26 | `current_period.py:155` | Instant preferred for balance sheet, duration for income | No | None |

## Finding 2: Our Standardization Layer Is Safe

**None of our 4 extraction layers or the reference validator call `get_statement()` or `render()`.** We completely bypass the dangerous transformations (T8–T12, T15–T16, T19, T21).

### What Each Layer Actually Reads

| Layer | EdgarTools API Used | What It Reads | Danger Zone Exposure |
|-------|-------------------|---------------|---------------------|
| Layer 1: Tree Parser | `xbrl.calculation_trees` | Structural relationships (parent, children, weight) | None |
| Layer 2: AI Semantic | `xbrl.calculation_trees` | Tree context for LLM prompt | None |
| Layer 3: Facts Search | `Company.get_facts().to_dataframe()` | Concept names only (existence check) | None |
| Layer 4: Dimensional | `xbrl.facts.get_facts_by_concept()` | Raw `numeric_value` from facts DataFrame | None |
| Reference Validator | `xbrl.facts.get_facts_by_concept()` | Raw `numeric_value` with own period filtering | None |

### Transformations We Inherit (Low Risk Only)

| Transform | Impact on Us |
|-----------|-------------|
| T1: Float coercion | We read `numeric_value` (the float). Precision loss only above 15 significant digits. |
| T2: Duplicate key renaming | All facts preserved; indexed differently. |
| T3: Fiscal period classification | We do our own duration-based filtering (±30 day tolerance), not dependent on EdgarTools' labels. |
| T4: `reporting_end_date` derivation | We use `filing_date` from filing metadata, not this derived date. |

### Trust Levels by API

| API Level | Transformations Applied | Trust Level |
|-----------|------------------------|-------------|
| `xbrl.facts` (raw facts query) | T1–T7 only (parsing + metadata) | **High** — values are faithful |
| `xbrl.get_statement()` (statement view) | T1–T21 (includes dedup, period filtering, fact selection) | **Medium** — values can be dropped or selected |
| `statement.render()` / `str()` (display) | All T1–T26 (includes sign flip, scaling) | **Low** — display values ≠ raw values |

**Our code exclusively uses the "High" trust level.**

## Finding 3: Two SEC Data Paths Exist

The SEC provides two fundamentally different ways to access financial data. We currently use Path A for values and Path B for concept discovery only.

### Path A: Filing-Level XBRL (our current value source)

```
Endpoint:  www.sec.gov/Archives/edgar/data/{cik}/{accession}/{filing}.htm
Code:      filing.xbrl() → parse inline XBRL → xbrl.facts
Scope:     One specific filing (e.g., Apple's FY2023 10-K)
```

Returns the actual tagged XBRL from a single filing, exactly as the company's accountants filed it.

### Path B: SEC Company Facts API (currently used for concept discovery only)

```
Endpoint:  data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
Code:      Company(ticker).get_facts()
Scope:     ALL facts from ALL filings for a company, ever
```

The SEC pre-compiles every XBRL filing into one JSON per company. One API call returns every concept × every period × every filing in the company's history.

### Comparison

| Dimension | Path A: Filing XBRL | Path B: Company Facts API |
|-----------|---------------------|---------------------------|
| **Speed** | Slow (download + parse per filing) | Fast (1 call = entire history) |
| **Authority** | The literal filed document | SEC's pre-compiled derivative index |
| **Dimensions** | Full dimensional data (segments, geography) | **None — non-dimensional totals only** |
| **Calculation trees** | Available (validates concept relationships) | **Not available** |
| **Multi-period** | Must parse each filing separately | Built-in — all periods in one response |
| **Ambiguity** | Low (one filing = one context) | High (see Bug #408 below) |
| **Precision metadata** | `decimals` attribute per fact | **Not available** |
| **Filing metadata** | Full XBRL context | Accession number, form type, filing date |
| **Staleness risk** | Authoritative by definition | May lag on amendments/restatements |

### Known Bug: Company Facts API Ambiguity (Bug #408)

The SEC Company Facts API can return multiple entries for the same `(fiscal_year, fiscal_period)` with different values:

```
Apple FY 2020, fp="FY", end=2020-09-26: $274,515,000,000  (363 days, annual)
Apple FY 2020, fp="FY", end=2020-09-26: $64,698,000,000   (90 days, quarterly)
```

Both are marked `fp="FY"`. Without duration-based filtering (which requires `start` date — only present for duration facts), consumers can pick the wrong value. This caused EdgarTools Bug #408 where annual statements showed quarterly values.

## Opportunity: Hybrid Approach for Multi-Period Validation

Our current multi-period golden master validation requires parsing 3+ separate 10-K filings per company. Path B could make this dramatically faster.

### Proposed Hybrid Strategy

| Use Case | Path | Rationale |
|----------|------|-----------|
| **Value extraction** (CQS scoring) | Path A | Authoritative, has dimensions, has precision |
| **Concept discovery** (Layer 3) | Path B | Already doing this — correct |
| **Multi-period stability check** | Path B (new) | One call instead of parsing 3-5 filings |
| **Golden master promotion** | Path A cross-checked with Path B | Both must agree for promotion |
| **Historical trend analysis** | Path B | Purpose-built for this use case |

### Benefits of Hybrid

- **Speed**: Golden master promotion could go from minutes to seconds per company
- **Coverage**: Path B has the company's entire history — easy to check 10+ periods
- **Cross-validation**: If Path A and Path B disagree on a value, that's a signal to investigate

### Risks of Hybrid

- **Dimensional blind spot**: Companies reporting only dimensional data (e.g., JPM's VIE-only commercial paper) won't appear in Path B at all
- **Ambiguity**: Must implement duration-based filtering to avoid Bug #408-style errors
- **Staleness**: Path B may lag Path A on amendments — cross-check mitigates this

## Decision

**Open for discussion.** Three questions for colleagues:

1. Should we adopt the hybrid approach for multi-period validation? The speed gain is significant, but it introduces a second data source that could disagree with our primary source.

2. For golden master promotion, is "Path A and Path B agree" a stronger standard than "Path A is stable across 3+ filings"? Or does the ambiguity in Path B make it less trustworthy than additional Path A parses?

3. Should we document and monitor the transformations we inherit (T1–T4) as part of our quality assurance, even though the risk is low? Float precision (T1) could theoretically matter for share counts in the trillions.

## References

- ADR-001: Separate Standardization Package from Upstream EdgarTools
- Consensus 018: CQS Scoring Integrity Reform
- Consensus 019: "Diagnose, Then Fix" Roadmap
- EdgarTools Bug #408: Annual period selection showing quarterly values
- Upstream: `edgar/entity/entity_facts.py` (Company Facts API wrapper)
- Upstream: `edgar/xbrl/parsers/instance.py` (Filing-level XBRL parser)
- Upstream comparison doc: `edgar/entity/.docs/internal/facts-xbrl-comparison.md`
