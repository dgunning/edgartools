"""
Live Large-Scale E2E Evaluation of Typed Actions.

Phases:
  0. Setup (logging, imports, cohort)
  1. Generate fresh gap manifest for 50 companies (~8 min)
  2. Run 2-arm benchmark: Typed Gemini Flash, Raw Gemini Flash control
  3. Limitations analysis — categorize unsolved gaps
  4. Save machine-readable report JSON

Usage:
  Self-running when OPENROUTER_API_KEY is set:
    python run_live_benchmark.py

  Or import for programmatic use:
    from run_live_benchmark import run_live_benchmark
    run_live_benchmark()  # Uses OpenRouter API automatically

  Or pass a custom AI caller (e.g. for Claude Code agent mode):
    run_live_benchmark(ai_caller=my_caller)
"""

import json
import logging
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from edgar.xbrl.standardization.tools.auto_eval import EXPANSION_COHORT_50
from edgar.xbrl.standardization.tools.auto_eval_loop import (
    generate_gap_manifest,
    load_gap_manifest,
    GapManifest,
    GAP_MANIFESTS_DIR,
)
from edgar.xbrl.standardization.tools.capability_registry import (
    GapDisposition,
    triage_gaps,
    print_triage_summary,
)
from edgar.xbrl.standardization.tools.consult_ai_gaps import (
    BenchmarkConfig,
    BenchmarkResult,
    DEFAULT_API_MODEL,
    build_typed_action_prompt,
    build_consultation_prompt,
    make_openrouter_caller,
    run_agent_benchmark,
    print_benchmark_comparison,
)

logger = logging.getLogger("live_benchmark")

# ─── Constants ─────────────────────────────────────────────────────────────────
EVAL_COHORT = EXPANSION_COHORT_50
MAX_GAPS = 30

# Tiered cohorts for progressive E2E testing
E2E_FOCUSED_COHORT = [
    "AAPL",  # Tech, well-mapped, few gaps (control)
    "JPM",   # Banking, has COGS exclusion (tests C3), sign_negate overrides
    "XOM",   # Energy, CapEx sign_convention: negate (tests C2)
    "CAT",   # Industrial, known hard gaps
    "MS",    # Dealer bank, ShareRepurchases sign_negate
    "DE",    # Industrial, many composite formulas
    "NEE",   # Utility, industry_structural gaps (tests C1 inert filtering)
    "LLY",   # Pharma, R&D-heavy
    "NVDA",  # Tech, fast-growing (variance-prone)
    "KO",    # Consumer staples, simple structure (control)
]

# Sector map matching EXPANSION_COHORT_50 comments in auto_eval.py
_SECTOR_MAP: Dict[str, str] = {}
for _sector, _tickers in {
    "Tech": ["AAPL", "MSFT", "GOOG", "AMZN", "META", "NVDA", "TSLA", "CRM", "ADBE", "INTC"],
    "Banking/Finance": ["JPM", "BAC", "GS", "MS", "C", "BLK", "SCHW", "AXP"],
    "Energy": ["XOM", "CVX", "COP", "SLB"],
    "Consumer": ["WMT", "PG", "KO", "PEP", "MCD", "NKE", "COST"],
    "Healthcare": ["JNJ", "UNH", "PFE", "LLY", "ABBV", "MRK", "TMO"],
    "Industrial": ["CAT", "HON", "GE", "DE", "RTX", "UPS"],
    "Other": ["V", "MA", "NEE", "T", "HD", "LOW", "NFLX", "AVGO"],
}.items():
    for _t in _tickers:
        _SECTOR_MAP[_t] = _sector

LIMITATION_CATEGORIES = {
    "industry_structural": "Metric doesn't exist for this industry (e.g. banking GrossProfit)",
    "missing_concept": "XBRL concept not in known_concepts list",
    "extension_concept": "Company uses custom taxonomy extension",
    "sign_error": "Sign convention mismatch XBRL vs yfinance",
    "algebraic_coincidence": "Multiple formulas produce same value",
    "reference_error": "yfinance reference value is questionable",
    "unmapped": "No mapping found — default semantic mapper territory",
    "high_variance": "Mapped but value differs significantly from reference",
    "regression": "Previously passing, now failing",
    "unknown": "Root cause not classified",
}


