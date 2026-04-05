"""Outer loop for expansion pipeline: investigate gaps, apply fixes, escalate.

Processes unresolved gaps from cohort reports:
1. Prioritize by (metric, industry) grouping (Amendment 6)
2. Classify root causes from evidence
3. Apply confident fixes via config_applier + confidence_scorer
4. Detect patterns (Amendment 5: same fix 3+ in same industry)
5. Generate escalation report for ambiguous gaps
"""
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from edgar.xbrl.standardization.tools.confidence_scorer import score_confidence
from edgar.xbrl.standardization.tools.config_applier import apply_action_to_json, _load_override
from edgar.xbrl.standardization.tools.report_generator import (
    AppliedFix,
    EscalatedGap,
    generate_escalation_report,
    load_evidence_sidecar,
    parse_cohort_report,
)

log = logging.getLogger(__name__)

_DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "escalation-reports"


@dataclass
class GapGroup:
    """Group of gaps sharing the same (metric, industry) key."""
    metric: str
    industry: Optional[str]
    gaps: List[Any] = field(default_factory=list)

    @property
    def total_impact(self) -> float:
        return sum(g.estimated_impact for g in self.gaps)


def prioritize_gaps(
    gaps: List[Any],
    industry_map: Dict[str, Optional[str]],
) -> List[GapGroup]:
    """Group gaps by (metric, industry) and rank by total impact.

    Amendment 6: This grouping allows investigating one metric across
    an entire industry at once, rather than per-company.

    Args:
        gaps: List of MetricGap (or any object with ticker, metric, estimated_impact).
        industry_map: Dict of ticker -> industry string (or None).

    Returns:
        List of GapGroup, sorted by total_impact descending.
    """
    groups: Dict[Tuple[str, Optional[str]], GapGroup] = {}

    for gap in gaps:
        industry = industry_map.get(gap.ticker)
        key = (gap.metric, industry)

        if key not in groups:
            groups[key] = GapGroup(metric=gap.metric, industry=industry)
        groups[key].gaps.append(gap)

    # Sort by total impact descending
    return sorted(groups.values(), key=lambda g: g.total_impact, reverse=True)


def detect_patterns(
    applied_fixes: List[Dict[str, Any]],
    threshold: int = 3,
) -> List[Dict[str, Any]]:
    """Detect repeated fix patterns across companies in same industry.

    Amendment 5: When the same action+metric is applied to 3+ companies
    in the same industry, flag it as a pattern for potential global promotion
    to industry_metrics.yaml.

    Args:
        applied_fixes: List of fix dicts with keys: ticker, metric, action, industry.
        threshold: Minimum count to flag as pattern (default 3).

    Returns:
        List of pattern dicts with: metric, action, industry, count, tickers.
    """
    # Group by (metric, action, industry)
    groups: Dict[Tuple[str, str, Optional[str]], List[str]] = defaultdict(list)

    for fix in applied_fixes:
        key = (fix["metric"], fix["action"], fix.get("industry"))
        groups[key].append(fix["ticker"])

    patterns = []
    for (metric, action, industry), tickers in groups.items():
        if len(tickers) >= threshold:
            patterns.append({
                "metric": metric,
                "action": action,
                "industry": industry,
                "count": len(tickers),
                "tickers": tickers,
            })

    return patterns


def classify_root_cause(
    gap_type: str,
    discovery_results: List[Dict[str, Any]],
    reference_value: Optional[float],
    xbrl_value: Optional[float],
) -> str:
    """Classify the root cause of a gap based on available evidence.

    Args:
        gap_type: "unmapped", "high_variance", "validation_failure", etc.
        discovery_results: Results from discover_concepts (list of dicts with concept, value).
        reference_value: Expected value (e.g., from yfinance).
        xbrl_value: Extracted XBRL value (may be None).

    Returns:
        Root cause string: "concept_absent", "sign_error", "wrong_concept",
        "reference_mismatch", "needs_composite", "genuinely_broken"
    """
    # No concepts found at all -> concept_absent
    if not discovery_results:
        if gap_type == "unmapped" or xbrl_value is None:
            return "concept_absent"
        return "genuinely_broken"

    # Check for sign error (exact negation)
    if xbrl_value is not None and reference_value is not None and reference_value != 0:
        ratio = xbrl_value / reference_value
        if abs(ratio + 1.0) < 0.05:  # Within 5% of exact negation
            return "sign_error"

    # Has discovery results but no XBRL value -> reference_mismatch
    if xbrl_value is None and discovery_results:
        return "reference_mismatch"

    # Has XBRL value that's different from reference -> wrong_concept
    if xbrl_value is not None and reference_value is not None:
        if reference_value != 0:
            variance = abs((xbrl_value - reference_value) / reference_value)
            if variance < 0.50:  # Within 50% -> likely wrong concept
                return "wrong_concept"

    return "genuinely_broken"


