"""
Closed-Loop E2E Validation: Can AI resolve gaps that deterministic solvers cannot?

Runs the full MEASURE → RESOLVE → VALIDATE pipeline on real data (5 companies),
with real API calls to Gemini Flash, real CQS gate evaluation (apply config,
measure CQS, revert on DISCARD), and structured result reporting.

Budget: ~10-15 min total, ~$0.04 API cost.

Run:
    hatch run test-network -- tests/xbrl/standardization/test_closed_loop_validation.py -xvs
"""

import json
import os
import time
import pytest
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from edgar.xbrl.standardization.tools.auto_eval import (
    identify_gaps,
    compute_cqs,
    QUICK_EVAL_COHORT,
    MetricGap,
    CQSResult,
)
from edgar.xbrl.standardization.tools.auto_eval_loop import (
    GapManifest,
    UnresolvedGap,
    AIAgentRouter,
    AIAgentType,
    _build_unresolved_gap,
    get_config_fingerprint,
    revert_all_configs,
    TIER1_CONFIGS,
)
from edgar.xbrl.standardization.tools.consult_ai_gaps import (
    dispatch_ai_gaps,
    evaluate_ai_proposals_live,
    make_openrouter_caller,
    AIDispatchReport,
    AIEvalReport,
    ProposalRecord,
)
from edgar.xbrl.standardization.tools.capability_registry import (
    classify_gap_disposition,
    GapDisposition,
)
from edgar.xbrl.standardization.ledger.schema import ExperimentLedger


needs_api_key = pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set",
)

