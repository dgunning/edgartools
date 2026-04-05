"""
Gap Resolution Tool

REUSABLE TOOL FOR AI AGENTS AND DIRECT USE

Provides functions for resolving XBRL concept mapping gaps after the
orchestrator identifies unmapped or invalid mappings.

Usage:
    from edgar.xbrl.standardization.tools.resolve_gaps import (
        resolve_all_gaps,
        calculate_coverage,
        generate_report,
        update_config
    )

    # After running orchestrator
    results = orchestrator.map_companies(tickers=['AAPL', 'GOOG', ...])

    # Calculate coverage before
    before = calculate_coverage(results)

    # Resolve gaps
    resolutions, updated_results = resolve_all_gaps(results)

    # Calculate coverage after
    after = calculate_coverage(updated_results)

    # Generate report
    report = generate_report(before, after, resolutions)
    print(report)

    # Update config with new concepts
    update_config(resolutions)
"""

import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from edgar import Company, set_identity, use_local_storage

from ..models import MappingResult, MappingSource, ConfidenceLevel
from .discover_concepts import discover_concepts
from .check_fallback_quality import check_fallback_quality
from .verify_mapping import verify_mapping
from .learn_mappings import learn_mappings


@dataclass
class CoverageStats:
    """Coverage statistics."""
    total_metrics: int
    mapped_metrics: int
    excluded_metrics: int
    invalid_metrics: int
    coverage_pct: float

    def __str__(self):
        return f"{self.coverage_pct:.1f}% ({self.mapped_metrics}/{self.total_metrics} mapped)"


@dataclass
class Resolution:
    """Result of attempting to resolve a gap."""
    ticker: str
    metric: str
    resolved: bool
    concept: Optional[str] = None
    confidence: Optional[float] = None
    source: Optional[str] = None
    reason: Optional[str] = None
    candidates_tried: int = 0
    verification_status: Optional[str] = None
    xbrl_value: Optional[float] = None
    reference_value: Optional[float] = None
    variance_pct: Optional[float] = None


@dataclass
class ResolutionReport:
    """Complete resolution report."""
    before: CoverageStats
    after: CoverageStats
    resolutions: List[Resolution]
    patterns_discovered: Dict[str, List[str]]
    config_changes: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


def calculate_coverage(
    results: Dict[str, Dict[str, MappingResult]]
) -> CoverageStats:
    """
    Calculate coverage statistics from mapping results.

    Args:
        results: Mapping results from orchestrator

    Returns:
        CoverageStats with coverage percentage and counts
    """
    total = 0
    mapped = 0
    excluded = 0
    invalid = 0

    for ticker, metrics in results.items():
        for metric, result in metrics.items():
            if result.source == MappingSource.CONFIG:
                excluded += 1
                continue

            total += 1

            if result.is_mapped:
                if result.validation_status == "invalid":
                    invalid += 1
                else:
                    mapped += 1

    coverage_pct = (mapped / total * 100) if total > 0 else 0.0

    return CoverageStats(
        total_metrics=total,
        mapped_metrics=mapped,
        excluded_metrics=excluded,
        invalid_metrics=invalid,
        coverage_pct=coverage_pct
    )


def resolve_all_gaps(
    results: Dict[str, Dict[str, MappingResult]],
    xbrl_cache: Optional[Dict[str, Any]] = None,
    confidence_threshold: float = 0.80,
    variance_threshold: float = 15.0
) -> Tuple[List[Resolution], Dict[str, Dict[str, MappingResult]]]:
    """
    Resolve all gaps in mapping results.

    Args:
        results: Mapping results from orchestrator
        xbrl_cache: Optional dict of ticker -> XBRL object
        confidence_threshold: Minimum confidence to accept (default 0.80)
        variance_threshold: Maximum variance % to accept (default 10.0)

    Returns:
        Tuple of (resolutions list, updated results dict)
    """
    set_identity("Dev Gunning developer-gunning@gmail.com")
    use_local_storage(True)  # Use bulk data, no API calls

    if xbrl_cache is None:
        xbrl_cache = {}

    resolutions = []
    updated_results = {ticker: dict(metrics) for ticker, metrics in results.items()}

    # Collect all gaps
    gaps = []
    for ticker, metrics in results.items():
        for metric, result in metrics.items():
            if result.source == MappingSource.CONFIG:
                continue

            if not result.is_mapped or result.validation_status == "invalid":
                gaps.append({
                    'ticker': ticker,
                    'metric': metric,
                    'result': result,
                    'reason': 'unmapped' if not result.is_mapped else 'invalid'
                })

    # Resolve each gap
    for gap in gaps:
        ticker = gap['ticker']
        metric = gap['metric']

        resolution = _resolve_single_gap(
            ticker, metric,
            xbrl_cache,
            confidence_threshold,
            variance_threshold
        )
        resolutions.append(resolution)

        # Update results if resolved
        if resolution.resolved and resolution.concept:
            updated_results[ticker][metric] = MappingResult(
                metric=metric,
                company=ticker,
                fiscal_period=gap['result'].fiscal_period,
                concept=resolution.concept,
                confidence=resolution.confidence or 0.0,
                confidence_level=ConfidenceLevel.HIGH if (resolution.confidence or 0) >= 0.95 else ConfidenceLevel.MEDIUM,
                source=MappingSource.AI,
                reasoning=f"Resolved by AI agent: {resolution.source}",
                validation_status="valid" if resolution.verification_status == "match" else "pending",
                value=resolution.xbrl_value
            )

    return resolutions, updated_results


