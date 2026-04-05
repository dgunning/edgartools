"""Per-root-cause confidence scoring for expansion pipeline (Amendment 2).

Pure logic, no I/O. Maps evidence patterns to confidence scores.
Thresholds calibrated against existing 186 gaps (Phase A).
Recalibrate after first 50 new companies (Phase B).
"""
from dataclasses import dataclass
from typing import Any, Dict


# Per-root-cause thresholds (Amendment 2, deep-consensus)
# None = never auto-apply
ROOT_CAUSE_THRESHOLDS = {
    "concept_absent": 0.85,
    "sign_error": 0.95,
    "wrong_concept": 0.90,
    "needs_composite": 0.90,
    "reference_mismatch": None,  # Always escalate
    "reference_disputed": None,  # Always escalate
    "genuinely_broken": None,    # Always escalate
}

# Root cause -> recommended action mapping
ROOT_CAUSE_ACTIONS = {
    "concept_absent": "EXCLUDE_METRIC",
    "sign_error": "FIX_SIGN_CONVENTION",
    "wrong_concept": "MAP_CONCEPT",
    "needs_composite": "ADD_FORMULA",
    "reference_mismatch": "DOCUMENT_DIVERGENCE",
    "reference_disputed": "ESCALATE",
    "genuinely_broken": "ESCALATE",
}


@dataclass
class ConfidenceResult:
    """Output of the confidence scorer."""
    root_cause: str
    confidence: float              # 0.0 - 1.0
    recommended_action: str        # TypedAction action string
    auto_apply: bool               # True if confidence >= threshold
    reasoning: str = ""


def score_confidence(
    root_cause: str,
    evidence: Dict[str, Any],
) -> ConfidenceResult:
    """Score confidence for a gap based on root cause and evidence.

    Returns ConfidenceResult with confidence score and auto-apply decision.
    """
    threshold = ROOT_CAUSE_THRESHOLDS.get(root_cause)
    action = ROOT_CAUSE_ACTIONS.get(root_cause, "ESCALATE")

    if threshold is None:
        # Never auto-apply for this root cause
        return ConfidenceResult(
            root_cause=root_cause,
            confidence=0.0,
            recommended_action=action,
            auto_apply=False,
            reasoning=f"Root cause '{root_cause}' always requires human review",
        )

    # Calculate confidence based on root cause + evidence
    confidence = _calculate_confidence(root_cause, evidence)

    return ConfidenceResult(
        root_cause=root_cause,
        confidence=confidence,
        recommended_action=action,
        auto_apply=confidence >= threshold,
        reasoning=_build_reasoning(root_cause, evidence, confidence, threshold),
    )


def _calculate_confidence(root_cause: str, evidence: Dict[str, Any]) -> float:
    """Calculate confidence score from evidence."""
    if root_cause == "concept_absent":
        return _score_concept_absent(evidence)
    elif root_cause == "sign_error":
        return _score_sign_error(evidence)
    elif root_cause == "wrong_concept":
        return _score_wrong_concept(evidence)
    elif root_cause == "needs_composite":
        return _score_needs_composite(evidence)
    return 0.0


def _score_concept_absent(evidence: Dict[str, Any]) -> float:
    """Concept absent: all three sources empty = 0.95, partial = lower."""
    in_calc = evidence.get("in_calc_tree", True)
    in_facts = evidence.get("in_facts", True)
    in_index = evidence.get("in_element_index", True)

    sources_empty = sum(1 for s in [in_calc, in_facts, in_index] if not s)
    if sources_empty == 3:
        return 0.95
    elif sources_empty == 2:
        return 0.75
    else:
        return 0.50


def _score_sign_error(evidence: Dict[str, Any]) -> float:
    """Sign error: exact negation = 0.98, close = lower."""
    xbrl = evidence.get("xbrl_value")
    ref = evidence.get("reference_value")
    if xbrl is not None and ref is not None and ref != 0:
        ratio = xbrl / ref
        if abs(ratio + 1.0) < 0.02:  # Within 2% of exact negation
            return 0.98
        elif abs(ratio + 1.0) < 0.10:
            return 0.85
    return 0.50


def _score_wrong_concept(evidence: Dict[str, Any]) -> float:
    """Wrong concept: low variance + peer confirmation = high confidence."""
    variance = abs(evidence.get("variance_pct", 100.0))
    peers = evidence.get("peer_count", 0)

    if variance < 5.0 and peers >= 2:
        return 0.95
    elif variance < 5.0 and peers >= 1:
        return 0.90
    elif variance < 10.0 and peers >= 2:
        return 0.85
    elif variance < 5.0:
        return 0.80
    return 0.50


def _score_needs_composite(evidence: Dict[str, Any]) -> float:
    """Needs composite: all components found = high confidence."""
    found = evidence.get("components_found", 0)
    needed = evidence.get("components_needed", 1)

    if needed == 0:
        return 0.50
    ratio = found / needed
    if ratio >= 1.0:
        return 0.95
    elif ratio >= 0.67:
        return 0.75
    return 0.50


def _build_reasoning(root_cause: str, evidence: Dict[str, Any],
                     confidence: float, threshold: float) -> str:
    """Build human-readable reasoning string."""
    if confidence >= threshold:
        return f"{root_cause}: confidence {confidence:.2f} >= threshold {threshold:.2f} — auto-apply"
    return f"{root_cause}: confidence {confidence:.2f} < threshold {threshold:.2f} — escalate"
