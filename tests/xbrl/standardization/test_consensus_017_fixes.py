"""
Verification tests for Consensus 017 post-review fixes.

Fix 1: O57 CQS scoring — forbidden metrics excluded from CQS scoring (not just gap list)
Fix 2: O55 derivation planner wiring — propose_change uses derivation planner
Fix 3: Divergence safety guardrail — prevents premature divergence annotations
"""
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.fast


# =============================================================================
# Fix 1: O57 CQS Scoring — Forbidden Metrics Excluded
# =============================================================================

class TestFix1ForbiddenMetricsCQSScoring:
    """Forbidden metrics should be excluded from CQS scoring like CONFIG exclusions."""

    def test_forbidden_metrics_excluded_from_cqs_scoring(self):
        """When forbidden_metrics is passed, those metrics are treated like CONFIG exclusions."""
        from edgar.xbrl.standardization.tools.auto_eval import _compute_company_cqs
        from edgar.xbrl.standardization.models import MappingResult, MappingSource

        # Build metrics dict with a forbidden metric (GrossProfit) that would normally fail
        metrics = {
            "Revenue": MappingResult(
                metric="Revenue", company="XOM", fiscal_period="2024-FY",
                concept="us-gaap:Revenues",
                source=MappingSource.TREE, value=100_000,
                validation_status="valid",
            ),
            "GrossProfit": MappingResult(
                metric="GrossProfit", company="XOM", fiscal_period="2024-FY",
                concept=None,
                source=MappingSource.TREE, value=None,
                validation_status="invalid",
            ),
        }

        golden_set = set()
        validations = {}

        # Without forbidden_metrics: GrossProfit counts as a failure
        score_without = _compute_company_cqs("XOM", metrics, golden_set, validations)

        # With forbidden_metrics: GrossProfit is excluded
        score_with = _compute_company_cqs(
            "XOM", metrics, golden_set, validations,
            forbidden_metrics={"GrossProfit"},
        )

        # GrossProfit should count as excluded (like CONFIG), not as a failure
        assert score_with.metrics_excluded > score_without.metrics_excluded
        # EF-CQS should be higher because the forbidden metric isn't penalizing
        assert score_with.ef_cqs >= score_without.ef_cqs

    def test_forbidden_metrics_none_is_no_op(self):
        """Default forbidden_metrics=None preserves existing behavior."""
        from edgar.xbrl.standardization.tools.auto_eval import _compute_company_cqs
        from edgar.xbrl.standardization.models import MappingResult, MappingSource

        metrics = {
            "Revenue": MappingResult(
                metric="Revenue", company="AAPL", fiscal_period="2024-FY",
                concept="us-gaap:Revenues",
                source=MappingSource.TREE, value=100_000,
                validation_status="valid",
            ),
        }

        golden_set = set()
        validations = {}

        # Both should produce identical results
        score_default = _compute_company_cqs("AAPL", metrics, golden_set, validations)
        score_explicit_none = _compute_company_cqs(
            "AAPL", metrics, golden_set, validations, forbidden_metrics=None,
        )

        assert score_default.ef_cqs == score_explicit_none.ef_cqs
        assert score_default.metrics_total == score_explicit_none.metrics_total


# =============================================================================
# Fix 2: O55 Derivation Planner Wiring
# =============================================================================

class TestFix2DerivationPlannerWiring:
    """propose_change should use the derivation planner for identity-based metrics."""

    def test_metric_gap_has_company_results_field(self):
        """MetricGap should have an optional company_results field."""
        from edgar.xbrl.standardization.tools.auto_eval import MetricGap

        gap = MetricGap(
            ticker="WMT", metric="GrossProfit",
            gap_type="unmapped", estimated_impact=0.01,
        )
        assert gap.company_results is None  # Default is None

        gap.company_results = {"Revenue": MagicMock()}
        assert gap.company_results is not None

    def test_propose_change_uses_derivation_planner(self):
        """Gap with company_results and complete identity → returns ADD_STANDARDIZATION."""
        from edgar.xbrl.standardization.tools.auto_eval import MetricGap
        from edgar.xbrl.standardization.tools.auto_eval_loop import propose_change, ChangeType
        from edgar.xbrl.standardization.models import MappingResult, MappingSource

        # Build company_results where Revenue and COGS are both resolved
        company_results = {
            "Revenue": MappingResult(
                metric="Revenue", company="WMT", fiscal_period="2024-FY",
                concept="us-gaap:Revenues",
                source=MappingSource.TREE, value=500_000,
                validation_status="valid",
            ),
            "COGS": MappingResult(
                metric="COGS", company="WMT", fiscal_period="2024-FY",
                concept="us-gaap:CostOfGoodsSold",
                source=MappingSource.TREE, value=350_000,
                validation_status="valid",
            ),
        }

        gap = MetricGap(
            ticker="WMT", metric="GrossProfit",
            gap_type="unmapped", estimated_impact=0.02,
            company_results=company_results,
        )

        change = propose_change(gap, graveyard_entries=[])
        assert change is not None
        assert change.change_type == ChangeType.ADD_STANDARDIZATION
        assert "GrossProfit" in change.rationale
        assert "derivation" in change.rationale.lower()

    def test_propose_change_falls_through_on_incomplete_derivation(self):
        """Gap with missing components → falls through to solver/other strategy."""
        from edgar.xbrl.standardization.tools.auto_eval import MetricGap
        from edgar.xbrl.standardization.tools.auto_eval_loop import propose_change, ChangeType

        # Revenue resolved but COGS missing → derivation incomplete
        company_results = {
            "Revenue": MagicMock(concept="us-gaap:Revenues"),
        }

        gap = MetricGap(
            ticker="WMT", metric="GrossProfit",
            gap_type="unmapped", estimated_impact=0.02,
            company_results=company_results,
        )

        # Should NOT return ADD_STANDARDIZATION (derivation incomplete)
        with patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop._propose_for_unmapped",
            return_value=None,
        ), patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop._is_metric_forbidden",
            return_value=False,
        ):
            change = propose_change(gap, graveyard_entries=[])
            # May return None or a non-derivation proposal
            if change is not None:
                assert change.change_type != ChangeType.ADD_STANDARDIZATION


