"""
Tests for MCP workflow-oriented tools (LEGACY).

Tests the old tool handlers in edgar.ai.mcp.tools module.
These are deprecated in favor of the intent-based tools tested in
test_mcp_intent_tools.py.
"""

import pytest

from edgar import set_identity


@pytest.mark.legacy
class TestCompanyResearchTool:
    """Test edgar_company_research tool handler (deprecated)."""

    @pytest.mark.asyncio
    async def test_company_research_minimal(self):
        """Test company research with minimal detail level."""
        from edgar.ai.mcp.tools.company_research import handle_company_research

        args = {
            "identifier": "AAPL",
            "detail_level": "minimal",
            "include_financials": False,
            "include_filings": False,
            "include_ownership": False
        }

        result = await handle_company_research(args)

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Apple" in result[0].text
        assert "CIK:" in result[0].text

    @pytest.mark.asyncio
    async def test_company_research_standard(self):
        """Test company research with standard detail level."""
        from edgar.ai.mcp.tools.company_research import handle_company_research

        args = {
            "identifier": "MSFT",
            "detail_level": "standard",
            "include_financials": True,
            "include_filings": True,
            "include_ownership": False
        }

        result = await handle_company_research(args)

        assert len(result) == 1
        assert result[0].type == "text"
        assert "MICROSOFT" in result[0].text
        # Should include financials section
        assert "Latest Financials:" in result[0].text or "Financials:" in result[0].text
        # Filings may or may not be available depending on data retrieval

    @pytest.mark.asyncio
    async def test_company_research_detailed(self):
        """Test company research with detailed level."""
        from edgar.ai.mcp.tools.company_research import handle_company_research

        args = {
            "identifier": "TSLA",
            "detail_level": "detailed",
            "include_financials": True,
            "include_filings": True,
            "include_ownership": True
        }

        result = await handle_company_research(args)

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Tesla" in result[0].text

    @pytest.mark.asyncio
    async def test_company_research_missing_identifier(self):
        """Test company research with missing identifier."""
        from edgar.ai.mcp.tools.company_research import handle_company_research

        args = {}

        result = await handle_company_research(args)

        assert len(result) == 1
        assert "Error:" in result[0].text
        assert "identifier" in result[0].text.lower()


@pytest.mark.legacy
class TestFinancialAnalysisTool:
    """Test edgar_analyze_financials tool handler (deprecated)."""

    @pytest.mark.asyncio
    async def test_financial_analysis_income_statement(self):
        """Test financial analysis with income statement only."""
        from edgar.ai.mcp.tools.financial_analysis import handle_analyze_financials

        args = {
            "company": "AAPL",
            "periods": 2,
            "annual": True,
            "statement_types": ["income"]
        }

        result = await handle_analyze_financials(args)

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Financial Analysis:" in result[0].text
        assert "Apple" in result[0].text
        assert "Income Statement" in result[0].text

    @pytest.mark.asyncio
    async def test_financial_analysis_multiple_statements(self):
        """Test financial analysis with multiple statement types."""
        from edgar.ai.mcp.tools.financial_analysis import handle_analyze_financials

        args = {
            "company": "MSFT",
            "periods": 4,
            "annual": True,
            "statement_types": ["income", "balance", "cash_flow"]
        }

        result = await handle_analyze_financials(args)

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Income Statement" in result[0].text or "income" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_financial_analysis_quarterly(self):
        """Test financial analysis with quarterly periods."""
        from edgar.ai.mcp.tools.financial_analysis import handle_analyze_financials

        args = {
            "company": "GOOGL",
            "periods": 4,
            "annual": False,
            "statement_types": ["income"]
        }

        result = await handle_analyze_financials(args)

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Quarterly" in result[0].text

    @pytest.mark.asyncio
    async def test_financial_analysis_missing_company(self):
        """Test financial analysis with missing company parameter."""
        from edgar.ai.mcp.tools.financial_analysis import handle_analyze_financials

        args = {}

        result = await handle_analyze_financials(args)

        assert len(result) == 1
        assert "Error:" in result[0].text
        assert "company" in result[0].text.lower()


@pytest.mark.legacy
class TestUtilityFunctions:
    """Test utility functions in edgar.ai.tools.utils (deprecated)."""

    def test_check_output_size_under_limit(self):
        """Test output size check when under token limit."""
        from edgar.ai.mcp.tools.utils import check_output_size

        data = "Short text" * 10
        result = check_output_size(data, max_tokens=1000)

        assert result == data
        assert "truncated" not in result

    def test_check_output_size_over_limit(self):
        """Test output size check when over token limit."""
        from edgar.ai.mcp.tools.utils import check_output_size

        # Create text that exceeds limit (1 token ≈ 4 chars)
        data = "x" * 10000  # ~2500 tokens
        result = check_output_size(data, max_tokens=500)

        assert len(result) < len(data)
        assert "truncated" in result

    def test_format_error_with_suggestions(self):
        """Test error formatting with suggestions."""
        from edgar.ai.mcp.tools.utils import format_error_with_suggestions

        error = ValueError("Invalid ticker symbol")
        result = format_error_with_suggestions(error)

        assert "Error:" in result
        assert "ValueError" in result
        assert "Suggestions:" in result

    def test_build_company_profile_minimal(self):
        """Test company profile building with minimal detail."""
        from edgar import Company
        from edgar.ai.mcp.tools.utils import build_company_profile

        company = Company("AAPL")
        profile = build_company_profile(company, detail_level="minimal")

        assert "Apple" in profile
        assert "CIK:" in profile

    def test_build_company_profile_standard(self):
        """Test company profile building with standard detail."""
        from edgar import Company
        from edgar.ai.mcp.tools.utils import build_company_profile

        company = Company("MSFT")
        profile = build_company_profile(company, detail_level="standard")

        assert "MICROSOFT" in profile
        assert "CIK:" in profile

    def test_build_company_profile_detailed(self):
        """Test company profile building with detailed level."""
        from edgar import Company
        from edgar.ai.mcp.tools.utils import build_company_profile

        company = Company("GOOGL")
        profile = build_company_profile(company, detail_level="detailed")

        assert "CIK:" in profile
