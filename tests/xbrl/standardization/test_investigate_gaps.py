"""Tests for investigate_gaps — outer loop of expansion pipeline."""
from dataclasses import dataclass
from typing import Optional

from edgar.xbrl.standardization.tools.investigate_gaps import (
    prioritize_gaps,
    detect_patterns,
    classify_root_cause,
    GapGroup,
)


@dataclass
class MockGap:
    """Minimal mock for MetricGap fields used by investigate_gaps."""
    ticker: str
    metric: str
    gap_type: str
    estimated_impact: float
    current_variance: Optional[float] = None
    reference_value: Optional[float] = None
    xbrl_value: Optional[float] = None
    graveyard_count: int = 0
    root_cause: Optional[str] = None


def test_prioritize_gaps_groups_by_metric_industry():
    """Amendment 6: Gaps grouped by (metric, industry) and ranked by total impact."""
    gaps = [
        MockGap(ticker="D", metric="GrossProfit", gap_type="unmapped", estimated_impact=0.02),
        MockGap(ticker="NEE", metric="GrossProfit", gap_type="unmapped", estimated_impact=0.02),
        MockGap(ticker="SO", metric="GrossProfit", gap_type="unmapped", estimated_impact=0.02),
        MockGap(ticker="HD", metric="ShortTermDebt", gap_type="high_variance", estimated_impact=0.01),
    ]
    industry_map = {"D": "utilities", "NEE": "utilities", "SO": "utilities", "HD": None}

    groups = prioritize_gaps(gaps, industry_map)

    # GrossProfit group (3 utilities) should be first (higher total impact)
    assert groups[0].metric == "GrossProfit"
    assert groups[0].industry == "utilities"
    assert len(groups[0].gaps) == 3
    assert groups[0].total_impact > groups[1].total_impact


def test_prioritize_gaps_none_industry_grouped():
    """Gaps with no industry are grouped under None."""
    gaps = [
        MockGap(ticker="A", metric="Revenue", gap_type="unmapped", estimated_impact=0.05),
        MockGap(ticker="B", metric="Revenue", gap_type="unmapped", estimated_impact=0.05),
    ]
    industry_map = {"A": None, "B": None}

    groups = prioritize_gaps(gaps, industry_map)
    assert len(groups) == 1
    assert groups[0].industry is None
    assert len(groups[0].gaps) == 2


def test_detect_patterns_flags_repeated_fixes():
    """Amendment 5: Same fix applied to 3+ companies in same industry -> pattern detected."""
    fixes = [
        {"ticker": "D", "metric": "GrossProfit", "action": "EXCLUDE_METRIC", "industry": "utilities"},
        {"ticker": "NEE", "metric": "GrossProfit", "action": "EXCLUDE_METRIC", "industry": "utilities"},
        {"ticker": "SO", "metric": "GrossProfit", "action": "EXCLUDE_METRIC", "industry": "utilities"},
        {"ticker": "HD", "metric": "Inventory", "action": "EXCLUDE_METRIC", "industry": None},
    ]
    patterns = detect_patterns(fixes)

    assert len(patterns) == 1
    assert patterns[0]["metric"] == "GrossProfit"
    assert patterns[0]["industry"] == "utilities"
    assert patterns[0]["count"] == 3


def test_detect_patterns_below_threshold():
    """Only 2 companies with same fix -> no pattern detected."""
    fixes = [
        {"ticker": "D", "metric": "GrossProfit", "action": "EXCLUDE_METRIC", "industry": "utilities"},
        {"ticker": "NEE", "metric": "GrossProfit", "action": "EXCLUDE_METRIC", "industry": "utilities"},
    ]
    patterns = detect_patterns(fixes)
    assert len(patterns) == 0


def test_classify_root_cause_concept_absent():
    """classify_root_cause with empty discovery results -> concept_absent."""
    result = classify_root_cause(
        gap_type="unmapped",
        discovery_results=[],
        reference_value=100.0,
        xbrl_value=None,
    )
    assert result == "concept_absent"


def test_classify_root_cause_sign_error():
    """classify_root_cause with exact negation -> sign_error."""
    result = classify_root_cause(
        gap_type="high_variance",
        discovery_results=[{"concept": "X", "value": -100.0}],
        reference_value=100.0,
        xbrl_value=-100.0,
    )
    assert result == "sign_error"


def test_classify_root_cause_wrong_concept():
    """classify_root_cause with value close but not matching -> wrong_concept."""
    result = classify_root_cause(
        gap_type="high_variance",
        discovery_results=[{"concept": "SomeConcept", "value": 105.0}],
        reference_value=100.0,
        xbrl_value=105.0,
    )
    assert result == "wrong_concept"


def test_classify_root_cause_reference_mismatch():
    """classify_root_cause with no XBRL value but has discovery -> reference_mismatch."""
    result = classify_root_cause(
        gap_type="high_variance",
        discovery_results=[{"concept": "X", "value": 200.0}],
        reference_value=100.0,
        xbrl_value=None,
    )
    assert result == "reference_mismatch"
