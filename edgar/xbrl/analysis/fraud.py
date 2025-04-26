"""Financial fraud detection module.

This module provides tools for detecting potential financial fraud and anomalies:
- Benford's Law Analysis for digit distribution anomalies
- Altman Z-Score for bankruptcy risk
- Beneish M-Score for earnings manipulation
- Piotroski F-Score for financial strength
"""

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..standardization import StandardConcept
from .metrics import AltmanZScore, BeneishMScore, PiotroskiFScore


@dataclass
class BenfordResult:
    """Results from Benford's Law analysis."""
    observed_dist: Dict[int, float]  # Observed digit distribution
    expected_dist: Dict[int, float]  # Expected Benford distribution
    chi_square: float  # Chi-square statistic
    p_value: float    # P-value for goodness of fit
    anomalous: bool   # Whether distribution is significantly different
    
    def __repr__(self) -> str:
        return f"{'Anomalous' if self.anomalous else 'Normal'} (p={self.p_value:.3f})"

class FraudDetector:
    """Detect potential financial fraud using multiple methods."""
    
    def __init__(self, xbrl):
        """Initialize with an XBRL instance."""
        self.xbrl = xbrl
        self.altman = AltmanZScore(xbrl)
        self.beneish = BeneishMScore(xbrl)
        self.piotroski = PiotroskiFScore(xbrl)
    
    def analyze_digit_distribution(self, values: List[float], significance: float = 0.05) -> Optional[BenfordResult]:
        """Analyze digit distribution using Benford's Law.
        
        Args:
            values: List of numeric values to analyze
            significance: P-value threshold for anomaly detection
            
        Returns:
            BenfordResult with analysis results, or None if insufficient data
        """
        if len(values) < 10:  # Need reasonable sample size
            return None
            
        # Get first digits
        first_digits = [int(str(abs(float(v))).lstrip('0')[0]) for v in values if v != 0]
        if not first_digits:
            return None
            
        # Calculate observed distribution
        digit_counts = Counter(first_digits)
        total = len(first_digits)
        observed_dist = {d: digit_counts.get(d, 0) / total for d in range(1, 10)}
        
        # Calculate expected Benford distribution
        expected_dist = {d: math.log10(1 + 1/d) for d in range(1, 10)}
        
        # Perform chi-square test
        chi_square = 0
        for d in range(1, 10):
            expected = expected_dist[d] * total
            observed = digit_counts.get(d, 0)
            chi_square += (observed - expected) ** 2 / expected
            
        # Get p-value (8 degrees of freedom for digits 1-9)
        from scipy.stats import chi2
        p_value = 1 - chi2.cdf(chi_square, 8)
        
        return BenfordResult(
            observed_dist=observed_dist,
            expected_dist=expected_dist,
            chi_square=chi_square,
            p_value=p_value,
            anomalous=p_value < significance
        )
    
    def analyze_all(self) -> Dict[str, Any]:
        """Run all fraud detection analyses.
        
        Returns:
            Dict containing:
            - altman_z: Altman Z-Score results
            - beneish_m: Beneish M-Score results
            - piotroski_f: Piotroski F-Score results
            - benford: Benford's Law analysis results
        """
        # Get financial values for Benford analysis
        values = []
        for concept in [
            StandardConcept.TOTAL_ASSETS,
            StandardConcept.TOTAL_LIABILITIES,
            StandardConcept.TOTAL_EQUITY,
            StandardConcept.REVENUE,
            StandardConcept.NET_INCOME,
            StandardConcept.OPERATING_INCOME,
            StandardConcept.OPERATING_CASH_FLOW
        ]:
            if hasattr(self.xbrl.statements, 'balance_sheet'):
                bs_value = self.altman._get_value(concept)
                if bs_value:
                    values.append(bs_value)
            if hasattr(self.xbrl.statements, 'income_statement'):
                is_value = self.altman._get_value(concept, "IncomeStatement")
                if is_value:
                    values.append(is_value)
            if hasattr(self.xbrl.statements, 'cash_flow'):
                cf_value = self.altman._get_value(concept, "CashFlow")
                if cf_value:
                    values.append(cf_value)
        
        return {
            'altman_z': self.altman.calculate(),
            'beneish_m': self.beneish.calculate(),
            'piotroski_f': self.piotroski.calculate(),
            'benford': self.analyze_digit_distribution(values)
        }
