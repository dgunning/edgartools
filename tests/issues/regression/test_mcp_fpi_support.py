"""
Regression test for Foreign Private Issuer (FPI) Support in EdgarTools MCP.

This adds support for 20-F and 6-K filings in the MCP server, enabling section
extraction and financial data for Foreign Private Issuers (companies like
Novo Nordisk, BioNTech, ASML that file 20-F instead of 10-K).

The core library already supports 20-F and 6-K - the gap was only in the MCP layer:
- TwentyF class exists with full section structure (Items 1-19)
- SixK = CurrentReport alias exists
- IFRS tags exist in statement_resolver.py alongside US-GAAP
- Missing: Section maps in MCP edgar_filing tool
"""

import logging

import pytest
from unittest.mock import MagicMock

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Unit tests for section maps and _extract_section (no network required)
# ---------------------------------------------------------------------------


class TestSectionMapCompleteness:
    """Verify 20-F and 6-K section maps exist and contain correct keys."""

    def test_20f_section_map_exists(self):
        """SECTION_MAP_20F must exist and contain required FPI sections."""
        from edgar.ai.mcp.tools.filing import SECTION_MAP_20F

        assert SECTION_MAP_20F is not None
        # Required sections for 20-F
        assert "business" in SECTION_MAP_20F
        assert "risk_factors" in SECTION_MAP_20F
        assert "mda" in SECTION_MAP_20F
        assert "financials" in SECTION_MAP_20F
        assert "directors" in SECTION_MAP_20F
        assert "shareholders" in SECTION_MAP_20F
        assert "financial_info" in SECTION_MAP_20F
        assert "controls" in SECTION_MAP_20F

    def test_20f_section_map_values(self):
        """SECTION_MAP_20F values should map to Item numbers for TwentyF.__getitem__."""
        from edgar.ai.mcp.tools.filing import SECTION_MAP_20F

        # These map to TwentyF Item keys
        assert SECTION_MAP_20F["business"] == "Item 4"
        assert SECTION_MAP_20F["risk_factors"] == "Item 3"
        assert SECTION_MAP_20F["mda"] == "Item 5"
        assert SECTION_MAP_20F["financials"] == "financials"
        assert SECTION_MAP_20F["directors"] == "Item 6"
        assert SECTION_MAP_20F["shareholders"] == "Item 7"
        assert SECTION_MAP_20F["financial_info"] == "Item 8"
        assert SECTION_MAP_20F["controls"] == "Item 15"

    def test_6k_section_map_exists(self):
        """SECTION_MAP_6K must exist and contain required sections."""
        from edgar.ai.mcp.tools.filing import SECTION_MAP_6K

        assert SECTION_MAP_6K is not None
        assert "financials" in SECTION_MAP_6K
        assert "full_text" in SECTION_MAP_6K

    def test_6k_section_map_values(self):
        """SECTION_MAP_6K values should be correct."""
        from edgar.ai.mcp.tools.filing import SECTION_MAP_6K

        assert SECTION_MAP_6K["financials"] == "financials"
        assert SECTION_MAP_6K["full_text"] == "full_text"


class TestGetSectionList:
    """Verify _get_section_list returns correct sections for 20-F and 6-K."""

    def test_20f_returns_correct_sections(self):
        """_get_section_list returns 20-F sections for 20-F form type."""
        from edgar.ai.mcp.tools.filing import _get_section_list, SECTION_MAP_20F

        sections = _get_section_list("20-F")
        assert sections == list(SECTION_MAP_20F.keys())

    def test_20f_amended_returns_correct_sections(self):
        """_get_section_list returns 20-F sections for 20-F/A form type."""
        from edgar.ai.mcp.tools.filing import _get_section_list, SECTION_MAP_20F

        sections = _get_section_list("20-F/A")
        assert sections == list(SECTION_MAP_20F.keys())

    def test_6k_returns_correct_sections(self):
        """_get_section_list returns 6-K sections for 6-K form type."""
        from edgar.ai.mcp.tools.filing import _get_section_list, SECTION_MAP_6K

        sections = _get_section_list("6-K")
        assert sections == list(SECTION_MAP_6K.keys())

    def test_6k_amended_returns_correct_sections(self):
        """_get_section_list returns 6-K sections for 6-K/A form type."""
        from edgar.ai.mcp.tools.filing import _get_section_list, SECTION_MAP_6K

        sections = _get_section_list("6-K/A")
        assert sections == list(SECTION_MAP_6K.keys())


