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
    ACTION_VOCABULARY,
    BenchmarkConfig,
    BenchmarkResult,
    COP_OUT_TYPES,
    TypedAction,
    _gap_key,
    build_agent_prompt,
    build_consultation_prompt,
    build_typed_action_prompt,
    collect_agent_proposals,
    collect_typed_proposals,
    compile_action,
    consult_ai_gaps,
    load_agent_responses,
    parse_typed_action,
    print_benchmark_comparison,
    run_agent_benchmark,
    save_agent_responses,
    validate_action_preflight,
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


# =============================================================================
# 27. _gap_key format
# =============================================================================

def test_gap_key_format():
    """_gap_key returns 'TICKER:Metric' format."""
    gap = _make_unresolved_gap(ticker="XOM", metric="Revenue")
    assert _gap_key(gap) == "XOM:Revenue"


# =============================================================================
# 28. save/load agent responses round-trip
# =============================================================================

def test_save_load_agent_responses_roundtrip(tmp_path, monkeypatch):
    """Save 2 responses, load back, verify content."""
    import edgar.xbrl.standardization.tools.consult_ai_gaps as _mod
    monkeypatch.setattr(_mod, "GAP_MANIFESTS_DIR", tmp_path)

    gap_a = _make_unresolved_gap(ticker="XOM", metric="GrossProfit")
    gap_b = _make_unresolved_gap(ticker="JPM", metric="NetIncome")

    responses = [
        (gap_a, '{"change_type": "ADD_CONCEPT", "rationale": "test"}'),
        (gap_b, '{"change_type": "ADD_EXCLUSION", "rationale": "test2"}'),
    ]

    path = save_agent_responses("sess-001", responses)
    assert path.exists()

    cache = load_agent_responses("sess-001")
    assert cache["XOM:GrossProfit"] == '{"change_type": "ADD_CONCEPT", "rationale": "test"}'
    assert cache["JPM:NetIncome"] == '{"change_type": "ADD_EXCLUSION", "rationale": "test2"}'


# =============================================================================
# 29. load_agent_responses excludes null
# =============================================================================

def test_load_agent_responses_excludes_null(tmp_path, monkeypatch):
    """Null responses are excluded from the returned dict."""
    import edgar.xbrl.standardization.tools.consult_ai_gaps as _mod
    monkeypatch.setattr(_mod, "GAP_MANIFESTS_DIR", tmp_path)

    gap_a = _make_unresolved_gap(ticker="XOM", metric="Revenue")
    gap_b = _make_unresolved_gap(ticker="JPM", metric="NetIncome")

    responses = [
        (gap_a, '{"some": "response"}'),
        (gap_b, None),  # failed attempt
    ]

    save_agent_responses("sess-null", responses)
    cache = load_agent_responses("sess-null")

    assert "XOM:Revenue" in cache
    assert "JPM:NetIncome" not in cache


# =============================================================================
# 30. load_agent_responses nonexistent file
# =============================================================================

def test_load_agent_responses_nonexistent(tmp_path, monkeypatch):
    """Missing cache file returns empty dict, no exception."""
    import edgar.xbrl.standardization.tools.consult_ai_gaps as _mod
    monkeypatch.setattr(_mod, "GAP_MANIFESTS_DIR", tmp_path)

    cache = load_agent_responses("does-not-exist")
    assert cache == {}


# =============================================================================
# 31. collect_agent_proposals auto-save with session_id
# =============================================================================

def test_collect_agent_proposals_auto_save(tmp_path, monkeypatch):
    """With session_id, both response cache and proposals file are written."""
    import edgar.xbrl.standardization.tools.consult_ai_gaps as _mod
    monkeypatch.setattr(_mod, "GAP_MANIFESTS_DIR", tmp_path)

    gap = _make_unresolved_gap(ticker="PFE", metric="Revenue", difficulty_tier="standard")
    valid_response = json.dumps({
        "change_type": "ADD_CONCEPT",
        "file": "metrics.yaml",
        "yaml_path": "metrics.Revenue.known_concepts",
        "new_value": "us-gaap:RevenueNet",
        "rationale": "Test rationale",
    })

    proposals = collect_agent_proposals(
        [(gap, valid_response)],
        session_id="auto-save-001",
    )

    assert len(proposals) == 1
    # Response cache file must exist
    assert (tmp_path / "agent_responses_auto-save-001.json").exists()
    # Proposals file must exist (non-empty proposals)
    assert (tmp_path / "ai_proposals_auto-save-001.json").exists()


