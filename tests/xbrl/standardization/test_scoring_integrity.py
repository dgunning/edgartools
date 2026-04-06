"""
Tests for CQS Scoring Integrity Reform (Consensus 018).

Validates:
- exclude_metrics dict format parsing (legacy list auto-convert)
- CompanyConfig.should_skip_metric / get_exclusion_reason
- Scoring behavior: extraction_failed gets penalty, not_applicable gets free pass
- Raw CQS, data completeness, and extraction_failed_count fields
"""

import pytest
from dataclasses import dataclass
from typing import Dict, Optional

from edgar.xbrl.standardization.models import CompanyConfig, MappingResult, MappingSource


# =============================================================================
# Config / Schema tests (fast, no network)
# =============================================================================


class TestExcludeMetricsDictFormat:
    """Test dict-based exclusions parsing and behavior."""

    def test_exclude_metrics_dict_format(self):
        """CompanyConfig accepts dict-based exclude_metrics."""
        config = CompanyConfig(
            ticker="TEST",
            name="Test Corp",
            cik=12345,
            exclude_metrics={
                "COGS": {"reason": "not_applicable", "notes": "No physical goods"},
                "ShortTermDebt": {"reason": "extraction_failed", "notes": "Debt exists but extraction fails"},
            },
        )
        assert isinstance(config.exclude_metrics, dict)
        assert len(config.exclude_metrics) == 2
        assert "COGS" in config.exclude_metrics
        assert config.exclude_metrics["COGS"]["reason"] == "not_applicable"

    def test_should_skip_metric_with_dict(self):
        """should_skip_metric works with dict-based exclude_metrics."""
        config = CompanyConfig(
            ticker="TEST",
            name="Test Corp",
            cik=12345,
            exclude_metrics={
                "COGS": {"reason": "not_applicable", "notes": ""},
                "Inventory": {"reason": "not_applicable", "notes": ""},
            },
        )
        assert config.should_skip_metric("COGS") is True
        assert config.should_skip_metric("Revenue") is False

    def test_get_exclusion_reason(self):
        """get_exclusion_reason returns correct reason for each tier."""
        config = CompanyConfig(
            ticker="TEST",
            name="Test Corp",
            cik=12345,
            exclude_metrics={
                "COGS": {"reason": "not_applicable", "notes": ""},
                "ShortTermDebt": {"reason": "extraction_failed", "notes": ""},
                "OperatingIncome": {"reason": "semantic_mismatch", "notes": ""},
            },
        )
        assert config.get_exclusion_reason("COGS") == "not_applicable"
        assert config.get_exclusion_reason("ShortTermDebt") == "extraction_failed"
        assert config.get_exclusion_reason("OperatingIncome") == "semantic_mismatch"
        assert config.get_exclusion_reason("Revenue") is None

    def test_exclude_metrics_list_auto_convert(self):
        """Legacy list format auto-converts to dict with not_applicable default in config_loader."""
        from edgar.xbrl.standardization.config_loader import ConfigLoader
        import yaml
        import tempfile
        from pathlib import Path

        # Create a minimal config with list-format exclude_metrics
        companies_yaml = {
            "version": "1.0.0",
            "companies": {
                "TEST": {
                    "name": "Test Corp",
                    "cik": 12345,
                    "exclude_metrics": ["COGS", "Inventory"],
                }
            },
            "defaults": {},
        }
        metrics_yaml = {"version": "1.0.0", "metrics": {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            with open(tmpdir / "companies.yaml", "w") as f:
                yaml.dump(companies_yaml, f)
            with open(tmpdir / "metrics.yaml", "w") as f:
                yaml.dump(metrics_yaml, f)

            loader = ConfigLoader(config_dir=tmpdir)
            config = loader.load()

        company = config.get_company("TEST")
        assert isinstance(company.exclude_metrics, dict)
        assert "COGS" in company.exclude_metrics
        assert company.exclude_metrics["COGS"]["reason"] == "not_applicable"
        assert company.should_skip_metric("COGS")
        assert not company.should_skip_metric("Revenue")


class TestGetExcludedMetricsForCompany:
    """Test the MappingConfig.get_excluded_metrics_for_company dict return type."""

    def test_returns_dict(self):
        """get_excluded_metrics_for_company returns Dict[str, Dict[str, str]]."""
        from edgar.xbrl.standardization.config_loader import ConfigLoader
        import yaml
        import tempfile
        from pathlib import Path

        companies_yaml = {
            "version": "1.0.0",
            "companies": {
                "TEST": {
                    "name": "Test Corp",
                    "cik": 12345,
                    "exclude_metrics": {
                        "COGS": {"reason": "extraction_failed", "notes": "test"},
                    },
                }
            },
            "defaults": {
                "industry_exclusions": {
                    "banking": ["SGA", "Inventory"],
                },
            },
        }
        metrics_yaml = {"version": "1.0.0", "metrics": {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            with open(tmpdir / "companies.yaml", "w") as f:
                yaml.dump(companies_yaml, f)
            with open(tmpdir / "metrics.yaml", "w") as f:
                yaml.dump(metrics_yaml, f)

            loader = ConfigLoader(config_dir=tmpdir)
            config = loader.load()

        result = config.get_excluded_metrics_for_company("TEST")
        assert isinstance(result, dict)
        assert "COGS" in result
        assert result["COGS"]["reason"] == "extraction_failed"

    def test_set_of_dict_returns_keys(self):
        """set(get_excluded_metrics_for_company()) returns metric name keys."""
        excluded = {"COGS": {"reason": "not_applicable"}, "Inventory": {"reason": "not_applicable"}}
        keys = set(excluded)
        assert keys == {"COGS", "Inventory"}
        assert "COGS" in keys
        assert "Revenue" not in keys


# =============================================================================
# Scoring tests (fast, mocked)
# =============================================================================


def _make_mapping_result(metric, source=MappingSource.TREE, validation_status="valid", concept="us-gaap:Test"):
    return MappingResult(
        metric=metric,
        company="TEST",
        fiscal_period="2024-FY",
        concept=concept,
        value=100.0,
        confidence=0.95,
        source=source,
        validation_status=validation_status,
    )


@dataclass
class MockValidation:
    variance_pct: Optional[float] = 0.0
    variance_type: str = "raw"
    ef_pass: bool = True
    sa_pass: bool = True
    rfa_pass: bool = True
    sma_pass: bool = True
    reference_value: Optional[float] = 100.0
    xbrl_value: Optional[float] = 100.0
    notes: str = ""
    rfa_source: Optional[str] = None
    publish_confidence: Optional[str] = None
    accession_number: Optional[str] = None
    period_type: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    unit: Optional[str] = None
    fact_decimals: Optional[int] = None


class TestScoringIntegrity:
    """Test that extraction_failed exclusions get penalized correctly."""

    def _compute(self, metrics, exclusion_reasons=None):
        from edgar.xbrl.standardization.tools.auto_eval import _compute_company_cqs
        golden_set = set()
        validations = {}
        for m in metrics.values():
            if m.validation_status == "valid" and m.source != MappingSource.CONFIG:
                validations[m.metric] = MockValidation()
        return _compute_company_cqs("TEST", metrics, golden_set, validations, exclusion_reasons=exclusion_reasons)

    def test_not_applicable_gets_free_pass(self):
        """not_applicable exclusion: valid=1, mapped=1, ef_pass=1 (free pass)."""
        metrics = {
            "Revenue": _make_mapping_result("Revenue"),
            "COGS": _make_mapping_result("COGS", source=MappingSource.CONFIG, validation_status="pending", concept=None),
        }
        reasons = {"COGS": {"reason": "not_applicable", "notes": ""}}
        result = self._compute(metrics, exclusion_reasons=reasons)

        # Both should count as valid — COGS gets free pass
        assert result.metrics_valid == 2
        assert result.extraction_failed_count == 0

    def test_extraction_failed_gets_penalty(self):
        """extraction_failed exclusion: total=1 but NOT valid/mapped/ef_pass."""
        metrics = {
            "Revenue": _make_mapping_result("Revenue"),
            "COGS": _make_mapping_result("COGS", source=MappingSource.CONFIG, validation_status="pending", concept=None),
        }
        reasons = {"COGS": {"reason": "extraction_failed", "notes": ""}}
        result = self._compute(metrics, exclusion_reasons=reasons)

        # Revenue valid, COGS penalized
        assert result.metrics_valid == 1
        assert result.metrics_excluded == 1
        assert result.extraction_failed_count == 1

    def test_semantic_mismatch_gets_free_pass(self):
        """semantic_mismatch treated same as not_applicable — free pass."""
        metrics = {
            "Revenue": _make_mapping_result("Revenue"),
            "OpIncome": _make_mapping_result("OpIncome", source=MappingSource.CONFIG, validation_status="pending", concept=None),
        }
        reasons = {"OpIncome": {"reason": "semantic_mismatch", "notes": ""}}
        result = self._compute(metrics, exclusion_reasons=reasons)

        assert result.metrics_valid == 2
        assert result.extraction_failed_count == 0

    def test_raw_cqs_lower_than_cqs(self):
        """raw_cqs <= cqs when there are legitimate exclusions."""
        metrics = {
            "Revenue": _make_mapping_result("Revenue"),
            "COGS": _make_mapping_result("COGS", source=MappingSource.CONFIG, validation_status="pending", concept=None),
            "Inventory": _make_mapping_result("Inventory", source=MappingSource.CONFIG, validation_status="pending", concept=None),
        }
        reasons = {
            "COGS": {"reason": "not_applicable", "notes": ""},
            "Inventory": {"reason": "not_applicable", "notes": ""},
        }
        result = self._compute(metrics, exclusion_reasons=reasons)

        # Raw CQS strips free passes → lower
        assert result.raw_cqs <= result.cqs

    def test_raw_cqs_equals_cqs_no_exclusions(self):
        """raw_cqs == cqs when there are no CONFIG exclusions."""
        metrics = {
            "Revenue": _make_mapping_result("Revenue"),
            "NetIncome": _make_mapping_result("NetIncome"),
        }
        result = self._compute(metrics)

        assert result.raw_cqs == pytest.approx(result.cqs, abs=0.001)

    def test_data_completeness_calculation(self):
        """data_completeness counts only truly-extracted values, not free passes."""
        metrics = {
            "Revenue": _make_mapping_result("Revenue"),
            "NetIncome": _make_mapping_result("NetIncome"),
            "COGS": _make_mapping_result("COGS", source=MappingSource.CONFIG, validation_status="pending", concept=None),
        }
        reasons = {"COGS": {"reason": "not_applicable", "notes": ""}}
        result = self._compute(metrics, exclusion_reasons=reasons)

        # 3 total metrics, 2 truly extracted (COGS free pass doesn't count as real data)
        # data_completeness = 2/3 ≈ 0.667
        assert result.data_completeness == pytest.approx(2 / 3, abs=0.01)

    def test_data_completeness_with_extraction_failed(self):
        """extraction_failed reduces data_completeness."""
        metrics = {
            "Revenue": _make_mapping_result("Revenue"),
            "NetIncome": _make_mapping_result("NetIncome"),
            "COGS": _make_mapping_result("COGS", source=MappingSource.CONFIG, validation_status="pending", concept=None),
        }
        reasons = {"COGS": {"reason": "extraction_failed", "notes": ""}}
        result = self._compute(metrics, exclusion_reasons=reasons)

        # 3 total metrics, 2 valid (COGS penalized)
        # data_completeness = 2/3 ≈ 0.667
        assert result.data_completeness == pytest.approx(2 / 3, abs=0.01)


class TestEfCqsStrict:
    """Tests for the strict EF-CQS field (Sub-project A).

    The lenient ef_cqs subtracts explained_variance_count from BOTH numerator AND
    denominator (laundering). ef_cqs_strict adds it back to the denominator only —
    keeping documented divergences as failures.
    """

    def _compute(self, metrics, known_divergences=None):
        from edgar.xbrl.standardization.tools.auto_eval import _compute_company_cqs
        golden_set = set()
        validations = {}
        for m in metrics.values():
            if m.validation_status == "valid" and m.source != MappingSource.CONFIG:
                validations[m.metric] = MockValidation()
        return _compute_company_cqs(
            "TEST", metrics, golden_set, validations,
            known_divergences=known_divergences,
        )

    def test_strict_equals_lenient_when_no_divergences(self):
        """Without known_divergences, strict and lenient EF-CQS are identical."""
        metrics = {
            "Revenue": _make_mapping_result("Revenue"),
            "NetIncome": _make_mapping_result("NetIncome"),
        }
        result = self._compute(metrics)

        assert result.ef_cqs == pytest.approx(result.ef_cqs_strict, abs=1e-9)
        # Both should be 1.0 (2 of 2 pass)
        assert result.ef_cqs_strict == pytest.approx(1.0, abs=1e-9)

    def test_strict_lower_than_lenient_with_divergences(self):
        """With a known_divergence, strict is lower (denominator wider)."""
        metrics = {
            "Revenue": _make_mapping_result("Revenue"),
            "NetIncome": _make_mapping_result("NetIncome"),
            "Capex": _make_mapping_result("Capex"),  # Will be marked as known divergence
        }
        # Lenient: Capex skipped from both numerator and denominator → 2/2 = 1.0
        # Strict:  Capex stays in denominator as failure → 2/3 ≈ 0.667
        result = self._compute(metrics, known_divergences={"Capex"})

        assert result.explained_variance_count == 1
        assert result.ef_cqs == pytest.approx(1.0, abs=1e-9)
        assert result.ef_cqs_strict == pytest.approx(2 / 3, abs=1e-9)
        assert result.ef_cqs_strict < result.ef_cqs

    def test_strict_zero_division_safe(self):
        """Strict EF-CQS is 0.0 when strict denominator is 0 (degenerate case)."""
        # All metrics are unverified — strict_total = 0
        metrics = {
            "Revenue": _make_mapping_result("Revenue", validation_status="unverified"),
        }
        result = self._compute(metrics)

        assert result.ef_cqs_strict == 0.0


class TestEfCqsStrictAggregation:
    """Test that aggregate CQSResult includes ef_cqs_strict."""

    def test_aggregate_ef_cqs_strict_is_mean_across_companies(self):
        from edgar.xbrl.standardization.tools.auto_eval import _aggregate_cqs, CompanyCQS

        scores = {
            "AAPL": CompanyCQS(
                ticker="AAPL", pass_rate=0.9, mean_variance=1.0,
                coverage_rate=0.95, golden_master_rate=0.8, regression_count=0,
                metrics_total=37, metrics_mapped=35, metrics_valid=33,
                metrics_excluded=2, cqs=0.85,
                ef_cqs=0.95, ef_cqs_strict=0.90,
            ),
            "JPM": CompanyCQS(
                ticker="JPM", pass_rate=0.85, mean_variance=2.0,
                coverage_rate=0.90, golden_master_rate=0.75, regression_count=0,
                metrics_total=37, metrics_mapped=30, metrics_valid=28,
                metrics_excluded=7, cqs=0.82,
                ef_cqs=0.92, ef_cqs_strict=0.85,
            ),
        }
        result = _aggregate_cqs(scores, baseline_cqs=None, duration=1.0)

        assert result.ef_cqs == pytest.approx((0.95 + 0.92) / 2, abs=0.001)
        assert result.ef_cqs_strict == pytest.approx((0.90 + 0.85) / 2, abs=0.001)
        # Strict should be lower than lenient (the whole point of the field)
        assert result.ef_cqs_strict < result.ef_cqs

    def test_serialization_roundtrip_preserves_ef_cqs_strict(self):
        from edgar.xbrl.standardization.tools.auto_eval import CQSResult, CompanyCQS

        original = CQSResult(
            pass_rate=0.9, mean_variance=1.0, coverage_rate=0.95,
            golden_master_rate=0.8, regression_rate=0.0, cqs=0.85,
            companies_evaluated=1, total_metrics=37, total_mapped=35,
            total_valid=33, total_regressions=0,
            ef_cqs=0.93, ef_cqs_strict=0.87,
            company_scores={
                "AAPL": CompanyCQS(
                    ticker="AAPL", pass_rate=0.9, mean_variance=1.0,
                    coverage_rate=0.95, golden_master_rate=0.8, regression_count=0,
                    metrics_total=37, metrics_mapped=35, metrics_valid=33,
                    metrics_excluded=2, cqs=0.85,
                    ef_cqs=0.93, ef_cqs_strict=0.87,
                ),
            },
        )
        d = original.to_dict()
        restored = CQSResult.from_dict(d)

        assert restored.ef_cqs_strict == pytest.approx(0.87)
        assert restored.company_scores["AAPL"].ef_cqs_strict == pytest.approx(0.87)


class TestCQSResultAggregation:
    """Test that aggregate CQSResult includes scoring integrity fields."""

    def test_aggregate_includes_new_fields(self):
        from edgar.xbrl.standardization.tools.auto_eval import _aggregate_cqs, CompanyCQS

        scores = {
            "AAPL": CompanyCQS(
                ticker="AAPL", pass_rate=0.9, mean_variance=1.0,
                coverage_rate=0.95, golden_master_rate=0.8, regression_count=0,
                metrics_total=37, metrics_mapped=35, metrics_valid=33,
                metrics_excluded=2, cqs=0.85, raw_cqs=0.80,
                data_completeness=0.89, extraction_failed_count=1,
            ),
            "JPM": CompanyCQS(
                ticker="JPM", pass_rate=0.85, mean_variance=2.0,
                coverage_rate=0.90, golden_master_rate=0.75, regression_count=0,
                metrics_total=37, metrics_mapped=30, metrics_valid=28,
                metrics_excluded=7, cqs=0.82, raw_cqs=0.75,
                data_completeness=0.76, extraction_failed_count=2,
            ),
        }
        result = _aggregate_cqs(scores, baseline_cqs=None, duration=1.0)

        assert result.raw_cqs == pytest.approx((0.80 + 0.75) / 2, abs=0.001)
        assert result.data_completeness == pytest.approx((0.89 + 0.76) / 2, abs=0.001)
        assert result.total_extraction_failed == 3


class TestCQSResultSerialization:
    """Test that new fields survive to_dict/from_dict roundtrip."""

    def test_roundtrip(self):
        from edgar.xbrl.standardization.tools.auto_eval import CQSResult

        original = CQSResult(
            pass_rate=0.9, mean_variance=1.0, coverage_rate=0.95,
            golden_master_rate=0.8, regression_rate=0.0, cqs=0.85,
            companies_evaluated=2, total_metrics=74, total_mapped=70,
            total_valid=66, total_regressions=0,
            raw_cqs=0.78, data_completeness=0.85, total_extraction_failed=3,
        )
        d = original.to_dict()
        restored = CQSResult.from_dict(d)

        assert restored.raw_cqs == pytest.approx(0.78)
        assert restored.data_completeness == pytest.approx(0.85)
        assert restored.total_extraction_failed == 3
