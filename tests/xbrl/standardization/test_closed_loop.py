"""
Tests for Phase 7: Lead Agent Closed Loop.

Tests dispatch_ai_gaps(), evaluate_ai_proposals_live(), run_closed_loop(),
and run_batch_expansion() using mocks — no network, no real AI calls.
"""

import json
import pytest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock

from edgar.xbrl.standardization.tools.auto_eval import CQSResult, MetricGap
from edgar.xbrl.standardization.tools.auto_eval_loop import (
    ChangeType,
    ConfigChange,
    Decision,
    ExperimentDecision,
    GapManifest,
    OvernightReport,
    ProposalRecord,
    UnresolvedGap,
    GAP_MANIFESTS_DIR,
    QUICK_EVAL_COHORT,
)
from edgar.xbrl.standardization.tools.consult_ai_gaps import (
    AIDispatchReport,
    AIEvalReport,
    dispatch_ai_gaps,
    evaluate_ai_proposals_live,
)


# =============================================================================
# TEST HELPERS
# =============================================================================

def _make_unresolved_gap(
    ticker="AAPL",
    metric="Revenue",
    graveyard_count=0,
    disposition="config_fixable",
    difficulty_tier="standard",
    gap_type="high_variance",
) -> UnresolvedGap:
    return UnresolvedGap(
        ticker=ticker,
        metric=metric,
        gap_type=gap_type,
        graveyard_count=graveyard_count,
        disposition=disposition,
        difficulty_tier=difficulty_tier,
        reference_value=100e9,
        xbrl_value=95e9,
        current_variance=5.0,
    )


def _make_manifest(gaps: List[UnresolvedGap], session_id="test") -> GapManifest:
    return GapManifest(
        session_id=session_id,
        created_at="2026-03-26T00:00:00",
        baseline_cqs=0.95,
        eval_cohort=["AAPL"],
        gaps=gaps,
        config_fingerprint="abc123",
    )


def _mock_ai_caller(response_json: dict):
    """Return a callable that returns a fixed JSON response for any prompt."""
    text = json.dumps(response_json)

    def _caller(prompt: str, model: str) -> Optional[str]:
        return text

    return _caller


def _make_cqs_result(cqs=0.95, ef_cqs=0.90, regressions=0, company_scores=None) -> CQSResult:
    """Build a minimal CQSResult mock."""
    result = MagicMock(spec=CQSResult)
    result.cqs = cqs
    result.ef_cqs = ef_cqs
    result.sa_cqs = 0.90
    result.total_regressions = regressions
    result.company_scores = company_scores or {}
    return result


def _make_proposal(ticker="AAPL", metric="Revenue") -> ProposalRecord:
    change = ConfigChange(
        file="metrics.yaml",
        change_type=ChangeType.ADD_CONCEPT,
        yaml_path=f"metrics.{metric}.known_concepts",
        new_value="us-gaap:TestConcept",
        rationale="test",
        target_metric=metric,
        target_companies=ticker,
        source="ai_agent",
    )
    gap = MetricGap(ticker=ticker, metric=metric, gap_type="high_variance", estimated_impact=0.01)
    return ProposalRecord(gap=gap, proposal=change, worker_id="agent_sonnet")


# =============================================================================
# GROUP 1: dispatch_ai_gaps
# =============================================================================

