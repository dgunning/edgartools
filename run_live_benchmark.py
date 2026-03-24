"""
Live Large-Scale E2E Evaluation of Typed Actions.

Phases:
  0. Setup (logging, imports, cohort)
  1. Generate fresh gap manifest for 50 companies (~8 min)
  2. Run 3-arm benchmark: Typed Sonnet, Typed Opus, Raw Sonnet control (~50 min)
  3. Limitations analysis — categorize unsolved gaps
  4. Save machine-readable report JSON

Usage:
  Run interactively from Claude Code (mcp__pal__chat provides the AI caller):
    from run_live_benchmark import run_live_benchmark
    run_live_benchmark(ai_caller=my_caller)

  Or import individual phases for step-by-step execution.
"""

import json
import logging
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# ─── Edgar setup ───────────────────────────────────────────────────────────────
from edgar import set_identity, use_local_storage

set_identity("Dev Gunning developer-gunning@gmail.com")
use_local_storage(True)

# ─── Logging ───────────────────────────────────────────────────────────────────
SESSION_ID = f"live_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
LOG_FILE = f"live_benchmark_{SESSION_ID}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("live_benchmark")

# ─── Imports ───────────────────────────────────────────────────────────────────
from edgar.xbrl.standardization.tools.auto_eval import (
    EXPANSION_COHORT_50,
    print_cqs_report,
    print_gap_report,
)
from edgar.xbrl.standardization.tools.auto_eval_loop import (
    generate_gap_manifest,
    GapManifest,
    GAP_MANIFESTS_DIR,
)
from edgar.xbrl.standardization.tools.consult_ai_gaps import (
    BenchmarkConfig,
    BenchmarkResult,
    build_typed_action_prompt,
    build_consultation_prompt,
    run_agent_benchmark,
    print_benchmark_comparison,
)

# ─── Constants ─────────────────────────────────────────────────────────────────
EVAL_COHORT = EXPANSION_COHORT_50
MAX_GAPS = 30


# =============================================================================
# AI CALLER
# =============================================================================

def make_placeholder_caller() -> Callable[[str, str], Optional[str]]:
    """Create a placeholder AI caller that raises NotImplementedError.

    When running from Claude Code, replace this with a caller that uses
    mcp__pal__chat. See run_live_benchmark() for the expected signature.
    """
    def _placeholder(prompt: str, model: str) -> Optional[str]:
        raise NotImplementedError(
            "No AI caller configured. Pass ai_caller= to run_live_benchmark() "
            "or replace this with an mcp__pal__chat wrapper."
        )
    return _placeholder


# =============================================================================
# PHASE 1: GENERATE GAP MANIFEST
# =============================================================================

def phase1_generate_manifest(
    session_id: str = SESSION_ID,
    max_workers: int = 2,
) -> Tuple[GapManifest, Path]:
    """Generate a fresh gap manifest for the full 50-company cohort."""
    logger.info("=" * 70)
    logger.info("PHASE 1: Generating gap manifest")
    logger.info(f"  Cohort: {len(EVAL_COHORT)} companies")
    logger.info(f"  Session: {session_id}")
    logger.info("=" * 70)

    t0 = time.time()
    manifest, manifest_path = generate_gap_manifest(
        eval_cohort=EVAL_COHORT,
        session_id=session_id,
        snapshot_mode=True,
        max_workers=max_workers,
    )
    elapsed = time.time() - t0

    # Log gap distribution
    type_dist = Counter(g.gap_type for g in manifest.gaps)
    root_dist = Counter(g.root_cause for g in manifest.gaps)
    agent_dist = Counter(g.ai_agent_type for g in manifest.gaps)

    logger.info(f"\nPhase 1 complete in {elapsed:.0f}s")
    logger.info(f"  Total gaps: {len(manifest.gaps)}")
    logger.info(f"  Baseline CQS: {manifest.baseline_cqs:.4f}")
    logger.info(f"  Gap type distribution: {dict(type_dist)}")
    logger.info(f"  Root cause distribution: {dict(root_dist)}")
    logger.info(f"  Agent type distribution: {dict(agent_dist)}")
    logger.info(f"  Manifest saved to: {manifest_path}")

    # Pretty-print CQS baseline
    print(f"\n{'='*70}")
    print(f"PHASE 1 RESULTS: {len(manifest.gaps)} gaps across {len(EVAL_COHORT)} companies")
    print(f"Baseline CQS: {manifest.baseline_cqs:.4f}")
    print(f"Gap types: {dict(type_dist)}")
    print(f"Root causes: {dict(root_dist)}")
    print(f"Elapsed: {elapsed:.0f}s")
    print(f"{'='*70}\n")

    return manifest, manifest_path


