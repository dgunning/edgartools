# Subscription-Grade Roadmap Design

**Date:** 2026-04-04
**Status:** Approved
**Consensus basis:** Deep-Consensus 022 (subscription-grade strategy) + PAL Consensus 022 (loop fate)

## Context

EdgarTools has an XBRL extraction system at EF-CQS 0.8544 on 100 companies (0.8740 on original 50). The real failure rate is ~3.8% (129 genuine failures out of 3,391 evaluated pairs). 6 of 8 core metrics have zero reference standard issues. The autonomous improvement loop has produced zero net improvements since Run 011 (19 runs). The system needs to pivot from "improve CQS score" to "ship quality signals to users" and scale to 500 companies.

## Architecture: Two Sub-Projects

### Sub-project 1: Quality Signals (~2 weeks)

Wire confidence intelligence to users. Establish ground truth.

```
Step 0: Decompose 129 failures (1 hour)
Step 1: Define subscription-grade data contract (1 day)
Step 2: Wire two-tier confidence signals (2-3 days)
Step 3: Build golden master set (3-5 days)
```

### Sub-project 2: Scale & Monitor (~2-3 weeks)

Build production monitoring. Expand to 500 companies.

```
Step 4: Document definitional choices (3 days)
Step 5: Build regression monitor (2-3 days)
Step 6: Extend DataDictionaryEntry for user-facing data contract (2 days)
Step 7: Scale to 500 companies (ongoing, batches of 50)
```

---

## Sub-project 1: Quality Signals

### Step 0: Decompose 129 Failures

**Duration:** 1 hour
**Files:** Read-only (measurement)

Run `identify_gaps(eval_cohort=EXPANSION_COHORT_100, snapshot_mode=True)` and classify each gap:

| Category | Definition | Action |
|----------|-----------|--------|
| `unmapped` | gap_type="unmapped", value is None | Investigate or not_applicable |
| `wrong_concept` | gap_type="high_variance", hv_subtype="hv_wrong_concept" | Fix config |
| `wrong_value` | gap_type="high_variance", right concept but exceeds tolerance | Scale/period fix |
| `composite_needed` | gap_type="high_variance", hv_subtype="hv_missing_component" | Build formula or defer |

Output: Classified gap report. Prioritize core metrics at large-cap companies. This determines scope for Steps 2-3.

### Step 1: Data Contract

**Duration:** 1 day
**Files:** New `docs/data-contract.md`, modify `config_loader.py`

One-page specification:

- **Product A scope:** 8 core metrics — Revenue, NetIncome, OperatingCashFlow, TotalAssets, EarningsPerShareDiluted, StockholdersEquity, TotalLiabilities, OperatingIncome
- **Coverage:** 500 S&P companies (100 evaluated, expanding)
- **Accuracy:** 99% against SEC filings for core metrics at `high` confidence
- **Confidence levels:**
  - `high` — tree-resolved, known concept, reference-confirmed
  - `medium` — mapped but reference differs or self-validated only
  - `low` — facts-search fallback, unverified source
  - `unverified` — unmapped or value is None
  - `not_applicable` — metric excluded for this company/industry
- **Known limitations per metric:** documented in DataDictionaryEntry
- **Temporal scope:** Latest annual (10-K). Multi-period deferred.
- **Freshness:** Data available within 48 hours of EDGAR availability

Extend `DataDictionaryEntry` (`config_loader.py:428`) with:
```python
known_limitations: Optional[str] = None
reference_standard_notes: Optional[str] = None
coverage_rate: Optional[float] = None
```

### Step 2: Two-Tier Confidence Signals

**Duration:** 2-3 days
**Files:** `standardized_financials.py`, `database/schema.py`, `database/populator.py`

#### Tier 1: Fast Heuristic (always-on, no network)

Add `_compute_lightweight_confidence()` to `standardized_financials.py`, called during `extract_standardized_financials()`:

```python
def _compute_lightweight_confidence(
    metric: StandardizedMetric,
    config: MappingConfig,
    company_config: Optional[CompanyConfig],
) -> Tuple[str, str]:
    """Returns (publish_confidence, evidence_tier)."""
    if metric.is_excluded:
        return ("not_applicable", "excluded")
    if metric.value is None:
        return ("unverified", "unverified")

    # Check known divergence
    has_divergence = (
        company_config
        and metric.name in getattr(company_config, 'known_divergences', {})
    )

    # Check if concept is in known_concepts for this metric
    metric_config = config.get_metric(metric.name)
    is_known = (
        metric_config
        and metric.concept
        and any(
            kc in metric.concept
            for kc in (metric_config.known_concepts or [])
        )
    )

    if metric.source == 'tree' and is_known and not has_divergence:
        return ("high", "tree_confirmed")
    if metric.source in ('tree', 'facts', 'industry'):
        evidence = "tree_confirmed" if metric.source == 'tree' else "facts_search"
        return ("medium", evidence)
    return ("low", "unverified")
```

