"""
Financial statement processing for XBRL data.

This module provides functions for working with financial statements.
"""

from typing import Dict, List, Any, Optional, Union

import pandas as pd
from rich import box
from rich.table import Table
from edgar.richtools import repr_rich


class Statement:
    """
    A single financial statement extracted from XBRL data.
    
    This class provides convenient methods for rendering and manipulating a specific
    financial statement.
    """
    
    def __init__(self, xbrl, role_or_type: str):
        """
        Initialize with an XBRL object and statement identifier.
        
        Args:
            xbrl: XBRL object containing parsed data
            role_or_type: Role URI, statement type, or statement short name
        """
        self.xbrl = xbrl
        self.role_or_type = role_or_type
        
    def render(self, period_filter: Optional[str] = None, 
               period_view: Optional[str] = None, 
               standard: bool = True,
               show_date_range: bool = False) -> Table:
        """
        Render the statement as a formatted table.
        
        Args:
            period_filter: Optional period key to filter facts
            period_view: Optional name of a predefined period view
            standard: Whether to use standardized concept labels
            show_date_range: Whether to show full date ranges for duration periods
            
        Returns:
            Rich Table containing the rendered statement
        """
        return self.xbrl.render_statement(self.role_or_type, 
                                        period_filter=period_filter,
                                        period_view=period_view, 
                                        standard=standard,
                                        show_date_range=show_date_range)

    def __rich__(self):
        """
        Rich console representation.

        Returns:
            Rich Table object
        """
        return self.render()

    def __repr__(self):
        return repr_rich(self.__rich__())

    def _pandas_dataframes(self, standard: bool = True) -> Dict[str, pd.DataFrame]:
        """
        Convert the statement to pandas DataFrames.
        
        Args:
            standard: Whether to use standardized concept labels
            
        Returns:
            Dictionary of DataFrames for different aspects of the statement
        """
        return self.xbrl.to_pandas(self.role_or_type, standard=standard)

    def to_dataframe(self):
        return self._pandas_dataframes()['statement']
    
    def get_raw_data(self, period_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get the raw statement data.
        
        Args:
            period_filter: Optional period key to filter facts
            
        Returns:
            List of line items with values
        """
        return self.xbrl.get_statement(self.role_or_type, period_filter=period_filter)


class Statements:
    """
    High-level interface for working with XBRL financial statements.
    
    This class provides a user-friendly way to access and manipulate 
    financial statements extracted from XBRL data.
    """
    
    def __init__(self, xbrl):
        """
        Initialize with an XBRL object.
        
        Args:
            xbrl: XBRL object containing parsed data
        """
        self.xbrl = xbrl
        self.statements = xbrl.get_all_statements()
        
        # Create statement type lookup for quick access
        self.statement_by_type = {}
        for stmt in self.statements:
            if stmt['type']:
                if stmt['type'] not in self.statement_by_type:
                    self.statement_by_type[stmt['type']] = []
                self.statement_by_type[stmt['type']].append(stmt)
    
    def __getitem__(self, item) -> Optional[Statement]:
        """
        Get a statement by index, type, or role.
        
        Args:
            item: Integer index, string statement type, or role URI
            
        Returns:
            Statement instance for the requested statement
        """
        if isinstance(item, int):
            if 0 <= item < len(self.statements):
                stmt = self.statements[item]
                return Statement(self.xbrl, stmt['role'])
        elif isinstance(item, str):
            # If it's a statement type with multiple statements, return the first one
            if item in self.statement_by_type and self.statement_by_type[item]:
                return Statement(self.xbrl, item)
            # Otherwise, try to use it directly as a role or statement name
            return Statement(self.xbrl, item)
    
    def __rich__(self):
        """
        Rich console representation.
        
        Returns:
            Rich Table object
        """
        table = Table(title="Available Statements", box=box.SIMPLE)
        table.add_column("#")
        table.add_column("Statement")
        table.add_column("Type")
        table.add_column("Elements")
        for index, stmt in enumerate(self.statements):
            table.add_row(str(index), stmt['definition'], stmt['type'] or "", str(stmt['element_count']))
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())
    
    def balance_sheet(self) -> Statement:
        """
        Get a balance sheet.
            
        Returns:
            A balance sheet statement
        """
        return self["BalanceSheet"]
    
    def income_statement(self) -> Statement:
        """
        Get an income statement.

        Returns:
            An income statement
        """
        return self["IncomeStatement"]
    
    def cash_flow_statement(self) -> Statement:
        """
        Get a cash flow statement.

        Returns:
             The cash flow statement
        """
        return self["CashFlowStatement"]
    
    def statement_of_equity(self) -> Statement:
        """
        Get a statement of equity.
            
        Returns:
           The statement of equity
        """
        return self["StatementOfEquity"]

    def get_period_views(self, statement_type: str) -> List[Dict[str, Any]]:
        """
        Get available period views for a statement type.
        
        Args:
            statement_type: Type of statement to get period views for
            
        Returns:
            List of period view options
        """
        return self.xbrl.get_period_views(statement_type)
    
    def to_dataframe(self, statement_type: str, period_view: Optional[str] = None, standard: bool = True) -> pd.DataFrame:
        """
        Convert a statement to a pandas DataFrame.
        
        Args:
            statement_type: Type of statement to convert
            period_view: Optional period view name
            standard: Whether to use standardized concept labels (default: True)
            
        Returns:
            pandas DataFrame containing the statement data
        """
        # Get the statement data with the right periods
        statement_data = None
        
        # If period view specified, use it
        if period_view:
            period_views = self.xbrl.get_period_views(statement_type)
            matching_view = next((view for view in period_views if view['name'] == period_view), None)
            
            if matching_view:
                role = next(
                    (stmt['role'] for stmt in self.statements if stmt['type'] == statement_type), 
                    None
                )
                if role:
                    # Get statement data with period keys from view
                    period_filter = matching_view['period_keys'][0] if matching_view['period_keys'] else None
                    statement_data = self.xbrl.get_statement(role, period_filter=period_filter)
        
        # If no period view or it failed, just get the statement directly
        if not statement_data:
            role = next(
                (stmt['role'] for stmt in self.statements if stmt['type'] == statement_type), 
                None
            )
            if role:
                statement_data = self.xbrl.get_statement(role)
        
        if not statement_data:
            return pd.DataFrame()  # Empty DataFrame if statement not found
            
        # Use XBRL's to_pandas method which now supports standardization
        dataframes = self.xbrl.to_pandas(statement_type, standard=standard)
        
        # Return the statement dataframe if available
        if 'statement' in dataframes:
            return dataframes['statement']
            
        # Fallback to manual conversion if to_pandas didn't work
        rows = []
        for item in statement_data:
            # Prepare row data
            row = {
                'concept': item['concept'],
                'label': item['label'],
                'level': item['level'],
                'is_abstract': item['is_abstract'],
                'has_values': item.get('has_values', False),
            }
            
            # Add original label if standardized
            if 'original_label' in item:
                row['original_label'] = item['original_label']
            
            # Add values for each period
            for period, value in item.get('values', {}).items():
                row[period] = value
            
            rows.append(row)
        
        return pd.DataFrame(rows)


class StitchedStatement:
    """
    A stitched financial statement across multiple time periods.
    
    This class provides convenient methods for rendering and manipulating a stitched
    financial statement from multiple filings.
    """
    
    def __init__(self, xbrls, statement_type: str, max_periods: int = 8, standardize: bool = True, use_optimal_periods: bool = True):
        """
        Initialize with XBRLS object and statement parameters.
        
        Args:
            xbrls: XBRLS object containing stitched data
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
            max_periods: Maximum number of periods to include
            standardize: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
        """
        self.xbrls = xbrls
        self.statement_type = statement_type
        self.max_periods = max_periods
        self.standardize = standardize
        self.use_optimal_periods = use_optimal_periods
        self.show_date_range = False  # Default to not showing date ranges
        
        # Statement titles
        self.statement_titles = {
            'BalanceSheet': 'CONSOLIDATED BALANCE SHEET',
            'IncomeStatement': 'CONSOLIDATED INCOME STATEMENT',
            'CashFlowStatement': 'CONSOLIDATED STATEMENT OF CASH FLOWS',
            'StatementOfEquity': 'CONSOLIDATED STATEMENT OF STOCKHOLDERS\' EQUITY',
            'ComprehensiveIncome': 'CONSOLIDATED STATEMENT OF COMPREHENSIVE INCOME'
        }
        self.title = self.statement_titles.get(statement_type, statement_type.upper())
        
        # Cache statement data
        self._statement_data = None
    
    @property
    def statement_data(self):
        """Get the underlying statement data, loading it if necessary."""
        if self._statement_data is None:
            self._statement_data = self.xbrls.get_statement(
                self.statement_type, 
                self.max_periods, 
                self.standardize,
                self.use_optimal_periods
            )
        return self._statement_data
    
    def render(self, show_date_range: bool = False) -> Table:
        """
        Render the stitched statement as a formatted table.
        
        Args:
            show_date_range: Whether to show full date ranges for duration periods
            
        Returns:
            Rich Table containing the rendered statement
        """
        from edgar.xbrl2.stitching import render_stitched_statement
        
        # Update the render_stitched_statement function call to pass the show_date_range parameter
        return render_stitched_statement(
            self.statement_data,
            statement_title=self.title,
            statement_type=self.statement_type,
            entity_info=self.xbrls.entity_info,
            show_date_range=show_date_range
        )
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert the stitched statement to a pandas DataFrame.
        
        Returns:
            pandas DataFrame with periods as columns and concepts as rows
        """
        from edgar.xbrl2.stitching import to_pandas
        
        return to_pandas(self.statement_data)
    
    def __rich__(self):
        """
        Rich console representation.
        
        Returns:
            Rich Table object
        """
        return self.render()
    
    def __repr__(self):
        return repr_rich(self.__rich__())
    
    def __str__(self) -> str:
        """
        String representation.
        
        Returns:
            String representation
        """
        return f"StitchedStatement({self.statement_type}, periods={len(self.statement_data['periods'])})"


class StitchedStatements:
    """
    User-friendly access to stitched financial statements across multiple time periods.
    
    This class provides a simplified API for accessing and rendering stitched financial
    statements from multiple filings, without requiring detailed knowledge of the
    underlying stitching process.
    """
    
    def __init__(self, xbrls):
        """
        Initialize with an XBRLS object.
        
        Args:
            xbrls: The XBRLS object to extract stitched statements from
        """
        self.xbrls = xbrls
        
    def balance_sheet(self, max_periods: int = 8, standardize: bool = True, 
                     use_optimal_periods: bool = True, show_date_range: bool = False) -> StitchedStatement:
        """
        Get a stitched balance sheet across multiple time periods.
        
        Args:
            max_periods: Maximum number of periods to include
            standardize: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            show_date_range: Whether to show full date ranges for duration periods
            
        Returns:
            StitchedStatement for the balance sheet
        """
        statement = StitchedStatement(self.xbrls, 'BalanceSheet', max_periods, standardize, use_optimal_periods)
        if show_date_range:
            statement.show_date_range = show_date_range
        return statement
    
    def income_statement(self, max_periods: int = 8, standardize: bool = True,
                         use_optimal_periods: bool = True, show_date_range: bool = False) -> StitchedStatement:
        """
        Get a stitched income statement across multiple time periods.
        
        Args:
            max_periods: Maximum number of periods to include
            standardize: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            show_date_range: Whether to show full date ranges for duration periods
            
        Returns:
            StitchedStatement for the income statement
        """
        statement = StitchedStatement(self.xbrls, 'IncomeStatement', max_periods, standardize, use_optimal_periods)
        if show_date_range:
            statement.show_date_range = show_date_range
        return statement
    
    def cash_flow_statement(self, max_periods: int = 8, standardize: bool = True,
                           use_optimal_periods: bool = True, show_date_range: bool = False) -> StitchedStatement:
        """
        Get a stitched cash flow statement across multiple time periods.
        
        Args:
            max_periods: Maximum number of periods to include
            standardize: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            show_date_range: Whether to show full date ranges for duration periods
            
        Returns:
            StitchedStatement for the cash flow statement
        """
        statement = StitchedStatement(self.xbrls, 'CashFlowStatement', max_periods, standardize, use_optimal_periods)
        if show_date_range:
            statement.show_date_range = show_date_range
        return statement
    
    def statement_of_equity(self, max_periods: int = 8, standardize: bool = True,
                           use_optimal_periods: bool = True, show_date_range: bool = False) -> StitchedStatement:
        """
        Get a stitched statement of changes in equity across multiple time periods.
        
        Args:
            max_periods: Maximum number of periods to include
            standardize: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            show_date_range: Whether to show full date ranges for duration periods
            
        Returns:
            StitchedStatement for the statement of equity
        """
        statement = StitchedStatement(self.xbrls, 'StatementOfEquity', max_periods, standardize, use_optimal_periods)
        if show_date_range:
            statement.show_date_range = show_date_range
        return statement
    
    def comprehensive_income(self, max_periods: int = 8, standardize: bool = True,
                            use_optimal_periods: bool = True, show_date_range: bool = False) -> StitchedStatement:
        """
        Get a stitched statement of comprehensive income across multiple time periods.
        
        Args:
            max_periods: Maximum number of periods to include
            standardize: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            show_date_range: Whether to show full date ranges for duration periods
            
        Returns:
            StitchedStatement for the comprehensive income statement
        """
        statement = StitchedStatement(self.xbrls, 'ComprehensiveIncome', max_periods, standardize, use_optimal_periods)
        if show_date_range:
            statement.show_date_range = show_date_range
        return statement
    
    def __getitem__(self, statement_type: str) -> StitchedStatement:
        """
        Get a statement by type using dictionary syntax.
        
        Args:
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
            
        Returns:
            StitchedStatement for the requested statement type
        """
        return StitchedStatement(self.xbrls, statement_type, use_optimal_periods=True)
    
    def __rich__(self):
        """
        Rich console representation.
        
        Returns:
            Rich Table object
        """
        table = Table(title="Available Stitched Statements", box=box.SIMPLE)
        table.add_column("Statement Type")
        table.add_column("Periods")
        
        # Get information about available statements
        statement_types = set()
        for xbrl in self.xbrls.xbrl_list:
            statements = xbrl.get_all_statements()
            for stmt in statements:
                if stmt['type']:
                    statement_types.add(stmt['type'])
        
        # Get periods
        periods = self.xbrls.get_periods()
        period_count = len(periods)
        
        # Add rows for each statement type
        for stmt_type in sorted(statement_types):
            table.add_row(stmt_type, str(period_count))
        
        return table
    
    def __repr__(self):
        return repr_rich(self.__rich__())
    
    def __str__(self) -> str:
        """
        String representation listing available statements.
        
        Returns:
            String representation
        """
        # Get information about available statements
        statement_types = set()
        for xbrl in self.xbrls.xbrl_list:
            statements = xbrl.get_all_statements()
            for stmt in statements:
                if stmt['type']:
                    statement_types.add(stmt['type'])
        
        # Get information about periods
        periods = self.xbrls.get_periods()
        period_count = len(periods)
        
        # Format output
        output = [f"Stitched statements across {period_count} periods:"]
        for stmt_type in sorted(statement_types):
            output.append(f"  - {stmt_type}")
        
        output.append("\nAvailable methods:")
        output.append("  - balance_sheet()")
        output.append("  - income_statement()")
        output.append("  - cash_flow_statement()")
        
        return "\n".join(output)