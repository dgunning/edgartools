#!/usr/bin/env python3
"""
Standard Industrial E2E Test Runner

Validates XBRL concept mappings for 30 major industrial companies against yfinance.
Organized by sector: MAG7, Industrial Manufacturing, Consumer Staples, Energy, Healthcare/Pharma, Transportation
Defaults: 2 years, 2 quarters
"""

import argparse
import json
import os
import yaml
from datetime import datetime
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Dict, List, Any, Optional

# 33-Company Industrial Test List
INDUSTRIAL_33 = [
    # MAG7
    'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'NVDA', 'TSLA',
    # Industrial Manufacturing
    'CAT', 'GE', 'HON', 'DE', 'MMM', 'EMR', 'RTX', 'ASTE',
    # Consumer Staples
    'PG', 'KO', 'PEP', 'WMT', 'COST', 'HSY',
    # Energy
    'XOM', 'CVX', 'COP', 'SLB', 'PBF',
    # Healthcare/Pharma
    'JNJ', 'UNH', 'LLY', 'PFE',
    # Transportation
    'UPS', 'FDX', 'BA'
]

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

# Target metrics to validate
TARGET_METRICS = [
    'Revenue', 'COGS', 'SGA', 'OperatingIncome', 'PretaxIncome', 'NetIncome',
    'OperatingCashFlow', 'Capex', 'TotalAssets', 'Goodwill', 'IntangibleAssets',
    'ShortTermDebt', 'LongTermDebt', 'CashAndEquivalents',
    # Derived
    'FreeCashFlow', 'TangibleAssets', 'NetDebt'
]


def load_known_divergences() -> Dict[str, Dict]:
    """Load known_divergences from companies.yaml config."""
    config_path = Path(__file__).resolve().parents[4] / "edgar/xbrl/standardization/config/companies.yaml"
    if not config_path.exists():
        return {}

    with open(config_path) as f:
        config = yaml.safe_load(f)

    divergences = {}
    companies = config.get("companies", {})
    for ticker, company_config in companies.items():
        known_div = company_config.get("known_divergences", {})
        if known_div:
            divergences[ticker] = known_div
    return divergences


def should_skip_validation(ticker: str, metric: str, form_type: str, known_divergences: Dict) -> tuple:
    """
    Check if validation should be skipped for this (ticker, metric, form_type).
    Returns (skip: bool, reason: str or None).
    """
    ticker_divs = known_divergences.get(ticker, {})
    metric_div = ticker_divs.get(metric, {})

    if not metric_div:
        return False, None

    form_types = metric_div.get("form_types", [])
    skip_validation = metric_div.get("skip_validation", False)

    if form_type in form_types and skip_validation:
        reason = metric_div.get("reason", "Known divergence documented in companies.yaml")
        return True, reason

    return False, None


# Suggested action patterns for industrial companies
SUGGESTED_ACTIONS = {
    "composite_high_variance": "Review COMPOSITE_METRICS in reference_validator.py for this sector",
    "capex_concept": "Check PaymentsToAcquireProductiveAssets vs PaymentsToAcquirePropertyPlantAndEquipment",
    "lease_accounting": "Review operating vs finance lease classification for Assets/Liabilities",
    "rnd_capitalization": "Check ResearchAndDevelopmentInProcess vs expensed R&D concepts",
    "alternative_available": "Consider adding {} to known_concepts in metrics.yaml",
    "dimension_issue": "Check dimensional filtering - possible segment mismatch",
    "missing_mapping": "Add concept to metrics.yaml known_concepts",
}


def get_suggested_actions(failure: Dict) -> List[str]:
    """Generate suggested actions based on failure patterns."""
    actions = []

    variance = failure.get("variance_pct", 0)
    sector = failure.get("sector", "")
    metric = failure.get("metric", "")
    alternatives = failure.get("alternative_concepts", [])
    mapping_source = failure.get("mapping_source", "")

    # High variance composite
    if variance > 50 and mapping_source == "composite":
        actions.append(SUGGESTED_ACTIONS["composite_high_variance"])

    # Capex issues in Energy sector
    if metric == "Capex" and sector == "Energy":
        actions.append(SUGGESTED_ACTIONS["capex_concept"])

    # Lease-related metrics in Retail
    if sector == "Consumer_Staples" and metric in ["TotalAssets", "TotalLiabilities"]:
        actions.append(SUGGESTED_ACTIONS["lease_accounting"])

    # R&D issues in Pharma
    if sector == "Healthcare_Pharma" and "RD" in metric:
        actions.append(SUGGESTED_ACTIONS["rnd_capitalization"])

    # Alternative concepts available
    if alternatives:
        actions.append(SUGGESTED_ACTIONS["alternative_available"].format(alternatives[0]))

    # No mapping found
    if not mapping_source or mapping_source == "none":
        actions.append(SUGGESTED_ACTIONS["missing_mapping"])

    return actions if actions else ["Manual investigation required"]


