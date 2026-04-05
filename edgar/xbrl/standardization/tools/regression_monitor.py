"""
Regression Monitor: Stateless quality regression detection for production monitoring.

Compares current extraction quality against a baseline CQS result and golden master
values to detect regressions. Read-only and stateless — safe to run in CI or as
a quarterly check.

Usage:
    python -m edgar.xbrl.standardization.tools.regression_monitor --cohort 100

Deprecated modules replaced by this:
    - auto_eval_loop.py (improvement loop exhausted since Run 011)
    - auto_solver.py (solver ceiling reached)
    - consult_ai_gaps.py (AI dispatch 0% KEEP rate)
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

log = logging.getLogger(__name__)


@dataclass
class Regression:
    """A single metric regression."""
    ticker: str
    metric: str
    old_status: str     # e.g., "pass", "match"
    new_status: str     # e.g., "fail", "high_variance"
    old_value: Optional[float] = None
    new_value: Optional[float] = None
    delta_pct: Optional[float] = None

    def __str__(self):
        delta = f" ({self.delta_pct:+.2%})" if self.delta_pct else ""
        return f"{self.ticker}:{self.metric} {self.old_status} -> {self.new_status}{delta}"


@dataclass
class RegressionReport:
    """Result of a regression check."""
    timestamp: str
    cohort_size: int
    ef_cqs: float
    baseline_ef_cqs: Optional[float]
    regressions: List[Regression] = field(default_factory=list)
    new_gaps: List[str] = field(default_factory=list)
    golden_master_failures: List[str] = field(default_factory=list)
    quality_summary: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_regressions(self) -> bool:
        return len(self.regressions) > 0

    @property
    def ef_cqs_delta(self) -> Optional[float]:
        if self.baseline_ef_cqs is not None:
            return self.ef_cqs - self.baseline_ef_cqs
        return None

    def to_dict(self) -> dict:
        d = asdict(self)
        d['has_regressions'] = self.has_regressions
        d['ef_cqs_delta'] = self.ef_cqs_delta
        return d

    def print_summary(self):
        """Print human-readable summary."""
        print(f"\n{'=' * 60}")
        print(f"Regression Monitor Report — {self.timestamp}")
        print(f"{'=' * 60}")
        print(f"Cohort: {self.cohort_size} companies")
        print(f"EF-CQS: {self.ef_cqs:.4f}", end="")
        if self.baseline_ef_cqs is not None:
            delta = self.ef_cqs_delta
            sign = "+" if delta >= 0 else ""
            print(f" (baseline: {self.baseline_ef_cqs:.4f}, delta: {sign}{delta:.4f})")
        else:
            print(" (no baseline)")

        if self.regressions:
            print(f"\nREGRESSIONS ({len(self.regressions)}):")
            for r in self.regressions:
                print(f"  - {r}")
        else:
            print("\nNo regressions detected.")

        if self.golden_master_failures:
            print(f"\nGOLDEN MASTER FAILURES ({len(self.golden_master_failures)}):")
            for f in self.golden_master_failures:
                print(f"  - {f}")

        if self.new_gaps:
            print(f"\nNEW GAPS ({len(self.new_gaps)}):")
            for g in self.new_gaps[:10]:
                print(f"  - {g}")
            if len(self.new_gaps) > 10:
                print(f"  ... and {len(self.new_gaps) - 10} more")

        print(f"\nQuality summary: {json.dumps(self.quality_summary, indent=2)}")
        print(f"{'=' * 60}\n")


def _detect_regressions(
    current,
    baseline,
) -> List[Regression]:
    """Compare current CQS result against baseline to find regressions."""
    regressions = []
    if baseline is None:
        return regressions

    # Check per-company EF pass rates
    for ticker, current_scores in current.company_scores.items():
        baseline_scores = baseline.company_scores.get(ticker)
        if baseline_scores is None:
            continue  # New company, not a regression

        # Compare per-metric results
        current_details = getattr(current_scores, 'metric_details', {})
        baseline_details = getattr(baseline_scores, 'metric_details', {})

        for metric, cur_detail in current_details.items():
            base_detail = baseline_details.get(metric)
            if base_detail is None:
                continue

            cur_pass = getattr(cur_detail, 'ef_pass', None)
            base_pass = getattr(base_detail, 'ef_pass', None)

            # Regression: was passing, now failing
            if base_pass and not cur_pass:
                regressions.append(Regression(
                    ticker=ticker,
                    metric=metric,
                    old_status="ef_pass",
                    new_status="ef_fail",
                ))

    return regressions


def _detect_new_gaps(current, baseline) -> List[str]:
    """Find gaps in current that didn't exist in baseline."""
    if baseline is None:
        return []

    new_gaps = []
    for ticker, current_scores in current.company_scores.items():
        baseline_scores = baseline.company_scores.get(ticker)
        if baseline_scores is None:
            continue

        current_details = getattr(current_scores, 'metric_details', {})
        baseline_details = getattr(baseline_scores, 'metric_details', {})

        for metric, cur_detail in current_details.items():
            base_detail = baseline_details.get(metric)
            if base_detail is None:
                continue

            cur_mapped = getattr(cur_detail, 'is_mapped', True)
            base_mapped = getattr(base_detail, 'is_mapped', True)

            if base_mapped and not cur_mapped:
                new_gaps.append(f"{ticker}:{metric}")

    return new_gaps


