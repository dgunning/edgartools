"""
KPI Tracker - Track run statistics for measuring knowledge growth.

This module provides tools to:
1. Log statistics from each run
2. Track coverage and knowledge metrics over time
3. Generate progression reports

Usage:
    from edgar.xbrl.standardization.tools.kpi_tracker import log_run, get_progression
"""

import json
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from pathlib import Path


RUNS_HISTORY_FILE = Path(__file__).parent.parent / "company_mappings" / "runs_history.json"


@dataclass
class RunStatistics:
    """Statistics from a single mapping run."""
    run_id: str
    timestamp: str
    companies: List[str]
    company_count: int
    
    # Coverage metrics
    total_metrics: int
    mapped_metrics: int
    excluded_metrics: int
    raw_coverage_pct: float
    adjusted_coverage_pct: float
    
    # Validation metrics
    matched_count: int
    trusted_count: int
    discrepancy_count: int
    
    # Knowledge metrics
    universal_concepts: int
    industry_rules: int
    company_specific_rules: int
    documented_discrepancies: int
    
    # New discoveries
    new_concepts: List[str]
    new_discrepancies: List[str]


def load_runs_history() -> Dict:
    """Load runs history from JSON file."""
    if RUNS_HISTORY_FILE.exists():
        with open(RUNS_HISTORY_FILE, 'r') as f:
            return json.load(f)
    return {
        "schema_version": "1.0",
        "runs": []
    }


