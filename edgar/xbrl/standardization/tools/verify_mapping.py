"""
Mapping Verifier Tool

REUSABLE TOOL FOR AI AGENTS

Verifies a mapping by comparing XBRL extracted values with reference values.
Checks entity consolidation context and reporting period alignment.

Usage by AI Agent:
    from edgar.xbrl.standardization.tools.verify_mapping import verify_mapping
    
    result = verify_mapping(mapping_result, xbrl, ticker)
    if not result.is_valid:
        print(f"Mismatch: {result.explanation}")
"""

import re
from typing import Optional, Dict, Any
from dataclasses import dataclass

try:
    import yfinance as yf
except ImportError:
    yf = None

from edgar.xbrl.xbrl import XBRL


@dataclass
class MappingVerification:
    """Result of mapping verification."""
    metric: str
    company: str
    concept: str
    is_valid: bool
    xbrl_value: Optional[float]
    reference_value: Optional[float]
    variance_pct: Optional[float]
    status: str  # "match", "mismatch", "no_xbrl", "no_ref", "error"
    explanation: str
    consolidation_check: Optional[str] = None  # Notes about entity context


# Mapping from metrics to yfinance field names
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

# Regex patterns for prefix stripping
NAMESPACE_PREFIX_PATTERN = re.compile(r'^(us-gaap:|dei:|ifrs-full:)')
COMPANY_PREFIX_PATTERN = re.compile(r'^[a-z]{2,5}_', re.IGNORECASE)


def strip_prefix(concept: str) -> str:
    """Strip namespace and company prefixes from a concept name."""
    result = NAMESPACE_PREFIX_PATTERN.sub('', concept)
    result = COMPANY_PREFIX_PATTERN.sub('', result)
    return result


def verify_mapping(
    metric: str,
    concept: str,
    xbrl: Optional[XBRL],
    ticker: str,
    tolerance_pct: float = 15.0
) -> MappingVerification:
    """
    Verify a mapping by comparing extracted values with reference.
    
    This is a REUSABLE TOOL for AI agents to validate mappings.
    
    Args:
        metric: Target metric name (e.g., "TotalAssets")
        concept: XBRL concept (e.g., "us-gaap:Assets")
        xbrl: XBRL object to extract value from
        ticker: Company ticker for yfinance lookup
        tolerance_pct: Acceptable variance percentage
        
    Returns:
        MappingVerification with is_valid, values, and explanation
    """
    # Get yfinance reference value
    ref_value = _get_yfinance_value(ticker, metric)
    
    if yf is None:
        return MappingVerification(
            metric=metric,
            company=ticker,
            concept=concept,
            is_valid=False,
            xbrl_value=None,
            reference_value=None,
            variance_pct=None,
            status="error",
            explanation="yfinance not installed"
        )
    
    # Get XBRL value
    xbrl_value = None
    if xbrl is not None:
        xbrl_value = _extract_xbrl_value(xbrl, concept)
    
    # Handle missing values
    if xbrl_value is None and ref_value is None:
        return MappingVerification(
            metric=metric,
            company=ticker,
            concept=concept,
            is_valid=True,  # Both missing - metric may not exist
            xbrl_value=None,
            reference_value=None,
            variance_pct=None,
            status="no_data",
            explanation="Neither XBRL nor reference has data"
        )
    
    if xbrl_value is None:
        return MappingVerification(
            metric=metric,
            company=ticker,
            concept=concept,
            is_valid=False,
            xbrl_value=None,
            reference_value=ref_value,
            variance_pct=None,
            status="no_xbrl",
            explanation=f"No XBRL value extracted but reference has {ref_value/1e9:.2f}B"
        )
    
    if ref_value is None:
        return MappingVerification(
            metric=metric,
            company=ticker,
            concept=concept,
            is_valid=True,  # Can't validate without reference
            xbrl_value=xbrl_value,
            reference_value=None,
            variance_pct=None,
            status="no_ref",
            explanation=f"XBRL has {xbrl_value/1e9:.2f}B but no reference to compare"
        )
    
    # Compare values (use absolute to handle sign differences in cash flows)
    abs_xbrl = abs(xbrl_value)
    abs_ref = abs(ref_value)
    
    if abs_ref == 0:
        variance = 0 if abs_xbrl == 0 else 100.0
    else:
        variance = abs(abs_xbrl - abs_ref) / abs_ref * 100
    
    tolerance = tolerance_pct
    is_match = variance <= tolerance
    
    # Check for consolidation issues (large discrepancy)
    consolidation_check = None
    if variance > 50:
        consolidation_check = "Large variance may indicate consolidation difference (parent-only vs consolidated)"
    
    return MappingVerification(
        metric=metric,
        company=ticker,
        concept=concept,
        is_valid=is_match,
        xbrl_value=xbrl_value,
        reference_value=ref_value,
        variance_pct=variance,
        status="match" if is_match else "mismatch",
        explanation=f"Variance: {variance:.1f}% ({'within' if is_match else 'exceeds'} {tolerance}% tolerance)",
        consolidation_check=consolidation_check
    )


def _get_yfinance_value(ticker: str, metric: str) -> Optional[float]:
    """Get reference value from yfinance."""
    if yf is None or metric not in YFINANCE_MAP:
        return None
    
    sheet_name, field_name = YFINANCE_MAP[metric]
    
    try:
        stock = yf.Ticker(ticker)
        
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


def _extract_xbrl_value(xbrl: XBRL, concept: str) -> Optional[float]:
    """Extract value from XBRL for a concept."""
    try:
        concept_name = strip_prefix(concept)
        
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
        
        # Sort by period_key to get the most recent
        if 'period_key' in total_rows.columns:
            total_rows = total_rows.sort_values('period_key', ascending=False)
        
        # Get the latest value
        latest = total_rows.iloc[0]
        return float(latest['numeric_value'])
        
    except Exception:
        return None


# Convenience function for quick testing
def verify(metric: str, concept: str, ticker: str) -> MappingVerification:
    """Quick way to verify a mapping."""
    from edgar import Company, set_identity, use_local_storage
    set_identity("Dev Gunning developer-gunning@gmail.com")
    use_local_storage(True)  # Use bulk data, no API calls

    try:
        company = Company(ticker)
        filing = list(company.get_filings(form='10-K'))[0]
        xbrl = filing.xbrl()
        return verify_mapping(metric, concept, xbrl, ticker)
    except Exception as e:
        return MappingVerification(
            metric=metric,
            company=ticker,
            concept=concept,
            is_valid=False,
            xbrl_value=None,
            reference_value=None,
            variance_pct=None,
            status="error",
            explanation=str(e)
        )
