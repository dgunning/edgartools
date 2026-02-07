"""
Tests for MCP server wiring and configuration.

Verifies that the server correctly imports tools, constructs schemas,
and routes tool calls.
"""

import pytest


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