# =============================================================================
# 32. collect_agent_proposals no save without session_id
# =============================================================================

def test_collect_agent_proposals_no_save_without_session_id(tmp_path, monkeypatch):
    """Without session_id, no files are written."""
    import edgar.xbrl.standardization.tools.consult_ai_gaps as _mod
    monkeypatch.setattr(_mod, "GAP_MANIFESTS_DIR", tmp_path)

    gap = _make_unresolved_gap(ticker="PFE", metric="Revenue", difficulty_tier="standard")
    valid_response = json.dumps({
        "change_type": "ADD_CONCEPT",
        "file": "metrics.yaml",
        "yaml_path": "metrics.Revenue.known_concepts",
        "new_value": "us-gaap:RevenueNet",
        "rationale": "Test rationale",
    })

    proposals = collect_agent_proposals([(gap, valid_response)])

    assert len(proposals) == 1
    # No files should be written
    json_files = list(tmp_path.glob("*.json"))
    assert json_files == []


# =============================================================================
# 33. BenchmarkConfig dataclass
# =============================================================================

def test_benchmark_config_dataclass():
    """BenchmarkConfig fields are accessible."""
    config = BenchmarkConfig(
        prompt_builder=build_consultation_prompt,
        model="sonnet",
        label="Base Sonnet",
    )
    assert config.model == "sonnet"
    assert config.label == "Base Sonnet"
    assert config.prompt_builder is build_consultation_prompt


# =============================================================================
# 34. BenchmarkResult properties
# =============================================================================

def test_benchmark_result_properties():
    """resolution_rate, cop_out_rate, cqs_lift computed correctly."""
    config = BenchmarkConfig(build_consultation_prompt, "sonnet", "Test")
    result = BenchmarkResult(
        config=config,
        total_gaps=10,
        valid_proposals=8,
        kept=3,
        discarded=4,
        vetoed=1,
        cop_outs=2,
        cqs_start=0.80,
        cqs_end=0.85,
    )
    assert result.resolution_rate == pytest.approx(0.3)       # 3/10
    assert result.cop_out_rate == pytest.approx(0.25)          # 2/8
    assert result.cqs_lift == pytest.approx(0.05)              # 0.85 - 0.80


# =============================================================================
# 35. BenchmarkResult zero division
# =============================================================================

def test_benchmark_result_zero_division():
    """0 gaps/proposals doesn't crash."""
    config = BenchmarkConfig(build_consultation_prompt, "sonnet", "Empty")
    result = BenchmarkResult(
        config=config,
        total_gaps=0,
        valid_proposals=0,
        kept=0,
        discarded=0,
        vetoed=0,
        cop_outs=0,
        cqs_start=0.80,
        cqs_end=0.80,
    )
    assert result.resolution_rate == 0.0
    assert result.cop_out_rate == 0.0
    assert result.cqs_lift == 0.0


# =============================================================================
# 36. Cop-out detection
# =============================================================================

def test_cop_out_detection():
    """ADD_DIVERGENCE and ADD_EXCLUSION are cop-outs; ADD_CONCEPT is not."""
    assert ChangeType.ADD_DIVERGENCE in COP_OUT_TYPES
    assert ChangeType.ADD_EXCLUSION in COP_OUT_TYPES
    assert ChangeType.ADD_CONCEPT not in COP_OUT_TYPES
    assert ChangeType.ADD_STANDARDIZATION not in COP_OUT_TYPES


# =============================================================================
# 37. Benchmark uses response cache (no AI calls)
# =============================================================================

