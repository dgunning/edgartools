"""
Verification tests for the two-step auto-eval architecture.

Covers:
  - UnresolvedGap / GapManifest serialization round-trips
  - _compute_difficulty_tier routing logic
  - _build_unresolved_gap evidence denormalization
  - parse_gpt_response JSON parsing (valid, invalid, fenced, wrong file)
  - build_consultation_prompt structure for standard and hard gaps
  - consult_ai_gaps end-to-end with a mock AI caller

All tests are Tier 1 (no network, no SEC data access) and run in < 1 second.
"""

import json
from pathlib import Path
from typing import Optional

import pytest

pytestmark = pytest.mark.fast

from edgar.xbrl.standardization.tools.auto_eval import ExtractionEvidence, MetricGap
from edgar.xbrl.standardization.tools.auto_eval_loop import (
    AIAgentType,
    ChangeType,
    GapManifest,
    UnresolvedGap,
    _build_unresolved_gap,
    _compute_difficulty_tier,
    load_gap_manifest,
    parse_gpt_response,
    save_gap_manifest,
)
from edgar.xbrl.standardization.tools.consult_ai_gaps import (
    build_agent_prompt,
    build_consultation_prompt,
    collect_agent_proposals,
    consult_ai_gaps,
)


# =============================================================================
# Helpers
# =============================================================================

def _make_metric_gap(
    ticker: str = "XOM",
    metric: str = "Revenue",
    gap_type: str = "high_variance",
    graveyard_count: int = 3,
    root_cause: Optional[str] = None,
    hv_subtype: Optional[str] = None,
    reference_value: float = 1_000_000.0,
    xbrl_value: float = 950_000.0,
    current_variance: float = 5.2,
    estimated_impact: float = 0.01,
    extraction_evidence: Optional[ExtractionEvidence] = None,
) -> MetricGap:
    return MetricGap(
        ticker=ticker,
        metric=metric,
        gap_type=gap_type,
        estimated_impact=estimated_impact,
        current_variance=current_variance,
        reference_value=reference_value,
        xbrl_value=xbrl_value,
        graveyard_count=graveyard_count,
        root_cause=root_cause,
        hv_subtype=hv_subtype,
        extraction_evidence=extraction_evidence,
    )


def _make_unresolved_gap(
    ticker: str = "JPM",
    metric: str = "NetIncome",
    gap_type: str = "validation_failure",
    difficulty_tier: str = "standard",
    graveyard_count: int = 2,
    root_cause: Optional[str] = None,
    resolution_type: str = "composite",
    components_used: Optional[list] = None,
    components_missing: Optional[list] = None,
    company_industry: Optional[str] = "Financial",
    graveyard_entries: Optional[list] = None,
    ai_agent_type: str = "semantic_mapper",
) -> UnresolvedGap:
    return UnresolvedGap(
        ticker=ticker,
        metric=metric,
        gap_type=gap_type,
        hv_subtype="hv_missing_component",
        reference_value=12_345_000.0,
        xbrl_value=11_900_000.0,
        current_variance=3.7,
        estimated_impact=0.02,
        graveyard_count=graveyard_count,
        root_cause=root_cause,
        notes="test note",
        resolution_type=resolution_type,
        components_used=components_used or ["NetIncomeLoss"],
        components_missing=components_missing or ["MinorityInterest"],
        company_industry=company_industry,
        graveyard_entries=graveyard_entries or [],
        ai_agent_type=ai_agent_type,
        difficulty_tier=difficulty_tier,
    )


# =============================================================================
# 1. UnresolvedGap serialization round-trip
# =============================================================================

