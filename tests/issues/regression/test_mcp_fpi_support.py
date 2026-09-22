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

GitHub PR: https://github.com/dgunning/edgartools/pull/660
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
        from edgar.ai.mcp.tools.reader import SECTION_MAP_20F

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
        from edgar.ai.mcp.tools.reader import SECTION_MAP_20F

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
        from edgar.ai.mcp.tools.reader import SECTION_MAP_6K

        assert SECTION_MAP_6K is not None
        assert "financials" in SECTION_MAP_6K
        assert "full_text" in SECTION_MAP_6K

    def test_6k_section_map_values(self):
        """SECTION_MAP_6K values should be correct."""
        from edgar.ai.mcp.tools.reader import SECTION_MAP_6K

        assert SECTION_MAP_6K["financials"] == "financials"
        assert SECTION_MAP_6K["full_text"] == "full_text"


class TestGetSectionList:
    """Verify _get_section_list returns correct sections for 20-F and 6-K."""

    def test_20f_returns_correct_sections(self):
        """_get_section_list returns 20-F sections for 20-F form type."""
        from edgar.ai.mcp.tools.reader import _get_section_list, SECTION_MAP_20F

        sections = _get_section_list("20-F")
        assert sections == list(SECTION_MAP_20F.keys())

    def test_20f_amended_returns_correct_sections(self):
        """_get_section_list returns 20-F sections for 20-F/A form type."""
        from edgar.ai.mcp.tools.reader import _get_section_list, SECTION_MAP_20F

        sections = _get_section_list("20-F/A")
        assert sections == list(SECTION_MAP_20F.keys())

    def test_6k_returns_correct_sections(self):
        """_get_section_list returns 6-K sections for 6-K form type."""
        from edgar.ai.mcp.tools.reader import _get_section_list, SECTION_MAP_6K

        sections = _get_section_list("6-K")
        assert sections == list(SECTION_MAP_6K.keys())

    def test_6k_amended_returns_correct_sections(self):
        """_get_section_list returns 6-K sections for 6-K/A form type."""
        from edgar.ai.mcp.tools.reader import _get_section_list, SECTION_MAP_6K

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
        from edgar.ai.mcp.tools.reader import _extract_section

        business_text = "Information on the Company: BioNTech SE is a biotechnology company..."
        obj = self._make_20f_obj({"Item 4": business_text})

        result = _extract_section(obj, "20-F", "business")
        assert result is not None, "Business section must not be null for 20-F"
        assert "biotechnology company" in result

    def test_20f_risk_factors_uses_item_3(self):
        """Risk Factors on 20-F should use 'Item 3' key (Key Information)."""
        from edgar.ai.mcp.tools.reader import _extract_section

        rf_text = "Key Information: Risk factors include regulatory approval, competition..."
        obj = self._make_20f_obj({"Item 3": rf_text})

        result = _extract_section(obj, "20-F", "risk_factors")
        assert result is not None, "Risk factors section must not be null for 20-F"
        assert "regulatory approval" in result

    def test_20f_mda_uses_item_5(self):
        """MD&A on 20-F should use 'Item 5' key (Operating and Financial Review)."""
        from edgar.ai.mcp.tools.reader import _extract_section

        mda_text = "Operating and Financial Review: Our revenues increased by 25%..."
        obj = self._make_20f_obj({"Item 5": mda_text})

        result = _extract_section(obj, "20-F", "mda")
        assert result is not None, "MD&A section must not be null for 20-F"
        assert "revenues increased" in result

    def test_20f_directors_uses_item_6(self):
        """Directors section on 20-F should use 'Item 6' key."""
        from edgar.ai.mcp.tools.reader import _extract_section

        directors_text = "Directors, Senior Management and Employees: Our board consists of..."
        obj = self._make_20f_obj({"Item 6": directors_text})

        result = _extract_section(obj, "20-F", "directors")
        assert result is not None, "Directors section must not be null for 20-F"
        assert "board consists" in result

    def test_20f_shareholders_uses_item_7(self):
        """Shareholders section on 20-F should use 'Item 7' key."""
        from edgar.ai.mcp.tools.reader import _extract_section

        shareholders_text = "Major Shareholders: The following table shows our major shareholders..."
        obj = self._make_20f_obj({"Item 7": shareholders_text})

        result = _extract_section(obj, "20-F", "shareholders")
        assert result is not None, "Shareholders section must not be null for 20-F"
        assert "major shareholders" in result.lower()

    def test_20f_controls_uses_item_15(self):
        """Controls section on 20-F should use 'Item 15' key."""
        from edgar.ai.mcp.tools.reader import _extract_section

        controls_text = "Controls and Procedures: Our disclosure controls are effective..."
        obj = self._make_20f_obj({"Item 15": controls_text})

        result = _extract_section(obj, "20-F", "controls")
        assert result is not None, "Controls section must not be null for 20-F"
        assert "disclosure controls" in result

    def test_20f_financials_uses_financials_property(self):
        """Financials section uses obj.financials property, not __getitem__."""
        from edgar.ai.mcp.tools.reader import _extract_section

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
        from edgar.ai.mcp.tools.reader import _extract_section

        business_text = "Company information for amended filing..."
        obj = self._make_20f_obj({"Item 4": business_text})

        result = _extract_section(obj, "20-F/A", "business")
        assert result is not None
        assert "amended filing" in result

    def test_6k_financials_uses_financials_property(self):
        """6-K financials section uses obj.financials property."""
        from edgar.ai.mcp.tools.reader import _extract_section

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
        from edgar.ai.mcp.tools.reader import _extract_section

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
        from edgar.ai.mcp.tools.reader import _extract_section

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


