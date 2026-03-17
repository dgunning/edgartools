"""
Auto-Eval: Autonomous quality measurement for the XBRL standardization pipeline.

Applies the autoresearch pattern — a single composite quality score (CQS) serves
as "val_bpb". The agent modifies only YAML configs ("weights"); the eval harness
(Orchestrator + ReferenceValidator + yf_snapshots) is fixed.

Key design:
- CQS is a weighted composite of pass_rate, variance, coverage, golden masters
- Regressions are a HARD VETO — any regression caps CQS below baseline
- Per-company breakdown enables drill-down diagnostics
- Gap analysis ranks opportunities by estimated CQS impact
"""

import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

from edgar.xbrl.standardization.models import MappingResult, MappingSource

logger = logging.getLogger(__name__)


# =============================================================================
# COHORT DEFINITIONS
# =============================================================================

# 5-company quick-eval cohort: diverse archetypes for fast feedback
QUICK_EVAL_COHORT = ["AAPL", "JPM", "XOM", "WMT", "JNJ"]

# 20-company validation cohort: broader coverage for overfitting protection
VALIDATION_COHORT = [
    "AAPL", "MSFT", "GOOG", "AMZN", "META", "NVDA", "TSLA",  # Tech
    "JPM", "BAC", "GS",                                         # Banking
    "XOM", "CVX",                                                # Energy
    "WMT", "PG", "KO", "PEP",                                   # Consumer
    "JNJ", "UNH", "PFE",                                        # Healthcare
    "CAT",                                                       # Industrial
]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CompanyCQS:
    """Per-company quality breakdown."""
    ticker: str
    pass_rate: float           # Fraction of metrics passing validation [0-1]
    mean_variance: float       # Average variance % across validated metrics
    coverage_rate: float       # Fraction of non-excluded metrics mapped [0-1]
    golden_master_rate: float  # Fraction of metrics with golden masters [0-1]
    regression_count: int      # Number of regressions vs previous baseline
    metrics_total: int         # Total non-excluded metrics
    metrics_mapped: int        # Mapped metrics
    metrics_valid: int         # Validation-passing metrics
    metrics_excluded: int      # CONFIG-excluded metrics
    cqs: float                 # Composite quality score for this company

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MetricGap:
    """A gap in the extraction pipeline, ranked by CQS impact."""
    ticker: str
    metric: str
    gap_type: str              # "unmapped" | "validation_failure" | "high_variance" | "regression"
    estimated_impact: float    # Estimated CQS improvement if resolved [0-1]
    current_variance: Optional[float] = None
    reference_value: Optional[float] = None
    xbrl_value: Optional[float] = None
    graveyard_count: int = 0   # Number of prior failed attempts
    notes: str = ""

    @property
    def is_dead_end(self) -> bool:
        """Skip gaps with too many prior failures."""
        return self.graveyard_count >= 3


@dataclass
class CQSResult:
    """
    Composite Quality Score — the single number that drives auto-eval decisions.

    CQS = weighted sum of sub-metrics, with hard veto on regressions.
    """
    # Aggregate sub-metrics
    pass_rate: float           # Weight: 0.50
    mean_variance: float       # Weight: 0.20 (inverted: lower is better)
    coverage_rate: float       # Weight: 0.15
    golden_master_rate: float  # Weight: 0.10
    regression_rate: float     # Weight: 0.05 (inverted: lower is better)

    # The composite score
    cqs: float

    # Metadata
    companies_evaluated: int
    total_metrics: int
    total_mapped: int
    total_valid: int
    total_regressions: int

    # Per-company breakdown
    company_scores: Dict[str, CompanyCQS] = field(default_factory=dict)

    # Timing
    duration_seconds: float = 0.0

    # Whether regressions triggered hard veto
    vetoed: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d['company_scores'] = {k: v.to_dict() if isinstance(v, CompanyCQS) else v
                               for k, v in self.company_scores.items()}
        return d

    def summary(self) -> str:
        """One-line summary."""
        veto = " [VETOED]" if self.vetoed else ""
        return (
            f"CQS={self.cqs:.4f}{veto} | "
            f"pass={self.pass_rate:.1%} var={self.mean_variance:.1f}% "
            f"cov={self.coverage_rate:.1%} golden={self.golden_master_rate:.1%} "
            f"regress={self.total_regressions} | "
            f"{self.companies_evaluated} cos, {self.duration_seconds:.1f}s"
        )


