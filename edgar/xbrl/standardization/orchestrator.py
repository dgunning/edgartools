"""
Orchestrator for the multi-layer mapping architecture.

Runs all mapping layers in sequence with fallback:
Layer 1 (Tree) → Layer 2 (AI) → Layer 4 (Facts Search) → Validate
"""

import json
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from edgar import Company, set_identity, use_local_storage

from .config_loader import get_config, MappingConfig
from .models import MappingResult, MappingSource, AuditLogEntry
from .layers.tree_parser import TreeParser
from .layers.ai_semantic import AISemanticMapper
from .layers.facts_search import FactsSearcher
from .reference_validator import ReferenceValidator, ValidationResult


class Orchestrator:
    """
    Runs all mapping layers in sequence.
    """
    
    def __init__(self, config: Optional[MappingConfig] = None):
        self.config = config or get_config()
        self.tree_parser = TreeParser(self.config)
        self.ai_mapper = AISemanticMapper(self.config)
        self.facts_searcher = FactsSearcher(self.config)
        self.validator = ReferenceValidator(self.config)
        self.audit_log = []
        self.validation_results = {}
    
    def map_company(
        self,
        ticker: str,
        use_ai: bool = True,
        use_facts: bool = True,
        amendments: bool = False
    ) -> Dict[str, MappingResult]:
        """
        Map all metrics for a company using all available layers.
        
        Args:
            ticker: Company ticker
            use_ai: Whether to use Layer 2 AI for gaps
            use_facts: Whether to use Layer 4 Facts Search for gaps
            amendments: Whether to include amended filings
            
        Returns:
            Dict mapping metric name to MappingResult
        """
        # Get filing
        filing = self._get_filing(ticker, amendments)
        if filing is None:
            return self.tree_parser._empty_results(ticker, "No filing found")
        
        try:
            xbrl = filing.xbrl()
        except Exception as e:
            return self.tree_parser._empty_results(ticker, f"XBRL error: {e}")
        
        fiscal_period = self.tree_parser._get_fiscal_period(filing)
        
        # Layer 1: Tree Parser
        results = self.tree_parser.map_company(ticker, filing)
        self._log_layer_results(ticker, fiscal_period, results, "tree")
        
        # Count gaps
        gaps = [m for m, r in results.items() 
                if not r.is_mapped and r.source != MappingSource.CONFIG]
        
        if gaps and use_ai:
            # Layer 2: AI Semantic
            results = self.ai_mapper.map_gaps(
                results, xbrl, ticker, fiscal_period
            )
            self._log_layer_results(ticker, fiscal_period, results, "ai")
            
            # Update gaps
            gaps = [m for m, r in results.items() 
                    if not r.is_mapped and r.source != MappingSource.CONFIG]
        
        if gaps and use_facts:
            # Layer 4: Facts Search  
            results = self.facts_searcher.search_gaps(
                results, ticker, fiscal_period
            )
            self._log_layer_results(ticker, fiscal_period, results, "tree")  # Mark as tree since it's XBRL
        
        return results
    
    def _map_company_with_xbrl(
        self,
        ticker: str,
        use_ai: bool = True,
        use_facts: bool = True,
        amendments: bool = False
    ) -> tuple:
        """
        Map company and return both results and XBRL object.
        Used internally for validation.
        """
        filing = self._get_filing(ticker, amendments)
        if filing is None:
            return self.tree_parser._empty_results(ticker, "No filing found"), None
        
        try:
            xbrl = filing.xbrl()
        except Exception as e:
            return self.tree_parser._empty_results(ticker, f"XBRL error: {e}"), None
        
        fiscal_period = self.tree_parser._get_fiscal_period(filing)
        
        # Layer 1: Tree Parser
        results = self.tree_parser.map_company(ticker, filing)
        self._log_layer_results(ticker, fiscal_period, results, "tree")
        
        gaps = [m for m, r in results.items() 
                if not r.is_mapped and r.source != MappingSource.CONFIG]
        
        if gaps and use_ai:
            results = self.ai_mapper.map_gaps(results, xbrl, ticker, fiscal_period)
            self._log_layer_results(ticker, fiscal_period, results, "ai")
            gaps = [m for m, r in results.items() 
                    if not r.is_mapped and r.source != MappingSource.CONFIG]
        
        if gaps and use_facts:
            results = self.facts_searcher.search_gaps(results, ticker, fiscal_period)
            self._log_layer_results(ticker, fiscal_period, results, "tree")
        
        return results, xbrl
    
    def map_companies(
        self,
        tickers: Optional[List[str]] = None,
        use_ai: bool = True,
        validate: bool = True
    ) -> Dict[str, Dict[str, MappingResult]]:
        """
        Map all metrics for multiple companies.

        Args:
            tickers: List of tickers (defaults to MAG7)
            use_ai: Whether to use AI layer
            validate: Whether to validate mappings against yfinance
        """
        set_identity("Dev Gunning developer-gunning@gmail.com")
        use_local_storage(True)  # Use bulk data, no API calls
        
        if tickers is None:
            tickers = list(self.config.companies.keys())
        
        all_results = {}
        xbrl_cache = {}  # Cache XBRL objects for validation
        
        for ticker in tickers:
            print(f"\nProcessing {ticker}...")
            results, xbrl = self._map_company_with_xbrl(ticker, use_ai=use_ai)
            all_results[ticker] = results
            if xbrl is not None:
                xbrl_cache[ticker] = xbrl
            
            # Print summary
            mapped = sum(1 for r in results.values() if r.is_mapped)
            excluded = sum(1 for r in results.values() if r.source == MappingSource.CONFIG)
            total = len(results) - excluded
            print(f"  Layer 1+2+4: {mapped}/{total} mapped")
        
        # Validate all results against yfinance
        if validate:
            print("\n" + "=" * 60)
            print("VALIDATING AGAINST YFINANCE REFERENCE")
            print("=" * 60)
            self._validate_all(all_results, xbrl_cache)
        
        return all_results
    
    def _validate_all(
        self, 
        results: Dict[str, Dict[str, MappingResult]],
        xbrl_cache: Dict[str, any] = None
    ):
        """Validate all mappings against yfinance reference.
        
        Uses validate_and_update_mappings to implement the FEEDBACK LOOP:
        mappings that fail validation are marked as INVALID.
        """
        if xbrl_cache is None:
            xbrl_cache = {}
            
        for ticker, metrics in results.items():
            print(f"\n{ticker}:")
            xbrl = xbrl_cache.get(ticker)
            
            # Use validate_and_update_mappings to mark INVALID mappings
            validations = self.validator.validate_and_update_mappings(ticker, metrics, xbrl)
            self.validation_results[ticker] = validations
            
            matches = 0
            mismatches = 0
            pending = 0
            
            for metric, v in validations.items():
                if v.status == "match":
                    matches += 1
                elif v.status == "mismatch":
                    mismatches += 1
                    var = v.variance_pct if v.variance_pct else 0
                    print(f"  [INVALID] {metric}: XBRL={v.xbrl_value/1e9:.2f}B vs yf={v.reference_value/1e9:.2f}B ({var:.1f}%)")
                elif v.status == "mapping_needed":
                    val = v.reference_value / 1e9 if v.reference_value else 0
                    print(f"  [NEED] {metric}: yfinance shows {val:.2f}B but no mapping")
                elif v.status == "pending_extraction":
                    pending += 1
            
            if mismatches == 0:
                if matches > 0:
                    print(f"  ✓ {matches} values matched with yfinance")
                elif pending > 0:
                    print(f"  ⚠ {pending} values pending extraction")
                else:
                    print(f"  ✓ All mapped metrics validated")
            else:
                print(f"  ⚠ {mismatches} mapping(s) marked as INVALID - need retry or review")

    
    def _get_filing(self, ticker: str, amendments: bool = False):
        """Get the latest 10-K filing."""
        try:
            c = Company(ticker)
            filings = c.get_filings(form='10-K', amendments=amendments)
            for f in filings:
                return f
        except Exception:
            pass
        return None
    
    def _log_layer_results(
        self,
        ticker: str,
        fiscal_period: str,
        results: Dict[str, MappingResult],
        layer: str
    ):
        """Log results for audit trail."""
        for metric, result in results.items():
            if result.source.value == layer:
                entry = AuditLogEntry(
                    timestamp=datetime.utcnow(),
                    company=ticker,
                    metric=metric,
                    fiscal_period=fiscal_period,
                    action="mapped" if result.is_mapped else "failed",
                    concept=result.concept,
                    source=result.source,
                    confidence=result.confidence,
                    reasoning=result.reasoning,
                    version=self.config.version
                )
                self.audit_log.append(entry)
    
    def save_results(
        self,
        results: Dict[str, Dict[str, MappingResult]],
        output_path: str
    ):
        """Save results to JSON file."""
        output_data = {
            ticker: {
                metric: result.to_dict()
                for metric, result in metrics.items()
            }
            for ticker, metrics in results.items()
        }
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
    
    def print_summary(self, results: Dict[str, Dict[str, MappingResult]]):
        """Print a summary table of results."""
        print("\n" + "=" * 70)
        print("ORCHESTRATOR RESULTS (Layer 1 + Layer 2)")
        print("=" * 70)
        
        total_mapped = 0
        total_metrics = 0
        
        for ticker, metrics in results.items():
            mapped = sum(1 for r in metrics.values() if r.is_mapped)
            excluded = sum(1 for r in metrics.values() if r.source == MappingSource.CONFIG)
            total = len(metrics) - excluded
            
            total_mapped += mapped
            total_metrics += total
            
            print(f"\n{ticker}: {mapped}/{total} mapped")
            
            for metric, result in metrics.items():
                if result.is_mapped:
                    source = result.source.value[:4].upper()
                    print(f"  [{source}] {metric}: {result.concept} ({result.confidence_level.value})")
                elif result.source == MappingSource.CONFIG:
                    print(f"  [SKIP] {metric}: excluded")
                else:
                    print(f"  [----] {metric}: not found")
        
        # Overall stats
        pct = (total_mapped / total_metrics * 100) if total_metrics > 0 else 0
        print(f"\n{'='*70}")
        print(f"TOTAL: {total_mapped}/{total_metrics} = {pct:.1f}%")
        print("=" * 70)