# =============================================================================
# PHASE 2: RUN 3-ARM BENCHMARK
# =============================================================================

def phase2_run_benchmark(
    manifest_path: Path,
    ai_caller: Callable[[str, str], Optional[str]],
    max_gaps: int = MAX_GAPS,
    max_workers: int = 2,
) -> List[BenchmarkResult]:
    """Run the 3-arm benchmark: Typed Sonnet, Typed Opus, Raw Sonnet control."""
    logger.info("=" * 70)
    logger.info("PHASE 2: Running 3-arm benchmark")
    logger.info(f"  Max gaps per arm: {max_gaps}")
    logger.info("=" * 70)

    configs = [
        BenchmarkConfig(
            prompt_builder=build_typed_action_prompt,
            model="sonnet",
            label="Typed Sonnet",
            use_typed_actions=True,
        ),
        BenchmarkConfig(
            prompt_builder=build_typed_action_prompt,
            model="opus",
            label="Typed Opus",
            use_typed_actions=True,
        ),
        BenchmarkConfig(
            prompt_builder=build_consultation_prompt,
            model="sonnet",
            label="Raw Sonnet (control)",
            use_typed_actions=False,
        ),
    ]

    t0 = time.time()
    results = run_agent_benchmark(
        manifest_path=manifest_path,
        configs=configs,
        ai_caller=ai_caller,
        max_gaps=max_gaps,
        eval_cohort=EVAL_COHORT,
        max_workers=max_workers,
    )
    elapsed = time.time() - t0

    logger.info(f"\nPhase 2 complete in {elapsed:.0f}s")
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

# Root cause categories and their meaning
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


def phase3_limitations_analysis(
    manifest: GapManifest,
    results: List[BenchmarkResult],
) -> Dict:
    """Analyze what the system cannot solve and why."""
    logger.info("=" * 70)
    logger.info("PHASE 3: Limitations analysis")
    logger.info("=" * 70)

    # --- Gap landscape by root cause ---
    root_cause_counts = Counter(g.root_cause or "unknown" for g in manifest.gaps)

    # --- Gap landscape by sector (derive from ticker if possible) ---
    sector_map = _build_sector_map()
    sector_counts = Counter(sector_map.get(g.ticker, "Unknown") for g in manifest.gaps)

    # --- Gap landscape by difficulty tier ---
    difficulty_counts = Counter(g.difficulty_tier for g in manifest.gaps)

    # --- Action distribution from typed arm responses ---
    action_dist: Counter = Counter()
    confidence_by_action: Dict[str, List[float]] = {}

    # Parse responses from typed arms (first two results are typed)
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

    # Average confidence per action
    avg_confidence = {
        action: sum(scores) / len(scores)
        for action, scores in confidence_by_action.items()
        if scores
    }

    # --- Print results ---
    print(f"\n{'='*70}")
    print("PHASE 3: LIMITATIONS ANALYSIS")
    print(f"{'='*70}")

    print(f"\n  Total gaps in manifest: {len(manifest.gaps)}")

    print("\n  Root Cause Distribution:")
    for cause, count in root_cause_counts.most_common():
        desc = LIMITATION_CATEGORIES.get(cause, "")
        print(f"    {cause:30s} {count:4d}  {desc}")

    print("\n  Sector Distribution:")
    for sector, count in sector_counts.most_common():
        print(f"    {sector:30s} {count:4d}")

    print("\n  Difficulty Tier Distribution:")
    for tier, count in difficulty_counts.most_common():
        print(f"    {tier:30s} {count:4d}")

    if action_dist:
        print("\n  Action Distribution (typed arms):")
        for action, count in action_dist.most_common():
            avg = avg_confidence.get(action, 0.0)
            print(f"    {action:30s} {count:4d}  (avg confidence: {avg:.2f})")

    analysis = {
        "total_gaps": len(manifest.gaps),
        "root_cause_distribution": dict(root_cause_counts),
        "sector_distribution": dict(sector_counts),
        "difficulty_distribution": dict(difficulty_counts),
        "action_distribution": dict(action_dist),
        "avg_confidence_by_action": avg_confidence,
        "limitation_descriptions": LIMITATION_CATEGORIES,
    }
    return analysis


