"""Tests for expand_cohort — inner loop of expansion pipeline."""
import json
from dataclasses import dataclass, field
from typing import List, Optional
from unittest.mock import patch, MagicMock
from pathlib import Path

from edgar.xbrl.standardization.tools.expand_cohort import (
    run_expand_cohort,
    detect_archetype_gaps,
    _diagnose_and_fix,
    _try_deterministic_fix,
)
from edgar.xbrl.standardization.tools.auto_eval import ExtractionEvidence, MetricGap


def test_detect_archetype_gaps():
    """Amendment 3: Flag companies without matching industry_metrics.yaml section."""
    gaps = detect_archetype_gaps([
        {"ticker": "TEST", "sic_code": "9999", "archetype": "A"},
        {"ticker": "JPM", "sic_code": "6022", "archetype": "B"},
    ])
    # SIC 9999 has no industry_metrics.yaml section -> flagged
    assert "TEST" in gaps
    # SIC 6022 is in banking (6020-6099) -> covered
    assert "JPM" not in gaps


@patch("edgar.xbrl.standardization.tools.expand_cohort._onboard_single")
@patch("edgar.xbrl.standardization.tools.expand_cohort._measure_cohort")
@patch("edgar.xbrl.standardization.tools.expand_cohort._diagnose_and_fix")
def test_run_expand_cohort_produces_report(mock_fix, mock_measure, mock_onboard, tmp_path):
    """Full pipeline produces a cohort report markdown file."""
    # Mock onboarding
    mock_result = MagicMock()
    mock_result.ticker = "HD"
    mock_result.cik = 354950
    mock_result.company_name = "Home Depot"
    mock_result.archetype = "A"
    mock_result.sic_code = "5211"
    mock_result.error = None
    mock_result.pass_rate = 85.0
    mock_onboard.return_value = {"HD": mock_result}

    # Mock measurement
    mock_company_cqs = MagicMock()
    mock_company_cqs.ef_cqs = 0.88
    mock_company_cqs.headline_ef_rate = 0.90
    mock_measure.return_value = {"HD": mock_company_cqs}

    # Mock diagnosis (returns fixes applied + unresolved gaps)
    mock_fix.return_value = ([], [])  # No fixes, no unresolved

    report_path = run_expand_cohort(
        tickers=["HD"],
        cohort_name="test",
        output_dir=tmp_path,
    )

    assert report_path.exists()
    content = report_path.read_text()
    assert "# Cohort Report" in content
    assert "HD" in content


def test_detect_archetype_gaps_empty_sic():
    """Companies with no SIC code are flagged."""
    gaps = detect_archetype_gaps([
        {"ticker": "UNKNOWN", "sic_code": None, "archetype": "A"},
    ])
    assert "UNKNOWN" in gaps


def test_diagnose_and_fix_components_derived_from_extraction_evidence():
    """components_found/needed are derived from extraction_evidence, not MetricGap fields."""
    evidence = ExtractionEvidence(
        metric="Revenue",
        ticker="AAPL",
        components_used=["us-gaap:Revenues", "us-gaap:SalesRevenueNet"],
        components_missing=["us-gaap:RevenueFromContractWithCustomer"],
    )
    gap = MetricGap(
        ticker="AAPL",
        metric="Revenue",
        gap_type="high_variance",
        estimated_impact=0.1,
        extraction_evidence=evidence,
    )

    # _diagnose_and_fix does a local import of identify_gaps; patch the source module
    with patch("edgar.xbrl.standardization.tools.auto_eval.identify_gaps", return_value=([gap], {})), \
         patch("edgar.xbrl.standardization.tools.expand_cohort._try_deterministic_fix", return_value=None):
        _, unresolved = _diagnose_and_fix(["AAPL"], {})

    assert len(unresolved) == 1
    entry = unresolved[0]
    # components_found = len(components_used) = 2
    assert entry.components_found == 2
    # components_needed = len(components_used) + len(components_missing) = 2 + 1 = 3
    assert entry.components_needed == 3


def test_diagnose_and_fix_components_none_extraction_evidence():
    """When extraction_evidence is None, components default to 0."""
    gap = MetricGap(
        ticker="TSLA",
        metric="NetIncome",
        gap_type="unmapped",
        estimated_impact=0.05,
        extraction_evidence=None,
    )

    # _diagnose_and_fix does a local import of identify_gaps; patch the source module
    with patch("edgar.xbrl.standardization.tools.auto_eval.identify_gaps", return_value=([gap], {})), \
         patch("edgar.xbrl.standardization.tools.expand_cohort._try_deterministic_fix", return_value=None):
        _, unresolved = _diagnose_and_fix(["TSLA"], {})

    assert len(unresolved) == 1
    entry = unresolved[0]
    assert entry.components_found == 0
    assert entry.components_needed == 0


