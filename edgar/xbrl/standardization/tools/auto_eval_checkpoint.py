"""
Checkpoint protocol for agent team auto-eval sessions.

Workers write structured checkpoint files so the team lead can monitor
progress without being in the loop. Checkpoints are atomic (tempfile + rename)
and read-safe for concurrent access.
"""

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

CHECKPOINTS_DIR = Path(__file__).parent.parent / "company_mappings" / "checkpoints"


@dataclass
class GapSummary:
    """Compact summary of a MetricGap for checkpoint persistence."""
    ticker: str
    metric: str
    gap_type: str              # "unmapped" | "validation_failure" | "high_variance" | "regression"
    reference_value: Optional[float] = None
    xbrl_value: Optional[float] = None
    current_variance: Optional[float] = None
    graveyard_count: int = 0
    decision: Optional[str] = None  # "KEEP" | "DISCARD" | "VETO" | None (not yet evaluated)
    change_type: Optional[str] = None  # "add_concept" | "add_exclusion" | etc.

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'GapSummary':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_metric_gap(cls, gap) -> 'GapSummary':
        """Create from a MetricGap object."""
        return cls(
            ticker=gap.ticker,
            metric=gap.metric,
            gap_type=gap.gap_type,
            reference_value=gap.reference_value,
            xbrl_value=gap.xbrl_value,
            current_variance=gap.current_variance,
            graveyard_count=gap.graveyard_count,
        )


@dataclass
class WorkerCheckpoint:
    """Structured status report from a worker agent."""
    worker_id: str
    role: str                    # "runner" | "evaluator" | "combined"
    phase: str                   # "starting" | "baseline" | "gaps" | "eval_N" | "finished"
    cohort_size: int
    gaps_found: int = 0
    proposals_total: int = 0
    keeps: int = 0
    discards: int = 0
    vetoes: int = 0
    baseline_cqs: float = 0.0
    current_cqs: float = 0.0
    elapsed_seconds: float = 0.0
    last_update: str = ""        # ISO timestamp
    current_gap: Optional[str] = None  # "TICKER:metric" in progress
    gaps: List[GapSummary] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d['gaps'] = [g.to_dict() for g in self.gaps]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> 'WorkerCheckpoint':
        gaps_data = d.pop('gaps', [])
        cp = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        cp.gaps = [GapSummary.from_dict(g) for g in gaps_data]
        return cp


@dataclass
class SessionState:
    """Persistent state for the CQS improvement loop.

    Written after every batch validation. Enables crash recovery
    and cross-session learning.
    """
    session_id: str                           # e.g. "2026-03-20-overnight"
    phase: str                                # "measure" | "diagnose" | "fix" | "validate" | "record" | "finished"
    baseline_cqs: float                       # CQS at session start
    current_cqs: float                        # Best CQS achieved so far
    baseline_commit: str                      # Git commit hash at session start
    current_commit: str                       # Git commit hash of last applied batch

    # Progress tracking
    gaps_total: int = 0                       # Total gaps found in diagnosis
    gaps_processed: int = 0                   # Gaps attempted so far
    gaps_remaining_tier1: int = 0             # Tier 1A/1B gaps left
    gaps_remaining_tier2: int = 0             # Tier 2+ gaps (for human report)

    # Experiment counts
    experiments_total: int = 0
    experiments_kept: int = 0
    experiments_discarded: int = 0
    experiments_vetoed: int = 0

    # Batch tracking
    current_batch: List[str] = field(default_factory=list)  # change_ids in current batch
    batches_completed: int = 0

    # Safety
    consecutive_failures: int = 0             # Circuit breaker counter
    regressions_found: int = 0
    worst_company: str = ""                   # Ticker of lowest-CQS company
    worst_company_cqs: float = 0.0

    # Timing
    started_at: str = ""                      # ISO timestamp
    last_update: str = ""
    elapsed_seconds: float = 0.0

    # Next session guidance
    next_session_focus: str = ""              # Human-readable recommendation

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'SessionState':
        # Filter to only known fields to handle forward/backward compat
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


SESSION_STATE_DIR = Path(__file__).parent.parent / "company_mappings"
SESSION_STATE_FILE = SESSION_STATE_DIR / "session_state.json"


def write_session_state(state: SessionState) -> None:
    """Atomic write session state. Same pattern as write_checkpoint."""
    SESSION_STATE_DIR.mkdir(parents=True, exist_ok=True)
    state.last_update = datetime.now().isoformat()

    fd, tmp_path = tempfile.mkstemp(
        dir=str(SESSION_STATE_DIR), suffix=".tmp", prefix="session_state_"
    )
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(state.to_dict(), f, indent=2)
        os.replace(tmp_path, str(SESSION_STATE_FILE))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def read_session_state() -> Optional[SessionState]:
    """Read session state. Returns None if no session file exists."""
    if not SESSION_STATE_FILE.exists():
        return None
    try:
        with open(SESSION_STATE_FILE, 'r') as f:
            data = json.load(f)
        return SessionState.from_dict(data)
    except Exception as e:
        logger.warning(f"Failed to read session state: {e}")
        return None


def clear_session_state() -> None:
    """Remove session state file (session completed cleanly)."""
    try:
        SESSION_STATE_FILE.unlink(missing_ok=True)
    except OSError as e:
        logger.warning(f"Failed to remove session state file: {e}")


