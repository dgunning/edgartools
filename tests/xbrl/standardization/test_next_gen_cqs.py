"""Tests for next-generation CQS loop improvements."""
import pytest
from unittest.mock import MagicMock, patch
from edgar.xbrl.standardization.tools.auto_eval import (
    CQSResult, CompanyCQS, MetricGap, derive_gaps_from_cqs,
)
from edgar.xbrl.standardization.tools.auto_eval_loop import (
    ProposalCache,
    RegressionDiagnosis,
    diagnose_regression,
)
from edgar.xbrl.standardization.reference_validator import (
    ReferenceAdjudicator, ReferenceVerdict,
)


def _make_company_cqs(ticker, failed_metrics, **overrides):
    """Helper to construct CompanyCQS with correct positional fields."""
    defaults = dict(
        ticker=ticker, pass_rate=0.8, mean_variance=5.0,
        coverage_rate=1.0, golden_master_rate=0.5,
        regression_count=0, metrics_total=10, metrics_mapped=10,
        metrics_valid=8, metrics_excluded=0, cqs=0.85,
        ef_pass_rate=0.9, sa_pass_rate=0.8, ef_cqs=0.9, sa_cqs=0.8,
        failed_metrics=failed_metrics,
    )
    defaults.update(overrides)
    return CompanyCQS(**defaults)


def _make_cqs_result(company_scores):
    """Helper to construct CQSResult with correct positional fields."""
    return CQSResult(
        pass_rate=0.8, mean_variance=5.0, coverage_rate=1.0,
        golden_master_rate=0.5, regression_rate=0.0, cqs=0.85,
        companies_evaluated=len(company_scores),
        total_metrics=50, total_mapped=45, total_valid=40,
        total_regressions=0,
        company_scores=company_scores, duration_seconds=10.0,
    )


class TestDeriveGapsFromCQS:
    """Test gap derivation from an existing CQSResult (no orchestrator re-run)."""

    def test_derive_gaps_returns_gaps_for_failing_metrics(self):
        """Gaps should be derived from company_scores without re-running orchestrator."""
        company_scores = {
            "AAPL": _make_company_cqs("AAPL", ["Revenue", "COGS"]),
        }
        cqs = _make_cqs_result(company_scores)

        gaps = derive_gaps_from_cqs(cqs, graveyard_counts={})
        assert len(gaps) == 2
        assert {g.metric for g in gaps} == {"Revenue", "COGS"}
        assert all(g.ticker == "AAPL" for g in gaps)

    def test_derive_gaps_respects_dead_ends(self):
        """Dead-end gaps (graveyard >= 6) should be filtered out."""
        company_scores = {
            "AAPL": _make_company_cqs(
                "AAPL", ["Revenue"],
                metrics_total=5, metrics_mapped=5, metrics_valid=4,
            ),
        }
        cqs = _make_cqs_result(company_scores)

        graveyard_counts = {"AAPL:Revenue": 7}
        gaps = derive_gaps_from_cqs(cqs, graveyard_counts=graveyard_counts)
        assert len(gaps) == 0

    def test_derive_gaps_multiple_companies(self):
        """Gaps from multiple companies should all be included."""
        company_scores = {
            "AAPL": _make_company_cqs("AAPL", ["Revenue"]),
            "JPM": _make_company_cqs("JPM", ["COGS", "SGA"]),
        }
        cqs = _make_cqs_result(company_scores)

        gaps = derive_gaps_from_cqs(cqs, graveyard_counts={})
        assert len(gaps) == 3
        assert {g.ticker for g in gaps} == {"AAPL", "JPM"}

    def test_derive_gaps_empty_when_no_failures(self):
        """No gaps when no metrics have failed."""
        company_scores = {
            "AAPL": _make_company_cqs("AAPL", []),
        }
        cqs = _make_cqs_result(company_scores)
        gaps = derive_gaps_from_cqs(cqs, graveyard_counts={})
        assert len(gaps) == 0


