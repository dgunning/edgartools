"""QuantEntityFacts - Extended EntityFacts with TTM calculation capability.

This wrapper class extends the core EntityFacts with additional methods
needed by the quant module, following the Soft Fork Protocol.
"""
from datetime import date
from typing import List, Optional

from edgar.entity.enhanced_statement import EnhancedStatementBuilder
from edgar.entity.entity_facts import EntityFacts

from .utils import TTMCalculator, TTMMetric


class QuantEntityFacts(EntityFacts):
    """Extended EntityFacts with TTM calculation capability.
    
    Wrapper class for use in quant module - does not modify core edgar/.
    Follows Soft Fork Protocol by extending rather than modifying.
    Overrides statement methods to ensure consistent behavior with QuantCompany.
    """

    def __init__(self, cik: int, name: str, facts: List, sic_code: Optional[int] = None):
        """Initialize QuantEntityFacts with company data.

        Args:
            cik: Central Index Key
            name: Company name
            facts: List of FinancialFact objects
            sic_code: Optional SIC code for industry classification

        """
        super().__init__(cik, name, facts, sic_code)
        self.sic = sic_code  # Ensure sic is available as 'sic' attribute

    def get_ttm(self, concept: str, as_of: Optional[date] = None) -> TTMMetric:
        """Calculate Trailing Twelve Months (TTM) value for a concept."""
        # Get facts for this concept using the parent class's index
        # This handles namespaces and other indexing details better than linear search
        concept_facts = self._fact_index['by_concept'].get(concept)

        if not concept_facts:
            # Try removing namespace if present
            if ':' in concept:
                local_name = concept.split(':')[1]
                concept_facts = self._fact_index['by_concept'].get(local_name)
            # Try adding us-gaap namespace if missing
            else:
                concept_facts = self._fact_index['by_concept'].get(f"us-gaap:{concept}")

        if not concept_facts:
            raise KeyError(f"Concept {concept} not found in facts")

        # Use TTMCalculator from quant.utils
        calc = TTMCalculator(concept_facts)
        return calc.calculate_ttm(as_of=as_of)

    def income_statement(self, periods: int = 4, annual: bool = False, **kwargs):
        """Get income statement (override uses EnhancedStatementBuilder explicitly)."""
        builder = EnhancedStatementBuilder(sic_code=self.sic)
        return builder.build_multi_period_statement(
            facts=self._facts,
            statement_type='IncomeStatement',
            periods=periods,
            annual=annual
        )

    def balance_sheet(self, periods: int = 4, annual: bool = False, **kwargs):
        """Get balance sheet (override uses EnhancedStatementBuilder explicitly)."""
        builder = EnhancedStatementBuilder(sic_code=self.sic)
        return builder.build_multi_period_statement(
            facts=self._facts,
            statement_type='BalanceSheet',
            periods=periods,
            annual=annual
        )

    def cash_flow(self, periods: int = 4, annual: bool = False, **kwargs):
        """Get cash flow (override uses EnhancedStatementBuilder explicitly)."""
        builder = EnhancedStatementBuilder(sic_code=self.sic)
        return builder.build_multi_period_statement(
            facts=self._facts,
            statement_type='CashFlow',
            periods=periods,
            annual=annual
        )
