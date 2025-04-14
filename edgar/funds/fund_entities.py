"""
Fund entity classes and access functions.

This module provides a more intuitive API for working with fund entities:
- FundCompany: The legal entity that manages funds (formerly called Fund)
- FundSeries: A specific investment strategy/product
- FundClass: A specific share class with its own ticker

It also provides specialized accessor functions for each entity type.
"""
import logging
import re
from typing import List, Dict, Optional, Union, Any, TYPE_CHECKING, Sequence, cast
from functools import cached_property
import pandas as pd

from edgar.entity.core import Entity

if TYPE_CHECKING:
    from edgar._filings import Filings
    from edgar.entity.data import EntityData
    from edgar.funds.core import Fund, FundClass as CoreFundClass, FundSeries as CoreFundSeries

log = logging.getLogger(__name__)


class FundCompany(Entity):
    """
    Represents an investment fund company (legal entity) that offers multiple fund series.
    
    This is the top-level entity in the fund hierarchy that files with the SEC under a 
    single CIK. Examples include Vanguard, Fidelity, BlackRock, etc.
    """
    
    def __init__(self, cik_or_identifier: Union[str, int]):
        # Import locally to avoid circular imports
        from edgar.funds.data import resolve_fund_identifier
        
        # Handle fund-specific identifiers
        super().__init__(resolve_fund_identifier(cik_or_identifier))
        self._cached_classes = None
        self._cached_series = None  # Will be initialized as list in get_series()
        self._cached_portfolio = None
    
    # We override the data property provided by the base class
    @cached_property  # type: ignore
    def data(self) -> 'EntityData':
        """Get detailed data for this fund company."""
        base_data = super().data
        
        # If we already have fund-specific data, return it
        if hasattr(base_data, 'is_fund') and base_data.is_fund:
            return base_data
            
        # Otherwise, try to convert to fund-specific data
        # This could be enhanced in the future
        return base_data
        
    def get_classes(self) -> Sequence['FundClass']:
        """
        Get all share classes offered by this fund company.
        
        Returns:
            Sequence of FundClass instances representing all share classes
        """
        # Import locally to avoid circular imports
        from edgar.funds.data import get_fund_classes
        
        if self._cached_classes is None:
            # Use cast to tell type checker that the returned classes will be converted
            # to our FundClass type (the actual implementation will handle the conversion)
            core_classes = get_fund_classes(cast('Fund', self))
            
            # Convert classes to our new type if needed (in practice, we rely on the fact
            # that our API functions will return the right types)
            self._cached_classes = core_classes  # type: ignore
            
        return self._cached_classes  # type: ignore
        
    def get_series(self) -> Sequence['FundSeries']:
        """
        Get all fund series offered by this fund company.
        
        Returns:
            Sequence of FundSeries instances representing all fund series
        """
        # Import locally to avoid circular imports
        from edgar.funds.data import get_fund_series

        if self._cached_series is None:
            # Use cast to tell type checker that we're handling the type conversion
            core_series = get_fund_series(cast('Fund', self))
            
            # Convert series to our new type if needed (in practice, we rely on the fact
            # that our API functions will return the right types)
            self._cached_series = core_series  # type: ignore
            
        return self._cached_series  # type: ignore
        
    def get_portfolio(self) -> pd.DataFrame:
        """
        Get the most recent portfolio holdings.
        
        Returns:
            DataFrame containing portfolio holdings data
        """
        # Import locally to avoid circular imports
        from edgar.funds.data import get_fund_portfolio
        
        if self._cached_portfolio is None:
            # Use cast to tell type checker that we're handling the type conversion
            self._cached_portfolio = get_fund_portfolio(cast('Fund', self))
            
        return self._cached_portfolio
    
    def get_ticker(self) -> Optional[str]:
        """
        Get the primary ticker for this fund company.
        
        Returns:
            Primary ticker symbol or None if not available
        """
        # Look for tickers in data first
        if hasattr(self.data, 'tickers') and self.data.tickers:
            return self.data.tickers[0]
            
        # Otherwise look for ticker in fund classes
        classes = self.get_classes()
        for cls in classes:
            if cls.ticker:
                return cls.ticker
                
        return None
    
    def __str__(self):
        ticker = self.get_ticker()
        ticker_str = f" - {ticker}" if ticker else ""
        
        if hasattr(self, 'data') and hasattr(self.data, 'name'):
            return f"FundCompany({self.data.name} [{self.cik}]{ticker_str})"
        return f"FundCompany(CIK={self.cik}{ticker_str})"

    def __rich__(self):
        """Creates a rich representation of the fund company with detailed information."""
        # Import locally to avoid circular imports
        from edgar.funds.core import Fund
        
        # Create a temporary Fund object to use its __rich__ method
        # This will be replaced in a future version with a native implementation
        fund = Fund.__new__(Fund)
        fund._cik = self.cik
        fund._data = self._data if hasattr(self, '_data') else None
        fund._cached_classes = self._cached_classes
        fund._cached_series = self._cached_series
        fund._cached_portfolio = self._cached_portfolio
        
        # Call the rich method on the temporary Fund object
        return fund.__rich__()
        

