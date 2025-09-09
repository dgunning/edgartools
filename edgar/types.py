"""
Type definitions for EdgarTools parameters with limited value sets.

This module provides StrEnum types for common EdgarTools parameters to enable:
- IDE autocomplete and better developer experience
- Parameter validation with helpful error messages  
- Type safety while maintaining backwards compatibility

Examples:
    from edgar import Company
    from edgar.types import FormType, PeriodType
    
    # New usage with autocomplete
    filings = company.get_filings(form=FormType.ANNUAL_REPORT)
    facts = company.get_facts(period=PeriodType.ANNUAL)
    statement = company.get_statement(StatementType.INCOME_STATEMENT)
    
    # Existing usage still works
    filings = company.get_filings(form="10-K")
    facts = company.get_facts(annual=True)
    statement = company.get_income_statement()
"""

try:
    from enum import StrEnum
except ImportError:
    # Python < 3.11 compatibility
    from enum import Enum
    
    class StrEnum(str, Enum):
        """Compatibility StrEnum for Python < 3.11"""
        def __new__(cls, value):
            obj = str.__new__(cls, value)
            obj._value_ = value
            return obj
        
        def __str__(self):
            return str(self._value_)

from typing import Union, List, Any, Optional, Set, Dict
import difflib
import re

__all__ = ['FormType', 'PeriodType', 'StatementType', 'ValidationError', 'enhanced_validate']


class FormType(StrEnum):
    """
    Enumeration of common SEC form types with IDE autocomplete support.
    
    This enum provides type-safe access to SEC form identifiers while maintaining
    backwards compatibility with string parameters through Union types.
    
    Values are the actual SEC form identifiers used in API calls.
    """
    
    # Most common periodic reports
    ANNUAL_REPORT = "10-K"
    QUARTERLY_REPORT = "10-Q" 
    ANNUAL_REPORT_AMENDED = "10-K/A"
    QUARTERLY_REPORT_AMENDED = "10-Q/A"
    
    # Current reports
    CURRENT_REPORT = "8-K"
    FOREIGN_CURRENT_REPORT = "6-K"
    
    # Proxy statements
    PROXY_STATEMENT = "DEF 14A"
    PRELIMINARY_PROXY = "PRE 14A"
    ADDITIONAL_PROXY = "DEFA14A"
    MERGER_PROXY = "DEFM14A"
    
    # Foreign issuers
    FOREIGN_ANNUAL = "20-F"
    CANADIAN_ANNUAL = "40-F"
    
    # Registration statements (most common)
    REGISTRATION_S1 = "S-1"
    REGISTRATION_S3 = "S-3" 
    REGISTRATION_S4 = "S-4"
    REGISTRATION_S8 = "S-8"
    
    # Foreign registration
    FOREIGN_REGISTRATION_F1 = "F-1"
    FOREIGN_REGISTRATION_F3 = "F-3"
    FOREIGN_REGISTRATION_F4 = "F-4"
    
    # Prospectus supplements
    PROSPECTUS_424B1 = "424B1"
    PROSPECTUS_424B2 = "424B2"
    PROSPECTUS_424B3 = "424B3"
    PROSPECTUS_424B4 = "424B4"
    PROSPECTUS_424B5 = "424B5"
    
    # Ownership reports
    BENEFICIAL_OWNERSHIP_13D = "SC 13D"
    BENEFICIAL_OWNERSHIP_13G = "SC 13G"
    
    # Other important filings
    EMPLOYEE_BENEFIT_PLAN = "11-K"
    SPECIALIZED_DISCLOSURE = "SD"
    ASSET_BACKED_SECURITIES = "ARS"
    
    # Late filing notifications
    LATE_10K_NOTICE = "NT 10-K"
    LATE_10Q_NOTICE = "NT 10-Q"


class PeriodType(StrEnum):
    """
    Enumeration of financial reporting period types with IDE autocomplete support.
    
    This enum provides type-safe access to period specifications while maintaining
    backwards compatibility with boolean annual parameters through Union types.
    
    Values correspond to common financial reporting periods.
    """
    
    # Primary period types
    ANNUAL = "annual"           # Annual reporting periods (full fiscal year)
    QUARTERLY = "quarterly"     # Quarterly reporting periods (3-month periods)
    MONTHLY = "monthly"         # Monthly reporting periods (rarely used)
    
    # Special period types  
    TTM = "ttm"                # Trailing Twelve Months
    YTD = "ytd"                # Year to Date
    
    # Alternative names for convenience
    YEARLY = "annual"          # Alias for ANNUAL
    QUARTER = "quarterly"      # Alias for QUARTERLY


