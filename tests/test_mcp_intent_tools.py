"""
Tests for the intent-based MCP tools.

Tests the new tool handlers in edgar.ai.mcp.tools module:
- edgar_company
- edgar_search
- edgar_filing
- edgar_compare
- edgar_ownership

Also tests the base utilities (tool registry, resolve_company, helpers).
"""

import pytest

from edgar import set_identity


# =============================================================================
# Tool Registry Tests (no network required)
# =============================================================================


class TestToolRegistry:
    """Test tool registration and routing."""

    def test_tools_register_on_import(self):
        """All 5 intent tools register when their modules are imported."""
        from edgar.ai.mcp.tools.base import TOOLS

        # Import all tool modules to trigger registration
        from edgar.ai.mcp.tools import company  # noqa: F401
        from edgar.ai.mcp.tools import search  # noqa: F401
        from edgar.ai.mcp.tools import filing  # noqa: F401
        from edgar.ai.mcp.tools import compare  # noqa: F401
        from edgar.ai.mcp.tools import ownership  # noqa: F401

        expected_tools = {
            "edgar_company",
            "edgar_search",
            "edgar_filing",
            "edgar_compare",
            "edgar_ownership",
        }
        assert expected_tools.issubset(set(TOOLS.keys()))

    def test_tool_schemas_have_required_fields(self):
        """Each registered tool has name, description, handler, and schema."""
        from edgar.ai.mcp.tools.base import TOOLS
        from edgar.ai.mcp.tools import company, search, filing, compare, ownership  # noqa: F401

        for name, info in TOOLS.items():
            assert "name" in info, f"Tool {name} missing 'name'"
            assert "description" in info, f"Tool {name} missing 'description'"
            assert "handler" in info, f"Tool {name} missing 'handler'"
            assert "schema" in info, f"Tool {name} missing 'schema'"
            assert info["schema"].get("type") == "object", f"Tool {name} schema type not 'object'"

    def test_get_tool_definitions(self):
        """get_tool_definitions returns list usable by MCP list_tools."""
        from edgar.ai.mcp.tools.base import get_tool_definitions
        from edgar.ai.mcp.tools import company, search, filing, compare, ownership  # noqa: F401

        definitions = get_tool_definitions()
        assert isinstance(definitions, list)
        assert len(definitions) >= 5

        for defn in definitions:
            assert "name" in defn
            assert "description" in defn
            assert "inputSchema" in defn

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        """Calling unknown tool returns error response, not exception."""
        from edgar.ai.mcp.tools.base import call_tool_handler

        result = await call_tool_handler("nonexistent_tool", {})
        assert result.success is False
        assert "Unknown tool" in result.error
        assert "nonexistent_tool" in result.error


# =============================================================================
# Base Utilities Tests (no network required)
# =============================================================================


class TestBaseUtilities:
    """Test base utility functions."""

    def test_truncate_text_short(self):
        """Short text passes through unchanged."""
        from edgar.ai.mcp.tools.base import truncate_text

        text = "Hello, world!"
        assert truncate_text(text, max_chars=100) == text

    def test_truncate_text_long(self):
        """Long text gets truncated with indicator."""
        from edgar.ai.mcp.tools.base import truncate_text

        text = "x" * 10000
        result = truncate_text(text, max_chars=100)
        assert len(result) < len(text)
        assert "truncated" in result

    def test_success_response(self):
        """success() creates proper ToolResponse."""
        from edgar.ai.mcp.tools.base import success

        resp = success({"key": "value"}, next_steps=["Do something"])
        assert resp.success is True
        assert resp.data == {"key": "value"}
        assert resp.next_steps == ["Do something"]
        assert resp.error is None

    def test_error_response(self):
        """error() creates proper ToolResponse."""
        from edgar.ai.mcp.tools.base import error

        resp = error("Something failed", suggestions=["Try this"])
        assert resp.success is False
        assert resp.error == "Something failed"
        assert resp.suggestions == ["Try this"]

    def test_tool_response_to_json(self):
        """ToolResponse serializes to valid JSON."""
        import json
        from edgar.ai.mcp.tools.base import success

        resp = success({"count": 42})
        json_str = resp.to_json()
        parsed = json.loads(json_str)
        assert parsed["success"] is True
        assert parsed["data"]["count"] == 42

    def test_format_filing_summary(self):
        """format_filing_summary extracts expected fields."""
        from unittest.mock import MagicMock
        from edgar.ai.mcp.tools.base import format_filing_summary

        filing = MagicMock()
        filing.accession_number = "0000320193-23-000077"
        filing.form = "10-K"
        filing.filing_date = "2023-11-03"
        filing.company = "Apple Inc"
        filing.cik = 320193

        result = format_filing_summary(filing)
        assert result["accession_number"] == "0000320193-23-000077"
        assert result["form"] == "10-K"

    def test_format_company_profile(self):
        """format_company_profile extracts available fields."""
        from unittest.mock import MagicMock
        from edgar.ai.mcp.tools.base import format_company_profile

        company = MagicMock()
        company.cik = 320193
        company.name = "Apple Inc"
        company.tickers = ["AAPL"]
        company.sic = "3571"
        company.sic_description = "Electronic Computers"

        result = format_company_profile(company)
        assert result["name"] == "Apple Inc"
        assert result["tickers"] == ["AAPL"]

    def test_get_error_suggestions_known_type(self):
        """Known error types return specific suggestions."""
        from edgar.ai.mcp.tools.base import get_error_suggestions

        suggestions = get_error_suggestions(ValueError("bad input"))
        assert len(suggestions) > 0

    def test_get_error_suggestions_unknown_type(self):
        """Unknown error types return generic suggestions."""
        from edgar.ai.mcp.tools.base import get_error_suggestions

        suggestions = get_error_suggestions(RuntimeError("something"))
        assert len(suggestions) > 0