class FundSeries:
    """
    Represents a specific investment fund/strategy offered by a fund company.
    
    A fund series is a particular investment product with its own objective,
    portfolio, and performance history. Each series can have multiple share classes.
    """
    
    def __init__(self, series_id: str, name: str, company: FundCompany):
        self.series_id = series_id
        self.name = name
        self.company = company  # Note: this was previously called 'fund'
    
    @property
    def fund(self) -> FundCompany:
        """
        Get the parent fund company.
        
        This is provided for backward compatibility with the previous API where
        'fund' referred to what is now called 'company'.
        
        Returns:
            The parent FundCompany instance
        """
        return self.company
    
    @property
    def fund_company(self) -> FundCompany:
        """
        Get the parent fund company.
        
        This is a convenience alias for the 'company' property for backward
        compatibility and clarity.
        
        Returns:
            The parent FundCompany instance
        """
        return self.company
        
    def get_classes(self) -> List['FundClass']:
        """
        Get all share classes in this series.
        
        Returns:
            List of FundClass instances belonging to this specific series
        """
        # Get all classes for the fund company
        all_classes = self.company.get_classes()
        
        # Filter to get only classes for this series
        series_classes = [
            cls for cls in all_classes 
            if hasattr(cls, 'series_id') and cls.series_id == self.series_id
        ]
        
        # If we didn't find any classes specifically marked with this series_id,
        # and this is the only series for the fund, return all classes
        if not series_classes and len(self.company.get_series()) == 1:
            return all_classes  # type: ignore
            
        return series_classes  # type: ignore
    
    def get_filings(self, **kwargs) -> 'Filings':
        """
        Get filings for this fund series.
        
        Args:
            **kwargs: Filtering parameters passed to get_filings
            
        Returns:
            Filings object with filtered filings
        """
        return self.company.get_filings(**kwargs)
        
    def __str__(self):
        return f"FundSeries({self.name} [{self.series_id}])"
    
    def __repr__(self):
        return self.__str__()
    
    def __rich__(self):
        """Creates a rich representation of the fund series."""
        # Import locally to avoid circular imports
        from edgar.funds.core import FundSeries as CoreFundSeries
        
        # Create a temporary FundSeries object to use its __rich__ method
        # This will be replaced in a future version with a native implementation
        series = CoreFundSeries.__new__(CoreFundSeries)
        series.series_id = self.series_id
        series.name = self.name
        series.fund = self.company  # Note: CoreFundSeries uses 'fund' not 'company'
        
        # Call the rich method on the temporary FundSeries object
        return series.__rich__()