class TestFPIIntegration:
    """Integration tests for real FPI filings."""

    @staticmethod
    def _latest_original_20f():
        """BioNTech's most recent 20-F, excluding amendments.

        ``get_filings(form="20-F")`` returns 20-F/A alongside 20-F, and the
        newest filing is often an amendment. That matters: an amendment carries
        only the parts being amended, so BNTX's 2026-07-30 20-F/A has no Item 4
        at all and its 2026-04-01 20-F/A has no income statement. Both tests
        below took ``filings[0]`` and so silently tested whichever of those
        happened to be newest -- which is why neither could afford to assert
        anything. Anchoring on the original filing is what makes the assertions
        below possible.
        """
        from edgar import Company

        filings = Company("BNTX").get_filings(form="20-F")
        assert len(filings) > 0, "BioNTech should have 20-F filings"
        originals = [f for f in filings if f.form == "20-F"]
        assert originals, (
            f"BNTX returned {len(filings)} filings but none was an unamended "
            "20-F, so there is nothing to extract a full annual report from"
        )
        return originals[0]

    @pytest.mark.network
    def test_biontech_20f_business_section(self):
        """Extract business section from real BioNTech 20-F filing."""
        obj = self._latest_original_20f().obj()
        assert obj is not None, "Should be able to create TwentyF object"

        business = obj["Item 4"]
        assert business is not None, (
            "Item 4 (Information on the Company) is absent. This test used to "
            "discard the result and assert nothing, so it reported green while "
            "extracting nothing at all."
        )
        # Item 4 is the bulk of a 20-F -- every BNTX original runs 330k-430k
        # characters. The floor is deliberately far below that: the claim is
        # that a real business section came back, not that it is a given size.
        text = str(business)
        assert len(text) > 50_000, (
            f"Item 4 extracted only {len(text)} characters; a 20-F business "
            "section is the largest item in the filing"
        )
        assert "BioNTech" in text, "Item 4 does not mention the registrant"

    @pytest.mark.network
    def test_biontech_20f_financials(self):
        """Access financials from real BioNTech 20-F (IFRS format)."""
        obj = self._latest_original_20f().obj()

        fin = getattr(obj, 'financials', None)
        assert fin is not None, (
            "TwentyF.financials is None for BioNTech, so IFRS financial access "
            "-- the thing this test is named for -- does not work"
        )

        income = fin.income_statement()
        assert income is not None, "income_statement() returned None for an IFRS filer"
        df = income.to_dataframe()
        assert not df.empty, "the IFRS income statement rendered no rows"

        # IFRS, not US-GAAP: the taxonomy is the point of FPI support. BioNTech
        # reports under IFRS and its income statement is rooted at the IFRS
        # `Profit or loss` presentation, with `Revenues` rather than us-gaap's
        # `RevenueFromContractWithCustomer...` labelling.
        labels = {str(v).lower() for v in df['label']}
        assert any('revenue' in v for v in labels), (
            f"no revenue line in the IFRS income statement; labels were {sorted(labels)[:15]}"
        )

    @pytest.mark.fast
    def test_fpi_ticker_resolves_to_cik(self):
        """An FPI ticker resolves to its CIK from the local reference data.

        This was called `test_company_financials_for_fpi` and its docstring
        claimed it returned financials for FPI companies. It asserted
        `company is not None` and `company.cik is not None` and stopped, so it
        never touched financials -- `test_biontech_20f_financials` above is
        what actually does. An offline audit found it passing with sockets
        blocked, which is the tell: ticker resolution reads a local file.

        Renamed to what it checks, and given the CIK so it can fail. Ticker
        resolution is worth protecting on its own -- every FPI code path in the
        MCP layer starts here.
        """
        from edgar import Company

        company = Company("BNTX")
        assert company.cik == 1776985, (
            f"BNTX should resolve to BioNTech SE, CIK 1776985; got {company.cik}"
        )