def process_company(args: tuple) -> Dict[str, Any]:
    """
    Worker function: Process a single company.
    Returns dict with stats and failures.
    """
    worker_config = args  # rename for clarity
    ticker = worker_config["ticker"]
    target_metrics = worker_config.get("metrics")
    known_divergences = worker_config.get("known_divergences", {})

    # Import here to avoid multiprocessing pickle issues
    from edgar import set_identity, use_local_storage, Company
    from edgar.xbrl.standardization.orchestrator import Orchestrator
    from edgar.entity.mappings_loader import get_industry_for_sic

    set_identity("E2E Test Runner e2e@test.local")
    use_local_storage(True)

    sector = TICKER_TO_SECTOR.get(ticker, "Unknown")

    result = {
        "ticker": ticker,
        "sector": sector,
        "10k_stats": {"total": 0, "passed": 0, "failed": 0, "no_ref": 0, "skipped": 0},
        "10q_stats": {"total": 0, "passed": 0, "failed": 0, "no_ref": 0, "skipped": 0},
        "failures": [],
        "skipped": []
    }

    try:
        company = Company(ticker)
        orchestrator = Orchestrator()

        # Get industry
        try:
            sic = company.data.sic
            industry = get_industry_for_sic(sic) if sic else None
        except:
            industry = None

        # Process 10-K filings
        filings_10k = company.get_filings(form='10-K').latest(worker_config["years"])
        if filings_10k is not None and not hasattr(filings_10k, '__iter__'):
            filings_10k = [filings_10k]
        if not filings_10k:
            print(f"DEBUG {ticker}: No 10-K filings found (years={worker_config['years']})")
            filings_10k = []
        else:
            print(f"DEBUG {ticker} [{sector}]: Found {len(filings_10k)} 10-Ks (Industry: {industry})")

        for filing in filings_10k:
            try:
                period_date = filing.period_of_report
                xbrl = filing.xbrl()
                if not xbrl:
                    continue

                results = orchestrator.tree_parser.map_company(ticker, filing)
                validations = orchestrator.validator.validate_and_update_mappings(
                    ticker, results, xbrl, filing_date=period_date, form_type='10-K'
                )

                for metric, v in validations.items():
                    print(f"DEBUG {ticker} 10-K {metric}: {v.status} (Ref: {v.reference_value})")
                    # Filter by target metrics if specified
                    if target_metrics and metric not in target_metrics:
                        continue

                    if v.status == 'match':
                        result["10k_stats"]["passed"] += 1
                        result["10k_stats"]["total"] += 1
                    elif v.status == 'mismatch':
                        # Check if this is a known divergence that should be skipped
                        skip, skip_reason = should_skip_validation(ticker, metric, "10-K", known_divergences)
                        if skip:
                            result["10k_stats"]["skipped"] += 1
                            result["skipped"].append({
                                "ticker": ticker,
                                "sector": sector,
                                "form": "10-K",
                                "metric": metric,
                                "variance_pct": round(v.variance_pct, 1) if v.variance_pct else None,
                                "reason": skip_reason
                            })
                            print(f"SKIPPED {ticker} 10-K {metric}: Known divergence - {skip_reason[:50]}...")
                            continue

                        result["10k_stats"]["failed"] += 1
                        result["10k_stats"]["total"] += 1

                        # Build detailed failure record
                        mapping_result = results.get(metric)
                        failure = {
                            "ticker": ticker,
                            "sector": sector,
                            "form": "10-K",
                            "filing_date": str(period_date),
                            "accession_no": filing.accession_no,
                            "metric": metric,
                            "xbrl_value": v.xbrl_value,
                            "ref_value": v.reference_value,
                            "variance_pct": round(v.variance_pct, 1) if v.variance_pct else None,
                            "mapping_source": mapping_result.source.value if mapping_result else None,
                            "concept_used": mapping_result.concept if mapping_result else None,
                            "industry": industry,
                            "alternative_concepts": [],  # TODO: populate from XBRL
                            "suggested_actions": []
                        }
                        failure["suggested_actions"] = get_suggested_actions(failure)
                        result["failures"].append(failure)
                    elif v.status == 'missing_ref':
                        result["10k_stats"]["no_ref"] += 1
            except Exception as e:
                import traceback
                print(f"ERROR processing {ticker} 10-K: {e}")
                traceback.print_exc()
                pass  # Skip individual filing errors

        # Process 10-Q filings
        filings_10q = company.get_filings(form='10-Q').latest(worker_config["quarters"])
        if filings_10q is not None and not hasattr(filings_10q, '__iter__'):
            filings_10q = [filings_10q]
        if not filings_10q:
            print(f"DEBUG {ticker}: No 10-Q filings found (quarters={worker_config['quarters']})")
            filings_10q = []
        else:
             print(f"DEBUG {ticker}: Found {len(filings_10q)} 10-Qs")

        for filing in filings_10q:
            try:
                period_date = filing.period_of_report
                xbrl = filing.xbrl()
                if not xbrl:
                    continue

                results = orchestrator.tree_parser.map_company(ticker, filing)

                # Switch to quarterly yfinance
                original_map = orchestrator.validator.YFINANCE_MAP.copy()
                quarterly_map = {
                    k: (v[0].replace('financials', 'quarterly_financials')
                           .replace('balance_sheet', 'quarterly_balance_sheet')
                           .replace('cashflow', 'quarterly_cashflow'), v[1])
                    for k, v in original_map.items()
                }
                orchestrator.validator.YFINANCE_MAP = quarterly_map

                validations = orchestrator.validator.validate_and_update_mappings(
                    ticker, results, xbrl, filing_date=period_date, form_type='10-Q'
                )
                orchestrator.validator.YFINANCE_MAP = original_map

                for metric, v in validations.items():
                    # Filter by target metrics if specified
                    if target_metrics and metric not in target_metrics:
                        continue

                    if v.status == 'match':
                        result["10q_stats"]["passed"] += 1
                        result["10q_stats"]["total"] += 1
                    elif v.status == 'mismatch':
                        # Check if this is a known divergence that should be skipped
                        skip, skip_reason = should_skip_validation(ticker, metric, "10-Q", known_divergences)
                        if skip:
                            result["10q_stats"]["skipped"] += 1
                            result["skipped"].append({
                                "ticker": ticker,
                                "sector": sector,
                                "form": "10-Q",
                                "metric": metric,
                                "variance_pct": round(v.variance_pct, 1) if v.variance_pct else None,
                                "reason": skip_reason
                            })
                            print(f"SKIPPED {ticker} 10-Q {metric}: Known divergence")
                            continue

                        result["10q_stats"]["failed"] += 1
                        result["10q_stats"]["total"] += 1

                        mapping_result = results.get(metric)
                        failure = {
                            "ticker": ticker,
                            "sector": sector,
                            "form": "10-Q",
                            "filing_date": str(period_date),
                            "accession_no": filing.accession_no,
                            "metric": metric,
                            "xbrl_value": v.xbrl_value,
                            "ref_value": v.reference_value,
                            "variance_pct": round(v.variance_pct, 1) if v.variance_pct else None,
                            "mapping_source": mapping_result.source.value if mapping_result else None,
                            "concept_used": mapping_result.concept if mapping_result else None,
                            "industry": industry,
                            "alternative_concepts": [],
                            "suggested_actions": []
                        }
                        failure["suggested_actions"] = get_suggested_actions(failure)
                        result["failures"].append(failure)
                    elif v.status == 'missing_ref':
                        result["10q_stats"]["no_ref"] += 1
            except Exception as e:
                import traceback
                print(f"ERROR processing {ticker} 10-Q: {e}")
                traceback.print_exc()
                pass

    except Exception as e:
        import traceback
        print(f"ERROR processing {ticker}: {e}")
        traceback.print_exc()
        result["error"] = str(e)

    return result


