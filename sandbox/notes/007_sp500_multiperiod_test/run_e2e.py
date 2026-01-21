#!/usr/bin/env python3
"""
S&P500 Multi-Period E2E Test Runner

Parallel validation of XBRL concept mappings against yfinance.
Outputs detailed JSON logs and markdown summaries for debugging.

Usage:
    python run_e2e.py --group sp25 --workers 4
    python run_e2e.py --group sp50 --workers 8 --years 3 --quarters 4
"""

import argparse
import json
import os
from datetime import datetime
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Dict, List, Any, Optional

# S&P25 and S&P50 Company Lists
SP25 = [
    "AAPL", "MSFT", "GOOG", "AMZN", "NVDA", "META", "TSLA",
    "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "AXP", "BLK", "C",
    "UNH", "JNJ", "LLY", "PFE", "MRK", "ABBV", "TMO", "DHR"
]

SP50 = SP25 + [
    "ABT", "WMT", "PG", "KO", "PEP", "COST", "MCD", "DIS", "NKE", "SBUX",
    "XOM", "CVX", "CAT", "GE", "RTX", "HON", "UPS", "BA",
    "CRM", "ORCL", "ADBE", "NFLX", "CSCO", "ACN", "IBM"
]

# Suggested action patterns
SUGGESTED_ACTIONS = {
    "composite_high_variance": "Review COMPOSITE_METRICS in reference_validator.py for this industry",
    "banking_metric": "Check dual-track extraction logic in industry_logic/",
    "alternative_available": "Consider adding {} to known_concepts in metrics.yaml",
    "dimension_issue": "Check dimensional filtering - possible segment mismatch",
    "missing_mapping": "Add concept to metrics.yaml known_concepts",
}