# =============================================================================
# CQS COMPUTATION
# =============================================================================

def compute_cqs(
    eval_cohort: Optional[List[str]] = None,
    snapshot_mode: bool = True,
    use_ai: bool = False,
    baseline_cqs: Optional[float] = None,
    ledger=None,
) -> CQSResult:
    """
    Compute the Composite Quality Score for a cohort of companies.

    This is the core measurement function — the "val_bpb" of our system.
    It runs the full Orchestrator pipeline and validates against yfinance
    snapshots, then computes a single composite score.

    Args:
        eval_cohort: List of tickers to evaluate (defaults to QUICK_EVAL_COHORT).
        snapshot_mode: Use cached yfinance snapshots (True for speed).
        use_ai: Whether to use Layer 3 AI mapping (False for deterministic eval).
        baseline_cqs: If provided, regressions trigger hard veto below this value.
        ledger: ExperimentLedger instance for golden master lookups.

    Returns:
        CQSResult with composite score and per-company breakdown.
    """
    from edgar.xbrl.standardization.orchestrator import Orchestrator
    from edgar.xbrl.standardization.ledger.schema import ExperimentLedger

    start_time = time.time()

    if eval_cohort is None:
        eval_cohort = QUICK_EVAL_COHORT

    if ledger is None:
        ledger = ExperimentLedger()

    # Run orchestrator on the cohort
    orchestrator = Orchestrator(snapshot_mode=snapshot_mode)
    all_results = orchestrator.map_companies(
        tickers=eval_cohort, use_ai=use_ai, validate=True
    )

    # Gather golden masters for regression detection
    golden_masters = ledger.get_all_golden_masters(active_only=True)
    golden_set = {(gm.ticker, gm.metric) for gm in golden_masters}

    # Compute per-company scores
    company_scores: Dict[str, CompanyCQS] = {}

    for ticker, metrics in all_results.items():
        company_scores[ticker] = _compute_company_cqs(
            ticker, metrics, golden_set, orchestrator.validation_results.get(ticker, {})
        )

    # Aggregate across companies
    result = _aggregate_cqs(company_scores, baseline_cqs, time.time() - start_time)

    logger.info(f"Auto-eval complete: {result.summary()}")
    return result


def _compute_company_cqs(
    ticker: str,
    metrics: Dict[str, MappingResult],
    golden_set: set,
    validations: dict,
) -> CompanyCQS:
    """Compute CQS sub-metrics for a single company."""
    total = 0
    mapped = 0
    valid = 0
    excluded = 0
    variances = []
    golden_count = 0
    regression_count = 0

    for metric, result in metrics.items():
        if result.source == MappingSource.CONFIG:
            excluded += 1
            continue

        total += 1

        if result.is_mapped:
            mapped += 1

        # Check validation status
        if result.validation_status == "valid":
            valid += 1
        elif result.validation_status == "invalid":
            # A previously golden metric that now fails = regression
            if (ticker, metric) in golden_set:
                regression_count += 1

        # Collect variance from validation results
        val_result = validations.get(metric)
        if val_result and val_result.variance_pct is not None:
            variances.append(abs(val_result.variance_pct))

        # Check golden master status
        if (ticker, metric) in golden_set:
            golden_count += 1

    # Compute sub-metrics
    pass_rate = valid / total if total > 0 else 0.0
    mean_variance = sum(variances) / len(variances) if variances else 0.0
    coverage_rate = mapped / total if total > 0 else 0.0
    golden_master_rate = golden_count / total if total > 0 else 0.0

    # Per-company CQS (same formula as aggregate)
    cqs = (
        0.50 * pass_rate
        + 0.20 * max(0, 1 - mean_variance / 100)
        + 0.15 * coverage_rate
        + 0.10 * golden_master_rate
        + 0.05 * (1.0 if regression_count == 0 else 0.0)
    )

    return CompanyCQS(
        ticker=ticker,
        pass_rate=pass_rate,
        mean_variance=mean_variance,
        coverage_rate=coverage_rate,
        golden_master_rate=golden_master_rate,
        regression_count=regression_count,
        metrics_total=total,
        metrics_mapped=mapped,
        metrics_valid=valid,
        metrics_excluded=excluded,
        cqs=cqs,
    )


