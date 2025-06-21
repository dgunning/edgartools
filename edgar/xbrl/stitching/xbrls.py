"""
XBRL Statement Stitching - XBRLS Class

This module contains the XBRLS class which represents multiple XBRL filings
stitched together for multi-period analysis.
"""

from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

import pandas as pd

from edgar.xbrl.stitching.core import StatementStitcher, stitch_statements
from edgar.xbrl.stitching.query import StitchedFactsView, StitchedFactQuery

if TYPE_CHECKING:
    from edgar.xbrl.statements import StitchedStatements


class XBRLS:
    """
    A class representing multiple XBRL filings stitched together.
    
    This provides a unified view of financial data across multiple time periods,
    automatically handling the complexities of statement stitching.
    """
    
    def __init__(self, xbrl_list: List[Any]):
        """
        Initialize an XBRLS instance with a list of XBRL objects.
        
        Args:
            xbrl_list: List of XBRL objects, should be from the same company
                       and ordered from newest to oldest
        """
        # Store the list of XBRL objects
        self.xbrl_list = xbrl_list
        
        # Extract entity info from the most recent XBRL
        self.entity_info = xbrl_list[0].entity_info if xbrl_list else {}
        
        # Cache for stitched statements
        self._statement_cache = {}
        
        # Cache for stitched facts view
        self._stitched_facts_view = None
    
    @classmethod
    def from_filings(cls, filings: Union['Filings', List[Any]]) -> 'XBRLS':
        """
        Create an XBRLS object from a list of Filing objects or a Filings object containing multiple filings.
        Each filing should be the same form (e.g., 10-K, 10-Q) and from the same company.
        
        Args:
            filings: List of Filing objects, should be from the same company
            
        Returns:
            XBRLS object with stitched data
        """
        from edgar.xbrl.xbrl import XBRL
        
        # Sort filings by date (newest first)
        sorted_filings = sorted(filings, key=lambda f: f.filing_date, reverse=True)
        
        # Create XBRL objects from filings
        xbrl_list = []
        for filing in sorted_filings:
            try:
                xbrl = XBRL.from_filing(filing)
                xbrl_list.append(xbrl)
            except Exception as e:
                print(f"Warning: Could not parse XBRL from filing {filing.accession_number}: {e}")
        
        return cls(xbrl_list)
    
    @classmethod
    def from_xbrl_objects(cls, xbrl_list: List[Any]) -> 'XBRLS':
        """
        Create an XBRLS object from a list of XBRL objects.
        
        Args:
            xbrl_list: List of XBRL objects, should be from the same company
            
        Returns:
            XBRLS object with stitched data
        """
        return cls(xbrl_list)
    
    @property
    def statements(self) -> 'StitchedStatements':
        """
        Get a user-friendly interface to access stitched financial statements.
        
        Returns:
            StitchedStatements object
        """
        from edgar.xbrl.statements import StitchedStatements
        return StitchedStatements(self)
    
    @property
    def facts(self) -> StitchedFactsView:
        """
        Get a view over stitched facts from all XBRL filings.
        
        Returns:
            StitchedFactsView for querying standardized, multi-period data
        """
        if self._stitched_facts_view is None:
            self._stitched_facts_view = StitchedFactsView(self)
        return self._stitched_facts_view
    
    def query(self, 
              max_periods: int = 8,
              standardize: bool = True,
              statement_types: Optional[List[str]] = None,
              **kwargs) -> StitchedFactQuery:
        """
        Start a new query for stitched facts across all filings.
        
        Args:
            max_periods: Maximum periods to include in stitched data
            standardize: Whether to use standardized labels
            statement_types: List of statement types to include
            **kwargs: Additional options passed to StitchedFactQuery
            
        Returns:
            StitchedFactQuery for building complex queries
        """
        # Pass query parameters to the StitchedFactQuery
        kwargs.update({
            'max_periods': max_periods,
            'standardize': standardize,
            'statement_types': statement_types
        })
        return self.facts.query(**kwargs)
    
    def get_statement(self, statement_type: str, 
                     max_periods: int = 8, 
                     standardize: bool = True,
                     use_optimal_periods: bool = True) -> Dict[str, Any]:
        """
        Get a stitched statement of the specified type.
        
        Args:
            statement_type: Type of statement to stitch ('IncomeStatement', 'BalanceSheet', etc.)
            max_periods: Maximum number of periods to include
            standardize: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            
        Returns:
            Dictionary with stitched statement data
        """
        # Check cache first
        cache_key = f"{statement_type}_{max_periods}_{standardize}_{use_optimal_periods}"
        if cache_key in self._statement_cache:
            return self._statement_cache[cache_key]
        
        # Stitch the statement
        result = stitch_statements(
            self.xbrl_list,
            statement_type=statement_type,
            period_type=StatementStitcher.PeriodType.ALL_PERIODS,
            max_periods=max_periods,
            standard=standardize,
            use_optimal_periods=use_optimal_periods
        )
        
        # Cache the result
        self._statement_cache[cache_key] = result
        
        return result
    
    def render_statement(self, statement_type: str, 
                        max_periods: int = 8, 
                        standardize: bool = True,
                        use_optimal_periods: bool = True,
                        show_date_range: bool = False):
        """
        Render a stitched statement in a rich table format.
        
        Args:
            statement_type: Type of statement to render ('BalanceSheet', 'IncomeStatement', etc.)
            max_periods: Maximum number of periods to include
            standardize: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            show_date_range: Whether to show full date ranges for duration periods
            
        Returns:
            RichTable: A formatted table representation of the stitched statement
        """
        # Create a StitchedStatement object and use its render method
        from edgar.xbrl.statements import StitchedStatement
        statement = StitchedStatement(self, statement_type, max_periods, standardize, use_optimal_periods)
        return statement.render(show_date_range=show_date_range)
    
    def to_dataframe(self, statement_type: str, 
                    max_periods: int = 8, 
                    standardize: bool = True) -> pd.DataFrame:
        """
        Convert a stitched statement to a pandas DataFrame.
        
        Args:
            statement_type: Type of statement to convert ('BalanceSheet', 'IncomeStatement', etc.)
            max_periods: Maximum number of periods to include
            standardize: Whether to use standardized concept labels
            
        Returns:
            DataFrame with periods as columns and concepts as index
        """
        # Create a StitchedStatement object and use its to_dataframe method
        from edgar.xbrl.statements import StitchedStatement
        statement = StitchedStatement(self, statement_type, max_periods, standardize)
        return statement.to_dataframe()
    
    def get_periods(self) -> List[Dict[str, str]]:
        """
        Get all available periods across all XBRL objects.
        
        Returns:
            List of period information dictionaries
        """
        all_periods = []
        
        # Go through all XBRL objects to collect periods
        for xbrl in self.xbrl_list:
            all_periods.extend(xbrl.reporting_periods)
        
        # De-duplicate periods with the same labels
        unique_periods = {}
        for period in all_periods:
            # Use the date string as the unique key
            key = period['date'] if period['type'] == 'instant' else f"{period['start_date']}_{period['end_date']}"
            if key not in unique_periods:
                unique_periods[key] = period
        
        return list(unique_periods.values())
    
    def __str__(self) -> str:
        """
        String representation of the XBRLS object.
        
        Returns:
            String representation
        """
        filing_count = len(self.xbrl_list)
        periods = self.get_periods()
        return f"XBRLS with {filing_count} filings covering {len(periods)} unique periods"
    
    def __rich__(self):
        """
        Rich representation for pretty console output.
        
        Returns:
            Rich console representation
        """
        from rich.panel import Panel
        from rich.text import Text
        
        # Get information about the XBRLS object
        filing_count = len(self.xbrl_list)
        periods = self.get_periods()
        
        # Create a panel with the information
        content = Text.from_markup("[bold]XBRLS Object[/bold]\n")
        content.append(f"Filings: {filing_count}\n")
        content.append(f"Unique Periods: {len(periods)}\n")
        
        # List available statement types
        statement_types = set()
        for xbrl in self.xbrl_list:
            statements = xbrl.get_all_statements()
            for stmt in statements:
                if stmt['type']:
                    statement_types.add(stmt['type'])
        
        content.append("\n[bold]Available Statement Types:[/bold]\n")
        for stmt_type in sorted(statement_types):
            content.append(f"- {stmt_type}\n")
        
        # Show how to access statements
        content.append("\n[bold]Example Usage:[/bold]\n")
        content.append("xbrls.statements.income_statement()\n")
        content.append("xbrls.statements.balance_sheet()\n")
        content.append("xbrls.to_dataframe('IncomeStatement')\n")
        
        return Panel(content, title="XBRLS", expand=False)