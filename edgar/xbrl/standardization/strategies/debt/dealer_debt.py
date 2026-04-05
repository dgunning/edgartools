"""
Dealer Bank Debt Strategy

Handles ShortTermDebt extraction for dealer/investment banks (GS, MS).

Dealers have repos as separate line items (~$274B for GS).
They report clean UnsecuredShortTermBorrowings tag, so use it directly.
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
class DealerDebtStrategy(BaseStrategy):
    """
    Dealer Banks (GS, MS): Direct UnsecuredSTB.

    Dealers have repos as separate line items (~$274B for GS).
    Use the clean unsecured STB tag directly.

    Parameters:
        use_unsecured_stb: Prefer UnsecuredShortTermBorrowings (default True)
        safe_fallback: Allow fallback to other concepts (default True)
    """

    strategy_name = "dealer_debt"
    metric_name = "ShortTermDebt"
    version = "1.0.0"

    def extract(
        self,
        xbrl: Any,
        facts_df: Any,
        mode: ExtractionMode = ExtractionMode.GAAP
    ) -> StrategyResult:
        """Execute dealer bank debt extraction."""
        ticker = self.params.get('ticker', 'UNKNOWN')

        # 1. Try direct DebtCurrent tag first (cleanest match to yfinance)
        debt_current = FactHelper.get_fact_value(facts_df, 'DebtCurrent')
        if debt_current is not None and debt_current > 0:
            return StrategyResult(
                value=debt_current,
                concept="us-gaap:DebtCurrent",
                method=ExtractionMethod.DIRECT,
                confidence=1.0,
                notes=f"Dealer [{ticker}]: DebtCurrent (yfinance-aligned)",
                metadata={'archetype': 'dealer'}
            )

        # Get CPLTD (always needed)
        cpltd = FactHelper.get_fact_value(facts_df, 'LongTermDebtCurrent') or 0

        # Dealer-specific: UnsecuredShortTermBorrowings (explicitly excludes repos)
        unsecured_stb = FactHelper.get_fact_value_fuzzy(facts_df, 'UnsecuredShortTermBorrowings') or 0

        if unsecured_stb == 0:
            # Fallback to ShortTermBorrowings (dealers usually report clean)
            unsecured_stb = FactHelper.get_fact_value(facts_df, 'ShortTermBorrowings') or 0

        # 10-Q FALLBACK: If still 0, try additional concepts
        if unsecured_stb == 0:
            unsecured_stb = FactHelper.get_fact_value(facts_df, 'DebtCurrent') or 0
            if unsecured_stb > 0:
                logger.debug(f"Dealer [{ticker}]: UnsecuredSTB fallback to DebtCurrent = ${unsecured_stb/1e9:.1f}B")

        if unsecured_stb == 0:
            unsecured_stb = FactHelper.get_fact_value(facts_df, 'OtherShortTermBorrowings') or 0
            if unsecured_stb > 0:
                logger.debug(f"Dealer [{ticker}]: UnsecuredSTB fallback to OtherSTB = ${unsecured_stb/1e9:.1f}B")

        total = unsecured_stb + cpltd

        # Get repos for metadata (dealers have large repos as separate line items)
        repos = self._get_repos_value(facts_df) or 0

        if total > 0:
            return StrategyResult(
                value=total,
                concept=None,
                method=ExtractionMethod.COMPOSITE,
                confidence=0.9,
                notes=f"Dealer [{ticker}]: UnsecuredSTB({unsecured_stb/1e9:.1f}B) + CPLTD({cpltd/1e9:.1f}B)",
                components={
                    'UnsecuredShortTermBorrowings': unsecured_stb,
                    'LongTermDebtCurrent': cpltd,
                },
                metadata={
                    'archetype': 'dealer',
                    'secured_funding_repos': repos,
                    'unsecured_stb': unsecured_stb,
                }
            )

        return StrategyResult(
            value=None,
            concept=None,
            method=ExtractionMethod.DIRECT,
            confidence=0.0,
            notes=f"Dealer [{ticker}]: No valid ShortTermDebt found",
            metadata={
                'archetype': 'dealer',
                'secured_funding_repos': repos,
            }
        )

    def _get_repos_value(self, facts_df: Any) -> Optional[float]:
        """Get repos value for metadata tracking."""
        repos_concepts = [
            'SecuritiesSoldUnderAgreementsToRepurchase',
            'SecuritiesSoldUnderRepurchaseAgreements',
            'RepurchaseAgreements',
        ]

        for concept in repos_concepts:
            val = FactHelper.get_fact_value_fuzzy(facts_df, concept)
            if val is not None and val > 0:
                return val

        return None
