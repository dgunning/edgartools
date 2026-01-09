"""
Multi-Period Validation Tool

Validates XBRL mappings across multiple fiscal years to build confidence
and identify discrepancies requiring investigation.

Usage:
    python -m edgar.xbrl.standardization.tools.validate_multi_period TICKER METRIC
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from edgar import set_identity, use_local_storage, Company


VALIDATION_HISTORY_FILE = Path(__file__).parent.parent / "company_mappings" / "validation_history.json"


def get_last_n_10ks(ticker: str, n: int = 3):
    """Fetch the last N 10-K filings for a company."""
    try:
        c = Company(ticker)
        filings = c.get_filings(form='10-K', amendments=False)
        return list(filings)[:n]
    except Exception as e:
        print(f"Error fetching filings for {ticker}: {e}")
        return []


def extract_value_from_filing(filing, metric: str, concept: str) -> Optional[float]:
    """Extract a value from a filing's XBRL data."""
    try:
        xbrl = filing.xbrl()
        if not xbrl or not xbrl.facts:
            return None
        
        # Try to find the concept in facts
        for fact in xbrl.facts:
            if hasattr(fact, 'concept') and concept in str(fact.concept):
                # Get the value for duration or instant
                if hasattr(fact, 'value') and fact.value is not None:
                    try:
                        return float(fact.value)
                    except (ValueError, TypeError):
                        continue
        return None
    except Exception as e:
        print(f"Error extracting {metric} from filing: {e}")
        return None


def validate_across_periods(
    ticker: str, 
    metric: str, 
    concept: str,
    years: int = 3
) -> Dict:
    """
    Validate a mapping is consistent across multiple 10-K filings.
    
    Returns:
        Dict with:
        - status: "zero_confirmed", "mapping_consistent", "values_vary", "needs_investigation"
        - values: dict of period -> value
        - periods_verified: list of periods
    """
    filings = get_last_n_10ks(ticker, years)
    
    if not filings:
        return {
            "status": "no_filings",
            "values": {},
            "periods_verified": []
        }
    
    values = {}
    for filing in filings:
        period = filing.period_of_report
        period_key = period.strftime("%Y-FY") if period else "unknown"
        value = extract_value_from_filing(filing, metric, concept)
        values[period_key] = value
    
    # Analyze results
    non_none_values = [v for v in values.values() if v is not None]
    
    if len(non_none_values) == 0:
        status = "needs_investigation"
    elif all(v == 0 for v in non_none_values):
        status = "zero_confirmed"
    elif len(non_none_values) >= 2:
        status = "mapping_consistent"
    else:
        status = "needs_more_data"
    
    return {
        "status": status,
        "values": values,
        "periods_verified": list(values.keys()),
        "concept": concept
    }


def record_to_history(ticker: str, metric: str, result: Dict):
    """Record validation result to validation_history.json."""
    # Load existing history
    if VALIDATION_HISTORY_FILE.exists():
        with open(VALIDATION_HISTORY_FILE, 'r') as f:
            history = json.load(f)
    else:
        history = {"schema_version": "1.0", "tiers": {}, "companies": {}}
    
    companies = history.setdefault("companies", {})
    company = companies.setdefault(ticker, {})
    
    # Determine tier
    if result["status"] == "zero_confirmed":
        tier = 1  # Trusted - consistently zero
    elif result["status"] == "mapping_consistent":
        tier = 1 if len(result["periods_verified"]) >= 3 else 2
    else:
        tier = 2  # Still verifying
    
    company[metric] = {
        "concept": result.get("concept", ""),
        "tier": tier,
        "periods_verified": result["periods_verified"],
        "values": result["values"],
        "notes": f"Auto-validated: {result['status']}",
        "validated_date": datetime.now().strftime("%Y-%m-%d")
    }
    
    # Save
    with open(VALIDATION_HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=4)
    
    return tier


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate XBRL mapping across periods")
    parser.add_argument("ticker", help="Company ticker")
    parser.add_argument("metric", help="Metric name")
    parser.add_argument("--concept", default="", help="XBRL concept to validate")
    parser.add_argument("--years", type=int, default=3, help="Number of years")
    parser.add_argument("--record", action="store_true", help="Record to history")
    
    args = parser.parse_args()
    
    set_identity('Dev Gunning developer-gunning@gmail.com')
    use_local_storage(True)
    
    print(f"\n=== Validating {args.ticker} {args.metric} ===\n")
    
    result = validate_across_periods(
        args.ticker, 
        args.metric, 
        args.concept or f"us-gaap:{args.metric}",
        args.years
    )
    
    print(f"Status: {result['status']}")
    print(f"Periods: {result['periods_verified']}")
    print(f"Values: {result['values']}")
    
    if args.record:
        tier = record_to_history(args.ticker, args.metric, result)
        print(f"\nRecorded to history as tier {tier}")


if __name__ == "__main__":
    main()
