#!/usr/bin/env python
"""
Analyze E2E test failures from JSON report for Standard Industrial tests.

Usage:
    python analyze_failures.py [report_path]

    If no report path is provided, uses the most recent report in the default directory.

Examples:
    # Analyze most recent report
    python analyze_failures.py

    # Analyze specific report
    python analyze_failures.py sandbox/notes/010_standard_industrial/reports/e2e_industrial_2026-01-25_1430.json
"""

import json
import sys
from pathlib import Path

# Sector groupings for reporting
SECTOR_GROUPS = {
    'MAG7': ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'NVDA', 'TSLA'],
    'Industrial_Manufacturing': ['CAT', 'GE', 'HON', 'DE', 'MMM', 'EMR', 'RTX', 'ASTE'],
    'Consumer_Staples': ['PG', 'KO', 'PEP', 'WMT', 'COST', 'HSY'],
    'Energy': ['XOM', 'CVX', 'COP', 'SLB', 'PBF'],
    'Healthcare_Pharma': ['JNJ', 'UNH', 'LLY', 'PFE'],
    'Transportation': ['UPS', 'FDX', 'BA']
}

# Reverse lookup: ticker -> sector
TICKER_TO_SECTOR = {
    ticker: sector
    for sector, tickers in SECTOR_GROUPS.items()
    for ticker in tickers
}


def find_latest_report(reports_dir: Path) -> Path | None:
    """Find the most recent JSON report in the directory."""
    json_files = list(reports_dir.glob("e2e_industrial_*.json"))
    if not json_files:
        return None
    return max(json_files, key=lambda f: f.stat().st_mtime)


def calculate_variance(xbrl_value: float, ref_value: float) -> float:
    """Calculate variance percentage."""
    if ref_value == 0:
        return float('inf') if xbrl_value != 0 else 0.0
    return abs(xbrl_value - ref_value) / abs(ref_value) * 100


def format_value(value: float) -> str:
    """Format value in billions."""
    if value is None:
        return "N/A"
    return f"{value / 1e9:.1f}B"


def analyze_report(report_path: Path) -> None:
    """Analyze and print failures from the report."""
    with open(report_path) as f:
        data = json.load(f)

    failures = data.get('failures', [])
    sector_summary = data.get('sector_summary', {})
    overall_summary = data.get('overall_summary', {})

    print(f"Report: {report_path.name}")
    print(f"Total failures: {len(failures)}")
    print()

    # Print sector pass rates
    if sector_summary:
        print(f"{'=' * 60}")
        print("Pass Rates by Sector")
        print(f"{'=' * 60}")

        for sector in SECTOR_GROUPS.keys():
            ss = sector_summary.get(sector, {})
            if ss.get('10k_total', 0) > 0 or ss.get('10q_total', 0) > 0:
                k_rate = f"{ss['10k_passed']/ss['10k_total']*100:.1f}%" if ss['10k_total'] > 0 else "N/A"
                q_rate = f"{ss['10q_passed']/ss['10q_total']*100:.1f}%" if ss['10q_total'] > 0 else "N/A"
                print(f"  {sector:25} 10-K {k_rate:>6} ({ss['10k_passed']}/{ss['10k_total']}) | "
                      f"10-Q {q_rate:>6} ({ss['10q_passed']}/{ss['10q_total']})")

        print()

    if not failures:
        print("No failures found in report.")
        return

    # Group failures by metric
    by_metric: dict[str, list] = {}
    for f in failures:
        metric = f.get('metric', 'Unknown')
        if metric not in by_metric:
            by_metric[metric] = []
        by_metric[metric].append(f)

    # Print failures by metric
    for metric, metric_failures in sorted(by_metric.items()):
        print(f"{'=' * 60}")
        print(f"{metric} Failures ({len(metric_failures)})")
        print(f"{'=' * 60}")

        # Sort by variance (descending)
        sorted_failures = sorted(
            metric_failures,
            key=lambda x: x.get('variance_pct', calculate_variance(
                x.get('xbrl_value', 0), x.get('ref_value', 0)
            )),
            reverse=True
        )

        for f in sorted_failures:
            ticker = f.get('ticker', 'Unknown')
            form = f.get('form', 'Unknown')
            sector = f.get('sector', TICKER_TO_SECTOR.get(ticker, 'Unknown'))
            xbrl_val = f.get('xbrl_value', 0) or 0
            ref_val = f.get('ref_value', 0) or 0

            # Use variance_pct from report, or calculate if missing
            variance = f.get('variance_pct')
            if variance is None or variance == 0:
                variance = calculate_variance(xbrl_val, ref_val)

            # Determine over/under extraction
            if xbrl_val > ref_val:
                direction = "OVER"
            elif xbrl_val < ref_val:
                direction = "UNDER"
            else:
                direction = "MATCH"

            print(f"  {ticker:5} [{sector[:12]:12}] ({form:4}): XBRL={format_value(xbrl_val):>8}, "
                  f"Ref={format_value(ref_val):>8}, Variance={variance:>6.1f}% [{direction}]")

        print()

    # Summary by sector
    print(f"{'=' * 60}")
    print("Failures by Sector")
    print(f"{'=' * 60}")

    by_sector: dict[str, int] = {}
    for f in failures:
        sector = f.get('sector', TICKER_TO_SECTOR.get(f.get('ticker', ''), 'Unknown'))
        by_sector[sector] = by_sector.get(sector, 0) + 1

    for sector, count in sorted(by_sector.items(), key=lambda x: -x[1]):
        suffix = "failure" if count == 1 else "failures"
        print(f"  {sector}: {count} {suffix}")

    print()

    # Summary by company
    print(f"{'=' * 60}")
    print("Failures by Company")
    print(f"{'=' * 60}")

    by_company: dict[str, int] = {}
    for f in failures:
        ticker = f.get('ticker', 'Unknown')
        by_company[ticker] = by_company.get(ticker, 0) + 1

    for ticker, count in sorted(by_company.items(), key=lambda x: -x[1]):
        sector = TICKER_TO_SECTOR.get(ticker, 'Unknown')
        suffix = "failure" if count == 1 else "failures"
        print(f"  {ticker} [{sector}]: {count} {suffix}")


def main():
    # Determine report path
    if len(sys.argv) > 1:
        report_path = Path(sys.argv[1])
    else:
        # Find default reports directory
        script_dir = Path(__file__).parent
        project_root = script_dir.parents[3]  # .claude/skills/standard-industrial-test/scripts -> project root
        reports_dir = project_root / "sandbox" / "notes" / "010_standard_industrial" / "reports"

        if not reports_dir.exists():
            print(f"Reports directory not found: {reports_dir}")
            sys.exit(1)

        report_path = find_latest_report(reports_dir)
        if report_path is None:
            print(f"No E2E reports found in: {reports_dir}")
            sys.exit(1)

    if not report_path.exists():
        print(f"Report not found: {report_path}")
        sys.exit(1)

    analyze_report(report_path)


if __name__ == "__main__":
    main()
