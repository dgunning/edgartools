"""
Tests for SectionMembership lookups (edgar.xbrl.standardization.sections).

All pure logic — no network calls needed.
"""

import json
import os
import tempfile

import pytest

from edgar.xbrl.standardization.sections import (
    SectionMembership,
    get_section_membership,
    get_section_for_concept,
    get_statement_for_concept,
    is_current,
    is_asset,
)


@pytest.fixture
def membership():
    """Load the real section membership data."""
    return get_section_membership()


@pytest.fixture
def tiny_membership(tmp_path):
    """Minimal membership for isolated testing."""
    data = {
        "BalanceSheet": {
            "Current Assets": ["Cash", "TradeReceivables"],
            "Non-Current Assets": ["PropertyPlantEquipment", "Goodwill"],
            "Current Liabilities": ["AccountsPayable"],
            "Non-Current Liabilities": ["LongTermDebt"],
            "Equity": ["RetainedEarnings", "CommonStock"],
        },
        "IncomeStatement": {
            "Revenue": ["Revenue", "ContractRevenue"],
            "Operating Expenses": ["SellingGeneralAdmin"],
        },
    }
    path = tmp_path / "test_sections.json"
    path.write_text(json.dumps(data))
    return SectionMembership(str(path))


# ── Real data tests ──────────────────────────────────────────────────────────

class TestSectionMembershipRealData:
    """Tests against the shipped section_membership.json."""

    def test_loads_without_error(self, membership):
        assert len(membership) > 0

    def test_balance_sheet_has_sections(self, membership):
        sections = membership.get_statement_sections("BalanceSheet")
        assert "Current Assets" in sections
        assert "Non-Current Assets" in sections or "Noncurrent Assets" in sections
        assert "Equity" in sections

    def test_income_statement_has_sections(self, membership):
        sections = membership.get_statement_sections("IncomeStatement")
        assert len(sections) > 0

    def test_all_statements_returned(self, membership):
        statements = membership.get_all_statements()
        assert "BalanceSheet" in statements
        assert "IncomeStatement" in statements

    def test_stats_populated(self, membership):
        stats = membership.stats
        assert stats["statement_count"] >= 2
        assert stats["section_count"] >= 4
        assert stats["concept_count"] >= 10


# ── Isolated logic tests ─────────────────────────────────────────────────────

class TestSectionMembershipLogic:
    """Tests against minimal fixture data."""

    def test_get_section_with_statement_type(self, tiny_membership):
        assert tiny_membership.get_section("Cash", "BalanceSheet") == "Current Assets"
        assert tiny_membership.get_section("LongTermDebt", "BalanceSheet") == "Non-Current Liabilities"

    def test_get_section_without_statement_type(self, tiny_membership):
        # Returns first section found
        assert tiny_membership.get_section("Cash") == "Current Assets"

    def test_get_section_unknown_concept(self, tiny_membership):
        assert tiny_membership.get_section("NonExistent") is None

    def test_get_statement_for_concept(self, tiny_membership):
        assert tiny_membership.get_statement_for_concept("Cash") == "BalanceSheet"
        assert tiny_membership.get_statement_for_concept("Revenue") == "IncomeStatement"
        assert tiny_membership.get_statement_for_concept("Unknown") is None

    def test_get_all_sections_for_concept(self, tiny_membership):
        sections = tiny_membership.get_all_sections_for_concept("Cash")
        assert sections == {"BalanceSheet": "Current Assets"}

    def test_get_all_sections_unknown(self, tiny_membership):
        assert tiny_membership.get_all_sections_for_concept("Unknown") == {}

    def test_get_concepts_in_section(self, tiny_membership):
        concepts = tiny_membership.get_concepts_in_section("BalanceSheet", "Current Assets")
        assert "Cash" in concepts
        assert "TradeReceivables" in concepts

    def test_get_concepts_in_missing_section(self, tiny_membership):
        assert tiny_membership.get_concepts_in_section("BalanceSheet", "Nonexistent") == []

    def test_is_current(self, tiny_membership):
        assert tiny_membership.is_current("Cash") is True
        assert tiny_membership.is_current("LongTermDebt") is False
        assert tiny_membership.is_current("Revenue") is None  # Not a BS concept

    def test_is_asset(self, tiny_membership):
        assert tiny_membership.is_asset("Cash") is True
        assert tiny_membership.is_asset("AccountsPayable") is False
        assert tiny_membership.is_asset("RetainedEarnings") is False
        assert tiny_membership.is_asset("Revenue") is None

    def test_is_liability(self, tiny_membership):
        assert tiny_membership.is_liability("AccountsPayable") is True
        assert tiny_membership.is_liability("Cash") is False

    def test_is_equity(self, tiny_membership):
        assert tiny_membership.is_equity("RetainedEarnings") is True
        assert tiny_membership.is_equity("Cash") is False

    def test_contains(self, tiny_membership):
        assert "Cash" in tiny_membership
        assert "Nonexistent" not in tiny_membership

    def test_len(self, tiny_membership):
        # 2+2+1+1+2+2+1 = 11 concepts total
        assert len(tiny_membership) == 11

    def test_missing_file_returns_empty(self, tmp_path):
        m = SectionMembership(str(tmp_path / "does_not_exist.json"))
        assert len(m) == 0
        assert m.get_section("Cash") is None


# ── Convenience function tests ───────────────────────────────────────────────

class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_get_section_for_concept_returns_string_or_none(self):
        result = get_section_for_concept("Cash", "BalanceSheet")
        # Either a valid section name or None depending on shipped data
        assert result is None or isinstance(result, str)

    def test_get_statement_for_concept_returns_string_or_none(self):
        result = get_statement_for_concept("Cash")
        assert result is None or isinstance(result, str)

    def test_is_current_returns_bool_or_none(self):
        result = is_current("Cash")
        assert result is None or isinstance(result, bool)

    def test_is_asset_returns_bool_or_none(self):
        result = is_asset("Cash")
        assert result is None or isinstance(result, bool)
