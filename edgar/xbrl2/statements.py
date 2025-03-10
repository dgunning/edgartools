"""
Financial statement processing for XBRL data.

This module provides functions for working with financial statements.
"""

from typing import Dict, List, Any, Optional

import pandas as pd
from rich import box
from rich.table import Table


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
    
    def __getitem__(self, item):
        """
        Get a statement by index.
        
        Args:
            item: Integer index or string statement type
            
        Returns:
            Statement data or list of statements
        """
        if isinstance(item, int):
            return self.statements[item]
        elif isinstance(item, str):
            return self.statement_by_type.get(item, [])
        return None
    
    def __rich__(self):
        """
        Rich console representation.
        
        Returns:
            Rich Table object
        """
        table = Table(title="Available Statements", box=box.SIMPLE)
        table.add_column("Statement")
        table.add_column("Type")
        table.add_column("Elements")
        for stmt in self.statements:
            table.add_row(stmt['definition'], stmt['type'] or "", str(stmt['element_count']))
        return table
    
    def balance_sheet(self, period_view: Optional[str] = None, standard: bool = False) -> Table:
        """
        Get a formatted balance sheet.
        
        Args:
            period_view: Optional period view name
            standard: Whether to use standardized concept labels (default: False)
            
        Returns:
            Rich Table containing the balance sheet
        """
        return self.xbrl.render_statement("BalanceSheet", period_view=period_view, standard=standard)
    
    def income_statement(self, period_view: Optional[str] = None, standard: bool = False) -> Table:
        """
        Get a formatted income statement.
        
        Args:
            period_view: Optional period view name
            standard: Whether to use standardized concept labels (default: False)
            
        Returns:
            Rich Table containing the income statement
        """
        return self.xbrl.render_statement("IncomeStatement", period_view=period_view, standard=standard)
    
    def cash_flow_statement(self, period_view: Optional[str] = None, standard: bool = False) -> Table:
        """
        Get a formatted cash flow statement.
        
        Args:
            period_view: Optional period view name
            standard: Whether to use standardized concept labels (default: False)
            
        Returns:
            Rich Table containing the cash flow statement
        """
        return self.xbrl.render_statement("CashFlowStatement", period_view=period_view, standard=standard)
    
    def statement_of_equity(self, period_view: Optional[str] = None, standard: bool = False) -> Table:
        """
        Get a formatted statement of equity.
        
        Args:
            period_view: Optional period view name
            standard: Whether to use standardized concept labels (default: False)
            
        Returns:
            Rich Table containing the statement of equity
        """
        return self.xbrl.render_statement("StatementOfEquity", period_view=period_view, standard=standard)
    
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