class FundClass:
    """
    Represents a specific share class of a fund series.
    
    Fund classes typically have their own ticker symbols and fee structures,
    but belong to the same underlying fund series. Each class belongs to a
    specific fund series.
    """
    
    def __init__(self, class_id: str, company: FundCompany, name: Optional[str] = None, 
                 ticker: Optional[str] = None, series_id: Optional[str] = None):
        self.class_id = class_id
        self.company = company  # Note: this was previously called 'fund'
        self._name = name
        self._ticker = ticker
        self.series_id = series_id  # The series ID this class belongs to
    
    @property
    def fund(self) -> FundCompany:
        """
        Get the parent fund company.
        
        This is provided for backward compatibility with the previous API where
        'fund' referred to what is now called 'company'.
        
        Returns:
            The parent FundCompany instance
        """
        return self.company
    
    @property
    def fund_company(self) -> FundCompany:
        """
        Get the parent fund company.
        
        This is a convenience alias for the 'company' property for backward
        compatibility and clarity.
        
        Returns:
            The parent FundCompany instance
        """
        return self.company
        
    @cached_property
    def series(self) -> Optional[FundSeries]:
        """
        Get the parent fund series.
        
        This is a convenience method to navigate up the hierarchy.
        
        Returns:
            The parent FundSeries instance, or None if series_id is not set
        """
        if not self.series_id:
            return None
            
        # Look through all series to find the one that matches our series_id
        for series in self.company.get_series():
            if series.series_id == self.series_id:
                return series
                
        return None
        
    @property
    def ticker(self) -> Optional[str]:
        """
        Get the ticker for this fund class.
        
        Returns:
            Ticker symbol or None if not available
        """
        if self._ticker:
            return self._ticker
            
        # Try to get ticker from current implementation
        try:
            # Import inside the function to avoid circular imports
            from edgar.funds import get_fund_with_filings
            fund_class = get_fund_with_filings(self.class_id)
            if fund_class and hasattr(fund_class, 'ticker'):
                self._ticker = fund_class.ticker
                return self._ticker
        except Exception:
            pass
            
        return None
        
    @property
    def name(self) -> str:
        """
        Get the name of this fund class.
        
        Returns:
            Name of the fund class
        """
        if self._name:
            return self._name
            
        # Try to get name from the current implementation
        try:
            # Import inside the function to avoid circular imports
            from edgar.funds import get_fund_with_filings
            fund_class = get_fund_with_filings(self.class_id)
            if fund_class and hasattr(fund_class, 'name') and fund_class.name:
                self._name = str(fund_class.name)
                return self._name
        except Exception:
            pass
            
        # Fallback to default name
        return f"{self.company.data.name} - Class {self.class_id[-1]}"
        
    def get_performance(self) -> pd.DataFrame:
        """
        Get performance data for this fund class.
        
        Returns:
            DataFrame containing performance data
        """
        # Look for N-CSR filings (shareholder reports) which contain performance data
        filings = self.company.get_filings(form=['N-CSR'])
        if filings:
            latest_ncsr = filings.latest()
            if latest_ncsr:
                # Parse N-CSR for performance data
                # This would be implemented in a future version
                pass
                
        return pd.DataFrame()
        
    def get_filings(self, **kwargs) -> 'Filings':
        """
        Get filings for this specific fund class.
        
        Args:
            **kwargs: Filtering parameters passed to get_filings
            
        Returns:
            Filings object with filtered filings
        """
        return self.company.get_filings(**kwargs)
    
    def __str__(self):
        ticker_str = f" - {self.ticker}" if self.ticker else ""
        return f"FundClass({self.name} [{self.class_id}]{ticker_str})"
        
    def __repr__(self):
        return self.__str__()
        
    def __rich__(self):
        """Creates a rich representation of the fund class."""
        # Import locally to avoid circular imports
        from edgar.funds.core import FundClass as CoreFundClass
        
        # Create a temporary FundClass object to use its __rich__ method
        # This will be replaced in a future version with a native implementation
        cls = CoreFundClass.__new__(CoreFundClass)
        cls.class_id = self.class_id
        cls.fund = self.company  # Note: CoreFundClass uses 'fund' not 'company'
        cls._name = self._name
        cls._ticker = self._ticker
        cls.series_id = self.series_id
        
        # Call the rich method on the temporary FundClass object
        return cls.__rich__()


# === New Smart Finder Function ===

