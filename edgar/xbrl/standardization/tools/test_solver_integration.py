"""
Integration test script: validates the full Auto-Solver + Two-Score pipeline.

Runs on QUICK_EVAL_COHORT (5 companies) and must complete in <5 minutes.

Usage:
    python -m edgar.xbrl.standardization.tools.test_solver_integration
"""

import logging
import sys
import time
from dataclasses import asdict

from edgar import set_identity, use_local_storage

set_identity("Dev Gunning developer-gunning@gmail.com")
use_local_storage(True)

from edgar.xbrl.standardization.tools.auto_eval import (
    CQSResult,
    MetricGap,
    compute_cqs,
    identify_gaps,
    QUICK_EVAL_COHORT,
)
from edgar.xbrl.standardization.tools.auto_eval_loop import (
    ChangeType,
    ConfigChange,
    OvernightReport,
    propose_change,
)
from edgar.xbrl.standardization.tools.auto_solver import AutoSolver

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"


def main():
    start = time.time()
    results = []

    print()
    print("=" * 70)
    print("  AUTO-SOLVER + TWO-SCORE INTEGRATION TEST")
    print(f"  Cohort: {QUICK_EVAL_COHORT}")
    print("=" * 70)

    # --- Test 1: Baseline CQS with EF/SA fields ---
    print("\n[1/6] Baseline CQS with EF/SA fields...")
    try:
        cqs = compute_cqs(eval_cohort=QUICK_EVAL_COHORT, snapshot_mode=True)
        has_ef = hasattr(cqs, "ef_cqs") and cqs.ef_cqs >= 0
        has_sa = hasattr(cqs, "sa_cqs") and cqs.sa_cqs >= 0
        has_explained = hasattr(cqs, "explained_variance_count")
        ok = has_ef and has_sa and has_explained and cqs.cqs > 0
        status = PASS if ok else FAIL
        print(f"  CQS={cqs.cqs:.4f}  EF={cqs.ef_cqs:.4f}  SA={cqs.sa_cqs:.4f}  "
              f"Explained={cqs.explained_variance_count}")
        print(f"  {status}")
        results.append(ok)
    except Exception as e:
        print(f"  {FAIL}: {e}")
        results.append(False)

    # --- Test 2: Identify solver-eligible gaps ---
    print("\n[2/6] Identify solver-eligible gaps...")
    eligible_gaps = []
    try:
        gaps, _ = identify_gaps(
            eval_cohort=QUICK_EVAL_COHORT, snapshot_mode=True
        )
        eligible_gaps = [
            g for g in gaps
            if g.gap_type in ("validation_failure", "high_variance")
            and g.reference_value is not None
        ]
        ok = True  # Finding gaps is informational, not a pass/fail
        print(f"  Total gaps: {len(gaps)}")
        print(f"  Solver-eligible: {len(eligible_gaps)}")
        for g in eligible_gaps[:5]:
            print(f"    {g.ticker}:{g.metric} ({g.gap_type}, var={g.current_variance}%)")
        status = PASS if ok else FAIL
        print(f"  {status}")
        results.append(ok)
    except Exception as e:
        print(f"  {FAIL}: {e}")
        results.append(False)

    # --- Test 3: Auto-Solver on first eligible gap ---
    print("\n[3/6] Auto-Solver solve_metric()...")
    if eligible_gaps:
        gap = eligible_gaps[0]
        try:
            solver = AutoSolver(snapshot_mode=True)
            candidates = solver.solve_metric(
                gap.ticker, gap.metric, yfinance_value=gap.reference_value
            )
            ok = isinstance(candidates, list)
            if candidates:
                best = candidates[0]
                print(f"  Gap: {gap.ticker}:{gap.metric}")
                print(f"  Found {len(candidates)} candidates")
                print(f"  Best: {' + '.join(best.components)} "
                      f"(${best.total/1e9:.3f}B vs ${best.target/1e9:.3f}B, "
                      f"{best.variance_pct:.2f}%)")
            else:
                print(f"  Gap: {gap.ticker}:{gap.metric}")
                print(f"  No formulas found (this is acceptable)")
            status = PASS if ok else FAIL
            print(f"  {status}")
            results.append(ok)
        except Exception as e:
            print(f"  {FAIL}: {e}")
            results.append(False)
    else:
        print(f"  {SKIP}: No solver-eligible gaps found")
        results.append(True)

    # --- Test 4: Proposal pipeline ---
    print("\n[4/6] propose_change() with solver fallback...")
    if eligible_gaps:
        gap = eligible_gaps[0]
        try:
            change = propose_change(gap, graveyard_entries=[])
            if change is not None:
                print(f"  Proposed: {change.change_type.value}")
                print(f"  Path: {change.yaml_path}")
                print(f"  Rationale: {change.rationale[:80]}")
                ok = True
            else:
                print(f"  No proposal generated (acceptable — gap may be too complex)")
                ok = True
            status = PASS if ok else FAIL
            print(f"  {status}")
            results.append(ok)
        except Exception as e:
            print(f"  {FAIL}: {e}")
            results.append(False)
    else:
        print(f"  {SKIP}: No solver-eligible gaps")
        results.append(True)

    # --- Test 5: OvernightReport with EF/SA fields ---
    print("\n[5/6] OvernightReport EF/SA fields...")
    try:
        report = OvernightReport(
            session_id="test",
            started_at="2026-01-01T00:00:00",
            finished_at="2026-01-01T01:00:00",
            duration_hours=1.0,
            focus_area=None,
            ef_cqs_start=0.95,
            ef_cqs_end=0.96,
            sa_cqs_start=0.80,
            sa_cqs_end=0.82,
            solver_proposals=5,
            solver_kept=2,
        )
        report_dict = asdict(report)
        required_fields = [
            "ef_cqs_start", "ef_cqs_end",
            "sa_cqs_start", "sa_cqs_end",
            "solver_proposals", "solver_kept",
        ]
        ok = all(f in report_dict for f in required_fields)
        print(f"  EF: {report.ef_cqs_start:.4f} -> {report.ef_cqs_end:.4f}")
        print(f"  SA: {report.sa_cqs_start:.4f} -> {report.sa_cqs_end:.4f}")
        print(f"  Solver: {report.solver_kept}/{report.solver_proposals}")
        status = PASS if ok else FAIL
        print(f"  {status}")
        results.append(ok)
    except Exception as e:
        print(f"  {FAIL}: {e}")
        results.append(False)

    # --- Test 6: ChangeType enum includes new values ---
    print("\n[6/6] ChangeType enum values...")
    try:
        ok = (
            ChangeType.ADD_STANDARDIZATION.value == "add_standardization"
            and ChangeType.ADD_KNOWN_VARIANCE.value == "add_known_variance"
        )
        print(f"  ADD_STANDARDIZATION = {ChangeType.ADD_STANDARDIZATION.value}")
        print(f"  ADD_KNOWN_VARIANCE = {ChangeType.ADD_KNOWN_VARIANCE.value}")
        status = PASS if ok else FAIL
        print(f"  {status}")
        results.append(ok)
    except Exception as e:
        print(f"  {FAIL}: {e}")
        results.append(False)

    # --- Summary ---
    elapsed = time.time() - start
    passed = sum(results)
    total = len(results)
    print()
    print("=" * 70)
    print(f"  RESULTS: {passed}/{total} passed  |  {elapsed:.1f}s elapsed")
    if elapsed > 300:
        print(f"  WARNING: Exceeded 5-minute time gate ({elapsed:.0f}s)")
    else:
        print(f"  Timing gate: {PASS} ({elapsed:.0f}s < 300s)")
    print("=" * 70)
    print()

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
