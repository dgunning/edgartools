"""
Financial statement processing for XBRL data.

This module provides functions for working with financial statements.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Union

import pandas as pd
from rich import box
from rich.table import Table

from edgar.richtools import repr_rich


@dataclass
class StatementInfo:
    name: str
    concept: str
    title: str


statement_to_concepts = {
    "IncomeStatement": StatementInfo(name="IncomeStatement",
                                     concept="us-gaap_IncomeStatementAbstract",
                                     title="Consolidated Statement of Income"),
    "BalanceSheet": StatementInfo(name="BalanceSheet",
                                  concept="us-gaap_StatementOfFinancialPositionAbstract",
                                  title="Consolidated Balance Sheets",
                                  ),
    "CashFlowStatement": StatementInfo(name="CashFlowStatement",
                                       concept="us-gaap_StatementOfCashFlowsAbstract",
                                       title="Consolidated Statement of Cash Flows"),
    "StatementOfEquity": StatementInfo(name="StatementOfEquity",
                                       concept="us-gaap_StatementOfStockholdersEquityAbstract",
                                       title="Consolidated Statement of Equity"
                                       ),
    "ComprehensiveIncome": StatementInfo(name="ComprehensiveIncome",
                                         concept="us-gaap_StatementOfIncomeAndComprehensiveIncomeAbstract",
                                         title="Consolidated Statement of Comprehensive Income"
                                         ),
    "CoverPage": StatementInfo(name="CoverPage",
                               concept="dei_CoverAbstract",
                                 title="Cover Page"
                                 ),

}


class StatementValidationError(Exception):
    """Raised when statement validation fails."""
    pass


class Statement:
    """
    A single financial statement extracted from XBRL data.
    
    This class provides convenient methods for rendering and manipulating a specific
    financial statement. It includes validation, normalization, and analysis capabilities.
    
    Features:
    - Statement structure validation
    - Error handling for missing/malformed data
    - Statement normalization across different companies
    - Common financial analysis methods
    - Ratio calculations and trend analysis
    """

    # Required concepts for each statement type
    REQUIRED_CONCEPTS = {
        'BalanceSheet': [
            'us-gaap_Assets',
            'us-gaap_Liabilities',
            'us-gaap_StockholdersEquity'
        ],
        'IncomeStatement': [
            'us-gaap_Revenues',
            'us-gaap_NetIncomeLoss'
        ],
        'CashFlowStatement': [
            'us-gaap_CashAndCashEquivalentsPeriodIncreaseDecrease',
            'us-gaap_CashAndCashEquivalentsAtCarryingValue'
        ]
    }
    
    def __init__(self, xbrl, role_or_type: str):
        """
        Initialize with an XBRL object and statement identifier.
        
        Args:
            xbrl: XBRL object containing parsed data
            role_or_type: Role URI, statement type, or statement short name
            
        Raises:
            StatementValidationError: If statement validation fails
        """
        self.xbrl = xbrl
        self.role_or_type = role_or_type
        self._validate_statement()

    def is_segmented(self) -> bool:
        """
        Check if the statement is a segmented statement.

        Returns:
            True if the statement is segmented, False otherwise
        """
        return self.role_or_type.startswith("Segment")

    def render(self, period_filter: Optional[str] = None,
               period_view: Optional[str] = None,
               standard: bool = True,
               show_date_range: bool = False) -> Any:
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

    def __rich__(self) -> Any:
        """
        Rich console representation.

        Returns:
            Rich Table object if rich is available, else string representation
        """
        if Table is None:
            return str(self)
        return self.render()

    def __repr__(self):
        return repr_rich(self.__rich__())

    @property
    def primary_concept(self):
        data = self.get_raw_data()
        return data[0]['all_names'][0]

    def to_dataframe(self,
                     period_filter:str=None,
                     period_view:str=None,
                     standard:bool=True ) -> Any:
        """Convert statement to pandas DataFrame.
            period_filter: Optional period key to filter facts
            period_view: Optional name of a predefined period view
            standard: Whether to use standardized concept labels
        
        Returns:
            DataFrame if pandas is available, else None
        """
        rendered_statement = self.render(period_filter=period_filter, period_view=period_view, standard=standard)
        return rendered_statement.to_dataframe()

    def _validate_statement(self) -> None:
        """Validate the statement structure and required concepts."""
        data = self.get_raw_data()
        if not data:
            raise StatementValidationError(f"No data found for statement {self.role_or_type}")
            
        # Check for required concepts if this is a standard statement type
        if self.role_or_type in self.REQUIRED_CONCEPTS:
            missing_concepts = []
            for concept in self.REQUIRED_CONCEPTS[self.role_or_type]:
                if not any(concept in item.get('all_names', []) for item in data):
                    missing_concepts.append(concept)
                    
            if missing_concepts:
                raise StatementValidationError(
                    f"Missing required concepts for {self.role_or_type}: {', '.join(missing_concepts)}")
        
    def calculate_ratios(self) -> Dict[str, float]:
        """Calculate common financial ratios for this statement."""
        ratios = {}
        data = self.get_raw_data()
        
        if self.role_or_type == 'BalanceSheet':
            # Calculate balance sheet ratios
            ratios.update(self._calculate_balance_sheet_ratios(data))
        elif self.role_or_type == 'IncomeStatement':
            # Calculate income statement ratios
            ratios.update(self._calculate_income_statement_ratios(data))
            
        return ratios
        
    def _calculate_balance_sheet_ratios(self, data: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate balance sheet specific ratios."""
        ratios = {}
        
        # Current ratio
        current_assets = self._get_concept_value(data, 'us-gaap_CurrentAssets')
        current_liabilities = self._get_concept_value(data, 'us-gaap_CurrentLiabilities')
        if current_assets and current_liabilities:
            ratios['current_ratio'] = current_assets / current_liabilities
            
        # Quick ratio
        inventory = self._get_concept_value(data, 'us-gaap_Inventory')
        if current_assets and current_liabilities and inventory:
            ratios['quick_ratio'] = (current_assets - inventory) / current_liabilities
            
        return ratios
        
    def _calculate_income_statement_ratios(self, data: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate income statement specific ratios."""
        ratios = {}
        
        # Gross margin
        revenue = self._get_concept_value(data, 'us-gaap_Revenues')
        gross_profit = self._get_concept_value(data, 'us-gaap_GrossProfit')
        if revenue and gross_profit:
            ratios['gross_margin'] = gross_profit / revenue
            
        # Net margin
        net_income = self._get_concept_value(data, 'us-gaap_NetIncomeLoss')
        if revenue and net_income:
            ratios['net_margin'] = net_income / revenue
            
        return ratios
        
    def _get_concept_value(self, data: List[Dict[str, Any]], concept: str) -> Optional[float]:
        """Get the value for a specific concept from statement data."""
        for item in data:
            if concept in item.get('all_names', []):
                values = item.get('values', {})
                if values:
                    return float(next(iter(values.values())))
        return None
        
    def analyze_trends(self, periods: int = 4) -> Dict[str, List[float]]:
        """Analyze trends in key metrics over time."""
        trends = {}
        
        # Get data for multiple periods
        period_views = self.xbrl.get_period_views(self.role_or_type)
        if not period_views:
            return trends
            
        periods_to_analyze = period_views[0].get('periods', [])[:periods]
        
        for period in periods_to_analyze:
            data = self.get_raw_data(period)
            
            if self.role_or_type == 'BalanceSheet':
                self._analyze_balance_sheet_trends(data, trends, period)
            elif self.role_or_type == 'IncomeStatement':
                self._analyze_income_statement_trends(data, trends, period)
                
        return trends
        
    def _analyze_balance_sheet_trends(self, data: List[Dict[str, Any]], 
                                     trends: Dict[str, List[float]], 
                                     period: str) -> None:
        """Analyze balance sheet trends."""
        metrics = {
            'total_assets': 'us-gaap_Assets',
            'total_liabilities': 'us-gaap_Liabilities',
            'equity': 'us-gaap_StockholdersEquity'
        }
        
        for metric_name, concept in metrics.items():
            value = self._get_concept_value(data, concept)
            if value:
                if metric_name not in trends:
                    trends[metric_name] = []
                trends[metric_name].append(value)
                
    def _analyze_income_statement_trends(self, data: List[Dict[str, Any]], 
                                        trends: Dict[str, List[float]], 
                                        period: str) -> None:
        """Analyze income statement trends."""
        metrics = {
            'revenue': 'us-gaap_Revenues',
            'gross_profit': 'us-gaap_GrossProfit',
            'net_income': 'us-gaap_NetIncomeLoss'
        }
        
        for metric_name, concept in metrics.items():
            value = self._get_concept_value(data, concept)
            if value:
                if metric_name not in trends:
                    trends[metric_name] = []
                trends[metric_name].append(value)
                
    def get_raw_data(self, period_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get the raw statement data.
        
        Args:
            period_filter: Optional period key to filter facts
            
        Returns:
            List of line items with values
            
        Raises:
            StatementValidationError: If data retrieval fails
        """
        data = self.xbrl.get_statement(self.role_or_type, period_filter=period_filter)
        if data is None:
            raise StatementValidationError(f"Failed to retrieve data for statement {self.role_or_type}")
        return data


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

    def find_statement_by_primary_concept(self, statement_type: str, is_parenthetical: bool = False) -> Optional[str]:
        """
        Find a statement by its primary concept.
        
        Args:
            statement_type: Statement type (e.g., 'BalanceSheet', 'IncomeStatement')
            is_parenthetical: Whether to look for a parenthetical statement
                             (only applicable for BalanceSheet)
            
        Returns:
            Role URI for the matching statement, or None if not found
        """
        if statement_type not in statement_to_concepts:
            return None
            
        # Get information about the statement's identifying concept
        concept_info = statement_to_concepts[statement_type]
        concept = concept_info.concept
        
        # Find all statements of the requested type
        matching_statements = self.statement_by_type.get(statement_type, [])
        
        if not matching_statements:
            return None
            
        # Parenthetical check is only relevant for BalanceSheet
        check_parenthetical = statement_type == 'BalanceSheet'
            
        # Try to find a statement containing the specific concept
        for stmt in matching_statements:
            role = stmt['role']
            
            # Check for parenthetical in the role name if it's a BalanceSheet
            if check_parenthetical:
                role_lower = role.lower()
                is_role_parenthetical = 'parenthetical' in role_lower
                
                # Skip if parenthetical status doesn't match what we're looking for
                if is_parenthetical != is_role_parenthetical:
                    continue
                
            # Examine the presentation tree for this role
            if role in self.xbrl.presentation_trees:
                tree = self.xbrl.presentation_trees[role]
                # Check if the identifying concept is in this tree
                normalized_concept = concept.replace(':', '_')
                for element_id in tree.all_nodes:
                    # Check both original and normalized form
                    if element_id == concept or element_id == normalized_concept:
                        return role
        
        # If no exact concept match, fall back to the first statement of the type
        # that matches the parenthetical requirement for BalanceSheet
        if check_parenthetical:
            for stmt in matching_statements:
                role = stmt['role']
                role_lower = role.lower()
                is_role_parenthetical = 'parenthetical' in role_lower
                
                if is_parenthetical == is_role_parenthetical:
                    return role
                
        # If still no match, return the first statement
        return matching_statements[0]['role']

    def __getitem__(self, item: Union[int, str]) -> Optional[Statement]:
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
            # Check if it's a standard statement type with a specific concept marker
            if item in statement_to_concepts:
                # Get the statement role using the primary concept
                role = self.find_statement_by_primary_concept(item)
                if role:
                    return Statement(self.xbrl, role)
                    
                # If no concept match, fall back to the type
                return Statement(self.xbrl, item)
                    
            # If it's a statement type with multiple statements, return the first one
            if item in self.statement_by_type and self.statement_by_type[item]:
                return Statement(self.xbrl, item)
            
            # Otherwise, try to use it directly as a role or statement name
            return Statement(self.xbrl, item)

    def __rich__(self) -> Any:
        """
        Rich console representation.
        
        Returns:
            Rich Table object if rich is available, else string representation
        """
        if Table is None:
            return str(self)
            
        table = Table(title="Available Statements", box=box.SIMPLE if box else None)
        table.add_column("#")
        table.add_column("Statement")
        table.add_column("Type")
        table.add_column("Elements")
        for index, stmt in enumerate(self.statements):
            table.add_row(str(index), stmt['definition'], stmt['type'] or "", str(stmt['element_count']))
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())

    def balance_sheet(self, parenthetical: bool = False) -> Statement:
        """
        Get a balance sheet.
        
        Args:
            parenthetical: Whether to get the parenthetical balance sheet
            
        Returns:
            A balance sheet statement
        """
        role = self.find_statement_by_primary_concept("BalanceSheet", is_parenthetical=parenthetical)
        if role:
            return Statement(self.xbrl, role)
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

    def to_dataframe(self,
                     statement_type: str,
                     period_view: Optional[str] = None,
                     standard: bool = True) -> Optional[pd.DataFrame]:
        """
        Convert a statement to a pandas DataFrame.
        
        Args:
            statement_type: Type of statement to convert
            period_view: Optional period view name
            standard: Whether to use standardized concept labels (default: True)
            
        Returns:
            pandas DataFrame containing the statement data
        """
        statement = self[statement_type]
        if standard:
            return statement.render(period_view=period_view, standard=standard).to_dataframe()


class StitchedStatement:
    """
    A stitched financial statement across multiple time periods.
    
    This class provides convenient methods for rendering and manipulating a stitched
    financial statement from multiple filings.
    """

    def __init__(self, xbrls, statement_type: str, max_periods: int = 8, standardize: bool = True,
                 use_optimal_periods: bool = True):
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
                      use_optimal_periods: bool = True, show_date_range: bool = False) -> Optional[StitchedStatement]:
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
                         use_optimal_periods: bool = True, show_date_range: bool = False) -> Optional[StitchedStatement]:
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
                            use_optimal_periods: bool = True, show_date_range: bool = False) -> Optional[StitchedStatement]:
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
                            use_optimal_periods: bool = True, show_date_range: bool = False) -> Optional[StitchedStatement]:
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
                             use_optimal_periods: bool = True, show_date_range: bool = False) -> Optional[StitchedStatement]:
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
