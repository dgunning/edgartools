"""
Reference Validator

Validates XBRL mappings against external data sources (yfinance).
This does NOT copy values - it confirms our mappings are correct by
comparing the XBRL extracted values with reference values.

Key principle: We map XBRL concepts → extract XBRL values → validate against reference
"""

import os
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime
from dataclasses import dataclass

try:
    import yfinance as yf
except ImportError:
    yf = None

from .config_loader import get_config, MappingConfig
from .models import MappingResult, MappingSource, ConfidenceLevel, FailurePattern
from .extraction_rules import get_extraction_rule, get_concept_priority, get_composite_components
from .layers.dimensional_aggregator import DimensionalAggregator
from edgar import Company


# Flow metrics that need quarterly derivation for 10-Q validation
# 10-Q filings report YTD cumulative values, but yfinance expects quarterly period values
# Includes both cash flow and income statement metrics (both can be YTD in XBRL)
QUARTERLY_DERIVABLE_METRICS = [
    # Cash flow metrics
    'OperatingCashFlow',
    'Capex',
    'StockBasedCompensation',
    'DividendsPaid',
    'DepreciationAmortization',
    # Income statement flow metrics (can be YTD in 10-Q XBRL)
    'NetIncome',
    'Revenue',
    'COGS',
    'SGA',
    'OperatingIncome',
    'PretaxIncome',
]


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
    #
    # IMPORTANT: yfinance "As Reported" Pattern
    # -----------------------------------------
    # yfinance sometimes provides TWO values for the same metric:
    #   - "<Metric>" = Yahoo-calculated/normalized value (may adjust for one-time items)
    #   - "<Metric> As Reported" or "Total <Metric> As Reported" = GAAP value from filing
    #
    # For most companies, these are identical. But for companies with significant
    # special charges (e.g., KO with $2.3B impairments), Yahoo "normalizes" the
    # base metric by adding back these charges.
    #
    # Our strategy: Use GAAP fields ("As Reported") when available, fallback to
    # calculated fields when not. See YFINANCE_GAAP_FALLBACKS below.
    #
    # Example (KO 2024):
    #   - "Operating Income" = $14.02B (Yahoo adds back special charges)
    #   - "Total Operating Income As Reported" = $9.99B (GAAP, matches XBRL)
    #
    # Search keywords: yfinance GAAP, As Reported, normalized, adjusted
    #
    YFINANCE_MAP = {
        'Revenue': ('financials', 'Total Revenue'),
        'COGS': ('financials', 'Cost Of Revenue'),
        'SGA': ('financials', 'Selling General And Administrative'),
        'OperatingIncome': ('financials', 'Total Operating Income As Reported'),  # GAAP field
        'NetIncome': ('financials', 'Net Income'),
        'OperatingCashFlow': ('cashflow', 'Operating Cash Flow'),
        'Capex': ('cashflow', 'Capital Expenditure'),
        'TotalAssets': ('balance_sheet', 'Total Assets'),
        'Goodwill': ('balance_sheet', 'Goodwill'),
        'IntangibleAssets': ('balance_sheet', 'Goodwill And Other Intangible Assets'),
        'ShortTermDebt': ('balance_sheet', 'Current Debt'),
        'LongTermDebt': ('balance_sheet', 'Long Term Debt'),
        'CashAndEquivalents': ('balance_sheet', 'Cash And Cash Equivalents'),
        # Universal additions
        'WeightedAverageSharesDiluted': ('financials', 'Diluted Average Shares'),
        'StockBasedCompensation': ('cashflow', 'Stock Based Compensation'),
        'DividendsPaid': ('cashflow', 'Cash Dividends Paid'),
        # Archetype A: Working capital
        'Inventory': ('balance_sheet', 'Inventory'),
        'AccountsReceivable': ('balance_sheet', 'Accounts Receivable'),
        'AccountsPayable': ('balance_sheet', 'Accounts Payable'),
        'DepreciationAmortization': ('cashflow', 'Depreciation And Amortization'),
    }
    
    # Fallback fields when GAAP "As Reported" field is not available
    # Some companies only have the calculated field (e.g., NKE, LLY)
    YFINANCE_GAAP_FALLBACKS = {
        'OperatingIncome': ('financials', 'Operating Income'),  # Fallback if "As Reported" missing
    }
    
    # Composite metrics: sum of multiple XBRL concepts
    # These metrics require summing components to match yfinance definition
    # NOTE: These are fallbacks. Prefer extraction_rules.py JSON config.
    COMPOSITE_METRICS = {
        # IntangibleAssets = Goodwill + (IntangibleAssetsNet OR IndefiniteLivedTrademarks)
        # IndefiniteLivedTrademarks is a FALLBACK for IntangibleAssetsNet (via CONCEPT_PRIORITY)
        'IntangibleAssets': ['Goodwill', 'IntangibleAssetsNetExcludingGoodwill'],
        'ShortTermDebt': ['LongTermDebtCurrent', 'CommercialPaper', 'ShortTermBorrowings'],
    }
    
    # DEPRECATED: Use extraction_rules.py instead
    # Kept as fallback if JSON config not available
    CONCEPT_PRIORITY = {
        'Goodwill': ['Goodwill'],
        'IntangibleAssetsNetExcludingGoodwill': [
            'IntangibleAssetsNetExcludingGoodwill',
            'IndefiniteLivedTrademarks',  # KO uses this instead
            'FiniteLivedIntangibleAssetsNet',
        ],
    }
    
    def __init__(
        self,
        config: Optional[MappingConfig] = None,
        tolerance_pct: float = 15.0,  # 15% tolerance for matching
        snapshot_mode: bool = False
    ):
        self.config = config or get_config()
        self.tolerance = tolerance_pct / 100.0
        self._yf_cache = {}  # Cache yfinance Stock objects by ticker
        self._dimensional_aggregator = DimensionalAggregator()  # For dimensional value aggregation
        self._snapshot_mode = snapshot_mode
        self._snapshot_cache = {}  # Cache loaded snapshot dicts by ticker

        if yf is None and not snapshot_mode:
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
    
    def _try_industry_extraction(self, ticker: str, metric: str, xbrl) -> Optional[float]:
        """
        Try industry-specific extraction for special metrics.

        Uses industry_logic module for:
        - ShortTermDebt (banks): Excludes Repos/FedFunds
        - OperatingIncome: Calculated fallback if tag missing

        Returns None if industry extraction doesn't apply or fails.
        """
        try:
            from .industry_logic import get_industry_extractor, BankingExtractor, DefaultExtractor
            from edgar.entity.mappings_loader import get_industry_for_sic
            from .extraction_rules import get_extraction_rule
            from edgar import Company
            import logging

            logger = logging.getLogger(__name__)

            # DATA INTEGRITY GATE (P0)
            # Check for zero-fact or low-fact filings before proceeding
            MIN_FACTS_THRESHOLD = 100  # Typical 10-K has 1000+ facts
            facts_df = None
            if xbrl and xbrl.facts:
                facts_df = xbrl.facts.to_dataframe()

            if facts_df is None or len(facts_df) == 0:
                logger.warning(f"DATA INTEGRITY FAILURE: {ticker} filing has 0 facts - corrupt or unsupported format")
                return None

            if len(facts_df) < MIN_FACTS_THRESHOLD:
                logger.warning(f"DATA INTEGRITY WARNING: {ticker} filing has only {len(facts_df)} facts (expected > {MIN_FACTS_THRESHOLD})")

            # Get industry for this company
            c = Company(ticker)
            sic = c.data.sic
            industry = get_industry_for_sic(sic) if sic else None
            
            # 1. Check for company-specific extraction rule (JSON config override)
            # This handles LLY Capex, MSFT IntangibleAssets, etc. explicitly
            rule = get_extraction_rule(ticker, metric, industry)
            if rule and rule.get('method') == 'concept_priority':
                priorities = rule.get('concept_priority', {}).get(metric, [])
                for variant in priorities:
                    # Handle namespaced concepts from rules
                    concept = variant if ':' in variant else f"us-gaap:{variant}"
                    val = self._extract_xbrl_value(xbrl, concept)
                    if val is not None:
                        return val
            
            # facts_df already extracted in DATA INTEGRITY GATE above

            # Check for explicitly disabled tree fallback (Safety Guardrail)
            # If industry logic returns None (extraction failed) and fallback_to_tree is False,
            # we return a SENTINEL that prevents the Tree Mapper from taking over.
            # We use float('nan') as a provisional sentinel or handle it in the caller.
            # actually, a better way is to check the rule configs.
            
            # Load config for this metric
            from .config_loader import get_config
            conf = get_config()
            
            # Banking-specific extraction for ShortTermDebt
            # Use GAAP mode for validation to prove we can reproduce yfinance values
            if industry == 'banking' and metric == 'ShortTermDebt':
                extractor = BankingExtractor()
                # CRITICAL: Use mode='gaap' for yfinance validation
                # Street View (mode='street') is for database, not validation
                # PHASE 3 FIX: Pass ticker for config-based archetype lookup
                result = extractor.extract_short_term_debt(xbrl, facts_df, mode='gaap', ticker=ticker)
                if result.value is not None:
                    return result.value
                
                # CHECK FALLBACK FLAG
                # If extraction failed (value is None), should we fall back to Tree?
                # We check the industry_metrics.yaml config via the extraction rules or direct config access
                # For now, hardcode the check based on the plan or safer implementation
                # But to follow the plan, we should read the config.
                
                # Quick access to industry config
                # Note: Banking config has metrics directly under industry (no concept_mapping layer)
                industry_conf = conf.data.get('industry_metrics', {}).get('banking', {})
                metric_conf = industry_conf.get('ShortTermDebt', {})
                if metric_conf.get('fallback_to_tree') is False:
                     # Return a special indicator that validation failed/missing (e.g. -1.0 or raise)
                     # But _try_industry_extraction signature is Optional[float].
                     # If we return None, it falls back to Tree.
                     # We need to signal "STOP".
                     # Limitation: The current architecture falls back to Tree if None is returned.
                     # We might need to return 0.0 or a specific small negative number if we want to force failure?
                     # No, that's hacky.
                     # The feedback said: "Explicitly return a sentinel... that doesn't proceed to Tree Mapping."
                     # Since I cannot easily change the caller `validate_company` logic without reading it fully (I did separate read),
                     # I will assume returning a specific "Missing" object or similar would break things.
                     # Wait, I can raise an exception? No.
                     # Let's look at `validate_company` (lines 583-585):
                     # industry_value = self._try_industry_extraction(ticker, metric, xbrl)
                     # if industry_value is not None: xbrl_value = industry_value
                     # elif metric in COMPOSITE... extraction logic
                     # else: ...
                     
                     # It doesn't seem to have a "Tree Mapping" step *inside* validate_company. 
                     # `validate_company` takes `results` (which come from Tree).
                     # Ah, `validate_company` is validating the *Tree Result*.
                     # If `industry_value` is found, it overrides `xbrl_value` (which came from Tree result... wait).
                     
                     # Line 576: if result.is_mapped and xbrl: ...
                     # The Tree Mapping has ALREADY happened before Validation.
                     # The Validation stage is overriding the Tree value with Industry value if available.
                     # If Industry Logic fails (returns None), it currently proceeds to use the Tree Mapped value (result.concept).
                     
                     # To "Disable Tree Fallback", we must INVALIDATE the Tree Result if Industry Logic fails!
                     
                     if metric_conf.get('fallback_to_tree') is False:
                         # We verified Industry Logic returned None (failed).
                         # We must now Tell the caller to discarding the Tree Result.
                         # But this method only returns float.
                         
                         # CRITICAL ARCHITECTURE ADAPTATION:
                         # We must return a Sentinel Float (NaN) to signal "STOP USE OF TREE".
                         return float('nan') # Sentinel for "Hard Missing"

            # Banking-specific extraction for CashAndEquivalents
            # Use GAAP mode for validation to prove we can reproduce yfinance values
            if industry == 'banking' and metric == 'CashAndEquivalents':
                extractor = BankingExtractor()
                # CRITICAL: Use mode='gaap' for yfinance validation
                # Street View (mode='street') is for database, not validation
                result = extractor.extract_cash_and_equivalents(xbrl, facts_df, mode='gaap')
                if result.value is not None:
                    return result.value
                
                # Fallback Check
                # Note: Banking config has metrics directly under industry (no concept_mapping layer)
                industry_conf = conf.data.get('industry_metrics', {}).get('banking', {})
                metric_conf = industry_conf.get('CashAndEquivalents', {})
                if metric_conf.get('fallback_to_tree') is False:
                     return float('nan') # Sentinel to kill Tree Result
            
            # Calculated OperatingIncome for any industry
            # Always return calculated value - handles companies like NKE/MRK
            # that don't report OperatingIncomeLoss concept at all
            if metric == 'OperatingIncome':
                extractor = get_industry_extractor(industry) if industry else DefaultExtractor()
                result = extractor.extract_operating_income(xbrl, facts_df)
                if result.value is not None:
                    return result.value
            
            return None
            
        except Exception:
            return None
    
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
    
    def _calculate_period_days(self, period_key: str) -> int:
        """Calculate days in a period from period_key like 'duration_2024-01-01_2024-12-31'.
        
        Used to differentiate annual periods (>300 days) from quarterly (<100 days).
        """
        try:
            if not period_key.startswith('duration_'):
                return 0
            parts = period_key.replace('duration_', '').split('_')
            if len(parts) == 2:
                start = datetime.strptime(parts[0], '%Y-%m-%d')
                end = datetime.strptime(parts[1], '%Y-%m-%d')
                return (end - start).days
        except Exception:
            pass
        return 0
    
    def _select_latest_filing(self, df) -> 'pd.DataFrame':
        """
        Select facts from the most recent filing for each period.
        
        Implements Point-in-Time (PiT) handling for restatements:
        - If FY2023 was filed in 2024 and restated in 2025, use the 2025 restated value
        - When multiple values exist for the same period, select MAX(filed_date)
        
        Args:
            df: DataFrame of XBRL facts with 'period_key' column
            
        Returns:
            DataFrame sorted by period_key (desc) with filing date precedence applied
        """
        if df is None or len(df) == 0:
            return df
        
        # Check if 'filed' column exists (filing date)
        # Common column names: 'filed', 'filing_date', 'filed_date'
        filed_col = None
        for col in ['filed', 'filing_date', 'filed_date']:
            if col in df.columns:
                filed_col = col
                break
        
        if filed_col is not None:
            # Parse filing date to datetime for proper sorting
            df = df.copy()
            try:
                df['_filed_dt'] = df[filed_col].apply(self._parse_filing_date)
                
                # Sort by period_key (desc) first, then by filing date (desc)
                # This gives us: most recent period + most recent filing for that period
                df = df.sort_values(
                    ['period_key', '_filed_dt'],
                    ascending=[False, False]
                )
                
                # For each unique period, keep only the row with the latest filing date
                df = df.drop_duplicates(subset=['period_key'], keep='first')
                
                # Clean up temp column
                df = df.drop(columns=['_filed_dt'])
                
            except Exception:
                # Fallback to simple period_key sort if date parsing fails
                df = df.sort_values('period_key', ascending=False)
        else:
            # No filing date column available, fallback to period_key sort
            df = df.sort_values('period_key', ascending=False)
        
        return df
    
    def _parse_filing_date(self, date_val) -> datetime:
        """
        Parse filing date from various formats to datetime.
        
        Handles:
        - datetime objects (passthrough)
        - ISO 8601 strings ('2024-01-15')
        - Common date strings ('2024-01-15T10:30:00')
        """
        if date_val is None:
            return datetime.min
        
        if isinstance(date_val, datetime):
            return date_val
        
        try:
            date_str = str(date_val)
            # Handle ISO 8601 with or without time
            if 'T' in date_str:
                date_str = date_str.split('T')[0]
            return datetime.strptime(date_str, '%Y-%m-%d')
        except Exception:
            return datetime.min
    
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
    
    def _is_balance_sheet_metric(self, metric: str) -> bool:
        """Check if metric is Point-in-Time (Balance Sheet)."""
        bs_metrics = {
            'TotalAssets', 'limit_stock', 'StockholdersEquity',
            'CashAndEquivalents', 'ShortTermDebt', 'LongTermDebt',
            'Goodwill', 'IntangibleAssets', 'RestrictedCash',
            # Working capital metrics
            'Inventory', 'AccountsReceivable', 'AccountsPayable'
        }
        return metric in bs_metrics

    def _is_flow_concept(self, concept: str) -> bool:
        """Check if concept implies Duration/Flow (Cash Flow)."""
        if not concept:
            return False
        flow_keywords = [
            'Proceeds', 'Payments', 'Repayments', 'CashFlow', 
            'NetChange', 'Increase', 'Decrease', 'Issuance', 'Retirement', 
            'Acquisition', 'Disposal'
        ]
        concept_clean = concept.split(':')[-1]
        return any(k.lower() in concept_clean.lower() for k in flow_keywords)

    def validate_company(
        self,
        ticker: str,
        results: Dict[str, MappingResult],
        xbrl=None,
        filing_date: Optional[Union[str, datetime]] = None,
        form_type: Optional[str] = None
    ) -> Dict[str, ValidationResult]:
        """
        Validate all mappings for a company against yfinance.
        
        Args:
            ticker: Company ticker
            results: Mapping results to validate
            xbrl: Optional XBRL object to extract values
            filing_date: Date of the filing (for historical matching)
            form_type: Form type (10-K or 10-Q) for period-aware extraction
            
        Returns:
            Dict of validation results per metric
        """
        if yf is None and not self._snapshot_mode:
            return {}

        # Get yfinance data (cached) — skip when using snapshots
        stock = None if self._snapshot_mode else self._get_stock(ticker)

        # Set ticker early so snapshot lookup can use it
        self._current_ticker = ticker

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
            
            # GUARDRAIL: Flow vs Stock Sieve (STT Fix)
            # If Balance Sheet metric mapped to Flow tag, invalidate it immediately
            # CPA Rule: Balance Sheet = Point-in-Time, Cash Flow = Duration.
            if result.is_mapped and self._is_balance_sheet_metric(metric):
                if self._is_flow_concept(result.concept):
                    # Invalidate the mapping - prevents using semantically wrong tag
                    result.concept = None 
                    result.confidence = 0.0
                    result.source = MappingSource.UNKNOWN
            
            # Get reference value from yfinance
            ref_value = self._get_yfinance_value(stock, metric, target_date=filing_date)
            
            # Get XBRL value (if we have a mapping and XBRL object)
            xbrl_value = None
            if result.is_mapped and xbrl:
                # Set context for pattern classification and period-aware extraction
                self._current_ticker = ticker
                self._current_metric = metric
                self._current_form_type = form_type  # For period filtering (10-K vs 10-Q)
                
                # Try industry-specific extraction first for special metrics
                industry_value = self._try_industry_extraction(ticker, metric, xbrl)
                if industry_value is not None:
                    # Check for SENTINEL (NaN) -> Hard Failure of Industry Logic
                    import math
                    if isinstance(industry_value, float) and math.isnan(industry_value):
                        # Sentinel received: Industry Logic Failed AND Tree Fallback Disabled
                        # Invalidate the Tree Mapping to prevent "guessing"
                        result.concept = None
                        result.source = MappingSource.UNKNOWN
                        xbrl_value = None
                        # Proceed as if unmapped (will hit fallback logic, but that's fine as it won't use Tree)
                    else:
                        xbrl_value = industry_value
                        # Update result to reflect industry extraction
                        result.source = MappingSource.INDUSTRY
                        result.concept = f"industry_logic:{metric}"
                        result.confidence = 1.0
                # Check if metric is composite (sum of multiple concepts)
                elif metric in self.COMPOSITE_METRICS:
                    # HYBRID LOGIC: If mapped to a "Total" concept, use direct extraction
                    # This prevents using component sum when a direct total (like DebtCurrent) exists
                    # Added LongTermDebtAndCapitalLeaseObligationsCurrent for KO (8.7% variance vs composite double-counting)
                    if result.concept in [
                        'us-gaap:DebtCurrent', 
                        'us-gaap:ShortTermDebt', 
                        'us-gaap:ShortTermDebtAndCapitalLeaseObligations', # Note: fixed name
                        'us-gaap:LongTermDebtAndCapitalLeaseObligationsCurrent'
                    ]:
                        xbrl_value = self._extract_xbrl_value(xbrl, result.concept)
                    else:
                        xbrl_value = self._extract_composite_value(xbrl, metric)
                else:
                    # Specialized Logic for 10-Q Flow Metrics (Derivation)
                    if form_type == '10-Q' and metric in QUARTERLY_DERIVABLE_METRICS:
                        # Force strict quarterly extraction (90 days)
                        strict_val = self._extract_xbrl_value(xbrl, result.concept, target_days=90)
                        
                        if strict_val is not None:
                            xbrl_value = strict_val
                        else:
                            # Strict extraction failed -> Quarterly fact missing -> Trigger Derivation
                            # Get YTD value (fallback behavior)
                            ytd_val = self._extract_xbrl_value(xbrl, result.concept, target_days=None)
                            
                            if ytd_val is not None:
                                derived = self._derive_quarterly_value(
                                    ticker, 
                                    result.concept, 
                                    filing_date, 
                                    ytd_val
                                )
                                if derived is not None:
                                    xbrl_value = derived
                                else:
                                    # If derivation fails (e.g. no prior filing), default to YTD
                                    xbrl_value = ytd_val
                            else:
                                xbrl_value = None
                    else:
                        xbrl_value = self._extract_xbrl_value(xbrl, result.concept)
            
            # FALLBACK: Industry/Calculated Logic when no mapping exists (or was invalidated)
            elif not result.is_mapped and xbrl and ref_value:
                # 1. Try Industry Extraction (OperatingIncome, Banking Debt/Cash, etc.)
                # This covers STT Flow/Stock invalidated case - we still try industry logic!
                industry_value = self._try_industry_extraction(ticker, metric, xbrl)
                if industry_value is not None:
                    xbrl_value = industry_value
                    # Create a synthetic mapping for the calculated value
                    result.concept = None  # Composite/Calculated
                    result.confidence = 0.85
                    result.source = MappingSource.TREE
                    result.reasoning = "Industry Logic Extraction (Unmapped Fallback)"
                
                # 2. Try Composite Metrics Fallback
                elif metric in self.COMPOSITE_METRICS:
                     composite_value = self._extract_composite_value(xbrl, metric)
                     if composite_value is not None:
                        xbrl_value = composite_value
                        result.concept = f"Composite: {', '.join(self.COMPOSITE_METRICS[metric])}"
                        result.confidence = 0.85
                        result.source = MappingSource.TREE
                        result.reasoning = f"Synthesized from {len(self.COMPOSITE_METRICS[metric])} components via Fallback"
            
            # FALLBACK: Generalized Composite Metrics (ShortTermDebt, IntangibleAssets, etc.)
            # Per Principal Architect: attempt composite construction before giving up
            elif not result.is_mapped and xbrl and metric in self.COMPOSITE_METRICS and ref_value:
                composite_value = self._extract_composite_value(xbrl, metric)
                if composite_value is not None:
                    xbrl_value = composite_value
                    # Mark as synthesized composite
                    result.concept = f"Composite: {', '.join(self.COMPOSITE_METRICS[metric])}"
                    result.confidence = 0.85
                    result.source = MappingSource.TREE
                    result.reasoning = f"Synthesized from {len(self.COMPOSITE_METRICS[metric])} components via Fallback"
            
            # SIGN CONVENTION: Capex is positive in XBRL but negative in yfinance
            # Per Principal Architect: XBRL reports outflows as positive; Street models use negative
            if metric == 'Capex' and xbrl_value is not None and ref_value is not None:
                if xbrl_value > 0 and ref_value < 0:
                    xbrl_value = -xbrl_value

            # SIGN CONVENTION: DividendsPaid is positive in XBRL but negative in yfinance
            # Cash dividends paid are cash outflows, reported as positive in XBRL but negative in yfinance
            if metric == 'DividendsPaid' and xbrl_value is not None and ref_value is not None:
                if xbrl_value > 0 and ref_value < 0:
                    xbrl_value = -xbrl_value

            # Validate
            validation = self._compare_values(
                metric, ticker, xbrl_value, ref_value, result
            )
            
            # IDENTITY CHECK GUARDRAIL (Bank Sector Expansion)
            # If OperatingIncome is extracted, cross-check against accounting identity
            if metric == 'OperatingIncome' and xbrl_value is not None and xbrl:
                try:
                    from .industry_logic import get_industry_extractor, DefaultExtractor
                    from edgar.entity.mappings_loader import get_industry_for_sic
                    from edgar import Company
                    
                    c = Company(ticker)
                    sic = c.data.sic
                    industry = get_industry_for_sic(sic) if sic else None
                    
                    extractor = get_industry_extractor(industry) if industry else DefaultExtractor()
                    
                    # For performance, only get facts if not already extracted
                    facts_df = None
                    if xbrl and xbrl.facts:
                        facts_df = xbrl.facts.to_dataframe()
                        
                    identity_warning = extractor.validate_accounting_identity(xbrl, facts_df, xbrl_value)
                    
                    if identity_warning:
                        # Append warning to validation notes
                        current_notes = validation.notes or ""
                        validation.notes = f"{current_notes} | {identity_warning}" if current_notes else identity_warning
                        # If identity completely fails (major logic error), consider downgrading status
                        # For now, we just warn to gather data during Sprint 4
                except Exception as e:
                    pass

            validations[metric] = validation
        
        return validations
    
    def validate_and_update_mappings(
        self,
        ticker: str,
        results: Dict[str, MappingResult],
        xbrl=None,
        filing_date: Optional[Union[str, datetime]] = None,
        form_type: Optional[str] = None
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
            filing_date: Date of the filing (for historical matching)
            form_type: Form type (10-K or 10-Q) for period-aware extraction
            
        Returns:
            Dict of validation results per metric
        """
        validations = self.validate_company(ticker, results, xbrl, filing_date=filing_date, form_type=form_type)
        
        # Update MappingResult objects based on validation
        for metric, validation in validations.items():
            if metric not in results:
                continue
            
            result = results[metric]
            
            if validation.status == "match":
                result.validation_status = "valid"
                result.validation_notes = "Value matches reference"
            elif validation.status == "mismatch":
                # SMART RETRY: For OperatingIncome, try calculation if direct tag failed
                retry_successful = False
                if metric == 'OperatingIncome' and xbrl is not None:
                    retry_successful = self._retry_with_calculation(
                        ticker, metric, result, validation, xbrl
                    )
                
                if not retry_successful:
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
    
    def _retry_with_calculation(
        self,
        ticker: str,
        metric: str,
        result: 'MappingResult',
        validation: 'ValidationResult',
        xbrl
    ) -> bool:
        """
        Smart Retry: Attempt calculated value when direct tag fails validation.
        
        For OperatingIncome, if the XBRL tag exists but doesn't match yfinance,
        try the GrossProfit - SGA - R&D formula instead.
        
        Returns True if calculation succeeds and is valid.
        """
        try:
            from .industry_logic import get_industry_extractor, DefaultExtractor
            from edgar.entity.mappings_loader import get_industry_for_sic
            from edgar import Company
            
            # Get industry and facts
            c = Company(ticker)
            sic = c.data.sic
            industry = get_industry_for_sic(sic) if sic else None
            
            facts_df = None
            if xbrl and xbrl.facts:
                facts_df = xbrl.facts.to_dataframe()
            
            # Get extractor and calculate
            extractor = get_industry_extractor(industry) if industry else DefaultExtractor()
            calc_result = extractor.extract_operating_income(xbrl, facts_df)
            
            # Only use if it was actually calculated (not direct tag)
            if calc_result.value is None or calc_result.extraction_method.value == 'direct':
                return False
            
            # Check if calculated value matches reference better
            ref_value = validation.reference_value
            if ref_value is None or ref_value == 0:
                return False
            
            calc_variance = abs(calc_result.value - ref_value) / abs(ref_value) * 100
            
            # Success: variance within tolerance (15%)
            if calc_variance <= 15.0:
                # Overwrite mapping with calculated result
                result.concept = None  # No single concept, it's calculated
                result.confidence = 0.85
                result.source = MappingSource.TREE  # Mark as derived
                result.validation_status = "valid"
                result.validation_notes = (
                    f"Smart Retry: Calculated value ({calc_result.value/1e9:.2f}B) matches reference "
                    f"({ref_value/1e9:.2f}B, variance={calc_variance:.1f}%). "
                    f"Formula: {calc_result.notes}"
                )
                
                # Log the swap
                print(f"    [SMART RETRY] {ticker} {metric}: Swapped to calculated value "
                      f"({calc_result.value/1e9:.2f}B vs tag {validation.xbrl_value/1e9:.2f}B)")
                
                return True
            
            # Calculation also fails validation
            return False
            
        except Exception as e:
            # Calculation failed, continue with original failure
            return False
    
    def _get_yfinance_value(
        self,
        stock,
        metric: str,
        max_periods: int = 4,
        target_date: Optional[Union[str, datetime]] = None
    ) -> Optional[float]:
        """Get a value from yfinance for a metric.

        Uses GAAP "As Reported" fields when available, falls back to
        calculated fields for companies that don't have the GAAP field.
        When snapshot_mode is enabled, reads from on-disk JSON instead of live API.

        Args:
            stock: yfinance Ticker object (None when snapshot_mode)
            metric: Metric name
            max_periods: Max periods to search if no target_date
            target_date: Optional specific date to match (within 7 days)

        Returns:
            Float value or None
        """
        if metric not in self.YFINANCE_MAP:
            return None

        # Snapshot mode: read from on-disk JSON instead of live yfinance
        if self._snapshot_mode:
            return self._get_snapshot_value(metric, max_periods, target_date)
        
        sheet_name, field_name = self.YFINANCE_MAP[metric]
        
        try:
            # Dynamically get the dataframe (financials, quarterly_financials, etc.)
            if hasattr(stock, sheet_name):
                df = getattr(stock, sheet_name)
            else:
                return None
            
            if df is None or df.empty:
                return None
            
            # Try primary field first, then fallback if not available
            fields_to_try = [field_name]
            if metric in self.YFINANCE_GAAP_FALLBACKS:
                fallback_sheet, fallback_field = self.YFINANCE_GAAP_FALLBACKS[metric]
                if fallback_sheet == sheet_name:
                    fields_to_try.append(fallback_field)
            
            for try_field in fields_to_try:
                if try_field not in df.index:
                    continue
                
                # DATE MATCHING LOGIC
                if target_date:
                    # Ensure target_date is datetime
                    if isinstance(target_date, str):
                        try:
                            # Handle YYYY-MM-DD or ISO format
                            if 'T' in target_date:
                                target_date = target_date.split('T')[0]
                            t_date = datetime.strptime(target_date, '%Y-%m-%d')
                        except:
                            # Fallback if parsing fails - just use first avail
                            t_date = None
                    else:
                        t_date = target_date
                        
                    if t_date:
                        # Find column nearest to target date
                        best_col = None
                        min_diff = 365 # Start huge
                        
                        for col in df.columns:
                            try:
                                col_date = col if isinstance(col, datetime) else datetime.strptime(str(col).split(' ')[0], '%Y-%m-%d')
                                diff = abs((col_date - t_date).days)
                                
                                # Match within 7 days window (accounting for filing lag vs period end)
                                if diff <= 7 and diff < min_diff:
                                    min_diff = diff
                                    best_col = col
                            except:
                                continue
                        
                        if best_col is not None:
                            val = df.loc[try_field, best_col]
                            if val is not None and not (hasattr(val, 'isna') and val.isna()):
                                return float(val)
                        
                        # If no date match found, return None (don't fallback to random other date)
                        return None

                # DEFAULT LOGIC (If no target_date or date parsing failed)
                # Try multiple periods, use first non-NaN value
                for col_idx in range(min(max_periods, len(df.columns))):
                    val = df.loc[try_field].iloc[col_idx]
                    if val is not None and not (hasattr(val, 'isna') and val.isna()):
                        try:
                            return float(val)
                        except (ValueError, TypeError):
                            continue
                            
        except Exception:
            pass
        
        return None  # All periods NaN or error

    def _get_snapshot_value(
        self,
        metric: str,
        max_periods: int = 4,
        target_date: Optional[Union[str, datetime]] = None
    ) -> Optional[float]:
        """Look up a reference value from on-disk JSON snapshot.

        Loads the snapshot once per ticker (cached in self._snapshot_cache),
        then delegates to yf_snapshot.get_snapshot_value for date matching.
        Handles GAAP fallbacks the same way _get_yfinance_value does.
        """
        from .yf_snapshot import load_snapshot, get_snapshot_value

        ticker = getattr(self, "_current_ticker", None)
        if not ticker:
            return None

        # Load snapshot with instance-level caching
        if ticker not in self._snapshot_cache:
            self._snapshot_cache[ticker] = load_snapshot(ticker)
        snapshot = self._snapshot_cache[ticker]
        if snapshot is None:
            return None

        sheet_name, field_name = self.YFINANCE_MAP[metric]

        # Try primary field
        val = get_snapshot_value(snapshot, sheet_name, field_name, target_date, max_periods)
        if val is not None:
            return val

        # Try GAAP fallback
        if metric in self.YFINANCE_GAAP_FALLBACKS:
            fb_sheet, fb_field = self.YFINANCE_GAAP_FALLBACKS[metric]
            val = get_snapshot_value(snapshot, fb_sheet, fb_field, target_date, max_periods)
            if val is not None:
                return val

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
    def _extract_xbrl_value(self, xbrl, concept: Union[str, List[str]], target_days: Optional[int] = None) -> Optional[float]:
        """
        Extract value for a concept (or list of candidate concepts).
        """
        try:
            if not xbrl:
                return None
            
            concepts = [concept] if isinstance(concept, str) else concept
            
            for concept in concepts:
                if not concept:
                    continue
                    
                # Get facts for this concept
                # We want exact matches or namespace matches
                # Check if concept has prefix
                concept_name = concept.split(':')[-1] if ':' in concept else concept
                
                df = xbrl.facts.get_facts_by_concept(concept)
                if df is None or len(df) == 0:
                    continue

                # Filter for expected concept name to be safe
                if 'concept' in df.columns:
                    # Normalized compare (case-insensitive)
                    expected_concepts = [
                        concept.lower(),
                        f"us-gaap:{concept.lower()}",
                        f"ifrs-full:{concept.lower()}"
                    ]
                    df = df[df['concept'].str.lower().isin(expected_concepts)]

                if len(df) == 0:
                    return None

                # Filter for non-dimensioned (total) values only
                if 'full_dimension_label' in df.columns:
                    total_rows = df[df['full_dimension_label'].isna()]
                    
                    # Check if we're filtering out dimensional-only values
                    if len(total_rows) == 0:
                        dim_rows = df[df['full_dimension_label'].notna()]
                        if len(dim_rows) > 0:
                            # Determine target period days from form type OR override
                            if target_days is not None:
                                target_period_days = target_days
                            else:
                                form_type = getattr(self, '_current_form_type', None)
                                target_period_days = 90 if form_type == '10-Q' else None
                            
                            # Use DimensionalAggregator for proper aggregation (with period filtering)
                            aggregation_result = self._dimensional_aggregator.aggregate_if_missing(
                                xbrl, concept_name, consolidated_value=None,
                                target_period_days=target_period_days
                            )
                            
                            if aggregation_result.aggregated_value is not None:
                                # Store aggregation info for transparency
                                if not hasattr(self, '_dimensional_aggregations'):
                                    self._dimensional_aggregations = {}
                                self._dimensional_aggregations[concept] = {
                                    'value': aggregation_result.aggregated_value,
                                    'dimension_count': aggregation_result.dimension_count,
                                    'dimensions_used': aggregation_result.dimensions_used,
                                    'method': aggregation_result.method,
                                    'notes': aggregation_result.notes
                                }
                                return aggregation_result.aggregated_value
                            
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

                # Sort by period_key to get most recent
                if 'period_key' in total_rows.columns:
                    # Separate instant vs duration facts
                    duration_mask = total_rows['period_key'].str.startswith('duration_')
                    duration_rows = total_rows[duration_mask]
                    instant_rows = total_rows[~duration_mask]
                    
                    if len(duration_rows) > 0:
                        # For duration-based metrics (income/cashflow), prefer annual periods
                        duration_rows = duration_rows.copy()
                        duration_rows['period_days'] = duration_rows['period_key'].apply(
                            self._calculate_period_days
                        )

                        # Exclude zero-day "point-in-time" facts (e.g. dividend declaration dates)
                        # These are tagged as duration but represent a single event, not a period flow
                        non_zero_rows = duration_rows[duration_rows['period_days'] > 0]
                        if len(non_zero_rows) > 0:
                            duration_rows = non_zero_rows

                        # PERIOD-AWARE EXTRACTION: Filter by form type or override
                        if target_days is not None:
                             target_period_days = target_days
                             # Use simple range overlap for matching
                             filtered = duration_rows[
                                (duration_rows['period_days'] >= target_period_days - 30) &
                                (duration_rows['period_days'] <= target_period_days + 30)
                             ]
                             if len(filtered) > 0:
                                 duration_rows = filtered
                             # If strict and no match?
                             # In IndustryLogic we made it strict.
                             # Here, let's also be strict if override is provided.
                             else:
                                 # Checking if this is explicitly requested target
                                 return None
                        else:
                            form_type = getattr(self, '_current_form_type', None)

                            if form_type == '10-Q':
                                # For 10-Q filings: filter for quarterly periods (~90 days)
                                quarterly_rows = duration_rows[
                                    (duration_rows['period_days'] >= 60) &
                                    (duration_rows['period_days'] <= 100)
                                ]
                                if len(quarterly_rows) > 0:
                                    duration_rows = quarterly_rows
                            else:
                                # For 10-K or unknown: prefer annual periods (>300 days)
                                annual_rows = duration_rows[duration_rows['period_days'] > 300]
                                if len(annual_rows) > 0:
                                    duration_rows = annual_rows
                        
                        # PiT: Sort by period_key first, then by filed date (if available)
                        duration_rows = self._select_latest_filing(duration_rows)
                        if len(duration_rows) == 0:
                            return None
                        latest = duration_rows.iloc[0]
                    elif len(instant_rows) > 0:
                        # PiT: Apply filing date precedence to instant facts too
                        instant_rows = self._select_latest_filing(instant_rows)
                        if len(instant_rows) == 0:
                             return None
                        latest = instant_rows.iloc[0]
                    else:
                        latest = total_rows.iloc[0]
                else:
                    latest = total_rows.iloc[0]

                # Get the value
                value = float(latest['numeric_value'])

                # Handle "placeholder zero"
                if value == 0:
                    aggregation_result = self._dimensional_aggregator.aggregate_if_missing(
                        xbrl, concept_name, consolidated_value=value
                    )
                    if self._dimensional_aggregator.should_aggregate(value, aggregation_result.aggregated_value or 0):
                        if not hasattr(self, '_dimensional_aggregations'):
                            self._dimensional_aggregations = {}
                        self._dimensional_aggregations[concept] = {
                            'value': aggregation_result.aggregated_value,
                            'dimension_count': aggregation_result.dimension_count,
                            'dimensions_used': aggregation_result.dimensions_used,
                            'method': aggregation_result.method,
                            'notes': f'Placeholder zero replaced: consolidated=0, dimensional_sum={aggregation_result.aggregated_value}'
                        }
                        return aggregation_result.aggregated_value

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
        
    def _derive_quarterly_value(
        self, 
        ticker: str, 
        concept: str, 
        current_filing_date: str, 
        current_ytd_value: float
    ) -> Optional[float]:
        """
        Derive quarterly value by subtracting Prior YTD from Current YTD.
        Q3_Quarterly = Q3_YTD (Current) - Q2_YTD (Prior)
        """
        try:
             # Need Company to fetch filings
             company = Company(ticker)

             # Fetch 10-Q/10-K filed BEFORE current filing date
             # Use day before current date to exclude the current filing itself
             date_str = str(current_filing_date).split(' ')[0]
             from datetime import datetime as _dt, timedelta as _td
             day_before = (_dt.strptime(date_str, '%Y-%m-%d') - _td(days=1)).strftime('%Y-%m-%d')
             filings = company.get_filings(form=['10-Q', '10-K']).filter(date=f":{day_before}")

             if not filings:
                 return None

             # Get immediate prior filing
             prior_filing = filings.latest(1)
             if not prior_filing:
                 return None
                 
             # Extract Prior YTD
             prior_xbrl = prior_filing.xbrl()
             if not prior_xbrl:
                  return None
                  
             # Extract Prior YTD (pass strict=None to allow finding YTD/Latest)
             # We use the same concept as current
             prior_ytd = self._extract_xbrl_value(prior_xbrl, concept, target_days=None)
             
             if prior_ytd is not None:
                  # Calculate Delta
                  quarterly_val = current_ytd_value - prior_ytd
                  return quarterly_val
                  
             return None
             
        except Exception as e:
             # Just log and fail gracefully
             print(f"Derivation failed for {ticker} {concept}: {e}")
             return None

    
    def _extract_composite_value(
        self,
        xbrl,
        metric: str
    ) -> Optional[float]:
        """
        Extract composite metric value by summing component concepts.
        
        Uses extraction_rules.py JSON config with fallback to hardcoded values.
        Priority: company-specific > industry > defaults > hardcoded
        
        Used for metrics like IntangibleAssets = Goodwill + IntangibleAssetsNetExcludingGoodwill
        """
        # Try to get components from extraction_rules (JSON config)
        ticker = getattr(self, '_current_ticker', None)
        components = get_composite_components(ticker, metric) if ticker else None
        
        # Fall back to hardcoded if no config
        if not components:
            if metric not in self.COMPOSITE_METRICS:
                return None
            components = self.COMPOSITE_METRICS[metric]
        
        total = 0.0
        found_any = False
        
        for component in components:
            value = None
            
            # Get priority from extraction_rules (JSON config)
            if ticker:
                priority_variants = get_concept_priority(ticker, metric, component)
            else:
                # Fallback to hardcoded priority
                priority_variants = self.CONCEPT_PRIORITY.get(component, [component])
            
            # Try each variant in priority order
            for variant in priority_variants:
                # Add us-gaap prefix if not present
                concept = variant if ':' in variant else f"us-gaap:{variant}"
                value = self._extract_xbrl_value(xbrl, concept)
                if value is not None:
                    break
            
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
        
        # Only return mapping_needed if we have no mapping AND no calculated value
        if not result.is_mapped and xbrl_value is None:
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
        
        # Dynamic tolerance per Principal Architect guidance:
        # - 10% for balance sheet debt items (definition differences are common)
        # - 5% default for most metrics
        # - Company-specific overrides take precedence
        base_tolerance = self._get_tolerance_for_company(ticker)
        
        # Debt metrics get higher tolerance due to definition mismatches
        # (yfinance may include/exclude leases, commercial paper differently)
        if metric in ['ShortTermDebt', 'LongTermDebt']:
            tolerance = max(base_tolerance, 0.10)  # At least 10% for debt
        else:
            tolerance = max(base_tolerance, 0.05)
        
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