Also populate from filing context (already available during extraction):
- `period_end` — from `filing.period_of_report`
- `accession_number` — from `filing.accession_no`

#### Tier 2: Full Validation (opt-in)

Add `validate=True` parameter to `extract_standardized_financials()`:
- When True, runs `validator.validate_company()` after extraction
- Copies `ValidationResult.publish_confidence` and `evidence_tier` onto `StandardizedMetric`
- Requires yfinance snapshots or network access
- Slower but more rigorous (checks reference matches + internal equations)

#### Database Integration

Add to `financial_metrics` table in `database/schema.py`:
```sql
publish_confidence TEXT,
evidence_tier TEXT
```

Update `populator.py` `record_metrics()` to write these fields.

### Step 3: Golden Master Set

**Duration:** 3-5 days (2 sessions verification + 3 days definitional choices)
**Files:** New `tests/xbrl/standardization/test_golden_masters.py`, update `docs/data-contract.md`

#### Selection: 10 companies x 8 core metrics = 80 values

| Sector | Company | Rationale |
|--------|---------|-----------|
| Technology | AAPL | Flagship, clean reporting |
| Financials | JPM | Banking archetype |
| Healthcare | JNJ | Pharma, standard reporting |
| Energy | XOM | Energy archetype |
| Consumer Staples | WMT | Retail, franchise FYE |
| Consumer Disc | AMZN | E-commerce, NCI equity edge case |
| Industrials | CAT | Financial services subsidiary |
| Utilities | DUK | Rate-regulated utility |
| Real Estate | PLD | REIT archetype |
| Telecom | CMCSA | Spectrum licenses, intangibles |

#### Process

For each company-metric pair:
1. Open actual 10-K on EDGAR
2. Find the line item in financial statements
3. Record: expected value, page/section reference, any definitional notes
4. If ambiguous (e.g., OperatingIncome scope), document the choice in `docs/data-contract.md`

#### Output

`tests/xbrl/standardization/test_golden_masters.py`:
```python
class TestGoldenMasters:
    """Hand-verified values from actual SEC 10-K filings.
    Each test documents: company, metric, expected value, filing reference.
    """

    def test_aapl_revenue(self):
        """AAPL FY2024 Revenue: $394,328M (10-K p.26)"""
        sf = extract_standardized_financials("AAPL")
        assert_within_tolerance(sf.revenue, 394328000000, tolerance=0.001)

    def test_jpm_total_assets(self):
        """JPM FY2024 Total Assets: $4,003,047M (10-K p.172)"""
        sf = extract_standardized_financials("JPM")
        assert_within_tolerance(sf.total_assets, 4003047000000, tolerance=0.001)
```

---

## Sub-project 2: Scale & Monitor

### Step 4: Document Definitional Choices

**Duration:** 3 days
**Files:** `docs/data-contract.md`

Resolve ambiguities surfaced by golden master verification:

| Metric | Ambiguity | Resolution |
|--------|-----------|------------|
| OperatingIncome | With/without impairment charges | GAAP as reported (includes impairment) |
| TotalLiabilities | us-gaap:Liabilities vs composite | Composite L&SE - SE, NCI-inclusive preferred |
| StockholdersEquity | Parent-only vs NCI-inclusive | NCI-inclusive when available, parent-only fallback |
| EarningsPerShareDiluted | Basic vs diluted, GAAP vs adjusted | GAAP diluted as reported |

Each choice documented with: definition, rationale, known edge cases, companies affected.

### Step 5: Regression Monitor

**Duration:** 2-3 days
**Files:** New `edgar/xbrl/standardization/tools/regression_monitor.py`

~200-300 lines. Imports from `auto_eval.py` only.