def test_benchmark_uses_response_cache(tmp_path, monkeypatch):
    """Pre-seeded cache means ai_caller is NOT called."""
    import edgar.xbrl.standardization.tools.consult_ai_gaps as _mod
    monkeypatch.setattr(_mod, "GAP_MANIFESTS_DIR", tmp_path)

    # Create manifest
    gap = _make_unresolved_gap(
        ticker="CVX", metric="Revenue",
        difficulty_tier="standard", graveyard_count=2,
    )
    manifest = GapManifest(
        session_id="bench-cache-001",
        created_at="2026-03-23T00:00:00",
        baseline_cqs=0.80,
        eval_cohort=["CVX"],
        gaps=[gap],
        config_fingerprint="any",
    )
    manifest_path = tmp_path / "manifest_bench.json"
    save_gap_manifest(manifest, manifest_path)

    # Pre-seed cache for the arm
    valid_response = json.dumps({
        "change_type": "ADD_CONCEPT",
        "file": "metrics.yaml",
        "yaml_path": "metrics.Revenue.known_concepts",
        "new_value": "us-gaap:RevenueNet",
        "rationale": "cached",
    })
    cache_data = [{"gap_key": "CVX:Revenue", "response_text": valid_response}]
    cache_path = tmp_path / "agent_responses_bench-cache-001_base_sonnet.json"
    cache_path.write_text(json.dumps(cache_data))

    # Mock compute_cqs and evaluate_experiment to avoid real computation
    from unittest.mock import MagicMock
    from edgar.xbrl.standardization.tools.auto_eval import CQSResult

    fake_cqs = MagicMock(spec=CQSResult)
    fake_cqs.cqs = 0.82
    monkeypatch.setattr(_mod, "compute_cqs", lambda **kwargs: fake_cqs)

    from edgar.xbrl.standardization.tools.auto_eval_loop import ExperimentDecision, Decision
    fake_decision = ExperimentDecision(
        decision=Decision.KEEP,
        cqs_before=0.80,
        cqs_after=0.82,
        reason="improved",
        new_cqs_result=fake_cqs,
    )
    monkeypatch.setattr(_mod, "evaluate_experiment", lambda *a, **kw: fake_decision)

    ai_calls = []

    def spy_caller(prompt: str, model: str) -> str:
        ai_calls.append((prompt, model))
        return valid_response

    config = BenchmarkConfig(build_consultation_prompt, "sonnet", "Base Sonnet")
    results = run_agent_benchmark(
        manifest_path=manifest_path,
        configs=[config],
        ai_caller=spy_caller,
        max_gaps=1,
    )

    # ai_caller should NOT have been called (cache hit)
    assert ai_calls == [], f"Expected no AI calls but got {len(ai_calls)}"

    assert len(results) == 1
    r = results[0]
    assert r.total_gaps == 1
    assert r.valid_proposals == 1
    assert r.kept == 1


# =============================================================================
# 38. print_benchmark_comparison smoke test
# =============================================================================

def test_print_benchmark_comparison_smoke(capsys):
    """print_benchmark_comparison doesn't raise and outputs a table."""
    config = BenchmarkConfig(build_consultation_prompt, "sonnet", "Test Arm")
    result = BenchmarkResult(
        config=config,
        total_gaps=5,
        valid_proposals=3,
        kept=2,
        discarded=1,
        vetoed=0,
        cop_outs=1,
        cqs_start=0.80,
        cqs_end=0.83,
    )

    print_benchmark_comparison([result])

    captured = capsys.readouterr()
    assert "Agent Benchmark Comparison" in captured.out
    assert "Test Arm" in captured.out


# =============================================================================
# PHASE 1: TypedAction Schema Tests (39–42)
# =============================================================================

def test_typed_action_valid_map_concept():
    """Valid MAP_CONCEPT response parses into TypedAction correctly."""
    response = json.dumps({
        "action": "MAP_CONCEPT",
        "ticker": "XOM",
        "metric": "GrossProfit",
        "params": {"concept": "us-gaap:GrossProfit"},
        "rationale": "XOM reports GrossProfit directly in XBRL",
        "confidence": 0.85,
    })

    result = parse_typed_action(response, "XOM", "GrossProfit")

    assert result is not None
    assert result.action == "MAP_CONCEPT"
    assert result.ticker == "XOM"
    assert result.metric == "GrossProfit"
    assert result.params["concept"] == "us-gaap:GrossProfit"
    assert result.rationale == "XOM reports GrossProfit directly in XBRL"
    assert result.confidence == pytest.approx(0.85)


def test_typed_action_unknown_action_rejected():
    """Action not in ACTION_VOCABULARY returns None."""
    response = json.dumps({
        "action": "INVENT_NEW_METRIC",
        "ticker": "XOM",
        "metric": "Revenue",
        "params": {"concept": "us-gaap:Revenue"},
        "rationale": "test",
        "confidence": 0.5,
    })

    result = parse_typed_action(response, "XOM", "Revenue")
    assert result is None