def test_unresolved_gap_serialization_roundtrip():
    """All UnresolvedGap fields survive a to_dict / from_dict cycle."""
    original = _make_unresolved_gap(
        graveyard_entries=[
            {
                "config_diff": "add_concept: us-gaap:SomeConceptX",
                "discard_reason": "no_improvement",
                "detail": "CQS unchanged",
                "target_companies": "JPM",
            }
        ],
    )

    d = original.to_dict()
    restored = UnresolvedGap.from_dict(d)

    assert restored.ticker == "JPM"
    assert restored.metric == "NetIncome"
    assert restored.gap_type == "validation_failure"
    assert restored.hv_subtype == "hv_missing_component"
    assert restored.reference_value == 12_345_000.0
    assert restored.xbrl_value == 11_900_000.0
    assert restored.current_variance == 3.7
    assert restored.estimated_impact == 0.02
    assert restored.graveyard_count == 2
    assert restored.notes == "test note"
    assert restored.resolution_type == "composite"
    assert restored.components_used == ["NetIncomeLoss"]
    assert restored.components_missing == ["MinorityInterest"]
    assert restored.company_industry == "Financial"
    assert restored.ai_agent_type == "semantic_mapper"
    assert restored.difficulty_tier == "standard"
    assert len(restored.graveyard_entries) == 1
    assert restored.graveyard_entries[0]["discard_reason"] == "no_improvement"


# =============================================================================
# 2. GapManifest serialization round-trip
# =============================================================================

def test_gap_manifest_serialization_roundtrip(tmp_path):
    """GapManifest with two gaps serializes to JSON and deserializes identically."""
    gap_a = _make_unresolved_gap(ticker="JPM", metric="NetIncome", difficulty_tier="standard")
    gap_b = _make_unresolved_gap(
        ticker="XOM",
        metric="Revenue",
        gap_type="regression",
        difficulty_tier="hard",
        graveyard_count=7,
    )

    manifest = GapManifest(
        session_id="test-session-001",
        created_at="2026-03-23T00:00:00",
        baseline_cqs=0.7834,
        eval_cohort=["JPM", "XOM", "JNJ"],
        gaps=[gap_a, gap_b],
        config_fingerprint="abc123def456",
        deterministic_kept=5,
        deterministic_discarded=12,
    )

    manifest_path = tmp_path / "manifest_test.json"
    save_gap_manifest(manifest, manifest_path)

    assert manifest_path.exists()

    loaded = load_gap_manifest(manifest_path)

    assert loaded.session_id == "test-session-001"
    assert loaded.created_at == "2026-03-23T00:00:00"
    assert loaded.baseline_cqs == pytest.approx(0.7834)
    assert loaded.eval_cohort == ["JPM", "XOM", "JNJ"]
    assert loaded.config_fingerprint == "abc123def456"
    assert loaded.deterministic_kept == 5
    assert loaded.deterministic_discarded == 12
    assert len(loaded.gaps) == 2

    loaded_a = loaded.gaps[0]
    assert loaded_a.ticker == "JPM"
    assert loaded_a.metric == "NetIncome"
    assert loaded_a.difficulty_tier == "standard"

    loaded_b = loaded.gaps[1]
    assert loaded_b.ticker == "XOM"
    assert loaded_b.metric == "Revenue"
    assert loaded_b.gap_type == "regression"
    assert loaded_b.difficulty_tier == "hard"
    assert loaded_b.graveyard_count == 7


# =============================================================================
# 3–6. _compute_difficulty_tier
# =============================================================================

def test_compute_difficulty_tier_standard():
    """graveyard_count=3, gap_type=high_variance, no special root_cause -> standard."""
    gap = _make_metric_gap(graveyard_count=3, gap_type="high_variance", root_cause=None)
    assert _compute_difficulty_tier(gap) == "standard"


def test_compute_difficulty_tier_hard_graveyard():
    """graveyard_count=6 -> hard regardless of gap_type."""
    gap = _make_metric_gap(graveyard_count=6, gap_type="high_variance")
    assert _compute_difficulty_tier(gap) == "hard"


def test_compute_difficulty_tier_hard_graveyard_above_threshold():
    """graveyard_count=10 -> still hard."""
    gap = _make_metric_gap(graveyard_count=10, gap_type="unmapped")
    assert _compute_difficulty_tier(gap) == "hard"


def test_compute_difficulty_tier_hard_regression():
    """gap_type=regression -> hard even with low graveyard count."""
    gap = _make_metric_gap(graveyard_count=1, gap_type="regression")
    assert _compute_difficulty_tier(gap) == "hard"


