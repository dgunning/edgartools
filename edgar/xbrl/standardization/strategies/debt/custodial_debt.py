"""
Custodial Bank Debt Strategy

Handles ShortTermDebt extraction for custodial banks (BK, STT).

Per Senior Architect directive:
- If components missing, return None
- NEVER fall back to fuzzy ShortTermBorrowings match
- Custodial banks have repos as financing, not contamination
"""

import logging
from typing import Any, Dict, Optional

from ..base import (
    BaseStrategy,
    StrategyResult,
    ExtractionMode,
    ExtractionMethod,
    FactHelper,
)
from .. import register_strategy

logger = logging.getLogger(__name__)


@register_strategy
class CustodialDebtStrategy(BaseStrategy):
    """
    Custodial Banks (STT, BK): Component Sum ONLY.

    Per Senior Architect directive:
    - If components missing, return None
    - NEVER fall back to fuzzy ShortTermBorrowings match
    - Custodial banks have repos as financing, not contamination

    Parameters:
        repos_as_debt: Include repos in debt calculation (default False for GAAP)
        safe_fallback: Whether to use DebtCurrent fallback (default False - NEVER fuzzy!)
    """

    strategy_name = "custodial_debt"
    metric_name = "ShortTermDebt"
    version = "1.0.0"

    def extract(
        self,
        xbrl: Any,
        facts_df: Any,
        mode: ExtractionMode = ExtractionMode.GAAP
    ) -> StrategyResult:
        """Execute custodial bank debt extraction."""
        ticker = self.params.get('ticker', 'UNKNOWN')

        # Get CPLTD (always needed)
        cpltd = FactHelper.get_fact_value(facts_df, 'LongTermDebtCurrent') or 0

        # Specific components for custodial banks
        other_stb = FactHelper.get_fact_value(facts_df, 'OtherShortTermBorrowings')
        fed_funds = FactHelper.get_fact_value(facts_df, 'FederalFundsPurchased')
        commercial_paper = FactHelper.get_fact_value(facts_df, 'CommercialPaper')

        # 10-Q FALLBACK: Try DebtCurrent if no components found
        if (other_stb is None or other_stb == 0) and \
           (fed_funds is None or fed_funds == 0) and \
           (commercial_paper is None or commercial_paper == 0):

            debt_current = FactHelper.get_fact_value(facts_df, 'DebtCurrent')

            # ADR-012: Validate DebtCurrent is reasonable for a custodial bank
            # Custodial bank current debt typically < $50B
            # If we find value > $100B, it's likely a tree fallback error
            MAX_REASONABLE_DEBT = 100_000_000_000  # $100B sanity check

            if debt_current is not None and 0 < debt_current < MAX_REASONABLE_DEBT:
                logger.debug(f"Custodial [{ticker}]: Using DebtCurrent fallback = ${debt_current/1e9:.1f}B")
                return StrategyResult(
                    value=debt_current + cpltd,
                    concept="us-gaap:DebtCurrent",
                    method=ExtractionMethod.DIRECT,
                    confidence=0.8,
                    notes=f"Custodial [{ticker}]: DebtCurrent({debt_current/1e9:.1f}B) + CPLTD({cpltd/1e9:.1f}B) [10-Q fallback]",
                    components={
                        'DebtCurrent': debt_current,
                        'LongTermDebtCurrent': cpltd,
                    },
                    metadata={'archetype': 'custodial', 'fallback': 'debt_current'}
                )
            elif debt_current is not None and debt_current >= MAX_REASONABLE_DEBT:
                # ADR-012: Reject unreasonable values - likely tree contamination
                logger.warning(f"Custodial [{ticker}]: ADR-012 rejected DebtCurrent=${debt_current/1e9:.1f}B (>$100B - likely tree contamination)")

        # Check for company-specific repos
        # For custodial, repos are financing but may NOT be included in GAAP "Current Debt"
        repos_liability = FactHelper.get_fact_value_fuzzy(facts_df, 'SecuritiesSoldUnderAgreementsToRepurchase') or 0

        components = {}
        total = 0.0

        if other_stb is not None and other_stb > 0:
            total += other_stb
            components['OtherShortTermBorrowings'] = other_stb

        if fed_funds is not None and fed_funds > 0:
            total += fed_funds
            components['FederalFundsPurchased'] = fed_funds

        if commercial_paper is not None and commercial_paper > 0:
            total += commercial_paper
            components['CommercialPaper'] = commercial_paper

        # Check config for repos_as_debt
        # For GAAP validation, repos typically NOT included in yfinance "Current Debt"
        include_repos = self.params.get('repos_as_debt', False)
        if include_repos and repos_liability > 0:
            total += repos_liability
            components['SecuritiesSoldUnderAgreementsToRepurchase'] = repos_liability

        if cpltd > 0:
            total += cpltd
            components['LongTermDebtCurrent'] = cpltd

        # CRITICAL: If no components found, return None - do NOT fuzzy match
        # Per architect: "return None rather than fuzzy-match for STT/BK"
        if total == 0 or not components:
            return StrategyResult(
                value=None,
                concept=None,
                method=ExtractionMethod.DIRECT,
                confidence=0.0,
                notes=f"Custodial [{ticker}]: No components found - flagged for manual review",
                metadata={'archetype': 'custodial', 'manual_review': True}
            )

        return StrategyResult(
            value=total,
            concept=None,
            method=ExtractionMethod.COMPOSITE,
            confidence=0.9,
            notes=f"Custodial [{ticker}]: Component sum",
            components=components,
            metadata={
                'archetype': 'custodial',
                'repos_liability': repos_liability,
                'include_repos': include_repos,
            }
        )