def test_typed_action_missing_required_param():
    """Missing 'concept' for MAP_CONCEPT returns None."""
    response = json.dumps({
        "action": "MAP_CONCEPT",
        "ticker": "XOM",
        "metric": "Revenue",
        "params": {},  # Missing "concept"
        "rationale": "test",
        "confidence": 0.5,
    })

    result = parse_typed_action(response, "XOM", "Revenue")
    assert result is None


def test_typed_action_strips_markdown_fences():
    """JSON inside ```json fences still parses correctly."""
    inner = json.dumps({
        "action": "FIX_SIGN_CONVENTION",
        "ticker": "AAPL",
        "metric": "ShareRepurchases",
        "params": {},
        "rationale": "Sign convention mismatch",
        "confidence": 0.9,
    })
    fenced = f"```json\n{inner}\n```"

    result = parse_typed_action(fenced, "AAPL", "ShareRepurchases")

    assert result is not None
    assert result.action == "FIX_SIGN_CONVENTION"
    assert result.ticker == "AAPL"


# =============================================================================
# PHASE 2: Action Compiler Tests (43–47)
# =============================================================================

def test_compile_map_concept():
    """MAP_CONCEPT produces correct yaml_path and ChangeType."""
    action = TypedAction(
        action="MAP_CONCEPT",
        ticker="XOM",
        metric="GrossProfit",
        params={"concept": "us-gaap:GrossProfit"},
        rationale="Direct XBRL concept",
    )

    change = compile_action(action)

    assert change is not None
    assert change.change_type == ChangeType.ADD_CONCEPT
    assert change.file == "metrics.yaml"
    assert change.yaml_path == "metrics.GrossProfit.known_concepts"
    assert change.new_value == "us-gaap:GrossProfit"
    assert change.target_metric == "GrossProfit"
    assert change.target_companies == "XOM"
    assert change.source == "ai_agent"


def test_compile_fix_sign_convention():
    """FIX_SIGN_CONVENTION produces ADD_COMPANY_OVERRIDE with sign_negate dict."""
    action = TypedAction(
        action="FIX_SIGN_CONVENTION",
        ticker="AAPL",
        metric="ShareRepurchases",
        params={},
        rationale="Sign inversion",
    )

    change = compile_action(action)

    assert change is not None
    assert change.change_type == ChangeType.ADD_COMPANY_OVERRIDE
    assert change.file == "companies.yaml"
    assert change.yaml_path == "companies.AAPL.metric_overrides.ShareRepurchases"
    assert change.new_value == {"sign_negate": True}


def test_compile_exclude_metric():
    """EXCLUDE_METRIC produces ADD_EXCLUSION with correct path."""
    action = TypedAction(
        action="EXCLUDE_METRIC",
        ticker="AMZN",
        metric="DividendsPaid",
        params={"reason_code": "not_reported"},
        rationale="Amazon does not pay dividends",
    )

    change = compile_action(action)

    assert change is not None
    assert change.change_type == ChangeType.ADD_EXCLUSION
    assert change.file == "companies.yaml"
    assert change.yaml_path == "companies.AMZN.exclude_metrics"
    assert change.new_value == "DividendsPaid"


def test_compile_escalate_returns_none():
    """ESCALATE action produces no ConfigChange."""
    action = TypedAction(
        action="ESCALATE",
        ticker="MS",
        metric="CashAndEquivalents",
        params={"reason": "Requires new engine capability"},
        rationale="Cannot resolve with config changes",
    )

    change = compile_action(action)
    assert change is None


def test_preflight_rejects_duplicate_concept(tmp_path, monkeypatch):
    """Concept already in known_concepts -> preflight error string."""
    import yaml
    from edgar.xbrl.standardization.tools import auto_eval_loop as _loop_mod
    from edgar.xbrl.standardization.tools.consult_ai_gaps import _load_metrics_config

    # Write a fake metrics.yaml with Revenue having a known concept
    fake_config_dir = tmp_path / "config"
    fake_config_dir.mkdir()
    fake_metrics = fake_config_dir / "metrics.yaml"
    fake_metrics.write_text(yaml.dump({
        "metrics": {
            "Revenue": {
                "known_concepts": ["us-gaap:Revenue", "us-gaap:Revenues"],
            }
        }
    }))

    # Patch TIER1_CONFIGS to point at our fake and invalidate cache
    original_configs = _loop_mod.TIER1_CONFIGS.copy()
    _loop_mod.TIER1_CONFIGS["metrics.yaml"] = fake_metrics
    _load_metrics_config._cache = None
    try:
        action = TypedAction(
            action="MAP_CONCEPT",
            ticker="XOM",
            metric="Revenue",
            params={"concept": "us-gaap:Revenue"},
        )

        err = validate_action_preflight(action)
        assert err is not None
        assert "already in" in err
        assert "us-gaap:Revenue" in err
    finally:
        _loop_mod.TIER1_CONFIGS.update(original_configs)
        _load_metrics_config._cache = None