@patch(
    "edgar.xbrl.standardization.tools.consult_ai_gaps._is_company_onboarded",
    return_value=True,
)
@patch(
    "edgar.xbrl.standardization.tools.consult_ai_gaps._build_candidates_context",
    return_value=("", []),
)
class TestDispatchAIGaps:

    @pytest.mark.fast
    def test_filters_dead_end_gaps(self, mock_candidates, mock_onboarded, tmp_path):
        """Gaps with graveyard >= threshold are skipped."""
        gaps = [
            _make_unresolved_gap(ticker="AAPL", graveyard_count=7),
            _make_unresolved_gap(ticker="JPM", graveyard_count=2),
        ]
        manifest = _make_manifest(gaps)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest.to_dict()))

        caller = _mock_ai_caller({
            "action": "MAP_CONCEPT",
            "ticker": "JPM",
            "metric": "Revenue",
            "params": {"concept": "us-gaap:Revenue"},
            "rationale": "test",
            "confidence": 0.9,
        })

        with patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.get_config_fingerprint",
            return_value="abc123",
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.load_agent_responses",
            return_value={},
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.save_agent_responses",
        ):
            proposals, report = dispatch_ai_gaps(
                manifest_path=manifest_path,
                ai_caller=caller,
                dead_end_threshold=6,
            )

        assert report.dead_end_skipped == 1
        # Only JPM should have been dispatched
        assert report.api_calls == 1

    @pytest.mark.fast
    def test_filters_scoring_inert_gaps(self, mock_candidates, mock_onboarded, tmp_path):
        """Gaps with scoring_inert disposition are filtered by filter_actionable_gaps."""
        gaps = [
            _make_unresolved_gap(ticker="AAPL", disposition="scoring_inert"),
            _make_unresolved_gap(ticker="JPM", disposition="config_fixable"),
        ]
        manifest = _make_manifest(gaps)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest.to_dict()))

        caller = _mock_ai_caller({
            "action": "MAP_CONCEPT",
            "ticker": "JPM",
            "metric": "Revenue",
            "params": {"concept": "us-gaap:Revenue"},
            "rationale": "test",
            "confidence": 0.9,
        })

        with patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.get_config_fingerprint",
            return_value="abc123",
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.load_agent_responses",
            return_value={},
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.save_agent_responses",
        ):
            proposals, report = dispatch_ai_gaps(
                manifest_path=manifest_path,
                ai_caller=caller,
            )

        assert report.actionable_gaps == 1  # Only JPM is actionable

    @pytest.mark.fast
    def test_cache_hits_skip_api_call(self, mock_candidates, mock_onboarded, tmp_path):
        """Cached responses are reused, no API call made."""
        gaps = [_make_unresolved_gap(ticker="AAPL")]
        manifest = _make_manifest(gaps)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest.to_dict()))

        cached_response = json.dumps({
            "action": "MAP_CONCEPT",
            "ticker": "AAPL",
            "metric": "Revenue",
            "params": {"concept": "us-gaap:Revenue"},
            "rationale": "cached",
            "confidence": 0.9,
        })

        call_count = {"n": 0}

        def counting_caller(prompt, model):
            call_count["n"] += 1
            return None

        with patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.get_config_fingerprint",
            return_value="abc123",
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.load_agent_responses",
            return_value={"AAPL:Revenue": cached_response},
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.save_agent_responses",
        ):
            proposals, report = dispatch_ai_gaps(
                manifest_path=manifest_path,
                ai_caller=counting_caller,
            )

        assert report.cache_hits == 1
        assert report.api_calls == 0
        assert call_count["n"] == 0

    @pytest.mark.fast
    def test_typed_action_pipeline_produces_proposals(self, mock_candidates, mock_onboarded, tmp_path):
        """Valid MAP_CONCEPT JSON -> ProposalRecord."""
        gaps = [_make_unresolved_gap(ticker="XOM", metric="GrossProfit")]
        manifest = _make_manifest(gaps)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest.to_dict()))

        caller = _mock_ai_caller({
            "action": "MAP_CONCEPT",
            "ticker": "XOM",
            "metric": "GrossProfit",
            "params": {"concept": "us-gaap:GrossProfit"},
            "rationale": "XOM reports GrossProfit directly",
            "confidence": 0.9,
        })

        with patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.get_config_fingerprint",
            return_value="abc123",
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.load_agent_responses",
            return_value={},
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.save_agent_responses",
        ):
            proposals, report = dispatch_ai_gaps(
                manifest_path=manifest_path,
                ai_caller=caller,
            )

        assert report.valid_proposals == 1
        assert len(proposals) == 1
        assert proposals[0].proposal.change_type == ChangeType.ADD_CONCEPT
        assert proposals[0].proposal.new_value == "us-gaap:GrossProfit"

    @pytest.mark.fast
    def test_invalid_responses_produce_zero_proposals(self, mock_candidates, mock_onboarded, tmp_path):
        """Garbage text from AI -> 0 proposals."""
        gaps = [_make_unresolved_gap()]
        manifest = _make_manifest(gaps)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest.to_dict()))

        def garbage_caller(prompt, model):
            return "This is not JSON at all, just random text."

        with patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.get_config_fingerprint",
            return_value="abc123",
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.load_agent_responses",
            return_value={},
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.save_agent_responses",
        ):
            proposals, report = dispatch_ai_gaps(
                manifest_path=manifest_path,
                ai_caller=garbage_caller,
            )

        assert report.valid_proposals == 0
        assert len(proposals) == 0

    @pytest.mark.fast
    def test_model_routing_standard_vs_hard(self, mock_candidates, mock_onboarded, tmp_path):
        """Standard gaps -> gemini-flash, hard gaps -> sonnet."""
        gaps = [
            _make_unresolved_gap(ticker="AAPL", difficulty_tier="standard"),
            _make_unresolved_gap(ticker="JPM", difficulty_tier="hard"),
        ]
        manifest = _make_manifest(gaps)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest.to_dict()))

        models_used = []

        def tracking_caller(prompt, model):
            models_used.append(model)
            return json.dumps({
                "action": "MAP_CONCEPT",
                "params": {"concept": "us-gaap:Test"},
                "rationale": "test",
                "confidence": 0.9,
            })

        with patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.get_config_fingerprint",
            return_value="abc123",
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.load_agent_responses",
            return_value={},
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.save_agent_responses",
        ):
            proposals, report = dispatch_ai_gaps(
                manifest_path=manifest_path,
                ai_caller=tracking_caller,
            )

        assert report.model_counts.get("gemini-flash", 0) >= 1
        assert report.model_counts.get("sonnet", 0) >= 1