def _aggregate_cqs(
    company_scores: Dict[str, CompanyCQS],
    baseline_cqs: Optional[float],
    duration: float,
) -> CQSResult:
    """Aggregate per-company scores into a single CQS."""
    if not company_scores:
        return CQSResult(
            pass_rate=0, mean_variance=0, coverage_rate=0,
            golden_master_rate=0, regression_rate=0, cqs=0,
            companies_evaluated=0, total_metrics=0, total_mapped=0,
            total_valid=0, total_regressions=0, duration_seconds=duration,
        )

    n = len(company_scores)
    scores = list(company_scores.values())

    # Weighted average (equal weight per company)
    pass_rate = sum(s.pass_rate for s in scores) / n
    mean_variance = sum(s.mean_variance for s in scores) / n
    coverage_rate = sum(s.coverage_rate for s in scores) / n
    golden_master_rate = sum(s.golden_master_rate for s in scores) / n

    total_regressions = sum(s.regression_count for s in scores)
    total_metrics = sum(s.metrics_total for s in scores)
    regression_rate = total_regressions / total_metrics if total_metrics > 0 else 0.0

    # Compute composite CQS
    raw_cqs = (
        0.50 * pass_rate
        + 0.20 * max(0, 1 - mean_variance / 100)
        + 0.15 * coverage_rate
        + 0.10 * golden_master_rate
        + 0.05 * (1 - regression_rate)
    )

    # HARD VETO: regressions cap CQS below baseline
    vetoed = False
    if total_regressions > 0 and baseline_cqs is not None:
        raw_cqs = baseline_cqs - 0.01
        vetoed = True

    return CQSResult(
        pass_rate=pass_rate,
        mean_variance=mean_variance,
        coverage_rate=coverage_rate,
        golden_master_rate=golden_master_rate,
        regression_rate=regression_rate,
        cqs=raw_cqs,
        companies_evaluated=n,
        total_metrics=total_metrics,
        total_mapped=sum(s.metrics_mapped for s in scores),
        total_valid=sum(s.metrics_valid for s in scores),
        total_regressions=total_regressions,
        company_scores=company_scores,
        duration_seconds=duration,
        vetoed=vetoed,
    )


# =============================================================================
# GAP ANALYSIS
# =============================================================================