def test_compute_difficulty_tier_hard_root_cause_extension():
    """root_cause=extension_concept -> hard."""
    gap = _make_metric_gap(graveyard_count=2, gap_type="high_variance", root_cause="extension_concept")
    assert _compute_difficulty_tier(gap) == "hard"


def test_compute_difficulty_tier_hard_root_cause_algebraic():
    """root_cause=algebraic_coincidence -> hard."""
    gap = _make_metric_gap(graveyard_count=2, gap_type="high_variance", root_cause="algebraic_coincidence")
    assert _compute_difficulty_tier(gap) == "hard"


def test_compute_difficulty_tier_standard_unrelated_root_cause():
    """root_cause that is not special -> standard (assuming low graveyard)."""
    gap = _make_metric_gap(graveyard_count=2, gap_type="high_variance", root_cause="missing_concept")
    assert _compute_difficulty_tier(gap) == "standard"


# =============================================================================
# 7. _build_unresolved_gap with extraction evidence
# =============================================================================

def test_build_unresolved_gap_with_evidence():
    """ExtractionEvidence fields are denormalized into UnresolvedGap."""
    evidence = ExtractionEvidence(
        metric="OperatingIncome",
        ticker="JNJ",
        reference_value=15_000_000.0,
        extracted_value=14_750_000.0,
        resolution_type="composite",
        components_used=["OperatingIncomeLoss"],
        components_missing=["ResearchAndDevelopmentExpense"],
        period_selected="2024-Q4",
        variance_pct=1.7,
        failure_reason="partial composite",
        company_industry="Healthcare",
    )

    gap = _make_metric_gap(
        ticker="JNJ",
        metric="OperatingIncome",
        extraction_evidence=evidence,
    )
    graveyard_entries = [
        {
            "config_diff": "add_concept: us-gaap:OperatingIncomeLoss",
            "discard_reason": "regression",
            "detail": "Caused regression in ABBV",
            "target_companies": "JNJ",
            "change_type": "add_concept",
            "timestamp": "2026-01-01T00:00:00",
        }
    ]

    result = _build_unresolved_gap(gap, graveyard_entries, AIAgentType.SEMANTIC_MAPPER)

    assert result.ticker == "JNJ"
    assert result.metric == "OperatingIncome"
    assert result.resolution_type == "composite"
    assert result.components_used == ["OperatingIncomeLoss"]
    assert result.components_missing == ["ResearchAndDevelopmentExpense"]
    assert result.company_industry == "Healthcare"
    assert result.ai_agent_type == AIAgentType.SEMANTIC_MAPPER.value
    assert result.difficulty_tier == "standard"  # graveyard_count=3, not regression


# =============================================================================
# 8. _build_unresolved_gap without extraction evidence
# =============================================================================

def test_build_unresolved_gap_without_evidence():
    """MetricGap with no extraction_evidence -> defaults for evidence fields."""
    gap = _make_metric_gap(
        ticker="CVX",
        metric="Revenue",
        extraction_evidence=None,
    )

    result = _build_unresolved_gap(gap, [], AIAgentType.REGRESSION_INVESTIGATOR)

    assert result.resolution_type == "none"
    assert result.components_used == []
    assert result.components_missing == []
    assert result.company_industry is None
    assert result.graveyard_entries == []
    assert result.ai_agent_type == AIAgentType.REGRESSION_INVESTIGATOR.value


# =============================================================================
# 9. _build_unresolved_gap filters graveyard by ticker
# =============================================================================