@patch("edgar.xbrl.standardization.tools.expand_cohort._onboard_single")
@patch("edgar.xbrl.standardization.tools.expand_cohort._measure_cohort")
@patch("edgar.xbrl.standardization.tools.expand_cohort._diagnose_and_fix")
def test_quality_tier_verified_at_095(mock_fix, mock_measure, mock_onboard, tmp_path):
    """Companies at EF-CQS >= 0.95 get 'verified' status."""
    mock_result = MagicMock()
    mock_result.error = None
    mock_onboard.return_value = {"NFLX": mock_result}

    mock_cqs = MagicMock()
    mock_cqs.ef_cqs = 0.96
    mock_measure.return_value = {"NFLX": mock_cqs}
    mock_fix.return_value = ([], [])

    report_path = run_expand_cohort(tickers=["NFLX"], cohort_name="tier-test", output_dir=tmp_path)
    content = report_path.read_text()
    assert "verified" in content


@patch("edgar.xbrl.standardization.tools.expand_cohort._onboard_single")
@patch("edgar.xbrl.standardization.tools.expand_cohort._measure_cohort")
@patch("edgar.xbrl.standardization.tools.expand_cohort._diagnose_and_fix")
def test_quality_tier_provisional_at_080_to_094(mock_fix, mock_measure, mock_onboard, tmp_path):
    """Companies at 0.80 <= EF-CQS < 0.95 get 'provisional' status."""
    mock_result = MagicMock()
    mock_result.error = None
    mock_onboard.return_value = {"HD": mock_result}

    mock_cqs = MagicMock()
    mock_cqs.ef_cqs = 0.88
    mock_measure.return_value = {"HD": mock_cqs}
    mock_fix.return_value = ([], [])

    report_path = run_expand_cohort(tickers=["HD"], cohort_name="tier-test", output_dir=tmp_path)
    content = report_path.read_text()
    assert "provisional" in content


@patch("edgar.xbrl.standardization.tools.expand_cohort._onboard_single")
@patch("edgar.xbrl.standardization.tools.expand_cohort._measure_cohort")
@patch("edgar.xbrl.standardization.tools.expand_cohort._diagnose_and_fix")
def test_quality_tier_needs_investigation_below_080(mock_fix, mock_measure, mock_onboard, tmp_path):
    """Companies at EF-CQS < 0.80 get 'needs_investigation' status."""
    mock_result = MagicMock()
    mock_result.error = None
    mock_onboard.return_value = {"XYZ": mock_result}

    mock_cqs = MagicMock()
    mock_cqs.ef_cqs = 0.65
    mock_measure.return_value = {"XYZ": mock_cqs}
    mock_fix.return_value = ([], [])

    report_path = run_expand_cohort(tickers=["XYZ"], cohort_name="tier-test", output_dir=tmp_path)
    content = report_path.read_text()
    assert "needs_investigation" in content


def test_deterministic_fix_sign_error():
    """Sign-inverted gap gets FIX_SIGN_CONVENTION action."""
    gap = MetricGap(
        ticker="HD",
        metric="Depreciation",
        gap_type="high_variance",
        estimated_impact=0.05,
        root_cause="sign_error",
        reference_value=500.0,
        xbrl_value=-500.0,
    )
    fix = _try_deterministic_fix(gap)
    assert fix is not None
    assert fix["action"] == "FIX_SIGN_CONVENTION"
    assert fix["confidence"] >= 0.95


def test_deterministic_fix_concept_absent_unmapped():
    """Unmapped metric with missing_concept root cause gets EXCLUDE_METRIC."""
    evidence = ExtractionEvidence(
        metric="ResearchAndDevelopment",
        ticker="HD",
        components_used=[],
        components_missing=[],
    )
    gap = MetricGap(
        ticker="HD",
        metric="ResearchAndDevelopment",
        gap_type="unmapped",
        estimated_impact=0.03,
        root_cause="missing_concept",
        extraction_evidence=evidence,
    )
    fix = _try_deterministic_fix(gap)
    assert fix is not None
    assert fix["action"] == "EXCLUDE_METRIC"


def test_deterministic_fix_high_variance_escalates():
    """High variance wrong_concept is NOT auto-fixed."""
    gap = MetricGap(
        ticker="HD",
        metric="Revenue",
        gap_type="high_variance",
        estimated_impact=0.2,
        root_cause="wrong_concept",
        reference_value=100.0,
        xbrl_value=50.0,
    )
    fix = _try_deterministic_fix(gap)
    assert fix is None  # escalate