def _resolve_single_gap(
    ticker: str,
    metric: str,
    xbrl_cache: Dict[str, Any],
    confidence_threshold: float,
    variance_threshold: float
) -> Resolution:
    """Resolve a single gap."""

    # Get or fetch XBRL
    if ticker not in xbrl_cache:
        try:
            company = Company(ticker)
            filing = list(company.get_filings(form='10-K'))[0]
            facts = company.get_facts()
            xbrl_cache[ticker] = {
                'xbrl': filing.xbrl(),
                'facts_df': facts.to_dataframe() if facts is not None else None
            }
        except Exception as e:
            return Resolution(
                ticker=ticker,
                metric=metric,
                resolved=False,
                reason=f"Failed to get XBRL: {e}"
            )

    xbrl = xbrl_cache[ticker]['xbrl']
    facts_df = xbrl_cache[ticker]['facts_df']

    # Step 1: Discover candidates
    try:
        candidates = discover_concepts(metric, xbrl, facts_df)
    except Exception as e:
        return Resolution(
            ticker=ticker,
            metric=metric,
            resolved=False,
            reason=f"Discovery failed: {e}"
        )

    if not candidates:
        return Resolution(
            ticker=ticker,
            metric=metric,
            resolved=False,
            reason="No candidates found",
            candidates_tried=0
        )

    # Try each candidate in order
    for i, candidate in enumerate(candidates[:5]):  # Try top 5
        # Step 2: Check quality
        try:
            quality = check_fallback_quality(metric, candidate.concept, xbrl)
        except Exception:
            continue

        if not quality.is_valid:
            continue

        if candidate.confidence < confidence_threshold:
            continue

        # Step 3: Verify mapping
        try:
            verification = verify_mapping(metric, candidate.concept, xbrl, ticker)
        except Exception:
            continue

        # Accept if match or no reference data
        if verification.status in ('match', 'no_ref', 'no_data'):
            return Resolution(
                ticker=ticker,
                metric=metric,
                resolved=True,
                concept=candidate.concept,
                confidence=candidate.confidence,
                source=candidate.source,
                candidates_tried=i + 1,
                verification_status=verification.status,
                xbrl_value=verification.xbrl_value,
                reference_value=verification.reference_value,
                variance_pct=verification.variance_pct
            )

        # Check variance threshold for mismatch
        if verification.status == 'mismatch' and verification.variance_pct:
            if verification.variance_pct <= variance_threshold:
                return Resolution(
                    ticker=ticker,
                    metric=metric,
                    resolved=True,
                    concept=candidate.concept,
                    confidence=candidate.confidence,
                    source=candidate.source,
                    candidates_tried=i + 1,
                    verification_status="match_within_threshold",
                    xbrl_value=verification.xbrl_value,
                    reference_value=verification.reference_value,
                    variance_pct=verification.variance_pct
                )

    # No candidate worked
    return Resolution(
        ticker=ticker,
        metric=metric,
        resolved=False,
        reason=f"All {min(len(candidates), 5)} candidates failed verification",
        candidates_tried=min(len(candidates), 5)
    )


