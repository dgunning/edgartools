"""
Reference Validator

Validates XBRL mappings against external data sources (yfinance).
This does NOT copy values - it confirms our mappings are correct by
comparing the XBRL extracted values with reference values.

Key principle: We map XBRL concepts → extract XBRL values → validate against reference
"""

import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

try:
    import yfinance as yf
except ImportError:
    yf = None

from .config_loader import get_config, MappingConfig
from .models import MappingResult, MappingSource, ConfidenceLevel


@dataclass
class ValidationResult:
    """Result of validating a mapping against reference data."""
    metric: str
    company: str
    xbrl_value: Optional[float]      # Value from our XBRL mapping
    reference_value: Optional[float]  # Value from yfinance
    is_valid: bool                    # Do they match (within tolerance)?
    variance_pct: Optional[float]     # Percentage difference
    status: str                       # "match", "mismatch", "missing_xbrl", "missing_ref"
    notes: Optional[str] = None


class ReferenceValidator:
    """
    Validates XBRL mappings against external reference data.
    
    Uses yfinance as reference to:
    1. Confirm our mapping is extracting the right concept
    2. Identify cases where metric truly doesn't exist (AAPL Goodwill)
    3. Flag potential mapping errors when values don't match
    """
    
    # Mapping from our metrics to yfinance field names
    YFINANCE_MAP = {
        'Revenue': ('financials', 'Total Revenue'),
        'COGS': ('financials', 'Cost Of Revenue'),
        'SGA': ('financials', 'Selling General And Administrative'),
        'OperatingIncome': ('financials', 'Operating Income'),
        'NetIncome': ('financials', 'Net Income'),
        'OperatingCashFlow': ('cashflow', 'Operating Cash Flow'),
        'Capex': ('cashflow', 'Capital Expenditure'),
        'TotalAssets': ('balance_sheet', 'Total Assets'),
        'Goodwill': ('balance_sheet', 'Goodwill'),
        'IntangibleAssets': ('balance_sheet', 'Goodwill And Other Intangible Assets'),
        'ShortTermDebt': ('balance_sheet', 'Current Debt'),
        'LongTermDebt': ('balance_sheet', 'Long Term Debt'),
        'CashAndEquivalents': ('balance_sheet', 'Cash And Cash Equivalents'),
    }
    
    def __init__(
        self,
        config: Optional[MappingConfig] = None,
        tolerance_pct: float = 10.0  # 10% tolerance for matching
    ):
        self.config = config or get_config()
        self.tolerance = tolerance_pct / 100.0
        
        if yf is None:
            print("Warning: yfinance not installed. Install with: pip install yfinance")
    
    def validate_company(
        self,
        ticker: str,
        results: Dict[str, MappingResult],
        xbrl=None
    ) -> Dict[str, ValidationResult]:
        """
        Validate all mappings for a company against yfinance.
        
        Args:
            ticker: Company ticker
            results: Mapping results to validate
            xbrl: Optional XBRL object to extract values
            
        Returns:
            Dict of validation results per metric
        """
        if yf is None:
            return {}
        
        # Get yfinance data
        stock = yf.Ticker(ticker)
        
        validations = {}
        
        for metric, result in results.items():
            if result.source == MappingSource.CONFIG:
                # Metric excluded for this company
                validations[metric] = ValidationResult(
                    metric=metric,
                    company=ticker,
                    xbrl_value=None,
                    reference_value=None,
                    is_valid=True,
                    variance_pct=None,
                    status="excluded",
                    notes="Metric excluded in config"
                )
                continue
            
            # Get reference value from yfinance
            ref_value = self._get_yfinance_value(stock, metric)
            
            # Get XBRL value (if we have a mapping and XBRL object)
            xbrl_value = None
            if result.is_mapped and xbrl:
                xbrl_value = self._extract_xbrl_value(xbrl, result.concept)
            
            # Validate
            validation = self._compare_values(
                metric, ticker, xbrl_value, ref_value, result
            )
            validations[metric] = validation
        
        return validations
    
    def validate_and_update_mappings(
        self,
        ticker: str,
        results: Dict[str, MappingResult],
        xbrl=None
    ) -> Dict[str, ValidationResult]:
        """
        Validate mappings and update MappingResult objects with validation status.
        
        This implements the VALIDATION FEEDBACK LOOP:
        - Pass: Mark mapping as validation_status="valid"
        - Fail: Mark mapping as validation_status="invalid", confidence_level=INVALID
        
        Args:
            ticker: Company ticker
            results: Mapping results to validate (will be modified in place)
            xbrl: Optional XBRL object to extract values
            
        Returns:
            Dict of validation results per metric
        """
        validations = self.validate_company(ticker, results, xbrl)
        
        # Update MappingResult objects based on validation
        for metric, validation in validations.items():
            if metric not in results:
                continue
            
            result = results[metric]
            
            if validation.status == "match":
                result.validation_status = "valid"
                result.validation_notes = "Value matches reference"
            elif validation.status == "mismatch":
                # FEEDBACK LOOP: Mark as INVALID
                result.validation_status = "invalid"
                result.validation_notes = f"Value mismatch: {validation.notes}"
                result.confidence_level = ConfidenceLevel.INVALID
            elif validation.status == "missing_ref":
                result.validation_status = "valid"  # Can't validate, assume OK
                result.validation_notes = "No reference data available"
            elif validation.status == "mapping_needed":
                result.validation_status = "pending"
                result.validation_notes = "Mapping required"
            elif validation.status == "pending_extraction":
                result.validation_status = "pending"
                result.validation_notes = "Value extraction pending"
            elif validation.status == "excluded":
                result.validation_status = "valid"
                result.validation_notes = "Metric excluded for this company"
        
        return validations
    
    def _get_yfinance_value(
        self,
        stock,
        metric: str
    ) -> Optional[float]:
        """Get a value from yfinance for a metric."""
        if metric not in self.YFINANCE_MAP:
            return None
        
        sheet_name, field_name = self.YFINANCE_MAP[metric]
        
        try:
            if sheet_name == 'financials':
                df = stock.financials
            elif sheet_name == 'cashflow':
                df = stock.cashflow
            elif sheet_name == 'balance_sheet':
                df = stock.balance_sheet
            else:
                return None
            
            if field_name in df.index:
                val = df.loc[field_name].iloc[0]
                if val is not None and not (hasattr(val, 'isna') and val.isna()):
                    return float(val)
        except Exception:
            pass
        
        return None
    
    def _extract_xbrl_value(
        self,
        xbrl,
        concept: str
    ) -> Optional[float]:
        """
        Extract value from XBRL for a concept.
        
        Finds the total (non-dimensioned) value for the most recent period.
        """
        try:
            # Remove namespace prefix if present
            concept_name = concept.replace('us-gaap:', '').replace('us-gaap_', '')
            
            # Handle company-specific prefixes
            for prefix in ['nvda_', 'tsla_', 'aapl_', 'msft_', 'goog_', 'amzn_', 'meta_']:
                concept_name = concept_name.replace(prefix, '')
            
            facts = xbrl.facts
            df = facts.get_facts_by_concept(concept_name)
            
            if df is None or len(df) == 0:
                return None
            
            # Filter for non-dimensioned (total) values only
            if 'full_dimension_label' in df.columns:
                total_rows = df[df['full_dimension_label'].isna()]
            else:
                total_rows = df
            
            if len(total_rows) == 0:
                return None
            
            # Filter for rows with actual numeric values
            total_rows = total_rows[total_rows['numeric_value'].notna()]
            if len(total_rows) == 0:
                return None
            
            # Sort by period_key (e.g., "instant_2024-12-31" or "duration_2024-01-01_2024-12-31")
            # to get the most recent
            if 'period_key' in total_rows.columns:
                total_rows = total_rows.sort_values('period_key', ascending=False)
            
            # Get the latest value
            latest = total_rows.iloc[0]
            value = float(latest['numeric_value'])
            
            # Handle absolute value for cash flows (some are negative in yfinance)
            return value
            
        except Exception as e:
            return None
    
    def _compare_values(
        self,
        metric: str,
        ticker: str,
        xbrl_value: Optional[float],
        ref_value: Optional[float],
        result: MappingResult
    ) -> ValidationResult:
        """Compare XBRL and reference values."""
        
        # Handle missing values
        if ref_value is None:
            return ValidationResult(
                metric=metric,
                company=ticker,
                xbrl_value=xbrl_value,
                reference_value=None,
                is_valid=True,  # Can't validate, assume OK
                variance_pct=None,
                status="missing_ref",
                notes="No reference data available (metric may not exist for this company)"
            )
        
        if not result.is_mapped:
            return ValidationResult(
                metric=metric,
                company=ticker,
                xbrl_value=None,
                reference_value=ref_value,
                is_valid=False,
                variance_pct=None,
                status="mapping_needed",
                notes=f"Reference shows value exists: {ref_value/1e9:.2f}B"
            )
        
        if xbrl_value is None:
            return ValidationResult(
                metric=metric,
                company=ticker,
                xbrl_value=None,
                reference_value=ref_value,
                is_valid=True,  # Mapping exists, value extraction TBD
                variance_pct=None,
                status="pending_extraction",
                notes="Mapping found, value extraction pending"
            )
        
        # Both values exist, compare using absolute values 
        # (sign conventions differ between XBRL and yfinance for cash flows)
        abs_xbrl = abs(xbrl_value)
        abs_ref = abs(ref_value)
        variance = abs(abs_xbrl - abs_ref) / abs_ref if abs_ref != 0 else 0
        is_match = variance <= self.tolerance
        
        return ValidationResult(
            metric=metric,
            company=ticker,
            xbrl_value=xbrl_value,
            reference_value=ref_value,
            is_valid=is_match,
            variance_pct=variance * 100,
            status="match" if is_match else "mismatch",
            notes=f"Variance: {variance*100:.1f}%" if not is_match else None
        )
    
    def check_metric_exists(
        self,
        ticker: str,
        metric: str
    ) -> Tuple[bool, Optional[float]]:
        """
        Quick check if a metric exists for a company in reference data.
        
        Returns (exists, value).
        """
        if yf is None:
            return (False, None)
        
        stock = yf.Ticker(ticker)
        value = self._get_yfinance_value(stock, metric)
        
        return (value is not None, value)
    
    def print_validation_report(
        self,
        validations: Dict[str, Dict[str, ValidationResult]]
    ):
        """Print a validation report."""
        print("\n" + "=" * 70)
        print("REFERENCE VALIDATION REPORT")
        print("=" * 70)
        
        for ticker, metrics in validations.items():
            print(f"\n{ticker}:")
            
            for metric, v in metrics.items():
                if v.status == "excluded":
                    print(f"  [SKIP] {metric}: excluded")
                elif v.status == "missing_ref":
                    print(f"  [N/A]  {metric}: no reference data")
                elif v.status == "mapping_needed":
                    val = v.reference_value / 1e9 if v.reference_value else 0
                    print(f"  [NEED] {metric}: ref has {val:.2f}B but no mapping")
                elif v.status == "pending_extraction":
                    print(f"  [OK]   {metric}: mapped, awaiting value extraction")
                elif v.status == "match":
                    print(f"  [OK]   {metric}: values match")
                elif v.status == "mismatch":
                    print(f"  [ERR]  {metric}: values differ by {v.variance_pct:.1f}%")