# =============================================================================
# GROUP 1b: O9 Auto-Resolve Tests
# =============================================================================

class TestAutoResolve:
    """Tests for O9: auto-resolve from value search."""

    @pytest.mark.fast
    def test_auto_resolve_skips_ai(self, tmp_path):
        """When _build_candidates_context returns a close us-gaap match, AI is skipped."""
        from edgar.xbrl.standardization.tools.discover_concepts import CandidateConcept

        close_candidate = CandidateConcept(
            concept="us-gaap:Revenues",
            source="value_match",
            confidence=0.95,
            reasoning="Value match",
            extracted_value=99.5e9,
            delta_pct=0.5,
        )

        gaps = [_make_unresolved_gap(ticker="AAPL", metric="Revenue")]
        manifest = _make_manifest(gaps)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest.to_dict()))

        call_count = {"n": 0}

        def counting_caller(prompt, model):
            call_count["n"] += 1
            return None

        with patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps._is_company_onboarded",
            return_value=True,
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps._build_candidates_context",
            return_value=("table text", [close_candidate]),
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.get_config_fingerprint",
            return_value="abc123",
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.load_agent_responses",
            return_value={},
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.save_agent_responses",
        ):
            proposals, report = dispatch_ai_gaps(
                manifest_path=manifest_path,
                ai_caller=counting_caller,
            )

        assert report.auto_resolved == 1
        assert report.api_calls == 0
        assert call_count["n"] == 0
        assert len(proposals) == 1
        assert proposals[0].proposal.new_value == "us-gaap:Revenues"

    @pytest.mark.fast
    def test_auto_resolve_rejects_extension_concepts(self, tmp_path):
        """Candidate with <2% variance but non-us-gaap prefix should NOT auto-resolve."""
        from edgar.xbrl.standardization.tools.discover_concepts import CandidateConcept

        extension_candidate = CandidateConcept(
            concept="aapl:CustomRevenue",
            source="value_match",
            confidence=0.95,
            reasoning="Value match",
            extracted_value=100.1e9,
            delta_pct=0.1,
        )

        gaps = [_make_unresolved_gap(ticker="AAPL", metric="Revenue")]
        manifest = _make_manifest(gaps)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest.to_dict()))

        caller = _mock_ai_caller({
            "action": "MAP_CONCEPT",
            "ticker": "AAPL",
            "metric": "Revenue",
            "params": {"concept": "us-gaap:Revenue"},
            "rationale": "test",
            "confidence": 0.9,
        })

        with patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps._is_company_onboarded",
            return_value=True,
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps._build_candidates_context",
            return_value=("table text", [extension_candidate]),
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.get_config_fingerprint",
            return_value="abc123",
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.load_agent_responses",
            return_value={},
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.save_agent_responses",
        ):
            proposals, report = dispatch_ai_gaps(
                manifest_path=manifest_path,
                ai_caller=caller,
            )

        # Extension concept should not auto-resolve — falls through to AI call
        assert report.auto_resolved == 0
        assert report.api_calls == 1


