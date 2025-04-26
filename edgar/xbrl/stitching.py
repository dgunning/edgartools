"""
XBRL Statement Stitching Module

This module provides functionality to combine multiple XBRL statements 
across different time periods into a unified view, handling concept 
consistency issues and normalizing data representation.
"""

from collections import defaultdict
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, TYPE_CHECKING

import pandas as pd

from edgar.xbrl.core import format_date, parse_date
from edgar.xbrl.standardization import ConceptMapper, initialize_default_mappings, standardize_statement

if TYPE_CHECKING:
    from edgar.xbrl.xbrl import XBRL
    from edgar.xbrl.statements import StitchedStatements


def determine_optimal_periods(xbrl_list: List['XBRL'], statement_type: str) -> List[Dict[str, Any]]:
    """
    Determine the optimal periods to display for stitched statements from a list of XBRL objects.
    
    This function analyzes entity info and reporting periods across multiple XBRL instances
    to select the most appropriate periods for display, ensuring consistency in period selection
    when creating stitched statements.
    
    Args:
        xbrl_list: List of XBRL objects ordered chronologically
        statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
        
    Returns:
        List of period metadata dictionaries containing information for display
    """
    all_period_metadata = []
    
    # First, extract all relevant reporting periods with their metadata
    for i, xbrl in enumerate(xbrl_list):
        # Skip XBRLs with no reporting periods
        if not xbrl.reporting_periods:
            continue
            
        entity_info = xbrl.entity_info or {}
        doc_period_end_date = None
        
        # Try to parse document_period_end_date from entity_info
        if 'document_period_end_date' in entity_info:
            try:
                doc_period_end_date = entity_info['document_period_end_date']
                if not isinstance(doc_period_end_date, date):
                    doc_period_end_date = parse_date(str(doc_period_end_date))
            except (ValueError, TypeError):
                pass
        
        # Get fiscal information if available
        fiscal_period = entity_info.get('fiscal_period')
        fiscal_year = entity_info.get('fiscal_year')
        
        # Filter appropriate periods based on statement type
        appropriate_periods = []
        if statement_type == 'BalanceSheet':
            # For balance sheets, we want instant periods
            periods = [p for p in xbrl.reporting_periods if p['type'] == 'instant']
            
            # If we have a document_period_end_date, use that to find the most appropriate period
            # The optimal period for BalanceSheet should be exactly the document_period_end_date
            if doc_period_end_date:
                # Find the exact match for document_period_end_date
                exact_period = None
                
                for period in periods:
                    try:
                        period_date = parse_date(period['date'])
                        # Find exact match or period with date within 3 days (accounting for minor differences)
                        days_diff = abs((period_date - doc_period_end_date).days)
                        if days_diff == 0:  # Exact match
                            exact_period = period
                            break
                        elif days_diff <= 3:  # Very close match (within 3 days)
                            exact_period = period
                            break
                    except (ValueError, TypeError):
                        continue
                
                # Use the exact period if found
                if exact_period:
                    appropriate_periods.append(exact_period)
                else:
                    # If no exact match, find the closest period that's still within 14 days
                    # (to accommodate for slight filing date variations)
                    closest_period = None
                    min_days_diff = float('inf')
                    
                    for period in periods:
                        try:
                            period_date = parse_date(period['date'])
                            days_diff = abs((period_date - doc_period_end_date).days)
                            
                            if days_diff < min_days_diff:
                                min_days_diff = days_diff
                                closest_period = period
                        except (ValueError, TypeError):
                            continue
                    
                    # Use the closest period if it's within 14 days
                    if closest_period and min_days_diff <= 14:
                        appropriate_periods.append(closest_period)
            
            # If we couldn't find a period based on document_period_end_date or don't have one,
            # fall back to the most recent period
            if not appropriate_periods and periods:
                # Sort by date (latest first)
                periods.sort(key=lambda x: x['date'], reverse=True)
                appropriate_periods.append(periods[0])
        else:
            # For income and cash flow statements, we want duration periods
            periods = [p for p in xbrl.reporting_periods if p['type'] == 'duration']
            
            # For income statements, different types of durations are appropriate based on fiscal period:
            # - Fiscal year (FY): ~365 day period
            # - Q1: ~90 day period
            # - Q2: ~90 day period (Q2 only) and ~180 day period (YTD)
            # - Q3: ~90 day period (Q3 only) and ~270 day period (YTD)
            # - Q4: ~90 day period (Q4 only) and ~365 day period (full year)
            
            # First, determine if this is an annual or quarterly report
            is_annual = fiscal_period == 'FY'
            
            # Group periods by duration length
            grouped_periods = defaultdict(list)
            for period in periods:
                try:
                    start_date = parse_date(period['start_date'])
                    end_date = parse_date(period['end_date'])
                    duration_days = (end_date - start_date).days
                    period_with_days = period.copy()
                    period_with_days['duration_days'] = duration_days
                    grouped_periods[duration_days].append(period_with_days)
                except (ValueError, TypeError):
                    continue
            
            # We need durations that end exactly on the document_period_end_date (or very close)
            matching_periods = []
            if doc_period_end_date:
                # First, find all periods that end on the document_period_end_date
                for period in periods:
                    try:
                        end_date = parse_date(period['end_date'])
                        days_diff = abs((end_date - doc_period_end_date).days)
                        
                        # Consider periods that end on or very close to document_period_end_date
                        if days_diff <= 3:
                            period_with_days = period.copy()
                            start_date = parse_date(period['start_date'])
                            period_with_days['duration_days'] = (end_date - start_date).days
                            matching_periods.append(period_with_days)
                    except (ValueError, TypeError):
                        continue
            
            # If we found periods that end on the document_period_end_date, filter by appropriate duration
            if matching_periods:
                # For annual reports, we want ~365 day periods
                if is_annual:
                    # Look for periods with annual duration (350-380 days)
                    annual_periods = [p for p in matching_periods if 350 <= p['duration_days'] <= 380]
                    if annual_periods:
                        # If multiple annual periods, take the one with duration closest to 365 days
                        annual_periods.sort(key=lambda x: abs(x['duration_days'] - 365))
                        appropriate_periods.append(annual_periods[0])
                    
                # For quarterly reports, select appropriate periods based on fiscal_period
                else:
                    # First, add the quarterly period if available
                    quarterly_periods = [p for p in matching_periods if 80 <= p['duration_days'] <= 100]
                    if quarterly_periods:
                        # Sort by how close to 90 days (ideal quarter)
                        quarterly_periods.sort(key=lambda x: abs(x['duration_days'] - 90))
                        appropriate_periods.append(quarterly_periods[0])
                    
                    # Then, add YTD period based on fiscal_period if available
                    if fiscal_period == 'Q2':
                        # Look for ~180 day YTD periods
                        ytd_periods = [p for p in matching_periods if 175 <= p['duration_days'] <= 190]
                        if ytd_periods:
                            ytd_periods.sort(key=lambda x: abs(x['duration_days'] - 180))
                            appropriate_periods.append(ytd_periods[0])
                    
                    elif fiscal_period == 'Q3':
                        # Look for ~270 day YTD periods
                        ytd_periods = [p for p in matching_periods if 260 <= p['duration_days'] <= 285]
                        if ytd_periods:
                            ytd_periods.sort(key=lambda x: abs(x['duration_days'] - 270))
                            appropriate_periods.append(ytd_periods[0])
                    
                    elif fiscal_period == 'Q4':
                        # Look for annual period (same as FY)
                        annual_periods = [p for p in matching_periods if 350 <= p['duration_days'] <= 380]
                        if annual_periods:
                            annual_periods.sort(key=lambda x: abs(x['duration_days'] - 365))
                            appropriate_periods.append(annual_periods[0])
            
            # If we didn't find any appropriate periods that end on document_period_end_date,
            # fall back to traditional selection logic
            if not appropriate_periods:
                if is_annual:
                    # For annual reports, prefer periods closest to 365 days
                    annual_periods = []
                    for days in range(350, 380):
                        if days in grouped_periods:
                            annual_periods.extend(grouped_periods[days])
                    
                    if annual_periods and doc_period_end_date:
                        # Find the annual period that best matches document_period_end_date
                        closest_period = None
                        min_days_diff = float('inf')
                        
                        for period in annual_periods:
                            try:
                                end_date = parse_date(period['end_date'])
                                days_diff = abs((end_date - doc_period_end_date).days)
                                
                                # Prioritize very close dates
                                if days_diff <= 3:
                                    closest_period = period
                                    break
                                
                                # Otherwise track the closest one
                                if days_diff < min_days_diff:
                                    min_days_diff = days_diff
                                    closest_period = period
                            except (ValueError, TypeError):
                                continue
                        
                        # Use the closest period if found and within reasonable range
                        if closest_period and min_days_diff <= 14:
                            appropriate_periods.append(closest_period)
                        else:
                            # Fall back to latest if no good match
                            annual_periods.sort(key=lambda x: x['end_date'], reverse=True)
                            appropriate_periods.append(annual_periods[0])
                    elif annual_periods:
                        # If no document_period_end_date, use the latest
                        annual_periods.sort(key=lambda x: x['end_date'], reverse=True)
                        appropriate_periods.append(annual_periods[0])
                else:
                    # For quarterly reports, prefer:
                    # 1. The quarter duration (~90 days)
                    # 2. The YTD (year-to-date) duration if available
                    
                    # Look for quarterly duration
                    quarterly_periods = []
                    for days in range(85, 100):
                        if days in grouped_periods:
                            quarterly_periods.extend(grouped_periods[days])
                    
                    if quarterly_periods and doc_period_end_date:
                        # Find the quarterly period that best matches document_period_end_date
                        closest_period = None
                        min_days_diff = float('inf')
                        
                        for period in quarterly_periods:
                            try:
                                end_date = parse_date(period['end_date'])
                                days_diff = abs((end_date - doc_period_end_date).days)
                                
                                # Prioritize very close dates
                                if days_diff <= 3:
                                    closest_period = period
                                    break
                                
                                # Otherwise track the closest one
                                if days_diff < min_days_diff:
                                    min_days_diff = days_diff
                                    closest_period = period
                            except (ValueError, TypeError):
                                continue
                        
                        # Use the closest period if found and within reasonable range
                        if closest_period and min_days_diff <= 14:
                            appropriate_periods.append(closest_period)
                        else:
                            # Fall back to latest if no good match
                            quarterly_periods.sort(key=lambda x: x['end_date'], reverse=True)
                            appropriate_periods.append(quarterly_periods[0])
                    elif quarterly_periods:
                        # If no document_period_end_date, use the latest
                        quarterly_periods.sort(key=lambda x: x['end_date'], reverse=True)
                        appropriate_periods.append(quarterly_periods[0])
                        
                    # Look for YTD duration if this is not Q1
                    if fiscal_period in ['Q2', 'Q3', 'Q4']:
                        # Define YTD day ranges based on fiscal period
                        ytd_days_range = {
                            'Q2': range(175, 190),
                            'Q3': range(260, 285),
                            'Q4': range(350, 380)
                        }.get(fiscal_period, range(0, 0))
                        
                        ytd_periods = []
                        for days in ytd_days_range:
                            if days in grouped_periods:
                                ytd_periods.extend(grouped_periods[days])
                        
                        if ytd_periods and doc_period_end_date:
                            # Find the YTD period that best matches document_period_end_date
                            closest_period = None
                            min_days_diff = float('inf')
                            
                            for period in ytd_periods:
                                try:
                                    end_date = parse_date(period['end_date'])
                                    days_diff = abs((end_date - doc_period_end_date).days)
                                    
                                    # Prioritize very close dates
                                    if days_diff <= 3:
                                        closest_period = period
                                        break
                                    
                                    # Otherwise track the closest one
                                    if days_diff < min_days_diff:
                                        min_days_diff = days_diff
                                        closest_period = period
                                except (ValueError, TypeError):
                                    continue
                            
                            # Use the closest period if found and within reasonable range
                            if closest_period and min_days_diff <= 14:
                                appropriate_periods.append(closest_period)
                            else:
                                # Fall back to latest if no good match
                                ytd_periods.sort(key=lambda x: x['end_date'], reverse=True)
                                appropriate_periods.append(ytd_periods[0])
                        elif ytd_periods:
                            # If no document_period_end_date, use the latest
                            ytd_periods.sort(key=lambda x: x['end_date'], reverse=True)
                            appropriate_periods.append(ytd_periods[0])
        
        # Add metadata and source XBRL index to each selected period
        for period in appropriate_periods:
            # Add useful metadata
            period_metadata = {
                'xbrl_index': i,
                'period_key': period['key'],
                'period_label': period['label'],
                'period_type': period['type'],
                'entity_info': entity_info,
                'doc_period_end_date': doc_period_end_date,
                'fiscal_period': fiscal_period,
                'fiscal_year': fiscal_year
            }
            
            # Add date information
            if period['type'] == 'instant':
                period_metadata['date'] = parse_date(period['date'])
                period_metadata['display_date'] = format_date(period_metadata['date'])
            else:  # duration
                period_metadata['start_date'] = parse_date(period['start_date'])
                period_metadata['end_date'] = parse_date(period['end_date']) 
                period_metadata['duration_days'] = period.get('duration_days', 
                    (period_metadata['end_date'] - period_metadata['start_date']).days)
                period_metadata['display_date'] = format_date(period_metadata['end_date'])
            
            all_period_metadata.append(period_metadata)
    
    # Now, select the optimal set of periods to display
    # 1. Remove duplicates (same end date or very close)
    # 2. Ensure proper chronological ordering
    # 3. Limit to a reasonable number of periods
    
    # First, sort all periods by date (most recent first)
    if statement_type == 'BalanceSheet':
        all_period_metadata.sort(key=lambda x: x['date'], reverse=True)
    else:
        all_period_metadata.sort(key=lambda x: x['end_date'], reverse=True)
    
    # Filter out periods that are too close to each other
    filtered_periods = []
    for period in all_period_metadata:
        too_close = False
        for included_period in filtered_periods:
            # Skip if period types don't match
            if period['period_type'] != included_period['period_type']:
                continue
            
            # Calculate date difference
            if period['period_type'] == 'instant':
                date1 = period['date']
                date2 = included_period['date']
            else:  # duration
                date1 = period['end_date']
                date2 = included_period['end_date']
            
            days_diff = abs((date1 - date2).days)
            
            # Periods are too close if they are within 14 days
            if days_diff <= 14:
                too_close = True
                break
        
        if not too_close:
            filtered_periods.append(period)
    
    # Limit to a reasonable number of periods (8 is usually sufficient)
    MAX_PERIODS = 8
    if len(filtered_periods) > MAX_PERIODS:
        filtered_periods = filtered_periods[:MAX_PERIODS]
    
    return filtered_periods


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
        max_periods: int = None,
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

        # Set max_periods if not provided
        max_periods = max_periods or len(statements) + 2 # Allow for the last statement to have 3 periods
        
        # Select appropriate periods based on period_type
        selected_periods = self._select_periods(all_periods, period_type, max_periods)
        self.periods = selected_periods
        
        # Process each statement
        for i, statement in enumerate(statements):
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
        Extract and sort all periods from the statements, de-duplicating periods with the same date.
        
        Args:
            statements: List of statement data
            
        Returns:
            List of (period_id, end_date) tuples, sorted by date (newest first)
        """
        # Use a dictionary to track unique periods by their end date
        # This will handle cases where different period_ids reference the same date
        unique_periods = {}  # key: date string, value: (period_id, datetime, statement_index)
        
        for i, statement in enumerate(statements):
            # Use statement index (i) to prioritize more recent filings
            # Lower index = more recent filing
            for period_id, period_info in statement['periods'].items():
                # Extract end date for sorting
                try:
                    # Initialize normalized_key to silence the type checker
                    normalized_key = ""
                    
                    if period_id.startswith('instant_'):
                        date_str = period_id.split('_')[1]
                        # Format the date consistently with single statements
                        try:
                            date_obj = parse_date(date_str)
                            display_date = format_date(date_obj)
                        except ValueError:
                            # Fall back to original label if parsing fails
                            display_date = period_info['label']
                        period_type = 'instant'
                        # For instant periods, create a normalized key with just the date
                        normalized_key = f"{period_type}_{date_str}"
                    else:  # duration
                        # For durations, extract both start and end dates
                        parts = period_id.split('_')
                        if len(parts) >= 3:
                            start_date_str = parts[1]
                            end_date_str = parts[2]
                            start_date = parse_date(start_date_str)
                            end_date = parse_date(end_date_str)
                            date_str = end_date_str  # Use end date for sorting
                            
                            # Format end date consistently - for stitched statements,
                            # we only need the end date for duration periods as that's what users compare
                            display_date = format_date(end_date)
                            period_type = 'duration'
                            # Create a normalized key that combines period type, start date, and end date
                            normalized_key = f"{period_type}_{format_date(start_date)}_{format_date(end_date)}"
                        else:
                            # Skip malformed period IDs
                            continue
                    
                    # Parse the end date for sorting
                    end_date = parse_date(date_str)
                    
                    # Check if we already have this period (by normalized key)
                    if normalized_key in unique_periods:
                        existing_idx = unique_periods[normalized_key][2]
                        # Only replace if this statement is from a more recent filing
                        if i < existing_idx:
                            unique_periods[normalized_key] = (period_id, end_date, i)
                            self.period_dates[period_id] = display_date
                    else:
                        # Add new period
                        unique_periods[normalized_key] = (period_id, end_date, i)
                        self.period_dates[period_id] = display_date
                
                except (ValueError, TypeError, IndexError):
                    # Skip periods with invalid dates
                    continue
        
        # Extract and sort the unique periods
        all_periods = [(period_id, end_date) for period_id, end_date, _ in unique_periods.values()]
        
        # Sort by date, newest first
        return sorted(all_periods, key=lambda x: x[1], reverse=True)
    
    def _select_periods(
        self, 
        all_periods: List[Tuple[str, Union[str,datetime]]],
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
        # Map to track concepts by their underlying concept ID, not just label
        # This helps merge rows that represent the same concept but have different labels
        concept_to_label_map = {}
        
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
            
            # Use concept as the primary key for identifying the same financial line item
            # This is more reliable than labels which may vary across filings
            
            # If we've already seen this concept, use the existing label as the key
            # This ensures we merge rows that represent the same concept
            if concept in concept_to_label_map:
                concept_key = concept_to_label_map[concept]
            else:
                # For a new concept, use the current label as the key
                concept_key = label
                # Remember this mapping for future occurrences
                concept_to_label_map[concept] = concept_key
            
            # Store metadata about the concept (level, abstract status, etc.)
            # If we've already seen this concept, only update metadata if it's from a more recent period
            # This ensures we use labels from the most recent filing when merging rows
            if concept_key not in self.concept_metadata:
                self.concept_metadata[concept_key] = {
                    'level': item.get('level', 0),
                    'is_abstract': item.get('is_abstract', False),
                    'is_total': item.get('is_total', False) or 'total' in label.lower(),
                    'original_concept': concept,
                    'latest_label': label  # Store the original label too
                }
            else:
                # For existing concepts, update the label to use the most recent one
                # We determine which periods are most recent based on position in self.periods
                # (earlier indices are more recent periods)
                
                # Find the periods in this statement
                statement_periods = [p for p in relevant_periods if p in self.periods]
                if statement_periods:
                    # Get the most recent period in this statement
                    most_recent_period = min(statement_periods, key=lambda p: self.periods.index(p))
                    most_recent_idx = self.periods.index(most_recent_period)
                    
                    # Find the earliest period where we have data for this concept
                    existing_periods = [p for p in self.data[concept_key].keys() if p in self.periods]
                    if existing_periods:
                        earliest_existing_idx = min(self.periods.index(p) for p in existing_periods)
                        
                        # If this statement has more recent data, update the label
                        if most_recent_idx < earliest_existing_idx:
                            # Update the concept key label for display
                            new_concept_key = label
                            
                            # If we're changing the label, we need to migrate existing data
                            if new_concept_key != concept_key:
                                # Copy existing data to the new key
                                if new_concept_key not in self.data:
                                    self.data[new_concept_key] = self.data[concept_key].copy()
                                    
                                # Update metadata
                                self.concept_metadata[new_concept_key] = self.concept_metadata[concept_key].copy()
                                self.concept_metadata[new_concept_key]['latest_label'] = label
                                
                                # Update the concept mapping
                                concept_to_label_map[concept] = new_concept_key
                                concept_key = new_concept_key
                            else:
                                # Just update the latest label
                                self.concept_metadata[concept_key]['latest_label'] = label
            
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
                # Use the latest label if available, otherwise fall back to the concept key
                'label': metadata.get('latest_label', concept),
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
    standard: bool = True,
    use_optimal_periods: bool = True
) -> Dict[str, Any]:
    """
    Stitch together statements from multiple XBRL objects.
    
    Args:
        xbrl_list: List of XBRL objects, should be from the same company and ordered by date
        statement_type: Type of statement to stitch ('IncomeStatement', 'BalanceSheet', etc.)
        period_type: Type of period view to generate
        max_periods: Maximum number of periods to include (default: 3)
        standard: Whether to use standardized concept labels (default: True)
        use_optimal_periods: Whether to use the entity info to determine optimal periods (default: True)
        
    Returns:
        Stitched statement data
    """
    # Initialize the stitcher
    stitcher = StatementStitcher()
    
    # Collect statements of the specified type from each XBRL object
    statements = []
    
    # If using optimal periods based on entity info
    if use_optimal_periods:
        # Use our utility function to determine the best periods
        optimal_periods = determine_optimal_periods(xbrl_list, statement_type)
        
        # Limit to max_periods if needed
        if len(optimal_periods) > max_periods:
            optimal_periods = optimal_periods[:max_periods]
            
        # Extract the XBRL objects that contain our optimal periods
        for period_metadata in optimal_periods:
            xbrl_index = period_metadata['xbrl_index']
            xbrl = xbrl_list[xbrl_index]
            
            # Get the statement and period info
            statement = xbrl.get_statement_by_type(statement_type)
            if statement:
                # Only include the specific period from this statement
                period_key = period_metadata['period_key']
                
                # Check if this period exists in the statement
                if period_key in statement['periods']:
                    # Create a filtered version of the statement with just this period
                    filtered_statement = {
                        'role': statement['role'],
                        'definition': statement['definition'],
                        'statement_type': statement['statement_type'],
                        'periods': {period_key: statement['periods'][period_key]},
                        'data': statement['data']
                    }
                    
                    # Update the period label to include information from entity_info
                    display_date = period_metadata['display_date']
                    period_type = period_metadata['period_type']
                    fiscal_period = period_metadata.get('fiscal_period')
                    
                    # Create a more informative label
                    if period_type == 'instant':
                        if fiscal_period == 'FY':
                            period_label = f"FY {display_date}"
                        else:
                            period_label = display_date
                    else:  # duration
                        # For duration periods, add fiscal quarter/year info if available
                        if fiscal_period == 'FY':
                            period_label = f"FY {display_date}"
                        elif fiscal_period in ['Q1', 'Q2', 'Q3', 'Q4']:
                            period_label = f"{fiscal_period} {display_date}"
                        else:
                            period_label = display_date
                            
                    # Update the period label
                    filtered_statement['periods'][period_key] = {
                        'label': period_label,
                        'original_label': statement['periods'][period_key]['label']
                    }
                    
                    statements.append(filtered_statement)
    # Traditional approach without using entity info
    else:
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
    entity_info: Dict[str, Any] = None,
    show_date_range: bool = False
):
    """
    Render a stitched statement using the same rendering logic as individual statements.
    
    Args:
        stitched_data: Stitched statement data
        statement_title: Title of the statement
        statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
        entity_info: Entity information (optional)
        show_date_range: Whether to show full date ranges for duration periods
        
    Returns:
        RichTable: A formatted table representation of the stitched statement
    """
    from edgar.xbrl.rendering import render_statement
    
    # Extract periods and statement data
    periods_to_display = stitched_data['periods']
    statement_data = stitched_data['statement_data']
    
    # Apply special title formatting for stitched statements
    if len(periods_to_display) > 1:
        # For multiple periods, modify the title to indicate the trend view
        period_desc = f" ({len(periods_to_display)}-Period View)"
        statement_title = f"{statement_title}{period_desc}"
    
    # Use the existing rendering function with the new show_date_range parameter
    return render_statement(
        statement_data=statement_data,
        periods_to_display=periods_to_display,
        statement_title=statement_title,
        statement_type=statement_type,
        entity_info=entity_info,
        show_date_range=show_date_range
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
    statement_data = stitched_data['statement_data']
    
    # Create a dictionary for the DataFrame
    data = {}

    # Initialize columns
    data['label'] = [None] * len(statement_data)
    data['concept'] = [None] * len(statement_data)
    
    for i, item in enumerate(statement_data):
        # Skip abstract items without values
        if item['is_abstract'] and not item['has_values']:
            continue

        data['label'][i] = item['label']
        data['concept'][i] = item['concept']
        
        # Add values for each period
        for j, (period_id, period_label) in enumerate(stitched_data['periods']):
            # Use the end_date in YYYY-MM-DD format as the column name
            col = period_id[-10:]
            if col not in data:
                data[col] = [None] * len(statement_data)
            
            # Get value for this period if available
            value = item['values'].get(period_id)
            data[col][i] = value
    
    # Create the DataFrame
    df = pd.DataFrame(data)
    
    return df


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
    
    @classmethod
    def from_filings(cls, filings: List[Any]) -> 'XBRLS':
        """
        Create an XBRLS object from a list of Filing objects.
        
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
    
    def __rich__(self) -> str:
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