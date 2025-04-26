"""
Investment funds package for EdgarTools.

This package provides comprehensive tools for working with investment funds,
fund classes, series information, and portfolio holdings from SEC filings.

The primary classes follow the domain model design:
- FundCompany: Represents the legal entity that manages funds (e.g., "Vanguard")
- FundSeries: Represents a specific investment product/strategy (e.g., "Vanguard 500 Index Fund")
- FundClass: Represents a specific share class with its own ticker (e.g., "Vanguard 500 Index Admiral Shares")

Key functions:
- find_fund(): Smart factory that returns the appropriate entity based on any identifier
- get_fund_company(): Get a fund company by CIK
- get_fund_series(): Get a fund series by series ID
- get_fund_class(): Get a fund class by ticker or class ID

This package provides a more organized, intuitive API for working with fund entities:
- fund_entities.py: Defines the domain entities and access functions
- data.py: Provides data access functions and implementations
- reports.py: Handles fund reports like N-PORT filings
"""

# Keep backward compatibility for now
from edgar.funds.core import (
    Fund,
    FundCompany,
    FundSeries,
    FundClass,
    find_fund,

    get_fund_company,
    get_fund_series,
    get_fund_class,
)

from edgar.funds.data import (
    FundData,
    resolve_fund_identifier,
    is_fund_ticker,
    get_fund_information,
    parse_fund_data
)

from edgar.funds.reports import (
    FundReport,
    CurrentMetric,
    NPORT_FORMS,
    get_fund_portfolio_from_filing
)

# Note: We don't import from reports and thirteenf modules directly here
# to avoid circular imports. These will be imported directly by clients.

from functools import lru_cache

# Backward compatibility function for code that relies on the old API
def get_fund_with_filings(identifier: str):
    """
    Get fund with filings for backward compatibility.
    
    This function is maintained for backward compatibility with the 
    legacy funds.py module. New code should use:
    
    - Fund.get_filings() to get filings for a fund
    - get_fund() factory function to create fund objects
    
    Args:
        identifier: Fund identifier (class ID, series ID, or CIK)
        
    Returns:
        Fund object with filings information
    """
    from edgar.funds.data import direct_get_fund_with_filings
    import logging
    
    if identifier:
        try:
            result = direct_get_fund_with_filings(identifier)
            if result:
                return result
        except Exception as e:
            logging.warning(f"Error in get_fund_with_filings: {e}")
    
    # Create a minimal object with the expected interface as a last resort
    class MinimalFundInfo:
        def __init__(self, identifier):
            self.id = "C000000"
            self.name = f"Unknown Fund {identifier}"
            self.fund_cik = 0
            
    return MinimalFundInfo(identifier or "Unknown")

# Define FundSeriesAndContracts for backward compatibility
class FundSeriesAndContracts:
    """
    Legacy series and contracts object that provides data on fund and classes.

    This class is maintained for backward compatibility with the legacy funds.py module.
    It stores fund series and class information parsed from SEC filings in a DataFrame.

    New code should use the Fund, FundClass, and FundSeries classes from edgar.funds.core
    which provide a more robust object model.
    """
    def __init__(self, data=None):
        import pandas as pd
        self.data = data if data is not None else pd.DataFrame()

__all__ = [
    # Primary user-facing class
    'Fund',
    
    # Domain entity classes
    'FundCompany',
    'FundSeries',
    'FundClass',
    
    # Access functions
    'find_fund',
    'get_fund_company',
    'get_fund_series',
    'get_fund_class',

    
    # Data classes
    'FundData',
    'resolve_fund_identifier',
    
    # Functions now implemented directly in the package
    'get_fund_information', 
    'is_fund_ticker',
    'parse_fund_data',
    
    # Portfolio and report functionality
    'FundReport',
    'CurrentMetric',
    'NPORT_FORMS',
    'get_fund_portfolio_from_filing',
    
    # Legacy compatibility
    'get_fund_with_filings',
    'FundSeriesAndContracts',
]