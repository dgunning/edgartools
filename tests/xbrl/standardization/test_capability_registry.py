"""
Tests for the 3-component Autonomous Data Quality Improvement System:
- C1: Capability-Aware Triage (GapDisposition classification)
- C2: Sign-Aware Gap Classification (cosmetic sign gap suppression)
- C3: Applicability-Aware CQS Scoring (CONFIG exclusion credit)
"""

import pytest

from edgar.xbrl.standardization.tools.capability_registry import (
    GapDisposition,
    classify_gap_disposition,
    triage_gaps,
)
from edgar.xbrl.standardization.tools.auto_eval_loop import UnresolvedGap
from edgar.xbrl.standardization.models import MetricConfig, MappingResult, MappingSource


# =============================================================================
# C1: Capability-Aware Triage
# =============================================================================

class TestGapDisposition:
    """Test classify_gap_disposition() classification rules."""

    def test_sign_error_is_scoring_inert(self):
        """Sign-inverted metrics pass CQS via abs() comparison -> scoring_inert."""
        result = classify_gap_disposition(
            root_cause="sign_error",
            reference_value=-90e9,
            hv_subtype="hv_sign_inverted",
        )
        assert result == GapDisposition.SCORING_INERT

    def test_hv_sign_inverted_subtype_is_scoring_inert(self):
        """hv_sign_inverted subtype alone triggers scoring_inert."""
        result = classify_gap_disposition(
            root_cause=None,
            reference_value=-50e9,
            hv_subtype="hv_sign_inverted",
        )
        assert result == GapDisposition.SCORING_INERT

    def test_industry_structural_no_ref_is_scoring_inert(self):
        """Industry-structural with ref=None -> already unverified in CQS."""
        result = classify_gap_disposition(
            root_cause="industry_structural",
            reference_value=None,
            hv_subtype=None,
        )
        assert result == GapDisposition.SCORING_INERT

    def test_extension_concept_is_engine_blocked(self):
        """Extension concepts can't be resolved by config changes."""
        result = classify_gap_disposition(
            root_cause="extension_concept",
            reference_value=50e9,
            hv_subtype=None,
        )
        assert result == GapDisposition.ENGINE_BLOCKED

    def test_missing_concept_with_ref_is_config_fixable(self):
        """Missing concept with reference value -> config can fix."""
        result = classify_gap_disposition(
            root_cause="missing_concept",
            reference_value=50e9,
            hv_subtype=None,
        )
        assert result == GapDisposition.CONFIG_FIXABLE

    def test_wrong_concept_with_ref_is_config_fixable(self):
        """Wrong concept with reference value -> config can fix."""
        result = classify_gap_disposition(
            root_cause="wrong_concept",
            reference_value=100e9,
            hv_subtype=None,
        )
        assert result == GapDisposition.CONFIG_FIXABLE

    def test_default_is_config_fixable(self):
        """Unknown root causes default to config_fixable."""
        result = classify_gap_disposition(
            root_cause="some_unknown_cause",
            reference_value=10e9,
            hv_subtype=None,
        )
        assert result == GapDisposition.CONFIG_FIXABLE

    def test_industry_structural_with_ref_is_config_fixable(self):
        """Industry-structural WITH a reference value is actionable."""
        result = classify_gap_disposition(
            root_cause="industry_structural",
            reference_value=25e9,
            hv_subtype=None,
        )
        assert result == GapDisposition.CONFIG_FIXABLE


class TestTriageGaps:
    """Test triage_gaps() partitioning."""

    def _make_gap(self, root_cause, hv_subtype=None, reference_value=50e9):
        return UnresolvedGap(
            ticker="TEST",
            metric="TestMetric",
            gap_type="unmapped",
            root_cause=root_cause,
            hv_subtype=hv_subtype,
            reference_value=reference_value,
        )

    def test_triage_partitions_correctly(self):
        gaps = [
            self._make_gap("sign_error", "hv_sign_inverted"),
            self._make_gap("industry_structural", reference_value=None),
            self._make_gap("missing_concept"),
            self._make_gap("wrong_concept"),
            self._make_gap("extension_concept"),
        ]
        triaged = triage_gaps(gaps)
        assert len(triaged[GapDisposition.SCORING_INERT]) == 2
        assert len(triaged[GapDisposition.CONFIG_FIXABLE]) == 2
        assert len(triaged[GapDisposition.ENGINE_BLOCKED]) == 1