def generate_report(
    before: CoverageStats,
    after: CoverageStats,
    resolutions: List[Resolution],
    patterns: Optional[Dict[str, List[str]]] = None,
    config_changes: Optional[List[str]] = None
) -> str:
    """
    Generate a human-readable resolution report.

    Args:
        before: Coverage stats before resolution
        after: Coverage stats after resolution
        resolutions: List of resolution results
        patterns: Optional patterns discovered
        config_changes: Optional config changes made

    Returns:
        Formatted report string
    """
    lines = []
    lines.append("=" * 60)
    lines.append("CONCEPT MAPPING RESOLUTION REPORT")
    lines.append("=" * 60)
    lines.append("")

    # Coverage comparison
    lines.append("COVERAGE COMPARISON")
    lines.append(f"  Before: {before}")
    lines.append(f"  After:  {after}")

    improvement = after.coverage_pct - before.coverage_pct
    resolved_count = sum(1 for r in resolutions if r.resolved)
    lines.append(f"  Improvement: +{improvement:.1f}% (+{resolved_count} metrics)")
    lines.append("")

    # Resolution details by company
    lines.append("RESOLUTION DETAILS")
    lines.append("")

    # Group by ticker
    by_ticker = {}
    for r in resolutions:
        by_ticker.setdefault(r.ticker, []).append(r)

    for ticker in sorted(by_ticker.keys()):
        lines.append(f"{ticker}:")
        for r in by_ticker[ticker]:
            if r.resolved:
                symbol = "[OK]"
                detail = f"{r.metric}: Resolved -> {r.concept}"
                lines.append(f"  {symbol} {detail}")
                lines.append(f"      Source: {r.source}, Confidence: {r.confidence:.2f}")
                if r.xbrl_value and r.reference_value:
                    lines.append(f"      Verification: XBRL={r.xbrl_value/1e9:.2f}B, Ref={r.reference_value/1e9:.2f}B, Variance={r.variance_pct:.1f}%")
            else:
                symbol = "[--]"
                detail = f"{r.metric}: Unable to resolve"
                lines.append(f"  {symbol} {detail}")
                lines.append(f"      Reason: {r.reason}")
                if r.candidates_tried > 0:
                    lines.append(f"      Candidates tried: {r.candidates_tried}")
        lines.append("")

    # Patterns discovered
    if patterns:
        lines.append("PATTERNS DISCOVERED")
        for metric, concepts in patterns.items():
            lines.append(f"  {metric}: {concepts}")
        lines.append("")

    # Config changes
    if config_changes:
        lines.append("CONFIG CHANGES")
        lines.append("  Updated: edgar/xbrl/standardization/config/metrics.yaml")
        for change in config_changes:
            lines.append(f"    - {change}")
        lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)


def update_config(
    resolutions: List[Resolution],
    config_path: Optional[str] = None
) -> List[str]:
    """
    Auto-update metrics.yaml with newly discovered concepts.

    Args:
        resolutions: List of successful resolutions
        config_path: Optional custom config path

    Returns:
        List of changes made
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "metrics.yaml"
    else:
        config_path = Path(config_path)

    # Read current config
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Collect new concepts by metric
    new_concepts = {}
    for r in resolutions:
        if r.resolved and r.concept:
            # Extract base concept name (strip prefix)
            concept_name = r.concept
            for prefix in ['us-gaap:', 'dei:', 'ifrs-full:']:
                concept_name = concept_name.replace(prefix, '')

            # Group by metric
            new_concepts.setdefault(r.metric, set()).add(concept_name)

    # Update config
    changes = []
    for metric, concepts in new_concepts.items():
        if metric not in config.get('metrics', {}):
            continue

        existing = set(config['metrics'][metric].get('known_concepts', []))

        for concept in concepts:
            if concept not in existing:
                config['metrics'][metric]['known_concepts'].append(concept)
                changes.append(f"{metric}: +{concept}")

    # Write updated config if changes made
    if changes:
        with open(config_path, 'w') as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)

    return changes


def learn_patterns(
    resolutions: List[Resolution],
    min_failures: int = 2
) -> Dict[str, List[str]]:
    """
    Learn patterns from failed resolutions.

    Identifies metrics that failed in multiple companies and attempts
    to discover cross-company patterns.

    Args:
        resolutions: List of resolution results
        min_failures: Minimum failures to trigger pattern learning

    Returns:
        Dict of metric -> new concept variants discovered
    """
    # Group failures by metric
    failed_metrics = {}
    for r in resolutions:
        if not r.resolved:
            failed_metrics.setdefault(r.metric, []).append(r.ticker)

    # Learn patterns for metrics with multiple failures
    patterns = {}
    for metric, tickers in failed_metrics.items():
        if len(tickers) >= min_failures:
            try:
                result = learn_mappings(metric, tickers)
                if result.new_concept_variants:
                    patterns[metric] = result.new_concept_variants
            except Exception:
                pass

    return patterns


# Convenience function for quick use
def resolve(tickers: List[str] = None) -> ResolutionReport:
    """
    Quick way to run full resolution workflow.

    Args:
        tickers: Optional list of tickers (defaults to MAG7)

    Returns:
        ResolutionReport with all results
    """
    from ..orchestrator import Orchestrator

    set_identity("Dev Gunning developer-gunning@gmail.com")

    if tickers is None:
        tickers = ['AAPL', 'GOOG', 'AMZN', 'MSFT', 'META', 'NVDA', 'TSLA']

    # Run orchestrator
    orchestrator = Orchestrator()
    results = orchestrator.map_companies(tickers=tickers, use_ai=False, validate=True)

    # Calculate before coverage
    before = calculate_coverage(results)

    # Resolve gaps
    resolutions, updated_results = resolve_all_gaps(results)

    # Calculate after coverage
    after = calculate_coverage(updated_results)

    # Learn patterns from failures
    patterns = learn_patterns(resolutions)

    # Update config
    config_changes = update_config(resolutions)

    # Print report
    report = generate_report(before, after, resolutions, patterns, config_changes)
    print(report)

    return ResolutionReport(
        before=before,
        after=after,
        resolutions=resolutions,
        patterns_discovered=patterns,
        config_changes=config_changes
    )
