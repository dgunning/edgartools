"""Single write path for per-company JSON overrides.

All expansion pipeline config changes go through this module.
Worktree-safe: only writes to per-company JSON files, never to shared YAML.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger(__name__)

_DEFAULT_CONFIG_DIR = Path(__file__).parent.parent / "config"


def _load_override(ticker: str, config_dir: Path = _DEFAULT_CONFIG_DIR) -> Dict[str, Any]:
    """Load existing JSON override for a company, or return empty dict."""
    json_path = config_dir / "company_overrides" / f"{ticker}.json"
    try:
        return json.loads(json_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_override(ticker: str, data: Dict[str, Any], config_dir: Path = _DEFAULT_CONFIG_DIR):
    """Write JSON override for a company."""
    overrides_dir = config_dir / "company_overrides"
    overrides_dir.mkdir(exist_ok=True)
    json_path = overrides_dir / f"{ticker}.json"
    json_path.write_text(json.dumps(data, indent=2))


def apply_action_to_json(
    action: Dict[str, Any],
    config_dir: Path = _DEFAULT_CONFIG_DIR,
) -> None:
    """Apply a typed action dict to per-company JSON override.

    action keys: action, ticker, metric, params
    Supported actions: EXCLUDE_METRIC, DOCUMENT_DIVERGENCE, MAP_CONCEPT,
                       FIX_SIGN_CONVENTION, SET_INDUSTRY
    """
    ticker = action["ticker"]
    metric = action["metric"]
    action_type = action["action"]
    params = action.get("params", {})

    data = _load_override(ticker, config_dir)

    if action_type == "EXCLUDE_METRIC":
        data.setdefault("exclude_metrics", {})[metric] = {
            "reason": params.get("reason", "not_applicable"),
            "notes": params.get("notes", "Auto-applied by expansion pipeline"),
        }

    elif action_type == "DOCUMENT_DIVERGENCE":
        data.setdefault("known_divergences", {})[metric] = {
            "variance_pct": params.get("variance_pct", 0.0),
            "reason": params.get("reason", ""),
            "skip_validation": True,
            "added_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "remediation_status": "deferred",
        }

    elif action_type == "MAP_CONCEPT":
        data.setdefault("metric_overrides", {}).setdefault(metric, {})["preferred_concept"] = params["concept"]

    elif action_type == "FIX_SIGN_CONVENTION":
        data.setdefault("metric_overrides", {}).setdefault(metric, {})["sign_negate"] = True

    elif action_type == "SET_INDUSTRY":
        data["industry"] = params["industry"]

    else:
        log.warning(f"Unknown action type: {action_type}")
        return

    _save_override(ticker, data, config_dir)
    log.info(f"Applied {action_type} for {ticker}:{metric} to JSON override")


def revert_action(
    action: Dict[str, Any],
    config_dir: Path = _DEFAULT_CONFIG_DIR,
) -> None:
    """Remove a specific action's effect from per-company JSON override."""
    ticker = action["ticker"]
    metric = action["metric"]
    action_type = action["action"]

    data = _load_override(ticker, config_dir)

    if action_type == "EXCLUDE_METRIC":
        data.get("exclude_metrics", {}).pop(metric, None)
    elif action_type == "DOCUMENT_DIVERGENCE":
        data.get("known_divergences", {}).pop(metric, None)
    elif action_type == "MAP_CONCEPT":
        overrides = data.get("metric_overrides", {}).get(metric, {})
        overrides.pop("preferred_concept", None)
        if not overrides:
            data.get("metric_overrides", {}).pop(metric, None)
    elif action_type == "FIX_SIGN_CONVENTION":
        overrides = data.get("metric_overrides", {}).get(metric, {})
        overrides.pop("sign_negate", None)
        if not overrides:
            data.get("metric_overrides", {}).pop(metric, None)

    _save_override(ticker, data, config_dir)
    log.info(f"Reverted {action_type} for {ticker}:{metric}")