def test_build_unresolved_gap_filters_graveyard_by_ticker():
    """Only graveyard entries whose target_companies contains the gap ticker are kept."""
    graveyard_entries = [
        {
            "config_diff": "add_concept: us-gaap:Revenue",
            "discard_reason": "no_improvement",
            "detail": "no change",
            "target_companies": "PFE",
            "change_type": "add_concept",
            "timestamp": "2026-01-01",
        },
        {
            "config_diff": "add_concept: us-gaap:RevenueFromContractWithCustomer",
            "discard_reason": "regression",
            "detail": "ABBV dropped",
            "target_companies": "ABBV",
            "change_type": "add_concept",
            "timestamp": "2026-01-02",
        },
        {
            "config_diff": "add_concept: us-gaap:TotalRevenues",
            "discard_reason": "no_improvement",
            "detail": "same result",
            "target_companies": "PFE",
            "change_type": "add_concept",
            "timestamp": "2026-01-03",
        },
    ]

    gap = _make_metric_gap(ticker="PFE", metric="Revenue", graveyard_count=3)
    result = _build_unresolved_gap(gap, graveyard_entries, AIAgentType.SEMANTIC_MAPPER)

    # Only the two PFE entries should survive
    assert len(result.graveyard_entries) == 2
    for entry in result.graveyard_entries:
        assert "PFE" in entry.get("target_companies", "")


# =============================================================================
# 10–14. parse_gpt_response
# =============================================================================

def test_parse_gpt_response_valid_json():
    """Well-formed JSON with all required fields produces a ConfigChange."""
    response = json.dumps({
        "change_type": "ADD_CONCEPT",
        "file": "metrics.yaml",
        "yaml_path": "metrics.Revenue.known_concepts",
        "new_value": "us-gaap:SalesRevenueNet",
        "rationale": "This concept maps correctly to Revenue for XOM",
    })

    result = parse_gpt_response(response, "XOM", "Revenue")

    assert result is not None
    assert result.change_type == ChangeType.ADD_CONCEPT
    assert result.file == "metrics.yaml"
    assert result.yaml_path == "metrics.Revenue.known_concepts"
    assert result.new_value == "us-gaap:SalesRevenueNet"
    assert "XOM" in result.target_companies
    assert result.target_metric == "Revenue"
    # Rationale is prefixed with [AI]
    assert "[AI]" in result.rationale
    assert "XOM" in result.rationale or "correctly" in result.rationale


def test_parse_gpt_response_invalid_json():
    """Malformed JSON returns None without raising."""
    result = parse_gpt_response("{ not valid json !!!", "XOM", "Revenue")
    assert result is None


def test_parse_gpt_response_missing_fields():
    """JSON missing required fields returns None."""
    response = json.dumps({
        "change_type": "ADD_CONCEPT",
        "file": "metrics.yaml",
        # yaml_path, new_value, rationale all missing
    })

    result = parse_gpt_response(response, "XOM", "Revenue")
    assert result is None


def test_parse_gpt_response_strips_markdown_fences():
    """JSON wrapped in triple-backtick fences is still parsed correctly."""
    inner = json.dumps({
        "change_type": "ADD_EXCLUSION",
        "file": "companies.yaml",
        "yaml_path": "companies.BRK-B.exclude_metrics",
        "new_value": "EPS",
        "rationale": "Berkshire does not report EPS in standard form",
    })
    fenced_response = f"```json\n{inner}\n```"

    result = parse_gpt_response(fenced_response, "BRK-B", "EPS")

    assert result is not None
    assert result.change_type == ChangeType.ADD_EXCLUSION
    assert result.file == "companies.yaml"
    assert result.new_value == "EPS"


def test_parse_gpt_response_non_tier1_file():
    """Proposing a file not in TIER1_CONFIGS returns None."""
    response = json.dumps({
        "change_type": "ADD_CONCEPT",
        "file": "some_other.yaml",
        "yaml_path": "metrics.Revenue.known_concepts",
        "new_value": "us-gaap:Revenue",
        "rationale": "Should be ignored",
    })

    result = parse_gpt_response(response, "XOM", "Revenue")
    assert result is None


# =============================================================================
# 15. build_consultation_prompt — standard gap
# =============================================================================

