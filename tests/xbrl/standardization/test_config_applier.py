"""Tests for config_applier and related JSON override functionality."""
import json
import tempfile
from pathlib import Path


def _create_minimal_config(tmp_path, companies_yaml_content=None):
    """Helper: create minimal metrics.yaml + companies.yaml for ConfigLoader."""
    (tmp_path / "metrics.yaml").write_text("version: '1.0'\nmetrics: {}\n")
    companies_yaml = tmp_path / "companies.yaml"
    if companies_yaml_content:
        companies_yaml.write_text(companies_yaml_content)
    else:
        companies_yaml.write_text("version: '1.0'\ncompanies: {}\n")
    (tmp_path / "company_overrides").mkdir(exist_ok=True)


def test_industry_loaded_from_json_override(tmp_path):
    """Amendment 1: industry field should be loadable from JSON override."""
    _create_minimal_config(
        tmp_path,
        "version: '1.0'\ncompanies:\n  TEST:\n    name: Test Corp\n    cik: 12345\n",
    )

    # Create JSON override with industry
    (tmp_path / "company_overrides" / "TEST.json").write_text(json.dumps({"industry": "banking"}))

    from edgar.xbrl.standardization.config_loader import ConfigLoader
    loader = ConfigLoader(config_dir=tmp_path)
    config = loader.load()

    assert config.get_company("TEST").industry == "banking"


def test_update_company_tiers_writes_json_not_yaml(tmp_path):
    """Amendment 1: update_company_tiers should write to JSON overrides, not companies.yaml."""
    import yaml
    from unittest.mock import MagicMock

    _create_minimal_config(
        tmp_path,
        yaml.dump({
            "version": "1.0",
            "companies": {"AAPL": {"name": "Apple", "cik": 320193}}
        }),
    )

    # Mock CQSResult with one company
    cqs_result = MagicMock()
    company_score = MagicMock()
    company_score.ef_cqs = 0.96
    company_score.headline_ef_rate = 0.99
    cqs_result.company_scores = {"AAPL": company_score}

    from edgar.xbrl.standardization.tools.auto_eval import update_company_tiers
    tiers = update_company_tiers(cqs_result, dry_run=False, config_dir=tmp_path)

    # JSON override should have quality_tier
    json_path = tmp_path / "company_overrides" / "AAPL.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert data["quality_tier"] == "verified"

    # companies.yaml should NOT have quality_tier
    yaml_data = yaml.safe_load((tmp_path / "companies.yaml").read_text())
    assert "quality_tier" not in yaml_data["companies"]["AAPL"]


def test_apply_exclusion_to_json(tmp_path):
    """Apply EXCLUDE_METRIC writes to per-company JSON override."""
    overrides_dir = tmp_path / "company_overrides"
    overrides_dir.mkdir()

    from edgar.xbrl.standardization.tools.config_applier import apply_action_to_json

    action = {
        "action": "EXCLUDE_METRIC",
        "ticker": "HD",
        "metric": "ResearchAndDevelopment",
        "params": {"reason": "not_applicable", "notes": "Retail company, no R&D"},
    }
    apply_action_to_json(action, config_dir=tmp_path)

    data = json.loads((overrides_dir / "HD.json").read_text())
    assert "ResearchAndDevelopment" in data["exclude_metrics"]
    assert data["exclude_metrics"]["ResearchAndDevelopment"]["reason"] == "not_applicable"


def test_apply_divergence_to_json(tmp_path):
    """Apply DOCUMENT_DIVERGENCE writes to per-company JSON override."""
    overrides_dir = tmp_path / "company_overrides"
    overrides_dir.mkdir()

    from edgar.xbrl.standardization.tools.config_applier import apply_action_to_json

    action = {
        "action": "DOCUMENT_DIVERGENCE",
        "ticker": "HD",
        "metric": "PropertyPlantEquipment",
        "params": {"reason": "Operating lease ROU assets included in yfinance", "variance_pct": 18.3},
    }
    apply_action_to_json(action, config_dir=tmp_path)

    data = json.loads((overrides_dir / "HD.json").read_text())
    assert "PropertyPlantEquipment" in data["known_divergences"]
    assert data["known_divergences"]["PropertyPlantEquipment"]["variance_pct"] == 18.3


def test_apply_concept_override_to_json(tmp_path):
    """Apply MAP_CONCEPT for high_variance writes preferred_concept override."""
    overrides_dir = tmp_path / "company_overrides"
    overrides_dir.mkdir()

    from edgar.xbrl.standardization.tools.config_applier import apply_action_to_json

    action = {
        "action": "MAP_CONCEPT",
        "ticker": "HD",
        "metric": "CashAndEquivalents",
        "params": {"concept": "CashAndCashEquivalentsAtCarryingValue"},
    }
    apply_action_to_json(action, config_dir=tmp_path)

    data = json.loads((overrides_dir / "HD.json").read_text())
    assert data["metric_overrides"]["CashAndEquivalents"]["preferred_concept"] == "CashAndCashEquivalentsAtCarryingValue"


def test_apply_preserves_existing_json(tmp_path):
    """Applying new action preserves existing JSON content."""
    overrides_dir = tmp_path / "company_overrides"
    overrides_dir.mkdir()
    (overrides_dir / "HD.json").write_text(json.dumps({
        "quality_tier": "provisional",
        "exclude_metrics": {"Inventory": {"reason": "not_applicable", "notes": "existing"}}
    }))

    from edgar.xbrl.standardization.tools.config_applier import apply_action_to_json

    action = {
        "action": "EXCLUDE_METRIC",
        "ticker": "HD",
        "metric": "ResearchAndDevelopment",
        "params": {"reason": "not_applicable", "notes": "new"},
    }
    apply_action_to_json(action, config_dir=tmp_path)

    data = json.loads((overrides_dir / "HD.json").read_text())
    assert data["quality_tier"] == "provisional"
    assert "Inventory" in data["exclude_metrics"]
    assert "ResearchAndDevelopment" in data["exclude_metrics"]


def test_revert_action(tmp_path):
    """revert_action removes the specific change from JSON."""
    overrides_dir = tmp_path / "company_overrides"
    overrides_dir.mkdir()
    (overrides_dir / "HD.json").write_text(json.dumps({
        "exclude_metrics": {
            "Inventory": {"reason": "not_applicable"},
            "ResearchAndDevelopment": {"reason": "not_applicable"},
        }
    }))

    from edgar.xbrl.standardization.tools.config_applier import revert_action

    action = {
        "action": "EXCLUDE_METRIC",
        "ticker": "HD",
        "metric": "ResearchAndDevelopment",
        "params": {},
    }
    revert_action(action, config_dir=tmp_path)

    data = json.loads((overrides_dir / "HD.json").read_text())
    assert "Inventory" in data["exclude_metrics"]
    assert "ResearchAndDevelopment" not in data["exclude_metrics"]
