"""
Cross-Company Mapping Learner Tool

REUSABLE TOOL FOR AI AGENTS

Runs mapping across multiple companies to discover patterns and 
automatically expand known_concepts lists.

Usage by AI Agent:
    from edgar.xbrl.standardization.tools.learn_mappings import learn_mappings
    
    result = learn_mappings("IntangibleAssets", ["AAPL", "GOOG", "AMZN"])
    print(f"New concepts to add: {result.new_concept_variants}")
"""

import re
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field

from edgar import Company, set_identity, use_local_storage


@dataclass
class LearningResult:
    """Result of learning mappings across companies."""
    metric: str
    companies_analyzed: List[str]
    successful_mappings: Dict[str, str]  # ticker -> concept
    failed_companies: Dict[str, str]     # ticker -> reason
    new_concept_variants: List[str]      # concepts to add to known_concepts
    patterns_found: List[str]            # patterns discovered
    summary: str


# Regex patterns for prefix stripping
NAMESPACE_PREFIX_PATTERN = re.compile(r'^(us-gaap:|dei:|ifrs-full:)')
COMPANY_PREFIX_PATTERN = re.compile(r'^[a-z]{2,5}_', re.IGNORECASE)


def strip_prefix(concept: str) -> str:
    """Strip namespace and company prefixes from a concept name."""
    result = NAMESPACE_PREFIX_PATTERN.sub('', concept)
    result = COMPANY_PREFIX_PATTERN.sub('', result)
    return result


def learn_mappings(
    metric: str,
    tickers: List[str],
    existing_known_concepts: Optional[List[str]] = None
) -> LearningResult:
    """
    Run mapping across companies to discover patterns.
    
    This is a REUSABLE TOOL for AI agents to expand known_concepts.
    
    Args:
        metric: Target metric name (e.g., "IntangibleAssets")
        tickers: List of company tickers to analyze
        existing_known_concepts: Optional list of already known concepts
        
    Returns:
        LearningResult with successful mappings, new variants, and patterns
    """
    set_identity("Dev Gunning developer-gunning@gmail.com")
    use_local_storage(True)  # Use bulk data, no API calls

    existing_known = set(existing_known_concepts) if existing_known_concepts else set()
    successful_mappings = {}
    failed_companies = {}
    discovered_concepts: Set[str] = set()
    
    for ticker in tickers:
        try:
            result = _analyze_company(ticker, metric)
            if result['success']:
                concept = result['concept']
                successful_mappings[ticker] = concept
                
                # Extract the base concept name (stripped)
                stripped = strip_prefix(concept)
                discovered_concepts.add(stripped)
            else:
                failed_companies[ticker] = result['reason']
        except Exception as e:
            failed_companies[ticker] = str(e)
    
    # Find new concepts not in existing known list
    new_variants = []
    for concept in discovered_concepts:
        if concept not in existing_known:
            new_variants.append(concept)
    
    # Find patterns
    patterns = _find_patterns(discovered_concepts)
    
    # Generate summary
    success_count = len(successful_mappings)
    total_count = len(tickers)
    summary = f"Analyzed {total_count} companies for '{metric}': {success_count} successful"
    
    if new_variants:
        summary += f", found {len(new_variants)} new concept variants"
    
    return LearningResult(
        metric=metric,
        companies_analyzed=tickers,
        successful_mappings=successful_mappings,
        failed_companies=failed_companies,
        new_concept_variants=new_variants,
        patterns_found=patterns,
        summary=summary
    )


def _analyze_company(ticker: str, metric: str) -> Dict:
    """Analyze a single company for a metric."""
    try:
        company = Company(ticker)
        filing = list(company.get_filings(form='10-K'))[0]
        xbrl = filing.xbrl()
        facts = company.get_facts()
        facts_df = facts.to_dataframe()
        
        # Search for matching concepts
        from .discover_concepts import discover_concepts
        
        candidates = discover_concepts(metric, xbrl, facts_df, top_k=5)
        
        if candidates:
            best = candidates[0]
            return {
                'success': True,
                'concept': best.concept,
                'confidence': best.confidence,
                'source': best.source
            }
        else:
            return {
                'success': False,
                'reason': 'No matching concepts found'
            }
            
    except Exception as e:
        return {
            'success': False,
            'reason': str(e)
        }


def _find_patterns(concepts: Set[str]) -> List[str]:
    """Find common patterns in discovered concepts."""
    patterns = []
    
    # Check for common suffixes
    suffixes = ['Net', 'Gross', 'Loss', 'Income', 'Expense', 'Current', 'Noncurrent']
    for suffix in suffixes:
        matching = [c for c in concepts if c.endswith(suffix)]
        if len(matching) > 1:
            patterns.append(f"Multiple concepts end with '{suffix}': {', '.join(matching)}")
    
    # Check for common prefixes
    if len(concepts) > 1:
        # Find common prefix
        sorted_concepts = sorted(concepts)
        first = sorted_concepts[0]
        last = sorted_concepts[-1]
        
        common_prefix = ""
        for i, c in enumerate(first):
            if i < len(last) and c == last[i]:
                common_prefix += c
            else:
                break
        
        if len(common_prefix) > 5:
            patterns.append(f"Common prefix found: '{common_prefix}'")
    
    return patterns


# Convenience function for quick testing
def learn(metric: str, tickers: List[str] = None) -> LearningResult:
    """Quick way to learn mappings."""
    if tickers is None:
        tickers = ['AAPL', 'GOOG', 'AMZN', 'MSFT', 'META', 'NVDA', 'TSLA']
    return learn_mappings(metric, tickers)
