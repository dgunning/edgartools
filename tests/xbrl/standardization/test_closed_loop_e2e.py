"""
E2E smoke test for the closed-loop AI dispatch pipeline.

Tests the real OpenRouter API call with Gemini Flash on a single gap.
Requires OPENROUTER_API_KEY environment variable.

Run: hatch run test-network -- tests/xbrl/standardization/test_closed_loop_e2e.py -xvs
"""

import json
import os
import pytest
from pathlib import Path

from edgar.xbrl.standardization.tools.auto_eval_loop import (
    GapManifest,
    UnresolvedGap,
    GAP_MANIFESTS_DIR,
)
from edgar.xbrl.standardization.tools.consult_ai_gaps import (
    AIDispatchReport,
    AIEvalReport,
    dispatch_ai_gaps,
    make_openrouter_caller,
    build_typed_action_prompt,
    parse_typed_action,
    MODEL_REGISTRY,
)


needs_api_key = pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set",
)


def _make_realistic_gap() -> UnresolvedGap:
    """A realistic gap that Gemini Flash should be able to resolve."""
    return UnresolvedGap(
        ticker="XOM",
        metric="GrossProfit",
        gap_type="high_variance",
        hv_subtype="hv_unmapped",
        reference_value=89_686_000_000,
        xbrl_value=None,
        current_variance=100.0,
        estimated_impact=0.02,
        graveyard_count=0,
        root_cause="unmapped_concept",
        notes="GrossProfit not found in known_concepts",
        disposition="config_fixable",
        difficulty_tier="standard",
        ai_agent_type="semantic_mapper",
    )


@pytest.mark.network
class TestAPICallSmoke:
    """Verify the real OpenRouter API works end-to-end."""

    @needs_api_key
    def test_make_openrouter_caller_returns_callable(self):
        """Factory creates a working caller + cost tracker."""
        caller, cost_tracker = make_openrouter_caller()
        assert callable(caller)
        assert "total_cost" in cost_tracker

    @needs_api_key
    def test_model_registry_has_valid_entries(self):
        """MODEL_REGISTRY maps abstract names to OpenRouter model IDs."""
        assert "gemini-flash" in MODEL_REGISTRY
        assert "sonnet" in MODEL_REGISTRY
        # All values should look like OpenRouter model IDs (org/model format)
        for key, model_id in MODEL_REGISTRY.items():
            assert "/" in model_id, f"{key} -> {model_id} doesn't look like an OpenRouter model ID"

    @needs_api_key
    def test_gemini_flash_returns_typed_action(self):
        """Send a real prompt to Gemini Flash and verify it returns valid TypedAction JSON."""
        caller, cost_tracker = make_openrouter_caller()
        gap = _make_realistic_gap()
        prompt = build_typed_action_prompt(gap)

        response = caller(prompt, "gemini-flash")

        assert response is not None, "API returned None"
        assert len(response) > 10, f"Response too short: {response!r}"

        # Should parse into a valid TypedAction
        action = parse_typed_action(response, gap.ticker, gap.metric)
        assert action is not None, f"Failed to parse TypedAction from response:\n{response}"
        assert action.action in (
            "MAP_CONCEPT", "ADD_FORMULA", "EXCLUDE_METRIC",
            "DOCUMENT_DIVERGENCE", "FIX_SIGN_CONVENTION", "SET_INDUSTRY", "ESCALATE",
        ), f"Unknown action: {action.action}"
        assert action.ticker == "XOM"
        assert action.metric == "GrossProfit"
        assert action.confidence > 0, "Confidence should be > 0"

        print(f"\n  Model: gemini-flash -> {MODEL_REGISTRY['gemini-flash']}")
        print(f"  Action: {action.action}")
        print(f"  Params: {action.params}")
        print(f"  Confidence: {action.confidence}")
        print(f"  Rationale: {action.rationale[:100]}")
        print(f"  API cost: ${cost_tracker['total_cost']:.4f}")


@pytest.mark.network
class TestDispatchE2E:
    """Verify dispatch_ai_gaps works end-to-end with real API."""

    @needs_api_key
    def test_dispatch_single_gap_e2e(self, tmp_path):
        """Full dispatch pipeline: manifest -> API call -> ProposalRecord."""
        gap = _make_realistic_gap()
        manifest = GapManifest(
            session_id="e2e_smoke_test",
            created_at="2026-03-26T00:00:00",
            baseline_cqs=0.90,
            eval_cohort=["XOM"],
            gaps=[gap],
            config_fingerprint="e2e_test",
        )

        manifest_path = tmp_path / "manifest_e2e.json"
        manifest_path.write_text(json.dumps(manifest.to_dict()))

        caller, cost_tracker = make_openrouter_caller()

        proposals, report = dispatch_ai_gaps(
            manifest_path=manifest_path,
            ai_caller=caller,
            session_id="e2e_smoke",
        )

        print(f"\n  Dispatch Report:")
        print(f"    Total gaps: {report.total_gaps}")
        print(f"    Actionable: {report.actionable_gaps}")
        print(f"    Dead-end skipped: {report.dead_end_skipped}")
        print(f"    API calls: {report.api_calls}")
        print(f"    Cache hits: {report.cache_hits}")
        print(f"    Valid proposals: {report.valid_proposals}")
        print(f"    Preflight rejected: {report.preflight_rejected}")
        print(f"    Escalated: {report.escalated}")
        print(f"    Model counts: {report.model_counts}")
        print(f"    API cost: ${cost_tracker['total_cost']:.4f}")

        assert report.total_gaps == 1
        assert report.actionable_gaps == 1
        assert report.api_calls == 1
        assert report.dead_end_skipped == 0

        # The model should have produced a valid proposal (or escalated)
        assert report.valid_proposals + report.escalated + report.preflight_rejected >= 1, (
            "Expected at least one outcome (proposal, escalation, or rejection)"
        )

        if proposals:
            p = proposals[0]
            print(f"\n  Proposal:")
            print(f"    Change type: {p.proposal.change_type.value}")
            print(f"    YAML path: {p.proposal.yaml_path}")
            print(f"    New value: {p.proposal.new_value}")
            print(f"    Rationale: {p.proposal.rationale[:100]}")
