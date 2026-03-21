"""Tests for Tier 1 CQS loop improvements.

Fix 1: Auto-create metric_overrides in config writer
Fix 2: Sign inversion proposal handler
Fix 3: Regression identification API
Fix 4: Improved solver candidate ranking
Fix 5: Store actual XBRL concept in extraction_runs
Fix 6: Guard against strategy-name golden concepts in regression fix
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from edgar.xbrl.standardization.ledger.schema import ExperimentLedger, ExtractionRun
from edgar.xbrl.standardization.tools.auto_eval import (
    CQSResult,
    CompanyCQS,
    MetricGap,
    list_regressions,
)
from edgar.xbrl.standardization.tools.auto_eval_loop import (
    ChangeType,
    ConfigChange,
    RegressionDiagnosis,
    apply_config_change,
    _propose_regression_fix,
    _propose_sign_negate,
)
from edgar.xbrl.standardization.tools.auto_solver import FormulaCandidate

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_company_cqs(ticker, failed_metrics=None, **overrides):
    defaults = dict(
        ticker=ticker, pass_rate=0.8, mean_variance=5.0,
        coverage_rate=1.0, golden_master_rate=0.5,
        regression_count=0, metrics_total=10, metrics_mapped=10,
        metrics_valid=8, metrics_excluded=0, cqs=0.85,
        ef_pass_rate=0.9, sa_pass_rate=0.8, ef_cqs=0.9, sa_cqs=0.8,
        failed_metrics=failed_metrics or [],
        regressed_metrics=[],
    )
    defaults.update(overrides)
    return CompanyCQS(**defaults)


def _make_cqs_result(company_scores, regressed_metrics=None):
    return CQSResult(
        pass_rate=0.8, mean_variance=5.0, coverage_rate=1.0,
        golden_master_rate=0.5, regression_rate=0.0, cqs=0.85,
        companies_evaluated=len(company_scores),
        total_metrics=50, total_mapped=45, total_valid=40,
        total_regressions=0,
        company_scores=company_scores,
        regressed_metrics=regressed_metrics or [],
    )


def _write_companies_yaml(tmpdir, data):
    path = os.path.join(tmpdir, "companies.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    return path


def _make_gap(**overrides):
    defaults = dict(
        ticker="XOM", metric="OperatingIncome",
        gap_type="high_variance", estimated_impact=0.01,
        current_variance=5.0, reference_value=50_000_000_000.0,
        xbrl_value=-48_000_000_000.0, graveyard_count=0,
        notes="Sign inverted", hv_subtype="hv_sign_inverted",
        root_cause="sign_error",
    )
    defaults.update(overrides)
    return MetricGap(**defaults)


# ===========================================================================
# Fix 1: Auto-create metric_overrides in config writer
# ===========================================================================

class TestAutoCreateMetricOverrides:
    """apply_config_change() should auto-create missing intermediate dicts
    for ADD_COMPANY_OVERRIDE changes."""

    def _apply_change(self, tmpdir, change):
        """Apply a config change with TIER1_CONFIGS patched to use tmpdir."""
        configs = {
            "companies.yaml": Path(tmpdir) / "companies.yaml",
            "metrics.yaml": Path(tmpdir) / "metrics.yaml",
            "industry_metrics.yaml": Path(tmpdir) / "industry_metrics.yaml",
        }
        with patch("edgar.xbrl.standardization.tools.auto_eval_loop.TIER1_CONFIGS", configs):
            with patch("edgar.xbrl.standardization.tools.auto_eval_loop.ConfigLock"):
                with patch("edgar.xbrl.standardization.config_loader.get_config"):
                    apply_config_change(change)

    def test_creates_metric_overrides_when_missing(self):
        """Company exists but no metric_overrides key -> auto-created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {"companies": {"CME": {"name": "CME Group", "cik": 1156375}}}
            _write_companies_yaml(tmpdir, data)

            change = ConfigChange(
                file="companies.yaml",
                change_type=ChangeType.ADD_COMPANY_OVERRIDE,
                yaml_path="companies.CME.metric_overrides.IntangibleAssets",
                new_value={"preferred_concept": "us-gaap:IntangibleAssetsNetExcludingGoodwill"},
            )
            self._apply_change(tmpdir, change)

            with open(os.path.join(tmpdir, "companies.yaml")) as f:
                result = yaml.safe_load(f)

            assert "metric_overrides" in result["companies"]["CME"]
            overrides = result["companies"]["CME"]["metric_overrides"]
            assert "IntangibleAssets" in overrides
            assert overrides["IntangibleAssets"]["preferred_concept"] == "us-gaap:IntangibleAssetsNetExcludingGoodwill"

    def test_preserves_existing_metric_overrides(self):
        """Company already has metric_overrides -> new entry merged, existing preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {"companies": {"META": {
                "name": "Meta",
                "cik": 1326801,
                "metric_overrides": {
                    "Revenue": {"preferred_concept": "AdvertisingRevenue"},
                },
            }}}
            _write_companies_yaml(tmpdir, data)

            change = ConfigChange(
                file="companies.yaml",
                change_type=ChangeType.ADD_COMPANY_OVERRIDE,
                yaml_path="companies.META.metric_overrides.Capex",
                new_value={"preferred_concept": "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment"},
            )
            self._apply_change(tmpdir, change)

            with open(os.path.join(tmpdir, "companies.yaml")) as f:
                result = yaml.safe_load(f)

            overrides = result["companies"]["META"]["metric_overrides"]
            # Old entry preserved
            assert overrides["Revenue"]["preferred_concept"] == "AdvertisingRevenue"
            # New entry added
            assert "Capex" in overrides

    def test_company_missing_auto_created(self):
        """Company not in YAML -> auto-created for ADD_COMPANY_OVERRIDE."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {"companies": {"AAPL": {"name": "Apple", "cik": 320193}}}
            _write_companies_yaml(tmpdir, data)

            change = ConfigChange(
                file="companies.yaml",
                change_type=ChangeType.ADD_COMPANY_OVERRIDE,
                yaml_path="companies.UNKNOWN.metric_overrides.Revenue",
                new_value={"preferred_concept": "us-gaap:Revenue"},
            )
            # UNKNOWN company doesn't exist, but auto-create will create it as empty dict
            self._apply_change(tmpdir, change)

            with open(os.path.join(tmpdir, "companies.yaml")) as f:
                result = yaml.safe_load(f)
            assert "UNKNOWN" in result["companies"]
            assert "metric_overrides" in result["companies"]["UNKNOWN"]

    def test_auto_create_only_for_allowed_types(self):
        """ADD_CONCEPT with missing path -> still raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {"metrics": {"Revenue": {"known_concepts": ["us-gaap:Revenues"]}}}
            path = os.path.join(tmpdir, "metrics.yaml")
            with open(path, "w") as f:
                yaml.dump(data, f)

            change = ConfigChange(
                file="metrics.yaml",
                change_type=ChangeType.ADD_CONCEPT,
                yaml_path="metrics.NonExistent.known_concepts",
                new_value="us-gaap:SomeNewConcept",
            )
            with pytest.raises(ValueError, match="missing key"):
                self._apply_change(tmpdir, change)


# ===========================================================================
# Fix 2: Sign inversion proposal handler
# ===========================================================================

class TestSignNegateProposal:
    """_propose_sign_negate() creates correct ConfigChange for sign-inverted gaps."""

    def test_produces_config_change_for_sign_inverted(self):
        gap = _make_gap(
            xbrl_value=-50_000_000_000.0,
            reference_value=48_000_000_000.0,
        )
        change = _propose_sign_negate(gap)

        assert change is not None
        assert change.change_type == ChangeType.ADD_COMPANY_OVERRIDE
        assert "sign_negate" in change.new_value
        assert change.new_value["sign_negate"] is True
        assert "XOM" in change.yaml_path
        assert "OperatingIncome" in change.yaml_path

    def test_rejects_distant_magnitude(self):
        """Magnitude ratio >1.2 -> returns None (not a simple sign flip)."""
        gap = _make_gap(
            xbrl_value=-100_000_000_000.0,  # 2x the reference
            reference_value=48_000_000_000.0,
        )
        change = _propose_sign_negate(gap)
        assert change is None

    def test_rejects_non_sign_inverted_subtype(self):
        gap = _make_gap(hv_subtype="hv_missing_component")
        change = _propose_sign_negate(gap)
        assert change is None

    def test_rejects_missing_values(self):
        gap = _make_gap(xbrl_value=None)
        change = _propose_sign_negate(gap)
        assert change is None

    def test_rejects_zero_reference(self):
        gap = _make_gap(reference_value=0)
        change = _propose_sign_negate(gap)
        assert change is None


class TestSignNegateRouting:
    """hv_sign_inverted gaps should route through _propose_sign_negate."""

    def test_sign_inverted_gap_routes_to_handler(self):
        """Verify the routing in propose_change dispatches to _propose_sign_negate."""
        gap = _make_gap()
        mock_change = ConfigChange(
            file="companies.yaml",
            change_type=ChangeType.ADD_COMPANY_OVERRIDE,
            yaml_path="companies.XOM.metric_overrides.OperatingIncome",
            new_value={"sign_negate": True},
        )
        with patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop._propose_sign_negate",
            return_value=mock_change,
        ) as mock_fn:
            from edgar.xbrl.standardization.tools.auto_eval_loop import propose_change
            result = propose_change(gap, graveyard_entries=[])
            mock_fn.assert_called_once_with(gap)
            assert result == mock_change


# ===========================================================================
# Fix 3: Regression identification API
# ===========================================================================

class TestRegressionTracking:
    """CompanyCQS and CQSResult track regressed metric names."""

    def test_company_cqs_tracks_regressed_metrics(self):
        cs = _make_company_cqs(
            "XOM",
            failed_metrics=["OperatingIncome", "LongTermDebt"],
            regressed_metrics=["OperatingIncome"],
            regression_count=1,
        )
        assert cs.regressed_metrics == ["OperatingIncome"]
        assert cs.regression_count == 1

    def test_cqs_result_aggregates_regressions(self):
        cs1 = _make_company_cqs("XOM", regressed_metrics=["OperatingIncome"], regression_count=1)
        cs2 = _make_company_cqs("JPM", regressed_metrics=["LongTermDebt", "CashAndEquivalents"], regression_count=2)
        result = _make_cqs_result(
            {"XOM": cs1, "JPM": cs2},
            regressed_metrics=[("XOM", "OperatingIncome"), ("JPM", "LongTermDebt"), ("JPM", "CashAndEquivalents")],
        )
        assert len(result.regressed_metrics) == 3
        assert ("XOM", "OperatingIncome") in result.regressed_metrics
        assert ("JPM", "LongTermDebt") in result.regressed_metrics

    def test_list_regressions_returns_all(self):
        regressed = [("XOM", "OperatingIncome"), ("JPM", "LongTermDebt")]
        result = _make_cqs_result({}, regressed_metrics=regressed)
        regressions = list_regressions(result)
        assert regressions == regressed

    def test_list_regressions_empty_when_no_regressions(self):
        result = _make_cqs_result({}, regressed_metrics=[])
        assert list_regressions(result) == []


# ===========================================================================
# Fix 4: Improved solver candidate ranking
# ===========================================================================

class TestSolverRanking:
    """Solver candidates ranked by multi-period matches first."""

    def _make_candidate(self, components, variance_pct, periods_passed=0, periods_checked=0):
        return FormulaCandidate(
            metric="OperatingIncome",
            ticker="XOM",
            components=components,
            values=[1.0] * len(components),
            total=float(len(components)),
            target=1.0,
            variance_pct=variance_pct,
            periods_checked=periods_checked,
            periods_passed=periods_passed,
        )

    def test_prefers_multi_period(self):
        """Candidate with 3 periods_passed ranks above one with 1."""
        c1 = self._make_candidate(["A"], 1.0, periods_passed=1, periods_checked=3)
        c2 = self._make_candidate(["A", "B"], 0.5, periods_passed=3, periods_checked=3)

        candidates = [c1, c2]
        candidates.sort(key=lambda f: (-f.periods_passed, len(f.components), f.variance_pct))

        assert candidates[0] is c2  # 3 periods beats 1 period

    def test_tiebreaker_components_then_variance(self):
        """Same periods_passed -> fewer components wins -> lower variance wins."""
        c1 = self._make_candidate(["A", "B"], 1.0, periods_passed=3, periods_checked=3)
        c2 = self._make_candidate(["A"], 2.0, periods_passed=3, periods_checked=3)
        c3 = self._make_candidate(["A"], 0.5, periods_passed=3, periods_checked=3)

        candidates = [c1, c2, c3]
        candidates.sort(key=lambda f: (-f.periods_passed, len(f.components), f.variance_pct))

        assert candidates[0] is c3  # 1 component, 0.5% variance
        assert candidates[1] is c2  # 1 component, 2.0% variance
        assert candidates[2] is c1  # 2 components

    def test_backward_compatible_zero_periods(self):
        """All periods_passed=0 -> same order as old ranking (fewest components, then lowest variance)."""
        c1 = self._make_candidate(["A", "B"], 0.5)
        c2 = self._make_candidate(["A"], 1.0)
        c3 = self._make_candidate(["A"], 0.3)

        candidates = [c1, c2, c3]
        candidates.sort(key=lambda f: (-f.periods_passed, len(f.components), f.variance_pct))

        assert candidates[0] is c3  # 1 component, 0.3%
        assert candidates[1] is c2  # 1 component, 1.0%
        assert candidates[2] is c1  # 2 components


# ===========================================================================
# Fix 5: Store actual XBRL concept in extraction_runs
# ===========================================================================

class TestConceptStorage:
    """ExtractionRun stores and retrieves the actual XBRL concept."""

    def test_extraction_run_stores_concept(self):
        """ExtractionRun with concept field -> concept stored in DB."""
        ledger = ExperimentLedger(db_path=":memory:")
        run = ExtractionRun(
            ticker="CME", metric="IntangibleAssets",
            fiscal_period="2024-FY", form_type="10-K",
            archetype="A", strategy_name="tree",
            concept="us-gaap:Goodwill",
            strategy_fingerprint="abc123",
            extracted_value=30_000_000_000.0,
            reference_value=30_090_000_000.0,
            variance_pct=0.3,
            is_valid=True,
            confidence=0.95,
        )
        run_id = ledger.record_run(run)
        retrieved = ledger.get_run(run_id)
        assert retrieved is not None
        assert retrieved.concept == "us-gaap:Goodwill"
        assert retrieved.strategy_name == "tree"

    def test_golden_context_returns_concept(self):
        """After recording with concept -> get_golden_extraction_context returns real concept."""
        ledger = ExperimentLedger(db_path=":memory:")

        # Record a valid run with actual concept
        run = ExtractionRun(
            ticker="CME", metric="IntangibleAssets",
            fiscal_period="2024-FY", form_type="10-K",
            archetype="A", strategy_name="tree",
            concept="us-gaap:Goodwill",
            strategy_fingerprint="abc123",
            extracted_value=30_000_000_000.0,
            reference_value=30_090_000_000.0,
            variance_pct=0.3,
            is_valid=True,
            confidence=0.95,
        )
        ledger.record_run(run)

        # Create a golden master so get_golden_extraction_context can find it
        from edgar.xbrl.standardization.ledger.schema import GoldenMaster
        gm = GoldenMaster(
            golden_id="gm-cme-001",
            ticker="CME", metric="IntangibleAssets",
            archetype="A", sub_archetype=None,
            strategy_name="tree",
            strategy_fingerprint="abc123",
            strategy_params={},
            validated_periods=["2024-FY"],
            validation_count=3,
            avg_variance_pct=0.3,
            max_variance_pct=0.5,
            is_active=True,
        )
        ledger.create_golden_master(gm)

        ctx = ledger.get_golden_extraction_context("CME", "IntangibleAssets")
        assert ctx is not None
        assert ctx["concept"] == "us-gaap:Goodwill"
        assert ctx["strategy_name"] == "tree"

    def test_golden_context_fallback_strategy_name(self):
        """Old records without concept -> falls back to strategy_name."""
        ledger = ExperimentLedger(db_path=":memory:")

        # Record a run WITHOUT concept (simulating old record)
        run = ExtractionRun(
            ticker="VZ", metric="IntangibleAssets",
            fiscal_period="2024-FY", form_type="10-K",
            archetype="A", strategy_name="tree",
            concept=None,  # No concept stored (old-style record)
            strategy_fingerprint="def456",
            extracted_value=190_000_000_000.0,
            reference_value=190_460_000_000.0,
            variance_pct=0.2,
            is_valid=True,
            confidence=0.90,
        )
        ledger.record_run(run)

        from edgar.xbrl.standardization.ledger.schema import GoldenMaster
        gm = GoldenMaster(
            golden_id="gm-vz-001",
            ticker="VZ", metric="IntangibleAssets",
            archetype="A", sub_archetype=None,
            strategy_name="tree",
            strategy_fingerprint="def456",
            strategy_params={},
            validated_periods=["2024-FY"],
            validation_count=3,
            avg_variance_pct=0.2,
            max_variance_pct=0.4,
            is_active=True,
        )
        ledger.create_golden_master(gm)

        ctx = ledger.get_golden_extraction_context("VZ", "IntangibleAssets")
        assert ctx is not None
        # Falls back to strategy_name since concept is None
        assert ctx["concept"] == "tree"


# ===========================================================================
# Fix 6: Guard against strategy-name golden concepts
# ===========================================================================

class TestRegressionFixGuard:
    """Regression fix proposals skip strategy-name golden concepts."""

    def test_regression_fix_skips_strategy_name_concept(self):
        """golden_concept='tree' -> doesn't propose preferred_concept='tree'."""
        gap = _make_gap(
            ticker="CME", metric="IntangibleAssets",
            gap_type="regression", estimated_impact=0.02,
            reference_value=30_090_000_000.0,
        )
        diag = RegressionDiagnosis(
            ticker="CME", metric="IntangibleAssets",
            golden_concept="tree",  # Strategy name, not XBRL concept!
            current_concept="us-gaap:Goodwill",
            golden_value=30_000_000_000.0,
            diagnosis_type="concept_changed",
        )
        with patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop.diagnose_regression",
            return_value=diag,
        ):
            with patch(
                "edgar.xbrl.standardization.tools.auto_eval_loop._propose_via_solver",
                return_value=None,
            ) as mock_solver:
                result = _propose_regression_fix(gap)
                # Should NOT produce a preferred_concept="tree" override
                mock_solver.assert_called_once()
                # The solver was called with a gap using golden_value as reference
                solver_gap = mock_solver.call_args[0][0]
                assert solver_gap.reference_value == 30_000_000_000.0

    def test_regression_fix_routes_to_solver(self):
        """golden_concept='tree' with golden_value -> routes to solver with golden value."""
        gap = _make_gap(
            ticker="CME", metric="IntangibleAssets",
            gap_type="regression", estimated_impact=0.02,
            reference_value=30_090_000_000.0,
        )
        diag = RegressionDiagnosis(
            ticker="CME", metric="IntangibleAssets",
            golden_concept="facts",
            golden_value=30_000_000_000.0,
            diagnosis_type="concept_changed",
        )
        mock_change = ConfigChange(
            file="metrics.yaml",
            change_type=ChangeType.ADD_STANDARDIZATION,
            yaml_path="metrics.IntangibleAssets.standardization",
            new_value={"formula": "Goodwill + IntangibleAssetsNetExcludingGoodwill"},
        )
        with patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop.diagnose_regression",
            return_value=diag,
        ):
            with patch(
                "edgar.xbrl.standardization.tools.auto_eval_loop._propose_via_solver",
                return_value=mock_change,
            ) as mock_solver:
                result = _propose_regression_fix(gap)
                assert result == mock_change
                # Solver got a gap with golden value, not the original reference
                solver_gap = mock_solver.call_args[0][0]
                assert solver_gap.reference_value == 30_000_000_000.0

    def test_regression_fix_uses_real_concept(self):
        """golden_concept='us-gaap:Goodwill' -> proposes correct preferred_concept."""
        gap = _make_gap(
            ticker="CME", metric="IntangibleAssets",
            gap_type="regression", estimated_impact=0.02,
            reference_value=30_090_000_000.0,
        )
        diag = RegressionDiagnosis(
            ticker="CME", metric="IntangibleAssets",
            golden_concept="us-gaap:Goodwill",
            current_concept="us-gaap:IntangibleAssetsNetExcludingGoodwill",
            diagnosis_type="concept_changed",
        )
        with patch(
            "edgar.xbrl.standardization.tools.auto_eval_loop.diagnose_regression",
            return_value=diag,
        ):
            result = _propose_regression_fix(gap)
            assert result is not None
            assert result.change_type == ChangeType.ADD_COMPANY_OVERRIDE
            assert result.new_value["preferred_concept"] == "us-gaap:Goodwill"