class TestUnresolvedGapDisposition:
    """Test disposition field on UnresolvedGap dataclass."""

    def test_default_disposition(self):
        gap = UnresolvedGap(ticker="AAPL", metric="Revenue", gap_type="unmapped")
        assert gap.disposition == "config_fixable"

    def test_disposition_serialization(self):
        gap = UnresolvedGap(
            ticker="AAPL", metric="Revenue", gap_type="unmapped",
            disposition="scoring_inert",
        )
        d = gap.to_dict()
        assert d["disposition"] == "scoring_inert"

    def test_disposition_deserialization(self):
        d = {
            "ticker": "AAPL", "metric": "Revenue", "gap_type": "unmapped",
            "disposition": "engine_blocked",
        }
        gap = UnresolvedGap.from_dict(d)
        assert gap.disposition == "engine_blocked"

    def test_disposition_deserialization_default(self):
        """Old manifests without disposition field default to config_fixable."""
        d = {"ticker": "AAPL", "metric": "Revenue", "gap_type": "unmapped"}
        gap = UnresolvedGap.from_dict(d)
        assert gap.disposition == "config_fixable"


# =============================================================================
# C2: Sign-Aware Gap Classification
# =============================================================================

class TestSignConvention:
    """Test sign_convention field on MetricConfig."""

    def test_metric_config_sign_convention_default(self):
        mc = MetricConfig(
            name="Revenue",
            description="Total revenue",
            known_concepts=["Revenues"],
        )
        assert mc.sign_convention is None

    def test_metric_config_sign_convention_negate(self):
        mc = MetricConfig(
            name="Capex",
            description="Capital expenditures",
            known_concepts=["PaymentsToAcquirePropertyPlantAndEquipment"],
            sign_convention="negate",
        )
        assert mc.sign_convention == "negate"


# =============================================================================
# C3: Applicability-Aware CQS Scoring
# =============================================================================

class TestApplicabilityCQS:
    """Test that CONFIG-excluded metrics count as valid in CQS."""

    def test_config_excluded_counts_in_total(self):
        """CONFIG-excluded metrics should be counted in total and as valid."""
        from edgar.xbrl.standardization.tools.auto_eval import _compute_company_cqs

        metrics = {
            "Revenue": MappingResult(
                metric="Revenue", company="TEST", fiscal_period="2024-FY",
                concept="Revenues", value=100e9, confidence=1.0,
                source=MappingSource.TREE, validation_status="valid",
            ),
            "COGS": MappingResult(
                metric="COGS", company="TEST", fiscal_period="2024-FY",
                source=MappingSource.CONFIG, validation_status="pending",
            ),
            "NetIncome": MappingResult(
                metric="NetIncome", company="TEST", fiscal_period="2024-FY",
                concept="NetIncomeLoss", value=10e9, confidence=1.0,
                source=MappingSource.TREE, validation_status="invalid",
            ),
        }

        class MockValidation:
            def __init__(self, variance_pct=None, ef_pass=False, sa_pass=False,
                         rfa_pass=False, sma_pass=False, variance_type="raw",
                         reference_value=None, xbrl_value=None, notes=""):
                self.variance_pct = variance_pct
                self.ef_pass = ef_pass
                self.sa_pass = sa_pass
                self.rfa_pass = rfa_pass
                self.sma_pass = sma_pass
                self.variance_type = variance_type
                self.reference_value = reference_value
                self.xbrl_value = xbrl_value
                self.notes = notes

        validations = {
            "Revenue": MockValidation(variance_pct=0.5, ef_pass=True, sa_pass=True,
                                       rfa_pass=True, sma_pass=True),
            "NetIncome": MockValidation(variance_pct=15.0, ef_pass=False, sa_pass=False,
                                         reference_value=12e9),
        }

        cqs = _compute_company_cqs(
            ticker="TEST",
            metrics=metrics,
            golden_set=set(),
            validations=validations,
        )

        # With C3: total=3 (Revenue + COGS_excluded + NetIncome), valid=2 (Revenue + COGS)
        assert cqs.pass_rate == pytest.approx(2/3, abs=0.01)
        assert cqs.metrics_excluded == 1
        assert cqs.metrics_total == 3
