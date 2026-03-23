"""
AI Consultation Module: Step 2 of the two-step auto-eval architecture.

Reads a gap manifest (JSON) produced by run_overnight() Step 1, dispatches
each unresolved gap to an AI model for proposal generation, then evaluates
proposals through the standard CQS gates.

Usage inside Claude Code:
    from edgar.xbrl.standardization.tools.consult_ai_gaps import (
        consult_ai_gaps, evaluate_ai_proposals,
        build_agent_prompt, collect_agent_proposals,
    )

    # Step 2a: Generate AI proposals
    proposals = consult_ai_gaps(
        manifest_path=Path("company_mappings/gap_manifests/manifest_xyz.json"),
        ai_caller=lambda prompt, model: mcp__pal__chat(prompt=prompt, model=model),
    )

    # Step 2b: Evaluate through CQS gates
    report = evaluate_ai_proposals(
        proposals_path=Path("company_mappings/gap_manifests/ai_proposals_xyz.json"),
    )
"""

import json
import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from edgar.xbrl.standardization.tools.auto_eval import (
    MetricGap,
    compute_cqs,
)
from edgar.xbrl.standardization.tools.auto_eval_loop import (
    Decision,
    OvernightReport,
    ProposalRecord,
    UnresolvedGap,
    evaluate_experiment,
    get_config_fingerprint,
    load_gap_manifest,
    log_experiment,
    save_proposals_to_json,
    load_proposals_from_json,
    GAP_MANIFESTS_DIR,
    QUICK_EVAL_COHORT,
    parse_gpt_response,
)
from edgar.xbrl.standardization.ledger.schema import ExperimentLedger

logger = logging.getLogger(__name__)


def _select_model(gap: UnresolvedGap) -> str:
    """Select AI model based on gap difficulty and agent type."""
    if gap.difficulty_tier == "hard" or gap.ai_agent_type == "pattern_learner":
        return "opus"
    return "sonnet"


def _metric_gap_from_unresolved(gap: UnresolvedGap) -> MetricGap:
    """Project an UnresolvedGap back to a MetricGap for ProposalRecord."""
    return MetricGap(
        ticker=gap.ticker,
        metric=gap.metric,
        gap_type=gap.gap_type,
        estimated_impact=gap.estimated_impact,
        reference_value=gap.reference_value,
        xbrl_value=gap.xbrl_value,
        hv_subtype=gap.hv_subtype,
        current_variance=gap.current_variance,
        graveyard_count=gap.graveyard_count,
        notes=gap.notes,
    )


def build_consultation_prompt(gap: UnresolvedGap) -> str:
    """Build a structured prompt for AI consultation.

    Refactored from _consult_gpt() to work with denormalized UnresolvedGap
    rather than requiring live MetricGap + SQLite access.
    """
    # Extraction evidence
    if gap.resolution_type != "none":
        evidence_context = (
            f"- Resolution type: {gap.resolution_type}\n"
            f"- Components used: {gap.components_used}\n"
            f"- Components missing: {gap.components_missing}\n"
            f"- Company industry: {gap.company_industry}\n"
        )
    else:
        evidence_context = "- No extraction evidence available\n"

    # Format graveyard history
    if gap.graveyard_entries:
        entries = []
        for entry in gap.graveyard_entries:
            entries.append(
                f"  - config_diff: {entry.get('config_diff', 'N/A')}\n"
                f"    discard_reason: {entry.get('discard_reason', 'N/A')}\n"
                f"    detail: {entry.get('detail', 'N/A')}"
            )
        graveyard_text = "\n".join(entries)
    else:
        graveyard_text = "None"

    # Difficulty context for hard gaps
    difficulty_context = ""
    if gap.difficulty_tier == "hard":
        reasons = []
        if gap.graveyard_count >= 6:
            reasons.append(f"{gap.graveyard_count} prior failures")
        if gap.gap_type == "regression":
            reasons.append("regression gap")
        if gap.root_cause in ("extension_concept", "algebraic_coincidence"):
            reasons.append(f"root cause: {gap.root_cause}")
        difficulty_context = (
            f"\n## Difficulty Assessment\n"
            f"This is a HARD gap ({', '.join(reasons)}). "
            f"Standard approaches have failed. Consider unconventional strategies.\n"
        )

    prompt = f"""You are an XBRL standardization expert. A metric gap resists automated resolution.

## Gap Details
- Ticker: {gap.ticker}, Metric: {gap.metric}
- Reference value (yfinance): {gap.reference_value}
- Extracted value (XBRL): {gap.xbrl_value}
- hv_subtype: {gap.hv_subtype}
- Current variance: {gap.current_variance}%
- Gap type: {gap.gap_type}
- Root cause: {gap.root_cause}
{evidence_context}
{difficulty_context}
## Prior Failed Attempts ({gap.graveyard_count} total)
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

    return prompt


def build_agent_prompt(gap: UnresolvedGap) -> str:
    """Build an enriched prompt for gap-solver or gap-investigator agents.

    Extends build_consultation_prompt() with:
    - Machine-readable gap JSON for structured parsing
    - Tool usage instructions specific to the agent type
    - Config file paths to read
    - Explicit output format requirements
    """
    base_prompt = build_consultation_prompt(gap)
    gap_json = json.dumps(gap.to_dict(), indent=2, default=str)

    if gap.difficulty_tier == "hard":
        tool_instructions = """## Tool Usage Instructions (Opus Investigation)