def identify_gaps(
    eval_cohort: Optional[List[str]] = None,
    snapshot_mode: bool = True,
    use_ai: bool = False,
    ledger=None,
    max_graveyard: int = 3,
) -> Tuple[List[MetricGap], CQSResult]:
    """
    Run evaluation and identify gaps ranked by CQS impact.

    Returns both the gaps and the CQS result so callers can use the
    baseline CQS for experiment decisions.

    Args:
        eval_cohort: Tickers to evaluate.
        snapshot_mode: Use cached snapshots.
        use_ai: Use AI mapping layer.
        ledger: ExperimentLedger for golden master + graveyard lookups.
        max_graveyard: Skip gaps with this many graveyard entries.

    Returns:
        Tuple of (ranked gaps, CQS result).
    """
    from edgar.xbrl.standardization.orchestrator import Orchestrator
    from edgar.xbrl.standardization.ledger.schema import ExperimentLedger

    if eval_cohort is None:
        eval_cohort = QUICK_EVAL_COHORT

    if ledger is None:
        ledger = ExperimentLedger()

    # Run full evaluation
    cqs_result = compute_cqs(
        eval_cohort=eval_cohort,
        snapshot_mode=snapshot_mode,
        use_ai=use_ai,
        ledger=ledger,
    )

    # Re-run orchestrator for detailed results (reuse from CQS cache if possible)
    orchestrator = Orchestrator(snapshot_mode=snapshot_mode)
    all_results = orchestrator.map_companies(
        tickers=eval_cohort, use_ai=use_ai, validate=True
    )

    # Get graveyard counts per metric
    graveyard_counts = _get_graveyard_counts(ledger)

    # Build gap list
    gaps: List[MetricGap] = []
    golden_masters = ledger.get_all_golden_masters(active_only=True)
    golden_set = {(gm.ticker, gm.metric) for gm in golden_masters}

    for ticker, metrics in all_results.items():
        validations = orchestrator.validation_results.get(ticker, {})
        company_total = sum(
            1 for r in metrics.values() if r.source != MappingSource.CONFIG
        )

        for metric, result in metrics.items():
            if result.source == MappingSource.CONFIG:
                continue

            gap = _classify_gap(
                ticker, metric, result, validations.get(metric),
                golden_set, company_total, graveyard_counts
            )
            if gap is not None:
                gaps.append(gap)

    # Sort by estimated impact (highest first), skip dead ends
    gaps.sort(key=lambda g: (-g.estimated_impact, g.graveyard_count))

    # Filter out dead ends
    active_gaps = [g for g in gaps if not g.is_dead_end]
    dead_ends = [g for g in gaps if g.is_dead_end]

    if dead_ends:
        logger.info(f"Skipping {len(dead_ends)} dead-end gaps (>={max_graveyard} graveyard entries)")

    return active_gaps, cqs_result


def _classify_gap(
    ticker: str,
    metric: str,
    result: MappingResult,
    validation,
    golden_set: set,
    company_total: int,
    graveyard_counts: Dict[str, int],
) -> Optional[MetricGap]:
    """Classify a single metric gap and estimate its CQS impact."""
    # Impact of fixing one metric for one company on aggregate CQS
    # pass_rate weight = 0.50, and each metric contributes 1/total to pass_rate
    per_metric_impact = 0.50 / max(company_total, 1)

    graveyard_key = f"{ticker}:{metric}"
    gc = graveyard_counts.get(graveyard_key, 0)

    xbrl_val = None
    ref_val = None
    variance = None

    if validation:
        xbrl_val = validation.xbrl_value
        ref_val = validation.reference_value
        variance = validation.variance_pct

    # Regression: previously golden, now failing
    if (ticker, metric) in golden_set and result.validation_status == "invalid":
        return MetricGap(
            ticker=ticker, metric=metric, gap_type="regression",
            estimated_impact=per_metric_impact * 2,  # Higher priority
            current_variance=variance, reference_value=ref_val,
            xbrl_value=xbrl_val, graveyard_count=gc,
            notes="Golden master regressed — high priority",
        )

    # Validation failure: mapped but wrong value
    if result.is_mapped and result.validation_status == "invalid":
        return MetricGap(
            ticker=ticker, metric=metric, gap_type="validation_failure",
            estimated_impact=per_metric_impact * 1.5,
            current_variance=variance, reference_value=ref_val,
            xbrl_value=xbrl_val, graveyard_count=gc,
            notes=f"Mapped to {result.concept} but failed validation",
        )

    # Unmapped: no concept found
    if not result.is_mapped:
        return MetricGap(
            ticker=ticker, metric=metric, gap_type="unmapped",
            estimated_impact=per_metric_impact,
            reference_value=ref_val, graveyard_count=gc,
            notes="No mapping found",
        )

    # High variance: mapped and "valid" but variance is concerning
    if variance is not None and abs(variance) > 10:
        return MetricGap(
            ticker=ticker, metric=metric, gap_type="high_variance",
            estimated_impact=per_metric_impact * 0.5,
            current_variance=variance, reference_value=ref_val,
            xbrl_value=xbrl_val, graveyard_count=gc,
            notes=f"Variance {variance:.1f}% is above 10% threshold",
        )

    return None


