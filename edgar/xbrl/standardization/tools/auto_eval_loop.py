"""
Auto-Eval Loop: Deterministic experiment infrastructure for config changes.

This is the mechanical experiment loop — safely modify YAML configs, measure CQS,
and rollback on failure. No AI here; just the infrastructure for the agentic engine
(Phase 3) to use.

Key invariants:
1. Only Tier 1 config files are modified (metrics.yaml, companies.yaml, industry_metrics.yaml)
2. All changes are git-recoverable
3. Regressions are a hard veto
4. No single company pass_rate drops >5 percentage points
5. Graveyard prevents re-attempting failed approaches (>=3 failures = skip)
6. Circuit breaker: 10 consecutive failures stops the session
"""

import fcntl
import hashlib
import json
import logging
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

from edgar.xbrl.standardization.ledger.schema import (
    AutoEvalExperiment,
    AutoEvalGraveyard,
    ExperimentLedger,
)
from edgar.xbrl.standardization.tools.auto_eval import (
    CQSResult,
    MetricGap,
    compute_cqs,
    compute_cqs_incremental,
    compute_cqs_incremental_batch,
    is_change_company_scoped,
    identify_gaps,
    derive_gaps_from_cqs,
    _get_graveyard_counts,
    generate_subcohorts,
    QUICK_EVAL_COHORT,
    VALIDATION_COHORT,
    EXPANSION_COHORT_50,
    EXPANSION_COHORT_100,
    EXPANSION_COHORT_500,
    SUB_COHORT_A,
    SUB_COHORT_B,
    SUB_COHORT_C,
)
from edgar.xbrl.standardization.tools.auto_solver import AutoSolver

logger = logging.getLogger(__name__)

# Tier 1 config files — the ONLY files the auto-eval loop may modify
CONFIG_DIR = Path(__file__).parent.parent / "config"
TIER1_CONFIGS = {
    "metrics.yaml": CONFIG_DIR / "metrics.yaml",
    "companies.yaml": CONFIG_DIR / "companies.yaml",
    "industry_metrics.yaml": CONFIG_DIR / "industry_metrics.yaml",
}


# =============================================================================
# DATA MODELS
# =============================================================================

class ChangeType(str, Enum):
    ADD_CONCEPT = "add_concept"
    ADD_DIVERGENCE = "add_divergence"
    ADD_TREE_HINT = "add_tree_hint"
    ADD_EXCLUSION = "add_exclusion"
    REMOVE_PATTERN = "remove_pattern"
    MODIFY_VALUE = "modify_value"
    ADD_STANDARDIZATION = "add_standardization"     # Write standardization formula to metrics.yaml
    ADD_KNOWN_VARIANCE = "add_known_variance"       # Write explained variance to metrics.yaml
    SET_INDUSTRY = "set_industry"                   # Set industry field in companies.yaml
    ADD_COMPANY_OVERRIDE = "add_company_override"   # Add metric_overrides entry in companies.yaml


class Decision(str, Enum):
    KEEP = "KEEP"
    DISCARD = "DISCARD"
    VETO = "VETO"  # Hard veto due to regression


class AIAgentType(str, Enum):
    """Specialized AI agents for the long-tail gaps."""
    REGRESSION_INVESTIGATOR = "regression_investigator"
    REFERENCE_AUDITOR = "reference_auditor"
    SEMANTIC_MAPPER = "semantic_mapper"
    PATTERN_LEARNER = "pattern_learner"


class AIAgentRouter:
    """
    Routes hard gaps to specialized AI agents.

    Key invariant: AI proposals go through evaluate_experiment() with the
    same CQS gate as deterministic proposals. AI never bypasses the gate.
    """

    MIN_GRAVEYARD_FOR_AI = 3

    def route(self, gap: 'MetricGap') -> Optional[AIAgentType]:
        """Route a single gap to the appropriate AI agent. Returns None if deterministic."""
        if gap.graveyard_count < self.MIN_GRAVEYARD_FOR_AI:
            return None
        if gap.gap_type == "regression":
            return AIAgentType.REGRESSION_INVESTIGATOR
        if gap.hv_subtype == "hv_reference_suspect":
            return AIAgentType.REFERENCE_AUDITOR
        if gap.gap_type in ("validation_failure", "high_variance"):
            return AIAgentType.SEMANTIC_MAPPER
        return None

    def route_cross_company(
        self,
        metric: str,
        failing_tickers: List[str],
        industry: Optional[str] = None,
    ) -> Optional[AIAgentType]:
        """Route a cross-company pattern to Pattern Learner."""
        if len(failing_tickers) >= 3:
            return AIAgentType.PATTERN_LEARNER
        return None


@dataclass
class ConfigChange:
    """Describes a proposed YAML configuration modification."""
    file: str                    # Which config file (key in TIER1_CONFIGS)
    change_type: ChangeType      # What kind of change
    yaml_path: str               # Dot-notation path (e.g., "metrics.Revenue.known_concepts")
    old_value: Any = None        # Before (None if adding new)
    new_value: Any = None        # After
    rationale: str = ""          # Why this change is proposed
    target_metric: str = ""      # Which metric gap this addresses
    target_companies: str = ""   # Comma-separated tickers affected
    source: str = "deterministic"   # "deterministic" | "ai_agent"
    ai_agent_type: str = ""         # Which AI agent generated this (if any)

    @property
    def config_file_path(self) -> Path:
        if self.file not in TIER1_CONFIGS:
            raise ValueError(f"Not a Tier 1 config: {self.file}")
        return TIER1_CONFIGS[self.file]

    @property
    def change_id(self) -> str:
        """Deterministic ID for deduplication."""
        content = f"{self.file}:{self.yaml_path}:{self.change_type}:{self.new_value}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def to_diff_string(self) -> str:
        """Human-readable diff."""
        return (
            f"[{self.change_type.value}] {self.file}:{self.yaml_path}\n"
            f"  old: {self.old_value}\n"
            f"  new: {self.new_value}\n"
            f"  reason: {self.rationale}"
        )


@dataclass
class ExperimentDecision:
    """Result of evaluating a single experiment."""
    decision: Decision
    cqs_before: float
    cqs_after: float
    reason: str
    company_deltas: Dict[str, float] = field(default_factory=dict)
    duration_seconds: float = 0.0
    new_cqs_result: Optional[CQSResult] = field(default=None, repr=False)

    @property
    def cqs_delta(self) -> float:
        return self.cqs_after - self.cqs_before


@dataclass
class RegressionDiagnosis:
    """
    Provenance diff for a regressed golden master.

    Compares the golden master's original extraction context against
    the current extraction to identify what changed.
    """
    ticker: str
    metric: str
    golden_concept: Optional[str] = None
    current_concept: Optional[str] = None
    golden_value: Optional[float] = None
    current_value: Optional[float] = None
    reference_value: Optional[float] = None
    golden_reference_value: Optional[float] = None
    diagnosis_type: str = "unknown"
    # Types: "concept_changed", "reference_changed", "value_drifted",
    #        "period_changed", "filing_changed", "unknown"
    notes: str = ""

    @property
    def has_actionable_fix(self) -> bool:
        """Whether this diagnosis suggests an automated fix."""
        return self.diagnosis_type in (
            "concept_changed",
            "reference_changed",
            "value_drifted",
        )


@dataclass
class OvernightReport:
    """Summary of an overnight auto-eval session."""
    session_id: str
    started_at: str
    finished_at: str
    duration_hours: float
    focus_area: Optional[str]

    # Experiment counts
    experiments_total: int = 0
    experiments_kept: int = 0
    experiments_discarded: int = 0
    experiments_vetoed: int = 0

    # CQS trajectory
    cqs_start: float = 0.0
    cqs_end: float = 0.0
    cqs_peak: float = 0.0

    # Circuit breaker
    stopped_early: bool = False
    stop_reason: str = ""

    # Two-score architecture
    ef_cqs_start: float = 0.0
    ef_cqs_end: float = 0.0
    sa_cqs_start: float = 0.0
    sa_cqs_end: float = 0.0
    solver_proposals: int = 0
    solver_kept: int = 0

    # Config changes committed
    config_diffs: List[str] = field(default_factory=list)

    # GPT escalation counters
    gpt_consultations: int = 0       # How many times GPT was consulted
    gpt_proposals_kept: int = 0      # How many GPT proposals survived CQS eval

    @property
    def cqs_improvement(self) -> float:
        return self.cqs_end - self.cqs_start


# =============================================================================
# SUBTYPE FAILURE TRACKING (GPT Escalation)
# =============================================================================

class _SubtypeFailureTracker:
    """Track per-gap subtype failures within a session to trigger GPT escalation.

    Lightweight in-session counter (not persisted — resets each overnight session).
    Tracks how many times each (ticker, metric, hv_subtype) combination has been
    tried without improvement, including both graveyard entries AND null-proposal events.
    """

    def __init__(self, escalation_threshold: int = 3):
        self.threshold = escalation_threshold
        self._counts: Dict[str, int] = {}  # key = "TICKER:metric:subtype"

    def record_failure(self, ticker: str, metric: str, hv_subtype: Optional[str]) -> None:
        key = f"{ticker}:{metric}:{hv_subtype or 'none'}"
        self._counts[key] = self._counts.get(key, 0) + 1

    def should_escalate(self, ticker: str, metric: str, hv_subtype: Optional[str]) -> bool:
        key = f"{ticker}:{metric}:{hv_subtype or 'none'}"
        return self._counts.get(key, 0) >= self.threshold

    def get_count(self, ticker: str, metric: str, hv_subtype: Optional[str]) -> int:
        key = f"{ticker}:{metric}:{hv_subtype or 'none'}"
        return self._counts.get(key, 0)


class ProposalCache:
    """
    In-session cache to prevent re-proposing identical changes.

    Tracks (ticker, metric, proposal_key) tuples. Resets each session.
    This avoids wasting evaluation time on proposals that were already
    rejected in the current session.
    """

    def __init__(self):
        self._tried: set = set()

    def was_tried(self, ticker: str, metric: str, proposal_key: str) -> bool:
        return (ticker, metric, proposal_key) in self._tried

    def record(self, ticker: str, metric: str, proposal_key: str):
        self._tried.add((ticker, metric, proposal_key))

    def proposal_key_for(self, change: 'ConfigChange') -> str:
        """Generate a dedup key from a ConfigChange."""
        return f"{change.change_type.value}:{change.new_value}"


# =============================================================================
# CONFIG MANIPULATION
# =============================================================================

class ConfigLock:
    """File-based lock for serializing config writes.

    Defense-in-depth: the multi-agent protocol already ensures only the
    coordinator writes configs, but this lock guards against accidental
    concurrent writes within a single process or from multiple coordinators.
    """
    LOCK_FILE = CONFIG_DIR / ".config.lock"

    def __enter__(self):
        self._fd = open(self.LOCK_FILE, 'w')
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *args):
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        self._fd.close()


