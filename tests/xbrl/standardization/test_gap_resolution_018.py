"""
Verification tests for Gap Resolution 018 — Config-Only Gap Fixes.

Tests cover:
- Banking CurrentAssets/CurrentLiabilities forbidden_metrics
- WMT ResearchAndDevelopment exclude_metrics
- JNJ Capex known_divergence
- Derivation planner for WMT:GrossProfit and WMT:TotalLiabilities
"""
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock

import pytest
import yaml
from pathlib import Path

pytestmark = pytest.mark.fast

CONFIG_DIR = Path(__file__).resolve().parents[3] / "edgar" / "xbrl" / "standardization" / "config"


# =============================================================================
# Stage 1A: Banking forbidden_metrics includes CurrentAssets/CurrentLiabilities
# =============================================================================

class TestBankingForbiddenMetrics:
    """CurrentAssets and CurrentLiabilities should be forbidden for banking companies."""

    def test_banking_forbidden_includes_current_assets(self):
        config = yaml.safe_load((CONFIG_DIR / "industry_metrics.yaml").read_text())
        forbidden = config["banking"]["forbidden_metrics"]
        assert "CurrentAssets" in forbidden, (
            "CurrentAssets must be in banking forbidden_metrics — "
            "banks use liquidity-based balance sheets"
        )

    def test_banking_forbidden_includes_current_liabilities(self):
        config = yaml.safe_load((CONFIG_DIR / "industry_metrics.yaml").read_text())
        forbidden = config["banking"]["forbidden_metrics"]
        assert "CurrentLiabilities" in forbidden, (
            "CurrentLiabilities must be in banking forbidden_metrics — "
            "banks use liquidity-based balance sheets"
        )

    def test_current_assets_forbidden_for_banking_company(self):
        """_is_metric_forbidden_fast returns True for JPM + CurrentAssets."""
        import edgar.xbrl.standardization.tools.auto_eval as ae
        from edgar.xbrl.standardization.tools.auto_eval import _is_metric_forbidden_fast

        ae._industry_metrics_cache = None

        mock_config = MagicMock()
        mock_company = MagicMock()
        mock_company.industry = "banking"
        mock_config.get_company.return_value = mock_company

        assert _is_metric_forbidden_fast("CurrentAssets", "JPM", mock_config) is True

    def test_current_assets_not_forbidden_for_non_banking(self):
        """CurrentAssets is valid for non-banking companies."""
        from edgar.xbrl.standardization.tools.auto_eval import _is_metric_forbidden_fast

        mock_config = MagicMock()
        mock_company = MagicMock()
        mock_company.industry = ""
        mock_config.get_company.return_value = mock_company

        assert _is_metric_forbidden_fast("CurrentAssets", "AAPL", mock_config) is False


# =============================================================================
# Stage 1B: WMT excludes ResearchAndDevelopment
# =============================================================================

class TestWMTExcludeMetrics:
    """WMT should exclude ResearchAndDevelopment — retailer with no material R&D."""

    def test_wmt_excludes_research_and_development(self):
        config = yaml.safe_load((CONFIG_DIR / "companies.yaml").read_text())
        wmt = config["companies"]["WMT"]
        assert "exclude_metrics" in wmt, "WMT must have exclude_metrics"
        assert "ResearchAndDevelopment" in wmt["exclude_metrics"], (
            "ResearchAndDevelopment must be excluded for WMT"
        )


# =============================================================================
# Stage 1C: JNJ Capex known_divergence
# =============================================================================

