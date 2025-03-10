"""
XBRL Statement Stitching Module

This module provides functionality to combine multiple XBRL statements 
across different time periods into a unified view, handling concept 
consistency issues and normalizing data representation.
"""

from typing import Dict, List, Any, Optional, Union, Tuple, Set
from collections import defaultdict
from datetime import datetime
import pandas as pd
from enum import Enum

from edgar.xbrl2.core import format_date, parse_date
from edgar.xbrl2.standardization import (
    ConceptMapper, MappingStore, standardize_statement, StandardConcept, 
    initialize_default_mappings
)


class StatementStitcher:
    """
    Combines multiple statements across time periods into a unified view.
    
    This class handles the complexities of combining financial statements 
    from different periods, including:
    - Normalizing concepts that change over time
    - Aligning periods correctly
    - Handling missing data points
    - Providing both standardized and company-specific views
    """
    
    class PeriodType(str, Enum):
        """Types of period views available for stitched statements"""
        RECENT_PERIODS = "Most Recent Periods"
        RECENT_YEARS = "Recent Years"
        THREE_YEAR_COMPARISON = "Three-Year Comparison" 
        THREE_QUARTERS = "Three Recent Quarters"
        ANNUAL_COMPARISON = "Annual Comparison"
        QUARTERLY_TREND = "Quarterly Trend"
        ALL_PERIODS = "All Available Periods"
    
    def __init__(self, concept_mapper: Optional[ConceptMapper] = None):
        """
        Initialize a StatementStitcher instance.
        
        Args:
            concept_mapper: Optional ConceptMapper for standardizing concepts.
                            If None, a default mapper is created.
        """
        if concept_mapper is None:
            self.mapping_store = initialize_default_mappings()
            self.concept_mapper = ConceptMapper(self.mapping_store)
        else:
            self.concept_mapper = concept_mapper
            self.mapping_store = concept_mapper.mapping_store
        
        # Initialize data structures
        self.periods = []  # Ordered list of period identifiers
        self.period_dates = {}  # Maps period ID to display dates
        self.data = defaultdict(dict)  # {concept: {period: value}}
        self.concept_metadata = {}  # Metadata for each concept (level, etc.)
        
    def stitch_statements(
        self, 
        statements: List[Dict[str, Any]], 
        period_type: Union[PeriodType, str] = PeriodType.RECENT_PERIODS,
        max_periods: int = 3,
        standard: bool = True
    ) -> Dict[str, Any]:
        """
        Stitch multiple statements into a unified view.
        
        Args:
            statements: List of statement data from different filings
            period_type: Type of period view to generate
            max_periods: Maximum number of periods to include
            standard: Whether to use standardized concept labels
            
        Returns:
            Dictionary with stitched statement data
        """
        # Reset state
        self.periods = []
        self.period_dates = {}
        self.data = defaultdict(dict)
        self.concept_metadata = {}
        
        # Extract and sort all periods
        all_periods = self._extract_periods(statements)
        
        # Select appropriate periods based on period_type
        selected_periods = self._select_periods(all_periods, period_type, max_periods)
        self.periods = selected_periods
        
        # Process each statement
        for statement in statements:
            # Only process statements that have periods in our selection
            statement_periods = set(statement['periods'].keys())
            relevant_periods = statement_periods.intersection(set(selected_periods))
            
            if not relevant_periods:
                continue
                
            # Standardize the statement if needed
            if standard:
                processed_data = self._standardize_statement_data(statement)
            else:
                processed_data = statement['data']
            
            # Store data for each item
            self._integrate_statement_data(processed_data, statement['periods'], relevant_periods)
        
        # Format the stitched data
        return self._format_output()
    
    def _extract_periods(self, statements: List[Dict[str, Any]]) -> List[Tuple[str, datetime]]:
        """
        Extract and sort all periods from the statements.
        
        Args:
            statements: List of statement data
            
        Returns:
            List of (period_id, end_date) tuples, sorted by date (newest first)
        """
        all_periods = []
        
        for statement in statements:
            for period_id, period_info in statement['periods'].items():
                # Extract end date for sorting
                if period_id.startswith('instant_'):
                    date_str = period_id.split('_')[1]
                    display_date = period_info['label']
                else:  # duration
                    date_str = period_id.split('_')[2]  # end date
                    display_date = period_info['label']
                
                try:
                    end_date = parse_date(date_str)
                    all_periods.append((period_id, end_date))
                    self.period_dates[period_id] = display_date
                except (ValueError, TypeError, IndexError):
                    # Skip periods with invalid dates
                    continue
        
        # Sort by date, newest first
        return sorted(all_periods, key=lambda x: x[1], reverse=True)
    
    def _select_periods(
        self, 
        all_periods: List[Tuple[str, datetime]], 
        period_type: Union[PeriodType, str],
        max_periods: int
    ) -> List[str]:
        """
        Select appropriate periods based on period_type.
        
        Args:
            all_periods: List of (period_id, end_date) tuples
            period_type: Type of period view to generate
            max_periods: Maximum number of periods to include
            
        Returns:
            List of selected period IDs
        """
        if isinstance(period_type, str):
            try:
                period_type = StatementStitcher.PeriodType(period_type)
            except ValueError:
                # Default to recent periods if string doesn't match enum
                period_type = StatementStitcher.PeriodType.RECENT_PERIODS
        
        # Extract period types (instant vs duration)
        instants = [(pid, date) for pid, date in all_periods if pid.startswith('instant_')]
        durations = [(pid, date) for pid, date in all_periods if not pid.startswith('instant_')]
        
        # Apply different selection logic based on period_type
        if period_type == StatementStitcher.PeriodType.RECENT_PERIODS:
            # Just take the most recent periods up to max_periods
            return [pid for pid, _ in all_periods[:max_periods]]
            
        elif period_type == StatementStitcher.PeriodType.THREE_YEAR_COMPARISON:
            # For balance sheets, find year-end instants
            year_ends = []
            years_seen = set()
            
            for pid, date in instants:
                year = parse_date(date).year
                if year not in years_seen and len(year_ends) < max_periods:
                    year_ends.append(pid)
                    years_seen.add(year)
            
            return year_ends
            
        elif period_type == StatementStitcher.PeriodType.THREE_QUARTERS:
            # Find the most recent quarters (for income statements)
            quarterly_periods = []
            
            for pid, date in durations:
                # Check if this appears to be a quarterly period
                if not pid.startswith('duration_'):
                    continue
                    
                start_date_str = pid.split('_')[1]
                end_date_str = pid.split('_')[2]
                
                try:
                    start_date = parse_date(start_date_str)
                    end_date = parse_date(end_date_str)
                    days = (end_date - start_date).days
                    
                    # Assuming quarterly is around 90 days
                    if 80 <= days <= 95:
                        quarterly_periods.append(pid)
                        if len(quarterly_periods) >= max_periods:
                            break
                except (ValueError, TypeError, IndexError):
                    continue
            
            return quarterly_periods
            
        elif period_type == StatementStitcher.PeriodType.ANNUAL_COMPARISON:
            # Find annual periods (for income statements)
            annual_periods = []
            
            for pid, date in durations:
                # Check if this appears to be an annual period
                if not pid.startswith('duration_'):
                    continue
                    
                start_date_str = pid.split('_')[1]
                end_date_str = pid.split('_')[2]
                
                try:
                    start_date = parse_date(start_date_str)
                    end_date = parse_date(end_date_str)
                    days = (end_date - start_date).days
                    
                    # Assuming annual is around 365 days
                    if 350 <= days <= 380:
                        annual_periods.append(pid)
                        if len(annual_periods) >= max_periods:
                            break
                except (ValueError, TypeError, IndexError):
                    continue
            
            return annual_periods
            
        elif period_type == StatementStitcher.PeriodType.ALL_PERIODS:
            # Return all periods, newest first, up to max_periods
            return [pid for pid, _ in all_periods[:max_periods]]
            
        # Default to recent periods
        return [pid for pid, _ in all_periods[:max_periods]]
    
    def _standardize_statement_data(self, statement: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Standardize the statement data using the concept mapper.
        
        Args:
            statement: Statement data
            
        Returns:
            Standardized statement data
        """
        # Add statement type to context for better mapping
        statement_type = statement.get('statement_type', '')
        statement_data = statement['data']
        
        for item in statement_data:
            item['statement_type'] = statement_type
        
        # Apply standardization using the concept mapper
        return standardize_statement(statement_data, self.concept_mapper)
    
    def _integrate_statement_data(
        self, 
        statement_data: List[Dict[str, Any]], 
        period_map: Dict[str, Dict[str, str]],
        relevant_periods: Set[str]
    ) -> None:
        """
        Integrate statement data from one statement into the stitched view.
        
        Args:
            statement_data: Statement data
            period_map: Map of period IDs to period information
            relevant_periods: Set of periods from this statement to include
        """
        for item in statement_data:
            concept = item.get('concept')
            label = item.get('label')
            
            # Skip items without concept or label
            if not concept or not label:
                continue
                
            # Skip abstract items with no children (headers without data)
            if item.get('is_abstract', False) and not item.get('children'):
                continue
                
            # Skip dimension items
            if any(bracket in label for bracket in ['[Axis]', '[Domain]', '[Member]', '[Line Items]', '[Table]', '[Abstract]']):
                continue
            
            # Use label as the concept identifier for data storage
            # This works well with standardized labels
            concept_key = label
            
            # Store metadata about the concept (level, abstract status, etc.)
            if concept_key not in self.concept_metadata:
                self.concept_metadata[concept_key] = {
                    'level': item.get('level', 0),
                    'is_abstract': item.get('is_abstract', False),
                    'is_total': item.get('is_total', False) or 'total' in label.lower(),
                    'original_concept': concept
                }
            
            # Store values for relevant periods
            for period_id in relevant_periods:
                if period_id in self.periods:  # Only include selected periods
                    value = item.get('values', {}).get(period_id)
                    if value is not None:
                        self.data[concept_key][period_id] = {
                            'value': value,
                            'decimals': item.get('decimals', {}).get(period_id, 0)
                        }
    
    def _format_output(self) -> Dict[str, Any]:
        """
        Format the stitched data for rendering.
        
        Returns:
            Stitched statement data in the expected format
        """
        # Create a hierarchical structure preserving ordering and relationships
        ordered_concepts = sorted(
            self.concept_metadata.items(),
            key=lambda x: (x[1]['level'], x[0])
        )
        
        # Build the output structure
        result = {
            'periods': [(pid, self.period_dates.get(pid, pid)) for pid in self.periods],
            'statement_data': []
        }
        
        for concept, metadata in ordered_concepts:
            # Create an item for each concept
            item = {
                'label': concept,
                'level': metadata['level'],
                'is_abstract': metadata['is_abstract'],
                'is_total': metadata['is_total'],
                'concept': metadata['original_concept'],
                'values': {},
                'decimals': {}
            }
            
            # Add values for each period
            for period_id in self.periods:
                if period_id in self.data[concept]:
                    item['values'][period_id] = self.data[concept][period_id]['value']
                    item['decimals'][period_id] = self.data[concept][period_id]['decimals']
            
            # Set has_values flag based on whether there are any values
            item['has_values'] = len(item['values']) > 0
            
            # Only include items with values or abstract items
            if item['has_values'] or item['is_abstract']:
                result['statement_data'].append(item)
        
        return result


def stitch_statements(
    xbrl_list: List[Any], 
    statement_type: str = 'IncomeStatement',
    period_type: Union[StatementStitcher.PeriodType, str] = StatementStitcher.PeriodType.RECENT_PERIODS,
    max_periods: int = 3,
    standard: bool = True
) -> Dict[str, Any]:
    """
    Stitch together statements from multiple XBRL objects.
    
    Args:
        xbrl_list: List of XBRL objects, should be from the same company and ordered by date
        statement_type: Type of statement to stitch ('IncomeStatement', 'BalanceSheet', etc.)
        period_type: Type of period view to generate
        max_periods: Maximum number of periods to include (default: 3)
        standard: Whether to use standardized concept labels (default: True)
        
    Returns:
        Stitched statement data
    """
    # Initialize the stitcher
    stitcher = StatementStitcher()
    
    # Collect statements of the specified type from each XBRL object
    statements = []
    
    for xbrl in xbrl_list:
        # Get statement data for the specified type
        statement = xbrl.get_statement_by_type(statement_type)
        if statement:
            statements.append(statement)
    
    # Stitch the statements
    return stitcher.stitch_statements(statements, period_type, max_periods, standard)


def render_stitched_statement(
    stitched_data: Dict[str, Any],
    statement_title: str,
    statement_type: str,
    entity_info: Dict[str, Any] = None
) -> 'RichTable':
    """
    Render a stitched statement using the same rendering logic as individual statements.
    
    Args:
        stitched_data: Stitched statement data
        statement_title: Title of the statement
        statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
        entity_info: Entity information (optional)
        
    Returns:
        RichTable: A formatted table representation of the stitched statement
    """
    from edgar.xbrl2.rendering import render_statement
    
    # Extract periods and statement data
    periods_to_display = stitched_data['periods']
    statement_data = stitched_data['statement_data']
    
    # Apply special title formatting for stitched statements
    if len(periods_to_display) > 1:
        # For multiple periods, modify the title to indicate the trend view
        period_desc = f" ({len(periods_to_display)}-Period View)"
        statement_title = f"{statement_title}{period_desc}"
    
    # Use the existing rendering function
    return render_statement(
        statement_data=statement_data,
        periods_to_display=periods_to_display,
        statement_title=statement_title,
        statement_type=statement_type,
        entity_info=entity_info
    )


def to_pandas(stitched_data: Dict[str, Any]) -> pd.DataFrame:
    """
    Convert stitched statement data to a pandas DataFrame.
    
    Args:
        stitched_data: Stitched statement data
        
    Returns:
        DataFrame with periods as columns and concepts as index
    """
    # Extract periods and statement data
    periods = [label for _, label in stitched_data['periods']]
    statement_data = stitched_data['statement_data']
    
    # Create a dictionary for the DataFrame
    data = {}
    index = []
    
    for i, item in enumerate(statement_data):
        # Skip abstract items without values
        if item['is_abstract'] and not item['has_values']:
            continue
            
        # Format the label with indentation based on level
        level = item['level']
        indent = "  " * level
        label = f"{indent}{item['label']}"
        index.append(label)
        
        # Add values for each period
        for j, (period_id, period_label) in enumerate(stitched_data['periods']):
            col = period_label
            if col not in data:
                data[col] = [None] * len(statement_data)
            
            # Get value for this period if available
            value = item['values'].get(period_id)
            data[col][i] = value
    
    # Create the DataFrame
    df = pd.DataFrame(data, index=index)
    
    return df