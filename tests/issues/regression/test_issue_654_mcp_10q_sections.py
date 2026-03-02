"""
Regression test for GitHub Issue #654:
edgar_filing MCP tool returns null for 10-Q narrative sections (MD&A, risk factors, etc.)

Root cause: _extract_section() used attribute access (obj.mda, obj.risk_factors) on TenQ
objects that only expose content via __getitem__ with Part/Item keys such as
'Part I, Item 2' (MD&A) or 'Part II, Item 1A' (Risk Factors).

Fix: _extract_section() now uses obj[key] via the SECTION_MAP_10K / SECTION_MAP_10Q
lookup tables which contain the canonical key formats accepted by TenK/TenQ.__getitem__.
"""

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Unit tests for _extract_section (no network required)
# ---------------------------------------------------------------------------


class TestExtractSectionMapping:
    """_extract_section uses __getitem__ not attribute access."""

    def _make_10q_obj(self, items_data: dict):
        """Build a mock TenQ-like object that responds to __getitem__."""
        obj = MagicMock()
        obj.__getitem__ = MagicMock(side_effect=lambda key: items_data.get(key))
        obj.financials = None
        return obj

    def _make_10k_obj(self, items_data: dict):
        """Build a mock TenK-like object that responds to __getitem__."""
        obj = MagicMock()
        obj.__getitem__ = MagicMock(side_effect=lambda key: items_data.get(key))
        obj.financials = None
        return obj

    def test_10q_mda_uses_part_i_item_2(self):
        """MDA section on 10-Q should use 'Part I, Item 2' key, not obj.mda attribute."""
        from edgar.ai.mcp.tools.filing import _extract_section

        mda_text = "Management's Discussion and Analysis content here."
        obj = self._make_10q_obj({"Part I, Item 2": mda_text})

        # Simulate attribute access failing (pre-fix behaviour would silently return None)
        del obj.mda  # ensure attribute does not exist

        result = _extract_section(obj, "10-Q", "mda")
        assert result is not None, "MD&A section must not be null for 10-Q"
        assert "Management's Discussion" in result

    def test_10q_risk_factors_uses_part_ii_item_1a(self):
        """Risk Factors on 10-Q should use 'Part II, Item 1A' key."""
        from edgar.ai.mcp.tools.filing import _extract_section

        rf_text = "Risk Factors: economic conditions, competition..."
        obj = self._make_10q_obj({"Part II, Item 1A": rf_text})
        del obj.risk_factors

        result = _extract_section(obj, "10-Q", "risk_factors")
        assert result is not None, "risk_factors section must not be null for 10-Q"
        assert "Risk Factors" in result

    def test_10q_legal_uses_part_ii_item_1(self):
        """Legal Proceedings on 10-Q should use 'Part II, Item 1' key."""
        from edgar.ai.mcp.tools.filing import _extract_section

        legal_text = "Legal Proceedings: pending litigation..."
        obj = self._make_10q_obj({"Part II, Item 1": legal_text})

        result = _extract_section(obj, "10-Q", "legal")
        assert result is not None, "legal section must not be null for 10-Q"
        assert "Legal Proceedings" in result

    def test_10q_controls_uses_part_i_item_4(self):
        """Controls & Procedures on 10-Q should use 'Part I, Item 4' key."""
        from edgar.ai.mcp.tools.filing import _extract_section

        controls_text = "Controls and Procedures: disclosure controls evaluated..."
        obj = self._make_10q_obj({"Part I, Item 4": controls_text})

        result = _extract_section(obj, "10-Q", "controls")
        assert result is not None
        assert "Controls" in result

    def test_10q_financials_uses_financials_cached_property(self):
        """Financials section uses obj.financials cached property, not __getitem__."""
        from edgar.ai.mcp.tools.filing import _extract_section

        fin = MagicMock()
        fin.income_statement.return_value = "Net income: $1B"
        fin.balance_sheet.return_value = None
        fin.cashflow_statement.return_value = None

        obj = MagicMock()
        obj.financials = fin

        result = _extract_section(obj, "10-Q", "financials")
        assert result is not None
        assert "Income Statement" in result
        assert "Net income: $1B" in result

    def test_10q_section_missing_returns_none_not_raises(self):
        """If a section is absent from the filing, return None gracefully."""
        from edgar.ai.mcp.tools.filing import _extract_section

        # 10-Q with no risk factors section
        obj = self._make_10q_obj({})
        result = _extract_section(obj, "10-Q", "risk_factors")
        assert result is None

    def test_10k_mda_uses_friendly_name_key(self):
        """MDA section on 10-K uses 'mda' friendly key via TenK.__getitem__."""
        from edgar.ai.mcp.tools.filing import _extract_section

        mda_text = "MD&A: our revenues increased by 15% year-over-year."
        obj = self._make_10k_obj({"mda": mda_text})

        result = _extract_section(obj, "10-K", "mda")
        assert result is not None, "MD&A section must not be null for 10-K"
        assert "revenues increased" in result

    def test_10k_business_uses_business_key(self):
        """Business section on 10-K uses 'business' friendly key."""
        from edgar.ai.mcp.tools.filing import _extract_section

        business_text = "Business: we develop and sell software products..."
        obj = self._make_10k_obj({"business": business_text})

        result = _extract_section(obj, "10-K", "business")
        assert result is not None
        assert "software products" in result

    def test_10k_risk_factors_uses_risk_factors_key(self):
        """Risk Factors on 10-K uses 'risk_factors' friendly key."""
        from edgar.ai.mcp.tools.filing import _extract_section

        rf_text = "Risk Factors: competitive market, regulatory changes..."
        obj = self._make_10k_obj({"risk_factors": rf_text})

        result = _extract_section(obj, "10-K", "risk_factors")
        assert result is not None
        assert "competitive market" in result