class TestJNJCapexDivergence:
    """JNJ should have Capex as a known_divergence (pharma capex structure)."""

    def test_jnj_capex_known_divergence(self):
        config = yaml.safe_load((CONFIG_DIR / "companies.yaml").read_text())
        jnj = config["companies"]["JNJ"]
        assert "known_divergences" in jnj
        assert "Capex" in jnj["known_divergences"], (
            "Capex must be a known_divergence for JNJ"
        )

    def test_jnj_capex_divergence_reason_mentions_pharma(self):
        config = yaml.safe_load((CONFIG_DIR / "companies.yaml").read_text())
        capex = config["companies"]["JNJ"]["known_divergences"]["Capex"]
        assert "pharma" in capex["reason"].lower() or "intangible" in capex["reason"].lower(), (
            "JNJ Capex divergence reason should explain pharma/intangible investment"
        )

    def test_jnj_capex_divergence_is_wont_fix(self):
        config = yaml.safe_load((CONFIG_DIR / "companies.yaml").read_text())
        capex = config["companies"]["JNJ"]["known_divergences"]["Capex"]
        assert capex["remediation_status"] == "wont_fix"


# =============================================================================
# Stage 3: JPM:ShareRepurchases known_divergence
# =============================================================================

class TestJPMShareRepurchasesDivergence:
    """JPM:ShareRepurchases should be a known_divergence (structural mismatch)."""

    def test_jpm_share_repurchases_known_divergence(self):
        config = yaml.safe_load((CONFIG_DIR / "companies.yaml").read_text())
        jpm = config["companies"]["JPM"]
        assert "known_divergences" in jpm
        assert "ShareRepurchases" in jpm["known_divergences"]

    def test_jpm_share_repurchases_is_wont_fix(self):
        config = yaml.safe_load((CONFIG_DIR / "companies.yaml").read_text())
        sr = config["companies"]["JPM"]["known_divergences"]["ShareRepurchases"]
        assert sr["remediation_status"] == "wont_fix"


# =============================================================================
# Derivation planner: WMT:GrossProfit and WMT:TotalLiabilities
# =============================================================================

class TestDerivationPlanner:
    """Derivation planner should propose formulas when components are resolved."""

    def test_derivation_wmt_gross_profit(self):
        """GrossProfit = Revenue - COGS should produce complete proposal."""
        from edgar.xbrl.standardization.tools.derivation_planner import (
            derive_formula_from_identity,
        )

        @dataclass
        class MockResult:
            concept: Optional[str] = None

        results = {
            "Revenue": MockResult(concept="us-gaap:Revenues"),
            "COGS": MockResult(concept="us-gaap:CostOfGoodsSold"),
        }

        proposal = derive_formula_from_identity("WMT", "GrossProfit", results)
        assert proposal is not None
        assert proposal.is_complete
        assert proposal.confidence == 1.0
        assert "Revenue" in proposal.formula
        assert "COGS" in proposal.formula
        assert proposal.components["Revenue"] == "us-gaap:Revenues"
        assert proposal.components["COGS"] == "us-gaap:CostOfGoodsSold"

    def test_derivation_wmt_total_liabilities(self):
        """TotalLiabilities = TotalAssets - StockholdersEquity should produce complete proposal."""
        from edgar.xbrl.standardization.tools.derivation_planner import (
            derive_formula_from_identity,
        )

        @dataclass
        class MockResult:
            concept: Optional[str] = None

        results = {
            "TotalAssets": MockResult(concept="us-gaap:Assets"),
            "StockholdersEquity": MockResult(concept="us-gaap:StockholdersEquity"),
        }

        proposal = derive_formula_from_identity("WMT", "TotalLiabilities", results)
        assert proposal is not None
        assert proposal.is_complete
        assert proposal.confidence == 1.0
        assert len(proposal.missing_components) == 0

    def test_derivation_incomplete_when_component_missing(self):
        """Proposal should be incomplete when a component is not resolved."""
        from edgar.xbrl.standardization.tools.derivation_planner import (
            derive_formula_from_identity,
        )

        @dataclass
        class MockResult:
            concept: Optional[str] = None

        results = {
            "Revenue": MockResult(concept="us-gaap:Revenues"),
            # COGS not resolved
        }

        proposal = derive_formula_from_identity("WMT", "GrossProfit", results)
        assert proposal is not None
        assert not proposal.is_complete
        assert "COGS" in proposal.missing_components
        assert proposal.confidence == 0.5
