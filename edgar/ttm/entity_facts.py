"""TTMEntityFacts - Extended EntityFacts with TTM calculation capability.

This wrapper class extends the core EntityFacts with the get_ttm() method
for calculating Trailing Twelve Months values.
"""
from datetime import date
from typing import List, Optional

from edgar.entity.entity_facts import EntityFacts

from edgar.ttm.calculator import TTMCalculator, TTMMetric


class TTMEntityFacts(EntityFacts):
    """Extended EntityFacts with TTM calculation capability.

    Adds get_ttm() method to calculate Trailing Twelve Months values.
    Inherits all statement methods (income_statement, balance_sheet, cash_flow) from EntityFacts.
    """

    def __init__(self, cik: int, name: str, facts: List, sic_code: Optional[int] = None):
        """Initialize TTMEntityFacts with company data.

        Args:
            cik: Central Index Key
            name: Company name
            facts: List of FinancialFact objects
            sic_code: Optional SIC code for industry classification

        """
        super().__init__(cik, name, facts, sic_code)

    def get_ttm(self, concept: str, as_of: Optional[date] = None) -> TTMMetric:
        """Calculate Trailing Twelve Months (TTM) value for a concept.

        Args:
            concept: XBRL concept name (e.g., 'Revenues', 'us-gaap:NetIncomeLoss')
            as_of: Calculate TTM as of this date (None = most recent)

        Returns:
            TTMMetric with value, periods, and metadata

        Raises:
            KeyError: If concept not found in facts

        """
        # Get facts for this concept using the parent class's index
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

        calc = TTMCalculator(concept_facts)
        return calc.calculate_ttm(as_of=as_of)