def test_build_consultation_prompt_standard():
    """Prompt for a standard gap contains key identifiers and gap details."""
    gap = _make_unresolved_gap(
        ticker="NVO",
        metric="GrossProfit",
        gap_type="high_variance",
        difficulty_tier="standard",
        graveyard_count=2,
        resolution_type="direct",
        components_used=["GrossProfit"],
        components_missing=[],
        company_industry="Pharmaceuticals",
    )

    prompt = build_consultation_prompt(gap)

    # Must contain ticker and metric
    assert "NVO" in prompt
    assert "GrossProfit" in prompt

    # Must contain gap_type
    assert "high_variance" in prompt

    # Must contain evidence section (resolution_type is not "none")
    assert "Resolution type: direct" in prompt
    assert "Pharmaceuticals" in prompt

    # Must NOT contain hard-gap section for standard tier
    assert "HARD gap" not in prompt


# =============================================================================
# 16. build_consultation_prompt — hard gap
# =============================================================================

def test_build_consultation_prompt_hard():
    """Prompt for a hard-tier gap contains the HARD gap difficulty section."""
    gap = _make_unresolved_gap(
        ticker="TSM",
        metric="Revenue",
        gap_type="regression",
        difficulty_tier="hard",
        graveyard_count=7,
        root_cause="extension_concept",
        resolution_type="none",
        components_used=[],
        components_missing=["us-gaap:Revenue"],
        graveyard_entries=[
            {
                "config_diff": "add_concept: xyz",
                "discard_reason": "regression",
                "detail": "broke AAPL",
                "target_companies": "TSM",
            }
        ],
    )

    prompt = build_consultation_prompt(gap)

    # Hard-gap difficulty section must appear
    assert "HARD gap" in prompt

    # Should explain one or more hard-gap reasons
    assert any(
        phrase in prompt
        for phrase in ["prior failures", "regression gap", "extension_concept"]
    )

    # Graveyard entry must be represented
    assert "broke AAPL" in prompt


# =============================================================================
# 17. consult_ai_gaps — mock AI caller returns valid proposals
# =============================================================================

def test_consult_ai_gaps_with_mock_caller(tmp_path):
    """consult_ai_gaps returns ProposalRecords when mock AI returns valid JSON."""
    gap = _make_unresolved_gap(
        ticker="CVX",
        metric="Revenue",
        gap_type="high_variance",
        difficulty_tier="standard",
        graveyard_count=3,
    )
    manifest = GapManifest(
        session_id="mock-session-001",
        created_at="2026-03-23T00:00:00",
        baseline_cqs=0.80,
        eval_cohort=["CVX"],
        gaps=[gap],
        config_fingerprint="any-fingerprint",
    )
    manifest_path = tmp_path / "manifest_mock.json"
    save_gap_manifest(manifest, manifest_path)

    valid_response = json.dumps({
        "change_type": "ADD_CONCEPT",
        "file": "metrics.yaml",
        "yaml_path": "metrics.Revenue.known_concepts",
        "new_value": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        "rationale": "Standard XBRL concept for energy sector Revenue",
    })

    def mock_ai_caller(prompt: str, model: str) -> str:
        return valid_response

    proposals = consult_ai_gaps(manifest_path, mock_ai_caller, max_gaps=0)

    assert len(proposals) == 1
    pr = proposals[0]
    assert pr.gap.ticker == "CVX"
    assert pr.gap.metric == "Revenue"
    assert pr.proposal.change_type == ChangeType.ADD_CONCEPT
    assert pr.proposal.file == "metrics.yaml"
    assert pr.proposal.source == "ai_agent"
    # worker_id encodes the model used
    assert "sonnet" in pr.worker_id  # standard tier -> sonnet


# =============================================================================
# 18. consult_ai_gaps — AI caller raises Exception
# =============================================================================

def test_consult_ai_gaps_handles_ai_failure(tmp_path):
    """An AI caller that raises an exception is caught; returns empty list."""
    gap = _make_unresolved_gap(ticker="XOM", metric="Revenue")
    manifest = GapManifest(
        session_id="fail-session-001",
        created_at="2026-03-23T00:00:00",
        baseline_cqs=0.78,
        eval_cohort=["XOM"],
        gaps=[gap],
        config_fingerprint="any-fingerprint",
    )
    manifest_path = tmp_path / "manifest_fail.json"
    save_gap_manifest(manifest, manifest_path)

    def failing_ai_caller(prompt: str, model: str) -> str:
        raise RuntimeError("Network unreachable")

    proposals = consult_ai_gaps(manifest_path, failing_ai_caller)

    # Must not raise; must return empty list
    assert proposals == []


