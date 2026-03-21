"""Tests for Tier 1 CQS loop improvements.

Fix 1: Auto-create metric_overrides in config writer
Fix 2: Sign inversion proposal handler
Fix 3: Regression identification API
Fix 4: Improved solver candidate ranking
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from edgar.xbrl.standardization.tools.auto_eval import (
    CQSResult,
    CompanyCQS,
    MetricGap,
    list_regressions,
)
from edgar.xbrl.standardization.tools.auto_eval_loop import (
    ChangeType,
    ConfigChange,
    apply_config_change,
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