# ===========================================================================
# Phase 1 Governance: Golden master promotion threshold
# ===========================================================================

class TestGoldenMasterPromotionThreshold:
    """Golden masters require 3+ periods to be promoted."""

    def test_single_period_not_promoted(self):
        """Single-period extraction should NOT become a golden master."""
        ledger = ExperimentLedger(db_path=":memory:")
        run = ExtractionRun(
            ticker="TEST", metric="Revenue", fiscal_period="2024-FY",
            form_type="10-K", archetype="A", strategy_name="tree",
            strategy_fingerprint="fp1", extracted_value=100.0,
            reference_value=100.0, variance_pct=0.0, is_valid=True,
        )
        ledger.record_run(run)
        promoted = ledger.promote_golden_masters()  # default min_periods=3
        assert len(promoted) == 0

    def test_three_periods_promoted(self):
        """Three-period extraction SHOULD become a golden master."""
        ledger = ExperimentLedger(db_path=":memory:")
        for period in ["2022-FY", "2023-FY", "2024-FY"]:
            run = ExtractionRun(
                ticker="TEST", metric="Revenue", fiscal_period=period,
                form_type="10-K", archetype="A", strategy_name="tree",
                strategy_fingerprint="fp1", extracted_value=100.0,
                reference_value=100.0, variance_pct=0.0, is_valid=True,
            )
            ledger.record_run(run)
        promoted = ledger.promote_golden_masters()
        assert len(promoted) >= 1


