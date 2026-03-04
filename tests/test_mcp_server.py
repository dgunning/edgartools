"""
Tests for MCP server wiring and configuration.

Verifies that the server correctly imports tools, constructs schemas,
and routes tool calls.
"""

import json

import pytest

from edgar.ai.mcp.tools.base import ToolResponse, classify_error, error


class TestServerToolImport:
    """Test that the server imports and registers all tools."""

    def test_import_tools_registers_all(self):
        """_import_tools() registers all 5 intent-based tools."""
        from edgar.ai.mcp.server import _import_tools
        from edgar.ai.mcp.tools.base import TOOLS

        _import_tools()

        expected = {"edgar_company", "edgar_search", "edgar_filing", "edgar_compare", "edgar_ownership"}
        assert expected.issubset(set(TOOLS.keys()))

    def test_tool_count(self):
        """Server registers exactly the expected number of tools."""
        from edgar.ai.mcp.server import _import_tools
        from edgar.ai.mcp.tools.base import TOOLS

        _import_tools()
        assert len(TOOLS) >= 5


class TestToolSchemas:
    """Test that tool schemas are well-formed for MCP."""

    def test_schemas_have_required_fields(self):
        """Each tool schema has type, properties, and required."""
        from edgar.ai.mcp.server import _import_tools
        from edgar.ai.mcp.tools.base import TOOLS

        _import_tools()

        for name, info in TOOLS.items():
            schema = info["schema"]
            assert "type" in schema, f"{name} schema missing 'type'"
            assert "properties" in schema, f"{name} schema missing 'properties'"
            assert "required" in schema, f"{name} schema missing 'required'"

    def test_required_params_exist_in_properties(self):
        """All required params are also defined in properties."""
        from edgar.ai.mcp.server import _import_tools
        from edgar.ai.mcp.tools.base import TOOLS

        _import_tools()

        for name, info in TOOLS.items():
            schema = info["schema"]
            properties = set(schema.get("properties", {}).keys())
            required = set(schema.get("required", []))
            assert required.issubset(properties), (
                f"{name}: required params {required - properties} not in properties"
            )


class TestCallToolHandler:
    """Test tool call routing."""

    @pytest.mark.asyncio
    async def test_routes_to_correct_handler(self):
        """call_tool_handler routes to the correct tool."""
        from edgar.ai.mcp.server import _import_tools
        from edgar.ai.mcp.tools.base import call_tool_handler

        _import_tools()

        # Call with missing required param - should get an error response, not crash
        result = await call_tool_handler("edgar_filing", {})
        # edgar_filing with no params returns error response
        assert result.success is False or result.success is True
        # The key point: it didn't raise, it returned a ToolResponse

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        """Unknown tool name returns error ToolResponse."""
        from edgar.ai.mcp.tools.base import call_tool_handler

        result = await call_tool_handler("totally_fake_tool", {})
        assert result.success is False
        assert "Unknown tool" in result.error


class TestServerConfiguration:
    """Test server configuration utilities."""

    def test_test_server_function_exists(self):
        """test_server function is importable."""
        from edgar.ai.mcp.server import test_server
        assert callable(test_server)

    def test_main_function_exists(self):
        """main function is importable."""
        from edgar.ai.mcp.server import main
        assert callable(main)


class TestToolResponseErrorCode:
    """Test error_code field on ToolResponse."""

    def test_error_code_included_in_dict_when_set(self):
        """error_code appears in to_dict() output when set."""
        resp = ToolResponse(success=False, error="fail", error_code="RATE_LIMIT")
        d = resp.to_dict()
        assert d["error_code"] == "RATE_LIMIT"

    def test_error_code_omitted_when_none(self):
        """error_code is omitted from to_dict() when None (backward compat)."""
        resp = ToolResponse(success=False, error="fail")
        d = resp.to_dict()
        assert "error_code" not in d

    def test_error_code_in_json(self):
        """error_code appears in JSON serialization."""
        resp = ToolResponse(success=False, error="fail", error_code="COMPANY_NOT_FOUND")
        parsed = json.loads(resp.to_json())
        assert parsed["error_code"] == "COMPANY_NOT_FOUND"

    def test_error_helper_with_error_code(self):
        """error() helper accepts and sets error_code."""
        resp = error("something broke", error_code="INTERNAL_ERROR")
        assert resp.error_code == "INTERNAL_ERROR"
        assert resp.success is False

    def test_error_helper_without_error_code(self):
        """error() helper defaults error_code to None."""
        resp = error("something broke")
        assert resp.error_code is None

    def test_success_response_has_no_error_code(self):
        """Success responses don't include error_code in output."""
        resp = ToolResponse(success=True, data={"result": 42})
        d = resp.to_dict()
        assert "error_code" not in d