def recover_session() -> Optional[SessionState]:
    """Check for crashed session and return recovery state.

    Recovery protocol:
    1. Read session_state.json
    2. If phase != "finished", session crashed — return state to resume from
    3. If phase == "finished", session completed — return None
    """
    state = read_session_state()
    if state is None:
        return None

    if state.phase == "finished":
        logger.info(f"Session {state.session_id} completed normally (CQS {state.current_cqs:.4f})")
        return None

    logger.warning(
        f"Crashed session detected: {state.session_id} "
        f"phase={state.phase}, processed={state.gaps_processed}/{state.gaps_total}, "
        f"CQS {state.baseline_cqs:.4f} -> {state.current_cqs:.4f}"
    )
    return state


def write_checkpoint(cp: WorkerCheckpoint) -> None:
    """Atomic write checkpoint to checkpoints/worker_{id}.json."""
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    cp.last_update = datetime.now().isoformat()

    target = CHECKPOINTS_DIR / f"{cp.worker_id}.json"

    # Atomic write: write to temp file then rename
    fd, tmp_path = tempfile.mkstemp(
        dir=str(CHECKPOINTS_DIR), suffix=".tmp", prefix=f"{cp.worker_id}_"
    )
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(cp.to_dict(), f, indent=2)
        os.replace(tmp_path, str(target))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def read_all_checkpoints() -> List[WorkerCheckpoint]:
    """Read all worker checkpoint files."""
    if not CHECKPOINTS_DIR.exists():
        return []

    checkpoints = []
    for path in sorted(CHECKPOINTS_DIR.glob("worker_*.json")):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            checkpoints.append(WorkerCheckpoint.from_dict(data))
        except Exception as e:
            logger.warning(f"Failed to read checkpoint {path}: {e}")

    return checkpoints


def print_team_dashboard() -> None:
    """Print formatted dashboard of all worker status for the team lead."""
    checkpoints = read_all_checkpoints()

    if not checkpoints:
        print("No active workers found.")
        return

    print("\n" + "=" * 90)
    print("AGENT TEAM DASHBOARD")
    print("=" * 90)

    # Header
    print(f"{'Worker':<12} {'Role':<10} {'Phase':<12} {'Cohort':>6} "
          f"{'Gaps':>5} {'K/D/V':>9} {'CQS':>8} {'Elapsed':>8} {'Current Gap':<20}")
    print("-" * 90)

    total_keeps = 0
    total_discards = 0
    total_vetoes = 0

    for cp in checkpoints:
        kdv = f"{cp.keeps}/{cp.discards}/{cp.vetoes}"
        elapsed = f"{cp.elapsed_seconds:.0f}s" if cp.elapsed_seconds < 3600 else f"{cp.elapsed_seconds/3600:.1f}h"
        current = cp.current_gap or ""
        if len(current) > 20:
            current = current[:17] + "..."

        print(f"{cp.worker_id:<12} {cp.role:<10} {cp.phase:<12} {cp.cohort_size:>6} "
              f"{cp.gaps_found:>5} {kdv:>9} {cp.current_cqs:>8.4f} {elapsed:>8} {current:<20}")

        total_keeps += cp.keeps
        total_discards += cp.discards
        total_vetoes += cp.vetoes

    print("-" * 90)
    total_proposals = total_keeps + total_discards + total_vetoes
    print(f"{'TOTAL':<12} {'':<10} {'':<12} {sum(cp.cohort_size for cp in checkpoints):>6} "
          f"{sum(cp.gaps_found for cp in checkpoints):>5} "
          f"{total_keeps}/{total_discards}/{total_vetoes}{'':>0} "
          f"{'':>8} {'':>8}")

    # Summary
    finished = sum(1 for cp in checkpoints if cp.phase == "finished")
    active = len(checkpoints) - finished
    print(f"\nWorkers: {len(checkpoints)} total, {active} active, {finished} finished")
    if total_proposals > 0:
        print(f"Proposals: {total_proposals} evaluated, {total_keeps} kept ({total_keeps/total_proposals:.0%} keep rate)")

    # Gap summary (if any checkpoints have gap data)
    all_gaps = [g for cp in checkpoints for g in cp.gaps]
    if all_gaps:
        print(f"\nGAPS: {len(all_gaps)} total")
        by_decision = {}
        for g in all_gaps:
            d = g.decision or "pending"
            by_decision.setdefault(d, []).append(g)
        for decision in ["KEEP", "DISCARD", "VETO", "pending"]:
            if decision in by_decision:
                count = len(by_decision[decision])
                label = decision.upper() if decision != "pending" else "PENDING"
                print(f"  {label}: {count}")
                for g in by_decision[decision][:5]:  # Show first 5
                    var = f" variance={g.current_variance:.0f}%" if g.current_variance else ""
                    ref = f" yf={g.reference_value/1e9:.1f}B" if g.reference_value else ""
                    print(f"    {g.ticker}:{g.metric} ({g.gap_type}){ref}{var}")
                if count > 5:
                    print(f"    ... and {count - 5} more")
    print()


def cleanup_checkpoints() -> None:
    """Remove checkpoint files after session ends."""
    if not CHECKPOINTS_DIR.exists():
        return

    count = 0
    for path in CHECKPOINTS_DIR.glob("worker_*.json"):
        try:
            path.unlink()
            count += 1
        except OSError as e:
            logger.warning(f"Failed to remove checkpoint {path}: {e}")

    if count > 0:
        logger.info(f"Cleaned up {count} checkpoint files")
