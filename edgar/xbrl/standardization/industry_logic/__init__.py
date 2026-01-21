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
        Bank ShortTermDebt: yfinance-aligned (excludes Repos/FedFunds).
        
        Used for validation against yfinance.
        """
        # yfinance uses OtherShortTermBorrowings for banks
        other = self._get_fact_value(facts_df, 'OtherShortTermBorrowings')
        if other is not None and other > 0:
            return ExtractedMetric(
                standard_name="ShortTermDebt",
                industry_counterpart="OtherShortTermBorrowings",
                xbrl_concept="us-gaap:OtherShortTermBorrowings",
                value=other,
                extraction_method=ExtractionMethod.DIRECT,
                notes="Bank (yfinance-aligned): OtherShortTermBorrowings only"
            )
        
        # Fallback: CommercialPaper
        cp = self._get_fact_value(facts_df, 'CommercialPaper') or 0
        
        # Fallback: ShortTermBorrowings (standard tag used by JPM when Other is missing)
        stb = self._get_fact_value(facts_df, 'ShortTermBorrowings') or 0
        
        if stb > 0 and stb > cp:
             return ExtractedMetric(
                standard_name="ShortTermDebt",
                industry_counterpart="ShortTermBorrowings",
                xbrl_concept="us-gaap:ShortTermBorrowings",
                value=stb,
                extraction_method=ExtractionMethod.DIRECT,
                notes="Bank (yfinance-aligned): ShortTermBorrowings"
            )
        
        if cp > 0:
            return ExtractedMetric(
                standard_name="ShortTermDebt",
                industry_counterpart="CommercialPaper",
                xbrl_concept="us-gaap:CommercialPaper",
                value=cp,
                extraction_method=ExtractionMethod.DIRECT,
                notes="Bank (yfinance-aligned): CommercialPaper"
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
        Bank Cash: Prioritize CashAndDueFromBanks and similar liquid assets.
        Crucially helps avoid falling back to OCI/Hedge tags in the tree.
        """
        # 1. Try standard CashAndCashEquivalentsAtCarryingValue
        val = self._get_fact_value(facts_df, 'CashAndCashEquivalentsAtCarryingValue')
        if val is not None:
             return ExtractedMetric(
                standard_name="CashAndEquivalents",
                industry_counterpart="CashAndCashEquivalentsAtCarryingValue",
                xbrl_concept="us-gaap:CashAndCashEquivalentsAtCarryingValue",
                value=val,
                extraction_method=ExtractionMethod.DIRECT,
                notes="Bank: Standard CashAndCashEquivalentsAtCarryingValue"
            )
            
        # 2. Try simple CashAndCashEquivalents
        val = self._get_fact_value(facts_df, 'CashAndCashEquivalents')
        if val is not None:
             return ExtractedMetric(
                standard_name="CashAndEquivalents",
                industry_counterpart="CashAndCashEquivalents",
                xbrl_concept="us-gaap:CashAndCashEquivalents",
                value=val,
                extraction_method=ExtractionMethod.DIRECT,
                notes="Bank: Standard CashAndCashEquivalents"
            )
            
        # 3. Try CashAndDueFromBanks (Classic bank tag)
        # We sum with InterestBearingDepositsInBanks to approximate "Cash & Equivalents"
        val = self._get_fact_value(facts_df, 'CashAndDueFromBanks')
        if val is not None:
            ibd = self._get_fact_value(facts_df, 'InterestBearingDepositsInBanks') or 0
            total = val + ibd
            
            note = "Bank: CashAndDueFromBanks"
            if ibd > 0:
                note += " + InterestBearingDepositsInBanks"
                
            return ExtractedMetric(
                standard_name="CashAndEquivalents",
                industry_counterpart="CashAndDueFromBanks",
                xbrl_concept="us-gaap:CashAndDueFromBanks",
                value=total,
                extraction_method=ExtractionMethod.COMPOSITE if ibd > 0 else ExtractionMethod.DIRECT,
                notes=note
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
        Bank OperatingIncome: Use PPNR (Pre-Provision Net Revenue).
        
        Formula: NetInterestIncome + NonInterestIncome - NonInterestExpense
        """
        nii = self._get_fact_value(facts_df, 'InterestIncomeExpenseNet')
        if nii is None:
            nii = self._get_fact_value(facts_df, 'NetInterestIncome')
        
        non_int_income = self._get_fact_value(facts_df, 'NoninterestIncome')
        non_int_expense = self._get_fact_value(facts_df, 'NoninterestExpense')
        
        if nii is not None and non_int_income is not None and non_int_expense is not None:
            ppnr = nii + non_int_income - non_int_expense
            return ExtractedMetric(
                standard_name="OperatingIncome",
                industry_counterpart="PPNR",
                xbrl_concept=None,
                value=ppnr,
                extraction_method=ExtractionMethod.CALCULATED,
                notes="Bank: NII + NonIntIncome - NonIntExpense"
            )
        
        return ExtractedMetric(
            standard_name="OperatingIncome",
            industry_counterpart="PPNR",
            xbrl_concept=None,
            value=None,
            extraction_method=ExtractionMethod.CALCULATED
        )


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