class TestProposalCache:
    """Test in-session proposal dedup cache."""

    def test_cache_blocks_duplicate_proposals(self):
        cache = ProposalCache()
        assert not cache.was_tried("AAPL", "Revenue", "add_concept:RevenueFromContractWithCustomerExcludingAssessedTax")
        cache.record("AAPL", "Revenue", "add_concept:RevenueFromContractWithCustomerExcludingAssessedTax")
        assert cache.was_tried("AAPL", "Revenue", "add_concept:RevenueFromContractWithCustomerExcludingAssessedTax")

    def test_cache_allows_different_proposals_for_same_gap(self):
        cache = ProposalCache()
        cache.record("AAPL", "Revenue", "add_concept:Revenues")
        assert not cache.was_tried("AAPL", "Revenue", "add_concept:SalesRevenueNet")

    def test_cache_allows_same_proposal_for_different_companies(self):
        cache = ProposalCache()
        cache.record("AAPL", "Revenue", "add_concept:Revenues")
        assert not cache.was_tried("MSFT", "Revenue", "add_concept:Revenues")


class TestRegressionDiagnosis:
    """Test regression provenance diff pipeline."""

    def test_diagnosis_identifies_concept_change(self):
        diag = RegressionDiagnosis(
            ticker="CAT",
            metric="Capex",
            golden_concept="PaymentsToAcquirePropertyPlantAndEquipment",
            current_concept="PaymentsToAcquireProductiveAssets",
            golden_value=5_000_000_000,
            current_value=3_200_000_000,
            reference_value=5_100_000_000,
            diagnosis_type="concept_changed",
        )
        assert diag.diagnosis_type == "concept_changed"
        assert diag.has_actionable_fix

    def test_diagnosis_identifies_reference_changed(self):
        diag = RegressionDiagnosis(
            ticker="D",
            metric="ShortTermDebt",
            golden_concept="ShortTermBorrowings",
            current_concept="ShortTermBorrowings",
            golden_value=2_000_000_000,
            current_value=2_000_000_000,
            reference_value=1_500_000_000,
            golden_reference_value=2_050_000_000,
            diagnosis_type="reference_changed",
        )
        assert diag.diagnosis_type == "reference_changed"
        assert diag.has_actionable_fix

    def test_diagnosis_unknown_is_not_actionable(self):
        diag = RegressionDiagnosis(
            ticker="X", metric="Y", diagnosis_type="unknown",
        )
        assert not diag.has_actionable_fix

    def test_value_drifted_is_actionable(self):
        diag = RegressionDiagnosis(
            ticker="X", metric="Y", diagnosis_type="value_drifted",
        )
        assert diag.has_actionable_fix


class TestDiagnoseRegression:
    """Test diagnose_regression() with mocked ledger data."""

    def test_diagnose_concept_changed(self):
        mock_ledger = MagicMock()
        mock_ledger.get_golden_extraction_context.return_value = {
            "concept": "PaymentsToAcquirePropertyPlantAndEquipment",
            "value": 5_000_000_000,
            "reference_value": 5_100_000_000,
            "fiscal_period": "2024-FY",
            "strategy_name": "PaymentsToAcquirePropertyPlantAndEquipment",
            "run_timestamp": "2025-01-01T00:00:00",
            "variance_pct": 2.0,
        }

        mock_validation = MagicMock()
        mock_validation.extracted_value = 3_200_000_000
        mock_validation.reference_value = 5_100_000_000
        mock_validation.components_used = ["PaymentsToAcquireProductiveAssets"]

        diag = diagnose_regression("CAT", "Capex", mock_validation, mock_ledger)
        assert diag.diagnosis_type == "concept_changed"
        assert diag.golden_concept == "PaymentsToAcquirePropertyPlantAndEquipment"
        assert diag.current_concept == "PaymentsToAcquireProductiveAssets"

    def test_diagnose_reference_changed(self):
        mock_ledger = MagicMock()
        mock_ledger.get_golden_extraction_context.return_value = {
            "concept": "ShortTermBorrowings",
            "value": 2_000_000_000,
            "reference_value": 2_050_000_000,
            "fiscal_period": "2024-FY",
            "strategy_name": "ShortTermBorrowings",
            "run_timestamp": "2025-01-01T00:00:00",
            "variance_pct": 2.5,
        }

        mock_validation = MagicMock()
        mock_validation.extracted_value = 2_000_000_000
        mock_validation.reference_value = 1_500_000_000
        mock_validation.components_used = ["ShortTermBorrowings"]

        diag = diagnose_regression("D", "ShortTermDebt", mock_validation, mock_ledger)
        assert diag.diagnosis_type == "reference_changed"

    def test_diagnose_unknown_when_no_golden_context(self):
        mock_ledger = MagicMock()
        mock_ledger.get_golden_extraction_context.return_value = None

        diag = diagnose_regression("CAT", "Capex", None, mock_ledger)
        assert diag.diagnosis_type == "unknown"

    def test_diagnose_value_drifted(self):
        mock_ledger = MagicMock()
        mock_ledger.get_golden_extraction_context.return_value = {
            "concept": "SameConcept",
            "value": 10_000_000_000,
            "reference_value": 10_500_000_000,
            "fiscal_period": "2024-FY",
            "strategy_name": "SameConcept",
            "run_timestamp": "2025-01-01T00:00:00",
            "variance_pct": 5.0,
        }

        mock_validation = MagicMock()
        mock_validation.extracted_value = 7_000_000_000  # 30% drift
        mock_validation.reference_value = 10_500_000_000
        mock_validation.components_used = ["SameConcept"]

        diag = diagnose_regression("X", "Y", mock_validation, mock_ledger)
        assert diag.diagnosis_type == "value_drifted"


