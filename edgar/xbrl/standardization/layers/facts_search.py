"""
Layer 4: Facts Search

Searches XBRL facts directly when concepts aren't in calculation trees.
This is a fallback for concepts that exist in filings but aren't in calc linkbase.

Key insight: Calculation trees are just ONE way XBRL organizes data.
Facts can exist independently of calculation relationships.
"""

import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from edgar import Company, set_identity

from ..config_loader import get_config, MappingConfig
from ..models import (
    MappingResult, MappingSource, ConfidenceLevel,
    MetricConfig
)

# Regex pattern to strip namespace prefixes (us-gaap:, dei:) and company prefixes (nvda_, tsla_, etc.)
# Company prefixes are typically 2-5 lowercase letters followed by underscore
NAMESPACE_PREFIX_PATTERN = re.compile(r'^(us-gaap:|dei:|ifrs-full:)')
COMPANY_PREFIX_PATTERN = re.compile(r'^[a-z]{2,5}_', re.IGNORECASE)


class FactsSearcher:
    """
    Layer 4: Search XBRL facts directly for unmapped concepts.
    
    Used when calculation trees don't contain the concept.
    """
    
    def __init__(self, config: Optional[MappingConfig] = None):
        self.config = config or get_config()
        self._thresholds = self.config.defaults.get("confidence_thresholds", {
            "tree_high": 0.95,
            "tree_medium": 0.80
        })
    
    def search_gaps(
        self,
        results: Dict[str, MappingResult],
        ticker: str,
        fiscal_period: str
    ) -> Dict[str, MappingResult]:
        """
        Search XBRL facts for concepts that weren't found in calc trees.
        
        Args:
            results: Results from previous layers
            ticker: Company ticker
            fiscal_period: Fiscal period for logging
            
        Returns:
            Updated results with facts-based mappings
        """
        # Find gaps
        gaps = [
            metric for metric, result in results.items()
            if not result.is_mapped and result.source != MappingSource.CONFIG
        ]
        
        if not gaps:
            return results
        
        print(f"  Facts searching {len(gaps)} gaps: {gaps}")
        
        # Get company facts
        try:
            c = Company(ticker)
            facts = c.get_facts()
            df = facts.to_dataframe()
            all_concepts = set(df['concept'].unique())
        except Exception as e:
            print(f"    Error getting facts: {e}")
            return results
        
        # Search for each gap
        updated = dict(results)
        
        for metric_name in gaps:
            metric_config = self.config.get_metric(metric_name)
            if metric_config is None:
                continue
            
            # Try to find matching concept in facts
            matched = self._search_facts(metric_config, all_concepts)
            
            if matched:
                concept, confidence, reasoning = matched
                updated[metric_name] = MappingResult(
                    metric=metric_name,
                    company=ticker,
                    fiscal_period=fiscal_period,
                    concept=concept,
                    confidence=confidence,
                    confidence_level=self._get_confidence_level(confidence),
                    source=MappingSource.TREE,  # Mark as TREE since it's from XBRL
                    reasoning=f"Found in facts (not in calc tree): {reasoning}"
                )
                print(f"    ✓ {metric_name}: {concept}")
        
        return updated
    
    def _search_facts(
        self,
        metric_config: MetricConfig,
        all_concepts: set
    ) -> Optional[Tuple[str, float, str]]:
        """
        Search XBRL facts for a metric's known concepts.
        
        Returns (concept, confidence, reasoning) if found.
        """
        # Build a lookup: stripped_name -> original_concept
        stripped_lookup = {}
        for concept in all_concepts:
            stripped = self._strip_prefix(concept)
            stripped_lookup[stripped.lower()] = concept
        
        # Direct match against known concepts
        for known in metric_config.known_concepts:
            known_lower = known.lower()
            
            # Try with us-gaap prefix
            full_concept = f"us-gaap:{known}"
            if full_concept in all_concepts:
                return (
                    full_concept,
                    self._thresholds.get("tree_high", 0.95),
                    f"Direct match: {known}"
                )
            
            # Try without prefix (already has it)
            if known in all_concepts:
                return (
                    known,
                    self._thresholds.get("tree_high", 0.95),
                    f"Direct match: {known}"
                )
            
            # Try matching against stripped concept names (handles company prefixes)
            if known_lower in stripped_lookup:
                original = stripped_lookup[known_lower]
                return (
                    original,
                    self._thresholds.get("tree_high", 0.95),
                    f"Prefix-stripped match: {known} -> {original}"
                )
        
        # Partial match (concept name contains known pattern)
        for known in metric_config.known_concepts:
            known_lower = known.lower()
            for stripped, original in stripped_lookup.items():
                if known_lower in stripped:
                    return (
                        original,
                        self._thresholds.get("tree_medium", 0.80),
                        f"Partial match with {known} (stripped: {stripped})"
                    )
        
        return None
    
    def _strip_prefix(self, concept: str) -> str:
        """
        Strip namespace and company prefixes from a concept name.
        
        Examples:
            us-gaap:Revenue -> Revenue
            nvda_PaymentsForFinanced... -> PaymentsForFinanced...
            tsla_LongTermDebt -> LongTermDebt
        """
        # First strip namespace prefix
        result = NAMESPACE_PREFIX_PATTERN.sub('', concept)
        # Then strip company prefix (e.g., nvda_, tsla_)
        result = COMPANY_PREFIX_PATTERN.sub('', result)
        return result
    
    def _get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Convert numeric confidence to level."""
        if confidence >= self._thresholds.get("tree_high", 0.95):
            return ConfidenceLevel.HIGH
        elif confidence >= self._thresholds.get("tree_medium", 0.80):
            return ConfidenceLevel.MEDIUM
        elif confidence > 0:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.NONE