class TestSectionMapCompleteness:
    """Verify section maps contain the correct canonical keys."""

    def test_10q_section_map_contains_correct_part_item_keys(self):
        """SECTION_MAP_10Q must map to Part/Item format keys, not old attribute names."""
        from edgar.ai.mcp.tools.filing import SECTION_MAP_10Q

        # Verify canonical format (Part X, Item Y)
        assert SECTION_MAP_10Q["mda"] == "Part I, Item 2"
        assert SECTION_MAP_10Q["risk_factors"] == "Part II, Item 1A"
        assert SECTION_MAP_10Q["legal"] == "Part II, Item 1"
        assert SECTION_MAP_10Q["financials"] == "Part I, Item 1"

        # Verify no old-style attribute names are present
        for key, val in SECTION_MAP_10Q.items():
            assert "part" in val.lower() or val.startswith("Part"), (
                f"10-Q section map value for '{key}' should be a Part/Item key, got '{val}'"
            )

    def test_10k_section_map_contains_friendly_names(self):
        """SECTION_MAP_10K must map to friendly names accepted by TenK.__getitem__."""
        from edgar.ai.mcp.tools.filing import SECTION_MAP_10K

        # These friendly names are directly accepted by TenK.__getitem__
        assert SECTION_MAP_10K["mda"] == "mda"
        assert SECTION_MAP_10K["business"] == "business"
        assert SECTION_MAP_10K["risk_factors"] == "risk_factors"

    def test_old_item_style_values_not_in_maps(self):
        """Old broken keys like 'item7', 'part1item2' must not appear in maps."""
        from edgar.ai.mcp.tools.filing import SECTION_MAP_10K, SECTION_MAP_10Q

        broken_patterns = ["item7", "item1a", "part1item2", "part2item1a", "item8"]
        for broken in broken_patterns:
            assert broken not in SECTION_MAP_10K.values(), (
                f"Broken key '{broken}' found in SECTION_MAP_10K values"
            )
            assert broken not in SECTION_MAP_10Q.values(), (
                f"Broken key '{broken}' found in SECTION_MAP_10Q values"
            )


class TestExtractSectionDoesNotUseAttributeAccess:
    """Confirm _extract_section does NOT use getattr for narrative content."""

    def test_attribute_error_does_not_propagate(self):
        """
        Accessing obj.mda on TenQ raises AttributeError.
        After the fix, _extract_section must not call getattr at all for narrative
        sections, so this error must never surface.
        """
        from edgar.ai.mcp.tools.filing import _extract_section

        # Build an object where attribute access raises AttributeError
        # but __getitem__ works correctly
        class StrictTenQ:
            def __getitem__(self, key):
                if key == "Part I, Item 2":
                    return "MD&A text from __getitem__"
                return None

            def __getattr__(self, name):
                if name in ("mda", "risk_factors", "business", "financials"):
                    raise AttributeError(
                        f"'TenQ' object has no attribute '{name}'"
                    )
                raise AttributeError(name)

        obj = StrictTenQ()
        # This must not raise AttributeError
        result = _extract_section(obj, "10-Q", "mda")
        assert result is not None
        assert "MD&A text" in result

    def test_silence_check_returns_none_not_raises_for_unknown_section(self):
        """Unknown section name produces None, not an exception."""
        from edgar.ai.mcp.tools.filing import _extract_section

        obj = MagicMock()
        obj.__getitem__ = MagicMock(return_value=None)

        result = _extract_section(obj, "10-Q", "nonexistent_section")
        assert result is None