class TestProposeRegressionFix:
    """Test _propose_regression_fix with real ExtractionEvidence and mocked ledger."""

    def test_concept_changed_produces_company_override(self):
        """_propose_regression_fix generates ADD_COMPANY_OVERRIDE for concept changes."""
        from edgar.xbrl.standardization.tools.auto_eval_loop import _propose_regression_fix, ChangeType
        from edgar.xbrl.standardization.tools.auto_eval import ExtractionEvidence

        evidence = ExtractionEvidence(
            metric="Capex", ticker="CAT",
            extracted_value=3_200_000_000,
            reference_value=5_100_000_000,
            components_used=["PaymentsToAcquireProductiveAssets"],
        )
        gap = MetricGap(
            ticker="CAT", metric="Capex", gap_type="regression",
            estimated_impact=0.05, graveyard_count=0,
            extraction_evidence=evidence,
        )

        mock_ledger = MagicMock()
        mock_ledger.get_golden_extraction_context.return_value = {
            "concept": "PaymentsToAcquirePropertyPlantAndEquipment",
            "value": 5_000_000_000,
            "reference_value": 5_100_000_000,
            "fiscal_period": "2024-FY",
            "strategy_name": "PaymentsToAcquirePropertyPlantAndEquipment",
            "run_timestamp": "2025-01-01T00:00:00",
            "variance_pct": 2.0,
        }

        change = _propose_regression_fix(gap, ledger=mock_ledger)
        assert change is not None
        assert change.change_type == ChangeType.ADD_COMPANY_OVERRIDE
        assert "PaymentsToAcquirePropertyPlantAndEquipment" in str(change.new_value)


class TestReferenceAdjudication:
    """Test the reference data trust hierarchy."""

    def test_verdict_trusted_when_sources_agree(self):
        adj = ReferenceAdjudicator()
        verdict = adj.adjudicate(
            xbrl_value=394_328_000_000,
            reference_value=394_328_000_000,
            golden_value=None,
            metric="Revenue",
            ticker="AAPL",
        )
        assert verdict.status == "trusted"
        assert verdict.reference_value == 394_328_000_000

    def test_verdict_disputed_when_xbrl_matches_golden_but_not_ref(self):
        adj = ReferenceAdjudicator()
        verdict = adj.adjudicate(
            xbrl_value=5_000_000_000,
            reference_value=3_500_000_000,
            golden_value=5_100_000_000,
            metric="ShortTermDebt",
            ticker="D",
        )
        assert verdict.status == "reference_disputed"
        assert verdict.trust_source == "golden_master"

    def test_verdict_uses_reference_when_no_golden(self):
        adj = ReferenceAdjudicator()
        verdict = adj.adjudicate(
            xbrl_value=5_000_000_000,
            reference_value=3_500_000_000,
            golden_value=None,
            metric="ShortTermDebt",
            ticker="D",
        )
        assert verdict.status == "mismatch"
        assert verdict.trust_source == "yfinance"

    def test_verdict_missing_when_no_xbrl(self):
        adj = ReferenceAdjudicator()
        verdict = adj.adjudicate(
            xbrl_value=None,
            reference_value=100,
            golden_value=None,
            metric="Revenue",
            ticker="X",
        )
        assert verdict.status == "missing"

    def test_verdict_missing_when_no_reference(self):
        adj = ReferenceAdjudicator()
        verdict = adj.adjudicate(
            xbrl_value=100,
            reference_value=None,
            golden_value=None,
            metric="Revenue",
            ticker="X",
        )
        assert verdict.status == "missing"

    def test_custom_tolerance(self):
        adj = ReferenceAdjudicator(tolerance_pct=5.0)
        verdict = adj.adjudicate(
            xbrl_value=100,
            reference_value=90,  # 11% variance -- outside 5% tolerance
            golden_value=None,
            metric="Revenue",
            ticker="X",
        )
        assert verdict.status == "mismatch"