# =============================================================================
# PHASE 3: Typed Action Prompt Tests (48–50)
# =============================================================================

def test_build_typed_action_prompt_contains_vocabulary():
    """Prompt lists all actions from ACTION_VOCABULARY."""
    gap = _make_unresolved_gap(
        ticker="XOM",
        metric="GrossProfit",
        difficulty_tier="standard",
    )

    prompt = build_typed_action_prompt(gap)

    for action_name in ACTION_VOCABULARY:
        assert action_name in prompt, f"Missing action {action_name} in prompt"


def test_build_typed_action_prompt_no_yaml_paths():
    """Prompt does NOT contain 'yaml_path' or config file paths."""
    gap = _make_unresolved_gap(
        ticker="XOM",
        metric="Revenue",
        difficulty_tier="standard",
    )

    prompt = build_typed_action_prompt(gap)

    assert "yaml_path" not in prompt
    assert "metrics.yaml" not in prompt
    assert "companies.yaml" not in prompt
    assert "edgar/xbrl/standardization/config" not in prompt


def test_collect_typed_proposals_end_to_end():
    """Valid MAP_CONCEPT response -> ProposalRecord with correct ConfigChange."""
    gap = _make_unresolved_gap(
        ticker="PFE",
        metric="Revenue",
        difficulty_tier="standard",
        ai_agent_type="semantic_mapper",
    )

    response = json.dumps({
        "action": "MAP_CONCEPT",
        "ticker": "PFE",
        "metric": "Revenue",
        "params": {"concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"},
        "rationale": "Standard ASC 606 concept for pharma",
        "confidence": 0.88,
    })

    proposals, preflight_rejected = collect_typed_proposals([(gap, response)])

    assert preflight_rejected == 0
    assert len(proposals) == 1
    pr = proposals[0]
    assert pr.gap.ticker == "PFE"
    assert pr.gap.metric == "Revenue"
    assert pr.proposal.change_type == ChangeType.ADD_CONCEPT
    assert pr.proposal.file == "metrics.yaml"
    assert pr.proposal.yaml_path == "metrics.Revenue.known_concepts"
    assert pr.proposal.new_value == "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
    assert pr.proposal.source == "ai_agent"
    assert "sonnet" in pr.worker_id


# =============================================================================
# PHASE 4: Benchmark Integration Tests (51–53)
# =============================================================================

def test_benchmark_config_typed_actions_flag():
    """use_typed_actions flag is accessible and defaults to False."""
    config_raw = BenchmarkConfig(build_consultation_prompt, "sonnet", "Raw")
    assert config_raw.use_typed_actions is False

    config_typed = BenchmarkConfig(
        build_typed_action_prompt, "sonnet", "Typed", use_typed_actions=True,
    )
    assert config_typed.use_typed_actions is True


def test_benchmark_result_preflight_field():
    """preflight_rejected field is tracked in BenchmarkResult."""
    config = BenchmarkConfig(build_consultation_prompt, "sonnet", "Test")
    result = BenchmarkResult(
        config=config,
        total_gaps=5,
        valid_proposals=3,
        kept=2,
        discarded=0,
        vetoed=0,
        cop_outs=1,
        cqs_start=0.80,
        cqs_end=0.82,
        preflight_rejected=1,
    )
    assert result.preflight_rejected == 1


