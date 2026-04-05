"""
Debt Extraction Strategies

This module provides specialized strategies for extracting short-term debt
across different company archetypes.

Banking Archetypes:
- Commercial (WFC, USB, PNC): Repos bundled in STB, must subtract
- Dealer (GS, MS): Clean UnsecuredSTB tag, repos separate
- Custodial (BK, STT): Component sum only, NEVER fuzzy match
- Hybrid (JPM, BAC, C): Check nesting before subtracting

Standard:
- StandardDebt: For non-financial companies
"""

from .commercial_debt import CommercialDebtStrategy
from .dealer_debt import DealerDebtStrategy
from .custodial_debt import CustodialDebtStrategy
from .hybrid_debt import HybridDebtStrategy
from .standard_debt import StandardDebtStrategy

__all__ = [
    'CommercialDebtStrategy',
    'DealerDebtStrategy',
    'CustodialDebtStrategy',
    'HybridDebtStrategy',
    'StandardDebtStrategy',
]