class StatementType(StrEnum):
    """
    Enumeration of financial statement types with IDE autocomplete support.
    
    This enum provides type-safe access to statement specifications while maintaining
    backwards compatibility with string parameters through Union types.
    
    Values correspond to common financial statement categories.
    """
    
    # Primary financial statements (The Big Four)
    INCOME_STATEMENT = "income_statement"           # Profit & Loss Statement
    BALANCE_SHEET = "balance_sheet"                 # Statement of Financial Position
    CASH_FLOW = "cash_flow_statement"              # Statement of Cash Flows  
    CHANGES_IN_EQUITY = "changes_in_equity"        # Statement of Changes in Equity
    
    # Comprehensive income statement
    COMPREHENSIVE_INCOME = "comprehensive_income"   # Statement of Comprehensive Income
    
    # Segment and subsidiary reporting
    SEGMENTS = "segment_reporting"                  # Segment Information
    SUBSIDIARIES = "subsidiaries"                   # Subsidiary Information
    
    # Notes and disclosures
    FOOTNOTES = "footnotes"                        # Notes to Financial Statements
    ACCOUNTING_POLICIES = "accounting_policies"     # Significant Accounting Policies
    
    # Special purpose statements
    REGULATORY_CAPITAL = "regulatory_capital"       # Regulatory Capital (banks)
    INSURANCE_RESERVES = "insurance_reserves"       # Insurance Reserves (insurance cos)
    
    # Alternative names for user convenience and compatibility
    PROFIT_LOSS = "income_statement"               # Alias for income statement
    PL_STATEMENT = "income_statement"              # Another P&L alias
    FINANCIAL_POSITION = "balance_sheet"           # Alias for balance sheet
    STATEMENT_OF_POSITION = "balance_sheet"        # Another balance sheet alias
    CASH_FLOWS = "cash_flow_statement"            # Alias for cash flow
    EQUITY_CHANGES = "changes_in_equity"          # Alias for equity statement


# Type aliases for function signatures
FormInput = Union[FormType, str, List[Union[FormType, str]]]
PeriodInput = Union[PeriodType, str]
StatementInput = Union[StatementType, str]


# FEAT-004: Enhanced Parameter Validation Framework
class ValidationError(ValueError):
    """Enhanced validation error with suggestions and context."""
    
    def __init__(self, message: str, parameter: str, invalid_value: Any, suggestions: Optional[List[str]] = None):
        self.parameter = parameter
        self.invalid_value = invalid_value
        self.suggestions = suggestions or []
        super().__init__(message)


def fuzzy_match(value: str, valid_options: Set[str], threshold: float = 0.6) -> List[str]:
    """
    Find fuzzy matches for a value against valid options.
    
    Args:
        value: The input value to match
        valid_options: Set of valid option strings
        threshold: Similarity threshold (0.0 to 1.0)
        
    Returns:
        List of suggested matches, ordered by similarity
    """
    if not isinstance(value, str):
        return []
    
    # Get close matches using difflib
    matches = difflib.get_close_matches(
        value.lower(), 
        [opt.lower() for opt in valid_options], 
        n=3, 
        cutoff=threshold
    )
    
    # Return original case matches
    original_matches = []
    for match in matches:
        for option in valid_options:
            if option.lower() == match:
                original_matches.append(option)
                break
                
    return original_matches


