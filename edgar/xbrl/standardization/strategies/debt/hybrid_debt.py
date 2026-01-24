"""
Hybrid Bank Debt Strategy

Handles ShortTermDebt extraction for hybrid/universal banks (JPM, BAC, C).

Per Senior Architect directive:
- Ensure we don't double-subtract if filer already reports Repos separately
- Check calculation/presentation linkbase for nesting relationship
- Apply balance guard: If repos > STB, repos cannot be nested inside STB
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
class HybridDebtStrategy(BaseStrategy):
    """
    Hybrid Banks (JPM, BAC, C): Check nesting before subtracting.

    Per Senior Architect directive:
    - Ensure we don't double-subtract if filer already reports Repos separately
    - Check calculation/presentation linkbase for nesting relationship
    - Apply balance guard: If repos > STB, repos cannot be nested inside STB

    Parameters:
        subtract_repos_from_stb: Whether to subtract repos (default False)
        check_nesting: Verify linkbase before subtraction (default True)
        safe_fallback: Allow fallback to other concepts (default True)
    """

    strategy_name = "hybrid_debt"
    metric_name = "ShortTermDebt"
    version = "1.0.0"

    def extract(
        self,
        xbrl: Any,
        facts_df: Any,
        mode: ExtractionMode = ExtractionMode.GAAP
    ) -> StrategyResult:
        """Execute hybrid bank debt extraction."""
        ticker = self.params.get('ticker', 'UNKNOWN')

        # 1. Try direct DebtCurrent tag first (cleanest match to yfinance)
        debt_current = FactHelper.get_fact_value(facts_df, 'DebtCurrent')
        if debt_current is not None and debt_current > 0:
            return StrategyResult(
                value=debt_current,
                concept="us-gaap:DebtCurrent",
                method=ExtractionMethod.DIRECT,
                confidence=1.0,
                notes=f"Hybrid [{ticker}]: DebtCurrent (yfinance-aligned)",
                metadata={'archetype': 'hybrid'}
            )

        # Get CPLTD (always needed)
        cpltd = FactHelper.get_fact_value(facts_df, 'LongTermDebtCurrent') or 0

        stb = FactHelper.get_fact_value(facts_df, 'ShortTermBorrowings') or 0

        # 10-Q FALLBACK: If STB is 0, try alternative concepts
        if stb == 0:
            stb = FactHelper.get_fact_value(facts_df, 'DebtCurrent') or 0
            if stb > 0:
                logger.debug(f"Hybrid [{ticker}]: STB fallback to DebtCurrent = ${stb/1e9:.1f}B")

        if stb == 0:
            stb = FactHelper.get_fact_value_fuzzy(facts_df, 'ShortTermBorrowings') or 0
            if stb > 0:
                logger.debug(f"Hybrid [{ticker}]: STB fallback to fuzzy match = ${stb/1e9:.1f}B")

        if stb == 0:
            stb = FactHelper.get_fact_value(facts_df, 'OtherShortTermBorrowings') or 0
            if stb > 0:
                logger.debug(f"Hybrid [{ticker}]: STB fallback to OtherSTB = ${stb/1e9:.1f}B")

        # Get repos value
        repos = self._get_repos_value(facts_df) or 0

        # CONFIG-DRIVEN subtraction (default: DO NOT subtract)
        # Per debugging: Hybrid banks (JPM, BAC, C) report repos SEPARATELY
        subtract_repos_config = self.params.get('subtract_repos_from_stb', False)
        check_nesting = self.params.get('check_nesting', True)

        # BALANCE GUARD: If repos > STB, repos CANNOT be nested inside STB
        balance_guard_passed = True
        if repos > 0 and stb > 0 and repos > stb:
            logger.debug(f"BALANCE GUARD: Repos ({repos/1e9:.1f}B) > STB ({stb/1e9:.1f}B) -> repos NOT nested")
            balance_guard_passed = False

        # CHECK: Is repos nested inside STB, or is it a separate line item?
        repos_is_nested = False
        if subtract_repos_config and check_nesting and xbrl is not None:
            repos_is_nested = self._is_concept_nested_in_stb(xbrl, 'SecuritiesSoldUnderAgreementsToRepurchase')
            # Apply balance guard as additional check
            repos_is_nested = repos_is_nested and balance_guard_passed

        if repos_is_nested and repos > 0:
            # Repos IS nested AND balance guard passed - we need to subtract
            clean_stb = max(0, stb - repos)
            total = clean_stb + cpltd
            notes = f"Hybrid [{ticker}]: STB({stb/1e9:.1f}B) - Repos({repos/1e9:.1f}B) [nested] + CPLTD({cpltd/1e9:.1f}B)"
        else:
            # Default: Do NOT subtract (repos is separate line item or balance guard failed)
            total = stb + cpltd
            notes = f"Hybrid [{ticker}]: STB({stb/1e9:.1f}B) + CPLTD({cpltd/1e9:.1f}B) [repos separate: {repos/1e9:.1f}B]"

        if total > 0:
            return StrategyResult(
                value=total,
                concept=None,
                method=ExtractionMethod.COMPOSITE,
                confidence=0.9,
                notes=notes,
                components={
                    'ShortTermBorrowings': stb,
                    'LongTermDebtCurrent': cpltd,
                },
                metadata={
                    'archetype': 'hybrid',
                    'secured_funding_repos': repos,
                    'repos_is_nested': repos_is_nested,
                    'balance_guard_passed': balance_guard_passed,
                    'subtract_repos_config': subtract_repos_config,
                    'raw_stb': stb,
                }
            )

        return StrategyResult(
            value=None,
            concept=None,
            method=ExtractionMethod.DIRECT,
            confidence=0.0,
            notes=f"Hybrid [{ticker}]: No valid ShortTermDebt found",
            metadata={'archetype': 'hybrid'}
        )

    def _get_repos_value(self, facts_df: Any) -> Optional[float]:
        """Get repos value using suffix matching."""
        repos_concepts = [
            'SecuritiesSoldUnderAgreementsToRepurchase',
            'SecuritiesSoldUnderRepurchaseAgreements',
            'RepurchaseAgreements',
        ]

        for concept in repos_concepts:
            val = FactHelper.get_fact_value_fuzzy(facts_df, concept)
            if val is not None and val > 0:
                logger.debug(f"Repos found via {concept}: ${val/1e9:.1f}B")
                return val

        # Fallback: Combined FedFunds + Repos concept
        val = FactHelper.get_fact_value_fuzzy(facts_df, 'FederalFundsPurchasedAndSecuritiesSoldUnderAgreementsToRepurchase')
        if val is not None and val > 0:
            return val

        return None

    def _is_concept_nested_in_stb(self, xbrl: Any, concept: str) -> bool:
        """
        Dual-Check Strategy with SUFFIX MATCHING for namespace resilience.

        Check Order:
        1. Calculation Linkbase - definitive parent/child with weight
        2. Presentation Linkbase - visual indentation implies summation
        3. Default: Assume SIBLING (Do Not Subtract)

        Returns True if concept is a CHILD of STB (should be subtracted).
        Returns False if concept is a SIBLING (should NOT be subtracted).
        """
        # Extract suffix for namespace-resilient matching
        concept_suffix = concept.split(':')[-1] if ':' in concept else concept
        concept_suffix = concept_suffix.replace('us-gaap_', '')

        # --- CHECK 1: Calculation Linkbase ---
        try:
            if hasattr(xbrl, 'calculation_trees') and xbrl.calculation_trees:
                calc_trees = xbrl.calculation_trees
                for role, tree in calc_trees.items():
                    # Only check balance sheet roles
                    if 'BalanceSheet' not in role and 'Position' not in role:
                        continue

                    # Find STB node using suffix matching
                    stb_node = None
                    for node_key in tree.keys() if hasattr(tree, 'keys') else []:
                        node_str = str(node_key)
                        if node_str.endswith('ShortTermBorrowings'):
                            stb_node = tree.get(node_key)
                            break

                    if stb_node and hasattr(stb_node, 'children'):
                        # Check if concept is in STB's children using SUFFIX matching
                        for child_id in stb_node.children:
                            child_str = str(child_id)
                            if child_str.endswith(concept_suffix):
                                logger.debug(f"CALC LINKBASE: {concept} IS child of STB -> SUBTRACT")
                                return True

                        # Check if concept is sibling
                        if hasattr(stb_node, 'parent') and stb_node.parent:
                            parent_node = tree.get(stb_node.parent)
                            if parent_node and hasattr(parent_node, 'children'):
                                for sibling_id in parent_node.children:
                                    sibling_str = str(sibling_id)
                                    if sibling_str.endswith(concept_suffix):
                                        logger.debug(f"CALC LINKBASE: {concept} IS sibling of STB -> DO NOT SUBTRACT")
                                        return False
        except Exception as e:
            logger.debug(f"Calculation linkbase check failed: {e}")

        # --- CHECK 2: Presentation Linkbase ---
        try:
            if hasattr(xbrl, 'presentation_trees') and xbrl.presentation_trees:
                pres_trees = xbrl.presentation_trees
                for role, tree in pres_trees.items():
                    if 'BalanceSheet' not in role and 'Position' not in role:
                        continue

                    stb_node = None
                    for node_key in tree.keys() if hasattr(tree, 'keys') else []:
                        node_str = str(node_key)
                        if node_str.endswith('ShortTermBorrowings'):
                            stb_node = tree.get(node_key)
                            break

                    if stb_node and hasattr(stb_node, 'children'):
                        for child_id in stb_node.children:
                            child_str = str(child_id)
                            if child_str.endswith(concept_suffix):
                                logger.debug(f"PRES LINKBASE: {concept} IS indented under STB -> SUBTRACT")
                                return True
        except Exception as e:
            logger.debug(f"Presentation linkbase check failed: {e}")

        # --- DEFAULT: Assume SIBLING ---
        logger.debug(f"DEFAULT: {concept} not found nested in STB linkbases -> DO NOT SUBTRACT")
        return False
