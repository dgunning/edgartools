"""
Regression tests for Issue #649: standard_concept metadata silently dropped during stitching.

The stitching pipeline (XBRLS) was not propagating the standard_concept field
from standardize_statement() through to the stitched output. This broke
downstream filtering and cross-company analysis.

Fix: Propagate standard_concept through concept_metadata, output dicts,
DataFrame columns, and fact extraction.
"""

import pytest

from edgar.xbrl.stitching.core import StatementStitcher


@pytest.mark.fast
class TestIssue649StandardConceptPropagation:
    """Verify standard_concept propagates through the stitching pipeline."""

    def _make_statement(self, data, periods, statement_type="IncomeStatement"):
        """Helper to create a minimal statement dict."""
        return {
            "statement_type": statement_type,
            "data": data,
            "periods": periods,
        }

    def test_standard_concept_in_concept_metadata(self):
        """standard_concept should be stored in concept_metadata during integration."""
        stitcher = StatementStitcher()
        stitcher.periods = ["duration_2024-01-01_2024-12-31"]
        stitcher.period_dates = {"duration_2024-01-01_2024-12-31": "FY 2024"}

        statement_data = [
            {
                "concept": "us-gaap_Revenue",
                "label": "Revenue",
                "standard_concept": "TotalRevenue",
                "level": 0,
                "is_abstract": False,
                "is_total": False,
                "values": {"duration_2024-01-01_2024-12-31": 100000},
                "decimals": {"duration_2024-01-01_2024-12-31": -3},
            }
        ]
        period_map = {"duration_2024-01-01_2024-12-31": {"label": "FY 2024"}}
        relevant_periods = {"duration_2024-01-01_2024-12-31"}

        stitcher._integrate_statement_data(statement_data, period_map, relevant_periods)

        # standard_concept should be in concept_metadata (keyed by concept, not label)
        assert "us-gaap_Revenue" in stitcher.concept_metadata
        assert stitcher.concept_metadata["us-gaap_Revenue"]["standard_concept"] == "TotalRevenue"

    def test_standard_concept_in_output(self):
        """standard_concept should appear in _format_output_with_ordering output."""
        stitcher = StatementStitcher()
        stitcher.periods = ["duration_2024-01-01_2024-12-31"]
        stitcher.period_dates = {"duration_2024-01-01_2024-12-31": "FY 2024"}

        # Manually set up data as if integration already happened (keyed by concept)
        stitcher.concept_metadata["us-gaap_Revenue"] = {
            "level": 0,
            "is_abstract": False,
            "is_total": False,
            "original_concept": "us-gaap_Revenue",
            "latest_label": "Revenue",
            "standard_concept": "TotalRevenue",
        }
        stitcher.data["us-gaap_Revenue"]["duration_2024-01-01_2024-12-31"] = {
            "value": 100000,
            "decimals": -3,
        }
        stitcher.original_statement_order = ["us-gaap_Revenue"]

        result = stitcher._format_output_with_ordering([])
        assert len(result["statement_data"]) == 1
        item = result["statement_data"][0]
        assert item["standard_concept"] == "TotalRevenue"

    def test_standard_concept_none_when_unmapped(self):
        """Items without standard_concept should have None, not KeyError."""
        stitcher = StatementStitcher()
        stitcher.periods = ["duration_2024-01-01_2024-12-31"]
        stitcher.period_dates = {"duration_2024-01-01_2024-12-31": "FY 2024"}

        statement_data = [
            {
                "concept": "custom_MyRevenue",
                "label": "My Revenue",
                "level": 0,
                "is_abstract": False,
                "is_total": False,
                "values": {"duration_2024-01-01_2024-12-31": 50000},
                "decimals": {"duration_2024-01-01_2024-12-31": -3},
            }
        ]
        period_map = {"duration_2024-01-01_2024-12-31": {"label": "FY 2024"}}
        relevant_periods = {"duration_2024-01-01_2024-12-31"}

        stitcher._integrate_statement_data(statement_data, period_map, relevant_periods)
        assert stitcher.concept_metadata["custom_MyRevenue"]["standard_concept"] is None

    def test_standard_concept_in_to_pandas(self):
        """to_pandas() should include a standard_concept column."""
        from edgar.xbrl.stitching.utils import to_pandas

        stitched_data = {
            "periods": [("duration_2024-01-01_2024-12-31", "FY 2024")],
            "statement_data": [
                {
                    "label": "Revenue",
                    "concept": "us-gaap_Revenue",
                    "standard_concept": "TotalRevenue",
                    "level": 0,
                    "is_abstract": False,
                    "is_total": False,
                    "has_values": True,
                    "values": {"duration_2024-01-01_2024-12-31": 100000},
                    "decimals": {"duration_2024-01-01_2024-12-31": -3},
                }
            ],
        }

        df = to_pandas(stitched_data)
        assert "standard_concept" in df.columns
        assert df["standard_concept"].iloc[0] == "TotalRevenue"

    def test_standard_concept_propagated_from_newer_filing(self):
        """When a newer filing provides standard_concept for an existing concept, it should be adopted."""
        stitcher = StatementStitcher()
        stitcher.periods = [
            "duration_2024-01-01_2024-12-31",
            "duration_2023-01-01_2023-12-31",
        ]
        stitcher.period_dates = {
            "duration_2024-01-01_2024-12-31": "FY 2024",
            "duration_2023-01-01_2023-12-31": "FY 2023",
        }

        # First: older filing without standard_concept
        old_data = [
            {
                "concept": "us-gaap_Revenue",
                "label": "Revenue",
                "level": 0,
                "is_abstract": False,
                "is_total": False,
                "values": {"duration_2023-01-01_2023-12-31": 90000},
                "decimals": {"duration_2023-01-01_2023-12-31": -3},
            }
        ]
        stitcher._integrate_statement_data(
            old_data,
            {"duration_2023-01-01_2023-12-31": {"label": "FY 2023"}},
            {"duration_2023-01-01_2023-12-31"},
        )
        assert stitcher.concept_metadata["us-gaap_Revenue"]["standard_concept"] is None

        # Second: newer filing with standard_concept
        new_data = [
            {
                "concept": "us-gaap_Revenue",
                "label": "Revenue",
                "standard_concept": "TotalRevenue",
                "level": 0,
                "is_abstract": False,
                "is_total": False,
                "values": {"duration_2024-01-01_2024-12-31": 100000},
                "decimals": {"duration_2024-01-01_2024-12-31": -3},
            }
        ]
        stitcher._integrate_statement_data(
            new_data,
            {"duration_2024-01-01_2024-12-31": {"label": "FY 2024"}},
            {"duration_2024-01-01_2024-12-31"},
        )
        assert stitcher.concept_metadata["us-gaap_Revenue"]["standard_concept"] == "TotalRevenue"