VALID_GAP_TYPES = {
    "unmapped", "validation_failure", "high_variance",
    "regression", "explained_variance", "reference_disputed",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_manifest_from_gaps(
    gaps: List[MetricGap],
    cqs_result: CQSResult,
    eval_cohort: List[str],
    session_id: str,
    tmp_path: Path,
) -> Tuple[GapManifest, Path]:
    """Build a GapManifest from identify_gaps() output and write to tmp_path."""
    ledger = ExperimentLedger()
    all_graveyard = ledger.get_graveyard_entries()
    graveyard_by_metric = {}
    for entry in all_graveyard:
        metric = entry.get("target_metric", "")
        graveyard_by_metric.setdefault(metric, []).append(entry)

    router = AIAgentRouter()
    unresolved_gaps: List[UnresolvedGap] = []
    for gap in gaps:
        graveyard_entries = graveyard_by_metric.get(gap.metric, [])
        agent_type = router.route(gap) or AIAgentType.SEMANTIC_MAPPER
        ugap = _build_unresolved_gap(gap, graveyard_entries, agent_type)
        ugap.disposition = classify_gap_disposition(
            root_cause=gap.root_cause,
            reference_value=gap.reference_value,
            hv_subtype=gap.hv_subtype,
        ).value
        unresolved_gaps.append(ugap)

    unresolved_gaps.sort(key=lambda g: g.estimated_impact, reverse=True)

    manifest = GapManifest(
        session_id=session_id,
        created_at=datetime.now().isoformat(),
        baseline_cqs=cqs_result.cqs,
        eval_cohort=eval_cohort,
        gaps=unresolved_gaps,
        config_fingerprint=get_config_fingerprint(),
    )

    manifest_path = tmp_path / f"manifest_{session_id}.json"
    manifest_path.write_text(json.dumps(manifest.to_dict()))
    return manifest, manifest_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def config_safety_net():
    """Revert all Tier 1 configs after every test, verifying idempotency."""
    fingerprint_before = get_config_fingerprint()
    yield
    revert_all_configs()
    fingerprint_after = get_config_fingerprint()
    assert fingerprint_after == fingerprint_before, (
        f"Config not restored! Before={fingerprint_before}, After={fingerprint_after}"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.network
class TestClosedLoopValidation:
    """Full closed-loop validation: MEASURE → RESOLVE → VALIDATE on real data."""

    def test_phase1_measure_identifies_real_gaps(self):
        """MEASURE: identify_gaps finds real gaps in QUICK_EVAL_COHORT."""
        t0 = time.time()
        gaps, cqs_result = identify_gaps(
            eval_cohort=QUICK_EVAL_COHORT,
            snapshot_mode=True,
            use_sec_facts=True,
        )
        elapsed = time.time() - t0

        # CQS in valid range
        assert 0 < cqs_result.cqs <= 1.0, f"CQS out of range: {cqs_result.cqs}"

        # At least one gap exists
        assert len(gaps) > 0, "No gaps found — nothing for AI to resolve"

        # Each gap is well-formed
        for gap in gaps:
            assert gap.ticker in QUICK_EVAL_COHORT, (
                f"Gap ticker {gap.ticker} not in eval cohort"
            )
            assert gap.metric, f"Empty metric for {gap.ticker}"
            assert gap.gap_type in VALID_GAP_TYPES, (
                f"Invalid gap_type {gap.gap_type!r} for {gap.ticker}:{gap.metric}"
            )

        # Per-company breakdown
        by_company = {}
        for gap in gaps:
            by_company.setdefault(gap.ticker, []).append(gap)

        print(f"\n{'='*60}")
        print(f"  PHASE 1: MEASURE ({elapsed:.1f}s)")
        print(f"{'='*60}")
        print(f"  CQS:     {cqs_result.cqs:.4f}")
        print(f"  EF-CQS:  {cqs_result.ef_cqs:.4f}")
        print(f"  SA-CQS:  {cqs_result.sa_cqs:.4f}")
        print(f"  Gaps:    {len(gaps)} total")
        for ticker in QUICK_EVAL_COHORT:
            count = len(by_company.get(ticker, []))
            print(f"    {ticker}: {count} gaps")

    @needs_api_key
    def test_phase2_resolve_ai_produces_valid_proposals(self, tmp_path):
        """MEASURE + RESOLVE: dispatch real gaps to Gemini Flash, verify proposals."""
        # Phase 1: Measure
        t0 = time.time()
        gaps, cqs_result = identify_gaps(
            eval_cohort=QUICK_EVAL_COHORT,
            snapshot_mode=True,
            use_sec_facts=True,
        )
        t_measure = time.time() - t0
        assert len(gaps) > 0, "No gaps to dispatch"

        # Phase 2: Resolve
        manifest, manifest_path = _build_manifest_from_gaps(
            gaps, cqs_result, QUICK_EVAL_COHORT,
            session_id="validation_resolve", tmp_path=tmp_path,
        )

        caller, cost_tracker = make_openrouter_caller()
        t1 = time.time()
        proposals, report = dispatch_ai_gaps(
            manifest_path=manifest_path,
            ai_caller=caller,
            session_id="validation_resolve",
        )
        t_resolve = time.time() - t1

        # AIDispatchReport is well-formed
        assert isinstance(report, AIDispatchReport)
        assert report.total_gaps > 0
        assert report.actionable_gaps <= report.total_gaps
        assert report.api_calls >= 0
        assert report.dead_end_skipped >= 0
        assert report.not_onboarded_skipped >= 0  # O2

        # At least one outcome occurred (accounting for O2 skips)
        assert (report.valid_proposals + report.escalated + report.preflight_rejected + report.not_onboarded_skipped) >= 1, (
            "Expected at least one outcome (proposal, escalation, rejection, or not-onboarded skip)"
        )

        # All proposals are well-formed
        for p in proposals:
            assert p.proposal.change_type is not None, "Missing change_type"
            assert p.proposal.target_metric, f"Empty target_metric in proposal"
            assert p.proposal.target_companies, f"Empty target_companies in proposal"
            assert p.proposal.source == "ai_agent", (
                f"Expected source='ai_agent', got {p.proposal.source!r}"
            )

        total_cost = cost_tracker.get("total_cost", 0)
        resolution_rate = (
            report.valid_proposals / report.actionable_gaps * 100
            if report.actionable_gaps > 0 else 0
        )

        print(f"\n{'='*60}")
        print(f"  PHASE 2: RESOLVE ({t_resolve:.1f}s, measure={t_measure:.1f}s)")
        print(f"{'='*60}")
        print(f"  Total gaps:       {report.total_gaps}")
        print(f"  Actionable:       {report.actionable_gaps}")
        print(f"  Dead-end skipped: {report.dead_end_skipped}")
        print(f"  Not-onboarded:    {report.not_onboarded_skipped}")
        print(f"  Cache hits:       {report.cache_hits}")
        print(f"  API calls:        {report.api_calls}")
        print(f"  Valid proposals:  {report.valid_proposals}")
        print(f"  Preflight reject: {report.preflight_rejected}")
        print(f"  Escalated:        {report.escalated}")
        print(f"  Resolution rate:  {resolution_rate:.1f}%")
        print(f"  Model counts:     {report.model_counts}")
        print(f"  API cost:         ${total_cost:.4f}")

    @needs_api_key
    def test_full_pipeline_measure_resolve_validate(self, tmp_path):
        """MEASURE + RESOLVE + VALIDATE: full closed-loop with CQS gate."""
        session_id = f"validation_full_{datetime.now().strftime('%H%M%S')}"

        # ---- Phase 1: MEASURE ----
        t0 = time.time()
        gaps, cqs_result = identify_gaps(
            eval_cohort=QUICK_EVAL_COHORT,
            snapshot_mode=True,
            use_sec_facts=True,
        )
        t_measure = time.time() - t0
        cqs_start = cqs_result.cqs
        ef_cqs_start = cqs_result.ef_cqs
        assert len(gaps) > 0, "No gaps to resolve"

        # ---- Phase 2: RESOLVE ----
        manifest, manifest_path = _build_manifest_from_gaps(
            gaps, cqs_result, QUICK_EVAL_COHORT,
            session_id=session_id, tmp_path=tmp_path,
        )

        caller, cost_tracker = make_openrouter_caller()
        t1 = time.time()
        proposals, dispatch_report = dispatch_ai_gaps(
            manifest_path=manifest_path,
            ai_caller=caller,
            session_id=session_id,
        )
        t_resolve = time.time() - t1

        # ---- Phase 3: VALIDATE ----
        t2 = time.time()
        if proposals:
            eval_report = evaluate_ai_proposals_live(
                proposals=proposals,
                baseline_cqs=cqs_result,
                eval_cohort=QUICK_EVAL_COHORT,
                session_id=session_id,
                use_sec_facts=True,
            )
        else:
            # No proposals — create a zero-result report
            eval_report = AIEvalReport(
                session_id=session_id,
                proposals_total=0,
                kept=0,
                discarded=0,
                vetoed=0,
                cqs_start=cqs_start,
                cqs_end=cqs_start,
                ef_cqs_start=ef_cqs_start,
                ef_cqs_end=ef_cqs_start,
            )
        t_validate = time.time() - t2

        # ---- Assertions ----

        # Report counts add up
        assert eval_report.kept + eval_report.discarded + eval_report.vetoed <= eval_report.proposals_total, (
            f"Counts don't add up: kept={eval_report.kept} + discarded={eval_report.discarded} "
            f"+ vetoed={eval_report.vetoed} > total={eval_report.proposals_total}"
        )

        # CQS gate invariant: if any KEEP, EF-CQS did not regress
        if eval_report.kept > 0:
            assert eval_report.ef_cqs_end >= ef_cqs_start - 0.001, (
                f"EF-CQS regressed after KEEP: {ef_cqs_start:.4f} → {eval_report.ef_cqs_end:.4f}"
            )

        # Zero-KEEP invariant: if 0 KEEP, CQS should be unchanged
        if eval_report.kept == 0:
            assert abs(eval_report.cqs_end - cqs_start) < 0.001, (
                f"CQS changed with 0 KEEPs: {cqs_start:.4f} → {eval_report.cqs_end:.4f}"
            )

        # Circuit breaker should not fire for small proposal counts
        if eval_report.proposals_total < 10:
            assert not eval_report.stopped_early, (
                f"Circuit breaker fired with only {eval_report.proposals_total} proposals: "
                f"{eval_report.stop_reason}"
            )

        # config_diffs count matches kept count
        assert len(eval_report.config_diffs) == eval_report.kept, (
            f"config_diffs count ({len(eval_report.config_diffs)}) != kept ({eval_report.kept})"
        )

        # O1: companies_exhausted is a list
        assert isinstance(eval_report.companies_exhausted, list)

        # O4: pre_screen_filtered is non-negative
        assert eval_report.pre_screen_filtered >= 0

        # O5: retry counts are non-negative, retry_kept <= retries
        assert eval_report.retries >= 0
        assert eval_report.retry_kept >= 0
        assert eval_report.retry_kept <= eval_report.retries

        # ---- Structured Summary ----
        total_cost = cost_tracker.get("total_cost", 0)
        total_elapsed = t_measure + t_resolve + t_validate
        resolution_rate = (
            dispatch_report.valid_proposals / dispatch_report.actionable_gaps * 100
            if dispatch_report.actionable_gaps > 0 else 0
        )
        cost_per_gap = (
            total_cost / dispatch_report.actionable_gaps
            if dispatch_report.actionable_gaps > 0 else 0
        )
        cost_per_resolved = (
            total_cost / eval_report.kept
            if eval_report.kept > 0 else float("inf")
        )

        print(f"\n{'='*60}")
        print(f"  FULL PIPELINE: MEASURE → RESOLVE → VALIDATE")
        print(f"{'='*60}")
        print(f"  Session:  {session_id}")
        print(f"  Cohort:   {QUICK_EVAL_COHORT}")
        print()
        print(f"  Timing:")
        print(f"    MEASURE:   {t_measure:.1f}s")
        print(f"    RESOLVE:   {t_resolve:.1f}s")
        print(f"    VALIDATE:  {t_validate:.1f}s")
        print(f"    Total:     {total_elapsed:.1f}s")
        print()
        print(f"  CQS Trajectory:")
        print(f"    CQS:    {cqs_start:.4f} → {eval_report.cqs_end:.4f} (Δ={eval_report.cqs_end - cqs_start:+.4f})")
        print(f"    EF-CQS: {ef_cqs_start:.4f} → {eval_report.ef_cqs_end:.4f} (Δ={eval_report.ef_cqs_end - ef_cqs_start:+.4f})")
        print()
        print(f"  Dispatch:")
        print(f"    Total gaps:     {dispatch_report.total_gaps}")
        print(f"    Actionable:     {dispatch_report.actionable_gaps}")
        print(f"    Not-onboarded:  {dispatch_report.not_onboarded_skipped}")
        print(f"    Proposals:      {dispatch_report.valid_proposals}")
        print(f"    Resolution:     {resolution_rate:.1f}%")
        print()
        print(f"  Evaluation:")
        print(f"    KEEP:     {eval_report.kept} (retry: {eval_report.retry_kept})")
        print(f"    DISCARD:  {eval_report.discarded}")
        print(f"    VETO:     {eval_report.vetoed}")
        print(f"    Pre-screened: {eval_report.pre_screen_filtered}")
        print(f"    Retries:  {eval_report.retries}")
        if eval_report.companies_exhausted:
            print(f"    Exhausted: {eval_report.companies_exhausted}")
        if eval_report.stopped_early:
            print(f"    STOPPED:  {eval_report.stop_reason}")
        print()
        print(f"  Cost:")
        print(f"    Total:        ${total_cost:.4f}")
        print(f"    Per gap:      ${cost_per_gap:.4f}")
        print(f"    Per resolved: ${cost_per_resolved:.4f}" if eval_report.kept > 0 else "    Per resolved: N/A (0 kept)")
        print(f"{'='*60}")

    def test_config_revert_is_idempotent(self):
        """Verify revert_all_configs() restores exact config fingerprint."""
        fingerprint_before = get_config_fingerprint()

        # Apply a harmless change: read metrics.yaml and write it back with a comment
        metrics_path = TIER1_CONFIGS["metrics.yaml"]
        original_content = metrics_path.read_text()
        metrics_path.write_text(original_content + "\n# test_validation_marker\n")

        # Fingerprint should differ now
        fingerprint_dirty = get_config_fingerprint()
        assert fingerprint_dirty != fingerprint_before, (
            "Config fingerprint unchanged after modification — test is invalid"
        )

        # Revert
        revert_all_configs()

        # Fingerprint should match original
        fingerprint_restored = get_config_fingerprint()
        assert fingerprint_restored == fingerprint_before, (
            f"Config not restored! Before={fingerprint_before}, Restored={fingerprint_restored}"
        )
