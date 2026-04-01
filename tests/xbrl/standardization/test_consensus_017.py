"""
Verification tests for Consensus 017 (O53-O58) — Autonomous Structural Gap Resolution.

Tests cover:
- O54: add_divergence is company-scoped (not global)
- O57: Energy archetype pre-exclusion in identify_gaps()
- O53: Gate applicability per change type (EF/SA decoupling)
- O56: Tree structure in AI evidence pack
- O55: Derivation planner for computed metrics
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.fast


# =============================================================================
# O54: add_divergence is company-scoped
# =============================================================================

class TestO54DivergenceScoping:
    """add_divergence should be in _COMPANY_SCOPED_CHANGES, not _GLOBAL_SCOPED_CHANGES."""

    def test_add_divergence_is_company_scoped(self):
        from edgar.xbrl.standardization.tools.auto_eval import (
            _COMPANY_SCOPED_CHANGES,
            _GLOBAL_SCOPED_CHANGES,
        )
        assert "add_divergence" in _COMPANY_SCOPED_CHANGES, (
            "add_divergence must be company-scoped (it modifies companies.yaml)"
        )
        assert "add_divergence" not in _GLOBAL_SCOPED_CHANGES, (
            "add_divergence must NOT be in global-scoped changes"
        )

    def test_is_change_company_scoped_for_divergence(self):
        from edgar.xbrl.standardization.tools.auto_eval import is_change_company_scoped

        mock_change = MagicMock()
        mock_change.change_type.value = "add_divergence"
        mock_change.target_companies = "JNJ"
        assert is_change_company_scoped(mock_change) is True

    def test_lis_handles_divergence_transition(self):
        """LIS should detect metric transitioning from failing to explained."""
        from edgar.xbrl.standardization.tools.auto_eval import (
            CompanyCQS, CQSResult, LISResult, compute_lis,
        )

        baseline_company = CompanyCQS(
            ticker="JNJ", pass_rate=0.80, mean_variance=5.0,
            coverage_rate=0.90, golden_master_rate=0.50,
            regression_count=0, metrics_total=20,
            metrics_mapped=18, metrics_valid=16, metrics_excluded=0,
            cqs=0.80, failed_metrics=["Capex", "GrossProfit"],
        )
        baseline = CQSResult(
            pass_rate=0.80, mean_variance=5.0, coverage_rate=0.90,
            golden_master_rate=0.50, regression_rate=0.0, cqs=0.80,
            companies_evaluated=1, total_metrics=20, total_mapped=18,
            total_valid=16, total_regressions=0,
            company_scores={"JNJ": baseline_company},
        )

        # After divergence: Capex is explained, removed from failed_metrics
        new_company = CompanyCQS(
            ticker="JNJ", pass_rate=0.85, mean_variance=5.0,
            coverage_rate=0.90, golden_master_rate=0.50,
            regression_count=0, metrics_total=20,
            metrics_mapped=18, metrics_valid=17, metrics_excluded=0,
            cqs=0.85, failed_metrics=["GrossProfit"],
        )

        result = compute_lis(baseline, "JNJ", "Capex", new_company)

        assert result.target_metric_improved is True, "Capex should be improved (removed from failed)"
        assert result.zero_regressions is True
        assert result.lis_pass is True, "LIS should pass for divergence fix"


# =============================================================================
# O57: Energy archetype pre-exclusion
# =============================================================================

class TestO57EnergyArchetype:
    """Energy archetype should exist and forbidden metrics should be pre-excluded."""

    def test_energy_archetype_exists(self):
        """industry_metrics.yaml must have an energy section."""
        import yaml
        from pathlib import Path

        path = Path(__file__).parents[3] / "edgar" / "xbrl" / "standardization" / "config" / "industry_metrics.yaml"
        with open(path) as f:
            config = yaml.safe_load(f)

        assert "energy" in config, "Energy archetype must exist in industry_metrics.yaml"
        energy = config["energy"]
        assert "forbidden_metrics" in energy
        assert "GrossProfit" in energy["forbidden_metrics"]

    def test_is_metric_forbidden_fast_energy(self):
        """GrossProfit should be forbidden for energy companies."""
        import edgar.xbrl.standardization.tools.auto_eval as ae
        from edgar.xbrl.standardization.tools.auto_eval import _is_metric_forbidden_fast

        # Reset the module-level cache so it picks up current YAML
        ae._industry_metrics_cache = None

        # Mock config with XOM as energy company
        mock_config = MagicMock()
        mock_company = MagicMock()
        mock_company.industry = "energy"
        mock_config.get_company.return_value = mock_company

        assert _is_metric_forbidden_fast("GrossProfit", "XOM", mock_config) is True

    def test_is_metric_forbidden_fast_non_energy(self):
        """GrossProfit should NOT be forbidden for non-energy companies."""
        from edgar.xbrl.standardization.tools.auto_eval import _is_metric_forbidden_fast

        mock_config = MagicMock()
        mock_company = MagicMock()
        mock_company.industry = ""
        mock_config.get_company.return_value = mock_company

        assert _is_metric_forbidden_fast("GrossProfit", "AAPL", mock_config) is False

    def test_is_metric_forbidden_fast_no_company(self):
        """Unknown companies should not have forbidden metrics."""
        from edgar.xbrl.standardization.tools.auto_eval import _is_metric_forbidden_fast

        mock_config = MagicMock()
        mock_config.get_company.return_value = None

        assert _is_metric_forbidden_fast("GrossProfit", "UNKNOWN", mock_config) is False

    def test_revenue_not_forbidden_for_energy(self):
        """Revenue is valid even for energy companies."""
        import edgar.xbrl.standardization.tools.auto_eval as ae
        from edgar.xbrl.standardization.tools.auto_eval import _is_metric_forbidden_fast

        ae._industry_metrics_cache = None

        mock_config = MagicMock()
        mock_company = MagicMock()
        mock_company.industry = "energy"
        mock_config.get_company.return_value = mock_company

        assert _is_metric_forbidden_fast("Revenue", "XOM", mock_config) is False


# =============================================================================
# O53: Gate applicability per change type
# =============================================================================

class TestO53GateApplicability:
    """EF/SA gates should be selectively applied based on change type."""

    def test_gate_applicability_map_exists(self):
        from edgar.xbrl.standardization.tools.auto_eval_loop import _GATE_APPLICABILITY
        assert isinstance(_GATE_APPLICABILITY, dict)

    def test_divergence_skips_ef_and_sa(self):
        from edgar.xbrl.standardization.tools.auto_eval_loop import _GATE_APPLICABILITY
        assert _GATE_APPLICABILITY["add_divergence"] == set()

    def test_exclusion_skips_ef_and_sa(self):
        from edgar.xbrl.standardization.tools.auto_eval_loop import _GATE_APPLICABILITY
        assert _GATE_APPLICABILITY["add_exclusion"] == set()

    def test_concept_has_ef_only(self):
        from edgar.xbrl.standardization.tools.auto_eval_loop import _GATE_APPLICABILITY
        assert _GATE_APPLICABILITY["add_concept"] == {"ef"}

    def test_standardization_has_sa_only(self):
        from edgar.xbrl.standardization.tools.auto_eval_loop import _GATE_APPLICABILITY
        assert _GATE_APPLICABILITY["add_standardization"] == {"sa"}

    def test_sa_cqs_tolerance_exists(self):
        from edgar.xbrl.standardization.tools.auto_eval_loop import SA_CQS_TOLERANCE
        assert SA_CQS_TOLERANCE == 0.001

    def test_change_passed_to_decision_gates(self):
        """evaluate_experiment_in_memory must pass change= to _apply_decision_gates."""
        import inspect
        from edgar.xbrl.standardization.tools.auto_eval_loop import evaluate_experiment_in_memory

        source = inspect.getsource(evaluate_experiment_in_memory)
        assert "change=change" in source, (
            "Bug fix O53: evaluate_experiment_in_memory must pass change=change "
            "to _apply_decision_gates"
        )

    def test_divergence_bypasses_ef_gate(self):
        """A divergence change should KEEP even when EF-CQS regresses."""
        from edgar.xbrl.standardization.tools.auto_eval import (
            CompanyCQS, CQSResult, LISResult,
        )
        from edgar.xbrl.standardization.tools.auto_eval_loop import (
            _apply_decision_gates, Decision,
        )

        baseline = CQSResult(
            pass_rate=0.80, mean_variance=5.0, coverage_rate=0.90,
            golden_master_rate=0.50, regression_rate=0.0, cqs=0.82,
            companies_evaluated=5, total_metrics=100, total_mapped=90,
            total_valid=80, total_regressions=0,
            ef_cqs=0.85, sa_cqs=0.80,
            company_scores={"JNJ": CompanyCQS(
                ticker="JNJ", pass_rate=0.80, mean_variance=5.0,
                coverage_rate=0.90, golden_master_rate=0.50,
                regression_count=0, metrics_total=20, metrics_mapped=18,
                metrics_valid=16, metrics_excluded=0, cqs=0.80,
            )},
        )
        # EF-CQS drops significantly (would normally DISCARD)
        new = CQSResult(
            pass_rate=0.82, mean_variance=5.0, coverage_rate=0.90,
            golden_master_rate=0.50, regression_rate=0.0, cqs=0.83,
            companies_evaluated=5, total_metrics=100, total_mapped=90,
            total_valid=82, total_regressions=0,
            ef_cqs=0.84,  # EF dropped by 0.01 (> 0.001 tolerance)
            sa_cqs=0.80,
            company_scores={"JNJ": CompanyCQS(
                ticker="JNJ", pass_rate=0.85, mean_variance=5.0,
                coverage_rate=0.90, golden_master_rate=0.50,
                regression_count=0, metrics_total=20, metrics_mapped=18,
                metrics_valid=17, metrics_excluded=0, cqs=0.85,
            )},
        )

        mock_change = MagicMock()
        mock_change.change_type.value = "add_divergence"
        mock_change.target_metric = "Capex"

        lis = LISResult(
            target_improved=True, target_metric_improved=True,
            zero_regressions=True, lis_pass=True,
            target_delta_pp=5.0, detail="Capex fixed",
        )

        result = _apply_decision_gates(
            baseline, new, True, ["JNJ"], 5.0, 1.0,
            change=mock_change, lis_result=lis,
        )
        assert result.decision == Decision.KEEP, (
            f"Divergence should bypass EF gate and KEEP, got: {result.reason}"
        )

    def test_concept_change_blocked_by_ef_regression(self):
        """A concept change should be DISCARDED when EF-CQS regresses."""
        from edgar.xbrl.standardization.tools.auto_eval import (
            CompanyCQS, CQSResult, LISResult,
        )
        from edgar.xbrl.standardization.tools.auto_eval_loop import (
            _apply_decision_gates, Decision,
        )

        baseline = CQSResult(
            pass_rate=0.80, mean_variance=5.0, coverage_rate=0.90,
            golden_master_rate=0.50, regression_rate=0.0, cqs=0.82,
            companies_evaluated=5, total_metrics=100, total_mapped=90,
            total_valid=80, total_regressions=0,
            ef_cqs=0.85, sa_cqs=0.80,
            company_scores={"AAPL": CompanyCQS(
                ticker="AAPL", pass_rate=0.80, mean_variance=5.0,
                coverage_rate=0.90, golden_master_rate=0.50,
                regression_count=0, metrics_total=20, metrics_mapped=18,
                metrics_valid=16, metrics_excluded=0, cqs=0.80,
            )},
        )
        new = CQSResult(
            pass_rate=0.82, mean_variance=5.0, coverage_rate=0.90,
            golden_master_rate=0.50, regression_rate=0.0, cqs=0.83,
            companies_evaluated=5, total_metrics=100, total_mapped=90,
            total_valid=82, total_regressions=0,
            ef_cqs=0.84,  # EF dropped by 0.01
            sa_cqs=0.80,
            company_scores={"AAPL": CompanyCQS(
                ticker="AAPL", pass_rate=0.85, mean_variance=5.0,
                coverage_rate=0.90, golden_master_rate=0.50,
                regression_count=0, metrics_total=20, metrics_mapped=18,
                metrics_valid=17, metrics_excluded=0, cqs=0.85,
            )},
        )

        mock_change = MagicMock()
        mock_change.change_type.value = "add_concept"
        mock_change.target_metric = "Revenue"

        lis = LISResult(
            target_improved=True, target_metric_improved=True,
            zero_regressions=True, lis_pass=True,
            target_delta_pp=5.0, detail="Revenue fixed",
        )

        result = _apply_decision_gates(
            baseline, new, True, ["AAPL"], 5.0, 1.0,
            change=mock_change, lis_result=lis,
        )
        assert result.decision == Decision.DISCARD, (
            f"Concept change should be blocked by EF regression, got: {result.reason}"
        )


# =============================================================================
# O56: Tree structure in AI evidence pack
# =============================================================================

class TestO56EvidencePack:
    """_build_candidates_context() should include tree structure and relationship info."""

    def test_tree_structure_included(self):
        """When candidates have tree_context, output should include tree structure."""
        from edgar.xbrl.standardization.tools.consult_ai_gaps import _build_candidates_context

        mock_gap = MagicMock()
        mock_gap.metric = "GrossProfit"
        mock_gap.ticker = "WMT"
        mock_gap.reference_value = 100000000

        mock_parent = MagicMock()
        mock_parent.element_id = "us-gaap_OperatingIncomeLoss"

        mock_candidate = MagicMock()
        mock_candidate.concept = "us-gaap:CostOfRevenue"
        mock_candidate.source = "calc_tree"
        mock_candidate.confidence = 0.9
        mock_candidate.extracted_value = 95000000
        mock_candidate.delta_pct = 5.0
        mock_candidate.tree_context = {
            'parent': mock_parent,
            'weight': -1.0,
            'statement': 'IncomeStatement',
        }

        with patch(
            'edgar.xbrl.standardization.tools.discover_concepts.discover_concepts',
            return_value=[mock_candidate]
        ), patch(
            'edgar.xbrl.standardization.tools.consult_ai_gaps._get_statement_family_for_metric',
            return_value=None
        ):
            text, candidates = _build_candidates_context(mock_gap)

        assert "## Calculation Tree Structure" in text
        assert "us-gaap_OperatingIncomeLoss" in text

    def test_accounting_relationships_included(self):
        """GrossProfit should show Revenue and COGS as related metrics when candidates exist."""
        from edgar.xbrl.standardization.tools.consult_ai_gaps import _build_candidates_context

        mock_gap = MagicMock()
        mock_gap.metric = "GrossProfit"
        mock_gap.ticker = "WMT"
        mock_gap.reference_value = 100000000

        mock_candidate = MagicMock()
        mock_candidate.concept = "us-gaap:CostOfRevenue"
        mock_candidate.source = "calc_tree"
        mock_candidate.confidence = 0.9
        mock_candidate.extracted_value = 95000000
        mock_candidate.delta_pct = 5.0
        mock_candidate.tree_context = None

        with patch(
            'edgar.xbrl.standardization.tools.discover_concepts.discover_concepts',
            return_value=[mock_candidate]
        ), patch(
            'edgar.xbrl.standardization.tools.consult_ai_gaps._get_statement_family_for_metric',
            return_value=None
        ):
            text, candidates = _build_candidates_context(mock_gap)

        assert "## Accounting Relationships" in text
        assert "Revenue" in text
        assert "COGS" in text


# =============================================================================
# O55: Derivation planner
# =============================================================================

class TestO55DerivationPlanner:
    """Derivation planner resolves computed metrics from accounting identities."""

    def test_accounting_identities_defined(self):
        from edgar.xbrl.standardization.tools.derivation_planner import ACCOUNTING_IDENTITIES
        assert "GrossProfit" in ACCOUNTING_IDENTITIES
        assert "TotalLiabilities" in ACCOUNTING_IDENTITIES
        assert "TotalDebt" in ACCOUNTING_IDENTITIES

    def test_gross_profit_identity(self):
        from edgar.xbrl.standardization.tools.derivation_planner import ACCOUNTING_IDENTITIES
        identity = ACCOUNTING_IDENTITIES["GrossProfit"]
        components = {metric: sign for metric, sign in identity}
        assert components == {"Revenue": 1, "COGS": -1}

    def test_derive_complete_proposal(self):
        """When all components are resolved, proposal should be complete."""
        from edgar.xbrl.standardization.tools.derivation_planner import derive_formula_from_identity

        results = {
            "Revenue": MagicMock(concept="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"),
            "COGS": MagicMock(concept="us-gaap:CostOfGoodsAndServicesSold"),
        }
        proposal = derive_formula_from_identity("WMT", "GrossProfit", results)

        assert proposal is not None
        assert proposal.is_complete is True
        assert proposal.confidence == 1.0
        assert len(proposal.missing_components) == 0
        assert "Revenue" in proposal.components
        assert "COGS" in proposal.components

    def test_derive_partial_proposal(self):
        """When some components are missing, proposal should be incomplete."""
        from edgar.xbrl.standardization.tools.derivation_planner import derive_formula_from_identity

        results = {
            "Revenue": MagicMock(concept="us-gaap:Revenue"),
            # COGS is missing
        }
        proposal = derive_formula_from_identity("WMT", "GrossProfit", results)

        assert proposal is not None
        assert proposal.is_complete is False
        assert proposal.confidence == 0.5
        assert "COGS" in proposal.missing_components

    def test_derive_unknown_metric_returns_none(self):
        """Metrics without identities should return None."""
        from edgar.xbrl.standardization.tools.derivation_planner import derive_formula_from_identity

        proposal = derive_formula_from_identity("WMT", "Capex", {})
        assert proposal is None

    def test_to_config_change_complete(self):
        """Complete proposals should produce ConfigChange."""
        from edgar.xbrl.standardization.tools.derivation_planner import (
            derive_formula_from_identity, to_config_change,
        )

        results = {
            "Revenue": MagicMock(concept="us-gaap:Revenue"),
            "COGS": MagicMock(concept="us-gaap:CostOfGoodsSold"),
        }
        proposal = derive_formula_from_identity("WMT", "GrossProfit", results)
        change = to_config_change(proposal)

        assert change is not None
        assert change.change_type.value == "add_standardization"
        assert change.target_metric == "GrossProfit"

    def test_to_config_change_incomplete_returns_none(self):
        """Incomplete proposals should not produce ConfigChange."""
        from edgar.xbrl.standardization.tools.derivation_planner import (
            derive_formula_from_identity, to_config_change,
        )

        results = {"Revenue": MagicMock(concept="us-gaap:Revenue")}
        proposal = derive_formula_from_identity("WMT", "GrossProfit", results)
        change = to_config_change(proposal)

        assert change is None

    def test_plan_derivations_topological_order(self):
        """plan_derivations should process in topological order."""
        from edgar.xbrl.standardization.tools.derivation_planner import plan_derivations

        results = {
            "Revenue": MagicMock(concept="us-gaap:Revenue"),
            "COGS": MagicMock(concept="us-gaap:CostOfGoodsSold"),
            "TotalAssets": MagicMock(concept="us-gaap:Assets"),
            "StockholdersEquity": MagicMock(concept="us-gaap:StockholdersEquity"),
        }
        proposals = plan_derivations(
            "WMT", results,
            failed_metrics=["GrossProfit", "TotalLiabilities"],
        )

        assert len(proposals) == 2
        # Both should be complete (all components resolved)
        assert all(p.is_complete for p in proposals)

    def test_resolution_order(self):
        """RESOLUTION_ORDER should have leaf metrics before composites."""
        from edgar.xbrl.standardization.tools.derivation_planner import RESOLUTION_ORDER
        gp_idx = RESOLUTION_ORDER.index("GrossProfit")
        oi_idx = RESOLUTION_ORDER.index("OperatingIncome")
        assert gp_idx < oi_idx, "GrossProfit must resolve before OperatingIncome"
