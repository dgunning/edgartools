"""
Internal Consistency Validator

Validates extracted XBRL values using accounting equations and calculation linkbase
relationships BEFORE external yfinance validation.

Key Principle:
- If internal validation passes but external fails → likely reference data issue
- If internal validation fails → potential extraction/mapping error

Accounting Equations Checked:
1. Balance Sheet: Assets = Liabilities + Equity
2. Income Statement: GrossProfit = Revenue - COGS
3. Income Statement: OperatingIncome = GrossProfit - OpEx
4. Cash Flow: FreeCashFlow = OperatingCashFlow - Capex
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum


class ValidationStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"  # Some components missing
    SKIP = "skip"  # Not enough data to validate


@dataclass
class EquationResult:
    """Result of a single equation validation."""
    equation_name: str
    lhs_name: str
    lhs_value: Optional[float]
    rhs_expression: str
    rhs_value: Optional[float]
    status: ValidationStatus
    variance_pct: Optional[float]
    notes: Optional[str] = None


@dataclass
class InternalValidationResult:
    """Overall internal validation result."""
    status: str  # VALID_INTERNAL, INVALID_INTERNAL, VALID_PARTIAL
    equation_results: Dict[str, EquationResult]
    passed_count: int
    failed_count: int
    partial_count: int
    notes: Optional[str] = None


class InternalConsistencyValidator:
    """
    Validates extracted values using XBRL calculation linkbase and accounting equations.
    
    Runs BEFORE external yfinance validation.
    If internal validation passes but external fails, the issue is likely
    in the reference data, not our extraction.
    
    Uses normalized values (signage corrected) as per Priority 4.
    """
    
    # Validation tolerance (internal equations should match closely)
    TOLERANCE = 0.05  # 5% for internal consistency
    
    # Accounting equation definitions
    # Format: (equation_name, lhs_concept, [(rhs_concept, sign), ...], equation_type)
    # sign: 1 = add, -1 = subtract
    ACCOUNTING_EQUATIONS = {
        # Balance Sheet Identity
        'balance_sheet_equation': {
            'lhs': 'TotalAssets',
            'rhs': [('TotalLiabilities', 1), ('StockholdersEquity', 1)],
            'operator': 'sum',
            'description': 'Assets = Liabilities + Equity'
        },
        
        # Income Statement Relationships
        'gross_profit_calc': {
            'lhs': 'GrossProfit',
            'rhs': [('Revenue', 1), ('COGS', -1)],
            'operator': 'calculate',
            'description': 'GrossProfit = Revenue - COGS'
        },
        'operating_income_calc': {
            'lhs': 'OperatingIncome',
            'rhs': [('GrossProfit', 1), ('SGA', -1), ('RnD', -1)],
            'operator': 'calculate',
            'description': 'OperatingIncome ≈ GrossProfit - SGA - R&D'
        },
        
        # Cash Flow Relationships
        'free_cash_flow_calc': {
            'lhs': 'FreeCashFlow',
            'rhs': [('OperatingCashFlow', 1), ('Capex', -1)],
            'operator': 'calculate',
            'description': 'FCF = OperatingCashFlow - Capex'
        },

        # Cross-statement: PretaxIncome >= NetIncome (taxes are non-negative)
        'pretax_ge_net_income': {
            'lhs': 'PretaxIncome',
            'rhs': [('NetIncome', 1)],
            'operator': 'calculate',
            'description': 'PretaxIncome >= NetIncome (tax reduces income)',
        },
    }
    
    def __init__(self, tolerance: float = 0.05):
        self.tolerance = tolerance
    
    def validate(
        self,
        extracted_values: Dict[str, float],
        normalized: bool = True
    ) -> Dict[str, EquationResult]:
        """
        Run accounting equation checks on extracted values.
        
        Args:
            extracted_values: Dict mapping metric names to extracted values
                              e.g., {'TotalAssets': 1000000, 'Revenue': 500000}
            normalized: If True, values have been signage-normalized
        
        Returns:
            Dict mapping equation name to EquationResult:
            - "pass": LHS = RHS within tolerance
            - "fail": LHS != RHS  
            - "partial": Some components missing
            - "skip": Not enough data to validate
        """
        results = {}
        
        for eq_name, eq_def in self.ACCOUNTING_EQUATIONS.items():
            result = self._validate_equation(eq_name, eq_def, extracted_values)
            results[eq_name] = result
        
        return results
    
    def _validate_equation(
        self,
        eq_name: str,
        eq_def: Dict,
        values: Dict[str, float]
    ) -> EquationResult:
        """Validate a single equation."""
        lhs_concept = eq_def['lhs']
        rhs_components = eq_def['rhs']
        
        # Get LHS value
        lhs_value = values.get(lhs_concept)
        
        # Calculate RHS
        rhs_value = 0.0
        missing_components = []
        
        for component, sign in rhs_components:
            comp_value = values.get(component)
            if comp_value is not None:
                rhs_value += sign * comp_value
            else:
                missing_components.append(component)
        
        # Build RHS expression string
        rhs_parts = []
        for component, sign in rhs_components:
            prefix = "" if sign > 0 else "-"
            rhs_parts.append(f"{prefix}{component}")
        rhs_expression = " + ".join(rhs_parts).replace("+ -", "- ")
        
        # Determine validation status
        if lhs_value is None:
            return EquationResult(
                equation_name=eq_name,
                lhs_name=lhs_concept,
                lhs_value=None,
                rhs_expression=rhs_expression,
                rhs_value=rhs_value if not missing_components else None,
                status=ValidationStatus.SKIP,
                variance_pct=None,
                notes=f"Missing LHS: {lhs_concept}"
            )
        
        if missing_components:
            return EquationResult(
                equation_name=eq_name,
                lhs_name=lhs_concept,
                lhs_value=lhs_value,
                rhs_expression=rhs_expression,
                rhs_value=None,
                status=ValidationStatus.PARTIAL,
                variance_pct=None,
                notes=f"Missing RHS components: {', '.join(missing_components)}"
            )
        
        # Calculate variance
        if rhs_value == 0:
            variance_pct = 100.0 if lhs_value != 0 else 0.0
        else:
            variance_pct = abs(lhs_value - rhs_value) / abs(rhs_value) * 100
        
        is_pass = variance_pct <= self.tolerance * 100
        
        return EquationResult(
            equation_name=eq_name,
            lhs_name=lhs_concept,
            lhs_value=lhs_value,
            rhs_expression=rhs_expression,
            rhs_value=rhs_value,
            status=ValidationStatus.PASS if is_pass else ValidationStatus.FAIL,
            variance_pct=variance_pct,
            notes=f"Variance: {variance_pct:.1f}% (tolerance: {self.tolerance*100:.0f}%)"
        )
    
    def get_internal_validity(
        self,
        extracted_values: Dict[str, float]
    ) -> InternalValidationResult:
        """
        Get overall internal validity status.
        
        Returns:
            InternalValidationResult with:
            - "VALID_INTERNAL": All equations pass
            - "VALID_PARTIAL": Some equations pass, some missing data
            - "INVALID_INTERNAL": Equation failures detected
        """
        equation_results = self.validate(extracted_values)
        
        passed = sum(1 for r in equation_results.values() if r.status == ValidationStatus.PASS)
        failed = sum(1 for r in equation_results.values() if r.status == ValidationStatus.FAIL)
        partial = sum(1 for r in equation_results.values() if r.status == ValidationStatus.PARTIAL)
        skipped = sum(1 for r in equation_results.values() if r.status == ValidationStatus.SKIP)
        
        # Determine overall status
        if failed > 0:
            status = "INVALID_INTERNAL"
            notes = f"Failed {failed} equation(s)"
        elif passed > 0 and partial == 0 and skipped == 0:
            status = "VALID_INTERNAL"
            notes = f"All {passed} equations pass"
        elif passed > 0:
            status = "VALID_PARTIAL"
            notes = f"{passed} pass, {partial + skipped} incomplete"
        else:
            status = "VALID_PARTIAL"
            notes = "Insufficient data for validation"
        
        return InternalValidationResult(
            status=status,
            equation_results=equation_results,
            passed_count=passed,
            failed_count=failed,
            partial_count=partial,
            notes=notes
        )
    
    def explain_mismatch(
        self,
        internal_result: InternalValidationResult,
        external_status: str
    ) -> str:
        """
        Explain when internal and external validations disagree.
        
        This helps identify whether issues are in our extraction or reference data.
        """
        if internal_result.status == "VALID_INTERNAL" and external_status == "invalid":
            return (
                "VALID_INTERNAL_MISMATCH: Internal accounting equations pass but "
                "external validation fails. This suggests the reference data (yfinance) "
                "may be using different calculation methods or have stale data."
            )
        elif internal_result.status == "INVALID_INTERNAL" and external_status == "valid":
            return (
                "WARNING: Internal equations fail but external validation passes. "
                "This may indicate inconsistent XBRL filing or extraction issues."
            )
        elif internal_result.status == "INVALID_INTERNAL" and external_status == "invalid":
            return (
                "CONFIRMED_INVALID: Both internal and external validation fail. "
                "Extraction likely has issues - review mapping."
            )
        else:
            return f"Internal: {internal_result.status}, External: {external_status}"

    @staticmethod
    def compute_concept_consensus(
        all_results: Dict[str, Dict],
        metric: str,
    ) -> Dict[str, int]:
        """
        Count how often each XBRL concept is used for a metric across companies.

        Returns dict mapping concept name to count. Useful for detecting outliers:
        if 90% of tech companies use us-gaap:Revenues for Revenue but one uses
        us-gaap:SalesRevenueNet, that outlier deserves investigation.
        """
        concept_counts: Dict[str, int] = {}
        for ticker, metrics in all_results.items():
            result = metrics.get(metric)
            if result is None:
                continue
            concept = getattr(result, 'concept', None)
            if concept:
                concept_counts[concept] = concept_counts.get(concept, 0) + 1
        return concept_counts
