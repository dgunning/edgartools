"""
Tests for XBRL abstract concept detection (edgar.xbrl.abstract_detection).

Pure logic — pattern matching and heuristics, no network calls.
"""

import pytest

from edgar.xbrl.abstract_detection import (
    is_abstract_concept,
    is_textblock_concept,
    add_known_abstract_concept,
    get_known_abstract_concepts,
    get_abstract_patterns,
    KNOWN_ABSTRACT_CONCEPTS,
)


class TestIsAbstractConcept:

    def test_known_abstract_concepts(self):
        assert is_abstract_concept("us-gaap_StatementOfFinancialPositionAbstract") is True
        assert is_abstract_concept("us-gaap_IncomeStatementAbstract") is True
        assert is_abstract_concept("dei_CoverAbstract") is True

    def test_schema_abstract_true(self):
        assert is_abstract_concept("anything", schema_abstract=True) is True

    def test_pattern_abstract_suffix(self):
        assert is_abstract_concept("us-gaap_SomeNewAbstract") is True

    def test_pattern_rollforward_suffix(self):
        assert is_abstract_concept("us-gaap_SomethingRollForward") is True

    def test_pattern_table_suffix(self):
        assert is_abstract_concept("us-gaap_SomeTable") is True

    def test_pattern_axis_suffix(self):
        assert is_abstract_concept("us-gaap_SomeAxis") is True

    def test_pattern_domain_suffix(self):
        assert is_abstract_concept("us-gaap_SomeDomain") is True

    def test_pattern_lineitems_suffix(self):
        assert is_abstract_concept("us-gaap_SomeLineItems") is True

    def test_structural_heuristic(self):
        # Has children but no values → abstract
        assert is_abstract_concept("us-gaap_Unknown", has_children=True, has_values=False) is True

    def test_structural_with_values_not_abstract(self):
        # Has children AND values → not abstract (it's a rollup)
        assert is_abstract_concept("us-gaap_Unknown", has_children=True, has_values=True) is False

    def test_regular_concept_not_abstract(self):
        assert is_abstract_concept("us-gaap_Revenue") is False
        assert is_abstract_concept("us-gaap_NetIncomeLoss") is False
        assert is_abstract_concept("us-gaap_Assets") is False

    def test_default_is_false(self):
        assert is_abstract_concept("us-gaap_Unknown") is False


class TestIsTextblockConcept:

    def test_textblock(self):
        assert is_textblock_concept("us-gaap:AccountingPoliciesTextBlock") is True
        assert is_textblock_concept("us-gaap_AccountingPoliciesTextBlock") is True

    def test_textblock_abstract_excluded(self):
        assert is_textblock_concept("us-gaap:DisclosureTextBlockAbstract") is False

    def test_non_textblock(self):
        assert is_textblock_concept("us-gaap:Revenue") is False


class TestAccessors:

    def test_get_known_returns_copy(self):
        known = get_known_abstract_concepts()
        assert isinstance(known, set)
        assert len(known) > 10
        # Modifying copy doesn't affect original
        known.add("test")
        assert "test" not in KNOWN_ABSTRACT_CONCEPTS

    def test_get_patterns_returns_copy(self):
        patterns = get_abstract_patterns()
        assert isinstance(patterns, list)
        assert any("Abstract" in p for p in patterns)