# =============================================================================
# GROUP 2: evaluate_ai_proposals_live
# =============================================================================

class TestEvaluateAIProposalsLive:
    """Tests for evaluate_ai_proposals_live with O1-O6 optimizations.

    All tests patch:
    - evaluate_experiment_in_memory (O4 pre-screen) to return KEEP → falls through to full eval
    - get_config (O4 baseline config) to return a mock
    - evaluate_experiment (full disk eval)
    - log_experiment
    """

    def _eval_patches(self, pre_screen_decision=None, full_decision=None):
        """Context manager stacking all required patches."""
        from contextlib import ExitStack

        if pre_screen_decision is None:
            pre_screen_decision = ExperimentDecision(
                decision=Decision.KEEP, cqs_before=0.95, cqs_after=0.96, reason="OK",
            )

        stack = ExitStack()
        # O4 imports are local (inside function body), patch at source module
        stack.enter_context(patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop.evaluate_experiment_in_memory",
            return_value=pre_screen_decision,
        ))
        stack.enter_context(patch(
            "edgar.xbrl.standardization.config_loader.get_config",
            return_value=MagicMock(),
        ))
        if full_decision is not None:
            stack.enter_context(patch(
                "edgar.xbrl.standardization.tools.consult_ai_gaps.evaluate_experiment",
                return_value=full_decision,
            ))
        stack.enter_context(patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.log_experiment",
        ))
        stack.enter_context(patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop.apply_change_to_config",
            return_value=MagicMock(),
        ))
        return stack

    @pytest.mark.fast
    def test_keep_updates_baseline(self):
        """KEPT proposal advances baseline CQS."""
        proposals = [_make_proposal()]
        baseline = _make_cqs_result(cqs=0.95, ef_cqs=0.90)

        new_cqs = _make_cqs_result(cqs=0.96, ef_cqs=0.91)
        keep_decision = ExperimentDecision(
            decision=Decision.KEEP,
            cqs_before=0.95,
            cqs_after=0.96,
            reason="Improved",
            new_cqs_result=new_cqs,
        )

        with self._eval_patches(full_decision=keep_decision):
            report = evaluate_ai_proposals_live(
                proposals=proposals,
                baseline_cqs=baseline,
                eval_cohort=["AAPL"],
            )

        assert report.kept == 1
        assert report.cqs_end == 0.96
        assert report.ef_cqs_end == 0.91

    @pytest.mark.fast
    def test_discard_via_prescreen(self):
        """DISCARDED at pre-screen leaves baseline unchanged."""
        proposals = [_make_proposal()]
        baseline = _make_cqs_result(cqs=0.95, ef_cqs=0.90)

        discard_decision = ExperimentDecision(
            decision=Decision.DISCARD,
            cqs_before=0.95,
            cqs_after=0.94,
            reason="No improvement",
        )

        with self._eval_patches(pre_screen_decision=discard_decision):
            report = evaluate_ai_proposals_live(
                proposals=proposals,
                baseline_cqs=baseline,
                eval_cohort=["AAPL"],
            )

        assert report.discarded == 1
        assert report.pre_screen_filtered == 1
        assert report.cqs_end == 0.95  # Unchanged

    @pytest.mark.fast
    def test_discard_at_full_eval(self):
        """DISCARDED at full eval (after pre-screen KEEP) leaves baseline unchanged."""
        proposals = [_make_proposal()]
        baseline = _make_cqs_result(cqs=0.95, ef_cqs=0.90)

        discard_decision = ExperimentDecision(
            decision=Decision.DISCARD,
            cqs_before=0.95,
            cqs_after=0.94,
            reason="No improvement",
        )

        with self._eval_patches(full_decision=discard_decision):
            report = evaluate_ai_proposals_live(
                proposals=proposals,
                baseline_cqs=baseline,
                eval_cohort=["AAPL"],
            )

        assert report.discarded == 1
        assert report.pre_screen_filtered == 0  # Passed pre-screen
        assert report.cqs_end == 0.95  # Unchanged

    @pytest.mark.fast
    def test_per_company_circuit_breaker(self):
        """Per-company breaker: 15 proposals same ticker, 10 discarded then company exhausted."""
        proposals = [_make_proposal(ticker="AAPL", metric=f"M{i}") for i in range(15)]
        baseline = _make_cqs_result(cqs=0.95, ef_cqs=0.90)

        discard_decision = ExperimentDecision(
            decision=Decision.DISCARD,
            cqs_before=0.95,
            cqs_after=0.94,
            reason="No improvement",
        )

        with self._eval_patches(pre_screen_decision=discard_decision):
            report = evaluate_ai_proposals_live(
                proposals=proposals,
                baseline_cqs=baseline,
                eval_cohort=["AAPL"],
                max_consecutive_failures=10,
            )

        assert report.stopped_early is True
        assert "exhausted" in report.stop_reason.lower()
        assert report.discarded == 10
        assert "AAPL" in report.companies_exhausted

    @pytest.mark.fast
    def test_returns_final_baseline_for_chaining(self):
        """final_baseline is set correctly after evaluation."""
        proposals = [_make_proposal()]
        baseline = _make_cqs_result(cqs=0.95, ef_cqs=0.90)

        new_cqs = _make_cqs_result(cqs=0.96, ef_cqs=0.91)
        keep_decision = ExperimentDecision(
            decision=Decision.KEEP,
            cqs_before=0.95,
            cqs_after=0.96,
            reason="Improved",
            new_cqs_result=new_cqs,
        )

        with self._eval_patches(full_decision=keep_decision):
            report = evaluate_ai_proposals_live(
                proposals=proposals,
                baseline_cqs=baseline,
                eval_cohort=["AAPL"],
            )

        assert report.final_baseline is not None
        assert report.final_baseline.cqs == 0.96

    @pytest.mark.fast
    def test_new_report_fields_present(self):
        """New O1-O6 report fields are populated."""
        proposals = [_make_proposal()]
        baseline = _make_cqs_result(cqs=0.95, ef_cqs=0.90)

        keep_decision = ExperimentDecision(
            decision=Decision.KEEP,
            cqs_before=0.95,
            cqs_after=0.96,
            reason="OK",
            new_cqs_result=_make_cqs_result(cqs=0.96, ef_cqs=0.91),
        )

        with self._eval_patches(full_decision=keep_decision):
            report = evaluate_ai_proposals_live(
                proposals=proposals,
                baseline_cqs=baseline,
                eval_cohort=["AAPL"],
            )

        assert isinstance(report.companies_exhausted, list)
        assert report.pre_screen_filtered >= 0
        assert report.retries >= 0
        assert report.retry_kept >= 0