def save_runs_history(data: Dict):
    """Save runs history to JSON file."""
    with open(RUNS_HISTORY_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def log_run(stats: RunStatistics) -> str:
    """Log a run's statistics to history.
    
    Returns:
        The run_id that was logged.
    """
    data = load_runs_history()
    data["runs"].append(asdict(stats))
    save_runs_history(data)
    return stats.run_id


def create_run_stats(
    run_name: str,
    results: Dict[str, Dict],
    knowledge_counts: Optional[Dict] = None
) -> RunStatistics:
    """Create RunStatistics from orchestrator results.
    
    Args:
        run_name: Name for this run (e.g., "mag7", "sp25")
        results: Dict of {ticker: {metric: MappingResult}}
        knowledge_counts: Optional dict with universal/industry/company counts
    """
    from edgar.xbrl.standardization.models import MappingSource
    
    companies = list(results.keys())
    total = 0
    mapped = 0
    excluded = 0
    matched = 0
    trusted = 0
    discrepancy = 0
    
    for ticker, metrics in results.items():
        for metric, result in metrics.items():
            if result.source == MappingSource.CONFIG:
                excluded += 1
                continue
            
            total += 1
            if result.is_mapped:
                mapped += 1
                
                if result.validation_status == "valid":
                    matched += 1
                elif result.validation_status == "trusted":
                    trusted += 1
    
    # Load discrepancy count
    disc_file = Path(__file__).parent.parent / "company_mappings" / "discrepancies.json"
    disc_count = 0
    if disc_file.exists():
        with open(disc_file, 'r') as f:
            disc_data = json.load(f)
            disc_count = disc_data.get("statistics", {}).get("total", 0)
    
    raw_coverage = mapped / total * 100 if total > 0 else 0
    adjusted_total = total  # Already excludes CONFIG
    adjusted_coverage = mapped / adjusted_total * 100 if adjusted_total > 0 else 0
    
    kc = knowledge_counts or {"universal": 27, "industry": 4, "company": 2}
    
    return RunStatistics(
        run_id=f"{run_name}-{datetime.now().strftime('%Y%m%d')}",
        timestamp=datetime.now().isoformat(),
        companies=companies,
        company_count=len(companies),
        total_metrics=total + excluded,
        mapped_metrics=mapped,
        excluded_metrics=excluded,
        raw_coverage_pct=round(raw_coverage, 1),
        adjusted_coverage_pct=round(adjusted_coverage, 1),
        matched_count=matched,
        trusted_count=trusted,
        discrepancy_count=discrepancy,
        universal_concepts=kc.get("universal", 0),
        industry_rules=kc.get("industry", 0),
        company_specific_rules=kc.get("company", 0),
        documented_discrepancies=disc_count,
        new_concepts=[],
        new_discrepancies=[]
    )


def snapshot_pipeline_kpis(ledger, run_name: str, tickers: List[str]) -> Optional[str]:
    """Auto-snapshot KPI metrics after a pipeline batch run.

    Reads per-metric success rates from the ledger's extraction_runs table.
    Falls back to parsing onboarding JSON reports if extraction_runs is empty.

    Args:
        ledger: ExperimentLedger instance.
        run_name: Identifier for this run (e.g., batch_id).
        tickers: List of tickers processed in this batch.

    Returns:
        The run_id that was logged, or None on failure.
    """
    total_metrics = 0
    mapped_metrics = 0
    matched_count = 0
    excluded_count = 0

    # Try extraction_runs first
    has_runs = False
    for ticker in tickers:
        summary = ledger.get_ticker_summary(ticker)
        metrics = summary.get('metrics', {})
        if metrics:
            has_runs = True
            for metric, data in metrics.items():
                total_metrics += data['runs']
                mapped_metrics += data['valid']
                matched_count += data['valid']

    # Fallback: parse onboarding reports
    if not has_runs:
        report_dir = Path(__file__).parent.parent / "config" / "onboarding_reports"
        if report_dir.exists():
            for ticker in tickers:
                report_path = report_dir / f"{ticker}_report.json"
                if report_path.exists():
                    try:
                        with open(report_path) as f:
                            report = json.load(f)
                        passed = len(report.get('metrics_passed', []))
                        failed = len(report.get('metrics_failed', []))
                        excl = len(report.get('metrics_excluded', []))
                        total_metrics += passed + failed
                        mapped_metrics += passed
                        matched_count += passed
                        excluded_count += excl
                    except Exception:
                        pass

    if total_metrics == 0:
        return None

    raw_coverage = mapped_metrics / total_metrics * 100 if total_metrics > 0 else 0
    adjusted_coverage = raw_coverage  # Already excludes CONFIG

    stats = RunStatistics(
        run_id=f"pipeline-{run_name}",
        timestamp=datetime.now().isoformat(),
        companies=tickers,
        company_count=len(tickers),
        total_metrics=total_metrics + excluded_count,
        mapped_metrics=mapped_metrics,
        excluded_metrics=excluded_count,
        raw_coverage_pct=round(raw_coverage, 1),
        adjusted_coverage_pct=round(adjusted_coverage, 1),
        matched_count=matched_count,
        trusted_count=0,
        discrepancy_count=0,
        universal_concepts=0,
        industry_rules=0,
        company_specific_rules=0,
        documented_discrepancies=0,
        new_concepts=[],
        new_discrepancies=[],
    )

    return log_run(stats)


def get_progression() -> List[Dict]:
    """Get progression of metrics over all runs."""
    data = load_runs_history()
    return data["runs"]


def get_latest_run() -> Optional[Dict]:
    """Get the most recent run statistics."""
    data = load_runs_history()
    if data["runs"]:
        return data["runs"][-1]
    return None


def print_run_report(stats: RunStatistics):
    """Print a formatted run report."""
    print("=" * 60)
    print(f"RUN REPORT: {stats.run_id}")
    print("=" * 60)
    print()
    print("COVERAGE:")
    print(f"  Companies:    {stats.company_count}")
    print(f"  Raw:          {stats.mapped_metrics}/{stats.total_metrics} ({stats.raw_coverage_pct}%)")
    print(f"  Adjusted:     {stats.mapped_metrics}/{stats.total_metrics - stats.excluded_metrics} ({stats.adjusted_coverage_pct}%)")
    print()
    print("VALIDATION:")
    print(f"  Matched:      {stats.matched_count}")
    print(f"  Trusted:      {stats.trusted_count}")
    print(f"  Discrepancy:  {stats.discrepancy_count}")
    print()
    print("KNOWLEDGE BASE:")
    print(f"  Universal:    {stats.universal_concepts}")
    print(f"  Industry:     {stats.industry_rules}")
    print(f"  Company:      {stats.company_specific_rules}")
    print(f"  Documented:   {stats.documented_discrepancies}")
    print("=" * 60)


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="KPI Tracker")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Show command
    subparsers.add_parser("show", help="Show latest run")
    
    # History command
    history_parser = subparsers.add_parser("history", help="Show run history")
    history_parser.add_argument("-n", type=int, default=5, help="Number of runs to show")
    
    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two runs")
    compare_parser.add_argument("run1", help="First run ID")
    compare_parser.add_argument("run2", help="Second run ID")
    
    args = parser.parse_args()
    
    if args.command == "show":
        latest = get_latest_run()
        if latest:
            stats = RunStatistics(**latest)
            print_run_report(stats)
        else:
            print("No runs recorded yet")
    
    elif args.command == "history":
        runs = get_progression()
        print(f"Last {args.n} runs:")
        for run in runs[-args.n:]:
            print(f"  {run['run_id']}: {run['adjusted_coverage_pct']}% ({run['company_count']} companies)")
    
    elif args.command == "compare":
        runs = get_progression()
        run1 = next((r for r in runs if r["run_id"] == args.run1), None)
        run2 = next((r for r in runs if r["run_id"] == args.run2), None)
        
        if run1 and run2:
            print(f"Coverage: {run1['adjusted_coverage_pct']}% → {run2['adjusted_coverage_pct']}%")
            print(f"Universal: {run1['universal_concepts']} → {run2['universal_concepts']}")
        else:
            print("Run(s) not found")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
