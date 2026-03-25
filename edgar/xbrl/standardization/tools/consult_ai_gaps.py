"""
AI Consultation Module: Step 2 of the two-step auto-eval architecture.

Reads a gap manifest (JSON) produced by run_overnight() Step 1, dispatches
each unresolved gap to an AI model for proposal generation, then evaluates
proposals through the standard CQS gates.

Usage inside Claude Code:
    from edgar.xbrl.standardization.tools.consult_ai_gaps import (
        consult_ai_gaps, evaluate_ai_proposals,
        build_agent_prompt, collect_agent_proposals,
        save_agent_responses, load_agent_responses,
        run_agent_benchmark, BenchmarkConfig, BenchmarkResult,
        print_benchmark_comparison,
        # AI caller factory
        make_openrouter_caller, MODEL_REGISTRY, DEFAULT_API_MODEL,
        # Typed action pipeline
        TypedAction, ACTION_VOCABULARY,
        parse_typed_action, compile_action, validate_action_preflight,
        build_typed_action_prompt, collect_typed_proposals,
    )

    # Step 2a: Generate AI proposals
    caller, cost_tracker = make_openrouter_caller()
    proposals = consult_ai_gaps(
        manifest_path=Path("company_mappings/gap_manifests/manifest_xyz.json"),
        ai_caller=caller,
    )

    # Step 2b: Evaluate through CQS gates
    report = evaluate_ai_proposals(
        proposals_path=Path("company_mappings/gap_manifests/ai_proposals_xyz.json"),
    )
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from edgar.xbrl.standardization.tools.auto_eval import (
    MetricGap,
    compute_cqs,
)
import yaml

from edgar.xbrl.standardization.tools.auto_eval_loop import (
    ChangeType,
    ConfigChange,
    Decision,
    OvernightReport,
    ProposalRecord,
    TIER1_CONFIGS,
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

# =============================================================================
# MODEL REGISTRY & AI CALLER FACTORY
# =============================================================================

MODEL_REGISTRY = {
    "gemini-flash": "google/gemini-3-flash-preview",
}
DEFAULT_API_MODEL = "gemini-flash"


def make_openrouter_caller(
    default_model: str = DEFAULT_API_MODEL,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> Tuple[Callable[[str, str], Optional[str]], Dict]:
    """Create an AI caller using OpenRouter API.

    Returns (caller, cost_tracker) tuple where caller matches the
    ai_caller contract: Callable[[str, str], Optional[str]].

    Model parameter accepts abstract names (resolved via MODEL_REGISTRY)
    or raw OpenRouter model IDs.

    Requires OPENROUTER_API_KEY environment variable.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "openai package required for OpenRouter caller. "
            "Install with: pip install openai"
        )

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY environment variable not set. "
            "Get your key at: https://openrouter.ai/keys"
        )

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    cost_tracker: Dict[str, Any] = {"total_cost": 0.0, "calls": 0}

    def _call(prompt: str, model: str) -> Optional[str]:
        resolved = MODEL_REGISTRY.get(model, model)
        try:
            response = client.chat.completions.create(
                model=resolved,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            logger.warning(f"  OpenRouter API error: {e}")
            return None

        content = response.choices[0].message.content if response.choices else None

        # Extract cost from OpenRouter usage metadata
        usage = getattr(response, "usage", None)
        if usage:
            raw = getattr(usage, "model_extra", None) or {}
            call_cost = raw.get("cost", 0.0)
            if call_cost:
                cost_tracker["total_cost"] += call_cost
                cost_tracker["calls"] += 1
                logger.info(
                    f"  API cost: ${call_cost:.4f} "
                    f"(cumulative: ${cost_tracker['total_cost']:.4f})"
                )
            else:
                cost_tracker["calls"] += 1

        return content

    return _call, cost_tracker


def _strip_json_fences(text: str) -> str:
    """Remove markdown ```json fences from AI response text."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


# =============================================================================
# TYPED ACTION SCHEMA (Phase 1)
# =============================================================================

ACTION_VOCABULARY = {
    "MAP_CONCEPT": {
        "required_params": ["concept"],
        "description": "Add an XBRL concept to the metric's known_concepts list",
    },
    "ADD_FORMULA": {
        "required_params": ["components", "scope"],
        "description": "Add a composite formula (sum of components)",
    },
    "EXCLUDE_METRIC": {
        "required_params": ["reason_code"],
        "description": "Exclude this metric for this company",
    },
    "DOCUMENT_DIVERGENCE": {
        "required_params": ["reason", "variance_pct"],
        "description": "Document a known divergence between XBRL and yfinance",
    },
    "FIX_SIGN_CONVENTION": {
        "required_params": [],
        "description": "Apply sign negation for inverted XBRL/yfinance convention",
    },
    "SET_INDUSTRY": {
        "required_params": ["industry"],
        "description": "Set the company's industry classification",
    },
    "ESCALATE": {
        "required_params": ["reason"],
        "description": "Flag gap for human review or engine upgrade",
    },
}


@dataclass
class TypedAction:
    """Structured intent from AI — no YAML paths, no file references."""
    action: str
    ticker: str
    metric: str
    params: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    confidence: float = 0.0


def parse_typed_action(
    response_text: str, ticker: str, metric: str,
) -> Optional[TypedAction]:
    """Parse AI response into a TypedAction.

    Extracts JSON from response (handles markdown fences), validates action
    is in ACTION_VOCABULARY, validates required params are present.
    Returns None on parse failure.
    """
    try:
        data = json.loads(_strip_json_fences(response_text))

        action_name = data.get("action", "")
        if action_name not in ACTION_VOCABULARY:
            logger.warning(f"Unknown typed action: {action_name}")
            return None

        vocab_entry = ACTION_VOCABULARY[action_name]
        params = data.get("params", {})

        for req in vocab_entry["required_params"]:
            if req not in params:
                logger.warning(
                    f"TypedAction {action_name} missing required param: {req}"
                )
                return None

        return TypedAction(
            action=action_name,
            ticker=data.get("ticker", ticker),
            metric=data.get("metric", metric),
            params=params,
            rationale=data.get("rationale", ""),
            confidence=float(data.get("confidence", 0.0)),
        )

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse typed action as JSON: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error parsing typed action: {e}")
        return None


# =============================================================================
# ACTION COMPILER (Phase 2)
# =============================================================================

def compile_action(action: TypedAction) -> Optional[ConfigChange]:
    """Translate a TypedAction into a ConfigChange with correct YAML paths.

    This is the layer that knows the config schema. The AI never needs to.
    Returns None for ESCALATE actions (logged, not applied).
    """

    if action.action == "MAP_CONCEPT":
        return ConfigChange(
            file="metrics.yaml",
            change_type=ChangeType.ADD_CONCEPT,
            yaml_path=f"metrics.{action.metric}.known_concepts",
            new_value=action.params["concept"],
            rationale=f"[AI/typed] {action.rationale}",
            target_metric=action.metric,
            target_companies=action.ticker,
            source="ai_agent",
        )

    elif action.action == "ADD_FORMULA":
        scope = action.params.get("scope", "default")
        components = action.params["components"]
        if scope == "company":
            yaml_path = (
                f"metrics.{action.metric}.standardization."
                f"company_overrides.{action.ticker}.components"
            )
        else:
            yaml_path = (
                f"metrics.{action.metric}.standardization.default.components"
            )
        return ConfigChange(
            file="metrics.yaml",
            change_type=ChangeType.ADD_STANDARDIZATION,
            yaml_path=yaml_path,
            new_value=components,
            rationale=f"[AI/typed] {action.rationale}",
            target_metric=action.metric,
            target_companies=action.ticker,
            source="ai_agent",
        )

    elif action.action == "EXCLUDE_METRIC":
        return ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.ADD_EXCLUSION,
            yaml_path=f"companies.{action.ticker}.exclude_metrics",
            new_value=action.metric,
            rationale=f"[AI/typed] {action.rationale}",
            target_metric=action.metric,
            target_companies=action.ticker,
            source="ai_agent",
        )

    elif action.action == "DOCUMENT_DIVERGENCE":
        return ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.ADD_DIVERGENCE,
            yaml_path=f"companies.{action.ticker}.known_divergences.{action.metric}",
            new_value={
                "reason": action.params["reason"],
                "variance_pct": action.params["variance_pct"],
            },
            rationale=f"[AI/typed] {action.rationale}",
            target_metric=action.metric,
            target_companies=action.ticker,
            source="ai_agent",
        )

    elif action.action == "FIX_SIGN_CONVENTION":
        return ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.ADD_COMPANY_OVERRIDE,
            yaml_path=f"companies.{action.ticker}.metric_overrides.{action.metric}",
            new_value={"sign_negate": True},
            rationale=f"[AI/typed] {action.rationale}",
            target_metric=action.metric,
            target_companies=action.ticker,
            source="ai_agent",
        )

    elif action.action == "SET_INDUSTRY":
        return ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.SET_INDUSTRY,
            yaml_path=f"companies.{action.ticker}.industry",
            new_value=action.params["industry"],
            rationale=f"[AI/typed] {action.rationale}",
            target_metric=action.metric,
            target_companies=action.ticker,
            source="ai_agent",
        )

    elif action.action == "ESCALATE":
        logger.info(
            f"ESCALATE for {action.ticker}:{action.metric} — "
            f"{action.params.get('reason', 'no reason')}"
        )
        return None

    else:
        logger.warning(f"Unhandled typed action: {action.action}")
        return None


def _load_metrics_config() -> dict:
    """Load and cache metrics.yaml. Cache is module-level, reset on file change."""
    metrics_path = TIER1_CONFIGS["metrics.yaml"]
    mtime = metrics_path.stat().st_mtime
    if (
        _load_metrics_config._cache is not None
        and _load_metrics_config._mtime == mtime
    ):
        return _load_metrics_config._cache
    with open(metrics_path) as f:
        cfg = yaml.safe_load(f)
    _load_metrics_config._cache = cfg
    _load_metrics_config._mtime = mtime
    return cfg

_load_metrics_config._cache = None
_load_metrics_config._mtime = None


def validate_action_preflight(action: TypedAction) -> Optional[str]:
    """Pre-CQS validation. Returns None if valid, error string if invalid.

    Checks:
    - Duplicate concept (already in known_concepts)
    """
    if action.action == "MAP_CONCEPT":
        try:
            metrics_cfg = _load_metrics_config()
            existing = (
                metrics_cfg.get("metrics", {})
                .get(action.metric, {})
                .get("known_concepts", [])
            )
            if action.params.get("concept") in existing:
                return (
                    f"Concept '{action.params['concept']}' already in "
                    f"{action.metric}.known_concepts"
                )
        except Exception as e:
            logger.debug(f"Preflight concept check failed: {e}")

    return None


# =============================================================================
# SHARED PROMPT HELPERS
# =============================================================================

def _build_evidence_context(gap: UnresolvedGap) -> str:
    """Build the extraction evidence section for AI prompts."""
    if gap.resolution_type != "none":
        return (
            f"- Resolution type: {gap.resolution_type}\n"
            f"- Components used: {gap.components_used}\n"
            f"- Components missing: {gap.components_missing}\n"
            f"- Company industry: {gap.company_industry}\n"
        )
    return "- No extraction evidence available\n"


def _build_graveyard_text(gap: UnresolvedGap) -> str:
    """Format graveyard history for AI prompts."""
    if not gap.graveyard_entries:
        return "None"
    entries = []
    for entry in gap.graveyard_entries:
        entries.append(
            f"  - config_diff: {entry.get('config_diff', 'N/A')}\n"
            f"    discard_reason: {entry.get('discard_reason', 'N/A')}\n"
            f"    detail: {entry.get('detail', 'N/A')}"
        )
    return "\n".join(entries)


def _build_difficulty_context(gap: UnresolvedGap) -> str:
    """Build the difficulty assessment section for hard gaps."""
    if gap.difficulty_tier != "hard":
        return ""
    reasons = []
    if gap.graveyard_count >= 6:
        reasons.append(f"{gap.graveyard_count} prior failures")
    if gap.gap_type == "regression":
        reasons.append("regression gap")
    if gap.root_cause in ("extension_concept", "algebraic_coincidence"):
        reasons.append(f"root cause: {gap.root_cause}")
    return (
        f"\n## Difficulty Assessment\n"
        f"This is a HARD gap ({', '.join(reasons)}). "
        f"Standard approaches have failed. Consider unconventional strategies.\n"
    )


# =============================================================================
# TYPED ACTION PROMPT (Phase 3)
# =============================================================================

def build_typed_action_prompt(gap: UnresolvedGap) -> str:
    """Build an AI prompt that requests a TypedAction JSON response.

    Key differences from build_consultation_prompt():
    - Response format is TypedAction JSON, not ConfigChange JSON
    - Lists available actions from ACTION_VOCABULARY
    - Does NOT include file paths, YAML paths, or config structure
    - Asks for confidence score (0-1)
    """
    evidence_context = _build_evidence_context(gap)
    graveyard_text = _build_graveyard_text(gap)
    difficulty_context = _build_difficulty_context(gap)

    action_lines = []
    for name, spec in ACTION_VOCABULARY.items():
        params_str = ", ".join(spec["required_params"]) if spec["required_params"] else "none"
        action_lines.append(f"- **{name}** (params: {params_str}): {spec['description']}")
    actions_section = "\n".join(action_lines)

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

## Available Actions
{actions_section}

## Engine Capabilities
- The engine supports sign negation via FIX_SIGN_CONVENTION (no params needed).
- Composite formulas sum their components; use ADD_FORMULA for multi-concept metrics.
- ESCALATE if you believe no config change can resolve this gap.

## Response Format (strict JSON only — no markdown fences)
{{
  "action": "MAP_CONCEPT",
  "ticker": "{gap.ticker}",
  "metric": "{gap.metric}",
  "params": {{"concept": "us-gaap:ExampleConcept"}},
  "rationale": "Why this will resolve the gap",
  "confidence": 0.85
}}

## Worked Example
For a gap where XOM:GrossProfit is missing, if you find the XBRL concept
"us-gaap:GrossProfit" reports the correct value:
{{
  "action": "MAP_CONCEPT",
  "ticker": "XOM",
  "metric": "GrossProfit",
  "params": {{"concept": "us-gaap:GrossProfit"}},
  "rationale": "XOM reports GrossProfit directly in XBRL",
  "confidence": 0.90
}}

IMPORTANT: Do NOT re-propose anything found in the prior failed attempts above.
Return ONLY the JSON object."""

    return prompt


def collect_typed_proposals(
    responses: List[Tuple[UnresolvedGap, Optional[str]]],
    session_id: Optional[str] = None,
) -> Tuple[List[ProposalRecord], int]:
    """Convert raw AI responses into ProposalRecords via typed action pipeline.

    Pipeline: raw response -> parse_typed_action() -> compile_action()
    -> validate_action_preflight() -> ProposalRecord

    Args:
        responses: List of (gap, response_text) tuples.
        session_id: If provided, auto-saves raw responses and parsed proposals.

    Returns:
        Tuple of (proposals, preflight_rejected_count).
    """
    proposals: List[ProposalRecord] = []
    preflight_rejected = 0

    for gap, response_text in responses:
        if response_text is None:
            logger.info(f"Skipping {gap.ticker}:{gap.metric} — no agent response")
            continue

        typed_action = parse_typed_action(response_text, gap.ticker, gap.metric)
        if typed_action is None:
            logger.info(f"Skipping {gap.ticker}:{gap.metric} — invalid typed action")
            continue

        change = compile_action(typed_action)
        if change is None:
            logger.info(
                f"Skipping {gap.ticker}:{gap.metric} — "
                f"action {typed_action.action} compiled to None (e.g. ESCALATE)"
            )
            continue

        preflight_err = validate_action_preflight(typed_action)
        if preflight_err is not None:
            preflight_rejected += 1
            logger.info(
                f"Preflight rejected {gap.ticker}:{gap.metric}: {preflight_err}"
            )
            continue

        change.ai_agent_type = gap.ai_agent_type

        model = _select_model(gap)
        worker_id = f"agent_{model}"

        proposals.append(ProposalRecord(
            gap=_metric_gap_from_unresolved(gap),
            proposal=change,
            worker_id=worker_id,
        ))
        logger.info(
            f"Typed proposal for {gap.ticker}:{gap.metric}: "
            f"{typed_action.action} -> {change.change_type.value} via {worker_id}"
        )

    logger.info(f"Collected {len(proposals)}/{len(responses)} typed proposals")

    if session_id is not None:
        save_agent_responses(session_id, responses)
        if proposals:
            output_path = GAP_MANIFESTS_DIR / f"ai_proposals_{session_id}.json"
            save_proposals_to_json(proposals, output_path)

    return proposals, preflight_rejected


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


def _gap_key(gap: UnresolvedGap) -> str:
    """Stable cache key: ticker:metric."""
    return f"{gap.ticker}:{gap.metric}"


def save_agent_responses(
    session_id: str,
    responses: List[Tuple[UnresolvedGap, Optional[str]]],
) -> Path:
    """Save raw agent responses to JSON for caching.

    Args:
        session_id: Session identifier for the cache file.
        responses: List of (gap, response_text) tuples. None responses
            are saved as null (records that the attempt was made).

    Returns:
        Path to the saved JSON file.
    """
    data = [
        {
            "gap_key": _gap_key(gap),
            "response_text": response_text,
        }
        for gap, response_text in responses
    ]
    output_path = GAP_MANIFESTS_DIR / f"agent_responses_{session_id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved {len(data)} agent responses to {output_path}")
    return output_path