# =============================================================================
# GROUP 3: run_closed_loop
# =============================================================================

class TestRunClosedLoop:

    @pytest.mark.fast
    def test_full_pipeline_calls_both_phases(self):
        """Patches run_overnight + dispatch + evaluate, asserts both phases called."""
        from edgar.xbrl.standardization.tools.auto_eval_loop import run_closed_loop

        det_report = OvernightReport(
            session_id="test_det",
            started_at="",
            finished_at="",
            duration_hours=0.1,
            focus_area=None,
            experiments_kept=2,
            experiments_discarded=1,
            cqs_start=0.94,
            cqs_end=0.95,
            ef_cqs_start=0.88,
            ef_cqs_end=0.90,
            gap_manifest_path="/tmp/manifest.json",
            unresolved_count=5,
        )

        proposals = [_make_proposal()]
        dispatch_report = AIDispatchReport(
            session_id="test",
            total_gaps=5,
            actionable_gaps=4,
            dead_end_skipped=1,
            cache_hits=0,
            api_calls=4,
            valid_proposals=1,
            preflight_rejected=0,
            escalated=0,
        )

        ai_baseline = _make_cqs_result(cqs=0.95, ef_cqs=0.90)
        ai_eval_report = AIEvalReport(
            session_id="test",
            proposals_total=1,
            kept=1,
            discarded=0,
            vetoed=0,
            cqs_start=0.95,
            cqs_end=0.96,
            ef_cqs_start=0.90,
            ef_cqs_end=0.92,
            final_baseline=_make_cqs_result(cqs=0.96, ef_cqs=0.92),
        )

        with patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop.run_overnight",
            return_value=det_report,
        ) as mock_overnight, patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.dispatch_ai_gaps",
            return_value=(proposals, dispatch_report),
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.evaluate_ai_proposals_live",
            return_value=ai_eval_report,
        ), patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop.compute_cqs",
            return_value=ai_baseline,
        ):
            report = run_closed_loop(
                eval_cohort=["AAPL"],
                duration_hours=0.5,
                ai_caller=lambda p, m: None,
            )

        assert report.det_kept == 2
        assert report.ai_kept == 1
        assert report.total_kept == 3
        assert report.ef_cqs_start == 0.88
        assert report.ef_cqs_end == 0.92
        mock_overnight.assert_called_once()

    @pytest.mark.fast
    def test_skips_ai_when_no_unresolved_gaps(self):
        """Empty manifest path -> AI phase skipped."""
        from edgar.xbrl.standardization.tools.auto_eval_loop import run_closed_loop

        det_report = OvernightReport(
            session_id="test_det",
            started_at="",
            finished_at="",
            duration_hours=0.1,
            focus_area=None,
            experiments_kept=5,
            cqs_start=0.94,
            cqs_end=0.97,
            ef_cqs_start=0.88,
            ef_cqs_end=0.95,
            gap_manifest_path="",  # No unresolved gaps
            unresolved_count=0,
        )

        with patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop.run_overnight",
            return_value=det_report,
        ):
            report = run_closed_loop(
                eval_cohort=["AAPL"],
                duration_hours=0.5,
                ai_caller=lambda p, m: None,
            )

        assert report.ai_kept == 0
        assert report.total_kept == 5  # Only deterministic
        assert report.ef_cqs_end == 0.95

    @pytest.mark.fast
    def test_creates_ai_caller_when_none_provided(self):
        """When ai_caller is None, make_openrouter_caller is called."""
        from edgar.xbrl.standardization.tools.auto_eval_loop import run_closed_loop

        det_report = OvernightReport(
            session_id="test_det",
            started_at="",
            finished_at="",
            duration_hours=0.1,
            focus_area=None,
            gap_manifest_path="/tmp/manifest.json",
            unresolved_count=3,
            ef_cqs_start=0.88,
            ef_cqs_end=0.90,
            cqs_start=0.94,
            cqs_end=0.95,
        )

        mock_caller = MagicMock(return_value=None)
        mock_cost = {}
        ai_baseline = _make_cqs_result(cqs=0.95, ef_cqs=0.90)

        dispatch_report = AIDispatchReport(
            session_id="test", total_gaps=3, actionable_gaps=3,
            dead_end_skipped=0, cache_hits=0, api_calls=0,
            valid_proposals=0, preflight_rejected=0, escalated=0,
        )

        with patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop.run_overnight",
            return_value=det_report,
        ), patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.make_openrouter_caller",
            return_value=(mock_caller, mock_cost),
        ) as mock_make, patch(
            "edgar.xbrl.standardization.tools.consult_ai_gaps.dispatch_ai_gaps",
            return_value=([], dispatch_report),
        ), patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop.compute_cqs",
            return_value=ai_baseline,
        ):
            report = run_closed_loop(
                eval_cohort=["AAPL"],
                duration_hours=0.5,
                ai_caller=None,
            )

        mock_make.assert_called_once()