def find_fund(identifier: str) -> Union[FundCompany, FundSeries, FundClass]:
    """
    Smart factory that finds and returns the most appropriate fund entity.
    
    This function takes any type of fund identifier and returns the most specific
    entity that matches it. For a series ID, it returns a FundSeries. For a class ID
    or ticker, it returns a FundClass. For a company CIK, it returns a FundCompany.
    
    Args:
        identifier: Fund ticker (e.g., 'VFINX'), Series ID (e.g., 'S000001234'), 
                  Class ID (e.g., 'C000012345'), or CIK number
                  
    Returns:
        The most specific fund entity that matches the identifier:
        - FundClass for tickers and class IDs
        - FundSeries for series IDs
        - FundCompany for company CIKs
    """
    # Check for Series ID (S000XXXXX)
    if isinstance(identifier, str) and identifier.upper().startswith('S') and identifier[1:].isdigit():
        return get_fund_series(identifier)
        
    # Check for Class ID (C000XXXXX)
    if isinstance(identifier, str) and identifier.upper().startswith('C') and identifier[1:].isdigit():
        return get_fund_class(identifier)
        
    # Check for ticker symbol
    if is_fund_class_ticker(identifier):
        return get_fund_class(identifier)
    
    # Default to returning a FundCompany
    return get_fund_company(identifier)


# === Specialized Getter Functions ===

def get_fund_company(cik_or_identifier: Union[str, int]) -> FundCompany:
    """
    Get a fund company by its CIK or identifier.
    
    Args:
        cik_or_identifier: CIK number or other identifier
        
    Returns:
        FundCompany instance
    """
    return FundCompany(cik_or_identifier)


def get_fund_series(series_id: str) -> FundSeries:
    """
    Get a fund series by its Series ID.
    
    Args:
        series_id: Series ID (e.g., 'S000001234')
        
    Returns:
        FundSeries instance
        
    Raises:
        ValueError: If the series cannot be found
    """
    # Use direct_get_fund_with_filings to get information about the series
    from edgar.funds.data import direct_get_fund_with_filings
    
    try:
        # Try our direct implementation
        fund_info = direct_get_fund_with_filings(series_id)
        if fund_info and hasattr(fund_info, 'fund') and hasattr(fund_info.fund, 'cik'):
            # Create the parent fund company
            company = FundCompany(fund_info.fund.cik)
            
            # Get the series name
            series_name = fund_info.name if hasattr(fund_info, 'name') else f"Series {series_id}"
            
            # Create and return the FundSeries
            return FundSeries(series_id=series_id, name=series_name, company=company)  # type: ignore
    except Exception as e:
        log.debug(f"Error getting fund series {series_id} using direct lookup: {e}")
    
    # Fallback: Look at all fund companies and find the one with this series
    # This is less efficient but more comprehensive
    from edgar.entity.search import search_entities
    
    # Search for fund entities
    fund_entities = search_entities(entity_type="fund", limit=100)
    
    for entity_data in fund_entities:
        try:
            company = FundCompany(entity_data.cik)
            for series in company.get_series():
                if series.series_id == series_id:
                    return series
        except Exception:
            continue
    
    # If we can't find the series, create a synthetic one
    # Try to resolve just the company first
    from edgar.funds.data import resolve_fund_identifier
    
    try:
        # Extract company CIK from series ID if possible
        # This is a heuristic - some series IDs encode the CIK
        cik_from_series = int(series_id[1:])
        company = FundCompany(cik_from_series)
        series_name = f"Series {series_id}"
        return FundSeries(series_id=series_id, name=series_name, company=company)
    except Exception:
        # Last resort - create a company with a dummy CIK
        company = FundCompany("0")
        company._cik = 0  # Set directly to avoid validation
        series_name = f"Series {series_id}"  # Create a definite string value
        return FundSeries(series_id=series_id, name=series_name, company=company)


