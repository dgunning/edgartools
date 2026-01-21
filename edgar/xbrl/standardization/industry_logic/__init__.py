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
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum


class ExtractionMethod(Enum):
    DIRECT = "direct"          # Single concept lookup
    COMPOSITE = "composite"    # Sum of multiple concepts
    CALCULATED = "calculated"  # Derived from other metrics
    MAPPED = "mapped"          # Industry counterpart mapping


@dataclass
class ExtractedMetric:
    """Result of metric extraction with full context."""
    standard_name: str              # e.g., "COGS"
    industry_counterpart: Optional[str]  # e.g., "InterestExpense" for banks
    xbrl_concept: Optional[str]     # e.g., "us-gaap:InterestExpense"
    value: Optional[float]
    extraction_method: ExtractionMethod
    notes: Optional[str] = None


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
    
    def extract_short_term_debt(self, xbrl, facts_df) -> ExtractedMetric:
        """
        Bank ShortTermDebt: Dual-track approach per architect guidance.
        
        Returns: yfinance-aligned value (excludes Repos) for validation.
        Use extract_short_term_debt_economic() for ground truth.
        """
        return self.extract_short_term_debt_yfinance(xbrl, facts_df)
    
    def extract_short_term_debt_yfinance(self, xbrl, facts_df) -> ExtractedMetric:
        """
        Bank ShortTermDebt: Street-aligned extraction (excludes Repos/FedFunds).
        
        Strategy (Per Analyst Guidance):
        1. Path A: Direct clean tag (OtherShortTermBorrowings - JPM style)
        2. Path B: Bottom-Up Construction (sum clean components - preferred for G-SIBs)
        3. Path C: Top-Down Subtraction (Aggregate - Repos/FedFunds)
        """
        # Path A: Direct clean tag (JPM-style)
        # ONLY use if OtherShortTermBorrowings == ShortTermBorrowings (meaning it's the total, not a component)
        other = self._get_fact_value(facts_df, 'OtherShortTermBorrowings')
        stb = self._get_fact_value(facts_df, 'ShortTermBorrowings')
        
        # Check if OtherShortTermBorrowings is the whole thing (JPM) or just a piece (Citi)
        if other is not None and other > 0:
            # If no aggregate or Other == Aggregate, use it (JPM pattern)
            if stb is None or abs(other - stb) < 1e6:  # Within $1M = same value
                return ExtractedMetric(
                    standard_name="ShortTermDebt",
                    industry_counterpart="OtherShortTermBorrowings",
                    xbrl_concept="us-gaap:OtherShortTermBorrowings",
                    value=other,
                    extraction_method=ExtractionMethod.DIRECT,
                    notes="Bank: OtherShortTermBorrowings (clean, equals aggregate)"
                )
            # If Other < Aggregate, Other is a component - skip to aggregate paths
        
        # Path B & C combined: Check if ShortTermBorrowings aggregate exists
        # If aggregate exists and is reasonable, use it (with/without subtraction)
        # If no aggregate OR aggregate is smaller than components, use bottom-up sum
        
        if stb is not None and stb > 0:
            # Path C: Top-Down (WFC/Citi style - use aggregate with potential subtraction)
            # Try NET repos tags first (comprehensive - avoid double counting)
            # Try NET tags first (comprehensive - avoid double counting)
            # WFC uses combined Repos+Loaned NET in balance sheet tag
            net_repos_tags = [
                'SecuritiesSoldUnderAgreementsToRepurchaseAndSecuritiesLoanedNetAmountInConsolidatedBalanceSheet',
                'SecuritiesLoanedAndSecuritiesSoldUnderAgreementToRepurchaseNetAmount',
            ]
            
            net_repos = None
            for tag in net_repos_tags:
                val = self._get_fact_value(facts_df, tag)
                if val is None:
                    val = self._get_fact_value_fuzzy(facts_df, tag.split('SecuritiesSold')[-1] if 'SecuritiesSold' in tag else tag)
                if val is not None:
                    net_repos = val
                    break
            
            if net_repos is not None:
                # Use NET tag exclusively (includes all components)
                net_value = stb - net_repos
                if net_value > 0:
                    return ExtractedMetric(
                        standard_name="ShortTermDebt",
                        industry_counterpart="ConstructedNetDebt",
                        xbrl_concept=None,
                        value=net_value,
                        extraction_method=ExtractionMethod.COMPOSITE,
                        notes=f"Bank: ShortTermBorrowings({stb/1e9:.1f}B) - Repos/Loaned(NET {net_repos/1e9:.1f}B) = {net_value/1e9:.1f}B"
                    )
            
            # Fallback: Try component tags if NET not found
            structure = {
                'add': [
                    'ShortTermBorrowings',
                ],
                'deduct': [
                    'SecuritiesSoldUnderAgreementsToRepurchase',
                    'FederalFundsPurchased',
                    'FederalFundsPurchasedAndSecuritiesSoldUnderAgreementsToRepurchase',
                ]
            }
            
            # Special Case: GS Foreign Currency Debt (Huge item, custom tag)
            # Use fuzzy match because exact string lookup proved fragile
            gs_hedge = self._get_fact_value_fuzzy(
                facts_df, 
                'ForeignCurrencyDenominatedDebtDesignatedAsForeignCurrencyHedge'
            )
            if gs_hedge and gs_hedge > 0:
                # Add to structure manually since structure dict expects exact match keys
                if structure.get('add'):
                    pass # We will add it to the constructed value below
            
            net_value = self._construct_net_metric(facts_df, structure)
            
            if gs_hedge:
                net_value = (net_value or 0) + gs_hedge

            # If subtraction decreased it or addition increased it significantly, use net value
            # Check for material difference (> 1%)
            if net_value is not None and net_value > 0 and abs(net_value - stb) > (stb * 0.01):
                return ExtractedMetric(
                    standard_name="ShortTermDebt",
                    industry_counterpart="ConstructedNetDebt",
                    xbrl_concept=None,
                    value=net_value,
                    extraction_method=ExtractionMethod.COMPOSITE,
                    notes=f"Bank: ShortTermBorrowings({stb/1e9:.1f}B) Adjusted = {net_value/1e9:.1f}B"
                )
            else:
                # No repos found or not material, use raw ShortTermBorrowings
                return ExtractedMetric(
                    standard_name="ShortTermDebt",
                    industry_counterpart="ShortTermBorrowings",
                    xbrl_concept="us-gaap:ShortTermBorrowings",
                    value=stb,
                    extraction_method=ExtractionMethod.DIRECT,
                    notes="Bank: ShortTermBorrowings"
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
    
    def extract_cash_and_equivalents(self, xbrl, facts_df) -> ExtractedMetric:
        """
        Bank Cash: Context-aware extraction with sanity check.
        
        Guardrail: Cash < 1% of Assets triggers fallback to bank-specific tags.
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
                        notes=f"Bank: CarryingValue({val/1e9:.1f}B) - Restricted({restricted/1e9:.1f}B)"
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
                notes="Bank: Standard CashAndCashEquivalentsAtCarryingValue"
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
                notes="Bank: Standard CashAndCashEquivalents"
            )
        
        # 3. Bank-specific: CashAndDueFromBanks + InterestBearingDeposits
        cash_due = self._get_fact_value(facts_df, 'CashAndDueFromBanks') or 0
        ibd = self._get_fact_value(facts_df, 'InterestBearingDepositsInBanks') or 0
        
        # Priority for Regional Banks (like USB):
        # 3a. Try CashAndDueFromBanks alone explicitly (common for Regionals)
        if cash_due > 0 and assets and cash_due / assets >= 0.01:
             return ExtractedMetric(
                standard_name="CashAndEquivalents",
                industry_counterpart="CashAndDueFromBanks",
                xbrl_concept="us-gaap:CashAndDueFromBanks",
                value=cash_due,
                extraction_method=ExtractionMethod.DIRECT,
                notes=f"Bank: CashAndDueFromBanks({cash_due/1e9:.1f}B)"
            )
        
        # 3b. Try Composite if needed
        if cash_due > 0 or ibd > 0:
            total = cash_due + ibd
            # Use this total if it's substantial (e.g. > 1% of assets)
            if assets and total / assets >= 0.01:
                 return ExtractedMetric(
                    standard_name="CashAndEquivalents",
                    industry_counterpart="CashDue+InterestBearDeps",
                    xbrl_concept="us-gaap:CashAndDueFromBanks",
                    value=total,
                    extraction_method=ExtractionMethod.COMPOSITE,
                    notes=f"Bank: CashDue({cash_due/1e9:.1f}B) + IntBearDeps({ibd/1e9:.1f}B)"
                )

        
        # Return empty metric to signal fallback
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