def apply_config_change(change: ConfigChange) -> None:
    """
    Apply a YAML configuration change.

    Reads the config file, navigates to the yaml_path, applies the change,
    and writes back. The change is immediately visible to the next
    Orchestrator run.

    Before modifying, saves a snapshot of the file content so that
    revert_config_change() can restore to the pre-change state (preserving
    any previously KEPT changes) instead of reverting to git HEAD.

    Raises:
        ValueError: If the config file or path is invalid.
        FileNotFoundError: If the config file doesn't exist.
    """
    path = change.config_file_path
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with ConfigLock():
        # Save pre-change snapshot for surgical revert
        with open(path, 'r') as f:
            pre_change_content = f.read()
        change._pre_change_snapshot = pre_change_content

        config = yaml.safe_load(pre_change_content)

        # Navigate to parent of target path
        # For ADD_COMPANY_OVERRIDE and ADD_DIVERGENCE, auto-create missing intermediate dicts
        # (e.g., companies.CME.metric_overrides may not exist yet)
        AUTO_CREATE_TYPES = {ChangeType.ADD_COMPANY_OVERRIDE, ChangeType.ADD_DIVERGENCE}
        keys = change.yaml_path.split('.')
        parent = config
        for key in keys[:-1]:
            if isinstance(parent, dict) and key in parent:
                parent = parent[key]
            elif change.change_type in AUTO_CREATE_TYPES and isinstance(parent, dict):
                parent[key] = {}
                parent = parent[key]
            else:
                raise ValueError(f"Path not found: {change.yaml_path} (missing key: {key})")

        target_key = keys[-1]

        # Apply change based on type
        if change.change_type == ChangeType.ADD_CONCEPT:
            # Add to a list (e.g., known_concepts)
            if target_key not in parent:
                parent[target_key] = []
            if isinstance(parent[target_key], list):
                if change.new_value not in parent[target_key]:
                    parent[target_key].append(change.new_value)
            else:
                raise ValueError(f"Expected list at {change.yaml_path}, got {type(parent[target_key])}")

        elif change.change_type == ChangeType.ADD_EXCLUSION:
            # Add to exclude_metrics list
            if target_key not in parent:
                parent[target_key] = []
            if isinstance(parent[target_key], list):
                if change.new_value not in parent[target_key]:
                    parent[target_key].append(change.new_value)
            else:
                raise ValueError(f"Expected list at {change.yaml_path}")

        elif change.change_type == ChangeType.ADD_DIVERGENCE:
            # Add a known_divergences entry (dict)
            if target_key not in parent:
                parent[target_key] = {}
            if isinstance(change.new_value, dict):
                parent[target_key].update(change.new_value)
            else:
                parent[target_key] = change.new_value

        elif change.change_type == ChangeType.ADD_TREE_HINT:
            # Add or update tree_hints
            if target_key not in parent:
                parent[target_key] = {}
            if isinstance(change.new_value, dict):
                parent[target_key].update(change.new_value)
            else:
                parent[target_key] = change.new_value

        elif change.change_type == ChangeType.REMOVE_PATTERN:
            # Remove from a list
            if target_key in parent and isinstance(parent[target_key], list):
                if change.old_value in parent[target_key]:
                    parent[target_key].remove(change.old_value)

        elif change.change_type == ChangeType.MODIFY_VALUE:
            # Direct value replacement
            parent[target_key] = change.new_value

        elif change.change_type == ChangeType.ADD_STANDARDIZATION:
            # Write a standardization formula to metrics.yaml
            # new_value = {"scope": "default"|"company:TICKER"|"sector:NAME", "components": [...], "notes": "..."}
            if target_key not in parent:
                parent[target_key] = {}
            std_config = parent[target_key]
            scope = change.new_value.get("scope", "default") if isinstance(change.new_value, dict) else "default"
            components = change.new_value.get("components", []) if isinstance(change.new_value, dict) else []
            notes = change.new_value.get("notes", "") if isinstance(change.new_value, dict) else ""

            if scope == "default":
                std_config["default"] = {"components": components}
                if notes:
                    std_config["default"]["notes"] = notes
            elif scope.startswith("company:"):
                ticker_key = scope.split(":", 1)[1]
                if "company_overrides" not in std_config:
                    std_config["company_overrides"] = {}
                std_config["company_overrides"][ticker_key] = {"components": components}
                if notes:
                    std_config["company_overrides"][ticker_key]["notes"] = notes
            elif scope.startswith("sector:"):
                sector_key = scope.split(":", 1)[1]
                if "sector_overrides" not in std_config:
                    std_config["sector_overrides"] = {}
                std_config["sector_overrides"][sector_key] = {"components": components}
                if notes:
                    std_config["sector_overrides"][sector_key]["notes"] = notes

        elif change.change_type == ChangeType.ADD_KNOWN_VARIANCE:
            # Write an explained variance entry to metrics.yaml
            # new_value = {"ticker": "ABBV", "status": "formula_added", "variance_pct": 2.3, "reason": "..."}
            if target_key not in parent:
                parent[target_key] = {}
            kv_config = parent[target_key]
            kv_data = change.new_value if isinstance(change.new_value, dict) else {}
            ticker_key = kv_data.get("ticker", "")
            if ticker_key:
                kv_config[ticker_key] = {
                    "status": kv_data.get("status", "formula_added"),
                    "variance_pct": kv_data.get("variance_pct", 0),
                    "reason": kv_data.get("reason", "Auto-solver discovered formula"),
                }

        elif change.change_type == ChangeType.SET_INDUSTRY:
            # Set industry field on a company in companies.yaml
            # yaml_path should be "companies.{ticker}.industry"
            if target_key not in parent or parent[target_key] is None:
                parent[target_key] = change.new_value
            else:
                # Don't overwrite existing industry
                parent[target_key] = change.new_value

        elif change.change_type == ChangeType.ADD_COMPANY_OVERRIDE:
            # Add a metric_overrides entry in companies.yaml
            # yaml_path = "companies.{ticker}.metric_overrides"
            # new_value = {"MetricName": {"preferred_concept": "...", "notes": "..."}}
            if target_key not in parent:
                parent[target_key] = {}
            if isinstance(change.new_value, dict):
                parent[target_key].update(change.new_value)
            else:
                parent[target_key] = change.new_value

        else:
            raise ValueError(f"Unknown change type: {change.change_type}")

        # Write back
        with open(path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # Invalidate the config cache so the next Orchestrator/Validator sees the new YAML
    from edgar.xbrl.standardization.config_loader import get_config
    get_config(reload=True)

    logger.info(f"Applied config change: {change.to_diff_string()}")


def revert_config_change(change: ConfigChange) -> None:
    """
    Revert a config change by restoring the pre-change snapshot.

    Uses the snapshot saved by apply_config_change() to restore the file
    to its state before THIS change, preserving any previously KEPT changes.
    Falls back to git checkout HEAD if no snapshot is available.
    """
    path = change.config_file_path
    snapshot = getattr(change, '_pre_change_snapshot', None)

    if snapshot is not None:
        # Surgical revert: restore to pre-change state (preserves prior KEEPs)
        with ConfigLock():
            with open(path, 'w') as f:
                f.write(snapshot)
        from edgar.xbrl.standardization.config_loader import get_config
        get_config(reload=True)
        logger.info(f"Reverted {change.file} to pre-change snapshot (preserving prior KEEPs)")
    else:
        # Fallback: git checkout HEAD (only used if snapshot wasn't saved)
        logger.warning(f"No snapshot for {change.file}, falling back to git checkout HEAD")
        try:
            subprocess.run(
                ["git", "checkout", "HEAD", "--", str(path)],
                cwd=str(path.parent),
                check=True,
                capture_output=True,
            )
            from edgar.xbrl.standardization.config_loader import get_config
            get_config(reload=True)
            logger.info(f"Reverted {change.file} to HEAD")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to revert {change.file}: {e.stderr.decode()}")
            raise


def revert_all_configs() -> None:
    """Revert ALL Tier 1 config files to git HEAD state."""
    for name, path in TIER1_CONFIGS.items():
        try:
            subprocess.run(
                ["git", "checkout", "HEAD", "--", str(path)],
                cwd=str(path.parent),
                check=True,
                capture_output=True,
            )
            logger.info(f"Reverted {name}")
        except subprocess.CalledProcessError:
            pass  # File may not be modified
    # Invalidate config cache after reverting all configs
    from edgar.xbrl.standardization.config_loader import get_config
    get_config(reload=True)


# =============================================================================
# IN-MEMORY CONFIG MUTATION (for parallel eval)
# =============================================================================

def apply_change_to_config(change: ConfigChange, config) -> 'MappingConfig':
    """
    Apply a config change to an in-memory MappingConfig. Returns a new copy.

    This is the in-memory equivalent of apply_config_change(). It operates on
    a MappingConfig deepcopy instead of YAML files on disk, enabling parallel
    evaluation without file locks or disk I/O.

    Args:
        change: The config change to apply.
        config: The baseline MappingConfig to mutate (not modified in place).

    Returns:
        A new MappingConfig with the change applied.
    """
    import copy
    new_config = copy.deepcopy(config)

    if change.change_type == ChangeType.ADD_CONCEPT:
        metric = new_config.metrics.get(change.target_metric)
        if metric and change.new_value not in metric.known_concepts:
            metric.known_concepts.append(change.new_value)

    elif change.change_type == ChangeType.ADD_EXCLUSION:
        company = new_config.companies.get(change.target_companies)
        if company and change.new_value not in company.exclude_metrics:
            company.exclude_metrics.append(change.new_value)

    elif change.change_type == ChangeType.ADD_STANDARDIZATION:
        metric = new_config.metrics.get(change.target_metric)
        if metric:
            if metric.standardization is None:
                metric.standardization = {}
            std = metric.standardization
            val = change.new_value if isinstance(change.new_value, dict) else {}
            scope = val.get("scope", "default")
            components = val.get("components", [])
            notes = val.get("notes", "")

            if scope == "default":
                std["default"] = {"components": components}
                if notes:
                    std["default"]["notes"] = notes
            elif scope.startswith("company:"):
                ticker_key = scope.split(":", 1)[1]
                if "company_overrides" not in std:
                    std["company_overrides"] = {}
                std["company_overrides"][ticker_key] = {"components": components}
                if notes:
                    std["company_overrides"][ticker_key]["notes"] = notes
            elif scope.startswith("sector:"):
                sector_key = scope.split(":", 1)[1]
                if "sector_overrides" not in std:
                    std["sector_overrides"] = {}
                std["sector_overrides"][sector_key] = {"components": components}
                if notes:
                    std["sector_overrides"][sector_key]["notes"] = notes

    elif change.change_type == ChangeType.ADD_KNOWN_VARIANCE:
        metric = new_config.metrics.get(change.target_metric)
        if metric:
            if metric.known_variances is None:
                metric.known_variances = {}
            kv_data = change.new_value if isinstance(change.new_value, dict) else {}
            ticker_key = kv_data.get("ticker", "")
            if ticker_key:
                metric.known_variances[ticker_key] = {
                    "status": kv_data.get("status", "formula_added"),
                    "variance_pct": kv_data.get("variance_pct", 0),
                    "reason": kv_data.get("reason", "Auto-solver discovered formula"),
                }

    elif change.change_type == ChangeType.ADD_TREE_HINT:
        metric = new_config.metrics.get(change.target_metric)
        if metric and isinstance(change.new_value, dict):
            metric.tree_hints.update(change.new_value)

    elif change.change_type == ChangeType.SET_INDUSTRY:
        company = new_config.companies.get(change.target_companies)
        if company:
            company.industry = change.new_value

    elif change.change_type == ChangeType.ADD_COMPANY_OVERRIDE:
        company = new_config.companies.get(change.target_companies)
        if company and isinstance(change.new_value, dict):
            company.metric_overrides.update(change.new_value)

    elif change.change_type == ChangeType.ADD_DIVERGENCE:
        company = new_config.companies.get(change.target_companies)
        if company and isinstance(change.new_value, dict):
            company.metric_overrides.update(change.new_value)

    elif change.change_type in (ChangeType.REMOVE_PATTERN, ChangeType.MODIFY_VALUE):
        # These are rare in auto-eval; fall through without mutation
        logger.warning(f"apply_change_to_config: {change.change_type} not supported in-memory")

    return new_config


# =============================================================================
# EXPERIMENT EVALUATION
# =============================================================================

def evaluate_experiment(
    change: ConfigChange,
    baseline_cqs: CQSResult,
    eval_cohort: Optional[List[str]] = None,
    ledger: Optional[ExperimentLedger] = None,
    max_company_drop: float = 5.0,
    max_workers: int = 1,
) -> ExperimentDecision:
    """
    Evaluate a single config change experiment.

    Decision logic:
    - KEEP if CQS improves AND zero regressions AND no company drops >5pp
    - VETO if any regressions detected (hard veto)
    - DISCARD otherwise

    Args:
        change: The config change to evaluate.
        baseline_cqs: CQS before the change was applied.
        eval_cohort: Companies to evaluate on.
        ledger: Ledger for golden master lookups.
        max_company_drop: Maximum allowed per-company pass_rate drop (pp).

    Returns:
        ExperimentDecision with KEEP/DISCARD/VETO and reasoning.
    """
    start_time = time.time()

    if eval_cohort is None:
        eval_cohort = QUICK_EVAL_COHORT

    # Apply the change
    try:
        apply_config_change(change)
    except Exception as e:
        return ExperimentDecision(
            decision=Decision.DISCARD,
            cqs_before=baseline_cqs.cqs,
            cqs_after=baseline_cqs.cqs,
            reason=f"Failed to apply change: {e}",
            duration_seconds=time.time() - start_time,
        )

    # --- FAST PRE-SCREEN for company-scoped changes ---
    # If change targets a single company and cohort is large, check the target
    # company first. If it doesn't improve, skip the expensive full cohort eval.
    target_tickers = [t.strip() for t in change.target_companies.split(",") if t.strip()]
    target_improved = False

    if len(target_tickers) == 1 and eval_cohort and len(eval_cohort) > 5:
        target = target_tickers[0]
        target_baseline = baseline_cqs.company_scores.get(target)
        logger.info(
            f"[PRE-SCREEN] Company-scoped change for {target} "
            f"(metric={change.target_metric}, type={change.change_type.value}), "
            f"evaluating target only before full cohort"
        )

        if target_baseline is not None:
            try:
                target_cqs = compute_cqs(
                    eval_cohort=[target],
                    snapshot_mode=True,
                    use_ai=False,
                    ledger=ledger,
                )
            except Exception as e:
                revert_config_change(change)
                return ExperimentDecision(
                    decision=Decision.DISCARD,
                    cqs_before=baseline_cqs.cqs,
                    cqs_after=baseline_cqs.cqs,
                    reason=f"Pre-screen evaluation error: {e}",
                    duration_seconds=time.time() - start_time,
                )

            target_new = target_cqs.company_scores.get(target)
            if target_new and target_new.cqs <= target_baseline.cqs:
                # Target company didn't improve — skip expensive full eval
                prescreen_duration = time.time() - start_time
                logger.info(
                    f"[PRE-SCREEN REJECT] {target} CQS not improved "
                    f"({target_baseline.cqs:.4f} -> {target_new.cqs:.4f}), "
                    f"skipped full cohort eval (saved ~{len(eval_cohort) * 8}s), "
                    f"pre-screen took {prescreen_duration:.1f}s"
                )
                revert_config_change(change)
                return ExperimentDecision(
                    decision=Decision.DISCARD,
                    cqs_before=target_baseline.cqs,
                    cqs_after=target_new.cqs,
                    reason=f"Fast pre-screen: {target} CQS not improved ({target_baseline.cqs:.4f} -> {target_new.cqs:.4f})",
                    duration_seconds=time.time() - start_time,
                )
            # Target improved — proceed to full eval (Stage 2)
            if target_new and target_new.cqs > target_baseline.cqs:
                target_improved = True
                logger.info(
                    f"Pre-screen PASS: {target} CQS improved "
                    f"{target_baseline.cqs:.4f} -> {target_new.cqs:.4f}, running full eval"
                )

    # Measure CQS after change (full cohort)
    try:
        new_cqs = compute_cqs(
            eval_cohort=eval_cohort,
            snapshot_mode=True,
            use_ai=False,
            baseline_cqs=baseline_cqs.cqs,
            ledger=ledger,
            max_workers=max_workers,
        )
    except Exception as e:
        revert_config_change(change)
        return ExperimentDecision(
            decision=Decision.DISCARD,
            cqs_before=baseline_cqs.cqs,
            cqs_after=baseline_cqs.cqs,
            reason=f"Evaluation error: {e}",
            duration_seconds=time.time() - start_time,
        )

    duration = time.time() - start_time

    # Check for hard veto (NEW regressions only — pre-existing ones don't count)
    new_regressions = new_cqs.total_regressions - baseline_cqs.total_regressions
    if new_regressions > 0:
        revert_config_change(change)
        return ExperimentDecision(
            decision=Decision.VETO,
            cqs_before=baseline_cqs.cqs,
            cqs_after=new_cqs.cqs,
            reason=f"HARD VETO: {new_regressions} new regression(s) detected (was {baseline_cqs.total_regressions}, now {new_cqs.total_regressions})",
            duration_seconds=duration,
        )

    # Check per-company drops
    company_deltas: Dict[str, float] = {}
    for ticker, new_score in new_cqs.company_scores.items():
        old_score = baseline_cqs.company_scores.get(ticker)
        if old_score:
            delta_pp = (new_score.pass_rate - old_score.pass_rate) * 100
            company_deltas[ticker] = delta_pp
            if delta_pp < -max_company_drop:
                revert_config_change(change)
                return ExperimentDecision(
                    decision=Decision.DISCARD,
                    cqs_before=baseline_cqs.cqs,
                    cqs_after=new_cqs.cqs,
                    reason=f"Company {ticker} dropped {delta_pp:.1f}pp (limit: {max_company_drop}pp)",
                    company_deltas=company_deltas,
                    duration_seconds=duration,
                )

    # Check for CQS improvement
    if target_improved:
        # Company-scoped change where target improved: only require non-regression globally
        # (rounding tolerance of 0.0001 to handle floating point noise)
        logger.info(
            f"[RELAXED GATE] Target {target_tickers[0]} improved, "
            f"using non-regression gate: global CQS {baseline_cqs.cqs:.4f} -> {new_cqs.cqs:.4f} "
            f"(threshold: >= {baseline_cqs.cqs - 0.0001:.4f})"
        )
        if new_cqs.cqs < baseline_cqs.cqs - 0.0001:
            revert_config_change(change)
            return ExperimentDecision(
                decision=Decision.DISCARD,
                cqs_before=baseline_cqs.cqs,
                cqs_after=new_cqs.cqs,
                reason=f"Global regression despite target improvement ({baseline_cqs.cqs:.4f} -> {new_cqs.cqs:.4f})",
                company_deltas=company_deltas,
                duration_seconds=duration,
            )
    else:
        # Non-company-scoped changes still require strict improvement
        if new_cqs.cqs <= baseline_cqs.cqs:
            revert_config_change(change)
            return ExperimentDecision(
                decision=Decision.DISCARD,
                cqs_before=baseline_cqs.cqs,
                cqs_after=new_cqs.cqs,
                reason=f"No CQS improvement ({baseline_cqs.cqs:.4f} -> {new_cqs.cqs:.4f})",
                company_deltas=company_deltas,
                duration_seconds=duration,
            )

    # SUCCESS — CQS improved (or non-regressing for company-scoped), no regressions, no company drops
    # Note: we do NOT revert — the change stays applied
    delta = new_cqs.cqs - baseline_cqs.cqs
    if target_improved and delta <= 0:
        reason = f"Target company improved, global CQS non-regressing ({baseline_cqs.cqs:.4f} -> {new_cqs.cqs:.4f})"
        logger.info(
            f"[RELAXED GATE KEEP] Company-scoped change KEPT via relaxed gate: "
            f"metric={change.target_metric}, target={target_tickers[0]}, "
            f"global delta={delta:+.4f}, duration={duration:.1f}s"
        )
    else:
        reason = f"CQS improved by {delta:.4f}"
    return ExperimentDecision(
        decision=Decision.KEEP,
        cqs_before=baseline_cqs.cqs,
        cqs_after=new_cqs.cqs,
        reason=reason,
        company_deltas=company_deltas,
        duration_seconds=duration,
        new_cqs_result=new_cqs,
    )


# =============================================================================
# IN-MEMORY EXPERIMENT EVALUATION (for parallel eval)
# =============================================================================

def evaluate_experiment_in_memory(
    change: ConfigChange,
    baseline_cqs: CQSResult,
    baseline_config,
    eval_cohort: Optional[List[str]] = None,
    ledger: Optional[ExperimentLedger] = None,
    max_company_drop: float = 5.0,
) -> ExperimentDecision:
    """
    Evaluate a config change using in-memory config. No disk writes, no locks.

    Same decision logic as evaluate_experiment() but uses apply_change_to_config()
    instead of apply_config_change()/revert_config_change(). No ConfigLock needed,
    no revert needed — the baseline_config is never modified.

    Args:
        change: The config change to evaluate.
        baseline_cqs: CQS before the change.
        baseline_config: The in-memory MappingConfig to apply the change to.
        eval_cohort: Companies to evaluate on.
        ledger: Ledger for golden master lookups.
        max_company_drop: Maximum allowed per-company pass_rate drop (pp).

    Returns:
        ExperimentDecision with KEEP/DISCARD/VETO and reasoning.
    """
    start_time = time.time()

    if eval_cohort is None:
        eval_cohort = QUICK_EVAL_COHORT

    # Apply change in memory (returns new config, baseline_config untouched)
    try:
        modified_config = apply_change_to_config(change, baseline_config)
    except Exception as e:
        return ExperimentDecision(
            decision=Decision.DISCARD,
            cqs_before=baseline_cqs.cqs,
            cqs_after=baseline_cqs.cqs,
            reason=f"Failed to apply change in memory: {e}",
            duration_seconds=time.time() - start_time,
        )

    # --- FAST PRE-SCREEN for company-scoped changes ---
    target_tickers = [t.strip() for t in change.target_companies.split(",") if t.strip()]
    target_improved = False

    if len(target_tickers) == 1 and eval_cohort and len(eval_cohort) > 5:
        target = target_tickers[0]
        target_baseline = baseline_cqs.company_scores.get(target)

        if target_baseline is not None:
            try:
                target_cqs = compute_cqs(
                    eval_cohort=[target],
                    snapshot_mode=True,
                    use_ai=False,
                    ledger=ledger,
                    config=modified_config,
                )
            except Exception as e:
                return ExperimentDecision(
                    decision=Decision.DISCARD,
                    cqs_before=baseline_cqs.cqs,
                    cqs_after=baseline_cqs.cqs,
                    reason=f"In-memory pre-screen error: {e}",
                    duration_seconds=time.time() - start_time,
                )

            target_new = target_cqs.company_scores.get(target)
            if target_new and target_new.cqs <= target_baseline.cqs:
                return ExperimentDecision(
                    decision=Decision.DISCARD,
                    cqs_before=target_baseline.cqs,
                    cqs_after=target_new.cqs,
                    reason=f"In-memory pre-screen: {target} CQS not improved ({target_baseline.cqs:.4f} -> {target_new.cqs:.4f})",
                    duration_seconds=time.time() - start_time,
                )
            if target_new and target_new.cqs > target_baseline.cqs:
                target_improved = True

    # Full cohort eval — use incremental CQS for company-scoped changes (Phase 2a)
    try:
        if is_change_company_scoped(change) and baseline_cqs.company_scores:
            new_cqs = compute_cqs_incremental(
                baseline_result=baseline_cqs,
                change=change,
                config=modified_config,
                eval_cohort=eval_cohort,
                ledger=ledger,
            )
        else:
            new_cqs = compute_cqs(
                eval_cohort=eval_cohort,
                snapshot_mode=True,
                use_ai=False,
                baseline_cqs=baseline_cqs.cqs,
                ledger=ledger,
                config=modified_config,
            )
    except Exception as e:
        return ExperimentDecision(
            decision=Decision.DISCARD,
            cqs_before=baseline_cqs.cqs,
            cqs_after=baseline_cqs.cqs,
            reason=f"In-memory evaluation error: {e}",
            duration_seconds=time.time() - start_time,
        )

    duration = time.time() - start_time

    # Check for hard veto (NEW regressions only — pre-existing ones don't count)
    new_regressions = new_cqs.total_regressions - baseline_cqs.total_regressions
    if new_regressions > 0:
        return ExperimentDecision(
            decision=Decision.VETO,
            cqs_before=baseline_cqs.cqs,
            cqs_after=new_cqs.cqs,
            reason=f"HARD VETO: {new_regressions} new regression(s) detected (was {baseline_cqs.total_regressions}, now {new_cqs.total_regressions})",
            duration_seconds=duration,
        )

    # Check per-company drops
    company_deltas: Dict[str, float] = {}
    for ticker, new_score in new_cqs.company_scores.items():
        old_score = baseline_cqs.company_scores.get(ticker)
        if old_score:
            delta_pp = (new_score.pass_rate - old_score.pass_rate) * 100
            company_deltas[ticker] = delta_pp
            if delta_pp < -max_company_drop:
                return ExperimentDecision(
                    decision=Decision.DISCARD,
                    cqs_before=baseline_cqs.cqs,
                    cqs_after=new_cqs.cqs,
                    reason=f"Company {ticker} dropped {delta_pp:.1f}pp (limit: {max_company_drop}pp)",
                    company_deltas=company_deltas,
                    duration_seconds=duration,
                )

    # Check for CQS improvement (same logic as evaluate_experiment)
    if target_improved:
        if new_cqs.cqs < baseline_cqs.cqs - 0.0001:
            return ExperimentDecision(
                decision=Decision.DISCARD,
                cqs_before=baseline_cqs.cqs,
                cqs_after=new_cqs.cqs,
                reason=f"Global regression despite target improvement ({baseline_cqs.cqs:.4f} -> {new_cqs.cqs:.4f})",
                company_deltas=company_deltas,
                duration_seconds=duration,
            )
    else:
        if new_cqs.cqs <= baseline_cqs.cqs:
            return ExperimentDecision(
                decision=Decision.DISCARD,
                cqs_before=baseline_cqs.cqs,
                cqs_after=new_cqs.cqs,
                reason=f"No CQS improvement ({baseline_cqs.cqs:.4f} -> {new_cqs.cqs:.4f})",
                company_deltas=company_deltas,
                duration_seconds=duration,
            )

    # SUCCESS
    delta = new_cqs.cqs - baseline_cqs.cqs
    if target_improved and delta <= 0:
        reason = f"Target company improved, global CQS non-regressing ({baseline_cqs.cqs:.4f} -> {new_cqs.cqs:.4f})"
    else:
        reason = f"CQS improved by {delta:.4f}"

    return ExperimentDecision(
        decision=Decision.KEEP,
        cqs_before=baseline_cqs.cqs,
        cqs_after=new_cqs.cqs,
        reason=reason,
        company_deltas=company_deltas,
        duration_seconds=duration,
        new_cqs_result=new_cqs,
    )


# =============================================================================
# EXPERIMENT LOGGING
# =============================================================================

def log_experiment(
    change: ConfigChange,
    result: ExperimentDecision,
    ledger: ExperimentLedger,
    run_id: str = "",
) -> str:
    """Log an experiment result to the ledger."""
    experiment_id = f"ae_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{change.change_id[:6]}"

    experiment = AutoEvalExperiment(
        experiment_id=experiment_id,
        run_id=run_id or f"session_{datetime.now().strftime('%Y%m%d')}",
        timestamp=datetime.now().isoformat(),
        target_metric=change.target_metric,
        target_companies=change.target_companies,
        change_type=change.change_type.value,
        config_diff=change.to_diff_string(),
        cqs_before=result.cqs_before,
        cqs_after=result.cqs_after,
        decision=result.decision.value,
        duration_seconds=result.duration_seconds,
        rationale=change.rationale,
        notes=result.reason,
    )

    ledger.record_experiment(experiment)

    # Log to graveyard if discarded or vetoed
    if result.decision != Decision.KEEP:
        log_to_graveyard(change, result, ledger)

    return experiment_id


def log_to_graveyard(
    change: ConfigChange,
    result: ExperimentDecision,
    ledger: ExperimentLedger,
) -> str:
    """Log a failed experiment to the graveyard."""
    # Count similar prior failures
    similar = ledger.get_graveyard_count(
        target_metric=change.target_metric,
        target_companies=change.target_companies,
    )

    reason_map = {
        Decision.VETO: "regression",
        Decision.DISCARD: "no_improvement",
    }
    if "dropped" in result.reason.lower():
        discard_reason = "company_drop"
    elif "error" in result.reason.lower():
        discard_reason = "error"
    else:
        discard_reason = reason_map.get(result.decision, "unknown")

    entry = AutoEvalGraveyard(
        experiment_id=f"gy_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{change.change_id[:6]}",
        target_metric=change.target_metric,
        target_companies=change.target_companies,
        discard_reason=discard_reason,
        detail=result.reason,
        similar_attempts=similar + 1,
        config_diff=change.to_diff_string(),
    )

    ledger.record_graveyard(entry)
    return entry.experiment_id


# =============================================================================
# REGRESSION DIAGNOSIS
# =============================================================================

def diagnose_regression(
    ticker: str,
    metric: str,
    current_validation,
    ledger: ExperimentLedger,
) -> RegressionDiagnosis:
    """
    Build a provenance diff for a regressed metric.

    Compares golden master extraction context against current extraction
    to identify what changed. Pure data comparison, no AI.
    """
    golden_ctx = ledger.get_golden_extraction_context(ticker, metric)

    current_concept = None
    current_value = None
    ref_value = None

    if current_validation:
        current_value = getattr(current_validation, 'extracted_value', None) if not isinstance(current_validation, dict) else current_validation.get('extracted_value')
        ref_value = getattr(current_validation, 'reference_value', None) if not isinstance(current_validation, dict) else current_validation.get('reference_value')
        components = getattr(current_validation, 'components_used', None) if not isinstance(current_validation, dict) else current_validation.get('components_used')
        if components:
            current_concept = components[0] if components else None

    if golden_ctx is None:
        return RegressionDiagnosis(
            ticker=ticker, metric=metric,
            current_concept=current_concept,
            current_value=current_value,
            reference_value=ref_value,
            diagnosis_type="unknown",
            notes="No golden extraction context found in ledger",
        )

    golden_concept = golden_ctx.get("concept")
    golden_value = golden_ctx.get("value")
    golden_ref = golden_ctx.get("reference_value")

    # Determine what changed
    diagnosis_type = "unknown"

    # Case 1: Concept selection changed
    if golden_concept and current_concept and golden_concept != current_concept:
        diagnosis_type = "concept_changed"

    # Case 2: Reference value changed (our extraction is stable)
    elif (golden_ref and ref_value and golden_value and current_value
          and abs(golden_value - current_value) / max(abs(golden_value), 1) < 0.05
          and abs(golden_ref - ref_value) / max(abs(golden_ref), 1) > 0.10):
        diagnosis_type = "reference_changed"

    # Case 3: Extracted value drifted (different filing or period)
    elif golden_value and current_value:
        drift_pct = abs(golden_value - current_value) / max(abs(golden_value), 1) * 100
        if drift_pct > 10:
            diagnosis_type = "value_drifted"

    return RegressionDiagnosis(
        ticker=ticker, metric=metric,
        golden_concept=golden_concept,
        current_concept=current_concept,
        golden_value=golden_value,
        current_value=current_value,
        reference_value=ref_value,
        golden_reference_value=golden_ref,
        diagnosis_type=diagnosis_type,
    )


def _propose_regression_fix(
    gap: MetricGap,
    config_dir: Optional[Path] = None,
    ledger: Optional[ExperimentLedger] = None,
) -> Optional[ConfigChange]:
    """
    Propose a fix for a regressed golden master.

    Uses provenance diff to determine the right fix:
    - concept_changed -> revert to golden concept via company_override
    - reference_changed -> add known_divergence
    - value_drifted -> add known_divergence with tolerance
    """
    if ledger is None:
        ledger = ExperimentLedger()
    diag = diagnose_regression(gap.ticker, gap.metric, gap.extraction_evidence, ledger)

    if not diag.has_actionable_fix:
        logger.warning(
            f"Regression {gap.ticker}:{gap.metric} diagnosed as '{diag.diagnosis_type}' "
            f"-- no automated fix available"
        )
        return None

    STRATEGY_NAMES = {"tree", "facts", "composite", "config", "industry", "unknown"}

    if diag.diagnosis_type == "concept_changed" and diag.golden_concept:
        # Don't use strategy names as preferred_concept — they're not XBRL concepts
        if diag.golden_concept in STRATEGY_NAMES:
            logger.warning(
                f"Regression {gap.ticker}:{gap.metric}: golden_concept is strategy name "
                f"'{diag.golden_concept}', not a real XBRL concept — falling through to solver"
            )
            # Try solver with golden value as target if available
            if diag.golden_value is not None and diag.golden_value != 0:
                solver_gap = MetricGap(
                    ticker=gap.ticker, metric=gap.metric,
                    gap_type="regression", estimated_impact=gap.estimated_impact,
                    reference_value=diag.golden_value,
                    graveyard_count=gap.graveyard_count,
                )
                return _propose_via_solver(solver_gap)
            return _propose_via_solver(gap)

        return ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.ADD_COMPANY_OVERRIDE,
            yaml_path=f"companies.{gap.ticker}.metric_overrides.{gap.metric}",
            new_value={
                "preferred_concept": diag.golden_concept,
                "notes": f"Regression fix: reverted from {diag.current_concept} to golden concept",
            },
            rationale=f"Regression: concept changed from {diag.golden_concept} to {diag.current_concept}",
            target_metric=gap.metric,
            target_companies=gap.ticker,
        )

    if diag.diagnosis_type == "reference_changed":
        variance = None
        if diag.current_value and diag.reference_value and diag.reference_value != 0:
            variance = abs(diag.current_value - diag.reference_value) / abs(diag.reference_value) * 100
        return ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.ADD_DIVERGENCE,
            yaml_path=f"companies.{gap.ticker}.known_divergences.{gap.metric}",
            new_value={
                "form_types": ["10-K"],
                "variance_pct": round(variance * 1.5, 1) if variance else 25.0,
                "reason": f"Reference value changed: golden_ref={diag.golden_reference_value}, current_ref={diag.reference_value}",
                "skip_validation": False,
            },
            rationale=f"Regression: yfinance reference changed, extraction stable at {diag.current_value}",
            target_metric=gap.metric,
            target_companies=gap.ticker,
        )

    if diag.diagnosis_type == "value_drifted":
        variance = gap.current_variance or 25.0
        return ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.ADD_DIVERGENCE,
            yaml_path=f"companies.{gap.ticker}.known_divergences.{gap.metric}",
            new_value={
                "form_types": ["10-K"],
                "variance_pct": round(abs(variance) * 1.5, 1),
                "reason": f"Value drifted: golden={diag.golden_value}, current={diag.current_value}",
                "skip_validation": False,
            },
            rationale=f"Regression: extracted value drifted from golden",
            target_metric=gap.metric,
            target_companies=gap.ticker,
        )

    return None


