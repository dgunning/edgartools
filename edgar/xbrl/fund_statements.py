"""
Fund-specific XBRL statement extraction.

This module provides specialized support for detecting and extracting
fund-specific data from investment company filings (BDCs, closed-end funds,
interval funds, etc.).

Note: Schedule of Investments is available via xbrl.statements.schedule_of_investments()
for all companies. This module focuses on fund detection and fund-only features
like Financial Highlights (pending TextBlock parsing implementation).
"""

import logging
from typing import List, Optional

from edgar.xbrl.statements import Statement

logger = logging.getLogger(__name__)


# Indicators that a filing is from an investment company
FUND_INDICATOR_CONCEPTS = [
    'us-gaap_ScheduleOfInvestmentsAbstract',
    'us-gaap_InvestmentOwnedAtFairValue',
    'us-gaap_InvestmentOwnedAtCost',
    'us-gaap_NetAssetValuePerShare',
    'us-gaap_InvestmentCompanyAbstract',
    'us-gaap_InvestmentCompanyFinancialHighlightsTableTextBlock',
    'us-gaap_ScheduleOfInvestmentsLineItems',
]

# Role URI patterns for Financial Highlights
FINANCIAL_HIGHLIGHTS_PATTERNS = [
    'financialhighlights',
    'investmentcompanyfinancialhighlights',
]


class FundStatements:
    """
    Interface for fund-specific XBRL features.

    This class provides:
    - Detection of investment company filings (BDCs, closed-end funds, etc.)
    - Access to fund-specific statements like Financial Highlights

    Note:
        Schedule of Investments is available for all companies via
        xbrl.statements.schedule_of_investments(). Use is_fund_filing()
        to determine if this is an investment company filing.

    Usage:
        >>> xbrl = filing.xbrl()
        >>> if xbrl.fund_statements.is_fund_filing():
        ...     print("This is a fund filing")
        ...     # Schedule of Investments available via statements
        ...     soi = xbrl.statements.schedule_of_investments()
    """

    def __init__(self, xbrl):
        """
        Initialize with an XBRL object.

        Args:
            xbrl: XBRL object containing parsed data
        """
        self.xbrl = xbrl
        self._is_fund_filing_cache = None

    def is_fund_filing(self) -> bool:
        """
        Detect if this XBRL filing is from an investment company.

        Uses heuristics based on:
        - Presence of fund-specific XBRL concepts
        - Financial Highlights role in presentation trees
        - Investment company-specific concepts

        Returns:
            bool: True if this appears to be an investment company filing
        """
        if self._is_fund_filing_cache is not None:
            return self._is_fund_filing_cache

        # Check presentation trees for fund-specific roles
        for role in self.xbrl.presentation_trees.keys():
            role_lower = role.lower().replace(' ', '')
            # Financial Highlights is a strong fund indicator
            if 'financialhighlights' in role_lower:
                self._is_fund_filing_cache = True
                return True
            # Schedule of Investments with specific fund patterns
            if 'consolidatedscheduleofinvestments' in role_lower:
                self._is_fund_filing_cache = True
                return True

        # Check for fund-specific concepts in the element catalog
        if hasattr(self.xbrl, 'element_catalog') and self.xbrl.element_catalog:
            # NetAssetValuePerShare is a strong fund indicator
            if 'us-gaap_NetAssetValuePerShare' in self.xbrl.element_catalog:
                self._is_fund_filing_cache = True
                return True
            # InvestmentCompany concepts
            for concept in ['us-gaap_InvestmentCompanyAbstract',
                          'us-gaap_InvestmentCompanyFinancialHighlightsTableTextBlock']:
                if concept in self.xbrl.element_catalog:
                    self._is_fund_filing_cache = True
                    return True

        # Check presentation trees for fund concepts
        for _role, tree in self.xbrl.presentation_trees.items():
            if hasattr(tree, 'all_nodes'):
                for node_id in tree.all_nodes:
                    # Check for NAV per share - definitive fund indicator
                    if 'NetAssetValuePerShare' in node_id:
                        self._is_fund_filing_cache = True
                        return True

        self._is_fund_filing_cache = False
        return False

    def financial_highlights(self) -> Optional[Statement]:
        """
        Get the Financial Highlights statement.

        This is a fund-specific statement showing per-share financial data:
        - Net Asset Value (NAV) per share
        - Total investment return
        - Expense ratios
        - Portfolio turnover
        - Per-share income/distributions

        Note:
            Currently returns None. Most fund filings present Financial Highlights
            as HTML TextBlocks rather than structured XBRL facts. TextBlock parsing
            is planned for a future release.

        Returns:
            Statement object for Financial Highlights, or None if not available
        """
        # Financial Highlights typically uses HTML TextBlocks rather than structured
        # XBRL facts. Until TextBlock parsing is implemented, return None.
        logger.debug("financial_highlights() not yet implemented - requires TextBlock parsing")
        return None

    def get_available_statements(self) -> List[str]:
        """
        Get list of available fund-specific statements.

        Note: Schedule of Investments is accessed via xbrl.statements.schedule_of_investments()
        and is not listed here as it's available for all companies.

        Returns:
            List of fund-specific statement type names available in this filing
        """
        available = []

        # Financial Highlights - currently stubbed pending TextBlock parsing
        # Will be added when implemented

        return available

    def __rich__(self):
        """Rich console representation."""
        from rich.panel import Panel
        from rich.text import Text

        is_fund = self.is_fund_filing()
        content = Text()
        content.append("Is Fund Filing: ", style="dim")
        content.append(f"{is_fund}\n", style="green" if is_fund else "red")

        if is_fund:
            content.append("\nFund-specific statements:\n", style="dim")
            content.append("• Financial Highlights: ", style="white")
            content.append("pending (requires TextBlock parsing)\n", style="yellow")
            content.append("\nNote: ", style="dim")
            content.append("Schedule of Investments available via\n", style="white")
            content.append("xbrl.statements.schedule_of_investments()", style="cyan")

        return Panel(
            content,
            title="Fund Statements",
            border_style="blue" if is_fund else "dim"
        )

    def __repr__(self) -> str:
        is_fund = self.is_fund_filing()
        return f"FundStatements(is_fund={is_fund})"