def _setup_environment(session_id: str) -> None:
    """Configure edgar identity, local storage, and logging. Called once per run."""
    from edgar import set_identity, use_local_storage
    set_identity("Dev Gunning developer-gunning@gmail.com")
    use_local_storage(True)

    log_file = f"live_benchmark_{session_id}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )


# =============================================================================
# AI CALLER
# =============================================================================

def make_default_ai_caller() -> Tuple[Callable[[str, str], Optional[str]], Dict]:
    """Create default AI caller using OpenRouter API (gemini-flash).

    Returns (caller, cost_tracker) tuple.
    Falls back to a caller that raises NotImplementedError if unavailable.
    """
    try:
        return make_openrouter_caller()
    except (ImportError, ValueError) as e:
        logger.warning(f"Cannot create OpenRouter caller: {e}")

        def _fallback(prompt: str, model: str) -> Optional[str]:
            raise NotImplementedError(
                f"No AI caller available: {e}. "
                "Set OPENROUTER_API_KEY or pass ai_caller= to run_live_benchmark()."
            )

        return _fallback, {"total_cost": 0.0, "calls": 0}


# =============================================================================
# PHASE 0: TRIAGE ONLY (no AI calls)
# =============================================================================

def phase0_triage_only(
    eval_cohort: List[str] = None,
    session_id: str = None,
    max_workers: int = 2,
) -> Dict:
    """Run manifest generation + triage analysis only (no AI calls).

    Fast validation that C1/C2/C3 work correctly:
    - Generates gap manifest with disposition annotations
    - Prints triage summary (how many config_fixable vs scoring_inert vs engine_blocked)
    - Computes CQS to verify no regression from C3 changes
    - Returns summary dict for assertions

    Args:
        eval_cohort: List of tickers. Defaults to QUICK_EVAL_COHORT (5 companies).
        session_id: Override session ID. Auto-generated if None.
        max_workers: Parallel workers for CQS computation.

    Returns:
        Dict with triage summary and CQS baseline.
    """
    from edgar.xbrl.standardization.tools.auto_eval import QUICK_EVAL_COHORT

    cohort = eval_cohort or QUICK_EVAL_COHORT
    sid = session_id or f"triage_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _setup_environment(sid)

    logger.info("=" * 70)
    logger.info("PHASE 0: Triage-only run (no AI)")
    logger.info(f"  Cohort: {cohort}")
    logger.info(f"  Session: {sid}")
    logger.info("=" * 70)

    t0 = time.time()
    manifest, manifest_path = generate_gap_manifest(
        eval_cohort=cohort,
        session_id=sid,
        snapshot_mode=True,
        max_workers=max_workers,
    )
    elapsed = time.time() - t0

    # Triage analysis
    triaged = triage_gaps(manifest.gaps)
    config_fixable = triaged[GapDisposition.CONFIG_FIXABLE]
    scoring_inert = triaged[GapDisposition.SCORING_INERT]
    engine_blocked = triaged[GapDisposition.ENGINE_BLOCKED]

    # Detailed inert breakdown
    sign_inert = [g for g in scoring_inert
                  if g.root_cause == "sign_error" or g.hv_subtype == "hv_sign_inverted"]
    structural_inert = [g for g in scoring_inert
                        if g.root_cause == "industry_structural"]

    logger.info(f"Phase 0 complete in {elapsed:.0f}s")
    logger.info(f"  Total gaps: {len(manifest.gaps)}")
    logger.info(f"  Baseline CQS: {manifest.baseline_cqs:.4f}")
    logger.info(f"  Config fixable: {len(config_fixable)}")
    logger.info(f"  Scoring inert: {len(scoring_inert)} "
                f"({len(sign_inert)} sign, {len(structural_inert)} structural)")
    logger.info(f"  Engine blocked: {len(engine_blocked)}")

    # Rich triage table
    print_triage_summary(manifest.gaps)

    result = {
        "total_gaps": len(manifest.gaps),
        "config_fixable": len(config_fixable),
        "scoring_inert": len(scoring_inert),
        "engine_blocked": len(engine_blocked),
        "baseline_cqs": manifest.baseline_cqs,
        "manifest_path": manifest_path,
        "sign_inert_count": len(sign_inert),
        "structural_inert_count": len(structural_inert),
        "elapsed_seconds": elapsed,
        "eval_cohort": cohort,
    }

    logger.info(f"  Manifest: {manifest_path}")
    return result