# =============================================================================
# PROPOSAL GENERATION (Phase 3)
# =============================================================================

def propose_change(
    gap: MetricGap,
    graveyard_entries: List[Dict],
    config_dir: Optional[Path] = None,
) -> Optional[ConfigChange]:
    """
    Propose a ConfigChange for a given gap using deterministic heuristics.

    This is the non-AI proposal function — it uses known patterns from
    the config to generate proposals. The agentic engine (auto-eval-runner)
    can override this with AI-based proposals.

    Args:
        gap: The metric gap to address.
        graveyard_entries: Prior failed attempts for this metric.
        config_dir: Override config directory for testing.

    Returns:
        ConfigChange if a proposal can be made, None otherwise.
    """
    if config_dir is None:
        config_dir = CONFIG_DIR

    # Dead-end filtering is handled by identify_gaps() — no redundant check here

    # Check what's already been tried
    tried_concepts = set()
    for entry in graveyard_entries:
        diff = entry.get("config_diff", "")
        if "add_concept" in diff.lower():
            # Extract the concept from the diff
            for line in diff.split("\n"):
                if "new:" in line:
                    tried_concepts.add(line.split("new:")[-1].strip())

    if gap.gap_type == "unmapped":
        return _propose_for_unmapped(gap, tried_concepts, config_dir)
    elif gap.gap_type == "validation_failure":
        # Divergence tolerance never improves CQS for validation failures
        # (the underlying concept is wrong, not slightly off) — go straight to solver
        return _propose_via_solver(gap)
    elif gap.gap_type == "high_variance":
        # Route based on hv_subtype for targeted proposals
        if gap.hv_subtype == "hv_missing_industry":
            change = _propose_industry_assignment(gap)
            if change is not None:
                return change
            # Fall through to solver if industry assignment isn't possible

        if gap.hv_subtype == "hv_missing_component":
            change = _propose_component_fix(gap)
            if change is not None:
                return change
            # Fall through to solver

        if gap.hv_subtype == "hv_sign_inverted":
            change = _propose_sign_negate(gap)
            if change is not None:
                return change
            # Fall through to solver

        # Default: tree_hint first, then solver
        if gap.graveyard_count == 0 and gap.hv_subtype not in ("hv_missing_industry", "hv_missing_component"):
            change = _propose_for_high_variance(gap, config_dir)
            if change is not None:
                return change
        return _propose_via_solver(gap)
    elif gap.gap_type == "explained_variance":
        logger.info(f"Skipping explained variance: {gap.ticker}:{gap.metric}")
        return None
    elif gap.gap_type == "regression":
        return _propose_regression_fix(gap, config_dir)

    return None


def _is_metric_forbidden(metric: str, ticker: str, config_dir: Path) -> bool:
    """Check if metric is forbidden by the company's industry archetype."""
    industry_path = config_dir / "industry_metrics.yaml"
    companies_path = config_dir / "companies.yaml"

    if not industry_path.exists() or not companies_path.exists():
        return False

    with open(companies_path) as f:
        companies = yaml.safe_load(f) or {}
    with open(industry_path) as f:
        industry_config = yaml.safe_load(f) or {}

    company = companies.get("companies", {}).get(ticker, {})
    industry = company.get("industry", "").lower()

    if not industry:
        return False

    archetype = industry_config.get(industry, {})
    forbidden = archetype.get("forbidden_metrics", [])
    return metric in forbidden


def _propose_for_unmapped(
    gap: MetricGap,
    tried_concepts: set,
    config_dir: Path,
) -> Optional[ConfigChange]:
    """Propose a concept addition for an unmapped metric."""
    # Check if metric is forbidden by industry archetype
    if _is_metric_forbidden(gap.metric, gap.ticker, config_dir):
        return ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.ADD_EXCLUSION,
            yaml_path=f"companies.{gap.ticker}.exclude_metrics",
            new_value=gap.metric,
            rationale=f"{gap.metric} is forbidden for {gap.ticker}'s industry archetype",
            target_metric=gap.metric,
            target_companies=gap.ticker,
        )

    # Load metrics config to see what concepts are already known
    metrics_path = config_dir / "metrics.yaml"
    if not metrics_path.exists():
        return None

    with open(metrics_path, 'r') as f:
        metrics_config = yaml.safe_load(f)

    metric_def = metrics_config.get("metrics", {}).get(gap.metric, {})
    known_concepts = metric_def.get("known_concepts", [])

    # If reference value is None, skip — don't exclude the metric.
    # Future validation layers (SEC-native self-validation) may be able to verify it.
    if gap.reference_value is None:
        logger.info(
            f"Skipping {gap.ticker}:{gap.metric} — no reference value available "
            f"(metric remains in pipeline for future validation)"
        )
        return None

    # Try common concept variations not yet in known_concepts
    standard_tag = metric_def.get("standard_tag", gap.metric)
    variations = _generate_concept_variations(standard_tag, gap.metric)

    for concept in variations:
        if concept not in known_concepts and concept not in tried_concepts:
            return ConfigChange(
                file="metrics.yaml",
                change_type=ChangeType.ADD_CONCEPT,
                yaml_path=f"metrics.{gap.metric}.known_concepts",
                new_value=concept,
                rationale=f"Common variation of {standard_tag} not yet in known_concepts",
                target_metric=gap.metric,
                target_companies=gap.ticker,
            )

    # Heuristics exhausted — search the actual filing with discovery tools
    return _propose_via_discovery(gap, known_concepts, tried_concepts)


def _propose_for_validation_failure(
    gap: MetricGap,
    config_dir: Path,
) -> Optional[ConfigChange]:
    """Propose a divergence for a validation failure."""
    if gap.current_variance is None:
        return None

    # For moderate variance, propose a known_divergence
    if abs(gap.current_variance) < 50:
        return ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.ADD_DIVERGENCE,
            yaml_path=f"companies.{gap.ticker}.known_divergences.{gap.metric}",
            new_value={
                "form_types": ["10-K"],
                "variance_pct": round(abs(gap.current_variance) * 1.5, 1),
                "reason": f"Auto-detected variance {gap.current_variance:.1f}%",
                "skip_validation": False,
            },
            rationale=f"Validation failure with {gap.current_variance:.1f}% variance — adding tolerance",
            target_metric=gap.metric,
            target_companies=gap.ticker,
        )

    return None


def _propose_for_high_variance(
    gap: MetricGap,
    config_dir: Path,
) -> Optional[ConfigChange]:
    """Propose a tree_hint adjustment for high variance."""
    if gap.current_variance is None:
        return None

    # Add a tree_hint to guide the tree parser
    return ConfigChange(
        file="metrics.yaml",
        change_type=ChangeType.ADD_TREE_HINT,
        yaml_path=f"metrics.{gap.metric}.tree_hints",
        new_value={"weight": 0.8},
        rationale=f"High variance {gap.current_variance:.1f}% — adjusting tree parser weight",
        target_metric=gap.metric,
        target_companies=gap.ticker,
    )


