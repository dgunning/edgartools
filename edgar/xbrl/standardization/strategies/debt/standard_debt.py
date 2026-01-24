"""
Standard Debt Strategy

Handles ShortTermDebt extraction for non-financial companies.

Standard composite: sum of short-term debt components:
- LongTermDebtCurrent (current portion of long-term debt)
- CommercialPaper
- ShortTermBorrowings
"""

import logging
from typing import Any, Dict

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
class StandardDebtStrategy(BaseStrategy):
    """
    Standard Debt Strategy for non-financial companies.

    Standard composite: sum of short-term debt components:
    - LongTermDebtCurrent (current portion of long-term debt)
    - CommercialPaper
    - ShortTermBorrowings

    This is the default strategy for industrial companies (Archetype A).

    Parameters:
        include_commercial_paper: Include CP in total (default True)
    """

    strategy_name = "standard_debt"
    metric_name = "ShortTermDebt"
    version = "1.0.0"

    def extract(
        self,
        xbrl: Any,
        facts_df: Any,
        mode: ExtractionMode = ExtractionMode.GAAP
    ) -> StrategyResult:
        """Execute standard debt extraction."""
        ticker = self.params.get('ticker', 'UNKNOWN')

        # Try direct DebtCurrent first
        debt_current = FactHelper.get_fact_value(facts_df, 'DebtCurrent')
        if debt_current is not None and debt_current > 0:
            return StrategyResult(
                value=debt_current,
                concept="us-gaap:DebtCurrent",
                method=ExtractionMethod.DIRECT,
                confidence=1.0,
                notes=f"Standard [{ticker}]: DebtCurrent (direct)",
                metadata={'archetype': 'standard'}
            )

        # Standard composite: sum of short-term debt components
        concepts = [
            ('LongTermDebtCurrent', 'us-gaap:LongTermDebtCurrent'),
            ('CommercialPaper', 'us-gaap:CommercialPaper'),
            ('ShortTermBorrowings', 'us-gaap:ShortTermBorrowings'),
        ]

        total = 0.0
        found_any = False
        components = {}
        primary_concept = None

        for name, concept in concepts:
            val = FactHelper.get_fact_value(facts_df, name)
            if val is not None and val > 0:
                total += val
                found_any = True
                components[name] = val
                if primary_concept is None:
                    primary_concept = concept

        if found_any:
            return StrategyResult(
                value=total,
                concept=primary_concept,
                method=ExtractionMethod.COMPOSITE,
                confidence=0.9,
                notes=f"Standard [{ticker}]: Composite sum of {len(components)} components",
                components=components,
                metadata={'archetype': 'standard'}
            )

        # Try short-term notes payable
        notes_payable = FactHelper.get_fact_value(facts_df, 'ShortTermNotesPayable')
        if notes_payable is not None and notes_payable > 0:
            return StrategyResult(
                value=notes_payable,
                concept="us-gaap:ShortTermNotesPayable",
                method=ExtractionMethod.DIRECT,
                confidence=0.8,
                notes=f"Standard [{ticker}]: ShortTermNotesPayable",
                components={'ShortTermNotesPayable': notes_payable},
                metadata={'archetype': 'standard'}
            )

        # Try bank overdrafts
        overdrafts = FactHelper.get_fact_value(facts_df, 'BankOverdrafts')
        if overdrafts is not None and overdrafts > 0:
            return StrategyResult(
                value=overdrafts,
                concept="us-gaap:BankOverdrafts",
                method=ExtractionMethod.DIRECT,
                confidence=0.7,
                notes=f"Standard [{ticker}]: BankOverdrafts",
                components={'BankOverdrafts': overdrafts},
                metadata={'archetype': 'standard'}
            )

        return StrategyResult(
            value=None,
            concept=None,
            method=ExtractionMethod.DIRECT,
            confidence=0.0,
            notes=f"Standard [{ticker}]: No short-term debt found",
            metadata={'archetype': 'standard'}
        )
