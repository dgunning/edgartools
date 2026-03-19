"""
Orchestrator for the multi-layer mapping architecture.

Runs all mapping layers in sequence with validation-in-loop:
Layer 1 (Tree Parser) → Validate → Layer 2 (Facts Search) → Validate → Layer 3 (AI Semantic) → Validate

Key design principles:
1. Static methods first - exhaust deterministic options before AI
2. Validation after each layer - early detection of invalid mappings
3. Gap = unmapped OR invalid - invalid mappings retry with next layer
"""

import json
import logging
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

from edgar import Company, set_identity, use_local_storage
from edgar.storage._local import is_using_local_storage

from .config_loader import get_config, MappingConfig
from .models import MappingResult, MappingSource, AuditLogEntry
from .layers.tree_parser import TreeParser
from .layers.ai_semantic import AISemanticMapper
from .layers.facts_search import FactsSearcher
from .reference_validator import ReferenceValidator, ValidationResult


AUDIT_LOG_FILE = Path(__file__).parent / "company_mappings" / "audit_log.jsonl"


def _process_company_worker(args):
    """
    Top-level worker function for ProcessPoolExecutor.

    Each subprocess creates its own Orchestrator to avoid shared-state issues.
    Must be top-level (not a method/closure) to be pickle-able.
    """
    ticker, snapshot_mode, use_ai, validate, config = args
    start = time.time()

    set_identity("Dev Gunning developer-gunning@gmail.com")
    use_local_storage(True)

    orch = Orchestrator(config=config, snapshot_mode=snapshot_mode)
    results, xbrl, filing_date, form_type = orch._map_company_with_xbrl(
        ticker, use_ai=use_ai
    )

    validations = {}
    if validate:
        validations = orch.validator.validate_and_update_mappings(
            ticker, results, xbrl,
            filing_date=filing_date, form_type=form_type,
        )

    mapped = sum(1 for r in results.values() if r.is_mapped)
    excluded = sum(1 for r in results.values() if r.source == MappingSource.CONFIG)
    total = len(results) - excluded
    elapsed = time.time() - start
    logger.info(f"{ticker}: {mapped}/{total} mapped ({elapsed:.1f}s)")

    return ticker, results, validations, elapsed