# =============================================================================
# 19. consult_ai_gaps — config drift (mismatched fingerprint)
# =============================================================================

def test_consult_ai_gaps_config_drift_warning(tmp_path):
    """Mismatched config fingerprint still processes gaps (logs warning only)."""
    gap = _make_unresolved_gap(ticker="JNJ", metric="NetIncome")
    manifest = GapManifest(
        session_id="drift-session-001",
        created_at="2026-03-23T00:00:00",
        baseline_cqs=0.82,
        eval_cohort=["JNJ"],
        gaps=[gap],
        config_fingerprint="deliberately-wrong-fingerprint-xyz",
    )
    manifest_path = tmp_path / "manifest_drift.json"
    save_gap_manifest(manifest, manifest_path)

    valid_response = json.dumps({
        "change_type": "ADD_DIVERGENCE",
        "file": "companies.yaml",
        "yaml_path": "companies.JNJ.known_divergences",
        "new_value": {"NetIncome": "yfinance excludes minority interest"},
        "rationale": "Structural mismatch documented",
    })

    def mock_ai_caller(prompt: str, model: str) -> str:
        return valid_response

    # Should not raise even with drifted fingerprint
    proposals = consult_ai_gaps(manifest_path, mock_ai_caller)
    assert len(proposals) == 1


# =============================================================================
# 20. consult_ai_gaps — model routing by difficulty tier
# =============================================================================

def test_consult_ai_gaps_model_routing(tmp_path):
    """Standard gaps use sonnet; hard gaps use opus."""
    standard_gap = _make_unresolved_gap(
        ticker="PFE",
        metric="Revenue",
        difficulty_tier="standard",
        graveyard_count=3,
        ai_agent_type="semantic_mapper",
    )
    hard_gap = _make_unresolved_gap(
        ticker="JNJ",
        metric="OperatingIncome",
        gap_type="regression",
        difficulty_tier="hard",
        graveyard_count=7,
        ai_agent_type="regression_investigator",
    )

    manifest = GapManifest(
        session_id="routing-session-001",
        created_at="2026-03-23T00:00:00",
        baseline_cqs=0.79,
        eval_cohort=["PFE", "JNJ"],
        gaps=[standard_gap, hard_gap],
        config_fingerprint="any-fingerprint",
    )
    manifest_path = tmp_path / "manifest_routing.json"
    save_gap_manifest(manifest, manifest_path)

    calls: list = []

    def tracking_ai_caller(prompt: str, model: str) -> str:
        calls.append(model)
        return json.dumps({
            "change_type": "ADD_EXCLUSION",
            "file": "companies.yaml",
            "yaml_path": f"companies.TICKER.exclude_metrics",
            "new_value": "SomeMetric",
            "rationale": "Unresolvable structural mismatch",
        })

    proposals = consult_ai_gaps(manifest_path, tracking_ai_caller)

    assert len(calls) == 2, f"Expected 2 AI calls, got {len(calls)}"

    # First call is for standard gap -> sonnet
    assert calls[0] == "sonnet", f"Standard gap should use sonnet, got {calls[0]}"

    # Second call is for hard gap -> opus
    assert calls[1] == "opus", f"Hard gap should use opus, got {calls[1]}"

    # Worker IDs encode the model
    worker_ids = [pr.worker_id for pr in proposals]
    assert any("sonnet" in wid for wid in worker_ids)
    assert any("opus" in wid for wid in worker_ids)


# =============================================================================
# 21. build_agent_prompt — includes tool instructions
# =============================================================================

def test_build_agent_prompt_includes_tool_instructions():
    """Agent prompt for standard gap contains Sonnet tool instructions."""
    gap = _make_unresolved_gap(
        ticker="CVX",
        metric="Revenue",
        difficulty_tier="standard",
    )

    prompt = build_agent_prompt(gap)

    assert "discover_concepts" in prompt
    assert "verify_mapping" in prompt
    assert "Tool Usage Instructions" in prompt
    # Standard tier gets Sonnet instructions
    assert "Sonnet Solver" in prompt
    assert "Opus Investigation" not in prompt