def load_agent_responses(session_id: str) -> Dict[str, str]:
    """Load cached agent responses.

    Args:
        session_id: Session identifier matching the cache file.

    Returns:
        Dict mapping gap_key -> response_text. Null responses are excluded
        so that ``key in cache`` means a real answer exists.
        Returns empty dict if the cache file doesn't exist.
    """
    cache_path = GAP_MANIFESTS_DIR / f"agent_responses_{session_id}.json"
    if not cache_path.exists():
        return {}
    with open(cache_path, "r") as f:
        data = json.load(f)
    return {
        entry["gap_key"]: entry["response_text"]
        for entry in data
        if entry["response_text"] is not None
    }


def build_consultation_prompt(gap: UnresolvedGap) -> str:
    """Build a structured prompt for AI consultation.

    Refactored from _consult_gpt() to work with denormalized UnresolvedGap
    rather than requiring live MetricGap + SQLite access.
    """
    evidence_context = _build_evidence_context(gap)
    graveyard_text = _build_graveyard_text(gap)
    difficulty_context = _build_difficulty_context(gap)

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
    session_id: Optional[str] = None,
) -> List[ProposalRecord]:
    """Convert raw agent response strings into validated ProposalRecords.

    Args:
        responses: List of (gap, response_text) tuples. response_text may be None
            if the agent failed or returned nothing.
        session_id: If provided, auto-saves raw responses and parsed proposals.

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

    # Auto-save when session_id is provided
    if session_id is not None:
        save_agent_responses(session_id, responses)
        if proposals:
            output_path = GAP_MANIFESTS_DIR / f"ai_proposals_{session_id}.json"
            save_proposals_to_json(proposals, output_path)

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
            Use make_openrouter_caller() for the default implementation.
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

    from edgar.xbrl.standardization.tools.capability_registry import filter_actionable_gaps

    gaps = manifest.gaps
    if max_gaps > 0:
        gaps = gaps[:max_gaps]

    gaps = filter_actionable_gaps(gaps)

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


# =============================================================================
# BENCHMARK FRAMEWORK
# =============================================================================

COP_OUT_TYPES = {ChangeType.ADD_DIVERGENCE, ChangeType.ADD_EXCLUSION}


@dataclass
class BenchmarkConfig:
    """Configuration for a single benchmark arm."""
    prompt_builder: Callable[[UnresolvedGap], str]
    model: str      # Abstract name from MODEL_REGISTRY or raw model ID
    label: str      # Human-readable name for comparison table
    use_typed_actions: bool = False  # Use typed action pipeline
    backend: str = "api"  # "api" (OpenRouter) or "agent" (Claude Code subagent)


@dataclass
class BenchmarkResult:
    """Results from a single benchmark arm."""
    config: BenchmarkConfig
    total_gaps: int
    valid_proposals: int
    kept: int
    discarded: int
    vetoed: int
    cop_outs: int
    cqs_start: float
    cqs_end: float
    responses: List[Tuple[str, Optional[str]]] = field(default_factory=list)
    preflight_rejected: int = 0

    @property
    def resolution_rate(self) -> float:
        return self.kept / self.total_gaps if self.total_gaps > 0 else 0.0

    @property
    def cop_out_rate(self) -> float:
        return self.cop_outs / self.valid_proposals if self.valid_proposals > 0 else 0.0

    @property
    def cqs_lift(self) -> float:
        return self.cqs_end - self.cqs_start


def _label_slug(label: str) -> str:
    """Convert a human-readable label to a filesystem-safe slug."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def run_agent_benchmark(
    manifest_path: Path,
    configs: List[BenchmarkConfig],
    ai_caller: Callable[[str, str], Optional[str]],
    max_gaps: int = 0,
    eval_cohort: Optional[List[str]] = None,
    max_workers: int = 2,
) -> List[BenchmarkResult]:
    """Run a benchmark comparing (prompt_builder, model) combinations.

    Each config arm is evaluated independently:
    1. Load manifest, check response cache
    2. For uncached gaps: call ai_caller(prompt, config.model)
    3. Save responses to cache
    4. Parse via collect_agent_proposals()
    5. Count cop-outs, evaluate through CQS gates
    6. Return BenchmarkResult per arm

    Args:
        manifest_path: Path to a gap manifest JSON.
        configs: List of BenchmarkConfig arms to compare.
        ai_caller: Callable(prompt, model) -> response_text.
        max_gaps: Max gaps to process per arm (0 = all).
        eval_cohort: Tickers for CQS evaluation. Defaults to QUICK_EVAL_COHORT.
        max_workers: Parallel workers for CQS computation.

    Returns:
        List of BenchmarkResult, one per config arm.
    """
    manifest = load_gap_manifest(manifest_path)
    cohort = eval_cohort or QUICK_EVAL_COHORT

    from edgar.xbrl.standardization.tools.capability_registry import filter_actionable_gaps

    gaps = manifest.gaps
    if max_gaps > 0:
        gaps = gaps[:max_gaps]

    gaps = filter_actionable_gaps(gaps)

    results: List[BenchmarkResult] = []

    for config in configs:
        slug = _label_slug(config.label)
        cache_session = f"{manifest.session_id}_{slug}"

        logger.info(f"=== Benchmark arm: {config.label} (model={config.model}) ===")

        # Check response cache
        cache = load_agent_responses(cache_session)

        # Dispatch uncached gaps
        arm_responses: List[Tuple[UnresolvedGap, Optional[str]]] = []
        for gap in gaps:
            key = _gap_key(gap)
            if key in cache:
                logger.info(f"  Cache hit: {key}")
                arm_responses.append((gap, cache[key]))
            else:
                prompt = config.prompt_builder(gap)
                try:
                    response = ai_caller(prompt, config.model)
                except Exception as e:
                    logger.warning(f"  AI call failed for {key}: {e}")
                    response = None
                arm_responses.append((gap, response))

        # Save all responses to cache
        save_agent_responses(cache_session, arm_responses)

        # Parse proposals — use typed action pipeline or raw pipeline
        preflight_rejected = 0
        if config.use_typed_actions:
            proposals, preflight_rejected = collect_typed_proposals(arm_responses)
        else:
            proposals = collect_agent_proposals(arm_responses)

        # Count cop-outs
        cop_outs = sum(
            1 for pr in proposals
            if pr.proposal.change_type in COP_OUT_TYPES
        )

        # Compute baseline CQS
        ledger = ExperimentLedger()
        baseline = compute_cqs(
            eval_cohort=cohort,
            snapshot_mode=True,
            ledger=ledger,
            max_workers=max_workers,
        )
        cqs_start = baseline.cqs

        # Evaluate each proposal through CQS gates
        kept = 0
        discarded = 0
        vetoed = 0
        current_baseline = baseline

        for pr in proposals:
            result = evaluate_experiment(
                pr.proposal,
                current_baseline,
                eval_cohort=cohort,
                ledger=ledger,
                max_workers=max_workers,
            )

            if result.decision == Decision.KEEP:
                kept += 1
                if result.new_cqs_result is not None:
                    current_baseline = result.new_cqs_result
                else:
                    current_baseline = compute_cqs(
                        eval_cohort=cohort,
                        snapshot_mode=True,
                        ledger=ledger,
                        max_workers=max_workers,
                    )
            elif result.decision == Decision.VETO:
                vetoed += 1
            else:
                discarded += 1

        cqs_end = current_baseline.cqs

        # Store gap_key -> response for the result
        response_pairs = [
            (_gap_key(gap), resp)
            for gap, resp in arm_responses
        ]

        results.append(BenchmarkResult(
            config=config,
            total_gaps=len(gaps),
            valid_proposals=len(proposals),
            kept=kept,
            discarded=discarded,
            vetoed=vetoed,
            cop_outs=cop_outs,
            cqs_start=cqs_start,
            cqs_end=cqs_end,
            responses=response_pairs,
            preflight_rejected=preflight_rejected,
        ))

        logger.info(
            f"  Arm '{config.label}': {kept}/{len(gaps)} kept, "
            f"CQS {cqs_start:.4f} -> {cqs_end:.4f}"
        )

    return results