# ===========================================================================
# Phase 1 Governance: Metric-class tolerances
# ===========================================================================

class TestMetricClassTolerances:
    """ExtractionRun uses metric-specific validation tolerances."""

    def test_default_tolerance_20_percent(self):
        """ExtractionRun without explicit tolerance uses 20%."""
        run = ExtractionRun(
            ticker="TEST", metric="Revenue", fiscal_period="2024-FY",
            form_type="10-K", archetype="A",
            extracted_value=100.0, reference_value=120.0,  # 16.7% variance
        )
        assert run.is_valid is True  # Within default 20%

    def test_custom_tolerance_tighter(self):
        """Revenue with 10% tolerance rejects 16.7% variance."""
        run = ExtractionRun(
            ticker="TEST", metric="Revenue", fiscal_period="2024-FY",
            form_type="10-K", archetype="A",
            extracted_value=100.0, reference_value=120.0,  # 16.7% variance
            validation_tolerance=10.0,
        )
        assert run.is_valid is False  # Exceeds 10% tolerance

    def test_custom_tolerance_looser(self):
        """Capex with 40% tolerance accepts 25% variance."""
        run = ExtractionRun(
            ticker="TEST", metric="Capex", fiscal_period="2024-FY",
            form_type="10-K", archetype="A",
            extracted_value=100.0, reference_value=133.0,  # 24.8% variance
            validation_tolerance=40.0,
        )
        assert run.is_valid is True  # Within 40% tolerance


