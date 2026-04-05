from edgar.xbrl.standardization.tools.confidence_scorer import score_confidence, ConfidenceResult


def test_concept_absent_high_confidence():
    """Concept missing from all sources -> high confidence exclusion."""
    result = score_confidence(
        root_cause="concept_absent",
        evidence={"in_calc_tree": False, "in_facts": False, "in_element_index": False},
    )
    assert result.confidence >= 0.85
    assert result.recommended_action == "EXCLUDE_METRIC"
    assert result.auto_apply is True


def test_concept_absent_partial_evidence_lowers_confidence():
    """Concept in facts but not calc tree -> lower confidence."""
    result = score_confidence(
        root_cause="concept_absent",
        evidence={"in_calc_tree": False, "in_facts": True, "in_element_index": False},
    )
    assert result.confidence < 0.85
    assert result.auto_apply is False


def test_sign_error_exact_negation():
    """Exact negation -> high confidence sign fix."""
    result = score_confidence(
        root_cause="sign_error",
        evidence={"xbrl_value": -100.0, "reference_value": 100.0},
    )
    assert result.confidence >= 0.95
    assert result.recommended_action == "FIX_SIGN_CONVENTION"
    assert result.auto_apply is True


def test_reference_mismatch_never_auto_apply():
    """Reference mismatch always escalates regardless of evidence."""
    result = score_confidence(
        root_cause="reference_mismatch",
        evidence={"peer_count": 5, "consistent_periods": 3, "variance_pct": 5.0},
    )
    assert result.auto_apply is False
    assert result.recommended_action == "DOCUMENT_DIVERGENCE"


def test_reference_disputed_never_auto_apply():
    """Reference disputed always escalates."""
    result = score_confidence(
        root_cause="reference_disputed",
        evidence={},
    )
    assert result.auto_apply is False


def test_wrong_concept_with_peer_confirmation():
    """Wrong concept with < 5% variance and peers -> auto-apply."""
    result = score_confidence(
        root_cause="wrong_concept",
        evidence={"variance_pct": 3.0, "peer_count": 2, "concept": "CashAndCashEquivalentsAtCarryingValue"},
    )
    assert result.confidence >= 0.90
    assert result.recommended_action == "MAP_CONCEPT"
    assert result.auto_apply is True


def test_wrong_concept_no_peers():
    """Wrong concept without peer confirmation -> escalate."""
    result = score_confidence(
        root_cause="wrong_concept",
        evidence={"variance_pct": 3.0, "peer_count": 0, "concept": "SomeObscureConcept"},
    )
    assert result.confidence < 0.90
    assert result.auto_apply is False


def test_needs_composite_all_components():
    """Composite with all components confirmed -> auto-apply."""
    result = score_confidence(
        root_cause="needs_composite",
        evidence={"components_found": 3, "components_needed": 3},
    )
    assert result.confidence >= 0.90
    assert result.recommended_action == "ADD_FORMULA"
    assert result.auto_apply is True


def test_needs_composite_missing_components():
    """Composite missing components -> escalate."""
    result = score_confidence(
        root_cause="needs_composite",
        evidence={"components_found": 1, "components_needed": 3},
    )
    assert result.auto_apply is False


def test_unknown_root_cause_escalates():
    """Unknown root cause always escalates."""
    result = score_confidence(root_cause="something_weird", evidence={})
    assert result.auto_apply is False