# =============================================================================
# resolve_company Tests (network required)
# =============================================================================


class TestResolveCompany:
    """Test company resolution from flexible identifiers."""

    def test_resolve_by_ticker(self):
        """Resolve company by ticker symbol."""
        from edgar.ai.mcp.tools.base import resolve_company

        company = resolve_company("AAPL")
        assert company is not None
        assert "Apple" in company.name

    def test_resolve_by_cik(self):
        """Resolve company by CIK number."""
        from edgar.ai.mcp.tools.base import resolve_company

        company = resolve_company("320193")
        assert company is not None
        assert "Apple" in company.name

    def test_resolve_empty_raises(self):
        """Empty identifier raises ValueError."""
        from edgar.ai.mcp.tools.base import resolve_company

        with pytest.raises(ValueError, match="cannot be empty"):
            resolve_company("")

    def test_resolve_whitespace_raises(self):
        """Whitespace-only identifier raises ValueError."""
        from edgar.ai.mcp.tools.base import resolve_company

        with pytest.raises(ValueError, match="cannot be empty"):
            resolve_company("   ")

    def test_resolve_lowercase_ticker(self):
        """Lowercase ticker gets resolved via uppercase fallback."""
        from edgar.ai.mcp.tools.base import resolve_company

        company = resolve_company("aapl")
        assert company is not None
        assert "Apple" in company.name


# =============================================================================
# edgar_company Tool Tests (network required)
# =============================================================================


class TestEdgarCompanyTool:
    """Test edgar_company intent tool."""

    @pytest.mark.asyncio
    async def test_company_profile_only(self):
        """Get company with profile only."""
        from edgar.ai.mcp.tools.company import edgar_company

        result = await edgar_company(identifier="AAPL", include=["profile"])
        assert result.success is True
        assert "Apple" in result.data["company"]
        assert "profile" in result.data

    @pytest.mark.asyncio
    async def test_company_with_financials(self):
        """Get company with financials included."""
        from edgar.ai.mcp.tools.company import edgar_company

        result = await edgar_company(
            identifier="MSFT",
            include=["profile", "financials"],
            periods=2,
        )
        assert result.success is True
        assert "financials" in result.data

    @pytest.mark.asyncio
    async def test_company_default_includes(self):
        """Default includes return profile, financials, and filings."""
        from edgar.ai.mcp.tools.company import edgar_company

        result = await edgar_company(identifier="AAPL")
        assert result.success is True
        assert "profile" in result.data
        assert "financials" in result.data
        assert "recent_filings" in result.data

    @pytest.mark.asyncio
    async def test_company_ttm_financials(self):
        """Get company with ttm financials."""
        from edgar.ai.mcp.tools.company import edgar_company

        result = await edgar_company(
            identifier="MSFT",
            include=["financials"],
            period="ttm",
            periods=2,
        )
        assert result.success is True
        assert "financials" in result.data
        assert result.data["financials"]["period_type"] == "ttm"
        assert result.data["financials"]["periods"] == 2

    @pytest.mark.asyncio
    async def test_company_legacy_annual_false(self):
        """Legacy annual=False maps to quarterly period."""
        from edgar.ai.mcp.tools.company import edgar_company

        result = await edgar_company(
            identifier="MSFT",
            include=["financials"],
            annual=False,
            periods=1
        )
        assert result.success is True
        assert result.data["financials"]["period_type"] == "quarterly"

    @pytest.mark.asyncio
    async def test_company_invalid_period_fallback(self):
        """Invalid period falls back to annual."""
        from edgar.ai.mcp.tools.company import edgar_company

        result = await edgar_company(
            identifier="MSFT",
            include=["financials"],
            period="invalid_mode"
        )
        assert result.success is True
        assert result.data["financials"]["period_type"] == "annual"


