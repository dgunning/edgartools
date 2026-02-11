"""
Regression test for GitHub Issue #637:
EntityFacts.discover_concept_tags() returns empty for all IFRS filers.

Root cause: discover_concept_tags(), get_concept(), and _get_standardized_concept_value()
only tried us-gaap: prefix, never ifrs-full: prefix. This made all IFRS-reporting
foreign private issuers (20-F filers) invisible to the standardization layer.

Fix: Added ifrs-full: to the variant search loop in all three methods,
added IFRS-specific concept names to synonym groups, and expanded
currency mappings so non-USD monetary values are recognized.
"""
import pytest
from edgar import Company


@pytest.mark.vcr
class TestIFRSConceptDiscovery:
    """Verify that IFRS filers can use the standardization layer."""

    @pytest.fixture
    def tsm_facts(self):
        """TSM (Taiwan Semiconductor) - IFRS filer with ifrs-full: prefixed tags."""
        company = Company("TSM")
        return company.get_facts()

    def test_discover_concept_tags_finds_ifrs_revenue(self, tsm_facts):
        """discover_concept_tags('revenue') should find tags for IFRS filers."""
        tags = tsm_facts.discover_concept_tags('revenue')
        assert len(tags) > 0, (
            "discover_concept_tags('revenue') returned empty for IFRS filer TSM. "
            "The ifrs-full: prefix is likely not being searched."
        )

    def test_discover_concept_tags_finds_ifrs_net_income(self, tsm_facts):
        """discover_concept_tags('net_income') should find tags for IFRS filers."""
        tags = tsm_facts.discover_concept_tags('net_income')
        assert len(tags) > 0, (
            "discover_concept_tags('net_income') returned empty for IFRS filer TSM."
        )

    def test_discover_concept_tags_finds_ifrs_eps(self, tsm_facts):
        """discover_concept_tags('earnings_per_share_basic') should find IFRS EPS tags."""
        tags = tsm_facts.discover_concept_tags('earnings_per_share_basic')
        assert len(tags) > 0, (
            "discover_concept_tags('earnings_per_share_basic') returned empty for IFRS filer TSM."
        )

    def test_discover_concept_tags_finds_ifrs_total_assets(self, tsm_facts):
        """discover_concept_tags('total_assets') should find tags for IFRS filers."""
        tags = tsm_facts.discover_concept_tags('total_assets')
        assert len(tags) > 0, (
            "discover_concept_tags('total_assets') returned empty for IFRS filer TSM."
        )

    def test_get_concept_returns_value_for_ifrs_revenue(self, tsm_facts):
        """get_concept('revenue') should return a non-None value for IFRS filers."""
        revenue = tsm_facts.get_concept('revenue')
        assert revenue is not None, (
            "get_concept('revenue') returned None for IFRS filer TSM, "
            "but manual ifrs-full:Revenue lookup works."
        )

    def test_get_concept_returns_value_for_ifrs_net_income(self, tsm_facts):
        """get_concept('net_income') should return a non-None value for IFRS filers."""
        net_income = tsm_facts.get_concept('net_income')
        assert net_income is not None, (
            "get_concept('net_income') returned None for IFRS filer TSM."
        )

    def test_get_concept_returns_value_for_ifrs_total_assets(self, tsm_facts):
        """get_concept('total_assets') should return a non-None value for IFRS filers."""
        total_assets = tsm_facts.get_concept('total_assets')
        assert total_assets is not None, (
            "get_concept('total_assets') returned None for IFRS filer TSM."
        )

    def test_get_concept_returns_value_for_ifrs_equity(self, tsm_facts):
        """get_concept('stockholders_equity') should return a non-None value for IFRS filers."""
        equity = tsm_facts.get_concept('stockholders_equity')
        assert equity is not None, (
            "get_concept('stockholders_equity') returned None for IFRS filer TSM."
        )

    def test_get_revenue_works_for_ifrs_filer(self, tsm_facts):
        """The get_revenue() convenience method should work for IFRS filers."""
        revenue = tsm_facts.get_revenue(annual=True)
        assert revenue is not None, (
            "get_revenue(annual=True) returned None for IFRS filer TSM."
        )

    def test_get_net_income_works_for_ifrs_filer(self, tsm_facts):
        """The get_net_income() convenience method should work for IFRS filers."""
        net_income = tsm_facts.get_net_income(annual=True)
        assert net_income is not None, (
            "get_net_income(annual=True) returned None for IFRS filer TSM."
        )

    def test_get_total_assets_works_for_ifrs_filer(self, tsm_facts):
        """The get_total_assets() convenience method should work for IFRS filers."""
        assets = tsm_facts.get_total_assets(annual=True)
        assert assets is not None, (
            "get_total_assets(annual=True) returned None for IFRS filer TSM."
        )

    def test_get_concept_metadata_shows_ifrs_tag(self, tsm_facts):
        """When return_metadata=True, the tag_used should reflect the ifrs-full prefix."""
        result = tsm_facts.get_concept('revenue', return_metadata=True)
        assert result is not None, "get_concept with metadata returned None for IFRS filer TSM."
        assert 'ifrs-full:' in result['tag_used'], (
            f"Expected ifrs-full: prefix in tag_used, got '{result['tag_used']}'"
        )
