"""Tests for expand_cohort — inner loop of expansion pipeline."""
import json
from unittest.mock import patch, MagicMock
from pathlib import Path

from edgar.xbrl.standardization.tools.expand_cohort import (
    run_expand_cohort,
    detect_archetype_gaps,
)


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