# =============================================================================
# edgar_search Tool Tests (network required)
# =============================================================================


class TestEdgarSearchTool:
    """Test edgar_search intent tool."""

    @pytest.mark.asyncio
    async def test_search_companies(self):
        """Search for companies by name."""
        from edgar.ai.mcp.tools.search import edgar_search

        result = await edgar_search(query="Apple", search_type="companies", limit=5)
        assert result.success is True
        assert "companies" in result.data

    @pytest.mark.asyncio
    async def test_search_filings_for_company(self):
        """Search filings for a specific company."""
        from edgar.ai.mcp.tools.search import edgar_search

        result = await edgar_search(
            identifier="AAPL",
            form="10-K",
            search_type="filings",
            limit=3,
        )
        assert result.success is True
        assert "filings" in result.data

    @pytest.mark.asyncio
    async def test_search_empty_query(self):
        """Search with no criteria returns error."""
        from edgar.ai.mcp.tools.search import edgar_search

        result = await edgar_search(search_type="companies")
        # No query + companies = no results, but filings might still work in "all" mode
        # With search_type="companies" and no query, result should be empty
        assert result.success is False or "companies" not in result.data


# =============================================================================
# edgar_filing Tool Tests (network required)
# =============================================================================


class TestEdgarFilingTool:
    """Test edgar_filing intent tool."""

    @pytest.mark.asyncio
    async def test_latest_10k_summary(self):
        """Get latest 10-K filing summary for a company."""
        from edgar.ai.mcp.tools.filing import edgar_filing

        result = await edgar_filing(
            identifier="AAPL",
            form="10-K",
            sections=["summary"],
        )
        assert result.success is True
        assert result.data["form_type"] in ["10-K", "10-K/A"]

    @pytest.mark.asyncio
    async def test_filing_no_params_returns_error(self):
        """Calling with no parameters returns error."""
        from edgar.ai.mcp.tools.filing import edgar_filing

        result = await edgar_filing()
        assert result.success is False


# =============================================================================
# edgar_compare Tool Tests (network required)
# =============================================================================


class TestEdgarCompareTool:
    """Test edgar_compare intent tool."""

    @pytest.mark.asyncio
    async def test_compare_two_companies(self):
        """Compare two companies."""
        from edgar.ai.mcp.tools.compare import edgar_compare

        result = await edgar_compare(
            identifiers=["AAPL", "MSFT"],
            metrics=["revenue"],
            periods=2,
        )
        assert result.success is True
        assert result.data["comparison"]["companies_count"] >= 1

    @pytest.mark.asyncio
    async def test_compare_single_company_error(self):
        """Comparing a single company returns error."""
        from edgar.ai.mcp.tools.compare import edgar_compare

        result = await edgar_compare(identifiers=["AAPL"])
        assert result.success is False
        assert "at least 2" in result.error

    @pytest.mark.asyncio
    async def test_compare_no_params_error(self):
        """Calling with no identifiers or industry returns error."""
        from edgar.ai.mcp.tools.compare import edgar_compare

        result = await edgar_compare()
        assert result.success is False


# =============================================================================
# edgar_ownership Tool Tests (network required)
# =============================================================================


class TestEdgarOwnershipTool:
    """Test edgar_ownership intent tool."""

    @pytest.mark.asyncio
    async def test_insider_transactions(self):
        """Get insider transactions for a company."""
        from edgar.ai.mcp.tools.ownership import edgar_ownership

        result = await edgar_ownership(
            identifier="AAPL",
            analysis_type="insiders",
            limit=5,
        )
        assert result.success is True
        assert result.data["analysis"] == "insider_transactions"

    @pytest.mark.asyncio
    async def test_institutional_holders_removed(self):
        """institutions analysis type returns helpful error with redirect."""
        from edgar.ai.mcp.tools.ownership import edgar_ownership

        result = await edgar_ownership(
            identifier="AAPL",
            analysis_type="institutions",
        )
        assert result.success is False
        assert "removed" in result.error
        assert len(result.suggestions) > 0

    @pytest.mark.asyncio
    async def test_fund_portfolio(self):
        """Get fund portfolio from 13F filing."""
        from edgar.ai.mcp.tools.ownership import edgar_ownership

        result = await edgar_ownership(
            identifier="1067983",  # Berkshire Hathaway CIK
            analysis_type="fund_portfolio",
            limit=5,
        )
        assert result.success is True
        assert result.data["analysis"] == "fund_portfolio"

    @pytest.mark.asyncio
    async def test_unknown_analysis_type(self):
        """Unknown analysis type returns error."""
        from edgar.ai.mcp.tools.ownership import edgar_ownership

        result = await edgar_ownership(
            identifier="AAPL",
            analysis_type="unknown_type",
        )
        assert result.success is False