def write_json_report(results: List[Dict], output_path: Path, config: Dict):
    """Write detailed JSON report with sector breakdowns."""
    all_failures = []
    all_skipped = []
    all_errors = []

    # Initialize sector summaries
    sector_summary = {}
    for sector in SECTOR_GROUPS.keys():
        sector_summary[sector] = {
            "10k_total": 0, "10k_passed": 0, "10k_skipped": 0,
            "10q_total": 0, "10q_passed": 0, "10q_skipped": 0
        }

    # Overall summary
    overall_summary = {
        "10k_total": 0, "10k_passed": 0, "10k_skipped": 0,
        "10q_total": 0, "10q_passed": 0, "10q_skipped": 0
    }

    for r in results:
        all_failures.extend(r["failures"])
        all_skipped.extend(r.get("skipped", []))
        if "error" in r:
            all_errors.append({"ticker": r["ticker"], "sector": r["sector"], "error": r["error"]})

        sector = r.get("sector", "Unknown")
        if sector in sector_summary:
            # Aggregate by sector
            sector_summary[sector]["10k_total"] += r["10k_stats"]["total"]
            sector_summary[sector]["10k_passed"] += r["10k_stats"]["passed"]
            sector_summary[sector]["10k_skipped"] += r["10k_stats"].get("skipped", 0)
            sector_summary[sector]["10q_total"] += r["10q_stats"]["total"]
            sector_summary[sector]["10q_passed"] += r["10q_stats"]["passed"]
            sector_summary[sector]["10q_skipped"] += r["10q_stats"].get("skipped", 0)

        # Overall
        overall_summary["10k_total"] += r["10k_stats"]["total"]
        overall_summary["10k_passed"] += r["10k_stats"]["passed"]
        overall_summary["10k_skipped"] += r["10k_stats"].get("skipped", 0)
        overall_summary["10q_total"] += r["10q_stats"]["total"]
        overall_summary["10q_passed"] += r["10q_stats"]["passed"]
        overall_summary["10q_skipped"] += r["10q_stats"].get("skipped", 0)

    # Remove known_divergences from config before serializing (too verbose)
    config_for_report = {k: v for k, v in config.items() if k != "known_divergences"}

    report = {
        "run_id": f"e2e_industrial_{datetime.now().isoformat()}",
        "timestamp": datetime.now().isoformat(),
        "config": config_for_report,
        "overall_summary": overall_summary,
        "sector_summary": sector_summary,
        "failure_count": len(all_failures),
        "skipped_count": len(all_skipped),
        "error_count": len(all_errors),
        "failures": all_failures,
        "skipped": all_skipped,
        "errors": all_errors
    }

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    return overall_summary, sector_summary, all_skipped