def test_benchmark_typed_vs_raw_arms():
    """Typed action arm parses correctly; raw arm fails on same typed-action response."""
    gap = _make_unresolved_gap(
        ticker="XOM",
        metric="GrossProfit",
        difficulty_tier="standard",
        ai_agent_type="semantic_mapper",
    )

    # This is a valid TypedAction response (NOT a valid raw ConfigChange response)
    typed_response = json.dumps({
        "action": "MAP_CONCEPT",
        "ticker": "XOM",
        "metric": "GrossProfit",
        "params": {"concept": "us-gaap:GrossProfit"},
        "rationale": "Direct XBRL concept",
        "confidence": 0.85,
    })

    # Typed action pipeline should succeed
    typed_proposals, preflight_rejected = collect_typed_proposals([(gap, typed_response)])
    assert len(typed_proposals) == 1
    assert preflight_rejected == 0
    assert typed_proposals[0].proposal.change_type == ChangeType.ADD_CONCEPT

    # Raw pipeline should fail (response doesn't have file/yaml_path/new_value)
    raw_proposals = collect_agent_proposals([(gap, typed_response)])
    assert len(raw_proposals) == 0


# =============================================================================
# PHASE 5: E2E Test — Prove the Thesis (54)
# =============================================================================

def test_e2e_typed_actions_solve_raw_pipeline_failure(tmp_path, monkeypatch):
    """E2E: raw arm fails on valid XBRL reasoning; typed arm succeeds on same reasoning.

    Given 3 gaps where the AI has correct XBRL reasoning:
    - Raw arm: AI writes invented YAML paths -> evaluate_experiment DISCARDs all 3
    - Typed arm: Same reasoning as TypedAction -> compile_action generates valid paths
      -> evaluate_experiment KEEPs 2-3

    This directly demonstrates the thesis: AI should emit typed intents, not raw YAML.
    """
    import re
    from unittest.mock import MagicMock

    import edgar.xbrl.standardization.tools.consult_ai_gaps as _mod
    from edgar.xbrl.standardization.tools.auto_eval import CQSResult
    from edgar.xbrl.standardization.tools.auto_eval_loop import (
        Decision,
        ExperimentDecision,
    )

    # --- Setup: redirect manifests dir, invalidate metrics cache ---
    monkeypatch.setattr(_mod, "GAP_MANIFESTS_DIR", tmp_path)
    from edgar.xbrl.standardization.tools.consult_ai_gaps import _load_metrics_config
    _load_metrics_config._cache = None

    # --- Create manifest with 3 gaps ---
    gap_xom = _make_unresolved_gap(
        ticker="XOM", metric="GrossProfit",
        gap_type="high_variance", difficulty_tier="standard",
        graveyard_count=2, ai_agent_type="semantic_mapper",
    )
    gap_aapl = _make_unresolved_gap(
        ticker="AAPL", metric="ShareRepurchases",
        gap_type="high_variance", difficulty_tier="standard",
        graveyard_count=1, ai_agent_type="semantic_mapper",
    )
    gap_jpm = _make_unresolved_gap(
        ticker="JPM", metric="GrossProfit",
        gap_type="validation_failure", difficulty_tier="standard",
        graveyard_count=3, company_industry="Financial",
        ai_agent_type="semantic_mapper",
    )

    manifest = GapManifest(
        session_id="e2e-thesis-001",
        created_at="2026-03-24T00:00:00",
        baseline_cqs=0.78,
        eval_cohort=["XOM", "AAPL", "JPM"],
        gaps=[gap_xom, gap_aapl, gap_jpm],
        config_fingerprint="any",
    )
    manifest_path = tmp_path / "manifest_e2e_thesis.json"
    save_gap_manifest(manifest, manifest_path)

    # --- Raw responses: valid JSON, but invented YAML paths ---
    raw_responses = {
        "XOM:GrossProfit": json.dumps({
            "change_type": "ADD_CONCEPT",
            "file": "metrics.yaml",
            "yaml_path": "metrics.GrossProfit.company_specific.XOM.components",
            "new_value": "us-gaap:GrossProfit",
            "rationale": "XOM reports GrossProfit directly",
        }),
        "AAPL:ShareRepurchases": json.dumps({
            "change_type": "MODIFY_VALUE",
            "file": "companies.yaml",
            "yaml_path": "companies.AAPL.settings.sign_override",
            "new_value": {"sign_negate": True},
            "rationale": "Sign convention mismatch",
        }),
        "JPM:GrossProfit": json.dumps({
            "change_type": "ADD_EXCLUSION",
            "file": "companies.yaml",
            "yaml_path": "global_settings.industry_exclusions.banking",
            "new_value": "GrossProfit",
            "rationale": "Banks have no COGS",
        }),
    }

    # --- Typed responses: same reasoning, TypedAction format ---
    typed_responses = {
        "XOM:GrossProfit": json.dumps({
            "action": "MAP_CONCEPT",
            "ticker": "XOM", "metric": "GrossProfit",
            "params": {"concept": "us-gaap:GrossProfit"},
            "rationale": "XOM reports GrossProfit directly",
            "confidence": 0.85,
        }),
        "AAPL:ShareRepurchases": json.dumps({
            "action": "FIX_SIGN_CONVENTION",
            "ticker": "AAPL", "metric": "ShareRepurchases",
            "params": {},
            "rationale": "Sign convention mismatch",
            "confidence": 0.9,
        }),
        "JPM:GrossProfit": json.dumps({
            "action": "EXCLUDE_METRIC",
            "ticker": "JPM", "metric": "GrossProfit",
            "params": {"reason_code": "industry_structural"},
            "rationale": "Banks have no COGS",
            "confidence": 0.95,
        }),
    }

    # --- Mock AI caller: detect arm by prompt content ---
    def mock_ai_caller(prompt: str, model: str) -> str:
        is_typed = "Available Actions" in prompt
        # Extract ticker and metric from prompt
        for gap_key in ["XOM:GrossProfit", "AAPL:ShareRepurchases", "JPM:GrossProfit"]:
            ticker, metric = gap_key.split(":")
            if f"Ticker: {ticker}" in prompt and f"Metric: {metric}" in prompt:
                if is_typed:
                    return typed_responses[gap_key]
                else:
                    return raw_responses[gap_key]
        return "{}"

    # --- Smart mock evaluate_experiment: validates yaml_path ---
    VALID_PATH_PATTERNS = [
        r'^metrics\.\w+\.known_concepts$',
        r'^companies\.\w+\.exclude_metrics$',
        r'^companies\.\w+\.metric_overrides\.\w+$',
        r'^companies\.\w+\.known_divergences\.\w+$',
        r'^companies\.\w+\.industry$',
        r'^metrics\.\w+\.standardization\.(default|company_overrides\.\w+)\.components$',
    ]

    fake_baseline = MagicMock(spec=CQSResult)
    fake_baseline.cqs = 0.78

    fake_improved = MagicMock(spec=CQSResult)
    fake_improved.cqs = 0.82

    def smart_evaluate(change, baseline, **kwargs):
        path_valid = any(re.match(p, change.yaml_path) for p in VALID_PATH_PATTERNS)
        if path_valid:
            return ExperimentDecision(
                decision=Decision.KEEP,
                cqs_before=baseline.cqs,
                cqs_after=0.82,
                reason="valid path, improvement",
                new_cqs_result=fake_improved,
            )
        else:
            return ExperimentDecision(
                decision=Decision.DISCARD,
                cqs_before=baseline.cqs,
                cqs_after=baseline.cqs,
                reason=f"Invalid path: {change.yaml_path}",
            )

    monkeypatch.setattr(_mod, "compute_cqs", lambda **kwargs: fake_baseline)
    monkeypatch.setattr(_mod, "evaluate_experiment", smart_evaluate)

    # --- Run benchmark with 2 arms ---
    results = run_agent_benchmark(
        manifest_path=manifest_path,
        configs=[
            BenchmarkConfig(
                build_consultation_prompt, "sonnet", "Raw Sonnet",
                use_typed_actions=False,
            ),
            BenchmarkConfig(
                build_typed_action_prompt, "sonnet", "Typed Sonnet",
                use_typed_actions=True,
            ),
        ],
        ai_caller=mock_ai_caller,
        max_gaps=3,
    )

    # --- Assertions ---
    assert len(results) == 2
    raw, typed = results[0], results[1]

    # Same gaps, different outcomes
    assert raw.total_gaps == typed.total_gaps == 3

    # Raw arm: all proposals fail (invented paths rejected by smart_evaluate)
    assert raw.kept == 0

    # Typed arm: compiler generates valid paths -> proposals succeed
    assert typed.kept >= 2
    assert typed.valid_proposals == 3

    # Typed arm outperforms raw arm
    assert typed.cqs_lift > raw.cqs_lift

    # JPM:GrossProfit EXCLUDE_METRIC is a cop-out
    assert typed.cop_outs == 1
