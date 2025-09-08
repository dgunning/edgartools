"""
Type definitions for EdgarTools parameters with limited value sets.

This module provides StrEnum types for common EdgarTools parameters to enable:
- IDE autocomplete and better developer experience
- Parameter validation with helpful error messages  
- Type safety while maintaining backwards compatibility

Examples:
    from edgar import Company
    from edgar.types import FormType
    
    # New usage with autocomplete
    filings = company.get_filings(form=FormType.ANNUAL_REPORT)
    
    # Existing usage still works
    filings = company.get_filings(form="10-K")
"""

from enum import StrEnum
from typing import Union, List

__all__ = ['FormType']


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


# Type aliases for function signatures
FormInput = Union[FormType, str, List[Union[FormType, str]]]


def validate_form_type(form: Union[FormType, str]) -> str:
    """
    Validate and normalize form type parameter.
    
    Args:
        form: Form type as FormType enum or string
        
    Returns:
        Normalized form string
        
    Raises:
        ValueError: If form string is not recognized with helpful suggestions
    """
    if isinstance(form, FormType):
        return form.value
    
    if isinstance(form, str):
        # Check if it's a valid form string
        valid_forms = set(FormType.__members__.values())
        
        if form in valid_forms:
            return form
            
        # Provide helpful error message with suggestions
        import difflib
        suggestions = difflib.get_close_matches(form, valid_forms, n=3, cutoff=0.6)
        
        if suggestions:
            raise ValueError(
                f"Invalid form type '{form}'. Did you mean one of: {', '.join(suggestions)}? "
                f"Use FormType enum for autocomplete or see FormType documentation for all valid forms."
            )
        else:
            raise ValueError(
                f"Invalid form type '{form}'. "
                f"Use FormType enum for autocomplete or see FormType documentation for all valid forms."
            )
    
    raise TypeError(f"Form must be FormType or str, not {type(form)}")


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