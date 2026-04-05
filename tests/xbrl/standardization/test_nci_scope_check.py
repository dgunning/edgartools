"""Tests for NCI scope-consistency check in _compute_sa_composite."""
import logging
from unittest.mock import MagicMock, patch

import pytest


class TestExtractFormulaConcept:
    """Test that _extract_formula_concept returns (label, value, resolved_concept)."""

    def _make_validator(self):
        """Create a minimal ReferenceValidator with mocked dependencies."""
        from edgar.xbrl.standardization.reference_validator import ReferenceValidator
        v = ReferenceValidator.__new__(ReferenceValidator)
        v.config = None
        return v

    def test_returns_resolved_concept_for_single(self):
        v = self._make_validator()
        v._extract_xbrl_value = MagicMock(return_value=1000.0)
        label, val, resolved = v._extract_formula_concept(None, "Revenue")
        assert label == "Revenue"
        assert val == 1000.0
        assert resolved == "Revenue"

    def test_returns_none_resolved_when_no_value(self):
        v = self._make_validator()
        v._extract_xbrl_value = MagicMock(return_value=None)
        label, val, resolved = v._extract_formula_concept(None, "Revenue")
        assert label == "Revenue"
        assert val is None
        assert resolved is None

    def test_returns_resolved_concept_for_list_first_match(self):
        v = self._make_validator()
        # First candidate matches
        v._extract_xbrl_value = MagicMock(side_effect=[5000.0])
        label, val, resolved = v._extract_formula_concept(
            None,
            ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
             "StockholdersEquity"],
        )
        assert label == "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
        assert val == 5000.0
        assert resolved == "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"

    def test_returns_resolved_concept_for_list_fallback(self):
        v = self._make_validator()
        # First candidate misses, second matches
        v._extract_xbrl_value = MagicMock(side_effect=[None, 3000.0])
        label, val, resolved = v._extract_formula_concept(
            None,
            ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
             "StockholdersEquity"],
        )
        # Label is always first in list
        assert label == "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
        assert val == 3000.0
        assert resolved == "StockholdersEquity"

    def test_returns_none_for_list_all_miss(self):
        v = self._make_validator()
        v._extract_xbrl_value = MagicMock(return_value=None)
        label, val, resolved = v._extract_formula_concept(
            None, ["ConceptA", "ConceptB"],
        )
        assert label == "ConceptA"
        assert val is None
        assert resolved is None


class TestNCIScopeCheck:
    """Test NCI scope-consistency warning in _compute_sa_composite."""

    def _make_validator_with_formula(self, formula_components, extract_results):
        """Create a validator with mocked formula resolution and extraction."""
        from edgar.xbrl.standardization.reference_validator import ReferenceValidator
        v = ReferenceValidator.__new__(ReferenceValidator)
        v.config = None
        v._resolve_formula_components = MagicMock(return_value=formula_components)

        # Mock _extract_formula_concept to return specified results
        v._extract_formula_concept = MagicMock(side_effect=extract_results)
        return v

    def test_nci_mismatch_logs_warning(self, caplog):
        """Mixed NCI scope (L&SE inclusive + SE exclusive) should log warning."""
        from edgar.xbrl.standardization.reference_validator import ReferenceValidator
        v = ReferenceValidator.__new__(ReferenceValidator)
        v.config = None

        # Simulate TotalLiabilities = L&SE - SE formula
        formula = [
            ("LiabilitiesAndStockholdersEquity", 1.0),
            (["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
              "StockholdersEquity"], -1.0),
        ]
        v._resolve_formula_components = MagicMock(return_value=formula)

        # L&SE found (NCI-inclusive), SE falls back to StockholdersEquity (NCI-exclusive)
        v._extract_xbrl_value = MagicMock(side_effect=[
            100000.0,  # L&SE
            None,       # SE-NCI-inclusive misses
            40000.0,    # SE-NCI-exclusive matches
        ])

        with caplog.at_level(logging.WARNING):
            result = v._compute_sa_composite("TotalLiabilities", "TEST", None, 60000.0)

        assert result is not None
        assert any("NCI SCOPE MISMATCH" in msg for msg in caplog.messages)

    def test_nci_consistent_no_warning(self, caplog):
        """Both NCI-inclusive concepts should NOT log warning."""
        from edgar.xbrl.standardization.reference_validator import ReferenceValidator
        v = ReferenceValidator.__new__(ReferenceValidator)
        v.config = None

        formula = [
            ("LiabilitiesAndStockholdersEquity", 1.0),
            (["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
              "StockholdersEquity"], -1.0),
        ]
        v._resolve_formula_components = MagicMock(return_value=formula)

        # Both resolve to NCI-inclusive concepts
        v._extract_xbrl_value = MagicMock(side_effect=[
            100000.0,  # L&SE (inclusive)
            40000.0,   # SE-NCI-inclusive matches on first try
        ])

        with caplog.at_level(logging.WARNING):
            result = v._compute_sa_composite("TotalLiabilities", "TEST", None, 60000.0)

        assert result is not None
        assert not any("NCI SCOPE MISMATCH" in msg for msg in caplog.messages)

    def test_nci_check_only_for_total_liabilities(self, caplog):
        """NCI check should NOT fire for non-TotalLiabilities metrics."""
        from edgar.xbrl.standardization.reference_validator import ReferenceValidator
        v = ReferenceValidator.__new__(ReferenceValidator)
        v.config = None

        formula = [
            (["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
              "StockholdersEquity"], 1.0),
        ]
        v._resolve_formula_components = MagicMock(return_value=formula)

        # Falls back to NCI-exclusive — but metric is not TotalLiabilities
        v._extract_xbrl_value = MagicMock(side_effect=[
            None,       # NCI-inclusive misses
            3000.0,     # NCI-exclusive matches
        ])

        with caplog.at_level(logging.WARNING):
            v._compute_sa_composite("StockholdersEquity", "TEST", None, 3000.0)

        assert not any("NCI SCOPE MISMATCH" in msg for msg in caplog.messages)