def detect_common_typos(value: str, valid_options: Set[str]) -> List[str]:
    """
    Detect common typos and provide specific suggestions.
    
    Args:
        value: The input value that might contain typos
        valid_options: Set of valid option strings
        
    Returns:
        List of likely intended values based on common typo patterns
    """
    suggestions = []
    value_lower = value.lower()
    
    for option in valid_options:
        option_lower = option.lower()
        
        # Check for common typo patterns
        patterns = [
            # Case issues (exact match except case)
            (lambda v, o: v == o, "case mismatch"),
            # Missing hyphen (10k -> 10-K)
            (lambda v, o: v.replace('-', '') == o.replace('-', ''), "missing hyphen"),
            # Missing characters (one char difference)
            (lambda v, o: len(v) == len(o) - 1 and all(c in o for c in v), "missing character"),
            # Extra characters (one char difference)
            (lambda v, o: len(v) == len(o) + 1 and all(c in v for c in o), "extra character"),
            # Single character substitution
            (lambda v, o: len(v) == len(o) and sum(c1 != c2 for c1, c2 in zip(v, o)) == 1, "character substitution"),
            # Transposed adjacent characters
            (lambda v, o: len(v) == len(o) and 
             any(v[:i] + v[i+1] + v[i] + v[i+2:] == o for i in range(len(v)-1)), "transposed characters")
        ]
        
        for pattern_func, pattern_name in patterns:
            if pattern_func(value_lower, option_lower):
                suggestions.append(option)
                break
                
    return suggestions[:3]  # Return top 3 suggestions


def enhanced_validate(value: Any, 
                     valid_options: Set[str], 
                     parameter_name: str,
                     enum_type: Optional[type] = None,
                     context_hint: Optional[str] = None) -> str:
    """
    Enhanced parameter validation with intelligent error messages.
    
    Args:
        value: The parameter value to validate
        valid_options: Set of valid string options
        parameter_name: Name of the parameter for error messages
        enum_type: Optional enum type for enhanced suggestions
        context_hint: Optional context for better error messages
        
    Returns:
        Validated and normalized parameter value
        
    Raises:
        ValidationError: With intelligent suggestions for invalid values
        TypeError: For completely wrong parameter types
    """
    # Handle None values
    if value is None:
        raise ValidationError(
            f"Parameter '{parameter_name}' cannot be None. "
            f"Valid options: {', '.join(sorted(valid_options)[:5])}{'...' if len(valid_options) > 5 else ''}",
            parameter_name,
            value
        )
    
    # Handle enum types
    if enum_type and hasattr(value, 'value'):
        return value.value
    
    # Handle string values
    if isinstance(value, str):
        if value in valid_options:
            return value
            
        # Try case-insensitive match
        for option in valid_options:
            if value.lower() == option.lower():
                return option
                
        # Generate suggestions
        typo_suggestions = detect_common_typos(value, valid_options)
        fuzzy_suggestions = fuzzy_match(value, valid_options, threshold=0.6)
        
        # Combine and deduplicate suggestions
        all_suggestions = list(dict.fromkeys(typo_suggestions + fuzzy_suggestions))
        
        # Build error message
        if all_suggestions:
            suggestions_text = "', '".join(all_suggestions[:3])
            error_msg = (
                f"Invalid {parameter_name} '{value}'. Did you mean '{suggestions_text}'? "
                f"{f'Use {enum_type.__name__} enum for autocomplete or ' if enum_type else ''}"
                f"see documentation for all valid {parameter_name}s."
            )
        else:
            # No good suggestions, show valid options
            sorted_options = sorted(valid_options)
            if len(sorted_options) <= 8:
                options_text = "', '".join(sorted_options)
            else:
                options_text = "', '".join(sorted_options[:8]) + "', ..."
            
            error_msg = (
                f"Invalid {parameter_name} '{value}'. "
                f"Valid {parameter_name}s: ['{options_text}']. "
                f"{f'Use {enum_type.__name__} enum for autocomplete or ' if enum_type else ''}"
                f"see documentation for complete list."
            )
            
        if context_hint:
            error_msg += f" {context_hint}"
            
        raise ValidationError(error_msg, parameter_name, value, all_suggestions)
    
    # Handle wrong types
    expected_types = f"{enum_type.__name__} or " if enum_type else ""
    raise TypeError(
        f"Parameter '{parameter_name}' must be {expected_types}str, not {type(value).__name__}. "
        f"{f'Use {enum_type.__name__} enum for autocomplete.' if enum_type else ''}"
    )


def validate_form_type(form: Union[FormType, str]) -> str:
    """
    Validate and normalize form type parameter using enhanced validation.
    
    Args:
        form: Form type as FormType enum or string
        
    Returns:
        Normalized form string
        
    Raises:
        ValidationError: If form string is not recognized with helpful suggestions
        TypeError: For wrong parameter types
    """
    valid_forms = set(FormType.__members__.values())
    return enhanced_validate(
        form, 
        valid_forms, 
        "form type",
        enum_type=FormType,
        context_hint="Common forms: '10-K' (annual), '10-Q' (quarterly), '8-K' (current report)."
    )