def get_suggested_actions(failure: Dict) -> List[str]:
    """Generate suggested actions based on failure patterns."""
    actions = []
    
    variance = failure.get("variance_pct", 0)
    industry = failure.get("industry", "")
    alternatives = failure.get("alternative_concepts", [])
    mapping_source = failure.get("mapping_source", "")
    
    # High variance composite
    if variance > 50 and mapping_source == "composite":
        actions.append(SUGGESTED_ACTIONS["composite_high_variance"])
    
    # Banking industry
    if industry == "banking":
        actions.append(SUGGESTED_ACTIONS["banking_metric"])
    
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
    
    # Import here to avoid multiprocessing pickle issues
    from edgar import set_identity, use_local_storage, Company
    from edgar.xbrl.standardization.orchestrator import Orchestrator
    from edgar.entity.mappings_loader import get_industry_for_sic
    
    set_identity("E2E Test Runner e2e@test.local")
    use_local_storage(True)
    
    result = {
        "ticker": ticker,
        "10k_stats": {"total": 0, "passed": 0, "failed": 0, "no_ref": 0},
        "10q_stats": {"total": 0, "passed": 0, "failed": 0, "no_ref": 0},
        "failures": []
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
            print(f"DEBUG {ticker}: Found {len(filings_10k)} 10-Ks (Industry: {industry})")
            
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
                        result["10k_stats"]["failed"] += 1
                        result["10k_stats"]["total"] += 1
                        
                        # Build detailed failure record
                        mapping_result = results.get(metric)
                        failure = {
                            "ticker": ticker,
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
                        result["10q_stats"]["failed"] += 1
                        result["10q_stats"]["total"] += 1
                        
                        mapping_result = results.get(metric)
                        failure = {
                            "ticker": ticker,
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
            except Exception:
                pass
                
    except Exception as e:
        import traceback
        print(f"ERROR processing {ticker}: {e}")
        traceback.print_exc()
        result["error"] = str(e)
    
    return result


def write_json_report(results: List[Dict], output_path: Path, config: Dict):
    """Write detailed JSON report."""
    all_failures = []
    all_errors = []
    summary = {
        "sp25": {"10k_total": 0, "10k_passed": 0, "10q_total": 0, "10q_passed": 0},
        "sp50": {"10k_total": 0, "10k_passed": 0, "10q_total": 0, "10q_passed": 0},
        "custom": {"10k_total": 0, "10k_passed": 0, "10q_total": 0, "10q_passed": 0}
    }
    
    for r in results:
        all_failures.extend(r["failures"])
        if "error" in r:
            all_errors.append({"ticker": r["ticker"], "error": r["error"]})
        
        # Aggregate stats
        ticker = r["ticker"]
        in_sp25 = ticker in SP25
        in_sp50 = ticker in SP50
        
        # Always add to custom/total stats if it's a custom run
        if config["group"] == "custom" or (not in_sp25 and not in_sp50):
             summary["custom"]["10k_total"] += r["10k_stats"]["total"]
             summary["custom"]["10k_passed"] += r["10k_stats"]["passed"]
             summary["custom"]["10q_total"] += r["10q_stats"]["total"]
             summary["custom"]["10q_passed"] += r["10q_stats"]["passed"]

        # Also add to specific groups if applicable
        if in_sp25:
            summary["sp25"]["10k_total"] += r["10k_stats"]["total"]
            summary["sp25"]["10k_passed"] += r["10k_stats"]["passed"]
            summary["sp25"]["10q_total"] += r["10q_stats"]["total"]
            summary["sp25"]["10q_passed"] += r["10q_stats"]["passed"]
            
        if in_sp50:
            summary["sp50"]["10k_total"] += r["10k_stats"]["total"]
            summary["sp50"]["10k_passed"] += r["10k_stats"]["passed"]
            summary["sp50"]["10q_total"] += r["10q_stats"]["total"]
            summary["sp50"]["10q_passed"] += r["10q_stats"]["passed"]
    
    report = {
        "run_id": f"e2e_{datetime.now().isoformat()}",
        "timestamp": datetime.now().isoformat(),
        "config": config,
        "config": config,
        "summary": summary,
        "failure_count": len(all_failures),
        "error_count": len(all_errors),
        "failures": all_failures,
        "errors": all_errors
    }
    
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    return summary


def write_markdown_report(summary: Dict, failures: List[Dict], output_path: Path, config: Dict):
    """Write markdown summary report."""
    lines = [
        f"# E2E Test Results - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"**Config:** Group={config['group']}, Workers={config['workers']}, "
        f"Years={config['years']}, Quarters={config['quarters']}",
        "",
        "## Pass Rates",
        "",
        "| Group | 10-K | 10-Q |",
        "|-------|------|------|",
    ]
    
    # Determine which groups to show based on what was tested
    groups_to_show = ["sp25", "sp50"]
    if config["group"] == "custom":
        groups_to_show = ["custom"]
    elif config["group"] == "sp25":
        groups_to_show = ["sp25"]
    
    for key in groups_to_show:
        s = summary[key]
        if s['10k_total'] > 0 or s['10q_total'] > 0:
            k_rate = f"{s['10k_passed']/s['10k_total']*100:.1f}%" if s['10k_total'] > 0 else "N/A"
            q_rate = f"{s['10q_passed']/s['10q_total']*100:.1f}%" if s['10q_total'] > 0 else "N/A"
            label = "Custom/Selected" if key == "custom" else ("SP25" if key == "sp25" else "SP50")
            lines.append(f"| **{label}** | {k_rate} ({s['10k_passed']}/{s['10k_total']}) | {q_rate} ({s['10q_passed']}/{s['10q_total']}) |")
    
    # Top failing metrics
    from collections import Counter
    metric_counts = Counter(f["metric"] for f in failures)
    lines.extend([
        "",
        "## Top 10 Failing Metrics",
        "",
        "| Metric | Failures |",
        "|--------|----------|",
    ])
    for metric, count in metric_counts.most_common(10):
        lines.append(f"| {metric} | {count} |")
    
    # Top failing companies
    ticker_counts = Counter(f["ticker"] for f in failures)
    lines.extend([
        "",
        "## Top 10 Failing Companies",
        "",
        "| Ticker | Failures |",
        "|--------|----------|",
    ])
    for ticker, count in ticker_counts.most_common(10):
        lines.append(f"| {ticker} | {count} |")
    
    lines.extend([
        "",
        f"*See JSON report for full failure details ({len(failures)} total failures)*"
    ])
    
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description="S&P500 Multi-Period E2E Test")
    parser.add_argument("--group", choices=["sp25", "sp50"], default="sp25", 
                        help="Company group to test")
    parser.add_argument("--workers", type=int, default=8, 
                        help="Number of parallel workers")
    parser.add_argument("--years", type=int, default=5, 
                        help="Number of 10-K years to test")
    parser.add_argument("--quarters", type=int, default=6, 
                        help="Number of 10-Q quarters to test")
    parser.add_argument("--tickers", type=str, metavar="TICKERS",
                        help="Comma-separated list of tickers to test (overrides --group)")
    parser.add_argument("--metrics", type=str, metavar="METRICS",
                        help="Comma-separated list of metrics to test")
    args = parser.parse_args()
    
    # Cap workers
    max_workers = min(args.workers, cpu_count(), 8)
    
    config = {
        "group": args.group if not args.tickers else "custom",
        "workers": max_workers,
        "years": args.years,
        "quarters": args.quarters,
        "metrics": [m.strip() for m in args.metrics.split(',')] if args.metrics else None
    }
    
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',') if t.strip()]
        group_name = "custom"
    else:
        tickers = SP25 if args.group == "sp25" else SP50
        group_name = args.group
    
    print(f"="*60)
    print(f"E2E TEST: {group_name.upper()} ({len(tickers)} companies)")
    if config["metrics"]:
        print(f"Metrics: {config['metrics']}")
    print(f"Workers: {max_workers}, Years: {args.years}, Quarters: {args.quarters}")
    print(f"="*60)
    
    # Run parallel processing
    # Create worker config for each ticker (needs to be pickleable)
    work_items = []
    for ticker in tickers:
        item = config.copy()
        item["ticker"] = ticker
        work_items.append(item)
    
    print(f"\nProcessing {len(tickers)} companies with {max_workers} workers...")
    with Pool(processes=max_workers) as pool:
        results = pool.map(process_company, work_items)
    
    # Aggregate all failures
    all_failures = []
    for r in results:
        all_failures.extend(r["failures"])
    
    # Write reports
    script_dir = Path(__file__).parent
    reports_dir = script_dir / "reports"
    reports_dir.mkdir(exist_ok=True)
    
    import random
    import string
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H%M")
    filename_base = f"e2e_{group_name}_{date_str}_{time_str}"
    
    json_path = reports_dir / f"{filename_base}.json"
    md_path = reports_dir / f"{filename_base}.md"
    
    summary = write_json_report(results, json_path, config)
    write_markdown_report(summary, all_failures, md_path, config)
    
    # Print summary
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    
    # Check if any summary has data
    has_results = False
    for key in ["sp25", "sp50", "custom"]:
        s = summary.get(key)
        if s and (s['10k_total'] > 0 or s['10q_total'] > 0):
            k_rate = f"{s['10k_passed']/s['10k_total']*100:.1f}%" if s['10k_total'] > 0 else "N/A"
            q_rate = f"{s['10q_passed']/s['10q_total']*100:.1f}%" if s['10q_total'] > 0 else "N/A"
            print(f"{key.upper()}: 10-K {k_rate} ({s['10k_passed']}/{s['10k_total']}), 10-Q {q_rate} ({s['10q_passed']}/{s['10q_total']})")
            has_results = True
            
    if not has_results:
        print("No validation results recorded.")
    
    print(f"\nTotal failures: {len(all_failures)}")
    print(f"Reports written to: {reports_dir}")
    print(f"  - {json_path.name}")
    print(f"  - {md_path.name}")


if __name__ == "__main__":
    main()