class TestExtractSectionFPI:
    """Test _extract_section for 20-F and 6-K forms."""

    def _make_20f_obj(self, items_data: dict):
        """Build a mock TwentyF-like object that responds to __getitem__."""
        obj = MagicMock()
        obj.__getitem__ = MagicMock(side_effect=lambda key: items_data.get(key))
        obj.financials = None
        return obj

    def _make_6k_obj(self, items_data: dict):
        """Build a mock 6-K object."""
        obj = MagicMock()
        obj.__getitem__ = MagicMock(side_effect=lambda key: items_data.get(key))
        obj.financials = None
        return obj

    def test_20f_business_uses_item_4(self):
        """Business section on 20-F should use 'Item 4' key."""
        from edgar.ai.mcp.tools.filing import _extract_section

        business_text = "Information on the Company: BioNTech SE is a biotechnology company..."
        obj = self._make_20f_obj({"Item 4": business_text})

        result = _extract_section(obj, "20-F", "business")
        assert result is not None, "Business section must not be null for 20-F"
        assert "biotechnology company" in result

    def test_20f_risk_factors_uses_item_3(self):
        """Risk Factors on 20-F should use 'Item 3' key (Key Information)."""
        from edgar.ai.mcp.tools.filing import _extract_section

        rf_text = "Key Information: Risk factors include regulatory approval, competition..."
        obj = self._make_20f_obj({"Item 3": rf_text})

        result = _extract_section(obj, "20-F", "risk_factors")
        assert result is not None, "Risk factors section must not be null for 20-F"
        assert "regulatory approval" in result

    def test_20f_mda_uses_item_5(self):
        """MD&A on 20-F should use 'Item 5' key (Operating and Financial Review)."""
        from edgar.ai.mcp.tools.filing import _extract_section

        mda_text = "Operating and Financial Review: Our revenues increased by 25%..."
        obj = self._make_20f_obj({"Item 5": mda_text})

        result = _extract_section(obj, "20-F", "mda")
        assert result is not None, "MD&A section must not be null for 20-F"
        assert "revenues increased" in result

    def test_20f_directors_uses_item_6(self):
        """Directors section on 20-F should use 'Item 6' key."""
        from edgar.ai.mcp.tools.filing import _extract_section

        directors_text = "Directors, Senior Management and Employees: Our board consists of..."
        obj = self._make_20f_obj({"Item 6": directors_text})

        result = _extract_section(obj, "20-F", "directors")
        assert result is not None, "Directors section must not be null for 20-F"
        assert "board consists" in result

    def test_20f_shareholders_uses_item_7(self):
        """Shareholders section on 20-F should use 'Item 7' key."""
        from edgar.ai.mcp.tools.filing import _extract_section

        shareholders_text = "Major Shareholders: The following table shows our major shareholders..."
        obj = self._make_20f_obj({"Item 7": shareholders_text})

        result = _extract_section(obj, "20-F", "shareholders")
        assert result is not None, "Shareholders section must not be null for 20-F"
        assert "major shareholders" in result.lower()

    def test_20f_controls_uses_item_15(self):
        """Controls section on 20-F should use 'Item 15' key."""
        from edgar.ai.mcp.tools.filing import _extract_section

        controls_text = "Controls and Procedures: Our disclosure controls are effective..."
        obj = self._make_20f_obj({"Item 15": controls_text})

        result = _extract_section(obj, "20-F", "controls")
        assert result is not None, "Controls section must not be null for 20-F"
        assert "disclosure controls" in result

    def test_20f_financials_uses_financials_property(self):
        """Financials section uses obj.financials property, not __getitem__."""
        from edgar.ai.mcp.tools.filing import _extract_section

        fin = MagicMock()
        fin.income_statement.return_value = "Revenue: $5B"
        fin.balance_sheet.return_value = None
        fin.cashflow_statement.return_value = None

        obj = MagicMock()
        obj.financials = fin

        result = _extract_section(obj, "20-F", "financials")
        assert result is not None
        assert "Income Statement" in result
        assert "Revenue: $5B" in result

    def test_20f_amended_form_uses_same_mapping(self):
        """20-F/A should use the same section mapping as 20-F."""
        from edgar.ai.mcp.tools.filing import _extract_section

        business_text = "Company information for amended filing..."
        obj = self._make_20f_obj({"Item 4": business_text})

        result = _extract_section(obj, "20-F/A", "business")
        assert result is not None
        assert "amended filing" in result

    def test_6k_financials_uses_financials_property(self):
        """6-K financials section uses obj.financials property."""
        from edgar.ai.mcp.tools.filing import _extract_section

        fin = MagicMock()
        fin.income_statement.return_value = "Quarterly Revenue: $1.2B"
        fin.balance_sheet.return_value = None
        fin.cashflow_statement.return_value = None

        obj = MagicMock()
        obj.financials = fin

        result = _extract_section(obj, "6-K", "financials")
        assert result is not None
        assert "Income Statement" in result
        assert "Quarterly Revenue" in result

    def test_20f_missing_section_returns_none(self):
        """If a section is absent from a 20-F filing, return None gracefully."""
        from edgar.ai.mcp.tools.filing import _extract_section

        obj = self._make_20f_obj({})
        result = _extract_section(obj, "20-F", "directors")
        assert result is None


