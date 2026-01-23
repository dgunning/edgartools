"""
Industry-Aware Metric Extraction Logic

This module provides sector-specific extraction strategies for financial metrics
that have different meanings across industries.

Key Concepts:
- Banking: COGS → InterestExpense, OperatingIncome → PPNR
- Insurance: COGS → LossesAndAdjustments, OperatingIncome → UnderwritingIncome
- REITs: COGS → PropertyOperatingExpenses, OperatingIncome → NOI

Usage:
    from edgar.xbrl.standardization.industry_logic import get_industry_extractor
    extractor = get_industry_extractor(ticker)
    value = extractor.extract_metric(xbrl, 'ShortTermDebt')
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class ExtractionMethod(Enum):
    DIRECT = "direct"          # Single concept lookup
    COMPOSITE = "composite"    # Sum of multiple concepts
    CALCULATED = "calculated"  # Derived from other metrics
    MAPPED = "mapped"          # Industry counterpart mapping


# =============================================================================
# ARCHETYPE EXTRACTION RULES
# =============================================================================
# Per Senior Architect directive: Deterministic archetype-based extraction rules
# These define HOW to extract ShortTermDebt for each bank archetype
#
# Archetypes:
#   - commercial: WFC, USB, PNC - traditional banks, repos bundled into STB
#   - dealer: GS, MS - investment banks, repos as separate line items
#   - custodial: BK, STT - custody banks, minimal STB, return None rather than fuzzy
#   - hybrid: JPM, BAC, C - universal banks, check nesting before subtracting
#   - regional: Smaller banks (SIC 6022) - fallback to commercial rules
# =============================================================================

ARCHETYPE_EXTRACTION_RULES = {
    'commercial': {
        # WFC, USB, PNC - traditional banks
        'repos_treatment': 'exclude_from_stb',      # Repos are NOT operating debt
        'trading_treatment': 'exclude_from_stb',    # Trading liabilities are NOT debt
        'extraction_strategy': 'hybrid',            # Try bottom-up, fall back to top-down
        'formula': 'STB - Repos - TradingLiab + CPLTD',
        'safe_fallback': True,                      # Allow top-down fallback
    },
    'dealer': {
        # GS, MS - investment banks
        'repos_treatment': 'separate_line_item',    # Repos already separate
        'trading_treatment': 'separate_line_item',
        'extraction_strategy': 'direct',            # Use UnsecuredSTB directly
        'formula': 'UnsecuredSTB + CPLTD',
        'safe_fallback': True,
    },
    'custodial': {
        # BK, STT - custody banks
        'repos_treatment': 'include_as_debt',       # Repos ARE financing for custody ops
        'trading_treatment': 'exclude',
        'extraction_strategy': 'component_sum',     # Sum specific components only
        'formula': 'OtherSTB + FedFundsPurchased + CPLTD',
        'safe_fallback': False,                     # NEVER fall back to fuzzy match!
    },
    'hybrid': {
        # JPM, BAC, C - universal banks
        'repos_treatment': 'check_nesting_first',   # Check if already separated
        'trading_treatment': 'separate_line_item',
        'extraction_strategy': 'direct',            # No subtraction unless confirmed nested
        'formula': 'STB + CPLTD (no subtraction)',
        'safe_fallback': True,
    },
    'regional': {
        # Smaller banks (SIC 6022) - fallback to commercial rules
        'repos_treatment': 'exclude_from_stb',
        'trading_treatment': 'exclude_from_stb',
        'extraction_strategy': 'hybrid',
        'formula': 'Commercial rules (default)',
        'safe_fallback': True,
    },
}


@dataclass
class ExtractedMetric:
    """Result of metric extraction with full context."""
    standard_name: str              # e.g., "COGS"
    industry_counterpart: Optional[str]  # e.g., "InterestExpense" for banks
    xbrl_concept: Optional[str]     # e.g., "us-gaap:InterestExpense"
    value: Optional[float]
    extraction_method: ExtractionMethod
    notes: Optional[str] = None
    # Per Senior Architect directive: Store supplemental data (repos, trading liab, archetype)
    # Don't discard data - store it for future analysis
    metadata: Optional[Dict[str, Any]] = field(default=None)


class IndustryExtractor(ABC):
    """Base class for industry-specific metric extraction."""
    
    industry_name: str = "default"
    
    @abstractmethod
    def extract_short_term_debt(self, xbrl, facts_df) -> ExtractedMetric:
        """Extract ShortTermDebt with industry-specific logic."""
        pass
    
    @abstractmethod
    def extract_capex(self, xbrl, facts_df) -> ExtractedMetric:
        """Extract Capex with industry-specific logic."""
        pass
    
    @abstractmethod
    def extract_operating_income(self, xbrl, facts_df) -> ExtractedMetric:
        """Extract OperatingIncome with industry-specific logic."""
        pass

    def validate_accounting_identity(self, xbrl, facts_df, reported_op_income: float) -> Optional[str]:
        """
        Validate the accounting identity: Revenue - Expenses == Operating Income.
        
        This is a powerful guardrail against "Impossible Data".
        If Constructed OpIncome significantly deviates from Reported OpIncome,
        it suggests a unit error, definition mismatch, or major non-GAAP adjustment.
        
        Args:
            reported_op_income: The value extracted by extract_operating_income()
            
        Returns:
            Warning string if identity fails, None otherwise.
        """
        # Default implementation (override in subclasses for sector specifics)
        revenue = (
            self._get_fact_value(facts_df, 'Revenues') or 
            self._get_fact_value(facts_df, 'SalesRevenueNet') or 0
        )
        
        costs = (
            self._get_fact_value(facts_df, 'CostOfGoodsAndServicesSold') or
            self._get_fact_value(facts_df, 'CostOfRevenue') or 0
        )
        
        opex = self._get_fact_value(facts_df, 'OperatingExpenses') or 0
        
        # If we have GrossProfit, use it (more reliable than Rev - Cost)
        gross_profit = self._get_fact_value(facts_df, 'GrossProfit')
        
        constructed = 0.0
        if gross_profit is not None and opex > 0:
            # Note: OperatingExpenses usually includes COGS if not separate, 
            # but if GrossProfit exists, OpEx is usually SGA+R&D.
            # Standard identity: GP - OpEx
            constructed = gross_profit - (opex - costs) # Adjust if OpEx includes Costs
            # Simplified: GP - (SGA + R&D)
            sga = self._get_fact_value(facts_df, 'SellingGeneralAndAdministrativeExpense') or 0
            rnd = self._get_fact_value(facts_df, 'ResearchAndDevelopmentExpense') or 0
            if sga > 0:
                 constructed = gross_profit - sga - rnd
        elif revenue > 0 and costs > 0:
             constructed = revenue - costs - (opex - costs) # Rough approximation
        
        # Base implementation is weak - rely on subclasses for robust checks
        return None

    def _get_fact_value(self, df, concept: str, target_period_days: int = None) -> Optional[float]:
        """
        Get the consolidated (non-dimensional) value for a concept from the appropriate period.
        
        Key logic:
        1. Match exact concept name (handle namespace prefix)
        2. Filter out dimensional values (keep only totals)
        3. Filter by target period duration if specified
        4. Select the most recent period
        5. For same period, prefer single value without dimensions
        
        Args:
            df: DataFrame of facts
            concept: XBRL concept name
            target_period_days: Optional. Target period duration (90 for quarterly, 365 for annual).
                               If None, uses most recent period without duration filtering.
        """
        if df is None or len(df) == 0:
            return None
        
        # Match exact concept (case-insensitive, handle namespace prefix)
        concept_lower = concept.lower()
        matches = df[
            df['concept'].str.replace('us-gaap:', '', regex=False).str.lower() == concept_lower
        ]
        
        if len(matches) == 0:
            # Try with namespace
            matches = df[df['concept'].str.lower() == f'us-gaap:{concept_lower}']
            
        if len(matches) == 0:
            return None
        
        # Filter for non-dimensional (total) values only
        # Check multiple dimension indicator columns
        non_dim = matches.copy()
        
        # Filter by full_dimension_label
        if 'full_dimension_label' in non_dim.columns:
            non_dim = non_dim[non_dim['full_dimension_label'].isna() | (non_dim['full_dimension_label'] == '')]
        
        # Filter by dimension_label  
        if 'dimension_label' in non_dim.columns and len(non_dim) > 1:
            subset = non_dim[non_dim['dimension_label'].isna() | (non_dim['dimension_label'] == '')]
            if len(subset) > 0:
                non_dim = subset
        
        # Filter by segment_label
        if 'segment_label' in non_dim.columns and len(non_dim) > 1:
            subset = non_dim[non_dim['segment_label'].isna() | (non_dim['segment_label'] == '')]
            if len(subset) > 0:
                non_dim = subset
        
        if len(non_dim) == 0:
            # If all values have dimensions, fall back to original matches
            non_dim = matches
        
        # Get numeric values only
        if 'numeric_value' not in non_dim.columns:
            return None
        
        numeric_df = non_dim[non_dim['numeric_value'].notna()]
        if len(numeric_df) == 0:
            return None
        
        # PERIOD FILTERING: Filter by target duration if specified
        if target_period_days and 'period_key' in numeric_df.columns:
            duration_mask = numeric_df['period_key'].str.startswith('duration_')
            if duration_mask.any():
                duration_rows = numeric_df[duration_mask].copy()
                duration_rows['period_days'] = duration_rows['period_key'].apply(
                    self._calculate_period_days
                )
                # 30-day tolerance band for period matching
                filtered = duration_rows[
                    (duration_rows['period_days'] >= target_period_days - 30) & 
                    (duration_rows['period_days'] <= target_period_days + 30)
                ]
                if len(filtered) > 0:
                    numeric_df = filtered
                else:
                    # Strict filtering: If target days specified but no match, return None
                    # This prevents 10-Q failing back to YTD (9mo) when we wanted Q (3mo)
                    return None
        
        # Sort by period to get most recent
        if 'period_key' in numeric_df.columns:
            numeric_df = numeric_df.sort_values('period_key', ascending=False)
        
        # Return first value (most recent period, non-dimensional)
        val = numeric_df.iloc[0]['numeric_value']
        return float(val) if val is not None else None
    
    def _calculate_period_days(self, period_key: str) -> int:
        """Calculate days in a period from period_key like 'duration_2024-01-01_2024-12-31'."""
        try:
            if not period_key.startswith('duration_'):
                return 0
            parts = period_key.replace('duration_', '').split('_')
            if len(parts) == 2:
                from datetime import datetime
                start = datetime.strptime(parts[0], '%Y-%m-%d')
                end = datetime.strptime(parts[1], '%Y-%m-%d')
                return (end - start).days
        except Exception:
            pass
        return 0
    
    def _construct_net_metric(self, facts_df, structure: Dict) -> Optional[float]:
        """
        Constructs a metric by summing 'add' components and subtracting 'deduct' components.
        
        This enables arithmetic construction patterns like:
        - WFC: ShortTermBorrowings - Repos = Net Financial Debt
        - Citi: CP + LT Current + FHLB = Total Short-Term Debt
        
        Args:
            facts_df: DataFrame of XBRL facts
            structure: {'add': [concepts...], 'deduct': [concepts...]}
        
        Returns:
            Net calculated value, or None if no components found
        """
        total = 0.0
        found_any = False
        
        # Summation Logic (Fixes Citi-style composite)
        for concept in structure.get('add', []):
            val = self._get_fact_value(facts_df, concept)
            if val is not None:
                total += val
                found_any = True
        
        # Subtraction Logic (Fixes WFC-style exclusion)
        # Use fuzzy matching for deduct because banks use company-extension prefixes
        for concept in structure.get('deduct', []):
            # First try exact match
            val = self._get_fact_value(facts_df, concept)
            if val is None:
                # Try fuzzy match (handles wfc:, jpm:, bac: company extensions)
                val = self._get_fact_value_fuzzy(facts_df, concept)
            if val is not None:
                total -= val
                found_any = True
        
        return total if found_any else None
    
    def _get_fact_value_fuzzy(self, df, concept_pattern: str) -> Optional[float]:
        """
        Get fact value using fuzzy/suffix matching.
        
        Banks often use company-extension prefixes (wfc:, jpm:, bac:) for
        concepts that should theoretically be us-gaap. This method searches
        by concept suffix pattern (case-insensitive contains).
        
        Example: "SecuritiesSoldUnderAgreementsToRepurchase" matches:
        - us-gaap:SecuritiesSoldUnderAgreementsToRepurchase
        - wfc:SecuritiesSoldUnderAgreementsToRepurchaseAtFairValue
        """
        if df is None or len(df) == 0:
            return None
        
        # Search by suffix pattern (case-insensitive)
        pattern_lower = concept_pattern.lower()
        matches = df[df['concept'].str.lower().str.contains(pattern_lower, regex=False, na=False)]
        
        if len(matches) == 0:
            return None
        
        # Filter for non-dimensional (total) values only
        non_dim = matches.copy()
        if 'full_dimension_label' in non_dim.columns:
            subset = non_dim[non_dim['full_dimension_label'].isna() | (non_dim['full_dimension_label'] == '')]
            if len(subset) > 0:
                non_dim = subset
        
        # Get numeric values only
        if 'numeric_value' not in non_dim.columns:
            return None
        
        numeric_df = non_dim[non_dim['numeric_value'].notna()]
        if len(numeric_df) == 0:
            return None
        
        # Sort by period to get most recent
        if 'period_key' in numeric_df.columns:
            numeric_df = numeric_df.sort_values('period_key', ascending=False)
        
        val = numeric_df.iloc[0]['numeric_value']
        return float(val) if val is not None else None


class DefaultExtractor(IndustryExtractor):
    """Default extraction logic for standard C&I companies."""
    
    industry_name = "default"
    
    def extract_short_term_debt(self, xbrl, facts_df) -> ExtractedMetric:
        # Standard composite: sum of short-term debt components
        concepts = [
            ('LongTermDebtCurrent', 'us-gaap:LongTermDebtCurrent'),
            ('CommercialPaper', 'us-gaap:CommercialPaper'),
            ('ShortTermBorrowings', 'us-gaap:ShortTermBorrowings'),
        ]
        
        total = 0.0
        found_any = False
        used_concept = None
        
        for name, concept in concepts:
            val = self._get_fact_value(facts_df, name)
            if val is not None:
                total += val
                found_any = True
                if used_concept is None:
                    used_concept = concept
        
        return ExtractedMetric(
            standard_name="ShortTermDebt",
            industry_counterpart=None,
            xbrl_concept=used_concept,
            value=total if found_any else None,
            extraction_method=ExtractionMethod.COMPOSITE
        )
    
    def extract_capex(self, xbrl, facts_df) -> ExtractedMetric:
        # Standard Capex: PPE + Intangibles
        ppe = self._get_fact_value(facts_df, 'PaymentsToAcquirePropertyPlantAndEquipment')
        intangibles = self._get_fact_value(facts_df, 'PaymentsToAcquireIntangibleAssets')
        software = self._get_fact_value(facts_df, 'PaymentsToDevelopSoftware')
        
        total = 0.0
        found_any = False
        
        if ppe is not None:
            total += ppe
            found_any = True
        if intangibles is not None:
            total += intangibles
            found_any = True
        if software is not None:
            total += software
            found_any = True
        
        return ExtractedMetric(
            standard_name="Capex",
            industry_counterpart=None,
            xbrl_concept="us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
            value=total if found_any else None,
            extraction_method=ExtractionMethod.COMPOSITE,
            notes="Includes intangibles and software" if (intangibles or software) else None
        )
    
    def extract_operating_income(self, xbrl, facts_df) -> ExtractedMetric:
        # Try direct tag first
        val = self._get_fact_value(facts_df, 'OperatingIncomeLoss')
        if val is not None:
            return ExtractedMetric(
                standard_name="OperatingIncome",
                industry_counterpart=None,
                xbrl_concept="us-gaap:OperatingIncomeLoss",
                value=val,
                extraction_method=ExtractionMethod.DIRECT
            )
        
        # Get component values (with abs() safety for expenses)
        gross_profit = self._get_fact_value(facts_df, 'GrossProfit')
        
        # R&D expense - try multiple variants (pharma uses different tags)
        rd = (
            self._get_fact_value(facts_df, 'ResearchAndDevelopmentExpense') or
            self._get_fact_value(facts_df, 'ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost') or
            self._get_fact_value(facts_df, 'ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost')
        )
        
        sga = self._get_fact_value(facts_df, 'SellingGeneralAndAdministrativeExpense')
        op_expenses = self._get_fact_value(facts_df, 'OperatingExpenses')
        
        # Normalize expense values (they should be positive for subtraction)
        rd_val = abs(rd) if rd is not None else 0
        sga_val = abs(sga) if sga is not None else 0
        op_exp_val = abs(op_expenses) if op_expenses is not None else 0
        
        # Fallback 1: GrossProfit - OperatingExpenses (most direct if available)
        if gross_profit is not None and op_expenses is not None:
            calculated = gross_profit - op_exp_val
            return ExtractedMetric(
                standard_name="OperatingIncome",
                industry_counterpart=None,
                xbrl_concept=None,
                value=calculated,
                extraction_method=ExtractionMethod.CALCULATED,
                notes="Calculated: GrossProfit - OperatingExpenses"
            )
        
        # Fallback 2: GrossProfit - SGA - R&D (yfinance formula)
        # IMPORTANT: yfinance OpIncome = GrossProfit - R&D - SGA (NO D&A!)
        # Verified: NKE 19.79 - 16.09 = 3.70B exactly
        if gross_profit is not None and (rd is not None or sga is not None):
            calculated = gross_profit - rd_val - sga_val
            return ExtractedMetric(
                standard_name="OperatingIncome",
                industry_counterpart=None,
                xbrl_concept=None,
                value=calculated,
                extraction_method=ExtractionMethod.CALCULATED,
                notes="Calculated: GrossProfit - R&D - SGA (yfinance formula)"
            )
        
        # Fallback 3: Revenue - COGS - R&D - SGA (when no GrossProfit tag)
        revenue = (
            self._get_fact_value(facts_df, 'Revenues') or
            self._get_fact_value(facts_df, 'SalesRevenueNet') or
            self._get_fact_value(facts_df, 'SalesRevenueServicesNet') or
            self._get_fact_value(facts_df, 'RevenueFromContractWithCustomerExcludingAssessedTax')
        )
        
        cogs = (
            self._get_fact_value(facts_df, 'CostOfGoodsAndServicesSold') or
            self._get_fact_value(facts_df, 'CostOfRevenue') or
            self._get_fact_value(facts_df, 'CostOfSales')
        )
        cogs_val = abs(cogs) if cogs is not None else 0
        
        if revenue is not None and cogs is not None:
            calculated = revenue - cogs_val - rd_val - sga_val
            return ExtractedMetric(
                standard_name="OperatingIncome",
                industry_counterpart=None,
                xbrl_concept=None,
                value=calculated,
                extraction_method=ExtractionMethod.CALCULATED,
                notes="Calculated: Revenue - COGS - R&D - SGA"
            )
        
        return ExtractedMetric(
            standard_name="OperatingIncome",
            industry_counterpart=None,
            xbrl_concept=None,
            value=None,
            extraction_method=ExtractionMethod.DIRECT
        )


class BankingExtractor(IndustryExtractor):
    """Banking-specific extraction logic."""

    industry_name = "banking"

    def _get_company_config(self, ticker: str) -> Optional[Dict]:
        """
        Get company-specific configuration from companies.yaml.

        Returns the full company config dict if found, None otherwise.
        """
        try:
            import yaml
            from pathlib import Path

            config_path = Path(__file__).parent.parent / 'config' / 'companies.yaml'
            if config_path.exists():
                with open(config_path) as f:
                    config = yaml.safe_load(f)
                    companies = config.get('companies', {})
                    return companies.get(ticker.upper())
        except Exception:
            pass
        return None

    def _get_archetype(self, facts_df, ticker: str = None) -> str:
        """
        Get bank archetype from config (preferred) or dynamic detection (fallback).

        Archetype hierarchy (per Principal Architect Directive #3):
        1. Config override (archetype_override: true) - deterministic
        2. Dynamic detection based on balance sheet ratios - probabilistic

        Returns:
            str: 'commercial', 'dealer', 'custodial', or 'hybrid'
        """
        import logging
        logger = logging.getLogger(__name__)

        if ticker:
            config = self._get_company_config(ticker)
            if config and config.get('archetype_override', False):
                archetype = config.get('bank_archetype', 'commercial')
                logger.debug(f"{ticker} archetype from config: {archetype}")
                return archetype

        # Fallback to dynamic detection
        return self._detect_bank_archetype(facts_df)

    def _get_extraction_rules(self, ticker: str) -> Dict:
        """
        Get company-specific extraction rules from config.

        Returns dict of rules like:
        - subtract_repos_from_stb: bool
        - cash_includes_ib_deposits: bool
        - street_debt_includes_net_repos: bool
        """
        config = self._get_company_config(ticker)
        if config:
            return config.get('extraction_rules', {})
        return {}

    def _is_concept_nested_in_stb(self, xbrl, concept: str) -> bool:
        """
        Dual-Check Strategy with SUFFIX MATCHING for namespace resilience.

        Per Senior Architect directive:
        - Use endswith() matching to catch wfc:, jpm:, bac: extensions
        - Do NOT rely on exact QName matching

        Check Order:
        1. Calculation Linkbase - definitive parent/child with weight
        2. Presentation Linkbase - visual indentation implies summation
        3. Default: Assume SIBLING (Do Not Subtract)

        Returns True if concept is a CHILD of STB (should be subtracted).
        Returns False if concept is a SIBLING (should NOT be subtracted).
        """
        import logging
        logger = logging.getLogger(__name__)

        # Extract suffix for namespace-resilient matching
        # e.g., "us-gaap:SecuritiesSoldUnderAgreementsToRepurchase" -> "SecuritiesSoldUnderAgreementsToRepurchase"
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
                            # Suffix match: catches wfc:SecuritiesSold..., us-gaap:SecuritiesSold...
                            if child_str.endswith(concept_suffix):
                                logger.debug(f"CALC LINKBASE: {concept} IS child of STB (suffix match) -> SUBTRACT")
                                return True

                        # Check if concept is sibling (both under same parent)
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
                    # Only check balance sheet/position roles
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
                        # Check if concept appears indented under STB using SUFFIX matching
                        for child_id in stb_node.children:
                            child_str = str(child_id)
                            if child_str.endswith(concept_suffix):
                                logger.debug(f"PRES LINKBASE: {concept} IS indented under STB (suffix match) -> SUBTRACT")
                                return True
        except Exception as e:
            logger.debug(f"Presentation linkbase check failed: {e}")

        # --- DEFAULT: Assume SIBLING ---
        logger.debug(f"DEFAULT: {concept} not found nested in STB linkbases -> DO NOT SUBTRACT")
        return False

    def _get_repos_value(self, facts_df) -> Optional[float]:
        """
        Get repos value using suffix matching (namespace-resilient).

        Per Senior Architect directive:
        - Catches: us-gaap:, wfc:, jpm:, bac:, gs: prefixed repos concepts
        - Uses fuzzy matching to handle company-extension namespaces

        Returns:
            Repos value if found, None otherwise
        """
        # Primary: Suffix match on SecuritiesSoldUnderAgreementsToRepurchase
        val = self._get_fact_value_fuzzy(facts_df, 'SecuritiesSoldUnderAgreementsToRepurchase')
        if val is not None and val > 0:
            return val

        # Fallback: Combined FedFunds + Repos concept
        val = self._get_fact_value_fuzzy(facts_df, 'FederalFundsPurchasedAndSecuritiesSoldUnderAgreementsToRepurchase')
        if val is not None and val > 0:
            return val

        # Fallback: Try exact us-gaap match
        val = self._get_fact_value(facts_df, 'SecuritiesSoldUnderAgreementsToRepurchase')
        return val

    def _get_dimensional_sum(self, facts_df, concept: str, axis: str = None) -> Optional[float]:
        """
        Sum dimensional facts for a concept when consolidated value is missing or suspect.

        Per Principal Architect Directive #4, this handles cases like STT where
        ShortTermBorrowings is only reported with dimensional breakdown (ShortTermDebtTypeAxis).

        Constraints:
        - Only use if consolidated value is missing OR < 50% of dimensional sum
        - Filter to balance sheet period only
        - Log full dimension breakdown for audit

        Args:
            facts_df: Facts dataframe
            concept: The concept to sum (e.g., 'ShortTermBorrowings')
            axis: Optional axis to filter by (e.g., 'ShortTermDebtTypeAxis')

        Returns:
            Sum of dimensional values, or None if not available
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            if facts_df is None or len(facts_df) == 0:
                return None

            # Normalize concept name for matching
            concept_lower = concept.lower()

            # Find dimensional facts for concept
            concept_facts = facts_df[
                facts_df['concept'].str.replace('us-gaap:', '', regex=False).str.lower() == concept_lower
            ].copy()

            if len(concept_facts) == 0:
                # Try with namespace
                concept_facts = facts_df[
                    facts_df['concept'].str.lower() == f'us-gaap:{concept_lower}'
                ].copy()

            if len(concept_facts) == 0:
                return None

            # Filter to dimensional facts only
            if 'full_dimension_label' not in concept_facts.columns:
                return None

            dim_facts = concept_facts[concept_facts['full_dimension_label'].notna()]

            if len(dim_facts) == 0:
                return None

            # Filter by axis if specified
            if axis:
                # Look for the axis in dimension columns or labels
                axis_lower = axis.lower()
                has_axis = dim_facts['full_dimension_label'].str.lower().str.contains(axis_lower, na=False)
                if has_axis.any():
                    dim_facts = dim_facts[has_axis]

            # Filter to latest period (balance sheet point-in-time)
            if 'period_key' in dim_facts.columns:
                # Prefer instant periods for balance sheet items
                instant_facts = dim_facts[dim_facts['period_key'].str.startswith('instant_')]
                if len(instant_facts) > 0:
                    latest_period = instant_facts['period_key'].max()
                    dim_facts = dim_facts[dim_facts['period_key'] == latest_period]
                else:
                    # Fall back to latest period overall
                    latest_period = dim_facts['period_key'].max()
                    dim_facts = dim_facts[dim_facts['period_key'] == latest_period]

            # Get numeric values
            if 'numeric_value' not in dim_facts.columns:
                return None

            dim_facts = dim_facts[dim_facts['numeric_value'].notna()]

            if len(dim_facts) == 0:
                return None

            # Sum numeric values
            dim_sum = dim_facts['numeric_value'].sum()

            # Log breakdown for audit
            logger.debug(f"Dimensional sum for {concept}: ${dim_sum/1e9:.2f}B")
            for _, row in dim_facts.iterrows():
                dim_label = row.get('full_dimension_label', 'unknown')
                val = row['numeric_value']
                logger.debug(f"  {dim_label}: ${val/1e9:.2f}B")

            return float(dim_sum) if dim_sum > 0 else None

        except Exception as e:
            logger.debug(f"Dimensional fallback failed for {concept}: {e}")
            return None

    def _should_use_dimensional_fallback(self, consolidated: Optional[float], dim_sum: Optional[float]) -> bool:
        """
        Determine if dimensional sum should override consolidated value.

        Per Principal Architect Directive #4, use dimensional if:
        - Consolidated is None/0, OR
        - Consolidated < 50% of dimensional sum (indicates missing components)

        Args:
            consolidated: The consolidated (non-dimensional) value
            dim_sum: The sum of dimensional values

        Returns:
            True if dimensional sum should be used instead
        """
        import logging
        logger = logging.getLogger(__name__)

        if consolidated is None or consolidated == 0:
            if dim_sum is not None and dim_sum > 0:
                logger.debug(f"Dimensional override: consolidated is None/0, using dim_sum ${dim_sum/1e9:.2f}B")
                return True
            return False

        if dim_sum is not None and dim_sum > 0:
            # If consolidated is less than 50% of dimensional sum, something is missing
            if consolidated < (dim_sum * 0.5):
                logger.debug(f"Dimensional override: consolidated ${consolidated/1e9:.2f}B < 50% of dim ${dim_sum/1e9:.2f}B")
                return True

        return False

    def extract_short_term_debt(self, xbrl, facts_df, mode: str = 'street', ticker: str = None) -> ExtractedMetric:
        """
        Bank ShortTermDebt extraction with mode selection.

        Dual-Track Architecture:
        - 'gaap': GAAP-aligned extraction for yfinance validation (reproduces their values)
        - 'street': Street View extraction for database (economic leverage, default)

        Args:
            xbrl: XBRL object
            facts_df: DataFrame of XBRL facts
            mode: 'gaap' for yfinance validation, 'street' for database (default)
            ticker: Optional ticker for config-based archetype lookup

        Returns:
            ExtractedMetric with appropriate extraction method
        """
        if mode == 'gaap':
            return self.extract_short_term_debt_gaap(xbrl, facts_df, ticker=ticker)
        else:
            return self.extract_street_debt(xbrl, facts_df, ticker=ticker)

    def extract_short_term_debt_gaap(self, xbrl, facts_df, ticker: str = None) -> ExtractedMetric:
        """
        GAAP-aligned ShortTermDebt extraction using Archetype-Driven Waterfall.

        Per Senior Architect directive:
        Waterfall by Archetype:
        1. Commercial: Try Bottom-Up → Fall back to Top-Down
        2. Custodial: Component Sum only → Return None if missing (NEVER fuzzy)
        3. Dealer: Direct UnsecuredSTB
        4. Hybrid: Check nesting before subtracting

        Args:
            xbrl: XBRL object for linkbase checks
            facts_df: DataFrame of XBRL facts
            ticker: Optional ticker for config-based archetype lookup

        Returns:
            ExtractedMetric with GAAP-aligned value and extraction notes
        """
        # 1. Try direct DebtCurrent tag first (cleanest match to yfinance "Current Debt")
        debt_current = self._get_fact_value(facts_df, 'DebtCurrent')
        if debt_current is not None and debt_current > 0:
            return ExtractedMetric(
                standard_name="ShortTermDebt",
                industry_counterpart="DebtCurrent_GAAP",
                xbrl_concept="us-gaap:DebtCurrent",
                value=debt_current,
                extraction_method=ExtractionMethod.DIRECT,
                notes="Bank GAAP: DebtCurrent (yfinance-aligned)"
            )

        # Get archetype and rules
        archetype = self._get_archetype(facts_df, ticker)
        rules = ARCHETYPE_EXTRACTION_RULES.get(archetype, ARCHETYPE_EXTRACTION_RULES['commercial'])

        # Get CPLTD (always needed across all archetypes)
        # STRICT: Only use balance sheet classification, NOT maturity schedule
        cpltd = self._get_fact_value(facts_df, 'LongTermDebtCurrent') or 0

        # === STRATEGY DISPATCH ===
        if archetype == 'custodial':
            return self._extract_custodial_stb(facts_df, cpltd, ticker, rules)

        elif archetype == 'dealer':
            return self._extract_dealer_stb(facts_df, cpltd, ticker, rules)

        elif archetype == 'hybrid':
            return self._extract_hybrid_stb(xbrl, facts_df, cpltd, ticker, rules)

        else:  # commercial or regional (default)
            return self._extract_commercial_stb(xbrl, facts_df, cpltd, ticker, rules)

    def _extract_custodial_stb(self, facts_df, cpltd: float, ticker: str, rules: dict) -> ExtractedMetric:
        """
        Custodial Banks (STT, BK): Component Sum ONLY.

        Per Senior Architect directive:
        - If components missing, return None
        - NEVER fall back to fuzzy ShortTermBorrowings match
        - Custodial banks have repos as financing, not contamination
        """
        # Specific components for custodial banks
        other_stb = self._get_fact_value(facts_df, 'OtherShortTermBorrowings')
        fed_funds = self._get_fact_value(facts_df, 'FederalFundsPurchased')

        # Check for company-specific repos (STT uses stt: prefix)
        # For custodial, repos ARE debt (unlike commercial)
        repos_liability = self._get_fact_value_fuzzy(facts_df, 'SecuritiesSoldUnderAgreementsToRepurchase') or 0

        components = []
        total = 0.0

        if other_stb is not None and other_stb > 0:
            total += other_stb
            components.append(f"OtherSTB({other_stb/1e9:.1f}B)")

        if fed_funds is not None and fed_funds > 0:
            total += fed_funds
            components.append(f"FedFunds({fed_funds/1e9:.1f}B)")

        # Add repos for custodial (it's financing, not contamination)
        if repos_liability > 0:
            total += repos_liability
            components.append(f"Repos({repos_liability/1e9:.1f}B)")

        if cpltd > 0:
            total += cpltd
            components.append(f"CPLTD({cpltd/1e9:.1f}B)")

        # CRITICAL: If no components found, return None - do NOT fuzzy match
        # Per architect: "return None rather than fuzzy-match for STT/BK"
        if total == 0 or not components:
            return ExtractedMetric(
                standard_name="ShortTermDebt",
                industry_counterpart=None,
                xbrl_concept=None,
                value=None,
                extraction_method=ExtractionMethod.DIRECT,
                notes=f"Custodial [{ticker}]: No components found - flagged for manual review"
            )

        return ExtractedMetric(
            standard_name="ShortTermDebt",
            industry_counterpart="ShortTermDebt_GAAP_Custodial",
            xbrl_concept=None,
            value=total,
            extraction_method=ExtractionMethod.COMPOSITE,
            notes=f"Custodial [{ticker}]: {' + '.join(components)}"
        )

    def _extract_commercial_stb(self, xbrl, facts_df, cpltd: float, ticker: str, rules: dict) -> ExtractedMetric:
        """
        Commercial Banks (WFC, USB, PNC): Hybrid Bottom-Up/Top-Down.

        Strategy:
        1. TRY Bottom-Up: CP + FHLB + OtherSTB + CPLTD
        2. IF Bottom-Up yields $0: Top-Down subtraction (STB - Repos - Trading)

        Per architect: Commercial banks bundle repos into STB, so we must subtract.
        """
        # === ATTEMPT 1: Bottom-Up Aggregation ===
        cp = self._get_fact_value(facts_df, 'CommercialPaper') or 0
        fhlb = self._get_fact_value_fuzzy(facts_df, 'FederalHomeLoanBankAdvances') or 0
        other_stb = self._get_fact_value(facts_df, 'OtherShortTermBorrowings') or 0

        bottom_up = cp + fhlb + other_stb + cpltd

        if bottom_up > 0:
            components = []
            if cp > 0:
                components.append(f"CP({cp/1e9:.1f}B)")
            if fhlb > 0:
                components.append(f"FHLB({fhlb/1e9:.1f}B)")
            if other_stb > 0:
                components.append(f"OtherSTB({other_stb/1e9:.1f}B)")
            if cpltd > 0:
                components.append(f"CPLTD({cpltd/1e9:.1f}B)")

            return ExtractedMetric(
                standard_name="ShortTermDebt",
                industry_counterpart="ShortTermDebt_GAAP_BottomUp",
                xbrl_concept=None,
                value=bottom_up,
                extraction_method=ExtractionMethod.COMPOSITE,
                notes=f"Commercial [{ticker}]: Bottom-Up = {' + '.join(components)}"
            )

        # === ATTEMPT 2: Top-Down Subtraction ===
        stb = self._get_fact_value(facts_df, 'ShortTermBorrowings') or 0

        if stb > 0:
            # Get contaminants using SUFFIX MATCHING (namespace-resilient)
            repos = self._get_repos_value(facts_df) or 0
            trading = self._get_fact_value(facts_df, 'TradingLiabilities') or 0
            if trading == 0:
                trading = self._get_fact_value_fuzzy(facts_df, 'TradingAccountLiabilities') or 0

            # Always subtract for commercial (per architect rules)
            clean_stb = max(0, stb - repos - trading)
            total = clean_stb + cpltd

            # Per architect: Store repos value in metadata - don't discard
            metadata = {
                'secured_funding_repos': repos,
                'trading_liabilities': trading,
                'archetype': 'commercial',
                'raw_stb': stb,
            }

            return ExtractedMetric(
                standard_name="ShortTermDebt",
                industry_counterpart="ShortTermDebt_GAAP_TopDown",
                xbrl_concept=None,
                value=total,
                extraction_method=ExtractionMethod.COMPOSITE,
                notes=f"Commercial [{ticker}]: Top-Down = STB({stb/1e9:.1f}B) - Repos({repos/1e9:.1f}B) - Trading({trading/1e9:.1f}B) + CPLTD({cpltd/1e9:.1f}B)",
                metadata=metadata
            )

        # No valid value found
        return ExtractedMetric(
            standard_name="ShortTermDebt",
            industry_counterpart=None,
            xbrl_concept=None,
            value=None,
            extraction_method=ExtractionMethod.DIRECT,
            notes=f"Commercial [{ticker}]: No valid ShortTermDebt found"
        )

    def _extract_hybrid_stb(self, xbrl, facts_df, cpltd: float, ticker: str, rules: dict) -> ExtractedMetric:
        """
        Hybrid Banks (JPM, BAC, C): Check nesting before subtracting.

        Per Senior Architect directive:
        - Ensure we don't double-subtract if filer already reports Repos separately
        - Check calculation/presentation linkbase for nesting relationship
        """
        stb = self._get_fact_value(facts_df, 'ShortTermBorrowings') or 0

        # Get repos value (using suffix matching)
        repos = self._get_repos_value(facts_df) or 0

        # CHECK: Is repos nested inside STB, or is it a separate line item?
        # For hybrid banks, check the calculation linkbase relationship
        repos_is_nested = self._is_concept_nested_in_stb(xbrl, 'SecuritiesSoldUnderAgreementsToRepurchase')

        if repos_is_nested and repos > 0:
            # Repos IS nested - we need to subtract
            clean_stb = max(0, stb - repos)
            total = clean_stb + cpltd
            notes = f"Hybrid [{ticker}]: STB({stb/1e9:.1f}B) - Repos({repos/1e9:.1f}B) [nested] + CPLTD({cpltd/1e9:.1f}B)"
        else:
            # Repos is separate line item - do NOT subtract (would double-count)
            total = stb + cpltd
            notes = f"Hybrid [{ticker}]: STB({stb/1e9:.1f}B) + CPLTD({cpltd/1e9:.1f}B) [repos separate: {repos/1e9:.1f}B]"

        # Per architect: Store repos value in metadata - don't discard
        metadata = {
            'secured_funding_repos': repos,
            'repos_is_nested': repos_is_nested,
            'archetype': 'hybrid',
            'raw_stb': stb,
        }

        if total > 0:
            return ExtractedMetric(
                standard_name="ShortTermDebt",
                industry_counterpart="ShortTermDebt_GAAP_Hybrid",
                xbrl_concept=None,
                value=total,
                extraction_method=ExtractionMethod.COMPOSITE,
                notes=notes,
                metadata=metadata
            )

        return ExtractedMetric(
            standard_name="ShortTermDebt",
            industry_counterpart=None,
            xbrl_concept=None,
            value=None,
            extraction_method=ExtractionMethod.DIRECT,
            notes=f"Hybrid [{ticker}]: No valid ShortTermDebt found"
        )

    def _extract_dealer_stb(self, facts_df, cpltd: float, ticker: str, rules: dict) -> ExtractedMetric:
        """
        Dealer Banks (GS, MS): Direct UnsecuredSTB.

        Dealers have repos as separate line items (~$274B for GS).
        Use the clean unsecured STB tag directly.
        """
        # Dealer-specific: UnsecuredShortTermBorrowings (explicitly excludes repos)
        unsecured_stb = self._get_fact_value_fuzzy(facts_df, 'UnsecuredShortTermBorrowings') or 0

        if unsecured_stb == 0:
            # Fallback to ShortTermBorrowings (dealers usually report clean)
            unsecured_stb = self._get_fact_value(facts_df, 'ShortTermBorrowings') or 0

        total = unsecured_stb + cpltd

        # Get repos for metadata (dealers have large repos as separate line items)
        repos = self._get_repos_value(facts_df) or 0

        # Per architect: Store repos value in metadata - don't discard
        metadata = {
            'secured_funding_repos': repos,
            'unsecured_stb': unsecured_stb,
            'archetype': 'dealer',
        }

        if total > 0:
            return ExtractedMetric(
                standard_name="ShortTermDebt",
                industry_counterpart="ShortTermDebt_GAAP_Dealer",
                xbrl_concept=None,
                value=total,
                extraction_method=ExtractionMethod.COMPOSITE,
                notes=f"Dealer [{ticker}]: UnsecuredSTB({unsecured_stb/1e9:.1f}B) + CPLTD({cpltd/1e9:.1f}B)",
                metadata=metadata
            )

        return ExtractedMetric(
            standard_name="ShortTermDebt",
            industry_counterpart=None,
            xbrl_concept=None,
            value=None,
            extraction_method=ExtractionMethod.DIRECT,
            notes=f"Dealer [{ticker}]: No valid ShortTermDebt found",
            metadata=metadata
        )
    
    def extract_street_debt(self, xbrl, facts_df, ticker: str = None) -> ExtractedMetric:
        """
        Street Debt: Wholesale Funding via Strict Component Summation.

        Refined Rules (to match analyst/Street View):
        - Commercial (USB): STB(Aggregate) - CPLTD - OperatingLiabilities. Exclude Repos.
        - Dealer (GS): UnsecuredSTB + BrokerPayables + OtherSecured + NetRepos (Economic Leverage).

        Guardrails:
        - TradingLiabilities exclusion: Excludes non-debt operating liabilities
        - Sanity Governor: If aggregate > 2x components, aggregate is contaminated
        """
        archetype = self._detect_bank_archetype(facts_df)

        # 1. Base Components
        cp = self._get_fact_value(facts_df, 'CommercialPaper') or 0
        other_stb = self._get_fact_value(facts_df, 'OtherShortTermBorrowings') or 0
        fhlb = self._get_fact_value_fuzzy(facts_df, 'FederalHomeLoanBankAdvances') or 0

        # Repos Logic
        repos = self._get_fact_value(facts_df, 'SecuritiesSoldUnderAgreementsToRepurchase') or 0
        if repos == 0:
            repos = self._get_fact_value_fuzzy(facts_df, 'SecuritiesSoldUnderAgreementsToRepurchase') or 0

        reverse_repos = self._get_fact_value(facts_df, 'SecuritiesPurchasedUnderAgreementsToResell') or 0
        if reverse_repos == 0:
            reverse_repos = self._get_fact_value_fuzzy(facts_df, 'SecuritiesPurchasedUnderAgreementsToResell') or 0

        net_repos = max(0, repos - reverse_repos)

        # 2. Archetype Specifics
        unsecured_stb = 0
        broker_payables = 0
        other_secured = 0
        if archetype == 'dealer':
            # Unsecured STB (GS specific extension) - anchor for dealers
            unsecured_stb = self._get_fact_value_fuzzy(facts_df, 'UnsecuredShortTermBorrowings') or 0
            # Broker Payables - Analysts often include this in liquidity/short-term debt stack
            broker_payables = self._get_fact_value_fuzzy(facts_df, 'PayablesToBrokerDealersAndClearingOrganizations') or 0
            # Other secured borrowings (excluding Repos)
            other_secured = self._get_fact_value_fuzzy(facts_df, 'OtherSecuredBorrowings') or 0

        # 3. Aggregate and CPLTD
        stb_aggregate = self._get_fact_value(facts_df, 'ShortTermBorrowings') or 0
        cpltd = (self._get_fact_value(facts_df, 'LongTermDebtCurrent') or
                 self._get_fact_value_fuzzy(facts_df, 'LongTermDebtAndLeaseObligationMaturityYearOne') or 0)

        # 4. OPERATING LIABILITIES (MUST EXCLUDE from debt for Street View)
        # These are trading/customer liabilities, not financing debt
        trading_liabilities = self._get_fact_value(facts_df, 'TradingLiabilities') or 0
        if trading_liabilities == 0:
            trading_liabilities = self._get_fact_value_fuzzy(facts_df, 'TradingAccountLiabilities') or 0

        payables_customers = self._get_fact_value(facts_df, 'PayablesToCustomers') or 0

        securities_sold_short = self._get_fact_value(facts_df, 'FinancialInstrumentsSoldNotYetPurchasedAtFairValue') or 0
        if securities_sold_short == 0:
            securities_sold_short = self._get_fact_value_fuzzy(facts_df, 'SecuritiesSoldShort') or 0

        operating_liabilities = trading_liabilities + payables_customers + securities_sold_short

        # 5. SANITY GOVERNOR: If aggregate > 2x components, it's contaminated
        components_sum = cp + other_stb + fhlb
        sanity_threshold = 2.0
        aggregate_is_contaminated = (
            stb_aggregate > 0 and
            components_sum > 0 and
            stb_aggregate > (components_sum * sanity_threshold)
        )

        # 6. FINAL LOGIC SELECTION
        total = 0
        notes = ""

        if archetype == 'dealer':
            # Street View for Dealers: Unsecured + BrokerPayables + OtherSecured + NetRepos (Economic Leverage)
            # Use max(stb_aggregate, unsecured_stb) as the core
            core = max(stb_aggregate, unsecured_stb)
            total = core + broker_payables + other_secured + net_repos
            notes = f"Bank Street Debt [dealer]: core({core/1e9:.1f}B) + broker_payables({broker_payables/1e9:.1f}B) + net_repos({net_repos/1e9:.1f}B)"
        else:
            # Street View for Commercial Banks
            if aggregate_is_contaminated:
                # SANITY GOVERNOR TRIGGERED: Aggregate is > 2x components, use components only
                total = cp + other_stb + fhlb
                notes = f"Bank Street Debt [commercial/SANITY]: CP({cp/1e9:.1f}B) + OtherSTB({other_stb/1e9:.1f}B) + FHLB({fhlb/1e9:.1f}B) [aggregate contaminated: {stb_aggregate/1e9:.1f}B > 2x {components_sum/1e9:.1f}B]"
            elif stb_aggregate > 0:
                # Does STB include CPLTD? If STB is significantly higher than components, it likely does.
                if stb_aggregate > (components_sum * 1.5) and cpltd > 0:
                    # Subtract CPLTD and operating liabilities for clean Street View
                    clean_debt = max(0, stb_aggregate - cpltd - operating_liabilities)
                    total = clean_debt
                    if operating_liabilities > 0:
                        notes = f"Bank Street Debt [commercial]: STB({stb_aggregate/1e9:.1f}B) - CPLTD({cpltd/1e9:.1f}B) - OpLiab({operating_liabilities/1e9:.1f}B)"
                    else:
                        notes = f"Bank Street Debt [commercial]: STB({stb_aggregate/1e9:.1f}B) - CPLTD({cpltd/1e9:.1f}B)"
                else:
                    # STB is likely the clean street number, but still exclude operating liabilities
                    if operating_liabilities > 0 and operating_liabilities < stb_aggregate:
                        clean_debt = max(0, stb_aggregate - operating_liabilities)
                        total = clean_debt
                        notes = f"Bank Street Debt [commercial]: STB({stb_aggregate/1e9:.1f}B) - OpLiab({operating_liabilities/1e9:.1f}B)"
                    else:
                        total = stb_aggregate
                        notes = f"Bank Street Debt [commercial]: STB({stb_aggregate/1e9:.1f}B) [aggregate]"
            else:
                total = cp + other_stb + fhlb
                notes = f"Bank Street Debt [commercial]: CP({cp/1e9:.1f}B) + OtherSTB({other_stb/1e9:.1f}B) + FHLB({fhlb/1e9:.1f}B) [components]"

        return ExtractedMetric(
            standard_name="ShortTermDebt",
            industry_counterpart="WholesaleFunding",
            xbrl_concept=None,
            value=total if total > 0 else None,
            extraction_method=ExtractionMethod.COMPOSITE,
            notes=notes
        )

    def _extract_short_term_debt_yfinance_legacy(self, xbrl, facts_df) -> ExtractedMetric:
        """
        LEGACY: Bank ShortTermDebt yfinance-aligned extraction (excludes Repos/FedFunds).
        
        Kept for reference/comparison. New code should use extract_street_debt().
        """
        # Path A: Direct clean tag (JPM-style)
        other = self._get_fact_value(facts_df, 'OtherShortTermBorrowings')
        stb = self._get_fact_value(facts_df, 'ShortTermBorrowings')
        
        if other is not None and other > 0:
            if stb is None or abs(other - stb) < 1e6:
                return ExtractedMetric(
                    standard_name="ShortTermDebt",
                    industry_counterpart="OtherShortTermBorrowings",
                    xbrl_concept="us-gaap:OtherShortTermBorrowings",
                    value=other,
                    extraction_method=ExtractionMethod.DIRECT,
                    notes="Bank LEGACY: OtherShortTermBorrowings (clean, equals aggregate)"
                )
        
        if stb is not None and stb > 0:
            return ExtractedMetric(
                standard_name="ShortTermDebt",
                industry_counterpart="ShortTermBorrowings",
                xbrl_concept="us-gaap:ShortTermBorrowings",
                value=stb,
                extraction_method=ExtractionMethod.DIRECT,
                notes="Bank LEGACY: ShortTermBorrowings"
            )
        
        return ExtractedMetric(
            standard_name="ShortTermDebt",
            industry_counterpart=None,
            xbrl_concept=None,
            value=None,
            extraction_method=ExtractionMethod.DIRECT
        )
    
    def extract_short_term_debt_economic(self, xbrl, facts_df) -> ExtractedMetric:
        """
        Bank ShortTermDebt: Economic view (includes Repos/FedFunds).
        
        Used for risk analysis - captures true leverage.
        """
        # Sum all short-term debt components (ground truth)
        st_borrowings = self._get_fact_value(facts_df, 'ShortTermBorrowings') or 0
        repos = self._get_fact_value(facts_df, 'FederalFundsPurchasedAndSecuritiesSoldUnderAgreementsToRepurchase') or 0
        cp = self._get_fact_value(facts_df, 'CommercialPaper') or 0
        
        total = st_borrowings + repos + cp
        
        return ExtractedMetric(
            standard_name="ShortTermDebt_Economic",
            industry_counterpart="AllShortTermDebt",
            xbrl_concept=None,
            value=total if total > 0 else None,
            extraction_method=ExtractionMethod.COMPOSITE,
            notes="Bank (economic): ShortTermBorrowings + Repos + CP"
        )
    
    def extract_cash_and_equivalents(self, xbrl, facts_df, mode: str = 'street') -> ExtractedMetric:
        """
        Bank Cash extraction with mode selection.

        Dual-Track Architecture:
        - 'gaap': GAAP-aligned extraction for yfinance validation
        - 'street': Street View extraction for database (economic liquidity, default)

        Args:
            xbrl: XBRL object
            facts_df: DataFrame of XBRL facts
            mode: 'gaap' for yfinance validation, 'street' for database (default)

        Returns:
            ExtractedMetric with appropriate extraction method
        """
        if mode == 'gaap':
            return self.extract_cash_gaap(xbrl, facts_df)
        else:
            return self.extract_street_cash(xbrl, facts_df)

    def extract_cash_gaap(self, xbrl, facts_df) -> ExtractedMetric:
        """
        GAAP-aligned Cash extraction (matches yfinance 'Cash And Cash Equivalents').

        yfinance formula: CashAndCashEquivalents + InterestBearingDeposits + FedDeposits - RestrictedCash

        Root Cause Analysis:
        - BK: CashAndCashEquivalentsAtCarryingValue ($4.2B) doesn't include Fed Deposits ($89.5B)
          but yfinance = $101.9B (CCE + Fed Deposits)
        - MS: CashAndCashEquivalentsAtCarryingValue ($105.4B) includes RestrictedCash ($29.6B)
          but yfinance = $75.7B (excludes Restricted)

        Strategy:
        1. Get base cash (CCE)
        2. SUBTRACT Restricted Cash (yfinance excludes)
        3. ADD Interest-Bearing Deposits + Fed Deposits (for banks with separate line items)
        4. Avoid double-counting using heuristics
        """
        # 1. Get base cash value - with expanded hierarchy for commercial banks
        cce = self._get_fact_value(facts_df, 'CashAndCashEquivalentsAtCarryingValue') or 0
        if cce == 0:
            # Priority 2: CashAndDueFromBanks (common for commercial banks like USB)
            # USB reports $56.5B here, which is exact match to yfinance
            cce = self._get_fact_value(facts_df, 'CashAndDueFromBanks') or 0
        if cce == 0:
            cce = self._get_fact_value(facts_df, 'CashAndCashEquivalents') or 0

        # 2. SUBTRACT Restricted Cash (yfinance excludes)
        restricted = self._get_fact_value(facts_df, 'RestrictedCashAndCashEquivalents') or 0
        if restricted == 0:
            restricted = self._get_fact_value(facts_df, 'RestrictedCash') or 0

        # 3. ADD Interest-Bearing Deposits (for banks, this is liquid)
        ib_deposits = self._get_fact_value(facts_df, 'InterestBearingDepositsInBanks') or 0

        # 4. ADD Fed Deposits (critical for custodial banks like BK)
        # BK uses: bk:InterestBearingDepositsInFederalReserveAndOtherCentralBanks (~$89.5B)
        fed_deposits = self._get_fact_value(facts_df, 'InterestBearingDepositsWithFederalReserveBank') or 0
        if fed_deposits == 0:
            fed_deposits = self._get_fact_value_fuzzy(facts_df, 'InterestBearingDepositsInFederalReserve') or 0
        if fed_deposits == 0:
            fed_deposits = self._get_fact_value_fuzzy(facts_df, 'DepositsWithFederalReserve') or 0

        # 5. Avoid double-counting: Check if CCE already includes IB/Fed deposits
        # Heuristic: If CCE is small relative to deposits, they're separate line items
        # If CCE is large and close to total deposits, it might already include them
        total_deposits = ib_deposits + fed_deposits

        if cce > 0 and total_deposits > 0:
            # Heuristic: If CCE < total_deposits, they're clearly separate (add them)
            # If CCE > total_deposits, CCE might already include them (don't double-count)
            if cce < total_deposits * 0.5:
                # CCE is clearly separate from deposits
                total = cce + total_deposits - restricted
            else:
                # CCE might include deposits, just subtract restricted
                total = cce - restricted
        elif total_deposits > 0:
            total = total_deposits - restricted
        else:
            total = cce - restricted

        total = max(0, total)

        if total > 0:
            return ExtractedMetric(
                standard_name="CashAndEquivalents",
                industry_counterpart="CashAndEquivalents_GAAP",
                xbrl_concept=None,
                value=total,
                extraction_method=ExtractionMethod.COMPOSITE,
                notes=f"Bank GAAP: CCE({cce/1e9:.1f}B) + IBDeposits({ib_deposits/1e9:.1f}B) + FedDeposits({fed_deposits/1e9:.1f}B) - Restricted({restricted/1e9:.1f}B)"
            )

        # Fallback to Cash
        val = self._get_fact_value(facts_df, 'Cash')
        if val is not None and val > 0:
            return ExtractedMetric(
                standard_name="CashAndEquivalents",
                industry_counterpart="Cash_GAAP",
                xbrl_concept="us-gaap:Cash",
                value=val,
                extraction_method=ExtractionMethod.DIRECT,
                notes="Bank GAAP: Cash (fallback)"
            )

        # No valid GAAP value found
        return ExtractedMetric(
            standard_name="CashAndEquivalents",
            industry_counterpart=None,
            xbrl_concept=None,
            value=None,
            extraction_method=ExtractionMethod.DIRECT,
            notes="Bank GAAP: No valid CashAndEquivalents found"
        )
    
    def extract_street_cash(self, xbrl, facts_df) -> ExtractedMetric:
        """
        Street Cash: Economic Liquidity.
        
        Refined Rules:
        - Commercial (USB): CashAndDueFromBanks only (excludes IBDeposits if physical cash is found).
        - Dealer (GS): CashAndDueFromBanks + IBDeposits + RestrictedCash.
        """
        archetype = self._detect_bank_archetype(facts_df)
        assets = self._get_fact_value(facts_df, 'Assets') or 0
        
        physical_cash = self._get_fact_value(facts_df, 'CashAndDueFromBanks') or 0
        ib_deposits = self._get_fact_value(facts_df, 'InterestBearingDepositsInBanks') or 0
        
        # CRITICAL FIX for BK/STT: Fed Deposits (company-extension tags)
        # BK uses: bk:InterestBearingDepositsInFederalReserveAndOtherCentralBanks (~$90B)
        # Try fuzzy match to catch company-prefixed variants
        fed_deposits = self._get_fact_value_fuzzy(facts_df, 'InterestBearingDepositsInFederalReserve') or 0
        if fed_deposits == 0:
            fed_deposits = self._get_fact_value_fuzzy(facts_df, 'DepositsInFederalReserve') or 0
        
        # Segregated/Restricted
        segregated_cash = (
            self._get_fact_value(facts_df, 'CashAndSecuritiesSegregatedUnderFederalAndOtherRegulations') or
            self._get_fact_value(facts_df, 'CashSegregatedUnderFederalAndOtherRegulations') or
            0
        )
        restricted = self._get_fact_value_fuzzy(facts_df, 'RestrictedCashAndCashEquivalents') or 0
        
        total = 0
        notes = ""
        
        if archetype == 'dealer':
            # Dealers: Sum all liquidity pools
            total = physical_cash + ib_deposits + fed_deposits + segregated_cash + restricted
            notes = f"Bank Street Cash [dealer]: physical({physical_cash/1e9:.1f}B) + ib_deposits({ib_deposits/1e9:.1f}B) + fed_deposits({fed_deposits/1e9:.1f}B) + restricted({restricted/1e9:.1f}B)"
        else:
            # Commercial: Prefer physical cash. Only add others if physical is low or missing.
            if physical_cash > (assets * 0.05): # Substantial liquidity pool
                total = physical_cash
                notes = f"Bank Street Cash [commercial]: physical({physical_cash/1e9:.1f}B) [anchor]"
            else:
                total = physical_cash + ib_deposits + fed_deposits
                notes = f"Bank Street Cash [commercial]: physical({physical_cash/1e9:.1f}B) + ib_deposits({ib_deposits/1e9:.1f}B) + fed_deposits({fed_deposits/1e9:.1f}B)"
        
        if total > 0 and assets > 0 and total / assets >= 0.01:
            return ExtractedMetric(
                standard_name="CashAndEquivalents",
                industry_counterpart="StreetCash",
                xbrl_concept=None,  # Composite - no single source (metadata integrity)
                value=total,
                extraction_method=ExtractionMethod.COMPOSITE,
                notes=notes
            )
        
        # Fallback to GAAP extraction if composite is not substantial
        return self._extract_cash_gaap_fallback(xbrl, facts_df)
    
    def _extract_cash_gaap_fallback(self, xbrl, facts_df) -> ExtractedMetric:
        """
        GAAP Cash fallback: Context-aware extraction with sanity check.
        
        Guardrail: Cash < 1% of Assets triggers further fallback.
        This prevents returning subsidiary/restricted cash instead of consolidated total.
        """
        # Get Total Assets for context validation
        assets = self._get_fact_value(facts_df, 'Assets')
        
        # 1. Try standard CashAndCashEquivalentsAtCarryingValue
        val = self._get_fact_value(facts_df, 'CashAndCashEquivalentsAtCarryingValue')
        
        # Investment Banks often include Restricted Cash in this tag
        # We must deduct it to match analyst "Cash & Equivalents" (unrestricted)
        if val is not None:
             restricted = (
                 self._get_fact_value(facts_df, 'RestrictedCashAndCashEquivalents') or # Combined
                 self._get_fact_value(facts_df, 'RestrictedCash') or                   # Standard
                 self._get_fact_value(facts_df, 'CashSegregatedUnderFederalAndOtherRegulations') or # Custody
                 0
             )
             if restricted > 0:
                 # Only deduct if it makes sense (e.g. doesn't turn negative)
                 net_val = val - restricted
                 if net_val > 0:
                     return ExtractedMetric(
                        standard_name="CashAndEquivalents",
                        industry_counterpart="CashAndCashEquivalents_Net",
                        xbrl_concept="us-gaap:CashAndCashEquivalentsAtCarryingValue",
                        value=net_val,
                        extraction_method=ExtractionMethod.CALCULATED,
                        notes=f"Bank GAAP: CarryingValue({val/1e9:.1f}B) - Restricted({restricted/1e9:.1f}B)"
                    )
        
        # Sanity Check: Is this suspiciously low for a bank?
        if val is not None and assets is not None and assets > 0:
            cash_ratio = val / assets
            if cash_ratio < 0.01:  # Less than 1% of assets
                # Likely subsidiary/restricted cash - force fallback
                val = None
        
        if val is not None:
            return ExtractedMetric(
                standard_name="CashAndEquivalents",
                industry_counterpart="CashAndCashEquivalentsAtCarryingValue",
                xbrl_concept="us-gaap:CashAndCashEquivalentsAtCarryingValue",
                value=val,
                extraction_method=ExtractionMethod.DIRECT,
                notes="Bank GAAP: Standard CashAndCashEquivalentsAtCarryingValue"
            )
        
        # 2. Try simple CashAndCashEquivalents (with same sanity check)
        val = self._get_fact_value(facts_df, 'CashAndCashEquivalents')
        if val is not None and assets is not None and assets > 0:
            if val / assets < 0.01:
                val = None
        
        if val is not None:
            return ExtractedMetric(
                standard_name="CashAndEquivalents",
                industry_counterpart="CashAndCashEquivalents",
                xbrl_concept="us-gaap:CashAndCashEquivalents",
                value=val,
                extraction_method=ExtractionMethod.DIRECT,
                notes="Bank GAAP: Standard CashAndCashEquivalents"
            )
        
        # Return empty metric to signal complete fallback failure
        return ExtractedMetric(
            standard_name="CashAndEquivalents",
            industry_counterpart=None,
            xbrl_concept=None,
            value=None,
            extraction_method=ExtractionMethod.DIRECT
        )

    def extract_capex(self, xbrl, facts_df) -> ExtractedMetric:
        # Banks have minimal Capex - use default logic
        return DefaultExtractor().extract_capex(xbrl, facts_df)
    
    def extract_operating_income(self, xbrl, facts_df) -> ExtractedMetric:
        """
        Bank OperatingIncome: Dual-track - PPNR vs Post-Provision.
        
        Analyst Convention:
        - PPNR (Pre-Provision Net Revenue): Pure operating power (NII + NonIntInc - NonIntExp).
        - Operating Income (yfinance): Typically PPNR - Provision for Credit Losses.
        
        We calculate both and return Post-Provision as the primary 'OperatingIncome',
        but note PPNR in the extraction details.
        """
        # Components
        nii = self._get_fact_value(facts_df, 'InterestIncomeExpenseNet')
        if nii is None:
            nii = self._get_fact_value(facts_df, 'NetInterestIncome')
        
        non_int_income = self._get_fact_value(facts_df, 'NoninterestIncome')
        non_int_expense = self._get_fact_value(facts_df, 'NoninterestExpense')
        
        # Provision for Credit Losses
        provision = (
            self._get_fact_value(facts_df, 'ProvisionForCreditLosses') or 
            self._get_fact_value(facts_df, 'ProvisionForLoanLeaseAndOtherLosses') or
            0
        )
        
        if nii is not None and non_int_income is not None and non_int_expense is not None:
            ppnr = nii + non_int_income - non_int_expense
            post_provision = ppnr - provision
            
            # Return Post-Provision as standard OperatingIncome (matches yfinance generally)
            return ExtractedMetric(
                standard_name="OperatingIncome",
                industry_counterpart="OperatingProfit_PostProvision",
                xbrl_concept=None,
                value=post_provision,
                extraction_method=ExtractionMethod.CALCULATED,
                notes=f"Bank: PPNR({ppnr/1e9:.2f}B) - Provision({provision/1e9:.2f}B)"
            )
        
        return ExtractedMetric(
            standard_name="OperatingIncome",
            industry_counterpart="PPNR",
            xbrl_concept=None,
            value=None,
            extraction_method=ExtractionMethod.CALCULATED
        )

    def validate_accounting_identity(self, xbrl, facts_df, reported_op_income: float) -> Optional[str]:
        """
        Bank Identity: (NII + NonIntInc) - (NonIntExp + Provisions) == OperatingIncome
        """
        if reported_op_income is None:
            return None
            
        nii = self._get_fact_value(facts_df, 'InterestIncomeExpenseNet') or self._get_fact_value(facts_df, 'NetInterestIncome') or 0
        non_int_inc = self._get_fact_value(facts_df, 'NoninterestIncome') or 0
        non_int_exp = self._get_fact_value(facts_df, 'NoninterestExpense') or 0
        provision = (
            self._get_fact_value(facts_df, 'ProvisionForCreditLosses') or 
            self._get_fact_value(facts_df, 'ProvisionForLoanLeaseAndOtherLosses') or
            0
        )
        
        constructed = (nii + non_int_inc) - (non_int_exp + provision)
        
        # Check for deviation > 10%
        if constructed != 0:
            diff_pct = abs(constructed - reported_op_income) / abs(reported_op_income)
            if diff_pct > 0.1:
                return (
                    f"IDENTITY FAIL: Reported OpInc ({reported_op_income/1e9:.2f}B) != "
                    f"Constructed ({constructed/1e9:.2f}B) [NII+NonIntInc-Exp-Prov]. "
                    f"Diff: {diff_pct:.1%}"
                )
        return None
    
    def _detect_bank_archetype(self, facts_df) -> str:
        """
        Detect bank archetype for extraction strategy selection.
        
        Archetypes:
        - 'custodial': BK, STT (PayablesToCustomers > 20% Liabilities)
        - 'dealer': GS, MS (High TradingAssets, Repos >> ReverseRepos)
        - 'commercial': WFC, BAC, JPM, PNC (Loans > 50% Assets, default)
        
        Returns:
            str: 'custodial', 'dealer', or 'commercial'
        """
        assets = self._get_fact_value(facts_df, 'Assets') or 0
        liabilities = self._get_fact_value(facts_df, 'Liabilities') or 0
        
        # Custodial signal: High payables to customers (asset management)
        payables_customers = self._get_fact_value(facts_df, 'PayablesToCustomers') or 0
        if liabilities > 0 and payables_customers / liabilities > 0.20:
            return 'custodial'
        
        # Dealer signal: High trading assets and low loans
        trading_assets = (
            self._get_fact_value(facts_df, 'TradingAssets') or
            self._get_fact_value(facts_df, 'TradingSecurities') or
            0
        )
        loans = (
            self._get_fact_value(facts_df, 'LoansAndLeasesReceivableGrossCarryingAmount') or
            self._get_fact_value(facts_df, 'LoansAndLeasesReceivableNetReportedAmount') or
            0
        )
        
        if assets > 0:
            trading_ratio = trading_assets / assets
            loan_ratio = loans / assets
            # Dealer: High trading (>15% assets) and low loans (<30% assets)
            if trading_ratio > 0.15 and loan_ratio < 0.30:
                return 'dealer'
        
        # Default: Commercial bank
        return 'commercial'


class SaaSExtractor(IndustryExtractor):
    """
    SaaS/Tech-specific extraction logic (SIC 7370-7379, 5112).
    
    Key differences from default:
    - Deferred Revenue treated as functional liability (not debt)
    - Capitalized Software separate from PP&E Capex
    - R&D often capitalized differently
    """
    
    industry_name = "saas"
    
    def extract_short_term_debt(self, xbrl, facts_df) -> ExtractedMetric:
        """SaaS ShortTermDebt: Standard approach (no special treatment)."""
        return DefaultExtractor().extract_short_term_debt(xbrl, facts_df)
    
    def extract_functional_debt(self, xbrl, facts_df) -> ExtractedMetric:
        """
        SaaS Functional Debt: Include Deferred Revenue as liability.
        
        Deferred Revenue represents subscription prepayments that must be
        "repaid" through future service delivery. While not traditional debt,
        it's a real liability for working capital analysis.
        """
        # Standard short-term debt
        std_result = self.extract_short_term_debt(xbrl, facts_df)
        std_value = std_result.value or 0
        
        # Add Deferred Revenue components
        deferred_current = (
            self._get_fact_value(facts_df, 'ContractWithCustomerLiabilityCurrent') or
            self._get_fact_value(facts_df, 'DeferredRevenueCurrent') or
            self._get_fact_value(facts_df, 'DeferredRevenueAndCredits') or
            0
        )
        
        total = std_value + deferred_current
        
        return ExtractedMetric(
            standard_name="FunctionalDebt",
            industry_counterpart="ShortTermDebt+DeferredRevenue",
            xbrl_concept=None,
            value=total if total > 0 else None,
            extraction_method=ExtractionMethod.COMPOSITE,
            notes=f"SaaS functional liability: STD={std_value/1e9:.2f}B + DeferredRev={deferred_current/1e9:.2f}B" if total > 0 else None
        )
    
    def extract_capex(self, xbrl, facts_df) -> ExtractedMetric:
        """SaaS Capex: Separate Growth (software) vs Maintenance (PP&E)."""
        result = self.extract_capex_breakdown(xbrl, facts_df)
        # Return total Capex for standard comparison
        total = result.get('total', 0)
        return ExtractedMetric(
            standard_name="Capex",
            industry_counterpart=None,
            xbrl_concept=None,
            value=total if total > 0 else None,
            extraction_method=ExtractionMethod.COMPOSITE,
            notes=f"SaaS: GrowthCapex={result.get('growth', 0)/1e9:.2f}B + MaintenanceCapex={result.get('maintenance', 0)/1e9:.2f}B" if total > 0 else None
        )
    
    def extract_capex_breakdown(self, xbrl, facts_df) -> Dict[str, float]:
        """
        Separate GrowthCapex (software) from MaintenanceCapex (PP&E).
        
        Key insight: For SaaS companies, capitalized software is "growth"
        investment in the product, while PP&E is maintenance/office costs.
        """
        # Growth Capex: Software and intangible development
        software = (
            self._get_fact_value(facts_df, 'PaymentsToDevelopSoftware') or
            self._get_fact_value(facts_df, 'CapitalizedComputerSoftwareAdditions') or
            0
        )
        intangibles = self._get_fact_value(facts_df, 'PaymentsToAcquireIntangibleAssets') or 0
        
        growth_capex = software + intangibles
        
        # Maintenance Capex: PP&E only
        maintenance_capex = self._get_fact_value(facts_df, 'PaymentsToAcquirePropertyPlantAndEquipment') or 0
        
        total = growth_capex + maintenance_capex
        
        return {
            'growth': growth_capex,
            'maintenance': maintenance_capex,
            'total': total,
            'growth_pct': (growth_capex / total * 100) if total > 0 else 0
        }
    
    def extract_operating_income(self, xbrl, facts_df) -> ExtractedMetric:
        """SaaS OperatingIncome: Standard calculation."""
        return DefaultExtractor().extract_operating_income(xbrl, facts_df)


class InsuranceExtractor(IndustryExtractor):
    """
    Insurance-specific extraction logic (SIC 6300-6499).
    
    Key differences from default:
    - Policy Reserves are primary liability (not traditional debt)
    - Claims expense is COGS equivalent
    - Investment income is significant revenue component
    """
    
    industry_name = "insurance"
    
    def extract_short_term_debt(self, xbrl, facts_df) -> ExtractedMetric:
        """Insurance ShortTermDebt: Standard approach."""
        return DefaultExtractor().extract_short_term_debt(xbrl, facts_df)
    
    def extract_policy_reserves(self, xbrl, facts_df) -> ExtractedMetric:
        """
        Insurance Policy Reserves: Primary liability measure.
        
        Maps: FuturePolicyBenefits + LiabilityForClaimsAndClaimsAdjustmentExpense
        
        These are debt equivalents for insurance valuation as they represent
        obligations to policyholders that must be fulfilled.
        """
        # Future policy benefits (life insurance, annuities)
        future_benefits = (
            self._get_fact_value(facts_df, 'LiabilityForFuturePolicyBenefits') or
            self._get_fact_value(facts_df, 'FuturePolicyBenefits') or
            0
        )
        
        # Claims reserves (P&C insurance)
        claims_reserve = (
            self._get_fact_value(facts_df, 'LiabilityForClaimsAndClaimsAdjustmentExpense') or
            self._get_fact_value(facts_df, 'LiabilityForUnpaidClaimsAndClaimsAdjustmentExpense') or
            0
        )
        
        # Unearned premiums (prepaid insurance)
        unearned = self._get_fact_value(facts_df, 'UnearnedPremiums') or 0
        
        total_reserves = future_benefits + claims_reserve + unearned
        
        return ExtractedMetric(
            standard_name="PolicyReserves",
            industry_counterpart="InsuranceLiabilities",
            xbrl_concept=None,
            value=total_reserves if total_reserves > 0 else None,
            extraction_method=ExtractionMethod.COMPOSITE,
            notes=f"Insurance reserves: FutureBenefits={future_benefits/1e9:.2f}B + Claims={claims_reserve/1e9:.2f}B + Unearned={unearned/1e9:.2f}B" if total_reserves > 0 else None
        )
    
    def extract_capex(self, xbrl, facts_df) -> ExtractedMetric:
        """Insurance Capex: Standard approach (minimal for insurers)."""
        return DefaultExtractor().extract_capex(xbrl, facts_df)
    
    def extract_operating_income(self, xbrl, facts_df) -> ExtractedMetric:
        """
        Insurance OperatingIncome: Underwriting Income.
        
        Formula: Premiums Earned - Claims & Benefits - Underwriting Expenses
        (Excludes investment income for operating comparison)
        """
        # Try direct underwriting income tag
        underwriting = self._get_fact_value(facts_df, 'UnderwritingIncomeLoss')
        if underwriting is not None:
            return ExtractedMetric(
                standard_name="OperatingIncome",
                industry_counterpart="UnderwritingIncome",
                xbrl_concept="us-gaap:UnderwritingIncomeLoss",
                value=underwriting,
                extraction_method=ExtractionMethod.DIRECT,
                notes="Insurance: Direct UnderwritingIncome tag"
            )
        
        # Calculate: Premiums - Losses - Expenses
        premiums = (
            self._get_fact_value(facts_df, 'PremiumsEarnedNet') or
            self._get_fact_value(facts_df, 'NetPremiumsEarned') or
            0
        )
        
        losses = (
            self._get_fact_value(facts_df, 'PolicyholderBenefitsAndClaimsIncurredNet') or
            self._get_fact_value(facts_df, 'BenefitsCostsAndExpenses') or
            0
        )
        
        if premiums > 0:
            underwriting_income = premiums - losses
            return ExtractedMetric(
                standard_name="OperatingIncome",
                industry_counterpart="UnderwritingIncome",
                xbrl_concept=None,
                value=underwriting_income,
                extraction_method=ExtractionMethod.CALCULATED,
                notes=f"Insurance: Premiums({premiums/1e9:.2f}B) - Losses({losses/1e9:.2f}B)"
            )
        
        # Fallback to default calculation
        return DefaultExtractor().extract_operating_income(xbrl, facts_df)


class EnergyExtractor(IndustryExtractor):
    """
    Energy-specific extraction logic (SIC 1300-1399, 2900-2999).
    
    Key differences from default:
    - Uses CostsAndExpenses aggregate (includes exploration, production)
    - Handles ExplorationExpense, DryHoleCosts explicitly
    - Revenue may use different tags (SalesRevenueNet common)
    """
    
    industry_name = "energy"
    
    def extract_short_term_debt(self, xbrl, facts_df) -> ExtractedMetric:
        """Energy ShortTermDebt: Standard approach."""
        return DefaultExtractor().extract_short_term_debt(xbrl, facts_df)
    
    def extract_capex(self, xbrl, facts_df) -> ExtractedMetric:
        """
        Energy Capex: Include exploration and development costs.
        """
        # Standard PP&E capex
        ppe_capex = self._get_fact_value(facts_df, 'PaymentsToAcquirePropertyPlantAndEquipment') or 0
        
        # Add exploration & development (common in O&G)
        exploration = self._get_fact_value(facts_df, 'PaymentsToExploreAndDevelopOilAndGasProperties') or 0
        
        total = ppe_capex + exploration
        
        return ExtractedMetric(
            standard_name="Capex",
            industry_counterpart="OilGasCapex",
            xbrl_concept=None,
            value=total if total > 0 else None,
            extraction_method=ExtractionMethod.COMPOSITE,
            notes=f"Energy: PPE({ppe_capex/1e9:.2f}B) + Exploration({exploration/1e9:.2f}B)" if total > 0 else None
        )
    
    def extract_operating_income(self, xbrl, facts_df) -> ExtractedMetric:
        """
        Energy OperatingIncome: Revenue - CostsAndExpenses approach.
        
        Energy companies often use:
        - Revenues aggregate
        - CostsAndExpenses aggregate (includes production, exploration, D&D)
        - OperatingCostsAndExpenses for production costs
        
        Formula: Revenue - CostsAndExpenses (if available)
        OR: Revenue - ProductionCosts - Exploration - D&D - SGA
        """
        # Try direct tag first
        val = self._get_fact_value(facts_df, 'OperatingIncomeLoss')
        if val is not None:
            return ExtractedMetric(
                standard_name="OperatingIncome",
                industry_counterpart=None,
                xbrl_concept="us-gaap:OperatingIncomeLoss",
                value=val,
                extraction_method=ExtractionMethod.DIRECT
            )
        
        # Get revenue - IMPORTANT: Energy sector often has gross vs net revenue difference
        # Prioritize net revenue (excludes assessed taxes, equity earnings) to match market data
        revenue = (
            self._get_fact_value(facts_df, 'RevenueFromContractWithCustomerExcludingAssessedTax') or  # Net (193.41B for CVX)
            self._get_fact_value(facts_df, 'SalesRevenueNet') or
            self._get_fact_value(facts_df, 'Revenues')  # Gross fallback (202.79B for CVX) - includes excise taxes
        )
        
        if revenue is None:
            return DefaultExtractor().extract_operating_income(xbrl, facts_df)
        
        # Energy Approach 1: Revenue - CostsAndExpenses (most complete)
        costs_and_expenses = self._get_fact_value(facts_df, 'CostsAndExpenses')
        if costs_and_expenses is not None:
            calculated = revenue - abs(costs_and_expenses)
            return ExtractedMetric(
                standard_name="OperatingIncome",
                industry_counterpart="EnergyOperatingIncome",
                xbrl_concept=None,
                value=calculated,
                extraction_method=ExtractionMethod.CALCULATED,
                notes=f"Energy: Revenue({revenue/1e9:.2f}B) - CostsAndExpenses({costs_and_expenses/1e9:.2f}B)"
            )
        
        # Energy Approach 2: Itemized costs
        cogs = self._get_fact_value(facts_df, 'CostOfGoodsAndServicesSold') or 0
        operating_costs = self._get_fact_value(facts_df, 'OperatingCostsAndExpenses') or 0
        exploration = self._get_fact_value(facts_df, 'ExplorationExpense') or 0
        sga = self._get_fact_value(facts_df, 'SellingGeneralAndAdministrativeExpense') or 0
        dda = self._get_fact_value(facts_df, 'DepreciationDepletionAndAmortization') or 0
        
        # Use the largest expense bucket + other items
        if operating_costs > 0:
            total_costs = operating_costs + exploration + sga
        else:
            total_costs = abs(cogs) + exploration + sga + dda
        
        calculated = revenue - total_costs
        return ExtractedMetric(
            standard_name="OperatingIncome",
            industry_counterpart="EnergyOperatingIncome",
            xbrl_concept=None,
            value=calculated,
            extraction_method=ExtractionMethod.CALCULATED,
            notes=f"Energy: Revenue - ItemizedCosts"
        )


# Registry of extractors by industry
EXTRACTORS = {
    'default': DefaultExtractor(),
    'banking': BankingExtractor(),
    'saas': SaaSExtractor(),
    'software': SaaSExtractor(),  # Alias
    'insurance': InsuranceExtractor(),
    'energy': EnergyExtractor(),
    'oil_gas': EnergyExtractor(),  # Alias for SIC codes
}


def get_industry_extractor(industry: str) -> IndustryExtractor:
    """Get the appropriate extractor for an industry."""
    return EXTRACTORS.get(industry.lower() if industry else 'default', EXTRACTORS['default'])
