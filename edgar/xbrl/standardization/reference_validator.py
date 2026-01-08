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
from .models import MappingResult, MappingSource, ConfidenceLevel, FailurePattern


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
    
    # Composite metrics: sum of multiple XBRL concepts
    # These metrics require summing components to match yfinance definition
    COMPOSITE_METRICS = {
        'IntangibleAssets': ['Goodwill', 'IntangibleAssetsNetExcludingGoodwill'],
        'ShortTermDebt': ['LongTermDebtCurrent', 'CommercialPaper', 'ShortTermBorrowings'],
    }
    
    def __init__(
        self,
        config: Optional[MappingConfig] = None,
        tolerance_pct: float = 15.0  # 15% tolerance for matching
    ):
        self.config = config or get_config()
        self.tolerance = tolerance_pct / 100.0
        self._yf_cache = {}  # Cache yfinance Stock objects by ticker
        
        if yf is None:
            print("Warning: yfinance not installed. Install with: pip install yfinance")
    
    def _get_stock(self, ticker: str):
        """
        Get yfinance Stock object with caching.
        
        Caches Stock objects to avoid redundant API calls when 
        validating after each layer.
        """
        if yf is None:
            return None
        
        if ticker not in self._yf_cache:
            self._yf_cache[ticker] = yf.Ticker(ticker)
        
        return self._yf_cache[ticker]
    
    def _get_tolerance_for_company(self, ticker: str) -> float:
        """
        Get validation tolerance for a specific company.
        
        Priority:
        1. Company-specific tolerance (validation_tolerance_pct)
        2. Industry-specific tolerance (from defaults.industry_tolerances)
        3. Default tolerance (self.tolerance)
        """
        company_config = self.config.get_company(ticker.upper())
        
        if company_config:
            # Check company-specific tolerance first
            if company_config.validation_tolerance_pct is not None:
                return company_config.validation_tolerance_pct / 100.0
            
            # Check industry-specific tolerance
            if company_config.industry:
                industry_tolerances = self.config.defaults.get('industry_tolerances', {})
                industry_tolerance = industry_tolerances.get(company_config.industry)
                if industry_tolerance is not None:
                    return industry_tolerance / 100.0
        
        # Fall back to default tolerance
        return self.tolerance
    
    def _check_dimensional_only(
        self,
        xbrl,
        concept: str
    ) -> Optional[Dict]:
        """
        Check if a concept has values ONLY with dimensions (no consolidated total).
        
        This helps identify cases like JPM's CommercialPaper which is reported
        only under dimensional contexts (e.g., "Beneficial interests issued by
        consolidated VIEs") with no non-dimensioned total.
        
        Args:
            xbrl: XBRL object
            concept: Concept name to check
            
        Returns:
            Dict with dimensional breakdown if concept is dimensional-only,
            None if concept has non-dimensioned values or doesn't exist.
        """
        try:
            concept_name = concept.replace('us-gaap:', '').replace('us-gaap_', '')
            facts = xbrl.facts
            df = facts.get_facts_by_concept(concept_name)
            
            if df is None or len(df) == 0:
                return None
            
            # Check for non-dimensioned and dimensioned values
            if 'full_dimension_label' not in df.columns:
                return None  # No dimension info available
            
            has_non_dim = len(df[df['full_dimension_label'].isna()]) > 0
            has_dim = len(df[df['full_dimension_label'].notna()]) > 0
            
            if has_dim and not has_non_dim:
                # This concept is ONLY reported with dimensions
                dim_rows = df[df['full_dimension_label'].notna()]
                return {
                    'concept': concept,
                    'dimensional_only': True,
                    'dimension_count': len(dim_rows),
                    'total_value': dim_rows['numeric_value'].sum() if 'numeric_value' in dim_rows.columns else None,
                    'dimensions': dim_rows[['full_dimension_label', 'numeric_value']].head(5).to_dict('records')
                }
            
            return None
            
        except Exception:
            return None
    
    def _classify_failure(
        self,
        xbrl,
        concept: str,
        ticker: str
    ) -> FailurePattern:
        """
        Classify why extraction failed for systematic handling.
        
        This enables the workflow to learn from failures by categorizing
        them into known patterns that can be automatically fixed.
        """
        try:
            concept_name = concept.replace('us-gaap:', '').replace('us-gaap_', '')
            
            # Check 1: Dimensional-only
            dim_check = self._check_dimensional_only(xbrl, concept)
            if dim_check:
                return FailurePattern.DIMENSIONAL_ONLY
            
            # Check 2: Amended filing
            if hasattr(self, '_current_filing') and self._current_filing:
                form = getattr(self._current_filing, 'form', '')
                if '/A' in str(form):
                    return FailurePattern.AMENDED_FILING
            
            # Check 3: Concept exists but no numeric value
            facts = xbrl.facts
            df = facts.get_facts_by_concept(concept_name)
            if df is not None and len(df) > 0:
                if 'numeric_value' in df.columns:
                    if df['numeric_value'].notna().sum() == 0:
                        return FailurePattern.NO_VALUE
                return FailurePattern.PERIOD_MISMATCH  # Has data but didn't match period
            
            # Check 4: Concept not in facts at all
            return FailurePattern.CONCEPT_NOT_IN_FACTS
            
        except Exception:
            return FailurePattern.UNKNOWN
    
    def _apply_fix_for_pattern(
        self,
        pattern: FailurePattern,
        xbrl,
        concept: str,
        ticker: str
    ) -> Optional[float]:
        """
        Apply known fix for classified failure pattern.
        
        Each pattern has a specific remediation strategy.
        """
        if pattern == FailurePattern.DIMENSIONAL_ONLY:
            return self._extract_dimensional_sum(xbrl, concept)
        
        elif pattern == FailurePattern.CONCEPT_NOT_IN_FACTS:
            # Try searching company facts API instead
            return self._extract_from_company_facts(ticker, concept)
        
        # Other patterns don't have automatic fixes yet
        return None
    
    def _extract_dimensional_sum(self, xbrl, concept: str) -> Optional[float]:
        """Extract sum of all dimensional values for a concept."""
        try:
            concept_name = concept.replace('us-gaap:', '').replace('us-gaap_', '')
            facts = xbrl.facts
            df = facts.get_facts_by_concept(concept_name)
            
            if df is None or len(df) == 0:
                return None
            
            if 'full_dimension_label' not in df.columns:
                return None
            
            dim_rows = df[df['full_dimension_label'].notna()]
            dim_rows = dim_rows[dim_rows['numeric_value'].notna()]
            
            if len(dim_rows) == 0:
                return None
            
            # Get latest period
            if 'period_key' in dim_rows.columns:
                dim_rows = dim_rows.sort_values('period_key', ascending=False)
                latest_period = dim_rows.iloc[0]['period_key']
                period_rows = dim_rows[dim_rows['period_key'] == latest_period]
                return float(period_rows['numeric_value'].sum())
            
            return float(dim_rows['numeric_value'].sum())
            
        except Exception:
            return None
    
    def _extract_from_company_facts(self, ticker: str, concept: str) -> Optional[float]:
        """Extract value from company facts API as fallback."""
        try:
            from edgar import Company
            concept_name = concept.replace('us-gaap:', '').replace('us-gaap_', '')
            
            c = Company(ticker)
            facts = c.get_facts()
            df = facts.to_dataframe()
            
            # Find matching concept
            matches = df[df['concept'].str.contains(concept_name, case=False, na=False)]
            if len(matches) > 0:
                # Get latest value
                matches = matches.sort_values('period', ascending=False)
                val = matches.iloc[0].get('value') or matches.iloc[0].get('numeric_value')
                if val is not None:
                    return float(val)
            return None
            
        except Exception:
            return None
    
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
        
        # Get yfinance data (cached)
        stock = self._get_stock(ticker)
        
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
                # Set context for pattern classification
                self._current_ticker = ticker
                # Check if metric is composite (sum of multiple concepts)
                if metric in self.COMPOSITE_METRICS:
                    self._current_metric = metric  # Set context for dimensional config lookup
                    xbrl_value = self._extract_composite_value(xbrl, metric)
                else:
                    self._current_metric = metric  # Set context for dimensional config lookup
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

            # Filter for EXACT concept match (get_facts_by_concept returns partial matches)
            # e.g., "Assets" query returns Assets, AssetsCurrent, AssetsNoncurrent, etc.
            if 'concept' in df.columns:
                # Build expected concept variations
                expected_concepts = [
                    f'us-gaap:{concept_name}',
                    f'us-gaap_{concept_name}',
                    concept_name,
                    # Company-specific prefixes
                    f'nvda:{concept_name}', f'nvda_{concept_name}',
                    f'tsla:{concept_name}', f'tsla_{concept_name}',
                    f'aapl:{concept_name}', f'aapl_{concept_name}',
                    f'msft:{concept_name}', f'msft_{concept_name}',
                    f'goog:{concept_name}', f'goog_{concept_name}',
                    f'amzn:{concept_name}', f'amzn_{concept_name}',
                    f'meta:{concept_name}', f'meta_{concept_name}',
                ]
                df = df[df['concept'].isin(expected_concepts)]

            if len(df) == 0:
                return None

            # Filter for non-dimensioned (total) values only
            if 'full_dimension_label' in df.columns:
                total_rows = df[df['full_dimension_label'].isna()]
                
                # Check if we're filtering out dimensional-only values
                if len(total_rows) == 0:
                    dim_rows = df[df['full_dimension_label'].notna()]
                    if len(dim_rows) > 0:
                        # Check if metric config allows dimensional inclusion
                        dim_config = None
                        if hasattr(self, '_current_metric') and self._current_metric:
                            metric_config = self.config.get_metric(self._current_metric)
                            if metric_config:
                                dim_config = metric_config.dimensional_handling
                        
                        if dim_config and dim_config.get('mode') == 'include_dimensional':
                            # Sum dimensional values as fallback
                            dim_rows = dim_rows[dim_rows['numeric_value'].notna()]
                            if len(dim_rows) > 0:
                                # Sort by period_key to get most recent
                                if 'period_key' in dim_rows.columns:
                                    dim_rows = dim_rows.sort_values('period_key', ascending=False)
                                # Get the latest period and sum all dimensional values for it
                                latest_period = dim_rows.iloc[0]['period_key'] if 'period_key' in dim_rows.columns else None
                                if latest_period:
                                    period_rows = dim_rows[dim_rows['period_key'] == latest_period]
                                    return float(period_rows['numeric_value'].sum())
                                else:
                                    return float(dim_rows['numeric_value'].sum())
                        
                        # Log this dimensional-only case for investigation
                        dim_sum = dim_rows['numeric_value'].sum() if 'numeric_value' in dim_rows.columns else None
                        warning = {
                            'concept': concept,
                            'dimensional_only': True,
                            'dimension_count': len(dim_rows),
                            'dimensional_sum': dim_sum,
                            'sample_dimensions': dim_rows['full_dimension_label'].head(3).tolist()
                        }
                        # Store warning for later retrieval
                        if not hasattr(self, '_dimensional_warnings'):
                            self._dimensional_warnings = {}
                        self._dimensional_warnings[concept] = warning
                    return None
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
            # Try auto-fix for known patterns
            if hasattr(self, '_current_ticker') and self._current_ticker:
                pattern = self._classify_failure(xbrl, concept, self._current_ticker)
                if pattern != FailurePattern.UNKNOWN:
                    fixed_value = self._apply_fix_for_pattern(pattern, xbrl, concept, self._current_ticker)
                    if fixed_value is not None:
                        return fixed_value
            return None
    
    def _extract_composite_value(
        self,
        xbrl,
        metric: str
    ) -> Optional[float]:
        """
        Extract composite metric value by summing component concepts.
        
        Used for metrics like IntangibleAssets = Goodwill + IntangibleAssetsNetExcludingGoodwill
        """
        if metric not in self.COMPOSITE_METRICS:
            return None
        
        components = self.COMPOSITE_METRICS[metric]
        total = 0.0
        found_any = False
        
        for component in components:
            value = self._extract_xbrl_value(xbrl, f"us-gaap:{component}")
            if value is not None:
                total += value
                found_any = True
        
        return total if found_any else None
    
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
        
        # Use company-specific tolerance if available
        tolerance = self._get_tolerance_for_company(ticker)
        is_match = variance <= tolerance
        
        return ValidationResult(
            metric=metric,
            company=ticker,
            xbrl_value=xbrl_value,
            reference_value=ref_value,
            is_valid=is_match,
            variance_pct=variance * 100,
            status="match" if is_match else "mismatch",
            notes=f"Variance: {variance*100:.1f}% (tolerance: {tolerance*100:.0f}%)" if not is_match else f"Used {tolerance*100:.0f}% tolerance"
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
        
        stock = self._get_stock(ticker)
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
    
    def get_dimensional_warnings(self) -> Dict[str, Dict]:
        """
        Get all dimensional-only warnings logged during validation.
        
        These are concepts that have values ONLY with dimensions,
        with no non-dimensioned (consolidated) total.
        
        Returns:
            Dict mapping concept name to warning details
        """
        return getattr(self, '_dimensional_warnings', {})
    
    def print_dimensional_warnings(self):
        """Print any dimensional-only warnings logged during validation."""
        warnings = self.get_dimensional_warnings()
        if not warnings:
            return
        
        print("\n" + "=" * 70)
        print("DIMENSIONAL-ONLY CONCEPTS DETECTED")
        print("=" * 70)
        print("These concepts have values ONLY with dimensions (no consolidated total):")
        print()
        
        for concept, info in warnings.items():
            dim_sum_b = info.get('dimensional_sum', 0) / 1e9 if info.get('dimensional_sum') else 0
            print(f"  {concept}:")
            print(f"    Dimensional values sum: ${dim_sum_b:.2f}B")
            print(f"    Dimension count: {info.get('dimension_count', 0)}")
            sample_dims = info.get('sample_dimensions', [])[:2]
            for dim in sample_dims:
                print(f"      - {dim[:60]}..." if len(dim) > 60 else f"      - {dim}")
        print()
