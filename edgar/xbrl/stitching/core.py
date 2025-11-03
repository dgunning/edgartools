"""
XBRL Statement Stitching - Core Functionality

This module contains the core StatementStitcher class and related functionality
for combining multiple XBRL statements across different time periods.
"""

from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from edgar.xbrl.core import format_date, parse_date
from edgar.xbrl.standardization import ConceptMapper, initialize_default_mappings, standardize_statement
from edgar.xbrl.stitching.ordering import StatementOrderingManager
from edgar.xbrl.stitching.periods import determine_optimal_periods
from edgar.xbrl.stitching.presentation import VirtualPresentationTree


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
        self.ordering_manager = None  # Will be initialized during stitching
        self.original_statement_order = []  # Track original order for hierarchy context

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
        self.original_statement_order = []

        # Initialize ordering manager for this statement type
        statement_type = statements[0].get('statement_type', 'IncomeStatement') if statements else 'IncomeStatement'
        self.ordering_manager = StatementOrderingManager(statement_type)

        # Capture original statement order from the most recent (first) statement for hierarchy context
        if statements:
            reference_statement = statements[0]
            self.original_statement_order = []
            for item in reference_statement.get('data', []):
                concept = item.get('concept')
                label = item.get('label')
                if concept:
                    self.original_statement_order.append(concept)
                if label and label not in self.original_statement_order:
                    self.original_statement_order.append(label)

        # Extract and sort all periods
        all_periods = self._extract_periods(statements)

        # Set max_periods if not provided
        max_periods = max_periods or len(statements) + 2 # Allow for the last statement to have 3 periods

        # Select appropriate periods based on period_type
        selected_periods = self._select_periods(all_periods, period_type, max_periods)
        self.periods = selected_periods

        # Process each statement
        for _i, statement in enumerate(statements):
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
        return self._format_output_with_ordering(statements)

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
                            # Use the enhanced label from period_info if available, otherwise fall back to display_date
                            self.period_dates[period_id] = period_info.get('label', display_date)
                    else:
                        # Add new period
                        unique_periods[normalized_key] = (period_id, end_date, i)
                        # Use the enhanced label from period_info if available, otherwise fall back to display_date
                        self.period_dates[period_id] = period_info.get('label', display_date)

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

            for pid, _date in durations:
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

            for pid, _date in durations:
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

    def _format_output_with_ordering(self, statements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Format the stitched data for rendering with intelligent ordering using virtual presentation tree.

        Args:
            statements: Original statements for ordering reference

        Returns:
            Stitched statement data in the expected format
        """
        # Get unified ordering for all concepts using the ordering manager
        concept_ordering = {}
        if self.ordering_manager:
            concept_ordering = self.ordering_manager.determine_ordering(statements)

        # Build virtual presentation tree to preserve hierarchy while applying semantic ordering
        presentation_tree = VirtualPresentationTree(self.ordering_manager)
        ordered_nodes = presentation_tree.build_tree(
            concept_metadata=self.concept_metadata,
            concept_ordering=concept_ordering,
            original_statement_order=self.original_statement_order
        )

        # Convert nodes back to the expected format
        ordered_concepts = [(node.concept, node.metadata) for node in ordered_nodes]

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

    def _format_output(self) -> Dict[str, Any]:
        """
        Backward compatibility method - calls the new ordering-aware method.

        Returns:
            Stitched statement data in the expected format
        """
        # For backward compatibility, call the new method with empty statements
        # This will use alphabetical ordering as before
        return self._format_output_with_ordering([])


def stitch_statements(
    xbrl_list: List[Any], 
    statement_type: str = 'IncomeStatement',
    period_type: Union[StatementStitcher.PeriodType, str] = StatementStitcher.PeriodType.RECENT_PERIODS,
    max_periods: int = 3,
    standard: bool = True,
    use_optimal_periods: bool = True,
    include_dimensions: bool = False
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
        include_dimensions: Whether to include dimensional segment data (default: False for stitching)

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
        optimal_periods = determine_optimal_periods(xbrl_list, statement_type, max_periods=max_periods)

        # Limit to max_periods if needed
        if len(optimal_periods) > max_periods:
            optimal_periods = optimal_periods[:max_periods]

        # Extract the XBRL objects that contain our optimal periods
        for period_metadata in optimal_periods:
            xbrl_index = period_metadata['xbrl_index']
            xbrl = xbrl_list[xbrl_index]

            # Get the statement and period info
            statement = xbrl.get_statement_by_type(statement_type, include_dimensions=include_dimensions)
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
                        # Also indicate if it's YTD (cumulative) vs quarterly (Issue #475)
                        if fiscal_period == 'FY':
                            period_label = f"FY {display_date}"
                        elif fiscal_period in ['Q1', 'Q2', 'Q3', 'Q4']:
                            # Check if this is a YTD period (longer duration) vs quarterly
                            # Threshold: 100 days (Q1≈90d, Q2 YTD≈180d, Q3 YTD≈270d)
                            duration_days = period_metadata.get('duration_days')
                            if duration_days and duration_days > 100:
                                # YTD period (cumulative from fiscal year start)
                                period_label = f"{fiscal_period} YTD {display_date}"
                            else:
                                # Regular quarterly period
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
            statement = xbrl.find_statement(statement_type)
            if statement:
                statements.append(statement)

    # Stitch the statements
    return stitcher.stitch_statements(statements, period_type, max_periods, standard)