def _get_graveyard_counts(ledger) -> Dict[str, int]:
    """Get graveyard failure counts per ticker:metric key."""
    counts: Dict[str, int] = {}
    try:
        entries = ledger.get_graveyard_entries()
        for entry in entries:
            key = f"{entry.get('target_companies', '')}:{entry.get('target_metric', '')}"
            counts[key] = counts.get(key, 0) + 1
    except (AttributeError, Exception):
        # Graveyard table may not exist yet
        pass
    return counts


# =============================================================================
# PRINTING / REPORTING
# =============================================================================

def print_cqs_report(result: CQSResult):
    """Print a formatted CQS report to console."""
    print()
    print("=" * 70)
    print("COMPOSITE QUALITY SCORE (CQS) REPORT")
    print("=" * 70)

    veto_str = " ** HARD VETO — REGRESSIONS DETECTED **" if result.vetoed else ""
    print(f"\n  CQS: {result.cqs:.4f}{veto_str}")
    print()

    print("  Sub-metrics:")
    print(f"    Pass Rate:          {result.pass_rate:.1%}  (weight: 0.50)")
    print(f"    Mean Variance:      {result.mean_variance:.1f}%  (weight: 0.20, inverted)")
    print(f"    Coverage Rate:      {result.coverage_rate:.1%}  (weight: 0.15)")
    print(f"    Golden Master Rate: {result.golden_master_rate:.1%}  (weight: 0.10)")
    print(f"    Regression Rate:    {result.regression_rate:.1%}  (weight: 0.05, inverted)")
    print()

    print("  Totals:")
    print(f"    Companies:    {result.companies_evaluated}")
    print(f"    Metrics:      {result.total_metrics}")
    print(f"    Mapped:       {result.total_mapped}")
    print(f"    Valid:        {result.total_valid}")
    print(f"    Regressions:  {result.total_regressions}")
    print(f"    Duration:     {result.duration_seconds:.1f}s")

    if result.company_scores:
        print()
        print("  Per-Company Breakdown:")
        print(f"    {'Ticker':<8} {'CQS':>6} {'Pass':>6} {'Cov':>6} {'Var%':>6} {'Gold':>6} {'Reg':>4}")
        print("    " + "-" * 48)
        for ticker in sorted(result.company_scores.keys()):
            cs = result.company_scores[ticker]
            print(
                f"    {ticker:<8} {cs.cqs:>6.3f} {cs.pass_rate:>5.1%} "
                f"{cs.coverage_rate:>5.1%} {cs.mean_variance:>5.1f} "
                f"{cs.golden_master_rate:>5.1%} {cs.regression_count:>4d}"
            )

    print("=" * 70)
    print()


def print_gap_report(gaps: List[MetricGap], limit: int = 20):
    """Print a formatted gap analysis report."""
    print()
    print("=" * 70)
    print(f"GAP ANALYSIS — Top {min(limit, len(gaps))} opportunities")
    print("=" * 70)

    if not gaps:
        print("  No gaps found — pipeline is at full quality!")
        return

    print(f"  Total gaps: {len(gaps)}")
    print()
    print(f"  {'#':>3} {'Ticker':<8} {'Metric':<28} {'Type':<18} {'Impact':>7} {'GY':>3}")
    print("  " + "-" * 70)

    for i, gap in enumerate(gaps[:limit], 1):
        print(
            f"  {i:>3} {gap.ticker:<8} {gap.metric:<28} "
            f"{gap.gap_type:<18} {gap.estimated_impact:>7.4f} {gap.graveyard_count:>3}"
        )
        if gap.notes:
            print(f"      {gap.notes}")

    print("=" * 70)
    print()
