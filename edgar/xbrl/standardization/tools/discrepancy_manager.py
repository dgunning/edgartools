"""
Discrepancy Manager - CLI for managing known XBRL/reference discrepancies.

This module provides tools to:
1. Add new discrepancies to the documentation
2. Search existing discrepancies
3. Check if a metric has a documented discrepancy

Usage:
    python -m edgar.xbrl.standardization.tools.discrepancy_manager add TSLA IntangibleAssets ...
    python -m edgar.xbrl.standardization.tools.discrepancy_manager search --ticker TSLA
    python -m edgar.xbrl.standardization.tools.discrepancy_manager check TSLA IntangibleAssets
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from pathlib import Path


DISCREPANCIES_FILE = Path(__file__).parent.parent / "company_mappings" / "discrepancies.json"


@dataclass
class Discrepancy:
    """A documented discrepancy between XBRL and reference data."""
    id: str
    ticker: str
    metric: str
    fiscal_period: str
    created_date: str
    xbrl: Dict
    reference: Dict
    variance_pct: Optional[float]
    classification: str  # definition_mismatch, reference_unavailable, period_mismatch
    status: str  # accepted, investigating, rejected
    investigation: Dict
    action: str  # use_xbrl_value, use_reference_value, manual_review


def load_discrepancies() -> Dict:
    """Load discrepancies from JSON file."""
    if DISCREPANCIES_FILE.exists():
        with open(DISCREPANCIES_FILE, 'r') as f:
            return json.load(f)
    return {
        "schema_version": "1.0",
        "statistics": {"total": 0, "by_classification": {}, "by_status": {}},
        "discrepancies": []
    }


def save_discrepancies(data: Dict):
    """Save discrepancies to JSON file."""
    # Update statistics
    classifications = {}
    statuses = {}
    for d in data["discrepancies"]:
        cls = d.get("classification", "unknown")
        classifications[cls] = classifications.get(cls, 0) + 1
        status = d.get("status", "unknown")
        statuses[status] = statuses.get(status, 0) + 1
    
    data["statistics"] = {
        "total": len(data["discrepancies"]),
        "by_classification": classifications,
        "by_status": statuses
    }
    
    with open(DISCREPANCIES_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def add_discrepancy(
    ticker: str,
    metric: str,
    fiscal_period: str,
    xbrl_value: float,
    xbrl_concepts: List[str],
    ref_value: Optional[float],
    ref_source: str,
    ref_field: str,
    classification: str,
    root_cause: str,
    action: str = "use_xbrl_value"
) -> str:
    """Add a new discrepancy to the documentation.
    
    Returns:
        The ID of the created discrepancy.
    """
    data = load_discrepancies()
    
    # Generate ID
    disc_id = f"{ticker}-{metric}-{fiscal_period.replace('-', '')}"
    
    # Check if already exists
    for d in data["discrepancies"]:
        if d["id"] == disc_id:
            raise ValueError(f"Discrepancy {disc_id} already exists")
    
    # Calculate variance
    variance = None
    if xbrl_value is not None and ref_value is not None and ref_value != 0:
        variance = abs(xbrl_value - ref_value) / abs(ref_value) * 100
    
    discrepancy = {
        "id": disc_id,
        "ticker": ticker,
        "metric": metric,
        "fiscal_period": fiscal_period,
        "created_date": datetime.now().strftime("%Y-%m-%d"),
        "xbrl": {
            "value": xbrl_value,
            "concepts": xbrl_concepts,
            "method": "composite_sum" if len(xbrl_concepts) > 1 else "direct"
        },
        "reference": {
            "source": ref_source,
            "field": ref_field,
            "value": ref_value
        },
        "variance_pct": round(variance, 1) if variance else None,
        "classification": classification,
        "status": "accepted",
        "investigation": {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "root_cause": root_cause,
            "verified_correct": True,
            "verified_by": "agent"
        },
        "action": action
    }
    
    data["discrepancies"].append(discrepancy)
    save_discrepancies(data)
    
    return disc_id


def search_discrepancies(
    ticker: Optional[str] = None,
    metric: Optional[str] = None,
    classification: Optional[str] = None
) -> List[Dict]:
    """Search discrepancies by criteria."""
    data = load_discrepancies()
    results = []
    
    for d in data["discrepancies"]:
        if ticker and d["ticker"] != ticker:
            continue
        if metric and d["metric"] != metric:
            continue
        if classification and d["classification"] != classification:
            continue
        results.append(d)
    
    return results


def check_discrepancy(ticker: str, metric: str) -> Optional[Dict]:
    """Check if a metric has a documented discrepancy.
    
    Returns:
        The discrepancy dict if found, None otherwise.
    """
    results = search_discrepancies(ticker=ticker, metric=metric)
    return results[0] if results else None


def get_statistics() -> Dict:
    """Get discrepancy statistics."""
    data = load_discrepancies()
    return data["statistics"]


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Discrepancy Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new discrepancy")
    add_parser.add_argument("ticker", help="Company ticker")
    add_parser.add_argument("metric", help="Metric name")
    add_parser.add_argument("--period", required=True, help="Fiscal period (e.g., 2024-FY)")
    add_parser.add_argument("--xbrl-value", type=float, required=True)
    add_parser.add_argument("--xbrl-concepts", nargs="+", required=True)
    add_parser.add_argument("--ref-value", type=float, default=None)
    add_parser.add_argument("--ref-source", default="yfinance")
    add_parser.add_argument("--ref-field", required=True)
    add_parser.add_argument("--classification", required=True,
                           choices=["definition_mismatch", "reference_unavailable", "period_mismatch"])
    add_parser.add_argument("--reason", required=True, help="Root cause explanation")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search discrepancies")
    search_parser.add_argument("--ticker", help="Filter by ticker")
    search_parser.add_argument("--metric", help="Filter by metric")
    search_parser.add_argument("--classification", help="Filter by classification")
    
    # Check command
    check_parser = subparsers.add_parser("check", help="Check if discrepancy exists")
    check_parser.add_argument("ticker", help="Company ticker")
    check_parser.add_argument("metric", help="Metric name")
    
    # Stats command
    subparsers.add_parser("stats", help="Show statistics")
    
    args = parser.parse_args()
    
    if args.command == "add":
        disc_id = add_discrepancy(
            ticker=args.ticker,
            metric=args.metric,
            fiscal_period=args.period,
            xbrl_value=args.xbrl_value,
            xbrl_concepts=args.xbrl_concepts,
            ref_value=args.ref_value,
            ref_source=args.ref_source,
            ref_field=args.ref_field,
            classification=args.classification,
            root_cause=args.reason
        )
        print(f"✓ Added discrepancy: {disc_id}")
    
    elif args.command == "search":
        results = search_discrepancies(
            ticker=args.ticker,
            metric=args.metric,
            classification=args.classification
        )
        print(f"Found {len(results)} discrepancies:")
        for d in results:
            print(f"  {d['id']}: {d['classification']} - {d['investigation']['root_cause'][:50]}...")
    
    elif args.command == "check":
        result = check_discrepancy(args.ticker, args.metric)
        if result:
            print(f"✓ Discrepancy found: {result['id']}")
            print(f"  Classification: {result['classification']}")
            print(f"  Action: {result['action']}")
        else:
            print(f"✗ No discrepancy found for {args.ticker} {args.metric}")
    
    elif args.command == "stats":
        stats = get_statistics()
        print(f"Total discrepancies: {stats['total']}")
        print(f"By classification: {stats['by_classification']}")
        print(f"By status: {stats['by_status']}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