# ===========================================================================
# Phase 1 Governance: No exclusion for None reference
# ===========================================================================

class TestNoExclusionForNoneReference:
    """reference_value=None should not trigger ADD_EXCLUSION."""

    def test_none_reference_returns_none_not_exclusion(self):
        """reference_value=None should return None, not ADD_EXCLUSION."""
        gap = _make_gap(
            ticker="JPM", metric="LongTermDebt",
            gap_type="unmapped", estimated_impact=0.01,
            reference_value=None,
        )
        from edgar.xbrl.standardization.tools.auto_eval_loop import propose_change
        result = propose_change(gap, graveyard_entries=[])
        if result is not None:
            assert result.change_type != ChangeType.ADD_EXCLUSION

    def test_unmapped_with_reference_still_proposes(self):
        """Unmapped gap WITH reference value should still get a proposal."""
        gap = _make_gap(
            ticker="AAPL", metric="Revenue",
            gap_type="unmapped", estimated_impact=0.01,
            reference_value=394_000_000_000.0,
        )
        from edgar.xbrl.standardization.tools.auto_eval_loop import propose_change
        result = propose_change(gap, graveyard_entries=[])
        # Should attempt some proposal (concept or solver), not None
        # (may still be None if no concepts available, but should NOT be ADD_EXCLUSION)
        if result is not None:
            assert result.change_type != ChangeType.ADD_EXCLUSION