def get_fund_class(class_id_or_ticker: str) -> FundClass:
    """
    Get a fund class by its Class ID or ticker.
    
    Args:
        class_id_or_ticker: Class ID (e.g., 'C000012345') or ticker symbol (e.g., 'VFINX')
        
    Returns:
        FundClass instance
        
    Raises:
        ValueError: If the class cannot be found
    """
    # If it's a ticker, get the class ID first
    class_id = class_id_or_ticker
    if is_fund_class_ticker(class_id_or_ticker):
        # Use get_class_id_for_ticker to convert ticker to class ID
        from edgar.funds.core import get_class_id_for_ticker
        class_id = get_class_id_for_ticker(class_id_or_ticker)
    
    # Now that we have a class ID, get information about it
    from edgar.funds.data import direct_get_fund_with_filings
    
    try:
        # Try our direct implementation
        fund_info = direct_get_fund_with_filings(class_id)
        if fund_info and hasattr(fund_info, 'fund_cik'):
            # Create the parent fund company
            company = FundCompany(fund_info.fund_cik)
            
            # Get the class attributes
            class_name = str(fund_info.name) if hasattr(fund_info, 'name') and fund_info.name else None
            ticker = class_id_or_ticker if is_fund_class_ticker(class_id_or_ticker) else None
            
            # Get the series ID if available
            series_id = None
            if hasattr(fund_info, 'fund') and hasattr(fund_info.fund, 'ident_info'):
                series_str = fund_info.fund.ident_info.get('Series', '')
                if series_str and series_str.startswith('S'):
                    series_match = re.match(r'([S]\d+)', series_str)
                    if series_match:
                        series_id = series_match.group(1)
            
            # Create and return the FundClass
            return FundClass(
                class_id=class_id,
                company=company,
                name=class_name or f"Class {class_id[-5:]}",  # Ensure we have a valid name
                ticker=ticker,
                series_id=series_id
            )
    except Exception as e:
        log.debug(f"Error getting fund class {class_id} using direct lookup: {e}")
    
    # Fallback: Use the original implementation
    from edgar.funds.core import get_fund
    
    try:
        # Use the existing get_fund function
        result = get_fund(class_id_or_ticker)
        
        # Convert the result to our new structure
        if hasattr(result, 'class_id'):  # It's a FundClass
            # Create our FundCompany from the Fund
            company = FundCompany(result.fund.cik)
            
            # Convert to our FundClass
            return FundClass(
                class_id=result.class_id,
                company=company,
                name=result.name,
                ticker=result.ticker,
                series_id=result.series_id
            )
        else:
            raise ValueError(f"Expected a fund class for {class_id_or_ticker}, but got a fund company")
    except Exception as e:
        raise ValueError(f"Could not find fund class {class_id_or_ticker}: {e}")


# === Helper Functions ===

def is_fund_class_ticker(identifier: str) -> bool:
    """
    Determine if the given identifier is a fund class ticker.
    
    Args:
        identifier: The identifier to check
        
    Returns:
        True if it's a fund class ticker, False otherwise
    """
    from edgar.funds.data import is_fund_ticker
    return is_fund_ticker(identifier)


def get_series_by_name(company_cik: int, name: str) -> Optional[FundSeries]:
    """
    Get a fund series by its name within a fund company.
    
    Args:
        company_cik: CIK of the fund company
        name: Name of the series to find (case-insensitive)
        
    Returns:
        FundSeries instance, or None if not found
    """
    company = FundCompany(company_cik)
    
    # Normalize the search name
    search_name = name.lower().strip()
    
    # Search all series for a matching name
    for series in company.get_series():
        if series.name.lower().strip() == search_name:
            return series
            
    # Try partial matching
    for series in company.get_series():
        if search_name in series.name.lower():
            return series
            
    return None


def get_class_by_ticker(ticker: str) -> FundClass:
    """
    Get a fund class by its ticker symbol.
    
    This is a convenience function and is equivalent to:
    get_fund_class(ticker)
    
    Args:
        ticker: Ticker symbol (e.g., 'VFINX')
        
    Returns:
        FundClass instance
        
    Raises:
        ValueError: If the class cannot be found
    """
    return get_fund_class(ticker)