def run_investigation(
    cohort_report_path: Path,
    output_dir: Optional[Path] = None,
    config_dir: Optional[Path] = None,
) -> Path:
    """Run investigation on unresolved gaps from a cohort report.

    Args:
        cohort_report_path: Path to cohort report markdown.
        output_dir: Where to write escalation report.
        config_dir: Config directory override (for testing).

    Returns:
        Path to the generated escalation report.
    """
    if output_dir is None:
        output_dir = _DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse cohort report
    cohort_data = parse_cohort_report(cohort_report_path.read_text())

    # Enrich parsed gaps with evidence from sidecar
    cohort_data.unresolved = load_evidence_sidecar(cohort_report_path, cohort_data.unresolved)

    # Enrich industry map from per-company JSON overrides
    resolve_dir = config_dir or Path(__file__).parent.parent / "config"
    industry_map: Dict[str, Optional[str]] = {}
    for company in cohort_data.companies:
        override = _load_override(company.ticker, resolve_dir)
        industry_map[company.ticker] = override.get("industry")

    # Process unresolved gaps
    applied_fixes: List[Dict] = []
    escalated_gaps: List[EscalatedGap] = []

    # Two passes: first collect peer counts, then score.
    # peer_count feeds _score_wrong_concept() which won't auto-apply without peers.
    peer_groups: Dict[Tuple[str, str, Optional[str]], List] = defaultdict(list)
    for gap_entry in cohort_data.unresolved:
        key = (gap_entry.metric, gap_entry.root_cause or "unknown", industry_map.get(gap_entry.ticker))
        peer_groups[key].append(gap_entry)

    for gap_entry in cohort_data.unresolved:
        root_cause = gap_entry.root_cause or "unknown"

        # Score confidence
        evidence = _build_evidence(gap_entry)

        # Inject peer count (other companies with same gap in same industry)
        key = (gap_entry.metric, root_cause, industry_map.get(gap_entry.ticker))
        evidence["peer_count"] = len(peer_groups[key]) - 1  # exclude self

        result = score_confidence(root_cause, evidence)

        if result.auto_apply:
            fix = {
                "action": result.recommended_action,
                "ticker": gap_entry.ticker,
                "metric": gap_entry.metric,
                "params": _build_fix_params(result, gap_entry),
                "confidence": result.confidence,
                "industry": industry_map.get(gap_entry.ticker),
                "detail": result.reasoning,
            }
            apply_action_to_json(fix, config_dir=resolve_dir)
            applied_fixes.append(fix)
        else:
            escalated_gaps.append(EscalatedGap(
                ticker=gap_entry.ticker,
                metric=gap_entry.metric,
                gap_type=gap_entry.gap_type,
                confidence=result.confidence,
                evidence=[result.reasoning],
                why_escalated=f"Confidence {result.confidence:.2f} below threshold",
                recommendation=result.recommended_action,
            ))

    # Detect patterns (same action+metric in 3+ companies of same industry)
    patterns = detect_patterns(applied_fixes)
    if patterns:
        log.info(f"Detected {len(patterns)} fix patterns for potential global promotion")

    # Generate escalation report
    md = generate_escalation_report(
        name=cohort_data.name,
        auto_fixes=[
            AppliedFix(
                ticker=f["ticker"], metric=f["metric"], action=f["action"],
                confidence=f["confidence"], detail=f["detail"],
            ) for f in applied_fixes
        ],
        escalated_gaps=escalated_gaps,
        ef_cqs_before=0.0,
        ef_cqs_after=0.0,
    )

    report_path = output_dir / f"escalation-{cohort_data.name}.md"
    report_path.write_text(md)

    log.info(f"Escalation report written to {report_path}")
    return report_path


def _build_evidence(gap_entry) -> Dict[str, Any]:
    """Build evidence dict from gap entry for confidence scoring."""
    evidence: Dict[str, Any] = {}
    if gap_entry.variance is not None:
        evidence["variance_pct"] = gap_entry.variance
    if gap_entry.reference_value is not None:
        evidence["reference_value"] = gap_entry.reference_value
    if gap_entry.xbrl_value is not None:
        evidence["xbrl_value"] = gap_entry.xbrl_value
    if gap_entry.components_found or gap_entry.components_needed:
        evidence["components_found"] = gap_entry.components_found
        evidence["components_needed"] = gap_entry.components_needed
    return evidence


def _build_fix_params(result, gap_entry) -> Dict[str, Any]:
    """Build action params from confidence result and gap entry."""
    params: Dict[str, Any] = {}
    if result.recommended_action == "EXCLUDE_METRIC":
        params["reason"] = "not_applicable"
        params["notes"] = f"Auto-excluded: {result.reasoning}"
    elif result.recommended_action == "DOCUMENT_DIVERGENCE":
        params["reason"] = result.reasoning
        if gap_entry.variance is not None:
            params["variance_pct"] = gap_entry.variance
    return params