# =============================================================================
# PHASE 1: GENERATE GAP MANIFEST
# =============================================================================

def phase1_generate_manifest(
    session_id: str,
    eval_cohort: List[str] = None,
    max_workers: int = 2,
) -> Tuple[GapManifest, Path]:
    """Generate a fresh gap manifest for the evaluation cohort.

    Args:
        session_id: Unique session identifier.
        eval_cohort: List of tickers. Defaults to EVAL_COHORT (50 companies).
        max_workers: Parallel workers for CQS computation.
    """
    cohort = eval_cohort or EVAL_COHORT
    logger.info("=" * 70)
    logger.info("PHASE 1: Generating gap manifest")
    logger.info(f"  Cohort: {len(cohort)} companies")
    logger.info(f"  Session: {session_id}")
    logger.info("=" * 70)

    t0 = time.time()
    manifest, manifest_path = generate_gap_manifest(
        eval_cohort=cohort,
        session_id=session_id,
        snapshot_mode=True,
        max_workers=max_workers,
    )
    elapsed = time.time() - t0

    type_dist = Counter(g.gap_type for g in manifest.gaps)
    root_dist = Counter(g.root_cause for g in manifest.gaps)
    agent_dist = Counter(g.ai_agent_type for g in manifest.gaps)
    disp_dist = Counter(g.disposition for g in manifest.gaps)

    logger.info(f"Phase 1 complete in {elapsed:.0f}s")
    logger.info(f"  Total gaps: {len(manifest.gaps)}")
    logger.info(f"  Baseline CQS: {manifest.baseline_cqs:.4f}")
    logger.info(f"  Gap type distribution: {dict(type_dist)}")
    logger.info(f"  Root cause distribution: {dict(root_dist)}")
    logger.info(f"  Agent type distribution: {dict(agent_dist)}")
    logger.info(f"  Disposition: {dict(disp_dist)}")
    logger.info(f"  Manifest saved to: {manifest_path}")

    # Rich triage summary
    print_triage_summary(manifest.gaps)

    return manifest, manifest_path


# =============================================================================
# PHASE 2: RUN 3-ARM BENCHMARK
# =============================================================================

def phase2_run_benchmark(
    manifest_path: Path,
    ai_caller: Callable[[str, str], Optional[str]],
    eval_cohort: List[str] = None,
    max_gaps: int = MAX_GAPS,
    max_workers: int = 2,
) -> List[BenchmarkResult]:
    """Run the 2-arm benchmark: Typed Gemini Flash vs Raw Gemini Flash control."""
    logger.info("=" * 70)
    logger.info("PHASE 2: Running 2-arm benchmark")
    logger.info(f"  Max gaps per arm: {max_gaps}")
    logger.info("=" * 70)

    configs = [
        BenchmarkConfig(
            prompt_builder=build_typed_action_prompt,
            model=DEFAULT_API_MODEL,
            label="Typed Gemini Flash",
            use_typed_actions=True,
            backend="api",
        ),
        BenchmarkConfig(
            prompt_builder=build_consultation_prompt,
            model=DEFAULT_API_MODEL,
            label="Raw Gemini Flash (control)",
            use_typed_actions=False,
            backend="api",
        ),
    ]

    cohort = eval_cohort or EVAL_COHORT
    t0 = time.time()
    results = run_agent_benchmark(
        manifest_path=manifest_path,
        configs=configs,
        ai_caller=ai_caller,
        max_gaps=max_gaps,
        eval_cohort=cohort,
        max_workers=max_workers,
    )
    elapsed = time.time() - t0

    logger.info(f"Phase 2 complete in {elapsed:.0f}s")
    for r in results:
        logger.info(
            f"  {r.config.label}: kept={r.kept}, discarded={r.discarded}, "
            f"vetoed={r.vetoed}, cop_outs={r.cop_outs}, "
            f"CQS {r.cqs_start:.4f} -> {r.cqs_end:.4f} ({r.cqs_lift:+.4f})"
        )

    print_benchmark_comparison(results)
    return results


