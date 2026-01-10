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
    
    def _get_fact_value(self, df, concept: str) -> Optional[float]:
        """Get the latest non-dimensional value for a concept."""
        if df is None or len(df) == 0:
            return None
        
        matches = df[df['concept'].str.contains(concept, case=False, na=False)]
        if len(matches) == 0:
            return None
        
        # Filter for non-dimensional (total) values
        if 'segment_label' in matches.columns:
            totals = matches[matches['segment_label'].isna() | (matches['segment_label'] == '')]
            if len(totals) > 0:
                matches = totals
        
        # Get latest period
        if 'period_key' in matches.columns:
            matches = matches.sort_values('period_key', ascending=False)
        
        if len(matches) > 0 and 'numeric_value' in matches.columns:
            val = matches.iloc[0]['numeric_value']
            if val is not None:
                return float(val)
        
        return None


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
        
        # Fallback: Calculate from components
        gross_profit = self._get_fact_value(facts_df, 'GrossProfit')
        rd = self._get_fact_value(facts_df, 'ResearchAndDevelopmentExpense')
        sga = self._get_fact_value(facts_df, 'SellingGeneralAndAdministrativeExpense')
        
        if gross_profit is not None and (rd is not None or sga is not None):
            calculated = gross_profit - (rd or 0) - (sga or 0)
            return ExtractedMetric(
                standard_name="OperatingIncome",
                industry_counterpart=None,
                xbrl_concept=None,
                value=calculated,
                extraction_method=ExtractionMethod.CALCULATED,
                notes="Calculated: GrossProfit - R&D - SGA"
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
        Bank ShortTermDebt: Exclude Repos and Fed Funds (operational funding).
        
        Logic:
        1. Try CommercialPaper + OtherShortTermBorrowings
        2. Else: ShortTermBorrowings - Repos - FedFunds
        """
        cp = self._get_fact_value(facts_df, 'CommercialPaper') or 0
        other = self._get_fact_value(facts_df, 'OtherShortTermBorrowings') or 0
        
        if cp > 0 or other > 0:
            return ExtractedMetric(
                standard_name="ShortTermDebt",
                industry_counterpart="CommercialPaper",
                xbrl_concept="us-gaap:CommercialPaper",
                value=cp + other,
                extraction_method=ExtractionMethod.COMPOSITE,
                notes="Bank: CommercialPaper + OtherBorrowings (excludes Repos)"
            )
        
        # Fallback: subtract operational funding
        total_borrowings = self._get_fact_value(facts_df, 'ShortTermBorrowings') or 0
        repos = self._get_fact_value(facts_df, 'SecuritiesSoldUnderAgreementsToRepurchase') or 0
        fed_funds = self._get_fact_value(facts_df, 'FederalFundsPurchased') or 0
        
        adjusted = total_borrowings - repos - fed_funds
        
        return ExtractedMetric(
            standard_name="ShortTermDebt",
            industry_counterpart="AdjustedShortTermBorrowings",
            xbrl_concept=None,
            value=adjusted if adjusted > 0 else None,
            extraction_method=ExtractionMethod.CALCULATED,
            notes="Bank: ShortTermBorrowings - Repos - FedFunds"
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


# Registry of extractors by industry
EXTRACTORS = {
    'default': DefaultExtractor(),
    'banking': BankingExtractor(),
    # Add more: 'insurance': InsuranceExtractor(), 'reits': REITExtractor()
}


def get_industry_extractor(industry: str) -> IndustryExtractor:
    """Get the appropriate extractor for an industry."""
    return EXTRACTORS.get(industry, EXTRACTORS['default'])
