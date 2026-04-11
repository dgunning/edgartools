"""Tests for upstream GAAP mapping expansion in ConfigLoader."""

import json
import pytest
from pathlib import Path
from edgar.xbrl.standardization.config_loader import ConfigLoader


@pytest.fixture
def config():
    """Load the full config with GAAP expansion applied."""
    return ConfigLoader().load()


@pytest.fixture
def gaap_index():
    """Load the raw GAAP index for direct testing."""
    return ConfigLoader()._load_gaap_mappings()


class TestLoadGaapMappings:
    """Tests for _load_gaap_mappings filtering logic."""

    def test_returns_dict(self, gaap_index):
        assert isinstance(gaap_index, dict)
        assert len(gaap_index) > 0

    def test_filters_ambiguous_entries(self, gaap_index):
        """Ambiguous entries (multiple standard_tags) should be excluded."""
        # Load raw data to find an ambiguous entry
        config_dir = Path(__file__).parent.parent / "edgar/xbrl/standardization/config"
        with open(config_dir / "upstream_gaap_mappings.json") as f:
            raw = json.load(f)

        # Find all concepts marked ambiguous
        ambiguous_concepts = [k for k, v in raw.items() if v.get("ambiguous")]
        assert len(ambiguous_concepts) > 0, "Test data should have ambiguous entries"

        # None of these should appear in the index values
        all_concepts_in_index = set()
        for concepts in gaap_index.values():
            all_concepts_in_index.update(concepts)

        for concept in ambiguous_concepts:
            assert concept not in all_concepts_in_index, f"Ambiguous concept {concept} should be filtered"

    def test_filters_deprecated_entries(self, gaap_index):
        """Deprecated entries should be excluded."""
        config_dir = Path(__file__).parent.parent / "edgar/xbrl/standardization/config"
        with open(config_dir / "upstream_gaap_mappings.json") as f:
            raw = json.load(f)

        deprecated_concepts = [k for k, v in raw.items() if v.get("deprecated")]
        assert len(deprecated_concepts) > 0, "Test data should have deprecated entries"

        all_concepts_in_index = set()
        for concepts in gaap_index.values():
            all_concepts_in_index.update(concepts)

        for concept in deprecated_concepts:
            assert concept not in all_concepts_in_index, f"Deprecated concept {concept} should be filtered"

    def test_filters_multi_tag_entries(self, gaap_index):
        """Entries with multiple standard_tags should be excluded."""
        config_dir = Path(__file__).parent.parent / "edgar/xbrl/standardization/config"
        with open(config_dir / "upstream_gaap_mappings.json") as f:
            raw = json.load(f)

        multi_tag = [k for k, v in raw.items() if len(v.get("standard_tags", [])) > 1]
        assert len(multi_tag) > 0, "Test data should have multi-tag entries"

        all_concepts_in_index = set()
        for concepts in gaap_index.values():
            all_concepts_in_index.update(concepts)

        for concept in multi_tag:
            assert concept not in all_concepts_in_index, f"Multi-tag concept {concept} should be filtered"


class TestExpandKnownConcepts:
    """Tests for known_concepts expansion."""

    def test_revenue_expanded(self, config):
        """Revenue should get 70+ known_concepts after expansion."""
        rev = config.get_metric("Revenue")
        assert len(rev.known_concepts) >= 70

    def test_cogs_expanded(self, config):
        """COGS should get many concepts from CostOfGoodsAndServicesSold tag."""
        cogs = config.get_metric("COGS")
        assert len(cogs.known_concepts) >= 60

    def test_originals_first(self, config):
        """Original known_concepts should appear before expanded ones."""
        rev = config.get_metric("Revenue")
        # The first concept should be "Revenues" (original)
        assert rev.known_concepts[0] == "Revenues"
        # The second should be the original ASC 606 concept
        assert rev.known_concepts[1] == "RevenueFromContractWithCustomerExcludingAssessedTax"

    def test_no_duplicates(self, config):
        """No metric should have duplicate known_concepts."""
        for name in config.get_all_metric_names():
            metric = config.get_metric(name)
            concepts = metric.known_concepts
            assert len(concepts) == len(set(concepts)), (
                f"{name} has duplicate concepts: "
                f"{[c for c in concepts if concepts.count(c) > 1]}"
            )

    def test_goodwill_exclude_patterns(self, config):
        """Goodwill should exclude IncludingGoodwill, Impaired, Gross patterns."""
        gw = config.get_metric("Goodwill")
        for concept in gw.known_concepts:
            assert "IncludingGoodwill" not in concept, f"Should exclude {concept}"
            assert "Impaired" not in concept, f"Should exclude {concept}"
            assert "Gross" not in concept, f"Should exclude {concept}"

    def test_stock_based_compensation_unchanged(self, config):
        """StockBasedCompensation has no standard_tag, should stay at 3 concepts."""
        sbc = config.get_metric("StockBasedCompensation")
        assert len(sbc.known_concepts) == 3
        assert sbc.standard_tag == []

    def test_composite_metrics_unaffected(self, config):
        """Composite metrics (IntangibleAssets, ShortTermDebt) should not be expanded."""
        ia = config.get_metric("IntangibleAssets")
        assert ia.composite is True
        assert len(ia.known_concepts) == 5  # Original count

        std = config.get_metric("ShortTermDebt")
        assert std.composite is True
        assert len(std.known_concepts) == 6  # Original count

    def test_capex_exclude_patterns_applied_to_expansion(self, config):
        """Capex exclude_patterns should filter expanded concepts too."""
        capex = config.get_metric("Capex")
        for concept in capex.known_concepts:
            assert "Businesses" not in concept, f"Should exclude {concept}"
            assert "Acquisitions" not in concept, f"Should exclude {concept}"

    def test_accounts_payable_exclude_patterns(self, config):
        """AccountsPayable exclude_patterns should filter 'Liabilities' from expansion."""
        ap = config.get_metric("AccountsPayable")
        for concept in ap.known_concepts:
            # The original 'AccountsPayableAndAccruedLiabilitiesCurrent' is allowed
            # because it was in the original list before expansion
            if concept == "AccountsPayableAndAccruedLiabilitiesCurrent":
                continue
            assert "Liabilities" not in concept, f"Should exclude {concept}"


class TestStandardTagParsing:
    """Tests for standard_tag YAML parsing and normalization."""

    def test_string_tag_normalized_to_list(self, config):
        """A string standard_tag should be normalized to a single-element list."""
        rev = config.get_metric("Revenue")
        assert isinstance(rev.standard_tag, list)
        assert rev.standard_tag == ["Revenue"]

    def test_list_tag_preserved(self, config):
        """A list standard_tag should be preserved as-is."""
        ni = config.get_metric("NetIncome")
        assert isinstance(ni.standard_tag, list)
        assert ni.standard_tag == ["NetIncome", "ProfitLoss"]

    def test_missing_tag_defaults_to_empty(self, config):
        """Metrics without standard_tag should get empty list."""
        oi = config.get_metric("OperatingIncome")
        assert oi.standard_tag == []

    def test_all_15_metrics_have_standard_tag(self, config):
        """Exactly 15 metrics should have a standard_tag set."""
        tagged = [
            name for name in config.get_all_metric_names()
            if config.get_metric(name).standard_tag
        ]
        assert len(tagged) == 15


class TestMissingGaapFile:
    """Test graceful handling when upstream file is missing."""

    def test_missing_file_returns_empty_index(self, tmp_path):
        """If upstream_gaap_mappings.json doesn't exist, return empty dict."""
        loader = ConfigLoader(config_dir=tmp_path)
        index = loader._load_gaap_mappings()
        assert index == {}
