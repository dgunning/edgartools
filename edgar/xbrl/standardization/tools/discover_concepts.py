"""
Concept Discovery Tool

REUSABLE TOOL FOR AI AGENTS

This tool searches both calculation trees AND facts to discover
concepts that match a target metric. Designed to be invoked when 
static mapping layers (Tree Parser, Facts Search) fail to find a match.

Usage by AI Agent:
    from edgar.xbrl.standardization.tools.discover_concepts import discover_concepts
    
    candidates = discover_concepts("IntangibleAssets", xbrl, facts_df)
    for c in candidates:
        print(f"{c.concept} (confidence: {c.confidence}, source: {c.source})")
"""

import re
from typing import List, Optional, Dict, Any, Set
from dataclasses import dataclass
from difflib import SequenceMatcher

import pandas as pd

from edgar import Company, use_local_storage
from edgar.xbrl.xbrl import XBRL


@dataclass
class CandidateConcept:
    """A candidate concept for a target metric."""
    concept: str           # Full concept name (e.g., "us-gaap:Revenue")
    source: str           # "calc_tree" | "facts" | "both" | "value_match"
    confidence: float     # 0.0 - 1.0
    reasoning: str        # Why this matched
    tree_context: Optional[Dict] = None  # Parent, weight, etc. if from calc tree
    extracted_value: Optional[float] = None   # Actual value from SEC facts
    delta_pct: Optional[float] = None         # Variance from reference (%)


# Regex patterns for prefix stripping
# Handles both colon form (us-gaap:Revenue) and underscore form (us-gaap_Revenue)
NAMESPACE_PREFIX_PATTERN = re.compile(r'^(us-gaap[_:]|dei[_:]|ifrs-full[_:])')
COMPANY_PREFIX_PATTERN = re.compile(r'^[a-z]{2,5}_', re.IGNORECASE)


def strip_prefix(concept: str) -> str:
    """Strip namespace and company prefixes from a concept name."""
    result = NAMESPACE_PREFIX_PATTERN.sub('', concept)
    result = COMPANY_PREFIX_PATTERN.sub('', result)
    return result


def semantic_similarity(s1: str, s2: str) -> float:
    """Calculate semantic similarity between two strings."""
    # Convert to lowercase for comparison
    s1_lower = s1.lower()
    s2_lower = s2.lower()
    
    # Use SequenceMatcher for similarity
    ratio = SequenceMatcher(None, s1_lower, s2_lower).ratio()
    return ratio


def discover_concepts(
    metric_name: str,
    xbrl: Optional[XBRL] = None,
    facts_df=None,
    ticker: Optional[str] = None,
    known_concepts: Optional[List[str]] = None,
    top_k: int = 10,
    reference_value: Optional[float] = None,
) -> List[CandidateConcept]:
    """
    Search both calc trees AND facts for matching concepts.

    This is a REUSABLE TOOL for AI agents to use when static mapping fails.

    Args:
        metric_name: Target metric name (e.g., "IntangibleAssets", "Capex")
        xbrl: Optional XBRL object with calculation trees
        facts_df: Optional DataFrame from Company.get_facts().to_dataframe()
        ticker: Optional company ticker (will fetch facts_df if not provided)
        known_concepts: Optional list of known concept names to prioritize
        top_k: Maximum number of candidates to return
        reference_value: Optional reference value for reverse value search (O8).
            When provided, also searches for concepts whose extracted value
            matches this reference within tolerance.

    Returns:
        List of CandidateConcept, ranked by confidence
    """
    candidates = []
    found_concepts: Set[str] = set()

    # Search calculation trees
    if xbrl is not None:
        tree_candidates = _search_calc_trees(metric_name, xbrl, known_concepts)
        for c in tree_candidates:
            found_concepts.add(c.concept)
        candidates.extend(tree_candidates)

    # Search facts
    if facts_df is not None or ticker is not None:
        if facts_df is None and ticker is not None:
            # Fetch facts DataFrame
            try:
                company = Company(ticker)
                facts = company.get_facts()
                facts_df = facts.to_dataframe()
            except Exception as e:
                facts_df = None

        if facts_df is not None:
            facts_candidates = _search_facts(
                metric_name, facts_df, known_concepts, found_concepts
            )
            for c in facts_candidates:
                found_concepts.add(c.concept)
            candidates.extend(facts_candidates)

    # O8: Reverse value search — find concepts by matching extracted value
    if reference_value is not None and facts_df is not None and abs(reference_value) > 0:
        value_candidates = _search_by_value(reference_value, facts_df, found_concepts)
        candidates.extend(value_candidates)

    # Sort by confidence and return top_k
    candidates.sort(key=lambda x: x.confidence, reverse=True)
    return candidates[:top_k]