You have access to powerful investigation tools. Use them IN ORDER:

1. **Read config state** — check what's already mapped in metrics.yaml and companies.yaml
2. **Analyze graveyard** — understand ALL prior failures before trying anything
3. **discover_concepts(ticker, metric)** — find candidate XBRL concepts
4. **verify_mapping(ticker, metric, concept)** — validate candidates against yfinance
5. **learn_mappings(metric, tickers)** — discover cross-company patterns
6. **Load XBRL filing** — examine calculation trees and dimensional data directly:
   ```python
   from edgar import Company
   company = Company(TICKER)
   filing = company.get_filings(form="10-K").latest()
   xbrl = filing.xbrl()
   ```

IMPORTANT: Do NOT re-propose anything found in the graveyard entries above."""
    else:
        tool_instructions = """## Tool Usage Instructions (Sonnet Solver)

Use these tools IN ORDER:

1. **Read config** — check metrics.yaml for current known_concepts
2. **discover_concepts(ticker, metric)** — find candidate XBRL concepts
3. **verify_mapping(ticker, metric, concept)** — validate candidates (variance < 15%)
4. **check_fallback_quality(metric, concept)** — ensure semantic quality before proposing

IMPORTANT: Do NOT re-propose anything found in the graveyard entries above."""

    config_paths = """## Config File Paths

```
edgar/xbrl/standardization/config/metrics.yaml
edgar/xbrl/standardization/config/companies.yaml
```"""

    return f"""{base_prompt}

{tool_instructions}

{config_paths}

## Machine-Readable Gap Context

```json
{gap_json}
```

## REMINDER: Return ONLY a JSON object. No markdown fences, no explanation outside the JSON."""


def collect_agent_proposals(
    responses: List[Tuple[UnresolvedGap, Optional[str]]],
) -> List[ProposalRecord]:
    """Convert raw agent response strings into validated ProposalRecords.

    Args:
        responses: List of (gap, response_text) tuples. response_text may be None
            if the agent failed or returned nothing.

    Returns:
        List of ProposalRecord ready for save_proposals_to_json().
    """
    proposals: List[ProposalRecord] = []

    for gap, response_text in responses:
        if response_text is None:
            logger.info(f"Skipping {gap.ticker}:{gap.metric} — no agent response")
            continue

        change = parse_gpt_response(response_text, gap.ticker, gap.metric)

        if change is None:
            logger.info(f"Skipping {gap.ticker}:{gap.metric} — invalid response")
            continue

        change.source = "ai_agent"
        change.ai_agent_type = gap.ai_agent_type

        model = _select_model(gap)
        worker_id = f"agent_{model}"

        proposals.append(ProposalRecord(
            gap=_metric_gap_from_unresolved(gap),
            proposal=change,
            worker_id=worker_id,
        ))
        logger.info(
            f"Collected proposal for {gap.ticker}:{gap.metric}: "
            f"{change.change_type.value} via {worker_id}"
        )

    logger.info(f"Collected {len(proposals)}/{len(responses)} valid proposals")
    return proposals


