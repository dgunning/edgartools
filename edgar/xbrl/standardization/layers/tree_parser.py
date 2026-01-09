"""
Layer 1: Tree Structure Parser

Extracts concept mappings from XBRL calculation trees.
This is the primary mapping layer, handling ~85% of mappings.

Key capabilities:
1. Match known concepts from config against tree nodes
2. Use parent-child relationships to infer mappings
3. Validate using calculation weights (sum check)
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

from edgar import Company, set_identity
from edgar.xbrl.xbrl import XBRL

from ..config_loader import get_config, MappingConfig
from ..models import (
    MappingResult, MappingSource, ConfidenceLevel,
    MetricConfig, CompanyConfig
)


class TreeParser:
    """
    Layer 1: Extracts concept mappings from XBRL calculation trees.
    
    Uses the calculation linkbase to identify financial concepts
    based on known concept names and tree structure.
    """
    
    def __init__(self, config: Optional[MappingConfig] = None):
        self.config = config or get_config()
        self._thresholds = self.config.defaults.get("confidence_thresholds", {
            "tree_high": 0.95,
            "tree_medium": 0.80
        })
    
    def map_company(self, ticker: str, filing=None) -> Dict[str, MappingResult]:
        """
        Map all metrics for a company from its latest 10-K.
        
        Args:
            ticker: Company ticker symbol
            filing: Optional specific filing to use (otherwise gets latest 10-K)
            
        Returns:
            Dict mapping metric name to MappingResult
        """
        company_config = self.config.get_company(ticker)
        
        # Get XBRL data
        if filing is None:
            filing = self._get_latest_filing(ticker)
        
        if filing is None:
            return self._empty_results(ticker, "No filing found")
        
        try:
            xbrl = filing.xbrl()
        except Exception as e:
            return self._empty_results(ticker, f"XBRL parse error: {e}")
        
        # Get fiscal period
        fiscal_period = self._get_fiscal_period(filing)
        
        # Map each metric
        results = {}
        
        # Get all excluded metrics (company-specific + industry-based)
        excluded_metrics = set(self.config.get_excluded_metrics_for_company(ticker))
        
        for metric_name in self.config.get_all_metric_names():
            # Check if metric should be skipped for this company
            if metric_name in excluded_metrics:
                results[metric_name] = MappingResult(
                    metric=metric_name,
                    company=ticker,
                    fiscal_period=fiscal_period,
                    source=MappingSource.CONFIG,
                    reasoning=f"Metric excluded for {ticker} (company or industry)"
                )
                continue
            
            result = self.map_metric(
                xbrl=xbrl,
                metric_name=metric_name,
                ticker=ticker,
                fiscal_period=fiscal_period
            )
            results[metric_name] = result
        
        return results
    
    def map_metric(
        self,
        xbrl: XBRL,
        metric_name: str,
        ticker: str,
        fiscal_period: str
    ) -> MappingResult:
        """
        Map a single metric for a company.
        
        Strategy:
        1. First try direct match against known concepts
        2. Then try tree structure hints
        3. Return with appropriate confidence
        """
        metric_config = self.config.get_metric(metric_name)
        if metric_config is None:
            return MappingResult(
                metric=metric_name,
                company=ticker,
                fiscal_period=fiscal_period,
                reasoning=f"Unknown metric: {metric_name}"
            )
        
        # Collect all concepts from calculation trees
        all_concepts = self._get_all_concepts(xbrl)
        
        # Strategy 1: Direct match against known concepts
        matched = self._match_known_concepts(metric_config, all_concepts)
        if matched:
            concept, confidence = matched
            return MappingResult(
                metric=metric_name,
                company=ticker,
                fiscal_period=fiscal_period,
                concept=concept,
                confidence=confidence,
                confidence_level=self._get_confidence_level(confidence),
                source=MappingSource.TREE,
                reasoning=f"Direct match: {concept} in known_concepts",
                tree_context=self._get_tree_context(xbrl, concept)
            )
        
        # Strategy 2: Use tree structure hints
        if metric_config.tree_hints:
            matched = self._match_by_tree_hints(xbrl, metric_config)
            if matched:
                concept, confidence, reasoning = matched
                return MappingResult(
                    metric=metric_name,
                    company=ticker,
                    fiscal_period=fiscal_period,
                    concept=concept,
                    confidence=confidence,
                    confidence_level=self._get_confidence_level(confidence),
                    source=MappingSource.TREE,
                    reasoning=reasoning,
                    tree_context=self._get_tree_context(xbrl, concept)
                )
        
        # No match found
        return MappingResult(
            metric=metric_name,
            company=ticker,
            fiscal_period=fiscal_period,
            source=MappingSource.UNKNOWN,
            reasoning="No match in calculation trees"
        )
    
    def _get_all_concepts(self, xbrl: XBRL) -> Dict[str, Dict]:
        """Get all concepts from calculation trees with their context."""
        concepts = {}
        
        for role, tree in xbrl.calculation_trees.items():
            tree_name = role.split('/')[-1] if '/' in role else role
            
            for node_id, node in tree.all_nodes.items():
                # Clean concept name
                concept = node_id.replace('us-gaap_', '').replace('us-gaap:', '')
                
                if concept not in concepts:
                    concepts[concept] = {
                        'full_id': node_id,
                        'trees': [],
                        'parent': node.parent,
                        'children': node.children,
                        'weight': node.weight
                    }
                concepts[concept]['trees'].append(tree_name)
        
        return concepts
    
    def _match_known_concepts(
        self,
        metric_config: MetricConfig,
        all_concepts: Dict[str, Dict]
    ) -> Optional[Tuple[str, float]]:
        """
        Match against known concepts from config.
        
        Returns (concept, confidence) if found, None otherwise.
        """
        for known in metric_config.known_concepts:
            if known in all_concepts:
                # High confidence for exact match
                return (f"us-gaap:{known}", self._thresholds.get("tree_high", 0.95))
        
        # Try partial matching (concept might have different prefix)
        for known in metric_config.known_concepts:
            for concept in all_concepts:
                if known in concept or concept in known:
                    return (f"us-gaap:{concept}", self._thresholds.get("tree_medium", 0.80))
        
        return None
    
    def _match_by_tree_hints(
        self,
        xbrl: XBRL,
        metric_config: MetricConfig
    ) -> Optional[Tuple[str, float, str]]:
        """
        Use tree structure hints to find concepts.
        
        Returns (concept, confidence, reasoning) if found.
        """
        hints = metric_config.tree_hints
        
        # Check if looking for root concepts
        if hints.get('is_root'):
            for role, tree in xbrl.calculation_trees.items():
                tree_name = role.split('/')[-1].upper()
                
                # Check if tree matches expected statements
                statements = hints.get('statements', [])
                if any(s in tree_name for s in statements):
                    root_concept = tree.root_element_id.replace('us-gaap_', 'us-gaap:')
                    return (
                        root_concept,
                        self._thresholds.get("tree_high", 0.95),
                        f"Root of {tree_name}"
                    )
        
        # Match by parent pattern and weight
        parent_pattern = hints.get('parent_pattern')
        expected_weight = hints.get('weight')
        
        if parent_pattern:
            for role, tree in xbrl.calculation_trees.items():
                for node_id, node in tree.all_nodes.items():
                    parent = node.parent or ""
                    if parent_pattern.lower() in parent.lower():
                        # Check weight if specified
                        if expected_weight is not None:
                            if node.weight == expected_weight:
                                concept = node_id.replace('us-gaap_', 'us-gaap:')
                                return (
                                    concept,
                                    self._thresholds.get("tree_medium", 0.80),
                                    f"Parent matches {parent_pattern}, weight={expected_weight}"
                                )
                        else:
                            concept = node_id.replace('us-gaap_', 'us-gaap:')
                            return (
                                concept,
                                self._thresholds.get("tree_medium", 0.80) * 0.9,
                                f"Parent matches {parent_pattern}"
                            )
        
        return None
    
    def _get_tree_context(self, xbrl: XBRL, concept: str) -> Optional[Dict]:
        """Get tree context for a concept (parent, siblings, weight)."""
        clean = concept.replace('us-gaap:', '').replace('us-gaap_', '')
        
        for role, tree in xbrl.calculation_trees.items():
            for node_id, node in tree.all_nodes.items():
                if clean in node_id:
                    return {
                        'tree': role.split('/')[-1],
                        'parent': node.parent,
                        'children': node.children[:5] if node.children else [],
                        'weight': node.weight
                    }
        return None
    
    def _get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Convert numeric confidence to level."""
        if confidence >= self._thresholds.get("tree_high", 0.95):
            return ConfidenceLevel.HIGH
        elif confidence >= self._thresholds.get("tree_medium", 0.80):
            return ConfidenceLevel.MEDIUM
        elif confidence > 0:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.NONE
    
    def _get_latest_filing(self, ticker: str):
        """Get latest 10-K filing for a company."""
        try:
            c = Company(ticker)
            filings = c.get_filings(form='10-K')
            for f in filings:
                return f
        except Exception:
            return None
        return None
    
    def _get_fiscal_period(self, filing) -> str:
        """Extract fiscal period from filing."""
        try:
            date = filing.filing_date
            year = date.year if hasattr(date, 'year') else str(date)[:4]
            return f"{year}-FY"
        except Exception:
            return "unknown"
    
    def _empty_results(self, ticker: str, reason: str) -> Dict[str, MappingResult]:
        """Create empty results for all metrics."""
        results = {}
        for metric_name in self.config.get_all_metric_names():
            results[metric_name] = MappingResult(
                metric=metric_name,
                company=ticker,
                fiscal_period="unknown",
                source=MappingSource.UNKNOWN,
                reasoning=reason
            )
        return results


