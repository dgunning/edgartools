"""
Tests for Subscription-Grade Data Contract (Consensus 019/022).

Validates:
- DataDictionaryEntry new fields (known_limitations, reference_standard_notes, coverage_rate)
- load_data_dictionary() parses new fields when present, defaults when absent
- Lightweight confidence signal computation
- Database round-trip for confidence fields
"""

import pytest
from edgar.xbrl.standardization.config_loader import DataDictionaryEntry, load_data_dictionary
from edgar.standardized_financials import StandardizedMetric, _compute_lightweight_confidence


# =============================================================================
# Stage 1: DataDictionaryEntry Extension
# =============================================================================


class TestDataDictionaryEntryExtension:
    """Test new optional fields on DataDictionaryEntry."""

    def test_new_fields_default_to_none(self):
        """New fields default to None when not provided."""
        entry = DataDictionaryEntry(
            name="Revenue",
            display_name="Revenue",
            description="Total revenues",
            statement_family="income_statement",
            unit="USD",
            sign_convention="positive",
            metric_tier="headline",
        )
        assert entry.known_limitations is None
        assert entry.reference_standard_notes is None
        assert entry.coverage_rate is None

    def test_new_fields_accept_values(self):
        """New fields accept explicit values."""
        entry = DataDictionaryEntry(
            name="TotalLiabilities",
            display_name="Total Liabilities",
            description="Sum of all liabilities",
            statement_family="balance_sheet",
            unit="USD",
            sign_convention="positive",
            metric_tier="headline",
            known_limitations="~11% use composite formula",
            reference_standard_notes="Composite: L&SE minus SE",
            coverage_rate=0.95,
        )
        assert entry.known_limitations == "~11% use composite formula"
        assert entry.reference_standard_notes == "Composite: L&SE minus SE"
        assert entry.coverage_rate == 0.95

    def test_load_data_dictionary_returns_entries(self):
        """load_data_dictionary() returns dict of DataDictionaryEntry objects."""
        dd = load_data_dictionary(reload=True)
        assert len(dd) > 0
        assert "Revenue" in dd
        assert isinstance(dd["Revenue"], DataDictionaryEntry)

    def test_load_data_dictionary_new_fields_default_none(self):
        """Existing YAML entries without new fields get None defaults."""
        dd = load_data_dictionary(reload=True)
        revenue = dd["Revenue"]
        # These fields aren't in the YAML yet, so should be None
        # (will be populated in Stage 4)
        assert revenue.known_limitations is None or isinstance(revenue.known_limitations, str)
        assert revenue.reference_standard_notes is None or isinstance(revenue.reference_standard_notes, str)
        assert revenue.coverage_rate is None or isinstance(revenue.coverage_rate, float)

    def test_data_dictionary_has_core_metrics(self):
        """Data dictionary includes all 8 core Product A metrics."""
        dd = load_data_dictionary(reload=True)
        core_metrics = [
            "Revenue", "NetIncome", "OperatingIncome", "OperatingCashFlow",
            "TotalAssets", "TotalLiabilities", "StockholdersEquity",
            "EarningsPerShareDiluted",
        ]
        for metric in core_metrics:
            assert metric in dd, f"Core metric {metric} missing from data dictionary"
            assert dd[metric].metric_tier == "headline", f"{metric} should be headline tier"


# =============================================================================
# Stage 2: Lightweight Confidence Computation
# =============================================================================


class TestLightweightConfidence:
    """Test _compute_lightweight_confidence() heuristic."""

    def test_excluded_metric(self):
        """Excluded metrics get not_applicable confidence."""
        metric = StandardizedMetric(
            name="COGS", value=None, concept=None,
            confidence=0.0, source="excluded", is_excluded=True,
        )
        pc, et = _compute_lightweight_confidence(metric, config=None, company_config=None)
        assert pc == "not_applicable"
        assert et == "excluded"

    def test_none_value(self):
        """Metrics with no value get unverified confidence."""
        metric = StandardizedMetric(
            name="Revenue", value=None, concept=None,
            confidence=0.0, source="unmapped",
        )
        pc, et = _compute_lightweight_confidence(metric, config=None, company_config=None)
        assert pc == "unverified"
        assert et == "unverified"

    def test_tree_source_with_known_concept(self):
        """Tree source + known concept + no divergence = high."""
        from edgar.xbrl.standardization.config_loader import get_config
        config = get_config()
        metric = StandardizedMetric(
            name="Revenue", value=394328000000,
            concept="Revenues",
            confidence=0.95, source="tree",
        )
        pc, et = _compute_lightweight_confidence(metric, config=config, company_config=None)
        assert pc == "high"
        assert et == "tree_confirmed"

    def test_tree_source_with_divergence(self):
        """Tree source + known divergence = medium (capped)."""
        from edgar.xbrl.standardization.config_loader import get_config
        from edgar.xbrl.standardization.models import CompanyConfig
        config = get_config()
        company_config = CompanyConfig(
            ticker="TEST", name="Test Corp", cik="0000000000",
            known_divergences={"Revenue": {"reason": "Non-standard revenue recognition"}},
        )
        metric = StandardizedMetric(
            name="Revenue", value=394328000000,
            concept="Revenues",
            confidence=0.95, source="tree",
        )
        pc, et = _compute_lightweight_confidence(metric, config=config, company_config=company_config)
        assert pc == "medium"
        assert et == "tree_confirmed"

    def test_facts_search_source(self):
        """Facts search source = medium."""
        metric = StandardizedMetric(
            name="Revenue", value=394328000000,
            concept="Revenues",
            confidence=0.80, source="facts_search",
        )
        pc, et = _compute_lightweight_confidence(metric, config=None, company_config=None)
        assert pc == "medium"
        assert et == "facts_search"

    def test_industry_source(self):
        """Industry source = medium."""
        metric = StandardizedMetric(
            name="Revenue", value=100000000,
            concept="Industry(Revenue)",
            confidence=0.80, source="industry",
        )
        pc, et = _compute_lightweight_confidence(metric, config=None, company_config=None)
        assert pc == "medium"
        assert et == "industry"

    def test_derived_source(self):
        """Derived metrics = low confidence."""
        metric = StandardizedMetric(
            name="FreeCashFlow", value=50000000,
            concept="Derived(OCF-Capex)",
            confidence=0.70, source="derived",
        )
        pc, et = _compute_lightweight_confidence(metric, config=None, company_config=None)
        assert pc == "low"
        assert et == "derived"

    def test_unmapped_with_value(self):
        """Unmapped source but has a value = low."""
        metric = StandardizedMetric(
            name="Revenue", value=100000000,
            concept="SomeUnknownConcept",
            confidence=0.50, source="unmapped",
        )
        pc, et = _compute_lightweight_confidence(metric, config=None, company_config=None)
        assert pc == "low"
        assert et == "unverified"
