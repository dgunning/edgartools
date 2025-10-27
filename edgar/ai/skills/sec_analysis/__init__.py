"""
SEC Filing Analysis Skill - Core EdgarTools AI skill.

Provides comprehensive documentation and helper functions for analyzing
SEC filings and financial statements using EdgarTools.
"""

from pathlib import Path
from typing import Dict, Callable
from edgar.ai.skills.base import BaseSkill

__all__ = ['SECAnalysisSkill', 'sec_analysis_skill']


class SECAnalysisSkill(BaseSkill):
    """
    SEC Filing Analysis - EdgarTools' foundational AI skill.

    This skill provides:
    - Comprehensive API documentation for SEC filing analysis
    - Helper functions for common workflows
    - Object reference with token estimates
    - Workflow patterns for multi-step analysis

    The skill covers:
    - Getting filings (3 approaches: Published, Current, Company-specific)
    - Getting financials (2 approaches: Entity Facts, Filing XBRL)
    - Multi-company analysis
    - Object representations optimized for AI

    Example:
        >>> from edgar.ai.skills.sec_analysis import sec_analysis_skill
        >>>
        >>> # List available documentation
        >>> print(sec_analysis_skill.get_documents())
        >>> ['skill', 'objects', 'workflows', 'readme']
        >>>
        >>> # Get main skill documentation
        >>> guide = sec_analysis_skill.get_document_content("skill")
        >>>
        >>> # Access helper functions
        >>> helpers = sec_analysis_skill.get_helpers()
        >>> get_revenue_trend = helpers['get_revenue_trend']
        >>> income = get_revenue_trend("AAPL", periods=3)
        >>>
        >>> # Export skill for Claude Desktop
        >>> path = sec_analysis_skill.export(
        ...     format="claude-desktop",
        ...     output_dir="~/.config/claude/skills"
        ... )
    """

    @property
    def name(self) -> str:
        """Skill name: 'SEC Filing Analysis'"""
        return "SEC Filing Analysis"

    @property
    def description(self) -> str:
        """Skill description for AI agents."""
        return (
            "Query and analyze SEC filings and financial statements using EdgarTools. "
            "Get company data, filings, XBRL financials, and perform multi-company analysis."
        )

    @property
    def content_dir(self) -> Path:
        """Path to skill documentation directory."""
        return Path(__file__).parent

    def get_object_docs(self) -> list[Path]:
        """
        Return centralized object documentation to include in skill exports.

        Returns paths to detailed API reference docs that complement the
        skill's tutorial documentation.

        Returns:
            List of Path objects to centralized markdown documentation files
        """
        # Navigate from edgar/ai/skills/sec_analysis/ to edgar/ root
        edgar_root = Path(__file__).parent.parent.parent.parent

        return [
            edgar_root / "entity/docs/Company.md",
            edgar_root / "entity/docs/EntityFiling.md",
            edgar_root / "entity/docs/EntityFilings.md",
            edgar_root / "xbrl/docs/XBRL.md",
            edgar_root / "xbrl/docs/Statement.md",
        ]

    def get_helpers(self) -> Dict[str, Callable]:
        """
        Return helper functions provided by this skill.

        Helper functions simplify common SEC analysis workflows:
        - get_filings_by_period: Get filings for a specific quarter
        - get_today_filings: Get recent filings (last ~24 hours)
        - get_revenue_trend: Get multi-period income statement
        - get_filing_statement: Get statement from specific filing
        - compare_companies_revenue: Compare revenue across companies

        Returns:
            Dict mapping function names to callable objects
        """
        # Import here to avoid circular dependencies
        from edgar.ai import helpers

        return {
            'get_filings_by_period': helpers.get_filings_by_period,
            'get_today_filings': helpers.get_today_filings,
            'get_revenue_trend': helpers.get_revenue_trend,
            'get_filing_statement': helpers.get_filing_statement,
            'compare_companies_revenue': helpers.compare_companies_revenue,
        }


# Create singleton instance for convenience
sec_analysis_skill = SECAnalysisSkill()