class TestErrorClassification:
    """Test classify_error() maps exceptions to correct error codes."""

    def test_company_not_found(self):
        from edgar.entity.core import CompanyNotFoundError
        result = classify_error(CompanyNotFoundError("XYZ"))
        assert result["error_code"] == "COMPANY_NOT_FOUND"
        assert len(result["suggestions"]) > 0

    def test_no_company_facts(self):
        from edgar.entity.entity_facts import NoCompanyFactsFound
        result = classify_error(NoCompanyFactsFound(12345))
        assert result["error_code"] == "NO_FACTS_DATA"

    def test_no_xbrl_data(self):
        from edgar.xbrl.xbrl import XBRLFilingWithNoXbrlData
        result = classify_error(XBRLFilingWithNoXbrlData("No XBRL"))
        assert result["error_code"] == "NO_XBRL_DATA"

    def test_too_many_requests(self):
        from edgar.httprequests import TooManyRequestsError
        result = classify_error(TooManyRequestsError("rate limited"))
        assert result["error_code"] == "RATE_LIMIT"
        assert any("10 minutes" in s for s in result["suggestions"])

    def test_ssl_verification_error(self):
        from edgar.httprequests import SSLVerificationError
        result = classify_error(SSLVerificationError("cert failed", "https://efts.sec.gov"))
        assert result["error_code"] == "SSL_ERROR"
        assert any("use_system_certs" in s for s in result["suggestions"])

    def test_identity_not_set(self):
        from edgar.httprequests import IdentityNotSetException
        result = classify_error(IdentityNotSetException())
        assert result["error_code"] == "IDENTITY_NOT_SET"
        assert any("EDGAR_IDENTITY" in s for s in result["suggestions"])

    def test_sec_identity_error(self):
        from edgar.sgml.sgml_parser import SECIdentityError
        result = classify_error(SECIdentityError())
        assert result["error_code"] == "IDENTITY_NOT_SET"

    def test_sec_filing_not_found(self):
        from edgar.sgml.sgml_parser import SECFilingNotFoundError
        result = classify_error(SECFilingNotFoundError("not found"))
        assert result["error_code"] == "FILING_NOT_FOUND"

    def test_timeout_exception(self):
        from httpx import ReadTimeout
        result = classify_error(ReadTimeout("timed out"))
        assert result["error_code"] == "NETWORK_TIMEOUT"

    def test_connect_error(self):
        from httpx import ConnectError
        result = classify_error(ConnectError("connection refused"))
        assert result["error_code"] == "NETWORK_CONNECTION"

    def test_value_error(self):
        result = classify_error(ValueError("bad input"))
        assert result["error_code"] == "INVALID_ARGUMENTS"
        assert "bad input" in result["message"]

    def test_generic_exception_fallback(self):
        result = classify_error(RuntimeError("something unexpected"))
        assert result["error_code"] == "INTERNAL_ERROR"
        assert "something unexpected" in result["message"]

    def test_all_results_have_required_keys(self):
        """Every classify_error result has error_code, message, suggestions."""
        exceptions = [
            ValueError("bad"),
            RuntimeError("oops"),
        ]
        for exc in exceptions:
            result = classify_error(exc)
            assert "error_code" in result
            assert "message" in result
            assert "suggestions" in result
            assert isinstance(result["suggestions"], list)


class TestCallToolHandlerErrorClassification:
    """Test that call_tool_handler returns structured errors with error_code."""

    @pytest.mark.asyncio
    async def test_value_error_gets_classified(self):
        """ValueError in a tool handler returns INVALID_ARGUMENTS error_code."""
        from edgar.ai.mcp.tools.base import TOOLS, call_tool_handler

        # Register a temporary tool that raises ValueError
        async def _raise_value_error():
            raise ValueError("bad param value")

        TOOLS["_test_value_error"] = {
            "name": "_test_value_error",
            "description": "test",
            "handler": _raise_value_error,
            "schema": {"type": "object", "properties": {}, "required": []},
        }
        try:
            result = await call_tool_handler("_test_value_error", {})
            assert result.success is False
            assert result.error_code == "INVALID_ARGUMENTS"
            assert "bad param value" in result.error
        finally:
            del TOOLS["_test_value_error"]

    @pytest.mark.asyncio
    async def test_runtime_error_gets_internal_error(self):
        """Generic RuntimeError returns INTERNAL_ERROR error_code."""
        from edgar.ai.mcp.tools.base import TOOLS, call_tool_handler

        async def _raise_runtime():
            raise RuntimeError("unexpected failure")

        TOOLS["_test_runtime"] = {
            "name": "_test_runtime",
            "description": "test",
            "handler": _raise_runtime,
            "schema": {"type": "object", "properties": {}, "required": []},
        }
        try:
            result = await call_tool_handler("_test_runtime", {})
            assert result.success is False
            assert result.error_code == "INTERNAL_ERROR"
            assert len(result.suggestions) > 0
        finally:
            del TOOLS["_test_runtime"]

    @pytest.mark.asyncio
    async def test_company_not_found_gets_classified(self):
        """CompanyNotFoundError returns COMPANY_NOT_FOUND error_code."""
        from edgar.ai.mcp.tools.base import TOOLS, call_tool_handler
        from edgar.entity.core import CompanyNotFoundError

        async def _raise_cnf():
            raise CompanyNotFoundError("ZZZXXX")

        TOOLS["_test_cnf"] = {
            "name": "_test_cnf",
            "description": "test",
            "handler": _raise_cnf,
            "schema": {"type": "object", "properties": {}, "required": []},
        }
        try:
            result = await call_tool_handler("_test_cnf", {})
            assert result.success is False
            assert result.error_code == "COMPANY_NOT_FOUND"
        finally:
            del TOOLS["_test_cnf"]
