from typing import Optional, Union, List
from datetime import date
import pandas as pd

from edgar import Company
from edgar.entity.entity_facts import EntityFacts
from edgar.entity.enhanced_statement import EnhancedStatementBuilder
from edgar.entity.models import FinancialFact

from .utils import (
    TTMCalculator,
    TTMStatementBuilder,
    TTMMetric,
    detect_splits,
    apply_split_adjustments,
)

class QuantCompany(Company):
    """
    A Company subclass with advanced quantitative features:
    - Trailing Twelve Months (TTM) calculations
    - Automatic Stock Split adjustments
    - Robust Quarterly Data (Q4 derivation)
    """

    def _get_adjusted_facts(self) -> List[FinancialFact]:
        """
        Get all facts, adjusted for stock splits.
        """
        # Access the raw facts from the parent Company -> EntityFacts wrapper
        # Company.facts returns an EntityFacts object.
        # EntityFacts._facts is the list of FinancialFact.
        ef = self.facts
        if not ef or not ef._facts:
            return []
        
        facts = ef._facts
        
        # Apply split adjustments
        splits = detect_splits(facts)
        if splits:
            facts = apply_split_adjustments(facts, splits)
            
        return facts

    def _prepare_quarterly_facts(self, facts: List[FinancialFact]) -> List[FinancialFact]:
        """
        Enhance facts with derived Q4 data for quarterly analysis.
        """
        # Group by concept
        from collections import defaultdict
        concept_facts = defaultdict(list)
        for f in facts:
            concept_facts[f.concept].append(f)

        derived_facts = []
        
        # Attempt to derive quarterly data for every concept
        # Attempt to derive quarterly data for every concept
        for concept, c_facts in concept_facts.items():
            try:
                calc = TTMCalculator(c_facts)
                # quarterize_facts returns reported quarters + derived quarters (Q2, Q3, Q4)
                quarterly = calc._quarterize_facts()
                
                # We only want to add the derived ones that might be missing from the original list
                for qf in quarterly:
                    if qf.calculation_context and 'derived' in qf.calculation_context:
                        derived_facts.append(qf)
                        
            except Exception as e:
                continue

        # Derive EPS for Q4 using Net Income and Shares
        def _collect_facts(concepts: List[str]) -> List[FinancialFact]:
            collected = []
            for name in concepts:
                if name in concept_facts:
                    collected.extend(concept_facts[name])
                prefixed = f"us-gaap:{name}"
                if prefixed in concept_facts:
                    collected.extend(concept_facts[prefixed])
            return collected

        net_income_facts = _collect_facts([
            "NetIncomeLoss",
            "NetIncomeLossAvailableToCommonStockholdersBasic",
        ])

        shares_basic_facts = _collect_facts([
            "WeightedAverageNumberOfSharesOutstandingBasic",
            "WeightedAverageNumberOfSharesOutstandingBasicAndDiluted",
        ])
        shares_diluted_facts = _collect_facts([
            "WeightedAverageNumberOfDilutedSharesOutstanding",
            "WeightedAverageNumberOfSharesOutstandingDiluted",
        ])

        if net_income_facts and shares_basic_facts:
            calc = TTMCalculator(net_income_facts)
            derived_facts.extend(
                calc.derive_eps_for_quarter(
                    net_income_facts,
                    shares_basic_facts,
                    eps_concept="us-gaap:EarningsPerShareBasic",
                )
            )

        if net_income_facts and shares_diluted_facts:
            calc = TTMCalculator(net_income_facts)
            derived_facts.extend(
                calc.derive_eps_for_quarter(
                    net_income_facts,
                    shares_diluted_facts,
                    eps_concept="us-gaap:EarningsPerShareDiluted",
                )
            )

        return facts + derived_facts

    def income_statement(
        self, 
        periods: int = 4, 
        period: str = 'annual', 
        annual: Optional[bool] = None, 
        as_dataframe: bool = False, 
        concise_format: bool = False
    ):
        """
        Get income statement data.
        
        Args:
            period: 'annual', 'quarterly', or 'ttm'
            annual: Legacy parameter (overrides period if True)
        """
        # Handle legacy param
        if annual is not None:
            period = 'annual' if annual else 'quarterly'
            
        facts = self._get_adjusted_facts()
        
        if period == 'ttm':
            # Use TTM Builder
            # Enhance facts with derived quarters so the structure builder sees them
            facts = self._prepare_quarterly_facts(facts)

            # Use QuantEntityFacts wrapper (extends EntityFacts with get_ttm)
            from .entity_facts_wrapper import QuantEntityFacts
            temp_ef = QuantEntityFacts(self.cik, self.name, facts=facts, sic_code=self.sic)
            
            builder = TTMStatementBuilder(temp_ef)
            stmt = builder.build_income_statement()
            
            if as_dataframe:
                return stmt.to_dataframe()
            return stmt

        elif period == 'quarterly':
            # Enhance with derived quarters
            facts = self._prepare_quarterly_facts(facts)
            
        # Standard Builder
        builder = EnhancedStatementBuilder(sic_code=self.sic)
        stmt = builder.build_multi_period_statement(
            facts=facts,
            statement_type='IncomeStatement',
            periods=periods,
            annual=(period == 'annual')
        )
        
        if as_dataframe:
            return stmt.to_dataframe()
        return stmt

    def balance_sheet(
        self, 
        periods: int = 4, 
        period: str = 'annual', 
        annual: Optional[bool] = None, 
        as_dataframe: bool = False, 
        concise_format: bool = False
    ):
        if annual is not None:
            period = 'annual' if annual else 'quarterly'
            
        if period == 'ttm':
            raise ValueError("TTM not applicable for Balance Sheet")
            
        facts = self._get_adjusted_facts()
        
        # No Q4 derivation needed for Balance Sheet usually (point in time), 
        # but quarterly derivation might help if companies only report FY? 
        # Usually BS is explicit.
        
        builder = EnhancedStatementBuilder(sic_code=self.sic)
        stmt = builder.build_multi_period_statement(
            facts=facts,
            statement_type='BalanceSheet',
            periods=periods,
            annual=(period == 'annual')
        )
        
        if as_dataframe:
            return stmt.to_dataframe()
        return stmt

    def cash_flow(
        self, 
        periods: int = 4, 
        period: str = 'annual', 
        annual: Optional[bool] = None, 
        as_dataframe: bool = False, 
        concise_format: bool = False
    ):
        if annual is not None:
            period = 'annual' if annual else 'quarterly'
            
        facts = self._get_adjusted_facts()
        
        if period == 'ttm':
            from .entity_facts_wrapper import QuantEntityFacts
            temp_ef = QuantEntityFacts(self.cik, self.name, facts=facts, sic_code=self.sic)
            builder = TTMStatementBuilder(temp_ef)
            stmt = builder.build_cashflow_statement()
            if as_dataframe:
                return stmt.to_dataframe()
            return stmt
            
        elif period == 'quarterly':
            facts = self._prepare_quarterly_facts(facts)
            
        builder = EnhancedStatementBuilder(sic_code=self.sic)
        stmt = builder.build_multi_period_statement(
            facts=facts,
            statement_type='CashFlow',
            periods=periods,
            annual=(period == 'annual')
        )
        
        if as_dataframe:
            return stmt.to_dataframe()
        return stmt

    # -------------------------------------------------------------------------
    # TTM Convenience Methods
    # -------------------------------------------------------------------------
    
    def _parse_as_of(self, as_of: Union[date, str, None]) -> Optional[date]:
        if as_of is None or isinstance(as_of, date):
            return as_of
        
        if isinstance(as_of, str):
            # Simple parser: YYYY-MM-DD or YYYY-QN
            # If YYYY-QN, map to approx end date
            try:
                if '-' in as_of and len(as_of.split('-')) == 3:
                    return date.fromisoformat(as_of)
                
                # Handle YYYY-QN
                parts = as_of.upper().split('-')
                if len(parts) == 2 and 'Q' in parts[1]:
                    year = int(parts[0])
                    q = int(parts[1].replace('Q', ''))
                    # Approximate end dates: Q1=Mar, Q2=Jun, Q3=Sep, Q4=Dec
                    months = {1: 3, 2: 6, 3: 9, 4: 12}
                    return date(year, months.get(q, 12), 30 if months.get(q)==6 or months.get(q)==9 else 31)
            except Exception:
                pass
        return None

    def get_ttm(self, concept: str, as_of: Optional[Union[date, str]] = None) -> TTMMetric:
        """Calculate TTM value for a concept."""
        facts = self._get_adjusted_facts()
        
        # Filter facts for concept
        # Concept name might need normalization (us-gaap prefix)
        if ':' not in concept:
            concept_candidates = [concept, f'us-gaap:{concept}']
        else:
            concept_candidates = [concept]
            
        target_facts = [f for f in facts if f.concept in concept_candidates]
        
        if not target_facts:
            raise KeyError(f"Concept {concept} not found")
            
        calc = TTMCalculator(target_facts)
        
        as_of_date = self._parse_as_of(as_of)
        
        return calc.calculate_ttm(as_of=as_of_date) 

    def get_ttm_revenue(self):
        # Simply try a few common revenue concepts
        for c in ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues', 'SalesRevenueNet', 'Revenue']:
            try:
                return self.get_ttm(c)
            except KeyError:
                continue
        raise KeyError("Could not find Revenue concept")

    def get_ttm_net_income(self):
        for c in ['NetIncomeLoss', 'NetIncome', 'ProfitLoss']:
            try:
                return self.get_ttm(c)
            except KeyError:
                continue
        raise KeyError("Could not find Net Income concept")
