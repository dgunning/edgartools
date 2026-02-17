"""
Regression tests for Issue #643: Duplicate rows in stitched statements.

When the same financial concept appears under different XBRL tags across
filings (e.g., label changed between years), stitching could produce
duplicate rows for the same standard_concept. The merge logic consolidates
these rows when they map to the same standard_concept and have no
overlapping periods.
"""

import pytest

from edgar.xbrl.stitching.core import StatementStitcher


@pytest.mark.fast
class TestIssue643DuplicateRowMerging:
    """Verify duplicate standard_concept rows are merged during stitching."""

    def test_merge_same_standard_concept_no_overlap(self):
        """Two concept keys mapping to the same standard_concept with non-overlapping periods should merge."""
        stitcher = StatementStitcher()
        stitcher.periods = [
            "duration_2024-01-01_2024-12-31",
            "duration_2023-01-01_2023-12-31",
        ]
        stitcher.period_dates = {
            "duration_2024-01-01_2024-12-31": "FY 2024",
            "duration_2023-01-01_2023-12-31": "FY 2023",
        }

        # Two different label keys both mapping to the same standard_concept
        stitcher.concept_metadata["Total Revenue"] = {
            "level": 0,
            "is_abstract": False,
            "is_total": True,
            "original_concept": "us-gaap_Revenues",
            "latest_label": "Total Revenue",
            "standard_concept": "TotalRevenue",
        }
        stitcher.data["Total Revenue"]["duration_2024-01-01_2024-12-31"] = {
            "value": 100000,
            "decimals": -3,
        }

        stitcher.concept_metadata["Revenue"] = {
            "level": 0,
            "is_abstract": False,
            "is_total": False,
            "original_concept": "us-gaap_Revenue",
            "latest_label": "Revenue",
            "standard_concept": "TotalRevenue",
        }
        stitcher.data["Revenue"]["duration_2023-01-01_2023-12-31"] = {
            "value": 90000,
            "decimals": -3,
        }

        stitcher._merge_duplicate_standard_concepts()

        # Only one concept key should remain
        remaining_keys = [k for k in stitcher.concept_metadata if stitcher.concept_metadata[k].get("standard_concept") == "TotalRevenue"]
        assert len(remaining_keys) == 1

        # The remaining key should have data from both periods
        primary_key = remaining_keys[0]
        assert "duration_2024-01-01_2024-12-31" in stitcher.data[primary_key]
        assert "duration_2023-01-01_2023-12-31" in stitcher.data[primary_key]

    def test_no_merge_when_periods_overlap(self):
        """Two concept keys with overlapping periods should NOT merge (genuinely different items)."""
        stitcher = StatementStitcher()
        stitcher.periods = ["duration_2024-01-01_2024-12-31"]
        stitcher.period_dates = {"duration_2024-01-01_2024-12-31": "FY 2024"}

        stitcher.concept_metadata["Product Revenue"] = {
            "level": 1,
            "is_abstract": False,
            "is_total": False,
            "original_concept": "us-gaap_ProductRevenue",
            "latest_label": "Product Revenue",
            "standard_concept": "ProductRevenue",
        }
        stitcher.data["Product Revenue"]["duration_2024-01-01_2024-12-31"] = {
            "value": 60000,
            "decimals": -3,
        }

        stitcher.concept_metadata["Service Revenue"] = {
            "level": 1,
            "is_abstract": False,
            "is_total": False,
            "original_concept": "us-gaap_ServiceRevenue",
            "latest_label": "Service Revenue",
            "standard_concept": "ProductRevenue",  # Same standard_concept (hypothetical)
        }
        stitcher.data["Service Revenue"]["duration_2024-01-01_2024-12-31"] = {
            "value": 40000,
            "decimals": -3,
        }

        stitcher._merge_duplicate_standard_concepts()

        # Both should still exist because they have overlapping period data
        assert "Product Revenue" in stitcher.concept_metadata
        assert "Service Revenue" in stitcher.concept_metadata

    def test_no_merge_without_standard_concept(self):
        """Items without standard_concept should never be merged."""
        stitcher = StatementStitcher()
        stitcher.periods = ["duration_2024-01-01_2024-12-31"]
        stitcher.period_dates = {"duration_2024-01-01_2024-12-31": "FY 2024"}

        stitcher.concept_metadata["Item A"] = {
            "level": 0,
            "is_abstract": False,
            "is_total": False,
            "original_concept": "custom_A",
            "latest_label": "Item A",
            "standard_concept": None,
        }
        stitcher.data["Item A"]["duration_2024-01-01_2024-12-31"] = {
            "value": 1000,
            "decimals": 0,
        }

        stitcher.concept_metadata["Item B"] = {
            "level": 0,
            "is_abstract": False,
            "is_total": False,
            "original_concept": "custom_B",
            "latest_label": "Item B",
            "standard_concept": None,
        }
        stitcher.data["Item B"]["duration_2024-01-01_2024-12-31"] = {
            "value": 2000,
            "decimals": 0,
        }

        stitcher._merge_duplicate_standard_concepts()

        # Both should still exist
        assert "Item A" in stitcher.concept_metadata
        assert "Item B" in stitcher.concept_metadata