# =============================================================================
# PHASE 3: LIMITATIONS ANALYSIS
# =============================================================================

def phase3_limitations_analysis(
    manifest: GapManifest,
    results: List[BenchmarkResult],
) -> Dict:
    """Analyze what the system cannot solve and why."""
    logger.info("=" * 70)
    logger.info("PHASE 3: Limitations analysis")
    logger.info("=" * 70)

    root_cause_counts = Counter(g.root_cause or "unknown" for g in manifest.gaps)
    sector_counts = Counter(_SECTOR_MAP.get(g.ticker, "Unknown") for g in manifest.gaps)
    difficulty_counts = Counter(g.difficulty_tier for g in manifest.gaps)

    action_dist: Counter = Counter()
    confidence_by_action: Dict[str, List[float]] = {}

    for r in results:
        if not r.config.use_typed_actions:
            continue
        for gap_key, response in r.responses:
            if response is None:
                continue
            try:
                parsed = json.loads(response)
                action = parsed.get("action", "UNKNOWN")
                confidence = parsed.get("confidence", 0.0)
                action_dist[action] += 1
                confidence_by_action.setdefault(action, []).append(confidence)
            except (json.JSONDecodeError, TypeError):
                action_dist["PARSE_FAILURE"] += 1

    avg_confidence = {
        action: sum(scores) / len(scores)
        for action, scores in confidence_by_action.items()
        if scores
    }

    logger.info(f"  Total gaps in manifest: {len(manifest.gaps)}")
    logger.info(f"  Root causes: {dict(root_cause_counts.most_common())}")
    logger.info(f"  Sectors: {dict(sector_counts.most_common())}")
    logger.info(f"  Difficulty: {dict(difficulty_counts.most_common())}")
    if action_dist:
        logger.info(f"  Actions: {dict(action_dist.most_common())}")
        logger.info(f"  Avg confidence: {avg_confidence}")

    return {
        "total_gaps": len(manifest.gaps),
        "root_cause_distribution": dict(root_cause_counts),
        "sector_distribution": dict(sector_counts),
        "difficulty_distribution": dict(difficulty_counts),
        "action_distribution": dict(action_dist),
        "avg_confidence_by_action": avg_confidence,
        "limitation_descriptions": LIMITATION_CATEGORIES,
    }


# =============================================================================
# PHASE 4: SAVE REPORT JSON
# =============================================================================

def phase4_save_report(
    manifest: GapManifest,
    results: List[BenchmarkResult],
    analysis: Dict,
    session_id: str,
    elapsed_total: float = 0.0,
) -> Path:
    """Save a machine-readable report JSON."""
    logger.info("=" * 70)
    logger.info("PHASE 4: Saving report")
    logger.info("=" * 70)

    report = {
        "session_id": session_id,
        "created_at": datetime.now().isoformat(),
        "eval_cohort": manifest.eval_cohort,
        "baseline_cqs": manifest.baseline_cqs,
        "total_gaps": len(manifest.gaps),
        "max_gaps_per_arm": MAX_GAPS,
        "elapsed_seconds": elapsed_total,
        "benchmark_arms": [
            {
                "label": r.config.label,
                "model": r.config.model,
                "backend": r.config.backend,
                "use_typed_actions": r.config.use_typed_actions,
                "total_gaps": r.total_gaps,
                "valid_proposals": r.valid_proposals,
                "kept": r.kept,
                "discarded": r.discarded,
                "vetoed": r.vetoed,
                "cop_outs": r.cop_outs,
                "preflight_rejected": r.preflight_rejected,
                "resolution_rate": r.resolution_rate,
                "cop_out_rate": r.cop_out_rate,
                "cqs_start": r.cqs_start,
                "cqs_end": r.cqs_end,
                "cqs_lift": r.cqs_lift,
            }
            for r in results
        ],
        "limitations": analysis,
    }

    report_path = GAP_MANIFESTS_DIR / f"live_benchmark_report_{session_id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    logger.info(f"Report saved to {report_path}")
    return report_path


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