def _build_sector_map() -> Dict[str, str]:
    """Map tickers from EXPANSION_COHORT_50 to sectors."""
    # Hardcoded from the cohort definition comments in auto_eval.py
    sectors = {
        "Tech": ["AAPL", "MSFT", "GOOG", "AMZN", "META", "NVDA", "TSLA", "CRM", "ADBE", "INTC"],
        "Finance": ["JPM", "BAC", "GS", "MS", "WFC", "BRK-B", "C", "AXP", "BLK", "SCHW"],
        "Healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "TMO", "ABT", "LLY", "BMY", "AMGN"],
        "Energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
        "Consumer": ["WMT", "PG", "KO", "PEP", "COST"],
        "Industrial": ["CAT", "BA", "HON", "GE", "MMM"],
        "Telecom": ["VZ", "TMUS", "T"],
        "Real Estate": ["AMT", "PLD"],
    }
    out = {}
    for sector, tickers in sectors.items():
        for t in tickers:
            out[t] = sector
    return out


# =============================================================================
# PHASE 4: SAVE REPORT JSON
# =============================================================================

def phase4_save_report(
    manifest: GapManifest,
    results: List[BenchmarkResult],
    analysis: Dict,
    session_id: str = SESSION_ID,
    elapsed_total: float = 0.0,
) -> Path:
    """Save a machine-readable report JSON."""
    logger.info("=" * 70)
    logger.info("PHASE 4: Saving report")
    logger.info("=" * 70)

    report = {
        "session_id": session_id,
        "created_at": datetime.now().isoformat(),
        "eval_cohort": list(EVAL_COHORT),
        "baseline_cqs": manifest.baseline_cqs,
        "total_gaps": len(manifest.gaps),
        "max_gaps_per_arm": MAX_GAPS,
        "elapsed_seconds": elapsed_total,

        # Benchmark arm results
        "benchmark_arms": [
            {
                "label": r.config.label,
                "model": r.config.model,
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

        # Limitations analysis
        "limitations": analysis,
    }

    report_path = GAP_MANIFESTS_DIR / f"live_benchmark_report_{session_id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    logger.info(f"Report saved to {report_path}")
    print(f"\nReport saved to: {report_path}")
    return report_path


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

def run_live_benchmark(
    ai_caller: Optional[Callable[[str, str], Optional[str]]] = None,
    max_gaps: int = MAX_GAPS,
    max_workers: int = 2,
    session_id: Optional[str] = None,
    skip_phase1: Optional[Path] = None,
) -> Dict:
    """Run the full 4-phase live benchmark.

    Args:
        ai_caller: Callable(prompt, model) -> response_text.
            Required for Phase 2. If None, uses placeholder (will error).
        max_gaps: Max gaps per benchmark arm.
        max_workers: Parallel workers for CQS computation.
        session_id: Override session ID. Auto-generated if None.
        skip_phase1: If provided, skip manifest generation and load from this path.

    Returns:
        Dict with full report data.
    """
    sid = session_id or SESSION_ID
    if ai_caller is None:
        ai_caller = make_placeholder_caller()

    t0 = time.time()

    # Phase 1
    if skip_phase1:
        from edgar.xbrl.standardization.tools.auto_eval_loop import load_gap_manifest
        logger.info(f"Skipping Phase 1, loading manifest from {skip_phase1}")
        manifest = load_gap_manifest(skip_phase1)
        manifest_path = skip_phase1
    else:
        manifest, manifest_path = phase1_generate_manifest(
            session_id=sid, max_workers=max_workers,
        )

    # Phase 2
    results = phase2_run_benchmark(
        manifest_path=manifest_path,
        ai_caller=ai_caller,
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

    # Summary
    print(f"\n{'='*70}")
    print("LIVE BENCHMARK COMPLETE")
    print(f"{'='*70}")
    print(f"  Session: {sid}")
    print(f"  Duration: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"  Manifest: {manifest_path}")
    print(f"  Report: {report_path}")

    # Quick comparison
    for r in results:
        marker = " ***" if r.kept > 0 else ""
        print(f"  {r.config.label}: {r.kept} kept, CQS lift {r.cqs_lift:+.4f}{marker}")
    print()

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
    print("This script is designed to be run from Claude Code (for AI caller access).")
    print("Usage:")
    print("  from run_live_benchmark import run_live_benchmark")
    print("  run_live_benchmark(ai_caller=my_caller)")
    print()
    print("For Phase 1 only (no AI needed):")
    print("  from run_live_benchmark import phase1_generate_manifest")
    print("  manifest, path = phase1_generate_manifest()")
    sys.exit(0)