def run_orchestrator(
    tickers: Optional[List[str]] = None,
    use_ai: bool = True,
    output: Optional[str] = None
) -> Dict[str, Dict[str, MappingResult]]:
    """
    Run the full mapping pipeline.
    
    Args:
        tickers: List of company tickers (defaults to MAG7)
        use_ai: Whether to use Layer 2 AI
        output: Optional path to save results JSON
        
    Returns:
        Nested dict of results
    """
    orchestrator = Orchestrator()
    results = orchestrator.map_companies(tickers, use_ai=use_ai)
    orchestrator.print_summary(results)
    
    if output:
        orchestrator.save_results(results, output)
        print(f"\nResults saved to {output}")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Mapping Orchestrator")
    parser.add_argument("--companies", type=str, default="MAG7",
                        help="Comma-separated tickers or 'MAG7'")
    parser.add_argument("--no-ai", action="store_true",
                        help="Skip Layer 2 AI mapping")
    parser.add_argument("--output", type=str, default=None,
                        help="Output JSON file")
    args = parser.parse_args()
    
    # Parse tickers
    if args.companies.upper() == "MAG7":
        tickers = None
    else:
        tickers = [t.strip().upper() for t in args.companies.split(",")]
    
    # Run
    run_orchestrator(
        tickers=tickers,
        use_ai=not args.no_ai,
        output=args.output
    )
