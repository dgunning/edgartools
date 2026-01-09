"""
Extraction Rules Loader - Load company-specific extraction rules from JSON configs.

This module provides:
1. Load extraction rules from company_mappings/*.json
2. Apply priority resolution (company > industry > defaults)
3. Get extraction method and concept priority for any metric

Usage:
    from edgar.xbrl.standardization.extraction_rules import get_extraction_rule
    
    rule = get_extraction_rule('MSFT', 'IntangibleAssets')
    # Returns: {'method': 'composite_sum', 'components': [...], ...}
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any


COMPANY_MAPPINGS_DIR = Path(__file__).parent / "company_mappings"


def _load_json(filepath: Path) -> Dict:
    """Load a JSON file, return empty dict if not found."""
    if filepath.exists():
        with open(filepath, 'r') as f:
            return json.load(f)
    return {}


def get_defaults() -> Dict:
    """Load default extraction rules."""
    return _load_json(COMPANY_MAPPINGS_DIR / "_defaults.json")


def get_company_mappings(ticker: str) -> Dict:
    """Load company-specific mappings.
    
    Tries both lowercase ticker (msft_mappings.json) and exact match.
    """
    # Try lowercase first (convention)
    filepath = COMPANY_MAPPINGS_DIR / f"{ticker.lower()}_mappings.json"
    if filepath.exists():
        return _load_json(filepath)
    
    # Try exact ticker
    filepath = COMPANY_MAPPINGS_DIR / f"{ticker}_mappings.json"
    return _load_json(filepath)


def get_industry_rules(industry: str) -> Dict:
    """Load industry-specific rules.
    
    Args:
        industry: Industry identifier (e.g., 'banking', 'insurance')
    """
    filepath = COMPANY_MAPPINGS_DIR / f"_industry_{industry}.json"
    return _load_json(filepath)


def get_extraction_rule(
    ticker: str,
    metric: str,
    industry: Optional[str] = None
) -> Optional[Dict]:
    """Get extraction rule for a metric.
    
    Priority resolution:
    1. Company-specific rule (msft_mappings.json)
    2. Industry rule (_industry_banking.json)
    3. Default rule (_defaults.json)
    
    Args:
        ticker: Company ticker
        metric: Metric name (e.g., 'IntangibleAssets')
        industry: Optional industry for industry-level rules
        
    Returns:
        Extraction rule dict with method, components, concept_priority, etc.
        None if no rule found.
    """
    # Check company-specific first
    company = get_company_mappings(ticker)
    if company:
        rules = company.get("extraction_rules", {})
        if metric in rules:
            return rules[metric]
    
    # Check industry rules
    if industry:
        industry_data = get_industry_rules(industry)
        rules = industry_data.get("extraction_rules", {})
        if metric in rules:
            return rules[metric]
    
    # Fall back to defaults
    defaults = get_defaults()
    rules = defaults.get("extraction_rules", {})
    return rules.get(metric)


def get_concept_priority(
    ticker: str,
    metric: str,
    component: str,
    industry: Optional[str] = None
) -> List[str]:
    """Get concept priority list for a composite component.
    
    Args:
        ticker: Company ticker
        metric: Metric name
        component: Component name (e.g., 'Goodwill')
        industry: Optional industry
        
    Returns:
        List of concepts to try in priority order.
    """
    rule = get_extraction_rule(ticker, metric, industry)
    if rule and "concept_priority" in rule:
        priority = rule["concept_priority"]
        if component in priority:
            return priority[component]
    
    # Default: just try the component name with us-gaap prefix
    return [f"us-gaap:{component}"]


def get_composite_components(
    ticker: str,
    metric: str,
    industry: Optional[str] = None
) -> Optional[List[str]]:
    """Get composite components for a metric.
    
    Args:
        ticker: Company ticker
        metric: Metric name
        industry: Optional industry
        
    Returns:
        List of component names, or None if not composite.
    """
    rule = get_extraction_rule(ticker, metric, industry)
    if rule and rule.get("method") == "composite_sum":
        return rule.get("components", [])
    return None


def get_period_selection_config() -> Dict:
    """Get period selection configuration."""
    defaults = get_defaults()
    return defaults.get("period_selection", {
        "duration_metrics": [],
        "prefer_annual": True,
        "min_days_for_annual": 300
    })


def is_duration_metric(metric: str) -> bool:
    """Check if metric should use annual period preference."""
    config = get_period_selection_config()
    return metric in config.get("duration_metrics", [])


# Summary functions for statistics

def get_all_company_rules() -> Dict[str, Dict]:
    """Get all company-specific extraction rules for KPI tracking."""
    result = {}
    for filepath in COMPANY_MAPPINGS_DIR.glob("*_mappings.json"):
        if filepath.name.startswith("_"):
            continue
        ticker = filepath.stem.replace("_mappings", "").upper()
        data = _load_json(filepath)
        rules = data.get("extraction_rules", {})
        if rules:
            result[ticker] = rules
    return result


def count_extraction_rules() -> Dict[str, int]:
    """Count extraction rules by type for KPI reporting."""
    defaults = get_defaults()
    
    default_count = len(defaults.get("extraction_rules", {}))
    
    company_count = 0
    for filepath in COMPANY_MAPPINGS_DIR.glob("*_mappings.json"):
        if filepath.name.startswith("_"):
            continue
        data = _load_json(filepath)
        company_count += len(data.get("extraction_rules", {}))
    
    industry_count = 0
    for filepath in COMPANY_MAPPINGS_DIR.glob("_industry_*.json"):
        data = _load_json(filepath)
        industry_count += len(data.get("extraction_rules", {}))
    
    return {
        "universal": default_count,
        "industry": industry_count,
        "company": company_count
    }