# =============================================================================
# Fix 3: Divergence Safety Guardrail
# =============================================================================

class TestFix3DivergenceGuardrail:
    """Divergence annotations require prior concept-level attempts."""

    def test_should_allow_divergence_blocked_with_zero_attempts(self):
        """Empty graveyard → divergence blocked."""
        from edgar.xbrl.standardization.tools.auto_eval import MetricGap
        from edgar.xbrl.standardization.tools.auto_eval_loop import _should_allow_divergence

        gap = MetricGap(
            ticker="JNJ", metric="NetIncome",
            gap_type="regression", estimated_impact=0.01,
        )
        assert _should_allow_divergence(gap, graveyard_entries=[]) is False

    def test_should_allow_divergence_blocked_with_one_attempt(self):
        """One concept attempt → still blocked (need >= 2)."""
        from edgar.xbrl.standardization.tools.auto_eval import MetricGap
        from edgar.xbrl.standardization.tools.auto_eval_loop import _should_allow_divergence

        gap = MetricGap(
            ticker="JNJ", metric="NetIncome",
            gap_type="regression", estimated_impact=0.01,
        )
        graveyard = [
            {"config_diff": "add_concept: us-gaap:NetIncomeLoss", "reason": "wrong concept"},
        ]
        assert _should_allow_divergence(gap, graveyard) is False

    def test_should_allow_divergence_allowed_with_two_attempts(self):
        """Two concept-level attempts → divergence allowed."""
        from edgar.xbrl.standardization.tools.auto_eval import MetricGap
        from edgar.xbrl.standardization.tools.auto_eval_loop import _should_allow_divergence

        gap = MetricGap(
            ticker="JNJ", metric="NetIncome",
            gap_type="regression", estimated_impact=0.01,
        )
        graveyard = [
            {"config_diff": "add_concept: us-gaap:NetIncomeLoss", "reason": "wrong concept"},
            {"config_diff": "add_company_override: preferred_concept=us-gaap:ProfitLoss", "reason": "also wrong"},
        ]
        assert _should_allow_divergence(gap, graveyard) is True

    def test_reference_changed_bypasses_guardrail(self):
        """Regression with 'reference changed' rationale → divergence allowed regardless."""
        from edgar.xbrl.standardization.tools.auto_eval import MetricGap
        from edgar.xbrl.standardization.tools.auto_eval_loop import (
            propose_change, ChangeType, _should_allow_divergence, ConfigChange,
        )

        gap = MetricGap(
            ticker="JNJ", metric="NetIncome",
            gap_type="regression", estimated_impact=0.01,
        )

        # Create a divergence change with "reference changed" rationale
        reference_changed_change = ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.ADD_DIVERGENCE,
            yaml_path="companies.JNJ.known_divergences.NetIncome",
            new_value={"variance_pct": 10.0},
            rationale="Regression: yfinance reference changed, extraction stable",
            target_metric="NetIncome",
            target_companies="JNJ",
        )

        # Even with 0 graveyard attempts, "reference changed" should bypass
        with patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop._propose_regression_fix",
            return_value=reference_changed_change,
        ):
            change = propose_change(gap, graveyard_entries=[])
            assert change is not None
            assert change.change_type == ChangeType.ADD_DIVERGENCE

    def test_divergence_blocked_falls_through_to_solver(self):
        """When guardrail blocks divergence, falls through to solver instead."""
        from edgar.xbrl.standardization.tools.auto_eval import MetricGap
        from edgar.xbrl.standardization.tools.auto_eval_loop import (
            propose_change, ChangeType, ConfigChange,
        )

        gap = MetricGap(
            ticker="JNJ", metric="NetIncome",
            gap_type="regression", estimated_impact=0.01,
        )

        # Create a divergence change WITHOUT "reference changed" rationale
        value_drifted_change = ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.ADD_DIVERGENCE,
            yaml_path="companies.JNJ.known_divergences.NetIncome",
            new_value={"variance_pct": 15.0},
            rationale="Regression: extracted value drifted from golden",
            target_metric="NetIncome",
            target_companies="JNJ",
        )

        solver_change = ConfigChange(
            file="metrics.yaml",
            change_type=ChangeType.ADD_CONCEPT,
            yaml_path="metrics.NetIncome.known_concepts",
            new_value="us-gaap:NetIncomeLoss",
            rationale="Solver proposal",
            target_metric="NetIncome",
            target_companies="JNJ",
        )

        # 0 graveyard attempts → divergence blocked → solver called
        with patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop._propose_regression_fix",
            return_value=value_drifted_change,
        ), patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop._propose_via_solver",
            return_value=solver_change,
        ) as mock_solver:
            change = propose_change(gap, graveyard_entries=[])
            mock_solver.assert_called_once_with(gap)
            assert change is not None
            assert change.change_type == ChangeType.ADD_CONCEPT