def _search_by_value(
    reference_value: float,
    facts_df: pd.DataFrame,
    already_found: Set[str],
    tolerance_pct: float = 20.0,
) -> List[CandidateConcept]:
    """O8: Reverse value search — find concepts whose extracted value matches reference.

    Searches the facts DataFrame for concepts with numeric values close to the
    reference value. Pure vectorized DataFrame filter — ~10ms for ~5000 concepts,
    zero API calls.

    Args:
        reference_value: The target value to match (e.g., from yfinance).
        facts_df: DataFrame from Company.get_facts().to_dataframe().
        already_found: Concepts already found by name-based search (excluded).
        tolerance_pct: Maximum allowed variance percentage (default 20%).

    Returns:
        List of CandidateConcept with source="value_match".
    """
    candidates = []
    try:
        df = facts_df
        # Filter for FY period and non-null numeric values
        has_period = 'fiscal_period' in df.columns
        has_value = 'numeric_value' in df.columns
        if not has_value:
            return candidates

        if has_period:
            df = df[df['fiscal_period'] == 'FY']
        df = df[df['numeric_value'].notna()]

        if df.empty:
            return candidates

        # Group by concept, take latest fiscal_year per concept
        if 'fiscal_year' in df.columns:
            idx = df.groupby('concept')['fiscal_year'].idxmax()
            df = df.loc[idx]
        else:
            df = df.drop_duplicates(subset='concept', keep='last')

        # Compute variance
        abs_ref = abs(reference_value)
        df = df.copy()
        df['_variance'] = (df['numeric_value'] - reference_value).abs() / abs_ref * 100

        # Keep rows within tolerance
        df = df[df['_variance'] <= tolerance_pct]

        # Exclude already-found concepts
        if already_found:
            df = df[~df['concept'].isin(already_found)]

        # Sort by variance ascending (closest match first)
        df = df.sort_values('_variance')

        for _, row in df.iterrows():
            variance = row['_variance']
            value = float(row['numeric_value'])

            # Map confidence by variance band
            if variance < 2.0:
                confidence = 0.95
            elif variance < 10.0:
                confidence = 0.80
            else:
                confidence = 0.65

            candidates.append(CandidateConcept(
                concept=row['concept'],
                source="value_match",
                confidence=confidence,
                reasoning=f"Value match: extracted={value:,.0f}, ref={reference_value:,.0f}, delta={variance:.1f}%",
                extracted_value=value,
                delta_pct=round(variance, 2),
            ))

    except Exception:
        pass

    return candidates