class Orchestrator:
    """
    Runs all mapping layers in sequence.
    """

    def __init__(self, config: Optional[MappingConfig] = None, snapshot_mode: bool = False):
        self.config = config or get_config()
        self.tree_parser = TreeParser(self.config)
        self.ai_mapper = AISemanticMapper(self.config)
        self.facts_searcher = FactsSearcher(self.config)
        self.validator = ReferenceValidator(self.config, snapshot_mode=snapshot_mode)
        self.audit_log = []
        self.validation_results = {}
        self._company_timings: Dict[str, float] = {}  # ticker -> seconds

    def flush_audit_log(self, path=None) -> int:
        """Flush in-memory audit log entries to a JSONL file on disk.

        Args:
            path: Optional override path. Defaults to AUDIT_LOG_FILE.

        Returns:
            Number of entries flushed.
        """
        if not self.audit_log:
            return 0

        target = path or AUDIT_LOG_FILE
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)

        with open(target, 'a') as f:
            for entry in self.audit_log:
                f.write(entry.to_json() + '\n')

        count = len(self.audit_log)
        self.audit_log.clear()
        return count
    
    def map_company(
        self,
        ticker: str,
        use_ai: bool = True,
        use_facts: bool = True,
        amendments: bool = False
    ) -> Dict[str, MappingResult]:
        """
        Map all metrics for a company using all available layers.
        
        Layers run in order with validation after each:
        1. Tree Parser (static, uses calc tree)
        2. Facts Search (static, uses facts database)
        3. AI Semantic (dynamic, uses LLM)
        
        Args:
            ticker: Company ticker
            use_ai: Whether to use Layer 3 AI for gaps
            use_facts: Whether to use Layer 2 Facts Search for gaps
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
        
        form_type = getattr(filing, 'form', '10-K')
        filing_date = getattr(filing, 'period_of_report', None)
        fiscal_period = self.tree_parser._get_fiscal_period(filing)

        # Layer 1: Tree Parser (static)
        results = self.tree_parser.map_company(ticker, filing)
        self._log_layer_results(ticker, fiscal_period, results, "tree")

        # Validate Layer 1 and get gaps (unmapped OR invalid)
        gaps = self._validate_layer(ticker, results, xbrl,
                                    filing_date=filing_date, form_type=form_type)
        total = len([m for m in results if results[m].source != MappingSource.CONFIG])
        print(f"  Layer 1 (Tree): {total - len(gaps)}/{total} resolved")

        # Layer 2: Facts Search (static) - run BEFORE AI
        if gaps and use_facts:
            results = self.facts_searcher.search_gaps(
                results, ticker, fiscal_period
            )
            self._log_layer_results(ticker, fiscal_period, results, "tree")

            # Validate Layer 2 and get gaps
            gaps = self._validate_layer(ticker, results, xbrl,
                                        filing_date=filing_date, form_type=form_type)
            print(f"  Layer 2 (Facts): {total - len(gaps)}/{total} resolved")

        # Layer 3: AI Semantic (dynamic) - run AFTER static methods
        if gaps and use_ai:
            results = self.ai_mapper.map_gaps(
                results, xbrl, ticker, fiscal_period
            )
            self._log_layer_results(ticker, fiscal_period, results, "ai")

            # Validate Layer 3 and get gaps
            gaps = self._validate_layer(ticker, results, xbrl,
                                        filing_date=filing_date, form_type=form_type)
            print(f"  Layer 3 (AI): {total - len(gaps)}/{total} resolved")

        if gaps:
            print(f"  Remaining gaps: {gaps}")

        return results
    
    def _validate_layer(
        self,
        ticker: str,
        results: Dict[str, MappingResult],
        xbrl,
        filing_date=None,
        form_type=None
    ) -> List[str]:
        """
        Validate after a layer and return updated gaps.

        A gap is a metric that is:
        - Not mapped, OR
        - Mapped but validation_status == 'invalid'

        Invalid mappings are reset so the next layer can retry.

        Returns:
            List of metric names that are gaps
        """
        # Run validation on all mappings
        self.validator.validate_and_update_mappings(
            ticker, results, xbrl, filing_date=filing_date, form_type=form_type
        )
        
        # Recalculate gaps including invalid mappings
        gaps = []
        for metric, result in results.items():
            if result.source == MappingSource.CONFIG:
                continue  # Excluded
            
            if not result.is_mapped:
                gaps.append(metric)
            elif result.validation_status == 'invalid':
                # Reset mapping so next layer can retry
                result.concept = None
                result.confidence = 0.0
                result.confidence_level = result.confidence_level  # Keep INVALID marker
                result.source = MappingSource.UNKNOWN
                result.reasoning = f"Previous mapping failed validation: {result.validation_notes}"
                gaps.append(metric)
        
        return gaps
    
    @staticmethod
    def _retry_xbrl_with_writable_cache(filing):
        """Retry filing.xbrl() bypassing the file cache.

        When local storage points to a read-only filesystem, the HTTP cache
        transport can't write .lock/.meta files. This temporarily switches
        to a cache-disabled HTTP manager, retries, then restores the original.
        """
        import edgar.httpclient as httpclient

        original_mgr = httpclient.HTTP_MGR
        try:
            # Create a fresh HTTP manager with cache disabled (no filesystem writes)
            httpclient.HTTP_MGR = httpclient.get_http_mgr(
                cache_enabled=False,
                request_per_sec_limit=httpclient.get_edgar_rate_limit_per_sec()
            )
            xbrl = filing.xbrl()
            return xbrl
        except Exception:
            return None
        finally:
            # Restore original HTTP manager
            try:
                httpclient.HTTP_MGR.close()
            except Exception:
                pass
            httpclient.HTTP_MGR = original_mgr

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

        Uses same layer order as map_company:
        Layer 1 (Tree) -> Layer 2 (Facts) -> Layer 3 (AI)
        """
        filing = self._get_filing(ticker, amendments)
        if filing is None:
            return self.tree_parser._empty_results(ticker, "No filing found"), None, None, None

        try:
            xbrl = filing.xbrl()
        except OSError as e:
            # Filesystem error (e.g. read-only local cache) - retry with writable cache
            if is_using_local_storage():
                print(f"  Local storage error for {ticker}, retrying via network...")
                xbrl = self._retry_xbrl_with_writable_cache(filing)
                if xbrl is None:
                    return self.tree_parser._empty_results(ticker, f"XBRL error: {e}"), None, None, None
            else:
                return self.tree_parser._empty_results(ticker, f"XBRL error: {e}"), None, None, None
        except Exception as e:
            return self.tree_parser._empty_results(ticker, f"XBRL error: {e}"), None, None, None

        form_type = getattr(filing, 'form', '10-K')
        filing_date = getattr(filing, 'period_of_report', None)
        fiscal_period = self.tree_parser._get_fiscal_period(filing)

        # Layer 1: Tree Parser (static)
        results = self.tree_parser.map_company(ticker, filing)
        self._log_layer_results(ticker, fiscal_period, results, "tree")

        # Validate Layer 1 and get gaps
        gaps = self._validate_layer(ticker, results, xbrl,
                                    filing_date=filing_date, form_type=form_type)
        total = len([m for m in results if results[m].source != MappingSource.CONFIG])
        print(f"  Layer 1 (Tree): {total - len(gaps)}/{total} resolved")

        # Layer 2: Facts Search (static) - run BEFORE AI
        if gaps and use_facts:
            results = self.facts_searcher.search_gaps(results, ticker, fiscal_period)
            self._log_layer_results(ticker, fiscal_period, results, "tree")
            gaps = self._validate_layer(ticker, results, xbrl,
                                        filing_date=filing_date, form_type=form_type)
            print(f"  Layer 2 (Facts): {total - len(gaps)}/{total} resolved")

        # Layer 3: AI Semantic (dynamic) - run AFTER static methods
        if gaps and use_ai:
            results = self.ai_mapper.map_gaps(results, xbrl, ticker, fiscal_period)
            self._log_layer_results(ticker, fiscal_period, results, "ai")
            gaps = self._validate_layer(ticker, results, xbrl,
                                        filing_date=filing_date, form_type=form_type)
            print(f"  Layer 3 (AI): {total - len(gaps)}/{total} resolved")

        if gaps:
            print(f"  Remaining gaps: {gaps}")

        return results, xbrl, filing_date, form_type
    
    def map_companies(
        self,
        tickers: Optional[List[str]] = None,
        use_ai: bool = True,
        validate: bool = True,
        max_workers: int = 1,
    ) -> Dict[str, Dict[str, MappingResult]]:
        """
        Map all metrics for multiple companies.

        Args:
            tickers: List of tickers (defaults to MAG7)
            use_ai: Whether to use AI layer
            validate: Whether to validate mappings against yfinance
            max_workers: Number of parallel workers (1 = sequential, >1 = parallel)
        """
        set_identity("Dev Gunning developer-gunning@gmail.com")
        use_local_storage(True)  # Use bulk data, no API calls

        if tickers is None:
            tickers = list(self.config.companies.keys())

        if max_workers > 1 and len(tickers) > 1:
            return self._map_companies_parallel(
                tickers, use_ai=use_ai, validate=validate, max_workers=max_workers
            )

        all_results = {}
        xbrl_cache = {}  # Cache XBRL objects for validation
        filing_context_cache = {}  # Cache filing context for validation

        for ticker in tickers:
            print(f"\nProcessing {ticker}...")
            t_start = time.time()
            results, xbrl, filing_date, form_type = self._map_company_with_xbrl(ticker, use_ai=use_ai)
            all_results[ticker] = results
            self._company_timings[ticker] = time.time() - t_start
            if xbrl is not None:
                xbrl_cache[ticker] = xbrl
            filing_context_cache[ticker] = (filing_date, form_type)

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
            self._validate_all(all_results, xbrl_cache, filing_context_cache)

        return all_results

    def _map_companies_parallel(
        self,
        tickers: List[str],
        use_ai: bool = True,
        validate: bool = True,
        max_workers: int = 4,
    ) -> Dict[str, Dict[str, MappingResult]]:
        """
        Map companies in parallel using ProcessPoolExecutor.

        Each subprocess creates its own Orchestrator to avoid
        shared-state issues (GIL, validator caches, _current_ticker).
        """
        all_results = {}
        snapshot_mode = self.validator._snapshot_mode

        args_list = [
            (ticker, snapshot_mode, use_ai, validate, self.config)
            for ticker in tickers
        ]

        logger.info(f"Parallel mapping: {len(tickers)} companies, {max_workers} workers")
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_process_company_worker, args): args[0]
                for args in args_list
            }

            completed = 0
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    ticker, results, validations, elapsed = future.result()
                    all_results[ticker] = results
                    if validations:
                        self.validation_results[ticker] = validations
                    self._company_timings[ticker] = elapsed
                    completed += 1
                    logger.info(f"[{completed}/{len(tickers)}] {ticker} done ({elapsed:.1f}s)")
                except Exception as e:
                    logger.error(f"{ticker} failed: {e}")
                    all_results[ticker] = self.tree_parser._empty_results(ticker, str(e))

        return all_results
    
    def _validate_all(
        self,
        results: Dict[str, Dict[str, MappingResult]],
        xbrl_cache: Dict[str, any] = None,
        filing_context_cache: Dict[str, tuple] = None
    ):
        """Validate all mappings against yfinance reference.

        Uses validate_and_update_mappings to implement the FEEDBACK LOOP:
        mappings that fail validation are marked as INVALID.
        """
        if xbrl_cache is None:
            xbrl_cache = {}
        if filing_context_cache is None:
            filing_context_cache = {}

        for ticker, metrics in results.items():
            print(f"\n{ticker}:")
            xbrl = xbrl_cache.get(ticker)
            filing_date, form_type = filing_context_cache.get(ticker, (None, None))

            # Use validate_and_update_mappings to mark INVALID mappings
            validations = self.validator.validate_and_update_mappings(
                ticker, metrics, xbrl, filing_date=filing_date, form_type=form_type
            )
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
    
    def _get_filing(self, ticker: str, amendments: bool = None):
        """Get a filing with optional amendments filter.
        
        Args:
            ticker: Company ticker
            amendments: Whether to include amended filings (10-K/A).
        """
        try:
            c = Company(ticker)
            filings = c.get_filings(form='10-K', amendments=amendments if amendments is not None else True)
            for f in filings:
                return f
        except Exception:
            pass
        return None
    
    def _get_best_filing(self, ticker: str):
        """Get the best filing: prefer amendment if XBRL complete, fallback to original.
        
        Smart filing selection strategy:
        1. Try to get both amended (10-K/A) and original (10-K) filing
        2. If amendment exists and has complete XBRL (calculation trees), use it
        3. Otherwise use original
        4. Return metadata about which source was used
        
        Returns:
            Tuple of (filing, metadata_dict)
        """
        original = None
        amended = None
        
        try:
            c = Company(ticker)
            
            # Get original (exclude amendments)
            orig_filings = c.get_filings(form='10-K', amendments=False)
            for f in orig_filings:
                original = f
                break
            
            # Get latest filing (may be amendment)
            all_filings = c.get_filings(form='10-K', amendments=True)
            for f in all_filings:
                if '/A' in str(f.form):
                    amended = f
                break
        except Exception:
            pass
        
        if not original and not amended:
            return None, {'source': 'none', 'error': 'no filing found'}
        
        # If no amendment, use original
        if not amended or amended == original:
            return original, {'source': 'original'}
        
        # Try amendment first - check if XBRL is complete
        try:
            amended_xbrl = amended.xbrl()
            if amended_xbrl and len(amended_xbrl.calculation_trees) > 0:
                # Amendment has complete XBRL - use it
                return amended, {
                    'source': 'amendment',
                    'calc_trees': len(amended_xbrl.calculation_trees)
                }
        except Exception:
            pass
        
        # Amendment incomplete - use original
        return original, {'source': 'original', 'reason': 'amendment_incomplete'}
    
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
