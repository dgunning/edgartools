"""
Validation Manager - Multi-period validation with tiered trust system.

Tiers:
1. Trusted - verified across 3+ periods, skip yfinance validation
2. Verifying - new mapping, compare with yfinance
3. Discrepancy - known mismatch, documented and accepted

Usage:
    from edgar.xbrl.standardization.validation_manager import (
        get_validation_tier,
        should_skip_yfinance,
        record_validation
    )
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Tuple


VALIDATION_HISTORY_FILE = Path(__file__).parent / "company_mappings" / "validation_history.json"
DISCREPANCIES_FILE = Path(__file__).parent / "company_mappings" / "discrepancies.json"


def _load_validation_history() -> Dict:
    """Load validation history from JSON file."""
    if VALIDATION_HISTORY_FILE.exists():
        with open(VALIDATION_HISTORY_FILE, 'r') as f:
            return json.load(f)
    return {"schema_version": "1.0", "tiers": {}, "companies": {}}


def _save_validation_history(data: Dict):
    """Save validation history to JSON file."""
    with open(VALIDATION_HISTORY_FILE, 'w') as f:
        json.dump(data, f, indent=4)


def _load_discrepancies() -> Dict:
    """Load discrepancies from JSON file."""
    if DISCREPANCIES_FILE.exists():
        with open(DISCREPANCIES_FILE, 'r') as f:
            return json.load(f)
    return {"discrepancies": []}


def get_validation_tier(ticker: str, metric: str) -> Tuple[int, Optional[Dict]]:
    """Get validation tier for a metric.
    
    Returns:
        Tuple of (tier, data) where tier is 1, 2, or 3:
        - 1: Trusted (skip yfinance)
        - 2: Verifying (compare with yfinance)
        - 3: Discrepancy (documented mismatch)
        
        data contains the tier entry details, or None for tier 2.
    """
    # Check discrepancies first (tier 3)
    discrepancies = _load_discrepancies()
    for d in discrepancies.get("discrepancies", []):
        if d["ticker"] == ticker and d["metric"] == metric:
            if d.get("status") == "accepted":
                return 3, d
    
    # Check validation history (tier 1)
    history = _load_validation_history()
    companies = history.get("companies", {})
    if ticker in companies:
        if metric in companies[ticker]:
            entry = companies[ticker][metric]
            if entry.get("tier") == 1:
                return 1, entry
    
    # Default to tier 2 (verifying)
    return 2, None


def should_skip_yfinance(ticker: str, metric: str) -> bool:
    """Check if yfinance validation should be skipped.
    
    Returns True for tier 1 (trusted) and tier 3 (discrepancy accepted).
    """
    tier, _ = get_validation_tier(ticker, metric)
    return tier in (1, 3)


def get_trust_reason(ticker: str, metric: str) -> Optional[str]:
    """Get the reason why yfinance validation is skipped."""
    tier, data = get_validation_tier(ticker, metric)
    if tier == 1 and data:
        periods = data.get("periods_verified", [])
        return f"trusted: verified across {len(periods)} periods"
    elif tier == 3 and data:
        return f"discrepancy: {data.get('classification', 'documented')}"
    return None


def record_validation(
    ticker: str,
    metric: str,
    concept: str,
    fiscal_period: str,
    value: float,
    matched_yfinance: bool
) -> bool:
    """Record a validation result and potentially promote to tier 1.
    
    Args:
        ticker: Company ticker
        metric: Metric name
        concept: XBRL concept mapped
        fiscal_period: e.g., "2024-FY"
        value: Extracted XBRL value
        matched_yfinance: Whether it matched yfinance
        
    Returns:
        True if promoted to tier 1, False otherwise.
    """
    history = _load_validation_history()
    companies = history.setdefault("companies", {})
    company = companies.setdefault(ticker, {})
    
    if metric not in company:
        company[metric] = {
            "concept": concept,
            "tier": 2,
            "periods_verified": [],
            "values": {},
            "notes": ""
        }
    
    entry = company[metric]
    
    # Only record if matched
    if matched_yfinance:
        if fiscal_period not in entry["periods_verified"]:
            entry["periods_verified"].append(fiscal_period)
            entry["values"][fiscal_period] = value
        
        # Promote to tier 1 if 3+ periods verified
        if len(entry["periods_verified"]) >= 3 and entry["tier"] != 1:
            entry["tier"] = 1
            entry["promoted_date"] = datetime.now().strftime("%Y-%m-%d")
            entry["notes"] = f"Auto-promoted after {len(entry['periods_verified'])} periods verified"
            _save_validation_history(history)
            return True
    
    _save_validation_history(history)
    return False


def get_tier_statistics() -> Dict[str, int]:
    """Get statistics on validation tiers."""
    history = _load_validation_history()
    discrepancies = _load_discrepancies()
    
    tier_1 = 0
    tier_2 = 0
    tier_3 = len([d for d in discrepancies.get("discrepancies", []) 
                  if d.get("status") == "accepted"])
    
    for company in history.get("companies", {}).values():
        for entry in company.values():
            if entry.get("tier") == 1:
                tier_1 += 1
            else:
                tier_2 += 1
    
    return {"tier_1_trusted": tier_1, "tier_2_verifying": tier_2, "tier_3_discrepancy": tier_3}