def write_markdown_report(overall_summary: Dict, sector_summary: Dict, failures: List[Dict],
                          skipped: List[Dict], output_path: Path, config: Dict):
    """Write markdown summary report with sector breakdowns."""
    lines = [
        f"# Standard Industrial E2E Test - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"**Config:** Companies={len(config['tickers'])}, Workers={config['workers']}, "
        f"Years={config['years']}, Quarters={config['quarters']}",
    ]

    if config.get("sector"):
        lines.append("")
        lines.append(f"**Sector Filter:** {config['sector']}")

    if config.get("metrics"):
        lines.append("")
        lines.append(f"**Metrics:** {', '.join(config['metrics'])}")

    # Overall pass rates
    lines.extend([
        "",
        "## Overall Pass Rates",
        "",
    ])

    s = overall_summary
    k_rate = f"{s['10k_passed']/s['10k_total']*100:.1f}%" if s['10k_total'] > 0 else "N/A"
    q_rate = f"{s['10q_passed']/s['10q_total']*100:.1f}%" if s['10q_total'] > 0 else "N/A"
    k_skip = f" (+{s.get('10k_skipped', 0)} skipped)" if s.get('10k_skipped', 0) > 0 else ""
    q_skip = f" (+{s.get('10q_skipped', 0)} skipped)" if s.get('10q_skipped', 0) > 0 else ""

    lines.extend([
        f"- **10-K**: {k_rate} ({s['10k_passed']}/{s['10k_total']}){k_skip}",
        f"- **10-Q**: {q_rate} ({s['10q_passed']}/{s['10q_total']}){q_skip}",
    ])

    # Sector-level pass rates
    lines.extend([
        "",
        "## Pass Rates by Sector",
        "",
        "| Sector | 10-K | 10-Q |",
        "|--------|------|------|",
    ])

    for sector in SECTOR_GROUPS.keys():
        ss = sector_summary.get(sector, {})
        if ss.get('10k_total', 0) > 0 or ss.get('10q_total', 0) > 0:
            k_rate = f"{ss['10k_passed']/ss['10k_total']*100:.1f}%" if ss['10k_total'] > 0 else "N/A"
            q_rate = f"{ss['10q_passed']/ss['10q_total']*100:.1f}%" if ss['10q_total'] > 0 else "N/A"
            k_skip = f" (+{ss.get('10k_skipped', 0)})" if ss.get('10k_skipped', 0) > 0 else ""
            q_skip = f" (+{ss.get('10q_skipped', 0)})" if ss.get('10q_skipped', 0) > 0 else ""
            lines.append(f"| **{sector}** | {k_rate} ({ss['10k_passed']}/{ss['10k_total']}){k_skip} | {q_rate} ({ss['10q_passed']}/{ss['10q_total']}){q_skip} |")

    # Known divergences section (if any were skipped)
    if skipped:
        lines.extend([
            "",
            "## Known Divergences (Skipped)",
            "",
            "| Ticker | Sector | Form | Metric | Variance | Reason |",
            "|--------|--------|------|--------|----------|--------|",
        ])
        for sk in skipped:
            reason = sk.get("reason", "")[:40] + "..." if len(sk.get("reason", "")) > 40 else sk.get("reason", "")
            lines.append(f"| {sk['ticker']} | {sk.get('sector', 'N/A')} | {sk['form']} | {sk['metric']} | {sk.get('variance_pct', 'N/A')}% | {reason} |")

    # Top failing metrics
    from collections import Counter
    metric_counts = Counter(f["metric"] for f in failures)
    lines.extend([
        "",
        "## Top Failing Metrics",
        "",
        "| Metric | Failures |",
        "|--------|----------|",
    ])
    for metric, count in metric_counts.most_common(10):
        lines.append(f"| {metric} | {count} |")

    # Failures by sector
    sector_counts = Counter(f.get("sector", "Unknown") for f in failures)
    lines.extend([
        "",
        "## Failures by Sector",
        "",
        "| Sector | Failures |",
        "|--------|----------|",
    ])
    for sector, count in sector_counts.most_common():
        lines.append(f"| {sector} | {count} |")

    # Top failing companies
    ticker_counts = Counter(f["ticker"] for f in failures)
    lines.extend([
        "",
        "## Top Failing Companies",
        "",
        "| Ticker | Sector | Failures |",
        "|--------|--------|----------|",
    ])
    for ticker, count in ticker_counts.most_common(10):
        sector = TICKER_TO_SECTOR.get(ticker, "Unknown")
        lines.append(f"| {ticker} | {sector} | {count} |")

    lines.extend([
        "",
        f"*See JSON report for full failure details ({len(failures)} total failures)*"
    ])

    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description="Standard Industrial E2E Test")
    parser.add_argument("--workers", type=int, default=8,
                        help="Number of parallel workers")
    parser.add_argument("--metrics", type=str, metavar="METRICS",
                        help="Comma-separated list of metrics to test")
    parser.add_argument("--sector", type=str, metavar="SECTOR",
                        help="Run only for specific sector (MAG7, Industrial_Manufacturing, etc.)")
    parser.add_argument("--tickers", type=str, metavar="TICKERS",
                        help="Comma-separated list of specific tickers to test")
    parser.add_argument("--years", type=int, default=2,
                        help="Number of 10-K years to test (default: 2)")
    parser.add_argument("--quarters", type=int, default=2,
                        help="Number of 10-Q quarters to test (default: 2)")
    args = parser.parse_args()

    # Determine which tickers to test
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
    elif args.sector:
        if args.sector not in SECTOR_GROUPS:
            print(f"Unknown sector: {args.sector}")
            print(f"Available sectors: {', '.join(SECTOR_GROUPS.keys())}")
            return
        tickers = SECTOR_GROUPS[args.sector]
    else:
        tickers = INDUSTRIAL_33

    # Cap workers
    max_workers = min(args.workers, cpu_count(), 8)

    # Load known divergences from companies.yaml
    known_divergences = load_known_divergences()

    # Use TARGET_METRICS as default, or user-specified metrics if provided
    metrics_to_test = [m.strip() for m in args.metrics.split(',')] if args.metrics else TARGET_METRICS

    config = {
        "group": "industrial_33",
        "workers": max_workers,
        "years": args.years,
        "quarters": args.quarters,
        "metrics": metrics_to_test,
        "sector": args.sector,
        "tickers": tickers
    }

    print(f"="*60)
    print(f"E2E TEST: STANDARD INDUSTRIAL ({len(tickers)} companies)")
    if args.sector:
        print(f"Sector: {args.sector}")
    print(f"Includes: {', '.join(tickers[:10])}{'...' if len(tickers) > 10 else ''}")
    if args.metrics:
        print(f"Metrics (custom): {metrics_to_test}")
    else:
        print(f"Metrics ({len(TARGET_METRICS)} target): {', '.join(TARGET_METRICS[:5])}...")
    print(f"Workers: {max_workers}, Years: {args.years}, Quarters: {args.quarters}")

    # Report known divergences that will be skipped
    skip_count = sum(
        1 for t in tickers if t in known_divergences
        for m in known_divergences.get(t, {})
        if known_divergences[t][m].get("skip_validation", False)
    )
    if skip_count > 0:
        print(f"Known divergences to skip: {skip_count}")
    print(f"="*60)

    # Run parallel processing
    work_items = []
    for ticker in tickers:
        item = config.copy()
        item["ticker"] = ticker
        item["known_divergences"] = known_divergences
        work_items.append(item)

    print(f"\nProcessing {len(tickers)} companies with {max_workers} workers...")
    with Pool(processes=max_workers) as pool:
        results = pool.map(process_company, work_items)

    # Aggregate all failures
    all_failures = []
    for r in results:
        all_failures.extend(r["failures"])

    # Write reports to specific directory
    project_root = Path(__file__).resolve().parents[4]
    script_dir = project_root / "sandbox/notes/010_standard_industrial/reports"
    script_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H%M")
    filename_base = f"e2e_industrial_{date_str}_{time_str}"

    json_path = script_dir / f"{filename_base}.json"
    md_path = script_dir / f"{filename_base}.md"

    overall_summary, sector_summary, all_skipped = write_json_report(results, json_path, config)
    write_markdown_report(overall_summary, sector_summary, all_failures, all_skipped, md_path, config)

    # Print summary
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")

    # Overall
    s = overall_summary
    k_rate = f"{s['10k_passed']/s['10k_total']*100:.1f}%" if s['10k_total'] > 0 else "N/A"
    q_rate = f"{s['10q_passed']/s['10q_total']*100:.1f}%" if s['10q_total'] > 0 else "N/A"
    k_skip = f" (+{s.get('10k_skipped', 0)} skipped)" if s.get('10k_skipped', 0) > 0 else ""
    q_skip = f" (+{s.get('10q_skipped', 0)} skipped)" if s.get('10q_skipped', 0) > 0 else ""
    print(f"OVERALL: 10-K {k_rate} ({s['10k_passed']}/{s['10k_total']}){k_skip}, 10-Q {q_rate} ({s['10q_passed']}/{s['10q_total']}){q_skip}")

    print(f"\nBy Sector:")
    for sector in SECTOR_GROUPS.keys():
        ss = sector_summary.get(sector, {})
        if ss.get('10k_total', 0) > 0 or ss.get('10q_total', 0) > 0:
            k_rate = f"{ss['10k_passed']/ss['10k_total']*100:.1f}%" if ss['10k_total'] > 0 else "N/A"
            q_rate = f"{ss['10q_passed']/ss['10q_total']*100:.1f}%" if ss['10q_total'] > 0 else "N/A"
            print(f"  {sector}: 10-K {k_rate}, 10-Q {q_rate}")

    print(f"\nTotal failures: {len(all_failures)}")
    if all_skipped:
        print(f"Known divergences skipped: {len(all_skipped)}")
    print(f"Reports written to: {script_dir}")
    print(f"  - {json_path.name}")
    print(f"  - {md_path.name}")


if __name__ == "__main__":
    main()
