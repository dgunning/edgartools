"""
Layer 1: Tree Structure Parser

Extracts concept mappings from XBRL calculation trees.
This is the primary mapping layer, handling ~85% of mappings.

Key capabilities:
1. Match known concepts from config against tree nodes
2. Use parent-child relationships to infer mappings
3. Validate using calculation weights (sum check)
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

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
    
    def map_company(self, ticker: str, filing=None, xbrl=None) -> Dict[str, MappingResult]:
        """
        Map all metrics for a company from its latest 10-K.

        Args:
            ticker: Company ticker symbol
            filing: Optional specific filing to use (otherwise gets latest 10-K)
            xbrl: Optional pre-parsed XBRL object (avoids redundant parsing)

        Returns:
            Dict mapping metric name to MappingResult
        """
        company_config = self.config.get_company(ticker)

        # Get XBRL data
        if filing is None:
            filing = self._get_latest_filing(ticker)

        if filing is None:
            return self._empty_results(ticker, "No filing found")

        if xbrl is None:
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

        Strategy (ENE Layered Approach):
        0. Check company-specific preferred_concept override
        1. First try direct match against known concepts in calculation trees
        2. Then try tree structure hints
        3. Fall back to facts-based search (concepts may exist in facts but not calc trees)
        4. Return with appropriate confidence
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

        # === Strategy 0: Company-specific preferred concept override ===
        company_config = self.config.get_company(ticker)
        if company_config and metric_name in company_config.metric_overrides:
            override = company_config.metric_overrides[metric_name]
            preferred = override.get('preferred_concept')
            if preferred:
                # Support both single string and list of fallback concepts
                preferred_list = preferred if isinstance(preferred, list) else [preferred]

                # Phase 1: Cheap calc-tree lookup (O(1) dict check per pref)
                for pref in preferred_list:
                    pref_clean = pref.split(':')[-1] if ':' in pref else pref
                    if pref_clean in all_concepts:
                        concept_ref = pref if ':' in pref else f"us-gaap:{pref}"
                        return MappingResult(
                            metric=metric_name,
                            company=ticker,
                            fiscal_period=fiscal_period,
                            concept=concept_ref,
                            confidence=0.98,
                            confidence_level=ConfidenceLevel.HIGH,
                            source=MappingSource.OVERRIDE,
                            reasoning=f"Company override: preferred_concept={pref}",
                            tree_context=self._get_tree_context(xbrl, pref_clean)
                        )

                # Phase 2: Facts lookup (only if no calc-tree hit)
                for pref in preferred_list:
                    matched = self._verify_concept_in_facts(xbrl, pref)
                    if matched:
                        return MappingResult(
                            metric=metric_name,
                            company=ticker,
                            fiscal_period=fiscal_period,
                            concept=matched,
                            confidence=0.95,
                            confidence_level=ConfidenceLevel.HIGH,
                            source=MappingSource.OVERRIDE,
                            reasoning=f"Company override (facts-verified): preferred_concept={pref}"
                        )

                # Hard failure: do not silently fall through to Strategy 1
                logger.warning(
                    "Strategy 0 MISS: preferred_concept=%s not found in "
                    "calc trees or facts for %s:%s",
                    preferred_list, ticker, metric_name
                )
                return MappingResult(
                    metric=metric_name,
                    company=ticker,
                    fiscal_period=fiscal_period,
                    confidence_level=ConfidenceLevel.INVALID,
                    source=MappingSource.OVERRIDE,
                    reasoning=f"Override MISS: preferred_concept={preferred_list} not in calc trees or facts"
                )

        # Strategy 1: Direct match against known concepts
        # IMPORTANT: Skip direct matching for composite metrics - they require aggregation
        # of multiple components (e.g., ShortTermDebt = LongTermDebtCurrent + CommercialPaper + ShortTermBorrowings)
        # Matching a single component would return incomplete data
        if not metric_config.is_composite:
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

        # Strategy 3: Facts-based fallback (ENE enhancement)
        # Handles concepts that exist in XBRL facts but not in calculation trees
        # (e.g., standalone disclosures, cash flow items)
        matched = self._match_from_facts(xbrl, metric_config)
        if matched:
            concept, confidence = matched
            return MappingResult(
                metric=metric_name,
                company=ticker,
                fiscal_period=fiscal_period,
                concept=concept,
                confidence=confidence,
                confidence_level=self._get_confidence_level(confidence),
                source=MappingSource.TREE,  # Still TREE source (Layer 1)
                reasoning=f"Facts fallback: {concept} found in XBRL facts"
            )

        # No match found
        return MappingResult(
            metric=metric_name,
            company=ticker,
            fiscal_period=fiscal_period,
            source=MappingSource.UNKNOWN,
            reasoning="No match in calculation trees or facts"
        )
    
    def _get_all_concepts(self, xbrl: XBRL) -> Dict[str, Dict]:
        """Get all concepts from calculation trees with their context including balance type."""
        concepts = {}
        
        for role, tree in xbrl.calculation_trees.items():
            tree_name = role.split('/')[-1] if '/' in role else role
            
            for node_id, node in tree.all_nodes.items():
                # Clean concept name
                concept = node_id.replace('us-gaap_', '').replace('us-gaap:', '')
                
                if concept not in concepts:
                    # Get balance type for signage normalization
                    balance_type = self._get_balance_type(concept)
                    
                    concepts[concept] = {
                        'full_id': node_id,
                        'trees': [],
                        'parent': node.parent,
                        'children': node.children,
                        'weight': node.weight,
                        'balance': balance_type  # NEW: 'debit' or 'credit' for signage
                    }
                concepts[concept]['trees'].append(tree_name)
        
        return concepts
    
    def _get_balance_type(self, concept: str) -> Optional[str]:
        """
        Get balance type (debit/credit) for signage normalization.
        
        XBRL Balance Types:
        - Debit: Assets, Expenses, Losses (increase with debits)
        - Credit: Liabilities, Equity, Revenue, Gains (increase with credits)
        
        This is crucial for correctly calculating formulas:
        - GrossProfit = Revenue (credit) - COGS (debit)
        - When XBRL reports COGS with negative sign (credit memo), we need to normalize
        """
        # Known balance types for common financial concepts
        # Based on US-GAAP taxonomy definitions
        KNOWN_BALANCE_TYPES = {
            # Revenue and Gains (Credit)
            'Revenues': 'credit',
            'RevenueFromContractWithCustomerExcludingAssessedTax': 'credit',
            'SalesRevenueNet': 'credit',
            'NetIncomeLoss': 'credit',
            'GrossProfit': 'credit',
            'OperatingIncomeLoss': 'credit',
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxes': 'credit',
            'ComprehensiveIncomeNetOfTax': 'credit',
            'InterestIncomeExpenseNet': 'credit',
            'NetInterestIncome': 'credit',
            'NoninterestIncome': 'credit',
            'GainLossOnSaleOfPropertyPlantEquipment': 'credit',
            'OtherIncome': 'credit',
            
            # Expenses and Losses (Debit)
            'CostOfRevenue': 'debit',
            'CostOfGoodsAndServicesSold': 'debit',
            'CostOfGoodsSold': 'debit',
            'SellingGeneralAndAdministrativeExpense': 'debit',
            'ResearchAndDevelopmentExpense': 'debit',
            'DepreciationAndAmortization': 'debit',
            'InterestExpense': 'debit',
            'IncomeTaxExpenseBenefit': 'debit',
            'NoninterestExpense': 'debit',
            'OperatingExpenses': 'debit',
            'OtherExpenses': 'debit',
            
            # Assets (Debit)
            'Assets': 'debit',
            'AssetsCurrent': 'debit',
            'CashAndCashEquivalentsAtCarryingValue': 'debit',
            'AccountsReceivableNetCurrent': 'debit',
            'Inventory': 'debit',
            'PropertyPlantAndEquipmentNet': 'debit',
            'Goodwill': 'debit',
            'IntangibleAssetsNetExcludingGoodwill': 'debit',
            
            # Liabilities (Credit)
            'Liabilities': 'credit',
            'LiabilitiesCurrent': 'credit',
            'AccountsPayableCurrent': 'credit',
            'LongTermDebt': 'credit',
            'LongTermDebtCurrent': 'credit',
            'ShortTermBorrowings': 'credit',
            'CommercialPaper': 'credit',
            'DeferredRevenue': 'credit',
            'ContractWithCustomerLiabilityCurrent': 'credit',
            
            # Equity (Credit)
            'StockholdersEquity': 'credit',
            'RetainedEarningsAccumulatedDeficit': 'credit',
            'CommonStockValue': 'credit',
            'AdditionalPaidInCapital': 'credit',
            
            # Cash Flow (Mixed - depends on nature)
            'NetCashProvidedByUsedInOperatingActivities': 'debit',
            'PaymentsToAcquirePropertyPlantAndEquipment': 'credit',  # Cash outflow
            'DepreciationDepletionAndAmortization': 'debit',
        }
        
        return KNOWN_BALANCE_TYPES.get(concept)
    
    def _match_known_concepts(
        self,
        metric_config: MetricConfig,
        all_concepts: Dict[str, Dict]
    ) -> Optional[Tuple[str, float]]:
        """
        Match against known concepts from config.

        Returns (concept, confidence) if found, None otherwise.

        Respects exclude_patterns to avoid matching wrong concepts
        (e.g., AccumulatedDepreciation when looking for Depreciation).
        """
        exclude = metric_config.exclude_patterns or []

        # Helper to check if concept should be excluded
        def should_exclude(concept_name: str) -> bool:
            concept_lower = concept_name.lower()
            return any(ex.lower() in concept_lower for ex in exclude)

        # Exact match against known concepts (highest confidence)
        for known in metric_config.known_concepts:
            if known in all_concepts:
                # Check exclusion patterns
                if should_exclude(known):
                    continue
                # High confidence for exact match
                return (f"us-gaap:{known}", self._thresholds.get("tree_high", 0.95))

        # Try partial matching (concept might have different prefix)
        for known in metric_config.known_concepts:
            for concept in all_concepts:
                # Check exclusion patterns first
                if should_exclude(concept):
                    continue
                # Forward: known is substring of concept (e.g., "Revenue" in "RevenueNet")
                # Guard: known must cover at least 40% of concept length to prevent
                # short strings matching much longer concepts (e.g., "Revenues" (8 chars)
                # should NOT match "RevenueFromContractWithCustomerExcludingAssessedTax" (52 chars))
                if known in concept and len(known) >= len(concept) * 0.4:
                    return (f"us-gaap:{concept}", self._thresholds.get("tree_medium", 0.80))
                # Reverse: concept is substring of known — only if concept is specific enough
                # Prevents short concepts like "Assets" matching "PaymentsToAcquirePropertyPlantAndEquipment"
                if concept in known and len(concept) >= 15:
                    return (f"us-gaap:{concept}", self._thresholds.get("tree_medium", 0.80))

        return None

    def _match_from_facts(
        self,
        xbrl: XBRL,
        metric_config: MetricConfig,
    ) -> Optional[Tuple[str, float]]:
        """
        Fallback: Match against XBRL facts when calculation tree search fails.

        ENE Spirit: Concepts may exist in facts but not in calculation trees.
        This handles balance sheet items, standalone disclosures (e.g., weighted
        average shares), and cash flow items (e.g., stock-based compensation,
        dividends paid).

        Respects exclude_patterns to avoid matching wrong concepts.

        Returns (concept, confidence) if found, None otherwise.
        """
        if not xbrl or not hasattr(xbrl, 'facts') or xbrl.facts is None:
            return None

        try:
            facts_df = xbrl.facts.to_dataframe()
            if facts_df is None or len(facts_df) == 0:
                return None

            # Get available concepts from facts
            available_concepts = set()
            if 'concept' in facts_df.columns:
                for c in facts_df['concept'].dropna().unique():
                    # Normalize: remove namespace prefix
                    clean = c.split(':')[-1] if ':' in c else c
                    available_concepts.add(clean)

            # Get exclusion patterns
            exclude = metric_config.exclude_patterns or []

            def should_exclude(concept_name: str) -> bool:
                concept_lower = concept_name.lower()
                return any(ex.lower() in concept_lower for ex in exclude)

            # Try each known concept from config (in priority order)
            for known in metric_config.known_concepts:
                # Check exclusion patterns
                if should_exclude(known):
                    continue

                # Direct match in facts
                if known in available_concepts:
                    return (f"us-gaap:{known}", 0.85)  # Slightly lower confidence

                # Case-insensitive match
                known_lower = known.lower()
                for concept in available_concepts:
                    # Check exclusion for matched concept
                    if should_exclude(concept):
                        continue
                    if concept.lower() == known_lower:
                        return (f"us-gaap:{concept}", 0.80)

            return None

        except Exception:
            return None
    
    def _verify_concept_in_facts(
        self,
        xbrl: XBRL,
        concept_name: str,
    ) -> Optional[str]:
        """
        Verify a specific concept exists in XBRL facts.

        Checks both us-gaap: and company-extension namespaces.
        Returns the full namespaced concept string if found, None otherwise.
        """
        if not xbrl or not hasattr(xbrl, 'facts') or xbrl.facts is None:
            return None

        try:
            facts_df = xbrl.facts.to_dataframe()
            if facts_df is None or len(facts_df) == 0:
                return None

            if 'concept' not in facts_df.columns:
                return None

            # Get all unique concepts from facts
            fact_concepts = facts_df['concept'].dropna().unique()

            # Check for exact match (with or without namespace)
            for fc in fact_concepts:
                clean = fc.split(':')[-1] if ':' in fc else fc
                target_clean = concept_name.split(':')[-1] if ':' in concept_name else concept_name
                if clean == target_clean:
                    return fc  # Return with original namespace (e.g., "cop:PaymentTo...")

            return None

        except Exception:
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