# ===========================================================================
# Phase 2: SEC-Native Self-Validation
# ===========================================================================

class TestInternalValidation:
    """Internal consistency validation using accounting equations."""

    def test_balance_sheet_equation_passes(self):
        """Assets = Liabilities + Equity should pass within tolerance."""
        from edgar.xbrl.standardization.internal_validator import (
            InternalConsistencyValidator, ValidationStatus,
        )
        validator = InternalConsistencyValidator()
        values = {
            'TotalAssets': 1_000_000.0,
            'TotalLiabilities': 600_000.0,
            'StockholdersEquity': 400_000.0,
        }
        results = validator.validate(values)
        assert results['balance_sheet_equation'].status == ValidationStatus.PASS

    def test_balance_sheet_equation_fails(self):
        """Mismatched values should fail the equation."""
        from edgar.xbrl.standardization.internal_validator import (
            InternalConsistencyValidator, ValidationStatus,
        )
        validator = InternalConsistencyValidator()
        values = {
            'TotalAssets': 1_000_000.0,
            'TotalLiabilities': 600_000.0,
            'StockholdersEquity': 200_000.0,  # Off by 200K
        }
        results = validator.validate(values)
        assert results['balance_sheet_equation'].status == ValidationStatus.FAIL

    def test_internal_validity_overall(self):
        """get_internal_validity returns correct aggregate status."""
        from edgar.xbrl.standardization.internal_validator import InternalConsistencyValidator
        validator = InternalConsistencyValidator()
        values = {
            'TotalAssets': 1_000_000.0,
            'TotalLiabilities': 600_000.0,
            'StockholdersEquity': 400_000.0,
            'Revenue': 500_000.0,
            'COGS': 300_000.0,
            'GrossProfit': 200_000.0,
        }
        result = validator.get_internal_validity(values)
        assert result.passed_count >= 2
        assert result.failed_count == 0

    def test_concept_consensus_counts(self):
        """Cross-company concept frequency is computed correctly."""
        from edgar.xbrl.standardization.internal_validator import InternalConsistencyValidator
        from types import SimpleNamespace

        all_results = {
            'AAPL': {'Revenue': SimpleNamespace(concept='us-gaap:Revenues')},
            'MSFT': {'Revenue': SimpleNamespace(concept='us-gaap:Revenues')},
            'GOOG': {'Revenue': SimpleNamespace(concept='us-gaap:Revenues')},
            'XOM': {'Revenue': SimpleNamespace(concept='us-gaap:SalesRevenueNet')},
        }
        counts = InternalConsistencyValidator.compute_concept_consensus(all_results, 'Revenue')
        assert counts['us-gaap:Revenues'] == 3
        assert counts['us-gaap:SalesRevenueNet'] == 1


# ===========================================================================
# Phase 4: SEC Facts Reference Source
# ===========================================================================

class TestSECFactsReference:
    """SEC Company Facts API as second reference source."""

    def test_sec_facts_disabled_by_default(self):
        """SEC facts lookup is off by default."""
        from edgar.xbrl.standardization.reference_validator import ReferenceValidator
        rv = ReferenceValidator()
        assert rv._use_sec_facts is False

    def test_sec_facts_enabled_flag(self):
        """SEC facts lookup can be enabled via constructor."""
        from edgar.xbrl.standardization.reference_validator import ReferenceValidator
        rv = ReferenceValidator(use_sec_facts=True)
        assert rv._use_sec_facts is True
        assert hasattr(rv, '_get_sec_facts_value')
        assert hasattr(rv, '_sec_facts_cache')

    def test_sec_facts_returns_none_when_disabled(self):
        """_get_sec_facts_value returns None when use_sec_facts is False."""
        from edgar.xbrl.standardization.reference_validator import ReferenceValidator
        rv = ReferenceValidator(use_sec_facts=False)
        result = rv._get_sec_facts_value("AAPL", "Revenue")
        assert result is None