import yaml
import os
import tempfile
from pathlib import Path


class TestIndustryArchetypes:
    """Test industry archetype template structure in industry_metrics.yaml."""

    @property
    def config_path(self):
        return Path(__file__).resolve().parents[3] / "edgar/xbrl/standardization/config/industry_metrics.yaml"

    def test_banking_has_forbidden_metrics(self):
        with open(self.config_path) as f:
            config = yaml.safe_load(f)
        banking = config.get("banking", {})
        forbidden = banking.get("forbidden_metrics", [])
        assert "Inventory" in forbidden, "Banking should forbid Inventory"
        assert "COGS" in forbidden, "Banking should forbid COGS"

    def test_insurance_has_forbidden_metrics(self):
        with open(self.config_path) as f:
            config = yaml.safe_load(f)
        insurance = config.get("insurance", {})
        forbidden = insurance.get("forbidden_metrics", [])
        assert "COGS" in forbidden
        assert "Inventory" in forbidden

    def test_reit_has_required_alternatives(self):
        with open(self.config_path) as f:
            config = yaml.safe_load(f)
        reits = config.get("reits", {})
        required = reits.get("required_alternatives", {})
        assert "FFO" in required
        assert "NOI" in required

    def test_archetype_has_sic_mapping(self):
        with open(self.config_path) as f:
            config = yaml.safe_load(f)
        for archetype_name in ["banking", "insurance", "reits"]:
            archetype = config.get(archetype_name, {})
            assert "sic_ranges" in archetype, f"{archetype_name} missing sic_ranges"

    def test_banking_required_alternatives(self):
        with open(self.config_path) as f:
            config = yaml.safe_load(f)
        banking = config.get("banking", {})
        required = banking.get("required_alternatives", {})
        assert "InterestExpense" in required
        assert required["InterestExpense"]["replaces"] == "COGS"


class TestIsMetricForbidden:
    """Test the _is_metric_forbidden helper."""

    def test_forbidden_metric_returns_true(self):
        from edgar.xbrl.standardization.tools.auto_eval_loop import _is_metric_forbidden

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write minimal config files
            companies_yaml = {"companies": {"JPM": {"industry": "banking"}}}
            industry_yaml = {"banking": {"forbidden_metrics": ["COGS", "Inventory"]}}

            with open(os.path.join(tmpdir, "companies.yaml"), "w") as f:
                yaml.dump(companies_yaml, f)
            with open(os.path.join(tmpdir, "industry_metrics.yaml"), "w") as f:
                yaml.dump(industry_yaml, f)

            assert _is_metric_forbidden("COGS", "JPM", Path(tmpdir))
            assert _is_metric_forbidden("Inventory", "JPM", Path(tmpdir))

    def test_allowed_metric_returns_false(self):
        from edgar.xbrl.standardization.tools.auto_eval_loop import _is_metric_forbidden

        with tempfile.TemporaryDirectory() as tmpdir:
            companies_yaml = {"companies": {"JPM": {"industry": "banking"}}}
            industry_yaml = {"banking": {"forbidden_metrics": ["COGS"]}}

            with open(os.path.join(tmpdir, "companies.yaml"), "w") as f:
                yaml.dump(companies_yaml, f)
            with open(os.path.join(tmpdir, "industry_metrics.yaml"), "w") as f:
                yaml.dump(industry_yaml, f)

            assert not _is_metric_forbidden("Revenue", "JPM", Path(tmpdir))

    def test_no_industry_returns_false(self):
        from edgar.xbrl.standardization.tools.auto_eval_loop import _is_metric_forbidden

        with tempfile.TemporaryDirectory() as tmpdir:
            companies_yaml = {"companies": {"AAPL": {}}}
            industry_yaml = {"banking": {"forbidden_metrics": ["COGS"]}}

            with open(os.path.join(tmpdir, "companies.yaml"), "w") as f:
                yaml.dump(companies_yaml, f)
            with open(os.path.join(tmpdir, "industry_metrics.yaml"), "w") as f:
                yaml.dump(industry_yaml, f)

            assert not _is_metric_forbidden("COGS", "AAPL", Path(tmpdir))


