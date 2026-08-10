"""
Regression test for GitHub Issue #637:
EntityFacts.discover_concept_tags() returns empty for all IFRS filers.

Root cause: discover_concept_tags(), get_concept(), and _get_standardized_concept_value()
only tried us-gaap: prefix, never ifrs-full: prefix. This made all IFRS-reporting
foreign private issuers (20-F filers) invisible to the standardization layer.

Fix: Added ifrs-full: to the variant search loop in all three methods,
added IFRS-specific concept names to synonym groups, and expanded
currency mappings so non-USD monetary values are recognized.

GitHub Issue: https://github.com/dgunning/edgartools/issues/637
"""
import pytest
from edgar import Company


class TestIFRSConceptDiscovery:
    """Verify that IFRS filers can use the standardization layer."""

    @pytest.fixture
    def tsm_facts(self):
        """TSM (Taiwan Semiconductor) - IFRS filer with ifrs-full: prefixed tags."""
        company = Company("TSM")
        facts = company.get_facts()
        assert facts is not None, (
            "TSM company facts should load; None is the IFRS filer path failing, "
            "which is exactly what this class verifies"
        )
        return facts

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

    # `assert x is not None` was the whole of each test below. That is the
    # weakest possible statement about a lookup whose bug was returning None:
    # it cannot tell a correct IFRS lookup from one that stumbled onto a
    # us-gaap tag, got the wrong period, or lost the currency. What is asserted
    # instead is the thing the fix actually changed -- the tag the value came
    # from carries the `ifrs-full:` prefix -- plus the unit, which is the other
    # half of the fix (currency mappings, so a non-USD monetary value is
    # recognised at all).
    #
    # Magnitudes are floors, not equalities. TSM's figures move every time it
    # files a 20-F, and pinning them would make this file fail annually for no
    # defect; the floors are two orders of magnitude below the observed values
    # and exist to catch a scale or unit error, not to restate the accounts.
    #
    # Observed when written (FY2024, period ending 2024-12-31, filed
    # 2025-04-17), all TWD:
    #     revenue              2,894,307,700,000  ifrs-full:Revenue
    #     net_income           1,157,523,900,000  ifrs-full:ProfitLoss
    #     total_assets         6,691,764,700,000  ifrs-full:Assets
    #     stockholders_equity  4,244,266,500,000  ifrs-full:EquityAttributableToOwnersOfParent

    @pytest.mark.parametrize("concept, floor", [
        ('revenue', 1e12),
        ('net_income', 1e11),
        ('total_assets', 1e12),
        ('stockholders_equity', 1e12),
    ])
    def test_get_concept_resolves_via_an_ifrs_tag(self, tsm_facts, concept, floor):
        """The concept resolves, and resolves through the IFRS taxonomy."""
        result = tsm_facts.get_concept(concept, return_metadata=True)
        assert result is not None, (
            f"get_concept({concept!r}) returned None for IFRS filer TSM, "
            "but a manual ifrs-full: lookup works."
        )
        assert result['tag_used'].startswith('ifrs-full:'), (
            f"{concept} resolved via {result['tag_used']!r}. TSM reports under "
            "IFRS; a us-gaap tag here means the value came from somewhere it "
            "should not have."
        )
        assert result['unit'] == 'TWD', (
            f"{concept} came back in {result['unit']!r}. TSM reports in New "
            "Taiwan dollars, and mis-reading the unit is how a non-USD filer's "
            "figures silently become wrong rather than absent."
        )
        assert result['value'] > floor, (
            f"{concept} is {result['value']:,.0f} TWD, below the {floor:,.0f} "
            "floor — suspect a scale or unit error rather than a real figure"
        )

    def test_ifrs_concepts_are_mutually_consistent(self, tsm_facts):
        """Cross-checks no single lookup can make true on its own.

        Four independent lookups that happen to return numbers could each be
        wrong. A balance sheet where equity exceeds assets, or an income
        statement where profit exceeds revenue, cannot be right.
        """
        revenue = tsm_facts.get_concept('revenue')
        net_income = tsm_facts.get_concept('net_income')
        assets = tsm_facts.get_concept('total_assets')
        equity = tsm_facts.get_concept('stockholders_equity')

        assert 0 < net_income < revenue, (
            f"net income {net_income:,.0f} is not a positive figure below "
            f"revenue {revenue:,.0f}"
        )
        assert 0 < equity < assets, (
            f"equity {equity:,.0f} is not a positive figure below total assets "
            f"{assets:,.0f}"
        )

    @pytest.mark.parametrize("method, concept", [
        ('get_revenue', 'revenue'),
        ('get_net_income', 'net_income'),
        ('get_total_assets', 'total_assets'),
    ])
    def test_convenience_method_agrees_with_get_concept(self, tsm_facts, method, concept):
        """The shortcut must return what the long way round returns.

        Previously each of these asserted only that the shortcut was not None,
        so the two APIs could have disagreed — different period, different tag,
        different scale — and all three tests would still have passed.
        """
        via_method = getattr(tsm_facts, method)(annual=True)
        via_concept = tsm_facts.get_concept(concept)
        assert via_method is not None, (
            f"{method}(annual=True) returned None for IFRS filer TSM."
        )
        assert via_method == via_concept, (
            f"{method}() returned {via_method!r} but get_concept({concept!r}) "
            f"returned {via_concept!r}; the two paths disagree"
        )

    def test_get_concept_metadata_shows_ifrs_tag(self, tsm_facts):
        """When return_metadata=True, the tag_used should reflect the ifrs-full prefix."""
        result = tsm_facts.get_concept('revenue', return_metadata=True)
        assert result is not None, "get_concept with metadata returned None for IFRS filer TSM."
        assert 'ifrs-full:' in result['tag_used'], (
            f"Expected ifrs-full: prefix in tag_used, got '{result['tag_used']}'"
        )