# =============================================================================
# 22. build_agent_prompt — includes machine-readable gap JSON
# =============================================================================

def test_build_agent_prompt_includes_gap_json():
    """Agent prompt contains machine-readable JSON with gap fields."""
    gap = _make_unresolved_gap(
        ticker="XOM",
        metric="OperatingIncome",
        difficulty_tier="hard",
        graveyard_count=7,
    )

    prompt = build_agent_prompt(gap)

    # Must contain the gap JSON block
    assert '"ticker": "XOM"' in prompt
    assert '"metric": "OperatingIncome"' in prompt
    assert "Machine-Readable Gap Context" in prompt
    # Hard tier gets Opus instructions
    assert "Opus Investigation" in prompt
    assert "learn_mappings" in prompt


# =============================================================================
# 23. collect_agent_proposals — valid responses
# =============================================================================

def test_collect_agent_proposals_valid():
    """Valid JSON responses produce ProposalRecords with correct fields."""
    gap = _make_unresolved_gap(
        ticker="PFE",
        metric="Revenue",
        difficulty_tier="standard",
        ai_agent_type="semantic_mapper",
    )

    valid_response = json.dumps({
        "change_type": "ADD_CONCEPT",
        "file": "metrics.yaml",
        "yaml_path": "metrics.Revenue.known_concepts",
        "new_value": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        "rationale": "discover_concepts found it; verify_mapping confirms 2.1% variance",
    })

    proposals = collect_agent_proposals([(gap, valid_response)])

    assert len(proposals) == 1
    pr = proposals[0]
    assert pr.gap.ticker == "PFE"
    assert pr.proposal.change_type == ChangeType.ADD_CONCEPT
    assert pr.proposal.source == "ai_agent"
    assert pr.proposal.ai_agent_type == "semantic_mapper"
    assert pr.worker_id == "agent_sonnet"


# =============================================================================
# 24. collect_agent_proposals — skips None responses
# =============================================================================

def test_collect_agent_proposals_skips_none():
    """None responses are gracefully skipped."""
    gap = _make_unresolved_gap(ticker="XOM", metric="Revenue")

    proposals = collect_agent_proposals([(gap, None)])

    assert proposals == []


# =============================================================================
# 25. collect_agent_proposals — skips invalid JSON
# =============================================================================

def test_collect_agent_proposals_skips_invalid():
    """Invalid JSON responses are skipped without raising."""
    gap = _make_unresolved_gap(ticker="JNJ", metric="NetIncome")

    proposals = collect_agent_proposals([(gap, "not valid json at all")])

    assert proposals == []


# =============================================================================
# 26. collect_agent_proposals — model routing by difficulty tier
# =============================================================================

def test_collect_agent_proposals_model_routing():
    """Standard gaps get agent_sonnet worker_id; hard gaps get agent_opus."""
    standard_gap = _make_unresolved_gap(
        ticker="PFE",
        metric="Revenue",
        difficulty_tier="standard",
        ai_agent_type="semantic_mapper",
    )
    hard_gap = _make_unresolved_gap(
        ticker="MS",
        metric="CashAndEquivalents",
        difficulty_tier="hard",
        graveyard_count=8,
        ai_agent_type="pattern_learner",
    )

    valid_response = json.dumps({
        "change_type": "ADD_EXCLUSION",
        "file": "companies.yaml",
        "yaml_path": "companies.TICKER.exclude_metrics",
        "new_value": "SomeMetric",
        "rationale": "Structural mismatch",
    })

    responses = [
        (standard_gap, valid_response),
        (hard_gap, valid_response),
    ]

    proposals = collect_agent_proposals(responses)

    assert len(proposals) == 2
    assert proposals[0].worker_id == "agent_sonnet"
    assert proposals[1].worker_id == "agent_opus"