from edgar.xbrl.standardization.tools.auto_solver import AutoSolver, FormulaCandidate


class TestRicherSolver:
    """Test extended formula solver capabilities."""

    def test_sign_flip_detection(self):
        """Solver should find formulas involving subtraction (A - B)."""
        solver = AutoSolver(max_components=4, allow_subtraction=True)

        # Target: 100, Facts: A=150, B=50 → A - B = 100
        facts = {"ConceptA": 150.0, "ConceptB": 50.0}
        candidates = solver.solve_metric(
            "TEST", "TestMetric",
            yfinance_value=100.0,
            xbrl_facts=facts,
        )
        assert len(candidates) >= 1
        # At least one should be a subtraction formula
        found_subtraction = any(
            any(v < 0 for v in c.values) and abs(c.variance_pct) < 1.0
            for c in candidates
        )
        assert found_subtraction, f"No subtraction formula found in {candidates}"

    def test_subtraction_not_found_without_flag(self):
        """Without allow_subtraction, only additive formulas are found."""
        solver = AutoSolver(max_components=4, allow_subtraction=False)
        facts = {"ConceptA": 150.0, "ConceptB": 50.0}
        candidates = solver.solve_metric(
            "TEST", "TestMetric",
            yfinance_value=100.0,
            xbrl_facts=facts,
        )
        # No additive combo of 150 and 50 sums to 100
        subtraction_results = [c for c in candidates if any(v < 0 for v in c.values)]
        assert len(subtraction_results) == 0

    def test_scale_normalization(self):
        """Solver should detect scale mismatches (thousands vs raw)."""
        solver = AutoSolver(max_components=4, allow_scale_search=True)

        # Target: 5,000,000, Facts: A=5000 (in thousands)
        facts = {"ConceptA": 5000.0}
        candidates = solver.solve_metric(
            "TEST", "TestMetric",
            yfinance_value=5_000_000.0,
            xbrl_facts=facts,
        )
        assert len(candidates) >= 1
        # Should find ConceptA * 1000 = 5,000,000
        scale_match = any(abs(c.total - 5_000_000) < 50_000 for c in candidates)
        assert scale_match, f"No scale-corrected formula found in {candidates}"

    def test_scale_not_found_without_flag(self):
        """Without allow_scale_search, scale mismatches are not found."""
        solver = AutoSolver(max_components=4, allow_scale_search=False)
        facts = {"ConceptA": 5000.0}
        candidates = solver.solve_metric(
            "TEST", "TestMetric",
            yfinance_value=5_000_000.0,
            xbrl_facts=facts,
        )
        # 5000 is within 2x of 5M (5000 <= 10M), so it's a candidate
        # but additive search won't match since 5000 != 5M
        exact_match = [c for c in candidates if abs(c.variance_pct) < 1.0]
        assert len(exact_match) == 0

    def test_increased_component_cap(self):
        """Solver should support up to 6 components."""
        solver = AutoSolver(max_components=6)

        # 6 facts that sum to target
        target = 600.0
        facts = {f"C{i}": 100.0 for i in range(6)}
        candidates = solver.solve_metric(
            "TEST", "TestMetric",
            yfinance_value=target,
            xbrl_facts=facts,
        )
        assert any(len(c.components) == 6 for c in candidates)

    def test_default_params_unchanged(self):
        """Default AutoSolver behavior should be unchanged."""
        solver = AutoSolver()
        assert solver.max_components == 4
        assert solver.allow_subtraction is False
        assert solver.allow_scale_search is False