def print_benchmark_comparison(results: List[BenchmarkResult]) -> None:
    """Print a Rich comparison table of benchmark results."""
    from rich.console import Console
    from rich.table import Table

    table = Table(title="Agent Benchmark Comparison")
    table.add_column("Metric", style="bold")
    for r in results:
        table.add_column(r.config.label, justify="right")

    rows = [
        ("Model", [r.config.model for r in results]),
        ("Total Gaps", [str(r.total_gaps) for r in results]),
        ("Valid Proposals", [str(r.valid_proposals) for r in results]),
        ("Kept", [str(r.kept) for r in results]),
        ("Discarded", [str(r.discarded) for r in results]),
        ("Vetoed", [str(r.vetoed) for r in results]),
        ("Cop-outs", [str(r.cop_outs) for r in results]),
        ("Preflight Rejected", [str(r.preflight_rejected) for r in results]),
        ("Resolution Rate", [f"{r.resolution_rate:.1%}" for r in results]),
        ("Cop-out Rate", [f"{r.cop_out_rate:.1%}" for r in results]),
        ("CQS Start", [f"{r.cqs_start:.4f}" for r in results]),
        ("CQS End", [f"{r.cqs_end:.4f}" for r in results]),
        ("CQS Lift", [f"{r.cqs_lift:+.4f}" for r in results]),
    ]

    for label, values in rows:
        table.add_row(label, *values)

    Console().print(table)
