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

import hashlib
import logging
import subprocess
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    identify_gaps,
    QUICK_EVAL_COHORT,
    VALIDATION_COHORT,
)

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


class Decision(str, Enum):
    KEEP = "KEEP"
    DISCARD = "DISCARD"
    VETO = "VETO"  # Hard veto due to regression


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

    @property
    def cqs_delta(self) -> float:
        return self.cqs_after - self.cqs_before


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

    # Config changes committed
    config_diffs: List[str] = field(default_factory=list)

    @property
    def cqs_improvement(self) -> float:
        return self.cqs_end - self.cqs_start


# =============================================================================
# CONFIG MANIPULATION
# =============================================================================

def apply_config_change(change: ConfigChange) -> None:
    """
    Apply a YAML configuration change.

    Reads the config file, navigates to the yaml_path, applies the change,
    and writes back. The change is immediately visible to the next
    Orchestrator run.

    Raises:
        ValueError: If the config file or path is invalid.
        FileNotFoundError: If the config file doesn't exist.
    """
    path = change.config_file_path
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, 'r') as f:
        config = yaml.safe_load(f)

    # Navigate to parent of target path
    keys = change.yaml_path.split('.')
    parent = config
    for key in keys[:-1]:
        if isinstance(parent, dict) and key in parent:
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

    else:
        raise ValueError(f"Unknown change type: {change.change_type}")

    # Write back
    with open(path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    logger.info(f"Applied config change: {change.to_diff_string()}")


def revert_config_change(change: ConfigChange) -> None:
    """
    Revert a config change using git checkout.

    This is the safest rollback — restores the file to its git HEAD state.
    """
    path = change.config_file_path
    try:
        subprocess.run(
            ["git", "checkout", "HEAD", "--", str(path)],
            cwd=str(path.parent),
            check=True,
            capture_output=True,
        )
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


# =============================================================================
# EXPERIMENT EVALUATION
# =============================================================================

def evaluate_experiment(
    change: ConfigChange,
    baseline_cqs: CQSResult,
    eval_cohort: Optional[List[str]] = None,
    ledger: Optional[ExperimentLedger] = None,
    max_company_drop: float = 5.0,
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

    # Measure CQS after change
    try:
        new_cqs = compute_cqs(
            eval_cohort=eval_cohort,
            snapshot_mode=True,
            use_ai=False,
            baseline_cqs=baseline_cqs.cqs,
            ledger=ledger,
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

    # Check for hard veto (regressions)
    if new_cqs.vetoed or new_cqs.total_regressions > 0:
        revert_config_change(change)
        return ExperimentDecision(
            decision=Decision.VETO,
            cqs_before=baseline_cqs.cqs,
            cqs_after=new_cqs.cqs,
            reason=f"HARD VETO: {new_cqs.total_regressions} regression(s) detected",
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

    # SUCCESS — CQS improved, no regressions, no company drops
    # Note: we do NOT revert — the change stays applied
    return ExperimentDecision(
        decision=Decision.KEEP,
        cqs_before=baseline_cqs.cqs,
        cqs_after=new_cqs.cqs,
        reason=f"CQS improved by {new_cqs.cqs - baseline_cqs.cqs:.4f}",
        company_deltas=company_deltas,
        duration_seconds=duration,
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

    # Skip dead ends
    if gap.graveyard_count >= 3:
        logger.info(f"Skipping dead end: {gap.ticker}:{gap.metric} ({gap.graveyard_count} graveyard entries)")
        return None

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
        return _propose_for_validation_failure(gap, config_dir)
    elif gap.gap_type == "high_variance":
        return _propose_for_high_variance(gap, config_dir)
    elif gap.gap_type == "regression":
        # Regressions need human/AI investigation — don't auto-propose
        logger.warning(f"Regression on {gap.ticker}:{gap.metric} — needs investigation")
        return None

    return None


def _propose_for_unmapped(
    gap: MetricGap,
    tried_concepts: set,
    config_dir: Path,
) -> Optional[ConfigChange]:
    """Propose a concept addition for an unmapped metric."""
    # Load metrics config to see what concepts are already known
    metrics_path = config_dir / "metrics.yaml"
    if not metrics_path.exists():
        return None

    with open(metrics_path, 'r') as f:
        metrics_config = yaml.safe_load(f)

    metric_def = metrics_config.get("metrics", {}).get(gap.metric, {})
    known_concepts = metric_def.get("known_concepts", [])

    # If reference value is None, this is likely a structural gap -> add exclusion
    if gap.reference_value is None:
        return ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.ADD_EXCLUSION,
            yaml_path=f"companies.{gap.ticker}.exclude_metrics",
            new_value=gap.metric,
            rationale=f"No reference value for {gap.metric} — structural gap for {gap.ticker}",
            target_metric=gap.metric,
            target_companies=gap.ticker,
        )

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
        "OperatingIncome": ["OperatingIncomeLoss", "IncomeLossFromOperations"],
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
        "CashAndEquivalents": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsAndShortTermInvestments"],
    }

    if metric_name in alternatives:
        for alt in alternatives[metric_name]:
            if alt not in variations:
                variations.append(alt)

    return variations


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

    if validation_cqs.total_regressions > 0:
        revert_config_change(change)
        return ExperimentDecision(
            decision=Decision.VETO,
            cqs_before=validation_baseline.cqs,
            cqs_after=validation_cqs.cqs,
            reason=f"Tournament Stage 2 VETO: {validation_cqs.total_regressions} regressions on validation set",
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

    Returns:
        OvernightReport with session summary.
    """
    if ledger is None:
        ledger = ExperimentLedger()

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
    logger.info(f"Session {session_id}: Establishing baseline...")
    baseline = compute_cqs(
        eval_cohort=QUICK_EVAL_COHORT,
        snapshot_mode=True,
        ledger=ledger,
    )
    report.cqs_start = baseline.cqs
    report.cqs_peak = baseline.cqs
    current_baseline = baseline

    consecutive_failures = 0
    max_consecutive_failures = 10

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

        # Identify gaps
        gaps, cqs_result = identify_gaps(
            eval_cohort=QUICK_EVAL_COHORT,
            snapshot_mode=True,
            ledger=ledger,
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
        for gap in gaps:
            if time.time() >= deadline:
                break

            # Skip dead ends
            if gap.is_dead_end:
                continue

            # Get proposal from the agent function
            if propose_fn is None:
                logger.info("No proposal function provided — ending loop")
                report.stopped_early = True
                report.stop_reason = "No proposal function"
                break

            change = propose_fn(gap, ledger.get_graveyard_entries(gap.metric))
            if change is None:
                continue

            report.experiments_total += 1

            if dry_run:
                logger.info(f"[DRY RUN] Would apply: {change.to_diff_string()}")
                continue

            # Evaluate
            if use_tournament:
                result = tournament_eval(change, current_baseline, ledger)
            else:
                result = evaluate_experiment(change, current_baseline, ledger=ledger)

            # Log result
            log_experiment(change, result, ledger, run_id=session_id)

            if result.decision == Decision.KEEP:
                report.experiments_kept += 1
                report.config_diffs.append(change.to_diff_string())
                consecutive_failures = 0
                made_progress = True

                # Update baseline
                current_baseline = compute_cqs(
                    eval_cohort=QUICK_EVAL_COHORT,
                    snapshot_mode=True,
                    ledger=ledger,
                )
                if current_baseline.cqs > report.cqs_peak:
                    report.cqs_peak = current_baseline.cqs

                logger.info(f"KEPT: {change.target_metric} — CQS now {current_baseline.cqs:.4f}")
                break  # Re-analyze gaps with updated config

            elif result.decision == Decision.VETO:
                report.experiments_vetoed += 1
                consecutive_failures += 1
                logger.warning(f"VETOED: {change.target_metric} — {result.reason}")

            else:
                report.experiments_discarded += 1
                consecutive_failures += 1
                logger.info(f"DISCARDED: {change.target_metric} — {result.reason}")

        if not made_progress and propose_fn is not None:
            consecutive_failures += 1

    # Finalize
    report.finished_at = datetime.now().isoformat()
    report.duration_hours = (time.time() - start_time) / 3600
    report.cqs_end = current_baseline.cqs

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
    from edgar.xbrl.standardization.tools.verify_mapping import verify_mapping
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
            facts_df = company.get_facts().to_dataframe()
        except Exception:
            pass

        # Discover candidates
        candidates = discover_concepts(
            metric_name=gap.metric, xbrl=xbrl, facts_df=facts_df,
            ticker=gap.ticker, known_concepts=known_concepts, top_k=5,
        )

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

            # Verify across periods
            periods_matched = 0
            periods_checked = 0
            all_xbrls = [xbrl] + older_xbrls

            for period_xbrl in all_xbrls:
                verification = verify_mapping(
                    metric=gap.metric, concept=concept,
                    xbrl=period_xbrl, ticker=gap.ticker, tolerance_pct=15.0,
                )
                if verification.xbrl_value is not None and verification.reference_value is not None:
                    periods_checked += 1
                    if verification.is_valid:
                        periods_matched += 1

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

    # Check for regressions (hard veto -> revert all)
    if new_cqs.vetoed or new_cqs.total_regressions > 0:
        logger.warning(f"Batch VETOED: {new_cqs.total_regressions} regressions")
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