def _propose_industry_assignment(
    gap: MetricGap,
) -> Optional[ConfigChange]:
    """
    Propose setting the industry field for a company with no industry in companies.yaml.

    Looks up the company's SIC code and maps it to an industry category.
    """
    try:
        from edgar import Company
        from edgar.entity.mappings_loader import get_industry_for_sic

        company = Company(gap.ticker)
        sic = company.data.sic
        if not sic:
            logger.info(f"No SIC code for {gap.ticker} — cannot assign industry")
            return None

        industry = get_industry_for_sic(sic)
        if not industry:
            logger.info(f"SIC {sic} for {gap.ticker} does not map to a known industry")
            return None

        # Check if company already has industry set in config
        companies_path = CONFIG_DIR / "companies.yaml"
        if companies_path.exists():
            with open(companies_path, 'r') as f:
                companies_config = yaml.safe_load(f)
            company_entry = companies_config.get("companies", {}).get(gap.ticker, {})
            if company_entry.get("industry"):
                logger.info(f"{gap.ticker} already has industry={company_entry['industry']}")
                return None

        return ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.SET_INDUSTRY,
            yaml_path=f"companies.{gap.ticker}.industry",
            new_value=industry,
            rationale=f"Company {gap.ticker} has SIC {sic} -> industry '{industry}' (was missing)",
            target_metric=gap.metric,
            target_companies=gap.ticker,
        )

    except Exception as e:
        logger.warning(f"Industry assignment failed for {gap.ticker}: {e}")
        return None


def _propose_sign_negate(gap: MetricGap) -> Optional[ConfigChange]:
    """Propose sign negation for metrics where XBRL and reference have opposite signs.

    When the gap classifier detects hv_sign_inverted (opposite signs but similar magnitudes),
    propose a sign_negate override so the extraction layer negates the value before comparison.
    """
    if gap.hv_subtype != "hv_sign_inverted":
        return None
    if gap.xbrl_value is None or gap.reference_value is None:
        return None
    if gap.reference_value == 0:
        return None
    # Only propose if magnitudes are close (within 20%)
    mag_ratio = abs(gap.xbrl_value) / abs(gap.reference_value)
    if not (0.8 < mag_ratio < 1.2):
        return None

    logger.info(
        f"Sign negate proposal for {gap.ticker}:{gap.metric}: "
        f"XBRL={gap.xbrl_value:.0f}, ref={gap.reference_value:.0f}"
    )
    return ConfigChange(
        file="companies.yaml",
        change_type=ChangeType.ADD_COMPANY_OVERRIDE,
        yaml_path=f"companies.{gap.ticker}.metric_overrides.{gap.metric}",
        new_value={
            "sign_negate": True,
            "notes": f"Sign convention differs from yfinance (XBRL={gap.xbrl_value:.0f}, ref={gap.reference_value:.0f})",
        },
        rationale=f"Sign inverted: XBRL={gap.xbrl_value:.0f}, ref={gap.reference_value:.0f}",
        target_metric=gap.metric,
        target_companies=gap.ticker,
    )


def _propose_component_fix(
    gap: MetricGap,
) -> Optional[ConfigChange]:
    """
    Propose a fix for a composite metric with missing components.

    When a composite metric (like IntangibleAssets = Goodwill + IntangibleAssetsNetExcludingGoodwill)
    has some components found but others missing, search XBRL facts for alternate concepts
    that could fill the missing component.
    """
    evidence = gap.extraction_evidence
    if evidence is None or not evidence.components_missing:
        return None

    if gap.reference_value is None:
        return None

    # Calculate the residual: what value the missing components should sum to
    found_total = evidence.extracted_value or 0.0
    residual = abs(gap.reference_value) - abs(found_total)

    if residual <= 0:
        return None

    # Try to solve for the residual using the auto-solver
    try:
        solver = AutoSolver(snapshot_mode=True, allow_subtraction=True, allow_scale_search=True)
        candidates = solver.solve_metric(
            gap.ticker, gap.metric,
            yfinance_value=residual,
            multi_period=False,  # Skip multi-period for component search
        )

        if not candidates:
            logger.info(
                f"No component fix found for {gap.ticker}:{gap.metric} "
                f"(missing: {evidence.components_missing}, residual=${residual/1e9:.2f}B)"
            )
            return None

        best = candidates[0]

        # Propose adding the discovered concept(s) as known_concepts for the missing component
        missing_component = evidence.components_missing[0]
        new_concept = best.components[0] if len(best.components) == 1 else best.components[0]

        return ConfigChange(
            file="metrics.yaml",
            change_type=ChangeType.ADD_CONCEPT,
            yaml_path=f"metrics.{gap.metric}.known_concepts",
            new_value=new_concept,
            rationale=(
                f"Component fix: {missing_component} missing in composite {gap.metric}. "
                f"Found {new_concept} matching residual ${residual/1e9:.2f}B "
                f"({best.variance_pct:.1f}% variance)"
            ),
            target_metric=gap.metric,
            target_companies=gap.ticker,
        )

    except Exception as e:
        logger.warning(f"Component fix failed for {gap.ticker}:{gap.metric}: {e}")
        return None


def _propose_via_solver(
    gap: MetricGap,
) -> Optional[ConfigChange]:
    """
    Escalate to the Auto-Solver to discover composite formulas.

    When standard proposals (divergence, tree_hint) fail, the solver
    performs a bounded subset-sum search over XBRL facts to find
    combinations that match the yfinance target value.

    Validation gates (both must pass to write ADD_STANDARDIZATION):
    1. Multi-period: formula holds for >=2 of the last 3 annual filings
    2. Cross-company: formula works for >=2 other companies (sector pattern)

    If multi-period passes but cross-company fails → company-specific
    ADD_STANDARDIZATION (company override).
    If multi-period fails → reject (likely coincidental match).
    """
    if gap.reference_value is None:
        logger.warning(f"Solver skipped {gap.ticker}:{gap.metric} — reference_value is None")
        return None

    try:
        solver = AutoSolver(snapshot_mode=True, allow_subtraction=True, allow_scale_search=True)

        # Composite-aware: solve component-by-component when evidence shows composite
        evidence = gap.extraction_evidence
        if (evidence and evidence.resolution_type == "composite"
                and evidence.components_used and evidence.components_missing):
            candidates = solver.solve_composite_metric(
                ticker=gap.ticker,
                metric=gap.metric,
                found_components=evidence.components_used,
                found_total=evidence.extracted_value or 0.0,
                target=abs(gap.reference_value),
            )
        else:
            # Standard solver: search for full target value
            # Use multi_period=True to run inline multi-period validation
            # during the search itself (loads 3 10-K filings upfront,
            # validates each candidate across all periods before yielding).
            candidates = solver.solve_metric(
                gap.ticker, gap.metric,
                yfinance_value=gap.reference_value,
                multi_period=True,
                num_periods=3,
            )

        if not candidates:
            logger.info(f"Solver found no formulas for {gap.ticker}:{gap.metric}")
            return None

        best = candidates[0]
        mp_checked = best.periods_checked
        mp_passed = best.periods_passed
        logger.info(
            f"Solver candidate for {gap.ticker}:{gap.metric}: {best} "
            f"(multi-period: {mp_passed}/{mp_checked}, "
            f"components={len(best.components)}, rank 1/{len(candidates)})"
        )

        # Gate 2: Cross-company validation
        validation_tickers = [t for t in QUICK_EVAL_COHORT if t != gap.ticker][:3]
        validation = solver.validate_formula(best, validation_tickers)

        # Collapse sector vs company-specific into scope + label
        if validation.is_sector_pattern:
            scope = "default"
            scope_label = "sector"
        else:
            scope = f"company:{gap.ticker}"
            scope_label = "company-specific"

        logger.info(
            f"{scope_label.title()} formula for {gap.ticker}:{gap.metric} "
            f"({mp_passed}/{mp_checked} periods, "
            f"{validation.pass_count}/{validation.total_count} cross-co)"
        )

        return ConfigChange(
            file="metrics.yaml",
            change_type=ChangeType.ADD_STANDARDIZATION,
            yaml_path=f"metrics.{gap.metric}.standardization",
            new_value={
                "scope": scope,
                "components": best.components,
                "notes": (
                    f"Auto-solver {scope_label} via {gap.ticker}, "
                    f"{mp_passed}/{mp_checked} periods, "
                    f"{validation.pass_count}/{validation.total_count} companies"
                ),
            },
            rationale=(
                f"Auto-solver: {' + '.join(best.components)} "
                f"({best.variance_pct:.1f}% var, "
                f"{mp_passed}/{mp_checked} periods, {scope_label})"
            ),
            target_metric=gap.metric,
            target_companies=gap.ticker,
        )

    except Exception as e:
        logger.warning(f"Solver failed for {gap.ticker}:{gap.metric}: {e}")
        return None


def _propose_via_discovery(
    gap: MetricGap,
    known_concepts: List[str],
    tried_concepts: set,
    min_periods: int = 2,
) -> Optional[ConfigChange]:
    """
    Search the actual XBRL filing to discover the right concept.

    This is the escalation path when heuristic name variations fail.
    Calls discover_concepts() to search calc trees and facts, then
    verifies the candidate across MULTIPLE fiscal periods to avoid
    false positives from coincidental single-period value matches.

    Args:
        gap: The metric gap to resolve.
        known_concepts: Concepts already in config.
        tried_concepts: Concepts already attempted (from graveyard).
        min_periods: Minimum periods that must match to accept (default 2).
    """
    from edgar.xbrl.standardization.tools.discover_concepts import discover_concepts, strip_prefix
    from edgar.xbrl.standardization.tools.verify_mapping import verify_mapping

    from edgar import Company, set_identity, use_local_storage
    set_identity("Dev Gunning developer-gunning@gmail.com")
    use_local_storage(True)

    try:
        company = Company(gap.ticker)
        filings_10k = list(company.get_filings(form='10-K', amendments=False))[:3]
        if not filings_10k:
            return None
        xbrl = filings_10k[0].xbrl()
    except Exception as e:
        logger.warning(f"Discovery failed for {gap.ticker}: could not load filing: {e}")
        return None

    # Get facts for broader search
    facts_df = None
    try:
        facts = company.get_facts()
        facts_df = facts.to_dataframe()
    except Exception:
        pass  # Facts search is optional — calc tree search alone can work

    # Discover candidates from the most recent filing
    candidates = discover_concepts(
        metric_name=gap.metric,
        xbrl=xbrl,
        facts_df=facts_df,
        ticker=gap.ticker,
        known_concepts=known_concepts,
        top_k=5,
    )

    if not candidates:
        logger.info(f"Discovery found no candidates for {gap.ticker}:{gap.metric}")
        return None

    # Load XBRL for older filings (for multi-period verification)
    older_xbrls = []
    for filing in filings_10k[1:]:
        try:
            older_xbrls.append(filing.xbrl())
        except Exception:
            pass

    # Try each candidate — verify across multiple periods
    for candidate in candidates:
        concept = candidate.concept
        clean_concept = strip_prefix(concept)

        if clean_concept in known_concepts or clean_concept in tried_concepts:
            continue

        # Verify across all available periods
        periods_matched = 0
        periods_checked = 0
        variances = []

        all_xbrls = [xbrl] + older_xbrls
        for period_xbrl in all_xbrls:
            verification = verify_mapping(
                metric=gap.metric,
                concept=concept,
                xbrl=period_xbrl,
                ticker=gap.ticker,
                tolerance_pct=15.0,
            )
            if verification.xbrl_value is not None and verification.reference_value is not None:
                periods_checked += 1
                if verification.is_valid:
                    periods_matched += 1
                    variances.append(verification.variance_pct)

        if periods_checked == 0:
            logger.debug(f"Discovery candidate {clean_concept}: no data in any period")
            continue

        if periods_matched < min(min_periods, periods_checked):
            logger.debug(
                f"Discovery candidate {clean_concept}: only {periods_matched}/{periods_checked} "
                f"periods matched (need {min_periods})"
            )
            continue

        avg_variance = sum(variances) / len(variances) if variances else 0

        logger.info(
            f"Discovery found multi-period verified concept for {gap.ticker}:{gap.metric}: "
            f"{clean_concept} ({periods_matched}/{periods_checked} periods, "
            f"avg variance={avg_variance:.1f}%)"
        )
        return ConfigChange(
            file="metrics.yaml",
            change_type=ChangeType.ADD_CONCEPT,
            yaml_path=f"metrics.{gap.metric}.known_concepts",
            new_value=clean_concept,
            rationale=(
                f"Discovered via {candidate.source} search, verified across "
                f"{periods_matched}/{periods_checked} fiscal periods "
                f"(avg variance={avg_variance:.1f}%, "
                f"confidence={candidate.confidence:.2f}). "
                f"{candidate.reasoning}"
            ),
            target_metric=gap.metric,
            target_companies=gap.ticker,
        )

    logger.info(f"Discovery found candidates but none passed multi-period verification for {gap.ticker}:{gap.metric}")
    return None


