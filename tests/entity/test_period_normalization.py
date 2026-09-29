"""Tests for period format normalization between EntityFacts and MultiPeriodStatement."""
import pytest
from unittest.mock import MagicMock

from edgar.entity.utils import normalize_period_to_entity_facts, normalize_period_to_statement


class TestNormalizePeriodToEntityFacts:
    """Normalize to '2023-FY' format."""

    def test_passthrough_entity_facts_format(self):
        assert normalize_period_to_entity_facts("2023-FY") == "2023-FY"
        assert normalize_period_to_entity_facts("2024-Q1") == "2024-Q1"
        assert normalize_period_to_entity_facts("2022-Q4") == "2022-Q4"

    def test_converts_statement_format(self):
        assert normalize_period_to_entity_facts("FY 2023") == "2023-FY"
        assert normalize_period_to_entity_facts("Q1 2024") == "2024-Q1"
        assert normalize_period_to_entity_facts("Q4 2022") == "2022-Q4"

    def test_unknown_format_passthrough(self):
        assert normalize_period_to_entity_facts("2023") == "2023"
        assert normalize_period_to_entity_facts("annual") == "annual"
        assert normalize_period_to_entity_facts("2023-01-01") == "2023-01-01"

    def test_edge_cases(self):
        assert normalize_period_to_entity_facts("") == ""
        assert normalize_period_to_entity_facts("FY2023") == "FY2023"  # no space — passthrough
        assert normalize_period_to_entity_facts("Q5 2023") == "Q5 2023"  # invalid quarter


class TestNormalizePeriodToStatement:
    """Normalize to 'FY 2023' format."""

    def test_passthrough_statement_format(self):
        assert normalize_period_to_statement("FY 2023") == "FY 2023"
        assert normalize_period_to_statement("Q1 2024") == "Q1 2024"
        assert normalize_period_to_statement("Q4 2022") == "Q4 2022"

    def test_converts_entity_facts_format(self):
        assert normalize_period_to_statement("2023-FY") == "FY 2023"
        assert normalize_period_to_statement("2024-Q1") == "Q1 2024"
        assert normalize_period_to_statement("2022-Q4") == "Q4 2022"

    def test_unknown_format_passthrough(self):
        assert normalize_period_to_statement("2023") == "2023"
        assert normalize_period_to_statement("annual") == "annual"
        assert normalize_period_to_statement("2023-01-01") == "2023-01-01"

    def test_edge_cases(self):
        assert normalize_period_to_statement("") == ""
        assert normalize_period_to_statement("2023FY") == "2023FY"  # no dash — passthrough
        assert normalize_period_to_statement("2023-Q5") == "2023-Q5"  # invalid quarter


class TestRoundTrip:
    """Converting in both directions should be lossless."""

    @pytest.mark.parametrize("entity_fmt,stmt_fmt", [
        ("2023-FY", "FY 2023"),
        ("2024-Q1", "Q1 2024"),
        ("2020-Q4", "Q4 2020"),
    ])
    def test_roundtrip(self, entity_fmt, stmt_fmt):
        assert normalize_period_to_statement(entity_fmt) == stmt_fmt
        assert normalize_period_to_entity_facts(stmt_fmt) == entity_fmt
        # Double-convert should be idempotent
        assert normalize_period_to_statement(normalize_period_to_statement(entity_fmt)) == stmt_fmt
        assert normalize_period_to_entity_facts(normalize_period_to_entity_facts(stmt_fmt)) == entity_fmt


class TestGetFactAcceptsStatementFormat:
    """EntityFacts.get_fact() should accept 'FY 2023' format."""

    def test_get_fact_normalizes_period(self):
        from edgar.entity.entity_facts import EntityFacts

        # Build a minimal EntityFacts with a mock fact
        mock_fact = MagicMock()
        mock_fact.fiscal_year = 2023
        mock_fact.fiscal_period = "FY"
        mock_fact.filing_date = "2024-02-01"
        mock_fact.period_end = "2023-12-31"

        ef = EntityFacts.__new__(EntityFacts)
        ef._suppress_warnings = True
        ef._fact_index = {"by_concept": {"Revenue": [mock_fact]}}
        ef._concept_aliases = {}
        ef._filing_metadata = {}
        ef.cik = 12345
        ef.name = "Test Corp"
        ef.taxonomy = "us-gaap"

        # "FY 2023" should be normalized to "2023-FY" internally
        result = ef.get_fact("Revenue", period="FY 2023")
        assert result is mock_fact

        # "2023-FY" should still work (passthrough)
        result2 = ef.get_fact("Revenue", period="2023-FY")
        assert result2 is mock_fact


class TestGetPeriodComparisonAcceptsEntityFactsFormat:
    """MultiPeriodStatement.get_period_comparison() should accept '2023-FY' format."""

    def test_get_period_comparison_normalizes(self):
        from edgar.entity.enhanced_statement import MultiPeriodStatement, MultiPeriodItem

        item = MultiPeriodItem(
            concept="Revenue",
            label="Revenue",
            depth=0,
            parent_concept=None,
            is_total=False,
            is_abstract=False,
            values={"FY 2024": 100_000, "FY 2023": 90_000},
        )
        stmt = MultiPeriodStatement(
            statement_type="income",
            periods=["FY 2024", "FY 2023"],
            items=[item],
        )

        # Should work with entity-facts format "2024-FY"
        comparison = stmt.get_period_comparison("2024-FY", "2023-FY")
        assert len(comparison) == 1
        assert comparison[0]["FY 2024"] == 100_000
        assert comparison[0]["FY 2023"] == 90_000


class TestGetDisplayValueAcceptsEntityFactsFormat:
    """MultiPeriodItem.get_display_value() should accept '2023-FY' format."""

    def test_get_display_value_normalizes(self):
        from edgar.entity.enhanced_statement import MultiPeriodItem

        item = MultiPeriodItem(
            concept="Revenue",
            label="Revenue",
            depth=0,
            parent_concept=None,
            is_total=False,
            is_abstract=False,
            values={"FY 2024": 100_000_000},
        )

        # Should work with entity-facts format
        val = item.get_display_value("2024-FY")
        assert val is not None
        assert val != ""

        # Should also work with native format
        val2 = item.get_display_value("FY 2024")
        assert val2 == val