def _search_calc_trees(
    metric_name: str,
    xbrl: XBRL,
    known_concepts: Optional[List[str]] = None
) -> List[CandidateConcept]:
    """Search calculation trees for matching concepts.

    Uses xbrl.calculation_trees (Dict[str, CalculationTree]) where each tree
    has .all_nodes (Dict[str, CalculationNode]) with element_id, weight,
    parent, and children attributes.
    """
    candidates = []

    try:
        # Check that calculation_trees exist
        if not hasattr(xbrl, 'calculation_trees') or not xbrl.calculation_trees:
            return candidates

        # Get all concepts from all calc trees
        all_concepts = {}

        for role_uri, tree in xbrl.calculation_trees.items():
            # Derive a short statement label from the role URI
            role_label = role_uri.split('/')[-1] if '/' in role_uri else role_uri

            for concept_name, node in tree.all_nodes.items():
                # concept_name is like "us-gaap_OperatingIncomeLoss" or "us-gaap:Revenue"
                all_concepts[concept_name] = {
                    'statement': role_label,
                    'parent': node.parent,
                    'weight': node.weight,
                    'role_uri': role_uri,
                }

        # Score each concept
        for concept, context in all_concepts.items():
            stripped = strip_prefix(concept)

            # Check against known concepts first
            if known_concepts:
                for known in known_concepts:
                    if stripped.lower() == known.lower():
                        candidates.append(CandidateConcept(
                            concept=concept,
                            source="calc_tree",
                            confidence=0.98,
                            reasoning=f"Exact match with known concept: {known}",
                            tree_context=context
                        ))
                        break
                    elif known.lower() in stripped.lower():
                        candidates.append(CandidateConcept(
                            concept=concept,
                            source="calc_tree",
                            confidence=0.85,
                            reasoning=f"Partial match with known concept: {known}",
                            tree_context=context
                        ))
                        break

            # Check semantic similarity to metric name
            similarity = semantic_similarity(metric_name, stripped)
            if similarity > 0.5:
                # Avoid duplicates
                if not any(c.concept == concept for c in candidates):
                    candidates.append(CandidateConcept(
                        concept=concept,
                        source="calc_tree",
                        confidence=min(0.9, similarity),
                        reasoning=f"Semantic similarity: {similarity:.2f}",
                        tree_context=context
                    ))

    except Exception as e:
        pass

    return candidates


def _search_facts(
    metric_name: str,
    facts_df,
    known_concepts: Optional[List[str]] = None,
    already_found: Optional[Set[str]] = None
) -> List[CandidateConcept]:
    """Search facts DataFrame for matching concepts."""
    candidates = []
    already_found = already_found or set()
    
    try:
        # Get unique concepts from facts
        all_concepts = set(facts_df['concept'].unique())
        
        for concept in all_concepts:
            # Skip if already found in calc trees
            if concept in already_found:
                continue
                
            stripped = strip_prefix(concept)
            
            # Check against known concepts first
            matched = False
            if known_concepts:
                for known in known_concepts:
                    if stripped.lower() == known.lower():
                        candidates.append(CandidateConcept(
                            concept=concept,
                            source="facts",
                            confidence=0.95,
                            reasoning=f"Exact match with known concept: {known}"
                        ))
                        matched = True
                        break
                    elif known.lower() in stripped.lower():
                        candidates.append(CandidateConcept(
                            concept=concept,
                            source="facts",
                            confidence=0.80,
                            reasoning=f"Partial match with known concept: {known}"
                        ))
                        matched = True
                        break
            
            if matched:
                continue
                
            # Check semantic similarity to metric name
            similarity = semantic_similarity(metric_name, stripped)
            if similarity > 0.5:
                candidates.append(CandidateConcept(
                    concept=concept,
                    source="facts",
                    confidence=min(0.85, similarity),
                    reasoning=f"Semantic similarity: {similarity:.2f}"
                ))
                    
    except Exception as e:
        pass
    
    return candidates


# Convenience function for quick testing
def discover(metric: str, ticker: str) -> List[CandidateConcept]:
    """Quick way to discover concepts for a metric+ticker."""
    from edgar import set_identity
    set_identity("Dev Gunning developer-gunning@gmail.com")
    use_local_storage(True)  # Use bulk data, no API calls

    try:
        company = Company(ticker)
        filing = list(company.get_filings(form='10-K'))[0]
        xbrl = filing.xbrl()
        facts = company.get_facts()
        facts_df = facts.to_dataframe()
        
        return discover_concepts(metric, xbrl, facts_df)
    except Exception as e:
        print(f"Error: {e}")
        return []
