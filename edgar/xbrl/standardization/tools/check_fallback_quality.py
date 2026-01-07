"""
Fallback Quality Checker Tool

REUSABLE TOOL FOR AI AGENTS

Verifies that a proposed concept is semantically valid for a metric.
Flags parent-concept fallbacks (e.g., Assets for IntangibleAssets).

Usage by AI Agent:
    from edgar.xbrl.standardization.tools.check_fallback_quality import check_fallback_quality
    
    result = check_fallback_quality("IntangibleAssets", "us-gaap:Assets", xbrl)
    if not result.is_valid:
        print(f"Invalid: {result.issues}")
        print(f"Suggestions: {result.suggestions}")
"""

import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from edgar.xbrl.xbrl import XBRL


@dataclass
class QualityResult:
    """Result of fallback quality check."""
    metric: str
    concept: str
    is_valid: bool
    confidence: float
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    explanation: Optional[str] = None


# Known parent concepts that are too generic to use as fallbacks
GENERIC_PARENT_CONCEPTS = {
    'Assets': ['IntangibleAssets', 'Goodwill', 'TangibleAssets', 'PropertyPlantEquipment'],
    'Liabilities': ['ShortTermDebt', 'LongTermDebt', 'AccountsPayable'],
    'Revenue': ['NetSales', 'GrossProfit'],
    'CostsAndExpenses': ['COGS', 'SGA', 'OperatingExpenses'],
    'StockholdersEquity': ['RetainedEarnings', 'CommonStock'],
}

# Mapping of metrics to concepts that are semantically too different
INVALID_FALLBACKS = {
    'IntangibleAssets': ['Assets', 'TotalAssets', 'CurrentAssets', 'NoncurrentAssets'],
    'Goodwill': ['Assets', 'TotalAssets', 'IntangibleAssets'],
    'ShortTermDebt': ['Liabilities', 'TotalLiabilities', 'LongTermDebt'],
    'LongTermDebt': ['Liabilities', 'TotalLiabilities', 'ShortTermDebt'],
    'Capex': ['CashFlows', 'OperatingCashFlow'],
    'COGS': ['CostsAndExpenses', 'OperatingExpenses'],
    'SGA': ['CostsAndExpenses', 'OperatingExpenses', 'CostOfRevenue'],
}

# Regex patterns for prefix stripping
NAMESPACE_PREFIX_PATTERN = re.compile(r'^(us-gaap:|dei:|ifrs-full:)')
COMPANY_PREFIX_PATTERN = re.compile(r'^[a-z]{2,5}_', re.IGNORECASE)


def strip_prefix(concept: str) -> str:
    """Strip namespace and company prefixes from a concept name."""
    result = NAMESPACE_PREFIX_PATTERN.sub('', concept)
    result = COMPANY_PREFIX_PATTERN.sub('', result)
    return result


def semantic_similarity(s1: str, s2: str) -> float:
    """Calculate semantic similarity between two strings."""
    s1_lower = s1.lower()
    s2_lower = s2.lower()
    return SequenceMatcher(None, s1_lower, s2_lower).ratio()