def validate_period_type(period: Union[PeriodType, str]) -> str:
    """
    Validate and normalize period type parameter using enhanced validation.
    
    Args:
        period: Period type as PeriodType enum or string
        
    Returns:
        Normalized period string
        
    Raises:
        ValidationError: If period string is not recognized with helpful suggestions
        TypeError: For wrong parameter types
    """
    valid_periods = set(PeriodType.__members__.values())
    return enhanced_validate(
        period, 
        valid_periods, 
        "period type",
        enum_type=PeriodType,
        context_hint="Common periods: 'annual' (full year), 'quarterly' (3 months), 'ttm' (trailing 12 months)."
    )


def validate_statement_type(statement: Union[StatementType, str]) -> str:
    """
    Validate and normalize statement type parameter using enhanced validation.
    
    Args:
        statement: Statement type as StatementType enum or string
        
    Returns:
        Normalized statement string
        
    Raises:
        ValidationError: If statement string is not recognized with helpful suggestions
        TypeError: For wrong parameter types
    """
    valid_statements = set(StatementType.__members__.values())
    return enhanced_validate(
        statement, 
        valid_statements, 
        "statement type",
        enum_type=StatementType,
        context_hint="Primary statements: 'income_statement' (P&L), 'balance_sheet' (financial position), 'cash_flow_statement' (cash movements)."
    )


def _get_form_display_name(form: Union[FormType, str]) -> str:
    """
    Get human-readable display name for form type.
    
    Args:
        form: Form type as FormType enum or string
        
    Returns:
        Human-readable form description
    """
    if isinstance(form, FormType):
        # Convert enum name to readable format
        # ANNUAL_REPORT -> Annual Report
        return form.name.replace('_', ' ').title()
    
    return str(form)


# Commonly used form collections for convenience
PERIODIC_FORMS = [
    FormType.ANNUAL_REPORT,
    FormType.QUARTERLY_REPORT, 
    FormType.ANNUAL_REPORT_AMENDED,
    FormType.QUARTERLY_REPORT_AMENDED
]

CURRENT_REPORT_FORMS = [
    FormType.CURRENT_REPORT,
    FormType.FOREIGN_CURRENT_REPORT
]

PROXY_FORMS = [
    FormType.PROXY_STATEMENT,
    FormType.PRELIMINARY_PROXY,
    FormType.ADDITIONAL_PROXY,
    FormType.MERGER_PROXY
]

REGISTRATION_FORMS = [
    FormType.REGISTRATION_S1,
    FormType.REGISTRATION_S3,
    FormType.REGISTRATION_S4,
    FormType.REGISTRATION_S8
]

# Period type collections for convenience
STANDARD_PERIODS = [
    PeriodType.ANNUAL,
    PeriodType.QUARTERLY
]

SPECIAL_PERIODS = [
    PeriodType.TTM,
    PeriodType.YTD
]

ALL_PERIODS = [
    PeriodType.ANNUAL,
    PeriodType.QUARTERLY,
    PeriodType.MONTHLY,
    PeriodType.TTM,
    PeriodType.YTD
]

# Statement type collections for convenience
PRIMARY_STATEMENTS = [
    StatementType.INCOME_STATEMENT,
    StatementType.BALANCE_SHEET,
    StatementType.CASH_FLOW,
    StatementType.CHANGES_IN_EQUITY
]

COMPREHENSIVE_STATEMENTS = [
    StatementType.INCOME_STATEMENT,
    StatementType.BALANCE_SHEET,
    StatementType.CASH_FLOW,
    StatementType.CHANGES_IN_EQUITY,
    StatementType.COMPREHENSIVE_INCOME
]

ANALYTICAL_STATEMENTS = [
    StatementType.SEGMENTS,
    StatementType.SUBSIDIARIES,
    StatementType.FOOTNOTES,
    StatementType.ACCOUNTING_POLICIES
]

SPECIALIZED_STATEMENTS = [
    StatementType.REGULATORY_CAPITAL,
    StatementType.INSURANCE_RESERVES
]

ALL_STATEMENTS = PRIMARY_STATEMENTS + [StatementType.COMPREHENSIVE_INCOME] + ANALYTICAL_STATEMENTS + SPECIALIZED_STATEMENTS