def _generate_concept_variations(standard_tag: str, metric_name: str) -> List[str]:
    """Generate common XBRL concept name variations."""
    variations = []
    base = standard_tag or metric_name

    # Common suffixes/prefixes
    suffixes = ["Net", "Gross", "Total", "Current", "Noncurrent"]
    prefixes = ["Total", "Net"]

    for suffix in suffixes:
        if not base.endswith(suffix):
            variations.append(f"{base}{suffix}")

    for prefix in prefixes:
        if not base.startswith(prefix):
            variations.append(f"{prefix}{base}")

    # Common alternative names
    alternatives = {
        "Revenue": ["Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax"],
        "NetIncome": ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
        "OperatingIncome": ["OperatingIncomeLoss", "IncomeLossFromOperations",
                           "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                           "IncomeLossFromContinuingOperations"],
        "TotalAssets": ["Assets"],
        "TotalLiabilities": ["Liabilities"],
        "ShareholdersEquity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
        "EPS": ["EarningsPerShareBasic", "EarningsPerShareDiluted"],
        "EBITDA": ["EarningsBeforeInterestTaxesDepreciationAndAmortization"],
        "OperatingCashFlow": ["NetCashProvidedByUsedInOperatingActivities"],
        "CapitalExpenditures": ["PaymentsToAcquirePropertyPlantAndEquipment", "CapitalExpenditureDiscontinuedOperations"],
        "Goodwill": ["GoodwillNet", "GoodwillGross"],
        "IntangibleAssets": ["IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet"],
        "LongTermDebt": ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"],
        "CashAndEquivalents": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsAndShortTermInvestments",
                               "CashAndDueFromBanks",
                               "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    }

    if metric_name in alternatives:
        for alt in alternatives[metric_name]:
            if alt not in variations:
                variations.append(alt)

    return variations


# =============================================================================
# GPT-5.4 ESCALATION
# =============================================================================

def _consult_gpt(
    gap: 'MetricGap',
    graveyard_entries: List[Dict],
    config_dir: Path,
) -> Optional[ConfigChange]:
    """
    Escalate to GPT-5.4 when deterministic strategies are exhausted.

    Sends structured context about the gap, extraction evidence, and
    prior failed attempts. Parses GPT's response into a ConfigChange.

    Only called after subtype-specific failures exceed the escalation threshold.

    Returns:
        ConfigChange if GPT proposes a valid change, None otherwise.
    """
    # Build context about the gap
    evidence = gap.extraction_evidence
    evidence_context = ""
    if evidence:
        evidence_context = (
            f"- Resolution type: {evidence.resolution_type}\n"
            f"- Components used: {evidence.components_used}\n"
            f"- Components missing: {evidence.components_missing}\n"
            f"- Company industry: {evidence.company_industry}\n"
        )
    else:
        evidence_context = "- No extraction evidence available\n"

    # Format prior failed attempts
    graveyard_text = "None"
    if graveyard_entries:
        entries = []
        for entry in graveyard_entries[-5:]:  # Last 5 attempts
            entries.append(
                f"  - config_diff: {entry.get('config_diff', 'N/A')}\n"
                f"    discard_reason: {entry.get('discard_reason', 'N/A')}\n"
                f"    detail: {entry.get('detail', 'N/A')}"
            )
        graveyard_text = "\n".join(entries)

    prompt = f"""You are an XBRL standardization expert. A metric gap resists automated resolution.

## Gap Details
- Ticker: {gap.ticker}, Metric: {gap.metric}
- Reference value (yfinance): {gap.reference_value}
- Extracted value (XBRL): {gap.xbrl_value}
- hv_subtype: {gap.hv_subtype}
- Current variance: {gap.current_variance}%
- Gap type: {gap.gap_type}
{evidence_context}

## Prior Failed Attempts
{graveyard_text}

## Available Fix Strategies
You may propose ONE of these ConfigChange types:
1. ADD_CONCEPT: Add an XBRL concept to metrics.yaml known_concepts list
2. ADD_STANDARDIZATION: Add a composite formula to metrics.yaml
3. SET_INDUSTRY: Set industry field in companies.yaml
4. ADD_COMPANY_OVERRIDE: Add metric_overrides in companies.yaml
5. ADD_EXCLUSION: Exclude this metric for this company
6. ADD_DIVERGENCE: Document a known divergence

## Response Format (strict JSON only — no markdown fences)
{{
  "change_type": "one of the above (e.g. ADD_CONCEPT)",
  "file": "metrics.yaml or companies.yaml",
  "yaml_path": "dot.notation.path (e.g. metrics.Revenue.known_concepts)",
  "new_value": "<value - string for ADD_CONCEPT, dict for others>",
  "rationale": "why this will work"
}}

If you believe this gap is fundamentally unresolvable (structural mismatch
between XBRL and yfinance), respond with ADD_EXCLUSION or ADD_DIVERGENCE."""

    # Collect file paths to send as context
    absolute_file_paths = []
    metrics_path = config_dir / "metrics.yaml"
    companies_path = config_dir / "companies.yaml"
    if metrics_path.exists():
        absolute_file_paths.append(str(metrics_path))
    if companies_path.exists():
        absolute_file_paths.append(str(companies_path))

    logger.info(f"GPT CONSULTATION: {gap.ticker}:{gap.metric} (subtype={gap.hv_subtype})")

    try:
        response_text = _call_gpt_via_mcp(prompt, absolute_file_paths)
    except Exception as e:
        logger.warning(f"GPT consultation failed for {gap.ticker}:{gap.metric}: {e}")
        return None

    if not response_text:
        logger.warning(f"GPT returned empty response for {gap.ticker}:{gap.metric}")
        return None

    # Parse the JSON response
    return _parse_gpt_response(response_text, gap)


def _call_gpt_via_mcp(prompt: str, file_paths: List[str]) -> Optional[str]:
    """
    Call GPT-5.4 via the mcp__pal__chat MCP tool.

    This function is designed to be monkey-patched or overridden in testing.
    In production, it's called within an agent context that has MCP access.

    The default implementation tries to import and call the MCP tool directly.
    If that fails, it returns None (the escalation is simply skipped).
    """
    # Try to call via MCP tool interface
    # In production, this is overridden by the agent framework
    logger.warning(
        "GPT consultation requires MCP tool access (mcp__pal__chat). "
        "Override _call_gpt_via_mcp or use make_escalation_propose_fn() "
        "with a gpt_caller argument."
    )
    return None


def _parse_gpt_response(response_text: str, gap: 'MetricGap') -> Optional[ConfigChange]:
    """Parse GPT's JSON response into a ConfigChange."""
    try:
        # Strip markdown code fences if present
        text = response_text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()

        data = json.loads(text)

        # Validate required fields
        required = {"change_type", "file", "yaml_path", "new_value", "rationale"}
        missing = required - set(data.keys())
        if missing:
            logger.warning(f"GPT response missing fields: {missing}")
            return None

        # Map change_type string to ChangeType enum
        change_type_str = data["change_type"].upper()
        # Handle both "ADD_CONCEPT" and "add_concept" formats
        try:
            change_type = ChangeType(change_type_str.lower())
        except ValueError:
            # Try matching by name
            try:
                change_type = ChangeType[change_type_str]
            except KeyError:
                logger.warning(f"GPT proposed unknown change_type: {data['change_type']}")
                return None

        # Validate file is a Tier 1 config
        if data["file"] not in TIER1_CONFIGS:
            logger.warning(f"GPT proposed non-Tier1 file: {data['file']}")
            return None

        return ConfigChange(
            file=data["file"],
            change_type=change_type,
            yaml_path=data["yaml_path"],
            new_value=data["new_value"],
            rationale=f"[GPT-5.4] {data['rationale']}",
            target_metric=gap.metric,
            target_companies=gap.ticker,
        )

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse GPT response as JSON: {e}")
        logger.debug(f"GPT response was: {response_text[:500]}")
        return None
    except Exception as e:
        logger.warning(f"Error parsing GPT response: {e}")
        return None


# =============================================================================
# GPT ESCALATION WRAPPER
# =============================================================================

def propose_change_with_escalation(
    gap: 'MetricGap',
    graveyard_entries: List[Dict],
    config_dir: Optional[Path] = None,
    tracker: Optional[_SubtypeFailureTracker] = None,
    gpt_caller: Optional[Callable] = None,
) -> Optional[ConfigChange]:
    """
    Enhanced propose_change with GPT-5.4 escalation.

    Flow:
    1. Try deterministic propose_change() first
    2. If None returned, record subtype failure
    3. If subtype failures >= threshold, escalate to GPT-5.4
    4. GPT proposals go through the same CQS eval gate

    Args:
        gap: The metric gap to address.
        graveyard_entries: Prior failed attempts.
        config_dir: Override config directory.
        tracker: Subtype failure tracker for escalation decisions.
        gpt_caller: Optional callable(prompt, file_paths) -> str for GPT calls.
            If provided, overrides the default _call_gpt_via_mcp.
    """
    # Try deterministic first
    change = propose_change(gap, graveyard_entries, config_dir)
    if change is not None:
        return change

    # Record this null-proposal as a subtype failure
    if tracker:
        tracker.record_failure(gap.ticker, gap.metric, gap.hv_subtype)

        if tracker.should_escalate(gap.ticker, gap.metric, gap.hv_subtype):
            logger.info(
                f"GPT ESCALATION: {gap.ticker}:{gap.metric} "
                f"(subtype={gap.hv_subtype}, "
                f"failures={tracker.get_count(gap.ticker, gap.metric, gap.hv_subtype)})"
            )

            # Temporarily override the MCP caller if provided
            if gpt_caller is not None:
                original = globals().get('_call_gpt_via_mcp')
                globals()['_call_gpt_via_mcp'] = gpt_caller
                try:
                    result = _consult_gpt(gap, graveyard_entries, config_dir or CONFIG_DIR)
                finally:
                    globals()['_call_gpt_via_mcp'] = original
                return result
            else:
                return _consult_gpt(gap, graveyard_entries, config_dir or CONFIG_DIR)

    return None


def make_escalation_propose_fn(
    escalation_threshold: int = 3,
    gpt_caller: Optional[Callable] = None,
) -> Callable:
    """
    Factory that creates a propose_fn with GPT escalation built in.

    Args:
        escalation_threshold: Number of subtype failures before GPT escalation.
        gpt_caller: Optional callable(prompt, file_paths) -> str for GPT calls.
            If None, uses the default _call_gpt_via_mcp (which requires MCP access).

    Returns:
        A propose_fn compatible with run_overnight(propose_fn=...).
    """
    tracker = _SubtypeFailureTracker(escalation_threshold=escalation_threshold)

    def _propose(gap, graveyard_entries):
        return propose_change_with_escalation(
            gap, graveyard_entries, tracker=tracker, gpt_caller=gpt_caller,
        )

    # Attach tracker for external inspection (e.g., reporting)
    _propose._tracker = tracker
    return _propose


# =============================================================================
# TOURNAMENT EVALUATION (Phase 4)
# =============================================================================

def tournament_eval(
    change: ConfigChange,
    baseline_cqs: CQSResult,
    ledger: Optional[ExperimentLedger] = None,
) -> ExperimentDecision:
    """
    Two-stage tournament evaluation for overfitting protection.

    Stage 1 (Fast, ~3 min): Run on 5-company quick-eval cohort.
        If CQS drops -> immediate DISCARD.
    Stage 2 (Validation, ~10 min): If CQS improves, run on 20-company set.
        If still improves -> KEEP. If regresses -> DISCARD.

    This prevents micro-batch overfitting where a change helps 5 companies
    but hurts the broader population.
    """
    # Stage 1: Quick eval
    logger.info("Tournament Stage 1: Quick eval (5 companies)")
    stage1 = evaluate_experiment(
        change=change,
        baseline_cqs=baseline_cqs,
        eval_cohort=QUICK_EVAL_COHORT,
        ledger=ledger,
    )

    if stage1.decision != Decision.KEEP:
        logger.info(f"Tournament Stage 1 FAILED: {stage1.reason}")
        return stage1

    # Stage 2: Validation eval (broader cohort)
    logger.info("Tournament Stage 2: Validation eval (20 companies)")

    # Compute validation baseline if we don't have it
    validation_baseline = compute_cqs(
        eval_cohort=VALIDATION_COHORT,
        snapshot_mode=True,
        use_ai=False,
        ledger=ledger,
    )

    # The change is still applied from Stage 1 (it was KEEP'd)
    # Now re-measure on the broader cohort
    validation_cqs = compute_cqs(
        eval_cohort=VALIDATION_COHORT,
        snapshot_mode=True,
        use_ai=False,
        baseline_cqs=validation_baseline.cqs,
        ledger=ledger,
    )

    if validation_cqs.cqs <= validation_baseline.cqs:
        revert_config_change(change)
        return ExperimentDecision(
            decision=Decision.DISCARD,
            cqs_before=validation_baseline.cqs,
            cqs_after=validation_cqs.cqs,
            reason=(
                f"Tournament Stage 2 FAILED: passed quick-eval but regressed on "
                f"validation set ({validation_baseline.cqs:.4f} -> {validation_cqs.cqs:.4f})"
            ),
            duration_seconds=stage1.duration_seconds,
        )

    new_regressions = validation_cqs.total_regressions - validation_baseline.total_regressions
    if new_regressions > 0:
        revert_config_change(change)
        return ExperimentDecision(
            decision=Decision.VETO,
            cqs_before=validation_baseline.cqs,
            cqs_after=validation_cqs.cqs,
            reason=f"Tournament Stage 2 VETO: {new_regressions} new regression(s) on validation set (was {validation_baseline.total_regressions}, now {validation_cqs.total_regressions})",
            duration_seconds=stage1.duration_seconds,
        )

    logger.info(
        f"Tournament PASSED: quick={stage1.cqs_after:.4f} "
        f"validation={validation_cqs.cqs:.4f}"
    )

    return ExperimentDecision(
        decision=Decision.KEEP,
        cqs_before=validation_baseline.cqs,
        cqs_after=validation_cqs.cqs,
        reason=f"Passed both tournament stages (validation CQS: {validation_cqs.cqs:.4f})",
        duration_seconds=stage1.duration_seconds,
    )


# =============================================================================
# OVERNIGHT LOOP (Phase 4)
# =============================================================================

def run_overnight(
    duration_hours: float = 7.5,
    focus_area: Optional[str] = None,
    use_tournament: bool = True,
    dry_run: bool = False,
    ledger: Optional[ExperimentLedger] = None,
    propose_fn=None,
    max_workers: int = 1,
    escalation_threshold: int = 3,
    eval_cohort: Optional[List[str]] = None,
) -> OvernightReport:
    """
    Run an overnight auto-eval session.

    Sequence:
    1. Establish baseline CQS
    2. Identify gaps
    3. For each gap, propose and evaluate config changes
    4. Keep successful changes, graveyard failures
    5. Full-tier eval as safety net before committing
    6. Circuit breakers: stop after 10 consecutive failures or CQS drop >0.02

    Args:
        duration_hours: How long to run (default 7.5 hours).
        focus_area: Optional focus (e.g., "banking", "add_concept", metric name).
        use_tournament: Whether to use 2-stage tournament eval.
        dry_run: If True, don't actually apply changes.
        ledger: ExperimentLedger instance.
        propose_fn: Callable(gap, graveyard) -> ConfigChange. If None, skips proposals.
        max_workers: Parallel workers for CQS computation (1 = sequential).
        escalation_threshold: Subtype failures before GPT escalation (default 3).
        eval_cohort: List of tickers to evaluate. Defaults to QUICK_EVAL_COHORT.

    Returns:
        OvernightReport with session summary.
    """
    if ledger is None:
        ledger = ExperimentLedger()

    cohort = eval_cohort or QUICK_EVAL_COHORT

    # Tournament is designed for small quick-eval cohorts.
    # When evaluating on >=20 companies, direct eval is sufficient.
    if len(cohort) >= 20 and use_tournament:
        logger.info(f"Auto-disabling tournament for {len(cohort)}-company cohort (direct eval sufficient)")
        use_tournament = False

    session_id = f"overnight_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    start_time = time.time()
    deadline = start_time + duration_hours * 3600

    report = OvernightReport(
        session_id=session_id,
        started_at=datetime.now().isoformat(),
        finished_at="",
        duration_hours=0,
        focus_area=focus_area,
    )

    # Step 1: Baseline CQS
    logger.info(f"Session {session_id}: Establishing baseline on {len(cohort)} companies...")
    baseline = compute_cqs(
        eval_cohort=cohort,
        snapshot_mode=True,
        ledger=ledger,
        max_workers=max_workers,
    )
    report.cqs_start = baseline.cqs
    report.cqs_peak = baseline.cqs
    report.ef_cqs_start = baseline.ef_cqs
    report.sa_cqs_start = baseline.sa_cqs
    current_baseline = baseline

    # Subtype failure tracker — for GPT escalation in propose_fn
    tracker = _SubtypeFailureTracker(escalation_threshold=escalation_threshold)
    proposal_cache = ProposalCache()

    consecutive_failures = 0
    max_consecutive_failures = 10

    use_fast_path_gaps = None  # Set after KEEP to skip identify_gaps()

    # Step 2: Main experiment loop
    while time.time() < deadline:
        # Check circuit breakers
        if consecutive_failures >= max_consecutive_failures:
            report.stopped_early = True
            report.stop_reason = f"Circuit breaker: {consecutive_failures} consecutive failures"
            logger.warning(report.stop_reason)
            break

        if current_baseline.cqs < report.cqs_start - 0.02:
            report.stopped_early = True
            report.stop_reason = (
                f"Circuit breaker: CQS dropped >0.02 "
                f"({report.cqs_start:.4f} -> {current_baseline.cqs:.4f})"
            )
            logger.warning(report.stop_reason)
            break

        # Identify gaps (skip if we have fast-path gaps from a KEEP)
        if use_fast_path_gaps is not None:
            gaps = use_fast_path_gaps
            use_fast_path_gaps = None
        else:
            gaps, cqs_result = identify_gaps(
                eval_cohort=cohort,
                snapshot_mode=True,
                ledger=ledger,
                max_workers=max_workers,
            )
            current_baseline = cqs_result

        if not gaps:
            report.stopped_early = True
            report.stop_reason = "No gaps remaining"
            logger.info(report.stop_reason)
            break

        # Filter gaps by focus area
        if focus_area:
            gaps = _filter_gaps_by_focus(gaps, focus_area)
            if not gaps:
                report.stopped_early = True
                report.stop_reason = f"No gaps matching focus: {focus_area}"
                break

        # Try each gap
        made_progress = False
        experiments_before = report.experiments_total
        null_proposals = 0
        for gap in gaps:
            if time.time() >= deadline:
                break

            # Dead-end filtering is handled by identify_gaps() — no redundant check here

            # Get proposal from the agent function
            if propose_fn is None:
                logger.info("No proposal function provided — ending loop")
                report.stopped_early = True
                report.stop_reason = "No proposal function"
                break

            change = propose_fn(gap, ledger.get_graveyard_entries(gap.metric))
            if change is None:
                router = AIAgentRouter()
                agent_type = router.route(gap)
                if agent_type is not None:
                    logger.info(f"AI routing: {gap.ticker}:{gap.metric} -> {agent_type.value}")
                    # TODO: Phase 2 — call the actual AI agent here
                null_proposals += 1
                continue

            # Proposal dedup: skip proposals that were already tried this session
            pkey = proposal_cache.proposal_key_for(change)
            if proposal_cache.was_tried(gap.ticker, gap.metric, pkey):
                logger.debug(f"Skipping duplicate proposal: {gap.ticker}:{gap.metric} {pkey}")
                null_proposals += 1
                continue
            proposal_cache.record(gap.ticker, gap.metric, pkey)

            # Track GPT consultations
            if change.rationale.startswith("[GPT-5.4]"):
                report.gpt_consultations += 1

            report.experiments_total += 1
            if change.change_type == ChangeType.ADD_STANDARDIZATION:
                report.solver_proposals += 1

            if dry_run:
                logger.info(f"[DRY RUN] Would apply: {change.to_diff_string()}")
                continue

            # Evaluate
            if use_tournament:
                result = tournament_eval(change, current_baseline, ledger)
            else:
                result = evaluate_experiment(
                    change, current_baseline,
                    eval_cohort=cohort,
                    ledger=ledger,
                    max_workers=max_workers,
                )

            # Log result
            log_experiment(change, result, ledger, run_id=session_id)

            if result.decision == Decision.KEEP:
                report.experiments_kept += 1
                if change.change_type == ChangeType.ADD_STANDARDIZATION:
                    report.solver_kept += 1
                is_gpt = change.rationale.startswith("[GPT-5.4]")
                if is_gpt:
                    report.gpt_proposals_kept += 1
                report.config_diffs.append(change.to_diff_string())
                consecutive_failures = 0
                made_progress = True

                # Reuse CQS from evaluation (Phase 1a optimization)
                if result.new_cqs_result is not None:
                    current_baseline = result.new_cqs_result
                else:
                    current_baseline = compute_cqs(
                        eval_cohort=cohort,
                        snapshot_mode=True,
                        ledger=ledger,
                        max_workers=max_workers,
                    )
                if current_baseline.cqs > report.cqs_peak:
                    report.cqs_peak = current_baseline.cqs

                logger.info(f"KEPT: {change.target_metric} — CQS now {current_baseline.cqs:.4f}")
                # Fast path: derive gaps instead of re-running identify_gaps()
                graveyard_counts = _get_graveyard_counts(ledger)
                use_fast_path_gaps = derive_gaps_from_cqs(current_baseline, graveyard_counts)
                if focus_area:
                    use_fast_path_gaps = _filter_gaps_by_focus(use_fast_path_gaps, focus_area)
                break  # Re-enter outer loop with fast-path gaps

            elif result.decision == Decision.VETO:
                report.experiments_vetoed += 1
                consecutive_failures += 1
                tracker.record_failure(gap.ticker, gap.metric, gap.hv_subtype)
                logger.warning(f"VETOED: {change.target_metric} — {result.reason}")

            else:
                report.experiments_discarded += 1
                consecutive_failures += 1
                tracker.record_failure(gap.ticker, gap.metric, gap.hv_subtype)
                logger.info(f"DISCARDED: {change.target_metric} — {result.reason}")

        # Fix 2: Only increment if no experiments were even attempted this iteration
        # (avoids double-counting with per-discard increments above)
        if not made_progress and report.experiments_total == experiments_before:
            if null_proposals > 0:
                # Fix 3: All gaps tried but none could produce a proposal — stop spinning
                report.stopped_early = True
                report.stop_reason = f"All {null_proposals} gaps exhausted (no viable proposals)"
                logger.warning(report.stop_reason)
                consecutive_failures = max_consecutive_failures  # Force circuit breaker
            elif propose_fn is not None:
                consecutive_failures += 1

    # Finalize
    report.finished_at = datetime.now().isoformat()
    report.duration_hours = (time.time() - start_time) / 3600
    report.cqs_end = current_baseline.cqs
    report.ef_cqs_end = current_baseline.ef_cqs
    report.sa_cqs_end = current_baseline.sa_cqs

    logger.info(
        f"Session {session_id} complete: "
        f"{report.experiments_kept}/{report.experiments_total} kept, "
        f"CQS {report.cqs_start:.4f} -> {report.cqs_end:.4f}"
    )

    return report


def _filter_gaps_by_focus(gaps: List[MetricGap], focus_area: str) -> List[MetricGap]:
    """Filter gaps by focus area keyword."""
    focus_lower = focus_area.lower()
    filtered = []
    for gap in gaps:
        if (
            focus_lower in gap.metric.lower()
            or focus_lower in gap.ticker.lower()
            or focus_lower in gap.gap_type.lower()
            or focus_lower in gap.notes.lower()
        ):
            filtered.append(gap)
    return filtered


# =============================================================================
# UTILITIES
# =============================================================================

def is_git_clean() -> bool:
    """Check if the git working tree is clean for Tier 1 configs."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"] + [str(p) for p in TIER1_CONFIGS.values()],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip() == ""
    except subprocess.CalledProcessError:
        return False


def get_config_fingerprint() -> str:
    """Get a hash of all Tier 1 config files for change detection."""
    h = hashlib.sha256()
    for name in sorted(TIER1_CONFIGS.keys()):
        path = TIER1_CONFIGS[name]
        if path.exists():
            h.update(path.read_bytes())
    return h.hexdigest()[:16]


# =============================================================================
# PHASE 1: PARALLEL SCOUT INFRASTRUCTURE (Python ThreadPoolExecutor)
# =============================================================================

@dataclass
class ScoutResult:
    """Result from a parallel concept scout."""
    ticker: str
    metric: str
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    classification: str = ""           # "unmapped" | "structural" | "validation_failure"
    recommended_action: str = ""       # "add_concept" | "add_exclusion" | "skip"
    best_candidate: Optional[str] = None
    confidence: float = 0.0
    error: Optional[str] = None

    @property
    def has_proposal(self) -> bool:
        if self.recommended_action == "add_exclusion" and self.confidence > 0.5:
            return True
        return self.best_candidate is not None and self.confidence > 0.5


def scout_result_to_change(result: ScoutResult, gap: MetricGap) -> Optional[ConfigChange]:
    """Convert a scout result into a ConfigChange proposal."""
    if not result.has_proposal:
        return None

    if result.recommended_action == "add_concept" and result.best_candidate:
        return ConfigChange(
            file="metrics.yaml",
            change_type=ChangeType.ADD_CONCEPT,
            yaml_path=f"metrics.{result.metric}.known_concepts",
            new_value=result.best_candidate,
            rationale=f"Parallel scout found concept (confidence={result.confidence:.2f})",
            target_metric=result.metric,
            target_companies=result.ticker,
        )
    elif result.recommended_action == "add_exclusion":
        return ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.ADD_EXCLUSION,
            yaml_path=f"companies.{result.ticker}.exclude_metrics",
            new_value=result.metric,
            rationale=f"Classified as structural gap ({result.classification})",
            target_metric=result.metric,
            target_companies=result.ticker,
        )

    return None


def _scout_single_gap(gap: MetricGap, known_concepts: List[str]) -> ScoutResult:
    """
    Scout a single gap using Python — discover concepts, verify multi-period.

    This is the unit of work for ThreadPoolExecutor. It calls the existing
    discover_concepts() and verify_mapping() functions directly.
    """
    from edgar.xbrl.standardization.tools.discover_concepts import discover_concepts, strip_prefix
    from edgar.xbrl.standardization.tools.verify_mapping import verify_mapping, _extract_xbrl_value
    from edgar import Company, set_identity, use_local_storage

    set_identity("Dev Gunning developer-gunning@gmail.com")
    use_local_storage(True)

    result = ScoutResult(ticker=gap.ticker, metric=gap.metric)

    # Structural gap: no reference value
    if gap.reference_value is None:
        result.classification = "structural"
        result.recommended_action = "add_exclusion"
        result.confidence = 0.9
        return result

    try:
        company = Company(gap.ticker)
        filings_10k = list(company.get_filings(form='10-K', amendments=False))[:3]
        if not filings_10k:
            result.error = "No 10-K filings found"
            return result

        xbrl = filings_10k[0].xbrl()

        # Get facts for broader search
        facts_df = None
        try:
            facts = company.get_facts()
            if facts is not None:
                facts_df = facts.to_dataframe()
        except Exception:
            pass

        # Discover candidates via calc tree + facts search
        candidates = discover_concepts(
            metric_name=gap.metric, xbrl=xbrl, facts_df=facts_df,
            ticker=gap.ticker, known_concepts=known_concepts, top_k=5,
        )

        # Also try known concept variations (common XBRL name alternatives)
        # that might not be found by similarity matching
        variations = _generate_concept_variations(gap.metric, gap.metric)
        variation_candidates = []
        calc_tree_concepts = set()
        if hasattr(xbrl, 'calculation_trees') and xbrl.calculation_trees:
            for tree in xbrl.calculation_trees.values():
                for name in tree.all_nodes:
                    stripped = strip_prefix(name)
                    calc_tree_concepts.add(stripped)

        for var in variations:
            if var not in known_concepts and var in calc_tree_concepts:
                # This variation exists in the calc tree — high confidence
                from edgar.xbrl.standardization.tools.discover_concepts import CandidateConcept
                variation_candidates.append(CandidateConcept(
                    concept=var, source="variation", confidence=0.92,
                    reasoning=f"Known variation '{var}' found in calc tree",
                ))

        # Merge: variations first (higher precision), then discovery candidates
        candidates = variation_candidates + candidates

        if not candidates:
            result.classification = "unmapped"
            result.recommended_action = "skip"
            return result

        # Multi-period verification for top candidates
        older_xbrls = []
        for filing in filings_10k[1:]:
            try:
                older_xbrls.append(filing.xbrl())
            except Exception:
                pass

        for candidate in candidates:
            concept = candidate.concept
            clean_concept = strip_prefix(concept)

            if clean_concept in known_concepts:
                continue

            # Try multi-period verification via verify_mapping (needs yfinance)
            periods_matched = 0
            periods_checked = 0
            has_xbrl_value = False
            all_xbrls = [xbrl] + older_xbrls

            for period_xbrl in all_xbrls:
                verification = verify_mapping(
                    metric=gap.metric, concept=concept,
                    xbrl=period_xbrl, ticker=gap.ticker, tolerance_pct=15.0,
                )
                if verification.xbrl_value is not None:
                    has_xbrl_value = True
                if verification.xbrl_value is not None and verification.reference_value is not None:
                    periods_checked += 1
                    if verification.is_valid:
                        periods_matched += 1

            # Accept if multi-period verification passes
            if periods_checked > 0 and periods_matched >= min(2, periods_checked):
                result.best_candidate = clean_concept
                result.confidence = candidate.confidence
                result.recommended_action = "add_concept"
                result.classification = "unmapped"
                result.candidates.append({
                    "concept": clean_concept,
                    "source": candidate.source,
                    "periods_matched": periods_matched,
                    "periods_checked": periods_checked,
                })
                break

            # Fallback: if yfinance isn't available (verify_mapping returns
            # xbrl_value=None without trying), extract value directly.
            # If concept is a known variation found in calc tree AND has an
            # XBRL value, propose it. CQS eval loop will catch bad proposals.
            if periods_checked == 0 and candidate.source == "variation":
                xbrl_val = _extract_xbrl_value(xbrl, concept)
                if xbrl_val is not None and candidate.confidence >= 0.9:
                    result.best_candidate = clean_concept
                    result.confidence = candidate.confidence * 0.9
                    result.recommended_action = "add_concept"
                    result.classification = "unmapped"
                    result.candidates.append({
                        "concept": clean_concept,
                        "source": "variation_unverified",
                        "xbrl_value": xbrl_val,
                    })
                    break

    except Exception as e:
        result.error = str(e)

    return result


def parallel_scout_gaps(
    gaps: List[MetricGap],
    known_concepts_map: Optional[Dict[str, List[str]]] = None,
    max_workers: int = 5,
) -> List[ScoutResult]:
    """
    Scout multiple gaps in parallel using ThreadPoolExecutor.

    Each gap gets its own thread running discover_concepts() + verify_mapping().
    This is pure Python parallelism — no LLM calls, deterministic, free.

    Args:
        gaps: List of MetricGaps to explore.
        known_concepts_map: Dict of metric -> known_concepts list. If None,
            reads from metrics.yaml.
        max_workers: Maximum parallel threads (default 5).

    Returns:
        List of ScoutResults, one per gap.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if known_concepts_map is None:
        known_concepts_map = _load_known_concepts()

    results: List[ScoutResult] = []
    futures_map = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for gap in gaps:
            known = known_concepts_map.get(gap.metric, [])
            future = executor.submit(_scout_single_gap, gap, known)
            futures_map[future] = gap

        for future in as_completed(futures_map):
            gap = futures_map[future]
            try:
                result = future.result(timeout=120)
                results.append(result)
                if result.has_proposal:
                    logger.info(
                        f"Scout found: {gap.ticker}:{gap.metric} -> "
                        f"{result.best_candidate} ({result.confidence:.2f})"
                    )
            except Exception as e:
                logger.warning(f"Scout failed for {gap.ticker}:{gap.metric}: {e}")
                results.append(ScoutResult(
                    ticker=gap.ticker, metric=gap.metric, error=str(e)
                ))

    return results


def _load_known_concepts() -> Dict[str, List[str]]:
    """Load known_concepts for all metrics from metrics.yaml."""
    metrics_path = CONFIG_DIR / "metrics.yaml"
    if not metrics_path.exists():
        return {}

    with open(metrics_path, 'r') as f:
        config = yaml.safe_load(f)

    result = {}
    for metric, defn in config.get("metrics", {}).items():
        result[metric] = defn.get("known_concepts", [])
    return result


def build_classifier_prompt(gap: MetricGap, graveyard_count: int) -> str:
    """Build the prompt for a Haiku gap classifier agent.

    Gap classification is a reasoning task — Haiku adds value here by
    applying industry knowledge that deterministic code cannot.
    """
    return (
        f"Classify metric gap: ticker={gap.ticker}, metric={gap.metric}, "
        f"gap_type={gap.gap_type}, reference_value={gap.reference_value}, "
        f"xbrl_value={gap.xbrl_value}, variance={gap.current_variance}, "
        f"graveyard_count={graveyard_count}. "
        f"Return strict JSON classification."
    )


# =============================================================================
# PHASE 2: BATCH EVALUATION
# =============================================================================

def changes_conflict(a: ConfigChange, b: ConfigChange) -> bool:
    """
    Check if two config changes conflict (modify the same scope).

    Two changes conflict if they modify the same key path in the same file.
    Company-specific changes to different companies never conflict.
    Metric-level changes to different metrics never conflict.
    """
    if a.file != b.file:
        return False

    a_parts = a.yaml_path.split('.')
    b_parts = b.yaml_path.split('.')

    if a.file == "companies.yaml":
        # Company-specific changes: conflict only if same company + same path
        if len(a_parts) >= 2 and len(b_parts) >= 2:
            return a_parts[1] == b_parts[1] and a.yaml_path == b.yaml_path
        return a.yaml_path == b.yaml_path

    if a.file == "metrics.yaml":
        # Metric-level changes: conflict only if same metric + same path
        if len(a_parts) >= 2 and len(b_parts) >= 2:
            return a_parts[1] == b_parts[1] and a.yaml_path == b.yaml_path
        return a.yaml_path == b.yaml_path

    # For other files, any overlap in path prefix is a conflict
    return a.yaml_path == b.yaml_path


def select_non_conflicting(changes: List[ConfigChange]) -> List[ConfigChange]:
    """Select the largest non-conflicting subset of changes."""
    selected: List[ConfigChange] = []
    for change in changes:
        if not any(changes_conflict(change, s) for s in selected):
            selected.append(change)
    return selected


@dataclass
class BatchResult:
    """Result of batch-evaluating multiple config changes."""
    changes_applied: List[ConfigChange]
    changes_kept: List[ConfigChange]
    changes_reverted: List[ConfigChange]
    cqs_before: float
    cqs_after: float
    duration_seconds: float = 0.0


def batch_evaluate(
    changes: List[ConfigChange],
    baseline_cqs: CQSResult,
    eval_cohort: Optional[List[str]] = None,
    ledger: Optional[ExperimentLedger] = None,
) -> BatchResult:
    """
    Evaluate a batch of non-conflicting config changes together.

    Applies all changes at once, measures CQS, and if it improved, keeps all.
    If CQS dropped, uses binary search to find which change(s) caused regression.

    Args:
        changes: List of non-conflicting ConfigChanges.
        baseline_cqs: CQS before any changes.
        eval_cohort: Companies to evaluate.
        ledger: ExperimentLedger.

    Returns:
        BatchResult with which changes were kept/reverted.
    """
    start_time = time.time()
    if eval_cohort is None:
        eval_cohort = QUICK_EVAL_COHORT

    # Filter to non-conflicting
    batch = select_non_conflicting(changes)
    if not batch:
        return BatchResult(
            changes_applied=[], changes_kept=[], changes_reverted=[],
            cqs_before=baseline_cqs.cqs, cqs_after=baseline_cqs.cqs,
        )

    # Apply all changes
    applied: List[ConfigChange] = []
    for change in batch:
        try:
            apply_config_change(change)
            applied.append(change)
        except Exception as e:
            logger.warning(f"Failed to apply {change.target_metric}: {e}")

    if not applied:
        return BatchResult(
            changes_applied=[], changes_kept=[], changes_reverted=[],
            cqs_before=baseline_cqs.cqs, cqs_after=baseline_cqs.cqs,
        )

    # Measure aggregate CQS
    try:
        new_cqs = compute_cqs(
            eval_cohort=eval_cohort,
            snapshot_mode=True,
            use_ai=False,
            baseline_cqs=baseline_cqs.cqs,
            ledger=ledger,
        )
    except Exception as e:
        logger.error(f"Batch evaluation failed: {e}")
        for change in applied:
            revert_config_change(change)
        return BatchResult(
            changes_applied=applied, changes_kept=[], changes_reverted=applied,
            cqs_before=baseline_cqs.cqs, cqs_after=baseline_cqs.cqs,
            duration_seconds=time.time() - start_time,
        )

    # Check for NEW regressions (hard veto -> revert all)
    new_regressions = new_cqs.total_regressions - baseline_cqs.total_regressions
    if new_regressions > 0:
        logger.warning(f"Batch VETOED: {new_regressions} new regressions (was {baseline_cqs.total_regressions}, now {new_cqs.total_regressions})")
        for change in applied:
            revert_config_change(change)
        return BatchResult(
            changes_applied=applied, changes_kept=[], changes_reverted=applied,
            cqs_before=baseline_cqs.cqs, cqs_after=new_cqs.cqs,
            duration_seconds=time.time() - start_time,
        )

    # CQS improved -> keep all
    if new_cqs.cqs > baseline_cqs.cqs:
        logger.info(f"Batch KEPT: {len(applied)} changes, CQS {baseline_cqs.cqs:.4f} -> {new_cqs.cqs:.4f}")
        return BatchResult(
            changes_applied=applied, changes_kept=applied, changes_reverted=[],
            cqs_before=baseline_cqs.cqs, cqs_after=new_cqs.cqs,
            duration_seconds=time.time() - start_time,
        )

    # CQS didn't improve -> binary search to isolate problematic changes
    logger.info("Batch didn't improve CQS — isolating individual changes")
    kept, reverted = _binary_search_changes(applied, baseline_cqs, eval_cohort, ledger)

    final_cqs = compute_cqs(eval_cohort=eval_cohort, snapshot_mode=True, ledger=ledger)

    return BatchResult(
        changes_applied=applied, changes_kept=kept, changes_reverted=reverted,
        cqs_before=baseline_cqs.cqs, cqs_after=final_cqs.cqs,
        duration_seconds=time.time() - start_time,
    )


def _binary_search_changes(
    changes: List[ConfigChange],
    baseline_cqs: CQSResult,
    eval_cohort: List[str],
    ledger: Optional[ExperimentLedger],
) -> tuple:
    """
    Binary search to find which changes help vs hurt.

    Reverts all, then re-applies one at a time, keeping those that improve.
    Falls back to sequential evaluation for small batches.
    """
    # For small batches, just try each individually
    for change in changes:
        revert_config_change(change)

    kept: List[ConfigChange] = []
    reverted: List[ConfigChange] = []

    for change in changes:
        try:
            apply_config_change(change)
            new_cqs = compute_cqs(
                eval_cohort=eval_cohort, snapshot_mode=True,
                baseline_cqs=baseline_cqs.cqs, ledger=ledger,
            )

            if new_cqs.cqs > baseline_cqs.cqs and new_cqs.total_regressions == 0:
                kept.append(change)
                logger.info(f"  Individual KEEP: {change.target_metric}")
            else:
                revert_config_change(change)
                reverted.append(change)
                logger.info(f"  Individual REVERT: {change.target_metric}")
        except Exception:
            revert_config_change(change)
            reverted.append(change)

    return kept, reverted


# =============================================================================
# PHASE 3: CROSS-COMPANY LEARNING
# =============================================================================

def cross_company_learn(
    metric: str,
    concept: str,
    source_ticker: str,
    target_tickers: Optional[List[str]] = None,
    max_workers: int = 5,
) -> List[ConfigChange]:
    """
    When a concept works for one company, verify it transfers to others.

    Uses Python ThreadPoolExecutor to check the concept across multiple
    companies in parallel. Returns proposals only for verified transfers.

    Args:
        metric: The metric name (e.g., "LongTermDebt").
        concept: The concept that worked (e.g., "LongTermDebtNoncurrent").
        source_ticker: The ticker where this concept was discovered.
        target_tickers: Other tickers to try. Defaults to QUICK_EVAL_COHORT.
        max_workers: Max parallel threads.

    Returns:
        List of ConfigChanges to evaluate (add concept to known_concepts).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from edgar.xbrl.standardization.tools.verify_mapping import verify_mapping
    from edgar import Company, set_identity, use_local_storage

    if target_tickers is None:
        target_tickers = [t for t in QUICK_EVAL_COHORT if t != source_ticker]

    proposals = []

    # Check if concept is already in known_concepts
    metrics_path = CONFIG_DIR / "metrics.yaml"
    if not metrics_path.exists():
        return proposals

    with open(metrics_path, 'r') as f:
        metrics_config = yaml.safe_load(f)

    metric_def = metrics_config.get("metrics", {}).get(metric, {})
    known = metric_def.get("known_concepts", [])

    if concept in known:
        # Already universal — no per-company proposals needed
        return proposals

    def _check_ticker(ticker: str) -> Optional[str]:
        """Check if concept works for a single ticker. Returns ticker if yes."""
        set_identity("Dev Gunning developer-gunning@gmail.com")
        use_local_storage(True)
        try:
            company = Company(ticker)
            filing = list(company.get_filings(form='10-K', amendments=False))[0]
            xbrl = filing.xbrl()
            result = verify_mapping(
                metric=metric, concept=concept,
                xbrl=xbrl, ticker=ticker, tolerance_pct=15.0,
            )
            if result.is_valid:
                return ticker
        except Exception:
            pass
        return None

    # Parallel verification across target companies
    verified_tickers = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_check_ticker, t): t for t in target_tickers}
        for future in as_completed(futures):
            result = future.result(timeout=60)
            if result:
                verified_tickers.append(result)

    if verified_tickers:
        all_tickers = ",".join([source_ticker] + verified_tickers)
        proposals.append(ConfigChange(
            file="metrics.yaml",
            change_type=ChangeType.ADD_CONCEPT,
            yaml_path=f"metrics.{metric}.known_concepts",
            new_value=concept,
            rationale=(
                f"Cross-company verified: {concept} works for {metric} across "
                f"{len(verified_tickers)+1} companies ({all_tickers})"
            ),
            target_metric=metric,
            target_companies=all_tickers,
        ))
        logger.info(
            f"Cross-company learning: {concept} verified for "
            f"{len(verified_tickers)}/{len(target_tickers)} targets"
        )

    return proposals


# =============================================================================
# PHASE 4: CONCURRENCY GUARDS
# =============================================================================

def enable_wal_mode(ledger: ExperimentLedger) -> None:
    """Enable WAL mode on the ledger's SQLite database for concurrent reads."""
    try:
        if hasattr(ledger, 'conn') and ledger.conn:
            ledger.conn.execute("PRAGMA journal_mode=WAL")
            logger.info("SQLite WAL mode enabled for experiment ledger")
    except Exception as e:
        logger.warning(f"Failed to enable WAL mode: {e}")


# =============================================================================
# PHASE 5: MULTI-AGENT PROPOSAL-ONLY LOOP
# =============================================================================

@dataclass
class ProposalRecord:
    """A gap + proposed change pair produced by a worker agent."""
    gap: MetricGap
    proposal: ConfigChange
    worker_id: str = ""

    def to_dict(self) -> dict:
        return {
            "gap": {
                "ticker": self.gap.ticker,
                "metric": self.gap.metric,
                "gap_type": self.gap.gap_type,
                "estimated_impact": self.gap.estimated_impact,
                "reference_value": self.gap.reference_value,
                "xbrl_value": self.gap.xbrl_value,
                "hv_subtype": self.gap.hv_subtype,
                "current_variance": self.gap.current_variance,
                "graveyard_count": self.gap.graveyard_count,
                "notes": self.gap.notes,
            },
            "proposal": {
                "file": self.proposal.file,
                "change_type": self.proposal.change_type.value,
                "yaml_path": self.proposal.yaml_path,
                "old_value": self.proposal.old_value,
                "new_value": self.proposal.new_value,
                "rationale": self.proposal.rationale,
                "target_metric": self.proposal.target_metric,
                "target_companies": self.proposal.target_companies,
            },
            "worker_id": self.worker_id,
        }


@dataclass
class EvaluatedProposal:
    """A proposal that has been evaluated in-memory by a worker.

    Only KEEP proposals are returned by propose_and_evaluate_loop().
    """
    gap: MetricGap
    proposal: ConfigChange
    decision: ExperimentDecision
    worker_id: str = ""

    def to_dict(self) -> dict:
        return {
            "gap": {
                "ticker": self.gap.ticker,
                "metric": self.gap.metric,
                "gap_type": self.gap.gap_type,
                "estimated_impact": self.gap.estimated_impact,
                "reference_value": self.gap.reference_value,
                "xbrl_value": self.gap.xbrl_value,
                "hv_subtype": self.gap.hv_subtype,
                "current_variance": self.gap.current_variance,
                "graveyard_count": self.gap.graveyard_count,
                "notes": self.gap.notes,
            },
            "proposal": {
                "file": self.proposal.file,
                "change_type": self.proposal.change_type.value,
                "yaml_path": self.proposal.yaml_path,
                "old_value": self.proposal.old_value,
                "new_value": self.proposal.new_value,
                "rationale": self.proposal.rationale,
                "target_metric": self.proposal.target_metric,
                "target_companies": self.proposal.target_companies,
            },
            "decision": {
                "decision": self.decision.decision.value,
                "cqs_before": self.decision.cqs_before,
                "cqs_after": self.decision.cqs_after,
                "reason": self.decision.reason,
                "duration_seconds": self.decision.duration_seconds,
            },
            "worker_id": self.worker_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'EvaluatedProposal':
        """Deserialize from JSON dict (for inter-agent communication)."""
        gap_data = d["gap"]
        gap = MetricGap(
            ticker=gap_data["ticker"],
            metric=gap_data["metric"],
            gap_type=gap_data["gap_type"],
            estimated_impact=gap_data.get("estimated_impact", 0.0),
            reference_value=gap_data.get("reference_value"),
            xbrl_value=gap_data.get("xbrl_value"),
            hv_subtype=gap_data.get("hv_subtype"),
            current_variance=gap_data.get("current_variance"),
            graveyard_count=gap_data.get("graveyard_count", 0),
            notes=gap_data.get("notes", ""),
        )

        prop_data = d["proposal"]
        proposal = ConfigChange(
            file=prop_data["file"],
            change_type=ChangeType(prop_data["change_type"]),
            yaml_path=prop_data["yaml_path"],
            old_value=prop_data.get("old_value"),
            new_value=prop_data["new_value"],
            rationale=prop_data.get("rationale", ""),
            target_metric=prop_data.get("target_metric", ""),
            target_companies=prop_data.get("target_companies", ""),
        )

        dec_data = d["decision"]
        decision = ExperimentDecision(
            decision=Decision(dec_data["decision"]),
            cqs_before=dec_data["cqs_before"],
            cqs_after=dec_data["cqs_after"],
            reason=dec_data.get("reason", ""),
            duration_seconds=dec_data.get("duration_seconds", 0.0),
        )

        return cls(
            gap=gap,
            proposal=proposal,
            decision=decision,
            worker_id=d.get("worker_id", ""),
        )


def propose_only_loop(
    eval_cohort: List[str],
    propose_fn=None,
    ledger: Optional[ExperimentLedger] = None,
    max_workers: int = 1,
    focus_area: Optional[str] = None,
    escalation_threshold: int = 3,
    worker_id: str = "",
) -> List[ProposalRecord]:
    """
    Identify gaps and generate proposals WITHOUT applying them.

    This is the worker-mode counterpart to run_overnight(). It runs the same
    gap identification and proposal logic but stops short of applying or
    evaluating changes. The coordinator collects proposals from multiple
    workers and applies them sequentially.

    Args:
        eval_cohort: List of tickers to evaluate.
        propose_fn: Callable(gap, graveyard_entries) -> ConfigChange.
            If None, uses the default propose_change.
        ledger: ExperimentLedger instance (read-only in worker mode).
        max_workers: Parallel workers for CQS computation.
        focus_area: Optional focus filter.
        escalation_threshold: Subtype failures before GPT escalation.
        worker_id: Identifier for this worker (for logging).

    Returns:
        List of ProposalRecord dicts with gap + proposed change pairs.
    """
    if ledger is None:
        ledger = ExperimentLedger()

    if propose_fn is None:
        propose_fn = propose_change

    prefix = f"[Worker {worker_id}] " if worker_id else ""
    logger.info(f"{prefix}Starting propose_only_loop on {len(eval_cohort)} companies")

    # Identify gaps
    gaps, cqs_result = identify_gaps(
        eval_cohort=eval_cohort,
        snapshot_mode=True,
        ledger=ledger,
        max_workers=max_workers,
    )

    logger.info(f"{prefix}Found {len(gaps)} gaps (CQS={cqs_result.cqs:.4f})")

    # Filter by focus area
    if focus_area:
        gaps = _filter_gaps_by_focus(gaps, focus_area)
        logger.info(f"{prefix}{len(gaps)} gaps after focus filter: {focus_area}")

    if not gaps:
        logger.info(f"{prefix}No gaps to propose on")
        return []

    # Generate proposals for each gap
    proposals: List[ProposalRecord] = []
    tracker = _SubtypeFailureTracker(escalation_threshold=escalation_threshold)

    for gap in gaps:
        graveyard_entries = ledger.get_graveyard_entries(gap.metric)

        change = propose_fn(gap, graveyard_entries)
        if change is None:
            tracker.record_failure(gap.ticker, gap.metric, gap.hv_subtype)
            continue

        proposals.append(ProposalRecord(
            gap=gap,
            proposal=change,
            worker_id=worker_id,
        ))
        logger.info(
            f"{prefix}Proposed: {change.change_type.value} for "
            f"{gap.ticker}:{gap.metric}"
        )

    logger.info(f"{prefix}Generated {len(proposals)} proposals from {len(gaps)} gaps")
    return proposals


def propose_and_evaluate_loop(
    eval_cohort: List[str],
    propose_fn=None,
    ledger: Optional[ExperimentLedger] = None,
    max_workers: int = 1,
    focus_area: Optional[str] = None,
    escalation_threshold: int = 3,
    worker_id: str = "",
    checkpoint_interval: int = 1,
    role: str = "combined",
) -> List[EvaluatedProposal]:
    """
    Worker-mode: propose changes AND evaluate them on sub-cohort using in-memory config.

    Unlike propose_only_loop(), this function evaluates each proposal against the
    worker's sub-cohort using evaluate_experiment_in_memory(). Only KEEP proposals
    are returned, and the baseline config is updated after each KEEP so subsequent
    proposals build on prior improvements.

    This eliminates the coordinator bottleneck: workers do both proposal generation
    AND evaluation in parallel, and the coordinator only validates the pre-filtered
    winners on the full cohort.

    Args:
        eval_cohort: List of tickers in this worker's sub-cohort.
        propose_fn: Callable(gap, graveyard_entries) -> ConfigChange.
        ledger: ExperimentLedger instance (read-only in worker mode).
        max_workers: Parallel workers for CQS computation.
        focus_area: Optional focus filter.
        escalation_threshold: Subtype failures before GPT escalation.
        worker_id: Identifier for this worker (for logging).
        checkpoint_interval: Write checkpoint every N proposals evaluated.
        role: Worker role ("combined", "runner", or "evaluator").

    Returns:
        List of EvaluatedProposal for proposals that passed evaluation (KEEP only).
    """
    from edgar.xbrl.standardization.config_loader import get_config
    from edgar.xbrl.standardization.tools.auto_eval_checkpoint import (
        WorkerCheckpoint, GapSummary, write_checkpoint,
    )

    if ledger is None:
        ledger = ExperimentLedger()

    if propose_fn is None:
        propose_fn = propose_change

    prefix = f"[Worker {worker_id}] " if worker_id else ""
    t_session_start = time.time()
    logger.info(f"{prefix}Starting propose_and_evaluate_loop on {len(eval_cohort)} companies")

    # Initialize checkpoint
    cp = WorkerCheckpoint(
        worker_id=worker_id or "anonymous",
        role=role,
        phase="baseline",
        cohort_size=len(eval_cohort),
    )
    if worker_id:
        _safe_write_checkpoint(cp)

    # Load baseline config and compute baseline CQS
    t0 = time.time()
    baseline_config = get_config(reload=True)
    baseline_cqs = compute_cqs(
        eval_cohort=eval_cohort,
        snapshot_mode=True,
        use_ai=False,
        ledger=ledger,
        max_workers=max_workers,
        config=baseline_config,
    )
    t_baseline = time.time() - t0

    cp.baseline_cqs = baseline_cqs.cqs
    cp.current_cqs = baseline_cqs.cqs
    cp.phase = "gaps"
    cp.elapsed_seconds = time.time() - t_session_start
    if worker_id:
        _safe_write_checkpoint(cp)

    # Identify gaps using the baseline config
    t1 = time.time()
    gaps, _ = identify_gaps(
        eval_cohort=eval_cohort,
        snapshot_mode=True,
        ledger=ledger,
        max_workers=max_workers,
        config=baseline_config,
    )
    t_gaps = time.time() - t1

    logger.info(f"{prefix}Found {len(gaps)} gaps (CQS={baseline_cqs.cqs:.4f})")
    logger.info(f"{prefix}Timing: baseline={t_baseline:.1f}s, gaps={t_gaps:.1f}s")

    cp.gaps_found = len(gaps)
    cp.gaps = [GapSummary.from_metric_gap(g) for g in gaps]
    cp.elapsed_seconds = time.time() - t_session_start
    if worker_id:
        _safe_write_checkpoint(cp)

    # Build lookup for updating gap decisions during eval
    _gap_index = {f"{g.ticker}:{g.metric}": i for i, g in enumerate(cp.gaps)}

    # Filter by focus area
    if focus_area:
        gaps = _filter_gaps_by_focus(gaps, focus_area)
        logger.info(f"{prefix}{len(gaps)} gaps after focus filter: {focus_area}")

    if not gaps:
        logger.info(f"{prefix}No gaps to evaluate")
        cp.phase = "finished"
        cp.elapsed_seconds = time.time() - t_session_start
        if worker_id:
            _safe_write_checkpoint(cp)
        return []

    # Generate and evaluate proposals
    evaluated: List[EvaluatedProposal] = []
    tracker = _SubtypeFailureTracker(escalation_threshold=escalation_threshold)
    proposals_evaluated = 0

    for gap in gaps:
        graveyard_entries = ledger.get_graveyard_entries(gap.metric)

        change = propose_fn(gap, graveyard_entries)
        if change is None:
            tracker.record_failure(gap.ticker, gap.metric, gap.hv_subtype)
            continue

        cp.current_gap = f"{gap.ticker}:{gap.metric}"

        # Evaluate in memory (no disk writes)
        result = evaluate_experiment_in_memory(
            change=change,
            baseline_cqs=baseline_cqs,
            baseline_config=baseline_config,
            eval_cohort=eval_cohort,
            ledger=ledger,
        )

        proposals_evaluated += 1

        logger.info(
            f"{prefix}{result.decision.value}: {change.change_type.value} for "
            f"{gap.ticker}:{gap.metric} "
            f"(CQS {result.cqs_before:.4f} -> {result.cqs_after:.4f}, "
            f"{result.duration_seconds:.1f}s)"
        )

        if result.decision == Decision.KEEP:
            cp.keeps += 1
            # Update baseline for next proposal (rolling baseline)
            baseline_config = apply_change_to_config(change, baseline_config)
            # Reuse CQS from evaluate_experiment_in_memory (Phase 1a optimization)
            if result.new_cqs_result is not None:
                baseline_cqs = result.new_cqs_result
            else:
                baseline_cqs = compute_cqs(
                    eval_cohort=eval_cohort,
                    snapshot_mode=True,
                    use_ai=False,
                    ledger=ledger,
                    max_workers=max_workers,
                    config=baseline_config,
                )
            cp.current_cqs = baseline_cqs.cqs

            evaluated.append(EvaluatedProposal(
                gap=gap,
                proposal=change,
                decision=result,
                worker_id=worker_id,
            ))
        elif result.decision == Decision.VETO:
            cp.vetoes += 1
            tracker.record_failure(gap.ticker, gap.metric, gap.hv_subtype)
        else:
            cp.discards += 1
            tracker.record_failure(gap.ticker, gap.metric, gap.hv_subtype)

        # Record decision on the gap summary in the checkpoint
        gap_key = f"{gap.ticker}:{gap.metric}"
        if gap_key in _gap_index:
            cp.gaps[_gap_index[gap_key]].decision = result.decision.value
            cp.gaps[_gap_index[gap_key]].change_type = change.change_type.value

        # Update checkpoint at configured interval
        cp.proposals_total = proposals_evaluated
        cp.phase = f"eval_{proposals_evaluated}"
        cp.elapsed_seconds = time.time() - t_session_start
        if worker_id and (proposals_evaluated % checkpoint_interval == 0):
            _safe_write_checkpoint(cp)

    t_total = time.time() - t_session_start
    logger.info(
        f"{prefix}Finished: {len(evaluated)} KEEPs from {len(gaps)} gaps "
        f"(baseline={t_baseline:.1f}s, gaps={t_gaps:.1f}s, total={t_total:.1f}s)"
    )

    # Final checkpoint
    cp.phase = "finished"
    cp.current_gap = None
    cp.elapsed_seconds = t_total
    if worker_id:
        _safe_write_checkpoint(cp)

    # Auto-save results so TeamSession.collect_results() can find them
    if worker_id and evaluated:
        results_dir = Path(__file__).parent.parent / "company_mappings" / "team_results"
        results_dir.mkdir(parents=True, exist_ok=True)
        save_evaluated_to_json(evaluated, results_dir / f"evaluated_{worker_id}.json")
        logger.info(f"{prefix}Auto-saved {len(evaluated)} results to team_results/evaluated_{worker_id}.json")

    return evaluated


def _safe_write_checkpoint(cp) -> None:
    """Write checkpoint with error suppression (non-critical)."""
    try:
        from edgar.xbrl.standardization.tools.auto_eval_checkpoint import write_checkpoint
        write_checkpoint(cp)
    except Exception as e:
        logger.debug(f"Checkpoint write failed (non-critical): {e}")


def save_proposals_to_json(
    proposals: List[ProposalRecord],
    output_path: Path,
) -> None:
    """Save proposals to a JSON file for coordinator collection."""
    data = [p.to_dict() for p in proposals]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    logger.info(f"Saved {len(proposals)} proposals to {output_path}")


def load_proposals_from_json(input_path: Path) -> List[ProposalRecord]:
    """Load proposals from a worker's JSON output file."""
    with open(input_path, 'r') as f:
        data = json.load(f)

    proposals = []
    for item in data:
        gap_data = item["gap"]
        prop_data = item["proposal"]

        gap = MetricGap(
            ticker=gap_data["ticker"],
            metric=gap_data["metric"],
            gap_type=gap_data["gap_type"],
            estimated_impact=gap_data.get("estimated_impact", 0.0),
            reference_value=gap_data.get("reference_value"),
            xbrl_value=gap_data.get("xbrl_value"),
            hv_subtype=gap_data.get("hv_subtype"),
            current_variance=gap_data.get("current_variance"),
            graveyard_count=gap_data.get("graveyard_count", 0),
            notes=gap_data.get("notes", ""),
        )

        change = ConfigChange(
            file=prop_data["file"],
            change_type=ChangeType(prop_data["change_type"]),
            yaml_path=prop_data["yaml_path"],
            old_value=prop_data.get("old_value"),
            new_value=prop_data["new_value"],
            rationale=prop_data.get("rationale", ""),
            target_metric=prop_data.get("target_metric", ""),
            target_companies=prop_data.get("target_companies", ""),
        )

        proposals.append(ProposalRecord(
            gap=gap,
            proposal=change,
            worker_id=item.get("worker_id", ""),
        ))

    logger.info(f"Loaded {len(proposals)} proposals from {input_path}")
    return proposals


def save_evaluated_to_json(
    proposals: List[EvaluatedProposal],
    output_path: Path,
) -> None:
    """Save evaluated proposals to a JSON file for coordinator collection."""
    data = [p.to_dict() for p in proposals]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    logger.info(f"Saved {len(proposals)} evaluated proposals to {output_path}")


def load_evaluated_from_json(input_path: Path) -> List[EvaluatedProposal]:
    """Load evaluated proposals from a worker's JSON output file."""
    with open(input_path, 'r') as f:
        data = json.load(f)
    proposals = [EvaluatedProposal.from_dict(item) for item in data]
    logger.info(f"Loaded {len(proposals)} evaluated proposals from {input_path}")
    return proposals


# =============================================================================
# PHASE 6: EVALUATOR-ONLY MODE
# =============================================================================

def evaluate_proposals_in_memory(
    proposals: List[ProposalRecord],
    eval_cohort: List[str],
    baseline_config,
    baseline_cqs: CQSResult,
    ledger: Optional[ExperimentLedger] = None,
    worker_id: str = "",
    checkpoint_interval: int = 1,
) -> List[EvaluatedProposal]:
    """Evaluate a batch of pre-built proposals in-memory. Returns only KEEPs.

    This is the pure evaluator function — it receives proposals (from runners)
    and evaluates each on a sub-cohort. Unlike propose_and_evaluate_loop(),
    this skips gap identification and proposal generation.

    Args:
        proposals: Pre-built proposals to evaluate.
        eval_cohort: List of tickers for evaluation.
        baseline_config: In-memory MappingConfig snapshot.
        baseline_cqs: CQS baseline for comparison.
        ledger: ExperimentLedger for golden master lookups.
        worker_id: Identifier for this evaluator (for logging/checkpoints).
        checkpoint_interval: Write checkpoint every N proposals.

    Returns:
        List of EvaluatedProposal for proposals that passed (KEEP only).
    """
    from edgar.xbrl.standardization.tools.auto_eval_checkpoint import (
        WorkerCheckpoint, GapSummary, write_checkpoint,
    )

    if ledger is None:
        ledger = ExperimentLedger()

    prefix = f"[Evaluator {worker_id}] " if worker_id else ""
    t_start = time.time()
    logger.info(f"{prefix}Evaluating {len(proposals)} proposals on {len(eval_cohort)} companies")

    cp = WorkerCheckpoint(
        worker_id=worker_id or "anonymous",
        role="evaluator",
        phase="eval_0",
        cohort_size=len(eval_cohort),
        gaps_found=len(proposals),
        baseline_cqs=baseline_cqs.cqs,
        current_cqs=baseline_cqs.cqs,
        gaps=[GapSummary.from_metric_gap(r.gap) for r in proposals],
    )
    _gap_index = {f"{r.gap.ticker}:{r.gap.metric}": i for i, r in enumerate(proposals)}
    if worker_id:
        _safe_write_checkpoint(cp)

    evaluated: List[EvaluatedProposal] = []
    current_config = baseline_config
    current_cqs = baseline_cqs

    for i, record in enumerate(proposals):
        cp.current_gap = f"{record.gap.ticker}:{record.gap.metric}"

        result = evaluate_experiment_in_memory(
            change=record.proposal,
            baseline_cqs=current_cqs,
            baseline_config=current_config,
            eval_cohort=eval_cohort,
            ledger=ledger,
        )

        logger.info(
            f"{prefix}{result.decision.value}: {record.proposal.change_type.value} for "
            f"{record.gap.ticker}:{record.gap.metric} "
            f"(CQS {result.cqs_before:.4f} -> {result.cqs_after:.4f}, "
            f"{result.duration_seconds:.1f}s)"
        )

        if result.decision == Decision.KEEP:
            cp.keeps += 1
            current_config = apply_change_to_config(record.proposal, current_config)
            # Reuse CQS from evaluate_experiment_in_memory (Phase 1a optimization)
            if result.new_cqs_result is not None:
                current_cqs = result.new_cqs_result
            else:
                current_cqs = compute_cqs(
                    eval_cohort=eval_cohort,
                    snapshot_mode=True,
                    use_ai=False,
                    ledger=ledger,
                    config=current_config,
                )
            cp.current_cqs = current_cqs.cqs

            evaluated.append(EvaluatedProposal(
                gap=record.gap,
                proposal=record.proposal,
                decision=result,
                worker_id=worker_id,
            ))
        elif result.decision == Decision.VETO:
            cp.vetoes += 1
        else:
            cp.discards += 1

        # Record decision on the gap summary
        gap_key = f"{record.gap.ticker}:{record.gap.metric}"
        if gap_key in _gap_index:
            cp.gaps[_gap_index[gap_key]].decision = result.decision.value
            cp.gaps[_gap_index[gap_key]].change_type = record.proposal.change_type.value

        cp.proposals_total = i + 1
        cp.phase = f"eval_{i + 1}"
        cp.elapsed_seconds = time.time() - t_start
        if worker_id and ((i + 1) % checkpoint_interval == 0):
            _safe_write_checkpoint(cp)

    cp.phase = "finished"
    cp.current_gap = None
    cp.elapsed_seconds = time.time() - t_start
    if worker_id:
        _safe_write_checkpoint(cp)

    logger.info(f"{prefix}Finished: {len(evaluated)} KEEPs from {len(proposals)} proposals")
    return evaluated


# =============================================================================
# PHASE 7: TEAM SESSION COORDINATOR
# =============================================================================

class TeamSession:
    """Coordinator for agent team auto-eval sessions.

    The team lead creates a session, gets worker assignments, launches
    agents, then collects and validates results.

    Usage:
        session = TeamSession(eval_cohort=EXPANSION_COHORT_100, num_workers=5)
        session.establish_baseline()
        assignments = session.get_worker_assignments()
        # ... user launches agents ...
        results = session.collect_results()
        report = session.validate_winners(results)
    """

    def __init__(self, eval_cohort: List[str], num_workers: int = 3, ledger=None):
        self.session_id = f"team_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.eval_cohort = eval_cohort
        self.num_workers = num_workers
        self.ledger = ledger or ExperimentLedger()
        self.subcohorts = generate_subcohorts(eval_cohort, k=num_workers, ledger=self.ledger)
        self.baseline_config = None
        self.baseline_cqs = None
        self._results_dir = Path(__file__).parent.parent / "company_mappings" / "team_results"
        self._results_dir.mkdir(parents=True, exist_ok=True)

    def establish_baseline(self, max_workers: int = 4) -> CQSResult:
        """Compute full-cohort baseline. Call once at session start."""
        from edgar.xbrl.standardization.config_loader import get_config

        self.baseline_config = get_config(reload=True)
        self.baseline_cqs = compute_cqs(
            eval_cohort=self.eval_cohort,
            config=self.baseline_config,
            snapshot_mode=True,
            ledger=self.ledger,
            max_workers=max_workers,
        )
        logger.info(
            f"[TeamSession {self.session_id}] Baseline established: "
            f"CQS={self.baseline_cqs.cqs:.4f} on {len(self.eval_cohort)} companies"
        )
        return self.baseline_cqs

    def get_worker_assignments(self) -> List[Dict]:
        """Return assignment dicts for the team lead to dispatch agents."""
        return [
            {
                "worker_id": f"worker_{chr(65 + i)}",  # worker_A, worker_B, ...
                "eval_cohort": subcohort,
                "cohort_size": len(subcohort),
                "role": "combined",
            }
            for i, subcohort in enumerate(self.subcohorts)
        ]

    def collect_results(self, results_dir: Optional[Path] = None) -> List[EvaluatedProposal]:
        """Collect EvaluatedProposal results from worker output files or checkpoint dir."""
        search_dir = results_dir or self._results_dir
        all_results: List[EvaluatedProposal] = []

        if not search_dir.exists():
            logger.warning(f"Results directory not found: {search_dir}")
            return all_results

        for path in sorted(search_dir.glob("evaluated_worker_*.json")):
            try:
                proposals = load_evaluated_from_json(path)
                all_results.extend(proposals)
                logger.info(f"Collected {len(proposals)} results from {path.name}")
            except Exception as e:
                logger.error(f"Failed to load results from {path}: {e}")

        logger.info(f"[TeamSession] Collected {len(all_results)} total results from workers")
        return all_results

    def validate_winners(
        self,
        proposals: List[EvaluatedProposal],
        max_workers: int = 4,
    ) -> OvernightReport:
        """Validate worker-approved proposals on FULL cohort.

        De-duplicates conflicting proposals, then evaluates winners using
        batched evaluation for non-conflicting company-scoped changes (Phase 2b)
        and sequential evaluation for global-scoped changes.

        Args:
            proposals: EvaluatedProposal results from workers.
            max_workers: Parallel workers for CQS computation.

        Returns:
            OvernightReport summarizing the session.
        """
        if self.baseline_config is None or self.baseline_cqs is None:
            raise RuntimeError("Must call establish_baseline() before validate_winners()")

        started_at = datetime.now().isoformat()
        t_start = time.time()

        # De-duplicate: extract ConfigChange objects, select non-conflicting
        changes = [p.proposal for p in proposals]
        non_conflicting = select_non_conflicting(changes)
        logger.info(
            f"[TeamSession] Validating {len(non_conflicting)} non-conflicting proposals "
            f"(from {len(proposals)} worker results) on full {len(self.eval_cohort)}-company cohort"
        )

        # Phase 2b: Split into batchable (company-scoped) and sequential (global)
        company_scoped = []
        global_scoped = []
        for change in non_conflicting:
            if is_change_company_scoped(change):
                company_scoped.append(change)
            else:
                global_scoped.append(change)

        logger.info(
            f"[TeamSession] Proposal split: {len(company_scoped)} company-scoped (batchable), "
            f"{len(global_scoped)} global-scoped (sequential)"
        )

        current_config = self.baseline_config
        current_cqs = self.baseline_cqs
        kept = []
        discarded = 0
        vetoed = 0
        cqs_peak = current_cqs.cqs

        # --- Batch evaluate company-scoped proposals ---
        if company_scoped:
            batch_config = current_config
            for change in company_scoped:
                batch_config = apply_change_to_config(change, batch_config)

            try:
                batch_cqs = compute_cqs_incremental_batch(
                    baseline_result=current_cqs,
                    changes=company_scoped,
                    config=batch_config,
                    eval_cohort=self.eval_cohort,
                    ledger=self.ledger,
                    max_workers=max_workers,
                )
                # Check: batch improved or held steady AND no regressions
                if not batch_cqs.vetoed and batch_cqs.cqs >= current_cqs.cqs - 0.0001:
                    # Batch success — keep all
                    current_config = batch_config
                    current_cqs = batch_cqs
                    kept.extend(company_scoped)
                    cqs_peak = max(cqs_peak, current_cqs.cqs)
                    logger.info(
                        f"[TeamSession] BATCH KEEP: {len(company_scoped)} company-scoped proposals "
                        f"-> CQS={current_cqs.cqs:.4f}"
                    )
                else:
                    # Batch failed — fall back to individual evaluation
                    logger.info(
                        f"[TeamSession] Batch evaluation regressed "
                        f"({current_cqs.cqs:.4f} -> {batch_cqs.cqs:.4f}), "
                        f"falling back to individual evaluation"
                    )
                    for change in company_scoped:
                        result = evaluate_experiment_in_memory(
                            change=change,
                            baseline_cqs=current_cqs,
                            baseline_config=current_config,
                            eval_cohort=self.eval_cohort,
                            ledger=self.ledger,
                        )
                        if result.decision == Decision.KEEP:
                            current_config = apply_change_to_config(change, current_config)
                            if result.new_cqs_result is not None:
                                current_cqs = result.new_cqs_result
                            kept.append(change)
                            cqs_peak = max(cqs_peak, current_cqs.cqs)
                            logger.info(f"[TeamSession] KEEP: {change.target_metric} -> CQS={current_cqs.cqs:.4f}")
                        elif result.decision == Decision.VETO:
                            vetoed += 1
                            logger.info(f"[TeamSession] VETO: {change.target_metric}")
                        else:
                            discarded += 1
                            logger.info(f"[TeamSession] DISCARD: {change.target_metric}")
            except Exception as e:
                logger.warning(f"[TeamSession] Batch evaluation error: {e}, falling back to sequential")
                for change in company_scoped:
                    result = evaluate_experiment_in_memory(
                        change=change,
                        baseline_cqs=current_cqs,
                        baseline_config=current_config,
                        eval_cohort=self.eval_cohort,
                        ledger=self.ledger,
                    )
                    if result.decision == Decision.KEEP:
                        current_config = apply_change_to_config(change, current_config)
                        if result.new_cqs_result is not None:
                            current_cqs = result.new_cqs_result
                        kept.append(change)
                        cqs_peak = max(cqs_peak, current_cqs.cqs)
                    elif result.decision == Decision.VETO:
                        vetoed += 1
                    else:
                        discarded += 1

        # --- Sequential evaluation for global-scoped proposals ---
        for change in global_scoped:
            result = evaluate_experiment_in_memory(
                change=change,
                baseline_cqs=current_cqs,
                baseline_config=current_config,
                eval_cohort=self.eval_cohort,
                ledger=self.ledger,
            )

            if result.decision == Decision.KEEP:
                current_config = apply_change_to_config(change, current_config)
                if result.new_cqs_result is not None:
                    current_cqs = result.new_cqs_result
                else:
                    current_cqs = compute_cqs(
                        eval_cohort=self.eval_cohort,
                        snapshot_mode=True,
                        use_ai=False,
                        ledger=self.ledger,
                        max_workers=max_workers,
                        config=current_config,
                    )
                kept.append(change)
                cqs_peak = max(cqs_peak, current_cqs.cqs)
                logger.info(f"[TeamSession] KEEP: {change.target_metric} -> CQS={current_cqs.cqs:.4f}")
            elif result.decision == Decision.VETO:
                vetoed += 1
                logger.info(f"[TeamSession] VETO: {change.target_metric}")
            else:
                discarded += 1
                logger.info(f"[TeamSession] DISCARD: {change.target_metric}")

        duration_hours = (time.time() - t_start) / 3600

        report = OvernightReport(
            session_id=self.session_id,
            started_at=started_at,
            finished_at=datetime.now().isoformat(),
            duration_hours=duration_hours,
            focus_area=None,
            experiments_total=len(non_conflicting),
            experiments_kept=len(kept),
            experiments_discarded=discarded,
            experiments_vetoed=vetoed,
            cqs_start=self.baseline_cqs.cqs,
            cqs_end=current_cqs.cqs,
            cqs_peak=cqs_peak,
            config_diffs=[c.to_diff_string() for c in kept],
        )

        # Expose validated changes so the coordinator can apply them
        self._validated_changes = kept

        logger.info(
            f"[TeamSession] Validation complete: {len(kept)}/{len(non_conflicting)} kept, "
            f"CQS {self.baseline_cqs.cqs:.4f} -> {current_cqs.cqs:.4f}"
        )
        return report

    def shutdown(self):
        """Clean up resources (persistent pool, etc.)."""
        from edgar.xbrl.standardization.orchestrator import shutdown_persistent_pool
        shutdown_persistent_pool()
        logger.info(f"[TeamSession] Session {self.session_id} shut down")

    def dashboard(self) -> str:
        """Print current team status from checkpoint files."""
        from edgar.xbrl.standardization.tools.auto_eval_checkpoint import print_team_dashboard
        print_team_dashboard()
        return "Dashboard printed"