def run_live_benchmark(
    ai_caller: Optional[Callable[[str, str], Optional[str]]] = None,
    eval_cohort: List[str] = None,
    max_gaps: int = MAX_GAPS,
    max_workers: int = 2,
    session_id: Optional[str] = None,
    skip_phase1: Optional[Path] = None,
) -> Dict:
    """Run the full 4-phase live benchmark.

    Args:
        ai_caller: Callable(prompt, model) -> response_text.
            If None, creates OpenRouter caller via make_default_ai_caller().
        eval_cohort: List of tickers. Defaults to EXPANSION_COHORT_50.
        max_gaps: Max gaps per benchmark arm.
        max_workers: Parallel workers for CQS computation.
        session_id: Override session ID. Auto-generated if None.
        skip_phase1: If provided, skip manifest generation and load from this path.

    Returns:
        Dict with full report data.
    """
    cohort = eval_cohort or EVAL_COHORT
    sid = session_id or f"live_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _setup_environment(sid)

    cost_tracker = None
    if ai_caller is None:
        ai_caller, cost_tracker = make_default_ai_caller()

    t0 = time.time()

    # Phase 1
    if skip_phase1:
        logger.info(f"Skipping Phase 1, loading manifest from {skip_phase1}")
        manifest = load_gap_manifest(skip_phase1)
        manifest_path = skip_phase1
    else:
        manifest, manifest_path = phase1_generate_manifest(
            session_id=sid, eval_cohort=cohort, max_workers=max_workers,
        )

    # Phase 2
    results = phase2_run_benchmark(
        manifest_path=manifest_path,
        ai_caller=ai_caller,
        eval_cohort=cohort,
        max_gaps=max_gaps,
        max_workers=max_workers,
    )

    # Phase 3
    analysis = phase3_limitations_analysis(manifest, results)

    # Phase 4
    elapsed = time.time() - t0
    report_path = phase4_save_report(
        manifest, results, analysis,
        session_id=sid, elapsed_total=elapsed,
    )

    # Cost tracking
    if cost_tracker and cost_tracker["calls"] > 0:
        logger.info(
            f"Total API cost: ${cost_tracker['total_cost']:.4f} "
            f"({cost_tracker['calls']} calls)"
        )

    # Summary
    logger.info(f"LIVE BENCHMARK COMPLETE — {sid}")
    logger.info(f"  Duration: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    logger.info(f"  Manifest: {manifest_path}")
    logger.info(f"  Report: {report_path}")
    for r in results:
        marker = " ***" if r.kept > 0 else ""
        logger.info(f"  {r.config.label}: {r.kept} kept, CQS lift {r.cqs_lift:+.4f}{marker}")

    return {
        "manifest_path": str(manifest_path),
        "report_path": str(report_path),
        "results": results,
        "analysis": analysis,
    }


# =============================================================================
# STANDALONE ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Live benchmark for AI gap consultation")
    parser.add_argument(
        "--cohort", choices=["focused", "full"], default="focused",
        help="Evaluation cohort: 'focused' (10 companies) or 'full' (50 companies)",
    )
    parser.add_argument("--max-gaps", type=int, default=MAX_GAPS, help="Max gaps per arm")
    parser.add_argument("--session-id", type=str, default=None, help="Override session ID")
    parser.add_argument("--triage-only", action="store_true", help="Run Phase 0 only (no AI)")
    args = parser.parse_args()

    cohort = E2E_FOCUSED_COHORT if args.cohort == "focused" else EVAL_COHORT

    if args.triage_only:
        result = phase0_triage_only(eval_cohort=cohort, session_id=args.session_id)
        print(f"\nTriage complete: {result['total_gaps']} gaps, CQS={result['baseline_cqs']:.4f}")
    else:
        result = run_live_benchmark(
            eval_cohort=cohort,
            max_gaps=args.max_gaps,
            session_id=args.session_id,
        )
        print(f"\nBenchmark complete. Report: {result['report_path']}")
