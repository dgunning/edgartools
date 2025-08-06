"""
EdgarTools AI: AI and LLM integration for SEC financial data analysis.

This package provides AI capabilities for EdgarTools including:
- LLM context generation with token optimization
- Model Context Protocol (MCP) server for Claude Desktop integration
- Semantic enrichment of financial data
- Token counting and optimization

Installation:
    pip install edgartools[ai]

Dependencies included:
    - mcp: Model Context Protocol server support
    - tiktoken: Token counting and optimization

Example:
    >>> from edgar import Company
    >>> from edgar.ai import enhance_financial_fact_llm_context
    >>> 
    >>> company = Company("AAPL")
    >>> # Enhanced context generation with token optimization
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
from edgar.ai.core import (
    AIEnabled,
    TokenOptimizer,
    SemanticEnricher,
    enhance_financial_fact_llm_context,
    check_ai_capabilities
)

# Optional MCP functionality
if MCP_AVAILABLE:
    try:
        from edgar.ai.edgartools_mcp import MCPServer, EdgarToolsServer
    except ImportError:
        # Fallback - MCP might not be fully working
        MCPServer = None
        EdgarToolsServer = None
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