"""
EdgarTools AI: AI and LLM integration for SEC financial data analysis.

This package provides AI capabilities for EdgarTools including:
- AI Skills: Portable documentation packages for Claude Desktop and other AI tools
- AI-optimized text methods (.text()) with research-backed formats (Markdown-KV, TSV)
- LLM context generation with token optimization
- Model Context Protocol (MCP) server for Claude Desktop integration
- Semantic enrichment of financial data
- Token counting and optimization

Installation:
    pip install edgartools[ai]

Dependencies included:
    - mcp: Model Context Protocol server support
    - tiktoken: Token counting and optimization

Skills API:
    >>> from edgar.ai import edgartools_skill, export_skill
    >>>
    >>> # Export skill for Claude Desktop
    >>> export_skill(edgartools_skill, format="claude-desktop")
    PosixPath('edgartools')

    >>> # List available skills
    >>> from edgar.ai import list_skills
    >>> skills = list_skills()

AI-Optimized Objects:
    >>> from edgar import Company
    >>> company = Company("AAPL")
    >>>
    >>> # Get AI-optimized text representation (Markdown-KV format)
    >>> text = company.text(max_tokens=2000)
    >>> print(text)
    **Company:** Apple Inc.
    **CIK:** 0000320193
    **Ticker:** AAPL

Context Generation:
    >>> from edgar.ai import enhance_financial_fact_llm_context
    >>> context = enhance_financial_fact_llm_context(fact, detail_level='detailed')
"""

# Check for AI dependencies
MISSING_DEPS = []

try:
    import mcp
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    MISSING_DEPS.append("mcp")

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    MISSING_DEPS.append("tiktoken")

# AI is available if we have at least some key dependencies
AI_AVAILABLE = MCP_AVAILABLE or TIKTOKEN_AVAILABLE

# Core functionality (always available)
from edgar.ai.core import AIEnabled, SemanticEnricher, TokenOptimizer, check_ai_capabilities, enhance_financial_fact_llm_context

# Skills infrastructure (always available)
from edgar.ai.skills.base import BaseSkill
from edgar.ai.skills import list_skills, get_skill
from edgar.ai.skills.core import edgartools_skill
from edgar.ai.exporters import export_skill

# Optional MCP functionality
# Note: The class-based MCPServer and EdgarToolsServer are deprecated.
# Use the function-based API instead: from edgar.ai.mcp import main, test_server
if MCP_AVAILABLE:
    # Provide stub classes for backward compatibility
    class MCPServer:
        def __init__(self, *args, **kwargs):
            raise DeprecationWarning(
                "MCPServer class is deprecated. "
                "Use function-based API: from edgar.ai.mcp import main, test_server"
            )

    class EdgarToolsServer:
        def __init__(self, *args, **kwargs):
            raise DeprecationWarning(
                "EdgarToolsServer class is deprecated. "
                "Use function-based API: from edgar.ai.mcp import main, test_server"
            )
else:
    def MCPServer(*args, **kwargs):
        raise ImportError(
            "MCP support requires additional dependencies. "
            "Install with: pip install edgartools[ai]"
        )
    EdgarToolsServer = MCPServer

# Public API
__all__ = [
    # Core
    "AIEnabled",
    "TokenOptimizer",
    "SemanticEnricher",
    "enhance_financial_fact_llm_context",
    "check_ai_capabilities",

    # Skills
    "BaseSkill",
    "list_skills",
    "get_skill",
    "edgartools_skill",
    "export_skill",

    # MCP
    "MCPServer",
    "EdgarToolsServer",

    # Status flags
    "AI_AVAILABLE",
    "MCP_AVAILABLE",
    "TIKTOKEN_AVAILABLE",
    "MISSING_DEPS"
]

def get_ai_info():
    """Get information about AI capabilities."""
    return {
        "ai_available": AI_AVAILABLE,
        "mcp_available": MCP_AVAILABLE,
        "tiktoken_available": TIKTOKEN_AVAILABLE,
        "missing_dependencies": MISSING_DEPS,
        "install_command": "pip install edgartools[ai]" if MISSING_DEPS else None
    }
