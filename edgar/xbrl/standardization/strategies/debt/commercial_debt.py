"""
Commercial Bank Debt Strategy

Handles ShortTermDebt extraction for commercial banks (WFC, USB, PNC).

Commercial banks bundle repos into ShortTermBorrowings, so we must subtract them.
Uses hybrid bottom-up/top-down approach:
1. TRY Bottom-Up: CP + FHLB + OtherSTB + CPLTD
2. IF Bottom-Up yields $0: Top-Down subtraction (STB - Repos - Trading)
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
class CommercialDebtStrategy(BaseStrategy):
    """
    Commercial Banks (WFC, USB, PNC): Hybrid Bottom-Up/Top-Down.

    Strategy:
    1. TRY Bottom-Up: CP + FHLB + OtherSTB + CPLTD
    2. IF Bottom-Up yields $0: Top-Down subtraction (STB - Repos - Trading)

    Per architect: Commercial banks bundle repos into STB, so we must subtract.

    Parameters:
        subtract_repos_from_stb: Whether repos are bundled (default True)
        subtract_trading_from_stb: Whether trading liabilities bundled (default True)
        safe_fallback: Allow top-down fallback (default True)
    """

    strategy_name = "commercial_debt"
    metric_name = "ShortTermDebt"
    version = "1.0.0"

    def extract(
        self,
        xbrl: Any,
        facts_df: Any,
        mode: ExtractionMode = ExtractionMode.GAAP
    ) -> StrategyResult:
        """Execute commercial bank debt extraction."""
        ticker = self.params.get('ticker', 'UNKNOWN')

        # 1. Try direct DebtCurrent tag first (cleanest match to yfinance)
        debt_current = FactHelper.get_fact_value(facts_df, 'DebtCurrent')
        if debt_current is not None and debt_current > 0:
            return StrategyResult(
                value=debt_current,
                concept="us-gaap:DebtCurrent",
                method=ExtractionMethod.DIRECT,
                confidence=1.0,
                notes=f"Commercial [{ticker}]: DebtCurrent (yfinance-aligned)",
                metadata={'archetype': 'commercial'}
            )

        # Get CPLTD (always needed)
        cpltd = FactHelper.get_fact_value(facts_df, 'LongTermDebtCurrent') or 0

        # WFC-specific: Check for maturity schedule concept
        # WFC reports CPLTD separately from STB using LongTermDebtMaturities concept
        if cpltd == 0:
            maturity_12mo = FactHelper.get_fact_value_fuzzy(
                facts_df,
                'LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths'
            ) or 0
            if maturity_12mo > 0:
                logger.debug(f"Commercial [{ticker}]: Using LongTermDebtMaturities as CPLTD = ${maturity_12mo/1e9:.1f}B")
                cpltd = maturity_12mo

        # === ATTEMPT 1: Bottom-Up Aggregation ===
        cp = FactHelper.get_fact_value(facts_df, 'CommercialPaper') or 0
        fhlb = FactHelper.get_fact_value_fuzzy(facts_df, 'FederalHomeLoanBankAdvances') or 0
        other_stb = FactHelper.get_fact_value(facts_df, 'OtherShortTermBorrowings') or 0

        bottom_up = cp + fhlb + other_stb + cpltd

        if bottom_up > 0:
            components = {}
            if cp > 0:
                components['CommercialPaper'] = cp
            if fhlb > 0:
                components['FederalHomeLoanBankAdvances'] = fhlb
            if other_stb > 0:
                components['OtherShortTermBorrowings'] = other_stb
            if cpltd > 0:
                components['LongTermDebtCurrent'] = cpltd

            return StrategyResult(
                value=bottom_up,
                concept=None,
                method=ExtractionMethod.COMPOSITE,
                confidence=0.9,
                notes=f"Commercial [{ticker}]: Bottom-Up aggregation",
                components=components,
                metadata={'archetype': 'commercial', 'approach': 'bottom_up'}
            )

        # === ATTEMPT 2: Top-Down Subtraction ===
        stb = FactHelper.get_fact_value(facts_df, 'ShortTermBorrowings') or 0

        # 10-Q FALLBACK: If STB is 0, try alternative concepts
        if stb == 0:
            stb = FactHelper.get_fact_value(facts_df, 'DebtCurrent') or 0
            if stb > 0:
                logger.debug(f"Commercial [{ticker}]: STB fallback to DebtCurrent = ${stb/1e9:.1f}B")

        if stb == 0:
            stb = FactHelper.get_fact_value_fuzzy(facts_df, 'ShortTermBorrowings') or 0
            if stb > 0:
                logger.debug(f"Commercial [{ticker}]: STB fallback to fuzzy match = ${stb/1e9:.1f}B")

        if stb > 0:
            # Get repos (prefer pure repos calculation for commercial banks)
            repos = self._get_repos_value(facts_df, prefer_net_in_bs=True) or 0

            # Only subtract trading if it's a consolidated (non-dimensional) value
            trading = FactHelper.get_fact_value_non_dimensional(facts_df, 'TradingLiabilities') or 0
            if trading == 0:
                trading = FactHelper.get_fact_value_non_dimensional(facts_df, 'TradingAccountLiabilities') or 0

            # CONFIG-DRIVEN + BALANCE GUARD
            subtract_repos_config = self.params.get('subtract_repos_from_stb', True)
            subtract_trading_config = self.params.get('subtract_trading_from_stb', True)

            repos_is_bundled = subtract_repos_config
            if repos > 0 and repos > stb:
                # Balance guard: If repos > STB, repos cannot be bundled inside STB
                logger.debug(f"BALANCE GUARD: Repos ({repos/1e9:.1f}B) > STB ({stb/1e9:.1f}B) -> repos NOT bundled")
                repos_is_bundled = False

            # Calculate clean STB
            repos_subtracted = repos if repos_is_bundled else 0
            trading_subtracted = trading if subtract_trading_config and trading < stb else 0
            clean_stb = max(0, stb - repos_subtracted - trading_subtracted)
            total = clean_stb + cpltd

            return StrategyResult(
                value=total,
                concept=None,
                method=ExtractionMethod.COMPOSITE,
                confidence=0.85,
                notes=f"Commercial [{ticker}]: Top-Down STB({stb/1e9:.1f}B) - Repos({repos_subtracted/1e9:.1f}B) - Trading({trading_subtracted/1e9:.1f}B) + CPLTD({cpltd/1e9:.1f}B)",
                components={
                    'ShortTermBorrowings': stb,
                    'ReposSubtracted': repos_subtracted,
                    'TradingSubtracted': trading_subtracted,
                    'LongTermDebtCurrent': cpltd,
                },
                metadata={
                    'archetype': 'commercial',
                    'approach': 'top_down',
                    'secured_funding_repos': repos,
                    'trading_liabilities': trading,
                    'repos_is_bundled': repos_is_bundled,
                    'raw_stb': stb,
                }
            )

        # No valid value found
        return StrategyResult(
            value=None,
            concept=None,
            method=ExtractionMethod.DIRECT,
            confidence=0.0,
            notes=f"Commercial [{ticker}]: No valid ShortTermDebt found",
            metadata={'archetype': 'commercial'}
        )

    def _get_repos_value(self, facts_df: Any, prefer_net_in_bs: bool = False) -> Optional[float]:
        """
        Get repos value using suffix matching (namespace-resilient).

        For commercial banks (WFC), calculate PURE REPOS by subtracting
        securities loaned from combined repos+sec loaned.
        """
        # For commercial banks, prefer pure repos calculation
        if prefer_net_in_bs:
            combined_net = FactHelper.get_fact_value_fuzzy(
                facts_df,
                'SecuritiesSoldUnderAgreementsToRepurchaseAndSecuritiesLoanedNetAmountInConsolidatedBalanceSheet'
            )

            if combined_net is not None and combined_net > 0:
                sec_loaned = FactHelper.get_fact_value_fuzzy(
                    facts_df,
                    'SecuritiesLoanedIncludingNotSubjectToMasterNettingArrangementAndAssetsOtherThanSecuritiesTransferred'
                ) or 0

                pure_repos = combined_net - sec_loaned
                if pure_repos > 0:
                    logger.debug(f"Pure Repos: ${pure_repos/1e9:.1f}B = Combined(${combined_net/1e9:.1f}B) - SecLoaned(${sec_loaned/1e9:.1f}B)")
                    return pure_repos
                else:
                    logger.debug(f"Repos (combined): ${combined_net/1e9:.1f}B")
                    return combined_net

        # Standard repos detection patterns
        repos_concepts = [
            'SecuritiesSoldUnderAgreementsToRepurchase',
            'SecuritiesSoldUnderRepurchaseAgreements',
            'RepurchaseAgreements',
            'SecuritiesSoldUnderRepoAgreements',
            'SecuritiesSoldNotYetPurchased',
        ]

        for concept in repos_concepts:
            val = FactHelper.get_fact_value_fuzzy(facts_df, concept)
            if val is not None and val > 0:
                logger.debug(f"Repos found via {concept}: ${val/1e9:.1f}B")
                return val

        # Fallback: Combined FedFunds + Repos concept
        val = FactHelper.get_fact_value_fuzzy(facts_df, 'FederalFundsPurchasedAndSecuritiesSoldUnderAgreementsToRepurchase')
        if val is not None and val > 0:
            logger.debug(f"Repos found via FedFunds+Repos combined: ${val/1e9:.1f}B")
            return val

        return None

    def _check_cpltd_is_sibling(self, xbrl: Any) -> bool:
        """
        Check if CPLTD is a sibling of STB (should add) or child (already included).

        This uses linkbase analysis to determine the relationship between
        LongTermDebtCurrent and ShortTermBorrowings in the calculation tree.

        Returns:
            True if sibling (ADD to total), False if child (already included in STB).
        """
        if xbrl is None:
            return True  # Default: assume sibling (safer - avoids undercounting)

        try:
            if hasattr(xbrl, 'calculation_trees') and xbrl.calculation_trees:
                for role, tree in xbrl.calculation_trees.items():
                    if 'BalanceSheet' not in role and 'Position' not in role:
                        continue

                    # Find STB node and check children
                    tree_dict = tree if isinstance(tree, dict) else {}
                    for node_key in tree_dict.keys():
                        if str(node_key).endswith('ShortTermBorrowings'):
                            stb_node = tree_dict.get(node_key)
                            if stb_node and hasattr(stb_node, 'children'):
                                for child_id in stb_node.children:
                                    if 'LongTermDebtCurrent' in str(child_id):
                                        logger.debug("CPLTD is CHILD of STB -> skip adding")
                                        return False  # Child, not sibling
        except Exception as e:
            logger.debug(f"Linkbase check failed: {e}")

        return True  # Default: sibling