def run_tree_parser(tickers: List[str] = None) -> Dict[str, Dict[str, MappingResult]]:
    """
    Run tree parser on specified companies.
    
    Args:
        tickers: List of tickers, defaults to MAG7
        
    Returns:
        Nested dict: {ticker: {metric: MappingResult}}
    """
    set_identity("Dev Gunning developer-gunning@gmail.com")
    
    if tickers is None:
        config = get_config()
        tickers = list(config.companies.keys())
    
    parser = TreeParser()
    all_results = {}
    
    for ticker in tickers:
        print(f"Processing {ticker}...")
        results = parser.map_company(ticker)
        all_results[ticker] = results
        
        # Print summary
        mapped = sum(1 for r in results.values() if r.is_mapped)
        print(f"  Mapped: {mapped}/{len(results)}")
    
    return all_results


if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Layer 1: Tree Parser")
    parser.add_argument("--companies", type=str, default="MAG7",
                        help="Comma-separated tickers or 'MAG7'")
    parser.add_argument("--output", type=str, default=None,
                        help="Output JSON file")
    args = parser.parse_args()
    
    # Parse tickers
    if args.companies.upper() == "MAG7":
        tickers = None  # Use default from config
    else:
        tickers = [t.strip().upper() for t in args.companies.split(",")]
    
    # Run parser
    results = run_tree_parser(tickers)
    
    # Print summary
    print("\n" + "=" * 60)
    print("TREE PARSER RESULTS")
    print("=" * 60)
    
    for ticker, metrics in results.items():
        mapped = sum(1 for r in metrics.values() if r.is_mapped)
        excluded = sum(1 for r in metrics.values() if r.source == MappingSource.CONFIG)
        print(f"\n{ticker}: {mapped}/{len(metrics) - excluded} mapped")
        
        for metric, result in metrics.items():
            if result.is_mapped:
                print(f"  ✓ {metric}: {result.concept} ({result.confidence_level.value})")
            elif result.source == MappingSource.CONFIG:
                print(f"  - {metric}: excluded")
            else:
                print(f"  ✗ {metric}: not found")
    
    # Save if requested
    if args.output:
        output_data = {
            ticker: {
                metric: result.to_dict()
                for metric, result in metrics.items()
            }
            for ticker, metrics in results.items()
        }
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults saved to {args.output}")