# =============================================================================
# GROUP 4: run_batch_expansion
# =============================================================================

class TestRunBatchExpansion:

    @pytest.mark.fast
    def test_splits_into_correct_batch_count(self):
        """100 tickers / 50 batch_size = 2 batches."""
        from edgar.xbrl.standardization.tools.auto_eval_loop import (
            run_batch_expansion,
            ClosedLoopReport,
        )

        tickers = [f"T{i:03d}" for i in range(100)]

        def mock_closed_loop(**kwargs):
            return ClosedLoopReport(
                session_id="test",
                started_at="",
                finished_at="",
                duration_hours=0.1,
                eval_cohort=kwargs.get("eval_cohort", []),
                ef_cqs_end=0.85,
            )

        with patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop.run_closed_loop",
            side_effect=mock_closed_loop,
        ):
            report = run_batch_expansion(
                total_cohort=tickers,
                batch_size=50,
                graduation_ef_cqs=0.80,
                ai_caller=lambda p, m: None,
                skip_precondition=True,
            )

        assert report.total_batches == 2

    @pytest.mark.fast
    def test_graduation_gate_applied(self):
        """Batch with ef_cqs=0.82 graduated, 0.75 not."""
        from edgar.xbrl.standardization.tools.auto_eval_loop import (
            run_batch_expansion,
            ClosedLoopReport,
        )

        tickers = [f"T{i:03d}" for i in range(60)]
        call_count = {"n": 0}

        def mock_closed_loop(**kwargs):
            call_count["n"] += 1
            ef = 0.82 if call_count["n"] == 1 else 0.75
            return ClosedLoopReport(
                session_id="test",
                started_at="",
                finished_at="",
                duration_hours=0.1,
                eval_cohort=kwargs.get("eval_cohort", []),
                ef_cqs_end=ef,
            )

        with patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop.run_closed_loop",
            side_effect=mock_closed_loop,
        ):
            report = run_batch_expansion(
                total_cohort=tickers,
                batch_size=30,
                graduation_ef_cqs=0.80,
                ai_caller=lambda p, m: None,
                skip_precondition=True,
            )

        assert report.graduated == 1
        assert report.failed == 1
        assert report.results[0].graduated is True
        assert report.results[1].graduated is False

    @pytest.mark.fast
    def test_precondition_blocks_large_expansion(self):
        """ef_cqs < 0.95 raises ValueError for >100 tickers."""
        from edgar.xbrl.standardization.tools.auto_eval_loop import run_batch_expansion

        tickers = [f"T{i:03d}" for i in range(150)]
        low_cqs = _make_cqs_result(cqs=0.90, ef_cqs=0.80)

        with patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop.compute_cqs",
            return_value=low_cqs,
        ), pytest.raises(ValueError, match="Base cohort EF-CQS"):
            run_batch_expansion(
                total_cohort=tickers,
                batch_size=50,
                ai_caller=lambda p, m: None,
                skip_precondition=False,
            )