def check_fallback_quality(
    metric: str,
    concept: str,
    xbrl: Optional[XBRL] = None,
    known_valid_concepts: Optional[List[str]] = None
) -> QualityResult:
    """
    Verify a proposed concept is semantically valid for a metric.
    
    This is a REUSABLE TOOL for AI agents to use before accepting 
    medium/low confidence mappings.
    
    Args:
        metric: Target metric name (e.g., "IntangibleAssets")
        concept: Proposed XBRL concept (e.g., "us-gaap:Assets")
        xbrl: Optional XBRL object for tree context
        known_valid_concepts: Optional list of known valid concepts
        
    Returns:
        QualityResult with is_valid, issues, and suggestions
    """
    issues = []
    suggestions = []
    
    stripped_concept = strip_prefix(concept)
    
    # Check 1: Is concept in the explicit invalid fallbacks list?
    if metric in INVALID_FALLBACKS:
        invalid_list = INVALID_FALLBACKS[metric]
        if stripped_concept in invalid_list:
            issues.append(f"'{stripped_concept}' is explicitly marked as invalid fallback for '{metric}'")
    
    # Check 2: Is concept a known generic parent?
    for parent, children in GENERIC_PARENT_CONCEPTS.items():
        if stripped_concept == parent and metric in children:
            issues.append(f"'{stripped_concept}' is a parent concept of '{metric}' - too generic")
    
    # Check 3: Check semantic similarity
    similarity = semantic_similarity(metric, stripped_concept)
    if similarity < 0.3:
        issues.append(f"Low semantic similarity ({similarity:.2f}) between '{metric}' and '{stripped_concept}'")
    
    # Check 4: Check against known valid concepts
    if known_valid_concepts:
        match_found = False
        for valid in known_valid_concepts:
            if strip_prefix(valid).lower() == stripped_concept.lower():
                match_found = True
                break
        if not match_found:
            issues.append(f"'{stripped_concept}' is not in the list of known valid concepts for '{metric}'")
            suggestions.extend([f"Consider: {c}" for c in known_valid_concepts[:3]])
    
    # Check 5: If we have XBRL, check tree context
    if xbrl is not None:
        tree_context = _get_tree_context(xbrl, concept)
        if tree_context:
            # Check if metric appears as a child of this concept
            if _is_parent_of_metric(xbrl, concept, metric):
                issues.append(f"'{stripped_concept}' appears to be a parent of '{metric}' in the calculation tree")
    
    # Determine validity
    is_valid = len(issues) == 0
    confidence = 1.0 - (len(issues) * 0.25)  # Reduce confidence for each issue
    confidence = max(0.0, confidence)
    
    explanation = "Valid fallback" if is_valid else f"Invalid: {'; '.join(issues)}"
    
    return QualityResult(
        metric=metric,
        concept=concept,
        is_valid=is_valid,
        confidence=confidence,
        issues=issues,
        suggestions=suggestions,
        explanation=explanation
    )


def _get_tree_context(xbrl: XBRL, concept: str) -> Optional[Dict]:
    """Get tree context for a concept."""
    try:
        stripped = strip_prefix(concept)
        
        for statement in ['INCOME', 'BALANCE', 'CASHFLOW', 'OPERATIONS']:
            try:
                calc_tree = getattr(xbrl.calculations, statement, None)
                if calc_tree is None:
                    continue
                    
                for node in calc_tree.traverse():
                    if strip_prefix(node.name) == stripped:
                        return {
                            'statement': statement,
                            'parent': node.parent.name if node.parent else None,
                            'weight': node.weight if hasattr(node, 'weight') else 1.0
                        }
            except Exception:
                continue
    except Exception:
        pass
    
    return None


def _is_parent_of_metric(xbrl: XBRL, concept: str, metric: str) -> bool:
    """Check if concept appears to be a parent of the metric in calc trees."""
    try:
        stripped_concept = strip_prefix(concept)
        
        for statement in ['INCOME', 'BALANCE', 'CASHFLOW', 'OPERATIONS']:
            try:
                calc_tree = getattr(xbrl.calculations, statement, None)
                if calc_tree is None:
                    continue
                    
                for node in calc_tree.traverse():
                    node_stripped = strip_prefix(node.name)
                    
                    # If we find the concept as a parent
                    if node_stripped.lower() == stripped_concept.lower():
                        # Check if any of its children match the metric
                        if hasattr(node, 'children'):
                            for child in node.children:
                                child_stripped = strip_prefix(child.name)
                                if metric.lower() in child_stripped.lower():
                                    return True
            except Exception:
                continue
    except Exception:
        pass
    
    return False


# Convenience function for quick testing
def check(metric: str, concept: str) -> QualityResult:
    """Quick way to check fallback quality."""
    return check_fallback_quality(metric, concept)
