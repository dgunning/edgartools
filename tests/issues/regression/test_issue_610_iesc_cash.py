"""
Regression test for Issue #610: Multi-year stitching splits cash across rows

GitHub Issue: https://github.com/dgunning/edgartools/issues/610

Bug (FIXED): IESC changed XBRL concepts for "cash" across 10-K filings.
The stitched 5-year balance sheet showed 3 separate cash rows instead of 1
because:
  1. The concepts mapped to different standard concepts
     (CashAndCashEquivalents vs CashAndMarketableSecurities)
  2. The variant-name check blocked merging since the concept names
     don't contain each other

Fix: Added _EQUIVALENT_STANDARD_CONCEPTS to declare that these standard
concepts represent the same economic item, and skip the variant-name check
for equivalent-merged groups while keeping value agreement as the guard.
"""

from collections import defaultdict

import pytest

from edgar.xbrl.stitching.core import StatementStitcher


class TestEquivalentStandardConceptMerge:
    """Unit tests for _merge_duplicate_standard_concepts with equivalent groups."""

    def _make_stitcher_with_data(self, concepts):
        """Build a StatementStitcher pre-loaded with synthetic concept data.

        Args:
            concepts: list of dicts with keys:
                key, standard_concept, periods (dict of period->value)
        """
        stitcher = StatementStitcher()
        for c in concepts:
            key = c['key']
            stitcher.data[key] = {
                p: {'value': v, 'decimals': -3}
                for p, v in c['periods'].items()
            }
            stitcher.concept_metadata[key] = {
                'standard_concept': c['standard_concept'],
                'level': 0,
                'is_abstract': False,
                'is_total': False,
                'original_concept': key,
                'latest_label': c.get('label', 'Cash'),
            }
        return stitcher

    def test_three_cash_concepts_merge_to_one(self):
        """Three concepts with two different-but-equivalent standard concepts
        should merge into a single row when overlapping values agree."""
        stitcher = self._make_stitcher_with_data([
            {
                'key': 'us-gaap:CashAndCashEquivalentsAtCarryingValue',
                'standard_concept': 'CashAndMarketableSecurities',
                'periods': {'2025': 100, '2024': 90},
            },
            {
                'key': 'us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
                'standard_concept': 'CashAndCashEquivalents',
                'periods': {'2022': 50, '2021': 40},
            },
            {
                'key': 'us-gaap:CashCashEquivalentsAndShortTermInvestments',
                'standard_concept': 'CashAndMarketableSecurities',
                'periods': {'2023': 70},
            },
        ])

        stitcher._merge_duplicate_standard_concepts()

        # All three should merge into one surviving key
        surviving_keys = [k for k in stitcher.data if len(stitcher.data[k]) > 0]
        assert len(surviving_keys) == 1, (
            f"Expected 1 merged concept, got {len(surviving_keys)}: {surviving_keys}"
        )

        merged_data = stitcher.data[surviving_keys[0]]
        assert set(merged_data.keys()) == {'2025', '2024', '2023', '2022', '2021'}
        assert merged_data['2025']['value'] == 100
        assert merged_data['2023']['value'] == 70
        assert merged_data['2021']['value'] == 40

    def test_equivalent_merge_blocked_by_value_disagreement(self):
        """Even with equivalent standard concepts, overlapping values that
        disagree should prevent merging."""
        stitcher = self._make_stitcher_with_data([
            {
                'key': 'us-gaap:CashAndCashEquivalentsAtCarryingValue',
                'standard_concept': 'CashAndMarketableSecurities',
                'periods': {'2024': 100, '2023': 70},
            },
            {
                'key': 'us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
                'standard_concept': 'CashAndCashEquivalents',
                # 2023 value disagrees (999 vs 70)
                'periods': {'2023': 999, '2022': 50},
            },
        ])

        stitcher._merge_duplicate_standard_concepts()

        # Should NOT merge because 2023 values disagree
        surviving_keys = [k for k in stitcher.data if len(stitcher.data[k]) > 0]
        assert len(surviving_keys) == 2

    def test_equivalent_merge_when_only_non_canonical_present(self):
        """When concepts only map to the non-canonical equivalent standard concept,
        they should still merge with concepts from the canonical side."""
        stitcher = self._make_stitcher_with_data([
            {
                'key': 'us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
                'standard_concept': 'CashAndCashEquivalents',
                'periods': {'2022': 50, '2021': 40},
            },
            {
                'key': 'us-gaap:CashAndCashEquivalentsAtCarryingValue',
                'standard_concept': 'CashAndMarketableSecurities',
                'periods': {'2024': 100, '2023': 70},
            },
        ])

        stitcher._merge_duplicate_standard_concepts()

        surviving_keys = [k for k in stitcher.data if len(stitcher.data[k]) > 0]
        assert len(surviving_keys) == 1
        merged_data = stitcher.data[surviving_keys[0]]
        assert set(merged_data.keys()) == {'2024', '2023', '2022', '2021'}

    def test_regular_same_standard_still_requires_variant_check(self):
        """Concepts with the same (non-equivalent) standard concept must still
        pass the variant-name check — Issue #642 protection stays intact."""
        stitcher = self._make_stitcher_with_data([
            {
                'key': 'us-gaap:NetCashProvidedByUsedInOperatingActivities',
                'standard_concept': 'OperatingCashFlow',
                'periods': {'2024': 500},
            },
            {
                'key': 'us-gaap:CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations',
                'standard_concept': 'OperatingCashFlow',
                'periods': {'2023': 30},
            },
        ])

        stitcher._merge_duplicate_standard_concepts()

        # Should NOT merge — different sub-items, variant check blocks it
        surviving_keys = [k for k in stitcher.data if len(stitcher.data[k]) > 0]
        assert len(surviving_keys) == 2


@pytest.mark.network
def test_iesc_balance_sheet_single_cash_row():
    """IESC 5-year balance sheet should show exactly 1 cash row with all years."""
    from edgar import Company
    from edgar.xbrl.stitching import XBRLS

    company = Company('IESC')
    filings = company.get_filings(form='10-K').head(5)
    xbrls = XBRLS.from_filings(filings)
    bs = xbrls.statements.balance_sheet()
    df = bs.to_dataframe()

    cash_rows = df[df['label'].str.contains('cash|Cash', case=False, na=False)]
    # There should be exactly 1 row for cash (not 3 split rows)
    assert len(cash_rows) == 1, (
        f"Expected 1 cash row, got {len(cash_rows)}:\n{cash_rows[['label']].to_string()}"
    )

    # The single cash row should have data for all 5 years (no NaN gaps)
    value_cols = [c for c in cash_rows.columns if c not in ('label', 'concept', 'level', 'is_abstract', 'is_total')]
    non_null = cash_rows.iloc[0][value_cols].notna().sum()
    assert non_null >= 5, (
        f"Expected data for at least 5 years, got {non_null} non-null values"
    )