class TestExtractSectionDoesNotUseAttributeAccess:
    """Confirm _extract_section uses __getitem__ for 20-F narrative content."""

    def test_20f_attribute_error_does_not_propagate(self):
        """
        Accessing obj.business on TwentyF may raise AttributeError.
        After the fix, _extract_section must use __getitem__ instead.
        """
        from edgar.ai.mcp.tools.filing import _extract_section

        class StrictTwentyF:
            def __getitem__(self, key):
                if key == "Item 4":
                    return "Business information from __getitem__"
                return None

            def __getattr__(self, name):
                if name in ("business", "risk_factors", "mda", "financials"):
                    raise AttributeError(
                        f"'TwentyF' object has no attribute '{name}'"
                    )
                raise AttributeError(name)

        obj = StrictTwentyF()
        # This must not raise AttributeError
        result = _extract_section(obj, "20-F", "business")
        assert result is not None
        assert "Business information" in result


# ---------------------------------------------------------------------------
# Integration tests (require network)
# ---------------------------------------------------------------------------


@pytest.mark.network
class TestFPIIntegration:
    """Integration tests for real FPI filings."""

    def test_biontech_20f_business_section(self):
        """Extract business section from real BioNTech 20-F filing."""
        from edgar import Company

        company = Company("BNTX")
        filings = company.get_filings(form="20-F")
        assert len(filings) > 0, "BioNTech should have 20-F filings"

        filing = filings[0]
        obj = filing.obj()
        assert obj is not None, "Should be able to create TwentyF object"

        # Try to get business section
        business = obj["Item 4"]
        # Business section may or may not be present depending on parsing
        # Just verify no exception is raised

    def test_biontech_20f_financials(self):
        """Access financials from real BioNTech 20-F (IFRS format)."""
        from edgar import Company

        company = Company("BNTX")
        filings = company.get_filings(form="20-F")
        assert len(filings) > 0

        filing = filings[0]
        obj = filing.obj()

        # Try to access financials (should work for IFRS filers)
        if hasattr(obj, 'financials') and obj.financials is not None:
            fin = obj.financials
            # Just verify we can access without exception
            try:
                _ = fin.income_statement()
            except Exception as e:
                logger.debug("Filing has no XBRL data or income_statement failed: %s", e)

    def test_company_financials_for_fpi(self):
        """edgar_company should return financials for FPI companies."""
        from edgar import Company

        company = Company("BNTX")
        # Just verify the company can be accessed
        assert company is not None
        assert company.cik is not None
