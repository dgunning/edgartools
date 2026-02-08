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
    pip install "edgartools[ai]"

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
from edgar.ai.exporters import export_skill
from edgar.ai.skills import get_skill, list_skills

# Skills infrastructure (always available)
from edgar.ai.skills.base import BaseSkill
from edgar.ai.skills.core import edgartools_skill


# Convenience functions for common workflows
def install_skill(skill=None, to=None, quiet=False, use_symlinks=True):
    """
    Install a skill to ~/.claude/skills/ for automatic discovery.

    Uses symlinks by default so skills stay in sync with package updates.
    When you upgrade edgartools, skills are automatically current.

    Args:
        skill: Skill to install (defaults to edgartools_skill)
        to: Custom installation directory (defaults to ~/.claude/skills/)
        quiet: If True, suppress output messages (default: False)
        use_symlinks: If True (default), use symlinks to keep skills in sync
                     with package. Falls back to copy on Windows without
                     symlink permissions.

    Returns:
        Path: Path to installed skill directory

    Examples:
        >>> from edgar.ai import install_skill
        >>>
        >>> # Install EdgarTools skill (default - uses symlinks)
        >>> install_skill()
        ✨ Installing EdgarTools skill...
        📁 Installed to: /Users/username/.claude/skills/edgartools
        🔗 Using symlinks (auto-updates with package)
        ✅ Ready to use in Claude Desktop and Claude Code!
        >>>
        >>> # Install to custom location
        >>> install_skill(to="~/my-skills")
        PosixPath('/Users/username/my-skills/edgartools')
    """
    import shutil
    from pathlib import Path
    from edgar.paths import get_claude_skills_directory

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

    # Determine output directory
    if to is None:
        output_dir = get_claude_skills_directory(create=True)
    else:
        output_dir = Path(to).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

    skill_dir_name = skill.name.lower().replace(' ', '-')
    skill_output_dir = output_dir / skill_dir_name

    # Remove existing installation
    if skill_output_dir.exists() or skill_output_dir.is_symlink():
        if skill_output_dir.is_symlink():
            skill_output_dir.unlink()
        else:
            shutil.rmtree(skill_output_dir)

    # Try symlink approach
    symlink_success = False
    if use_symlinks:
        try:
            symlink_success = _install_skill_symlinks(skill, skill_output_dir)
        except OSError:
            # Symlinks not supported (Windows without permissions)
            symlink_success = False

    # Fall back to copy if symlinks failed
    if not symlink_success:
        result = export_skill(
            skill,
            format="claude-skills",
            output_dir=output_dir,
            install=False
        )
        if not quiet:
            print(f"📁 Installed to: {result}")
            print("📋 Using file copy (upgrade edgartools to update skills)")
    else:
        result = skill_output_dir
        if not quiet:
            print(f"📁 Installed to: {result}")
            print("🔗 Using symlinks (auto-updates with package)")

    if not quiet:
        print("✅ Ready to use in Claude Desktop and Claude Code!")
        print("="*60 + "\n")

    return result


def _install_skill_symlinks(skill, target_dir: 'Path') -> bool:
    """
    Install skill using symlinks for auto-sync with package updates.

    Creates a directory with symlinks pointing back to the installed package.
    When the package is upgraded, skills automatically reflect the new version.

    Args:
        skill: The skill to install
        target_dir: Where to create the skill directory

    Returns:
        True if successful, False if symlinks not supported
    """
    import shutil
    from pathlib import Path

    content_dir = skill.content_dir  # edgar/ai/skills/core/
    skills_parent = content_dir.parent  # edgar/ai/skills/

    # Create the target directory
    target_dir.mkdir(parents=True, exist_ok=True)

    # Symlink skill files from content_dir (core/)
    # Skip Python module files and cache directories
    skip_patterns = {'__init__.py', '__pycache__', '.pyc'}
    for item in content_dir.iterdir():
        if item.name in skip_patterns or item.name.endswith('.pyc'):
            continue
        if item.is_file():
            (target_dir / item.name).symlink_to(item)

    # Symlink skill subdirectories
    skill_subdirs = ['financials', 'holdings', 'ownership', 'reports', 'xbrl']
    for subdir_name in skill_subdirs:
        subdir = skills_parent / subdir_name
        if subdir.exists() and subdir.is_dir():
            (target_dir / subdir_name).symlink_to(subdir)

    # Symlink forms.yaml
    forms_yaml = skills_parent / "forms.yaml"
    if forms_yaml.exists():
        (target_dir / "forms.yaml").symlink_to(forms_yaml)

    # Copy api-reference (can't symlink - assembled from multiple locations)
    object_docs = skill.get_object_docs()
    if object_docs:
        api_ref_dir = target_dir / "api-reference"
        api_ref_dir.mkdir(exist_ok=True)
        for doc_path in object_docs:
            if doc_path.exists():
                shutil.copy2(doc_path, api_ref_dir / doc_path.name)

    return True


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
        print("💡 Ready to upload via Claude Desktop's skill upload interface!")
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
            'Install with: pip install "edgartools[ai]"'
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
        "install_command": 'pip install "edgartools[ai]"' if MISSING_DEPS else None
    }
