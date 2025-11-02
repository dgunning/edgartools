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
    >>> from edgar.ai import install_skill, package_skill
    >>>
    >>> # Install skill to ~/.claude/skills/
    >>> install_skill()
    PosixPath('/Users/username/.claude/skills/edgartools')
    >>>
    >>> # Create ZIP for Claude Desktop upload
    >>> package_skill()
    PosixPath('edgartools.zip')

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

# Convenience functions for common workflows
def install_skill(skill=None, to=None, quiet=False):
    """
    Install a skill to ~/.claude/skills/ for automatic discovery.

    Simple, delightful API for installing skills to Claude.

    Args:
        skill: Skill to install (defaults to edgartools_skill)
        to: Custom installation directory (defaults to ~/.claude/skills/)
        quiet: If True, suppress output messages (default: False)

    Returns:
        Path: Path to installed skill directory

    Examples:
        >>> from edgar.ai import install_skill
        >>>
        >>> # Install EdgarTools skill (default)
        >>> install_skill()
        ✨ Installing EdgarTools skill...
        📁 Installed to: /Users/username/.claude/skills/edgartools
        ✅ Ready to use in Claude Desktop and Claude Code!
        >>>
        >>> # Install to custom location
        >>> install_skill(to="~/my-skills")
        PosixPath('/Users/username/my-skills/edgartools')
    """
    if skill is None:
        skill = edgartools_skill

    # Show delightful message
    if not quiet:
        print("\n" + "="*60)
        print("""
   ___    _                 _____           _
  | __|__| |__ _ __ _ _ _  |_   _|__  ___ | |___
  | _|/ _` / _` / _` | '_|   | |/ _ \\/ _ \\| (_-<
  |___\\__,_\\__, \\__,_|_|     |_|\\___/\\___/|_/__/
           |___/
        """)
        print("="*60)
        print(f"✨ Installing {skill.name} skill...")
        print()

    result = export_skill(
        skill,
        format="claude-skills",
        output_dir=to,
        install=(to is None)  # Only use install flag if no custom dir
    )

    if not quiet:
        print(f"📁 Installed to: {result}")
        print(f"✅ Ready to use in Claude Desktop and Claude Code!")
        print("="*60 + "\n")

    return result


def package_skill(skill=None, output=None, quiet=False):
    """
    Create a ZIP package for Claude Desktop upload.

    Simple, delightful API for packaging skills as ZIP files.

    Args:
        skill: Skill to package (defaults to edgartools_skill)
        output: Output directory (defaults to current directory)
        quiet: If True, suppress output messages (default: False)

    Returns:
        Path: Path to created ZIP file

    Examples:
        >>> from edgar.ai import package_skill
        >>>
        >>> # Create ZIP in current directory (default)
        >>> package_skill()
        📦 Packaging EdgarTools skill...
        ✅ Created: edgartools.zip
        💡 Ready to upload via Claude Desktop's skill upload interface!
        >>>
        >>> # Create ZIP in custom location
        >>> package_skill(output="~/Desktop")
        PosixPath('/Users/username/Desktop/edgartools.zip')
    """
    if skill is None:
        skill = edgartools_skill

    # Show delightful message
    if not quiet:
        print("\n" + "="*60)
        print("""
   ___    _                 _____           _
  | __|__| |__ _ __ _ _ _  |_   _|__  ___ | |___
  | _|/ _` / _` / _` | '_|   | |/ _ \\/ _ \\| (_-<
  |___\\__,_\\__, \\__,_|_|     |_|\\___/\\___/|_/__/
           |___/
        """)
        print("="*60)
        print(f"📦 Packaging {skill.name} skill as ZIP...")
        print()

    result = export_skill(
        skill,
        format="claude-desktop",
        output_dir=output,
        create_zip=True
    )

    if not quiet:
        print(f"✅ Created: {result.name}")
        print(f"📍 Location: {result.parent}")
        print(f"💡 Ready to upload via Claude Desktop's skill upload interface!")
        print("="*60 + "\n")

    return result

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

    # Convenience functions (delightful API)
    "install_skill",
    "package_skill",

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