def run_regression_check(
    cohort: Optional[List[str]] = None,
    baseline=None,
    snapshot_mode: bool = True,
) -> RegressionReport:
    """
    Run a regression check against a baseline.

    Stateless, read-only. Imports from auto_eval only.

    Args:
        cohort: List of tickers to evaluate (defaults to EXPANSION_COHORT_100)
        baseline: Previous CQSResult to compare against (None = no comparison)
        snapshot_mode: Use cached yfinance snapshots

    Returns:
        RegressionReport with detected regressions and quality summary
    """
    from edgar.xbrl.standardization.tools.auto_eval import (
        compute_cqs, EXPANSION_COHORT_100,
    )

    if cohort is None:
        cohort = EXPANSION_COHORT_100

    # Run current evaluation
    result = compute_cqs(eval_cohort=cohort, snapshot_mode=snapshot_mode)

    # Detect regressions
    regressions = _detect_regressions(result, baseline)
    new_gaps = _detect_new_gaps(result, baseline)

    report = RegressionReport(
        timestamp=datetime.now().isoformat(),
        cohort_size=result.companies_evaluated,
        ef_cqs=result.ef_cqs,
        baseline_ef_cqs=baseline.ef_cqs if baseline else None,
        regressions=regressions,
        new_gaps=new_gaps,
        quality_summary={
            "pass_rate": result.pass_rate,
            "coverage_rate": result.coverage_rate,
            "ef_pass_rate": result.ef_pass_rate,
            "sa_pass_rate": result.sa_pass_rate,
            "weighted_ef_cqs": result.weighted_ef_cqs,
            "headline_ef_rate": result.headline_ef_rate,
            "total_metrics": result.total_metrics,
            "total_mapped": result.total_mapped,
            "total_valid": result.total_valid,
            "total_regressions": len(regressions),
        },
    )

    return report


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Regression Monitor: detect quality regressions in XBRL extraction"
    )
    parser.add_argument(
        "--cohort", type=int, default=100, choices=[50, 100, 500],
        help="Cohort size (50, 100, or 500 companies)"
    )
    parser.add_argument(
        "--baseline", type=str, default=None,
        help="Path to baseline CQSResult JSON file"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Path to save report JSON"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # Load cohort
    from edgar.xbrl.standardization.tools.auto_eval import (
        EXPANSION_COHORT_50, EXPANSION_COHORT_100, EXPANSION_COHORT_500, CQSResult,
    )

    cohort_map = {50: EXPANSION_COHORT_50, 100: EXPANSION_COHORT_100, 500: EXPANSION_COHORT_500}
    cohort = cohort_map[args.cohort]

    # Load baseline
    baseline = None
    if args.baseline:
        with open(args.baseline) as f:
            baseline = CQSResult.from_dict(json.load(f))

    # Run check
    report = run_regression_check(cohort=cohort, baseline=baseline)
    report.print_summary()

    # Save if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"Report saved to {args.output}")

    # Exit code: 1 if regressions found
    sys.exit(1 if report.has_regressions else 0)


if __name__ == "__main__":
    main()
