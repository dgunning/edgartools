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