```python
@dataclass
class RegressionReport:
    timestamp: str
    cohort_size: int
    ef_cqs: float
    regressions: List[Regression]  # (ticker, metric, old_value, new_value, delta)
    new_gaps: List[MetricGap]      # gaps not in previous run
    quality_summary: Dict[str, Any]

def run_regression_check(
    cohort: List[str] = EXPANSION_COHORT_100,
    baseline: Optional[CQSResult] = None,
    golden_masters: Optional[Dict] = None,
    snapshot_mode: bool = True,
) -> RegressionReport:
    """Quarterly regression check. Read-only, stateless."""
    result = compute_cqs(eval_cohort=cohort, snapshot_mode=snapshot_mode)
    regressions = _detect_regressions(result, baseline, golden_masters)
    new_gaps = _detect_new_gaps(result, baseline)
    return RegressionReport(...)
```

CLI entry point:
```bash
python -m edgar.xbrl.standardization.tools.regression_monitor --cohort 100 --baseline latest
```

### Step 6: Data Contract Extension

**Duration:** 2 days
**Files:** `config_loader.py`, `config/data_dictionary.yaml`

Populate the 3 new `DataDictionaryEntry` fields for all 36 metrics:

```yaml
Revenue:
  known_limitations: null  # No known limitations
  reference_standard_notes: "Matches us-gaap:Revenues or us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
  coverage_rate: 1.0  # 100% of S&P 500

TotalLiabilities:
  known_limitations: "~11% of companies use composite formula (L&SE - SE) because us-gaap:Liabilities is absent"
  reference_standard_notes: "Composite: LiabilitiesAndStockholdersEquity minus StockholdersEquity (NCI-inclusive preferred)"
  coverage_rate: 0.95
```

### Step 7: 500-Company Expansion

**Duration:** Ongoing (batches of 50)
**Files:** Various config files

Pipeline per batch:
1. Generate yfinance snapshots: `refresh_yf_snapshots.py`
2. Classify industry: add to `_COMPANY_INDUSTRY_MAP`
3. Onboard: `onboard_company.py --no-ai`
4. Screen: `regression_monitor.py --cohort new_batch`
5. Fix outliers: create JSON overrides
6. Verify: EF-CQS >= 0.85 on full cohort
7. Expand golden masters: add 5-10 companies per quarter

### Deprecated Modules

Per Consensus 022, mark as deprecated in docstrings:
- `auto_eval_loop.py` — "Deprecated: improvement loop exhausted since Run 011. Use regression_monitor.py."
- `auto_solver.py` — "Deprecated: deterministic solver ceiling reached."
- `consult_ai_gaps.py` — "Deprecated: AI dispatch 0% KEEP rate."

---

## Verification

### Sub-project 1 verification
```bash
# Step 0: Run gap decomposition
python3 -c "from edgar.xbrl.standardization.tools.auto_eval import identify_gaps, EXPANSION_COHORT_100; gaps, r = identify_gaps(EXPANSION_COHORT_100); print(f'{len(gaps)} gaps')"

# Step 2: Verify confidence signals populate
python3 -c "
from edgar.standardized_financials import extract_standardized_financials
sf = extract_standardized_financials('AAPL')
assert sf['Revenue'].publish_confidence is not None
print(f'Revenue confidence: {sf[\"Revenue\"].publish_confidence}')
"

# Step 3: Run golden master tests
python -m pytest tests/xbrl/standardization/test_golden_masters.py -v

# Full test suite (no regressions)
python -m pytest tests/xbrl/standardization/ -q --tb=short
```

### Sub-project 2 verification
```bash
# Step 5: Run regression monitor
python -m edgar.xbrl.standardization.tools.regression_monitor --cohort 100

# Step 7: 500-company quality gate
python3 -c "
from edgar.xbrl.standardization.tools.auto_eval import compute_cqs, EXPANSION_COHORT_500
r = compute_cqs(eval_cohort=EXPANSION_COHORT_500, snapshot_mode=True)
print(f'500-co EF-CQS: {r.ef_cqs:.4f} (must be >= 0.85)')
"
```

## Success Criteria

| Criterion | Target |
|-----------|--------|
| `publish_confidence` populated on every StandardizedMetric | 100% (never None) |
| Core metrics at `high` confidence for standard companies | >= 90% |
| Golden master tests passing (80 hand-verified values) | 100% |
| Regression monitor detects known regressions | Verified with synthetic test |
| 500-company EF-CQS | >= 0.85 |
| Zero regressions in original 100 companies | EF-CQS >= 0.8544 |
| Deprecated modules marked in docstrings | auto_eval_loop, auto_solver, consult_ai_gaps |
