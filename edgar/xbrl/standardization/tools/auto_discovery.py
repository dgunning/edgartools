"""
Auto-Discovery Module - Automatically record new concept mappings discovered during runs.

This module tracks:
1. New concepts discovered by facts search
2. Industry patterns (when 3+ companies use same concept)
3. Suggestions for metrics.yaml updates

Usage:
    from edgar.xbrl.standardization.auto_discovery import record_discovery, get_discoveries
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict


DISCOVERIES_FILE = Path(__file__).parent.parent / "company_mappings" / "discoveries.json"


def _load_discoveries() -> Dict:
    """Load existing discoveries."""
    if DISCOVERIES_FILE.exists():
        with open(DISCOVERIES_FILE, 'r') as f:
            return json.load(f)
    return {
        "schema_version": "1.0",
        "last_updated": None,
        "discoveries": [],
        "industry_patterns": {},
        "suggestions": []
    }


def _save_discoveries(data: Dict):
    """Save discoveries to file."""
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(DISCOVERIES_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def record_discovery(
    ticker: str,
    metric: str,
    concept: str,
    method: str,
    value: Optional[float] = None,
    industry: Optional[str] = None
):
    """
    Record a new concept mapping discovered during a run.
    
    Args:
        ticker: Company ticker
        metric: Standard metric name
        concept: XBRL concept found
        method: How it was discovered (e.g., 'facts_search', 'tree_parser')
        value: Optional extracted value
        industry: Optional industry of the company
    """
    data = _load_discoveries()
    
    # Check if already recorded
    existing = [d for d in data["discoveries"] 
                if d["ticker"] == ticker and d["metric"] == metric]
    if existing:
        return  # Already recorded
    
    # Add new discovery
    discovery = {
        "ticker": ticker,
        "metric": metric,
        "concept": concept,
        "method": method,
        "value": value,
        "industry": industry,
        "discovered_at": datetime.now().strftime("%Y-%m-%d")
    }
    data["discoveries"].append(discovery)
    
    # Update industry patterns
    if industry:
        patterns = data.setdefault("industry_patterns", {})
        industry_data = patterns.setdefault(industry, {})
        metric_data = industry_data.setdefault(metric, {})
        concepts = metric_data.setdefault("concepts", {})
        concepts[concept] = concepts.get(concept, 0) + 1
    
    # Check for suggestions (3+ companies using same concept)
    concept_counts = defaultdict(int)
    for d in data["discoveries"]:
        if d["metric"] == metric:
            concept_counts[d["concept"]] += 1
    
    for c, count in concept_counts.items():
        if count >= 3:
            suggestion = {
                "metric": metric,
                "concept": c,
                "count": count,
                "action": "add_to_known_concepts"
            }
            existing_sugg = [s for s in data["suggestions"] 
                           if s["metric"] == metric and s["concept"] == c]
            if not existing_sugg:
                data["suggestions"].append(suggestion)
    
    _save_discoveries(data)


def get_discoveries(metric: Optional[str] = None, industry: Optional[str] = None) -> List[Dict]:
    """Get recorded discoveries, optionally filtered."""
    data = _load_discoveries()
    discoveries = data["discoveries"]
    
    if metric:
        discoveries = [d for d in discoveries if d["metric"] == metric]
    if industry:
        discoveries = [d for d in discoveries if d.get("industry") == industry]
    
    return discoveries


def get_suggestions() -> List[Dict]:
    """Get suggestions for metrics.yaml updates."""
    data = _load_discoveries()
    return data.get("suggestions", [])


def get_industry_patterns() -> Dict:
    """Get industry patterns discovered."""
    data = _load_discoveries()
    return data.get("industry_patterns", {})


def print_report():
    """Print a summary of discoveries."""
    data = _load_discoveries()
    
    print(f"\n=== Discoveries Report ===")
    print(f"Total discoveries: {len(data['discoveries'])}")
    print(f"Last updated: {data.get('last_updated', 'never')}")
    
    # By metric
    by_metric = defaultdict(list)
    for d in data["discoveries"]:
        by_metric[d["metric"]].append(d)
    
    print(f"\nBy metric:")
    for metric, discs in sorted(by_metric.items()):
        concepts = set(d["concept"] for d in discs)
        print(f"  {metric}: {len(discs)} discoveries, {len(concepts)} unique concepts")
    
    # Suggestions
    suggs = data.get("suggestions", [])
    if suggs:
        print(f"\nSuggestions for metrics.yaml:")
        for s in suggs:
            print(f"  Add {s['concept']} to {s['metric']} ({s['count']} companies use it)")


if __name__ == "__main__":
    print_report()