def consult_ai_gaps(
    manifest_path: Path,
    ai_caller: Callable[[str, str], Optional[str]],
    max_gaps: int = 0,
) -> List[ProposalRecord]:
    """Generate AI proposals for unresolved gaps from a manifest.

    This is Step 2a of the two-step architecture. It reads a gap manifest,
    builds prompts, calls the AI, and parses responses into ProposalRecords.

    Args:
        manifest_path: Path to the gap manifest JSON.
        ai_caller: Callable(prompt, model) -> response_text.
            In Claude Code, this wraps mcp__pal__chat.
        max_gaps: Max gaps to process (0 = all).

    Returns:
        List of ProposalRecord for successfully parsed AI responses.
    """
    manifest = load_gap_manifest(manifest_path)

    # Config drift check
    current_fingerprint = get_config_fingerprint()
    if current_fingerprint != manifest.config_fingerprint:
        logger.warning(
            f"Config fingerprint drifted since manifest was written "
            f"({manifest.config_fingerprint} -> {current_fingerprint}). "
            f"Proposals may be stale."
        )

    gaps = manifest.gaps
    if max_gaps > 0:
        gaps = gaps[:max_gaps]

    proposals: List[ProposalRecord] = []
    model_counts: Dict[str, int] = {"sonnet": 0, "opus": 0}

    for i, gap in enumerate(gaps):
        model = _select_model(gap)

        logger.info(
            f"[{i+1}/{len(gaps)}] Consulting {model} for "
            f"{gap.ticker}:{gap.metric} ({gap.ai_agent_type})"
        )

        prompt = build_consultation_prompt(gap)

        try:
            response = ai_caller(prompt, model)
        except Exception as e:
            logger.warning(f"AI call failed for {gap.ticker}:{gap.metric}: {e}")
            continue

        if not response:
            logger.warning(f"Empty AI response for {gap.ticker}:{gap.metric}")
            continue

        change = parse_gpt_response(response, gap.ticker, gap.metric)

        if change is not None:
            change.source = "ai_agent"
            change.ai_agent_type = gap.ai_agent_type
            proposals.append(ProposalRecord(
                gap=_metric_gap_from_unresolved(gap),
                proposal=change,
                worker_id=f"agent_{model}",
            ))
            model_counts[model] += 1
            logger.info(f"  -> Proposal: {change.change_type.value} on {change.yaml_path}")
        else:
            logger.info(f"  -> No valid proposal parsed")

    logger.info(
        f"AI consultation complete: {len(proposals)}/{len(gaps)} proposals "
        f"(sonnet={model_counts.get('sonnet', 0)}, opus={model_counts.get('opus', 0)})"
    )

    # Save proposals
    if proposals:
        output_path = GAP_MANIFESTS_DIR / f"ai_proposals_{manifest.session_id}.json"
        save_proposals_to_json(proposals, output_path)

    return proposals


def evaluate_ai_proposals(
    proposals_path: Path,
    eval_cohort: Optional[List[str]] = None,
    max_workers: int = 2,
    ledger: Optional[ExperimentLedger] = None,
) -> OvernightReport:
    """Evaluate AI-generated proposals through CQS gates.

    This is Step 2b. It loads proposals from JSON (produced by consult_ai_gaps)
    and evaluates each through the same evaluate_experiment() gates used by
    deterministic proposals.

    Args:
        proposals_path: Path to the AI proposals JSON file.
        eval_cohort: List of tickers. Defaults to QUICK_EVAL_COHORT.
        max_workers: Parallel workers for CQS computation.
        ledger: ExperimentLedger for experiment logging.

    Returns:
        OvernightReport summarizing the evaluation session.
    """
    if ledger is None:
        ledger = ExperimentLedger()

    cohort = eval_cohort or QUICK_EVAL_COHORT

    proposals = load_proposals_from_json(proposals_path)
    session_id = f"ai_eval_{Path(proposals_path).stem}"

    # Compute baseline
    logger.info(f"Computing baseline CQS on {len(cohort)} companies...")
    baseline = compute_cqs(
        eval_cohort=cohort,
        snapshot_mode=True,
        ledger=ledger,
        max_workers=max_workers,
    )

    report = OvernightReport(
        session_id=session_id,
        started_at="",
        finished_at="",
        duration_hours=0,
        focus_area="ai_consultation",
        cqs_start=baseline.cqs,
        cqs_peak=baseline.cqs,
    )

    current_baseline = baseline

    for i, pr in enumerate(proposals):
        change = pr.proposal
        logger.info(
            f"[{i+1}/{len(proposals)}] Evaluating: "
            f"{change.change_type.value} for {change.target_metric}"
        )

        report.experiments_total += 1
        result = evaluate_experiment(
            change, current_baseline,
            eval_cohort=cohort,
            ledger=ledger,
            max_workers=max_workers,
        )

        log_experiment(change, result, ledger, run_id=session_id)

        if result.decision == Decision.KEEP:
            report.experiments_kept += 1
            report.config_diffs.append(change.to_diff_string())
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
            logger.info(f"  KEPT — CQS now {current_baseline.cqs:.4f}")

        elif result.decision == Decision.VETO:
            report.experiments_vetoed += 1
            logger.warning(f"  VETOED — {result.reason}")

        else:
            report.experiments_discarded += 1
            logger.info(f"  DISCARDED — {result.reason}")

    report.cqs_end = current_baseline.cqs
    logger.info(
        f"AI evaluation complete: "
        f"{report.experiments_kept}/{report.experiments_total} kept, "
        f"CQS {report.cqs_start:.4f} -> {report.cqs_end:.4f}"
    )

    return report
