"""
Period handling functionality for XBRL statements.

This module provides functions for handling periods in XBRL statements, including:
- Determining available period views for different statement types
- Selecting appropriate periods for display
- Handling fiscal year and quarter information
"""

from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

# Configuration for different statement types
STATEMENT_TYPE_CONFIG = {
    'BalanceSheet': {
        'period_type': 'instant',
        'max_periods': 3,
        'allow_annual_comparison': True,
        'views': [
            {
                'name': 'Three Recent Periods',
                'description': 'Shows three most recent reporting periods',
                'max_periods': 3,
                'requires_min_periods': 3
            },
            {
                'name': 'Current vs. Previous Period',
                'description': 'Shows the current period and the previous period',
                'max_periods': 2,
                'requires_min_periods': 1
            },
            {
                'name': 'Three-Year Annual Comparison',
                'description': 'Shows three fiscal years for comparison',
                'max_periods': 3,
                'requires_min_periods': 3,
                'annual_only': True
            }
        ]
    },
    'IncomeStatement': {
        'period_type': 'duration',
        'max_periods': 3,
        'allow_annual_comparison': True,
        'views': [
            {
                'name': 'Three Recent Periods',
                'description': 'Shows three most recent reporting periods',
                'max_periods': 3,
                'requires_min_periods': 3
            },
            {
                'name': 'YTD and Quarterly Breakdown',
                'description': 'Shows YTD figures and quarterly breakdown',
                'max_periods': 5,
                'requires_min_periods': 2,
                'mixed_view': True
            }
        ]
    },
    'StatementOfEquity': {
        'period_type': 'duration',
        'max_periods': 3,
        'views': [
            {
                'name': 'Three Recent Periods',
                'description': 'Shows three most recent reporting periods',
                'max_periods': 3,
                'requires_min_periods': 1
            }
        ]
    },
    'ComprehensiveIncome': {
        'period_type': 'duration',
        'max_periods': 3,
        'views': [
            {
                'name': 'Three Recent Periods',
                'description': 'Shows three most recent reporting periods',
                'max_periods': 3,
                'requires_min_periods': 1
            }
        ]
    },
    'CoverPage': {
        'period_type': 'instant',
        'max_periods': 1,
        'views': [
            {
                'name': 'Current Period',
                'description': 'Shows the current reporting period',
                'max_periods': 1,
                'requires_min_periods': 1
            }
        ]
    },
    'Notes': {
        'period_type': 'instant',
        'max_periods': 1,
        'views': [
            {
                'name': 'Current Period',
                'description': 'Shows the current reporting period',
                'max_periods': 1,
                'requires_min_periods': 1
            }
        ]
    }
}

def sort_periods(periods: List[Dict], period_type: str) -> List[Dict]:
    """Sort periods by date, with most recent first."""
    if period_type == 'instant':
        return sorted(periods, key=lambda x: x['date'], reverse=True)
    return sorted(periods, key=lambda x: (x['end_date'], x['start_date']), reverse=True)

def filter_periods_by_document_end_date(periods: List[Dict], document_period_end_date: str, period_type: str) -> List[Dict]:
    """Filter periods to only include those that end on or before the document period end date."""
    if not document_period_end_date:
        return periods
        
    try:
        doc_end_date = datetime.strptime(document_period_end_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        # If we can't parse the document end date, return all periods
        return periods
    
    filtered_periods = []
    for period in periods:
        try:
            if period_type == 'instant':
                period_date = datetime.strptime(period['date'], '%Y-%m-%d').date()
                if period_date <= doc_end_date:
                    filtered_periods.append(period)
            else:  # duration
                period_end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                if period_end_date <= doc_end_date:
                    filtered_periods.append(period)
        except (ValueError, TypeError):
            # If we can't parse the period date, include it to be safe
            filtered_periods.append(period)
    
    return filtered_periods

def filter_periods_by_type(periods: List[Dict], period_type: str) -> List[Dict]:
    """Filter periods by their type (instant or duration)."""
    return [p for p in periods if p['type'] == period_type]

def calculate_fiscal_alignment_score(end_date: datetime.date, fiscal_month: int, fiscal_day: int) -> int:
    """Calculate how well a date aligns with fiscal year end."""
    if end_date.month == fiscal_month and end_date.day == fiscal_day:
        return 100
    if end_date.month == fiscal_month and abs(end_date.day - fiscal_day) <= 15:
        return 75
    if abs(end_date.month - fiscal_month) <= 1 and abs(end_date.day - fiscal_day) <= 15:
        return 50
    return 0


def generate_period_view(view_config: Dict[str, Any], periods: List[Dict], is_annual: bool = False) -> Optional[Dict[str, Any]]:
    """Generate a period view based on configuration and available periods.
    
    Args:
        view_config: Configuration for the view (from STATEMENT_TYPE_CONFIG)
        periods: List of periods to choose from
        is_annual: Whether this is an annual report
        
    Returns:
        Dictionary with view name, description, and period keys if view is valid,
        None if view cannot be generated with available periods
    """
    if len(periods) < view_config['requires_min_periods']:
        return None
        
    if view_config.get('annual_only', False) and not is_annual:
        return None
        
    max_periods = min(view_config['max_periods'], len(periods))
    return {
        'name': view_config['name'],
        'description': view_config['description'],
        'period_keys': [p['key'] for p in periods[:max_periods]]
    }


def generate_mixed_view(view_config: Dict[str, Any], ytd_periods: List[Dict], 
                       quarterly_periods: List[Dict]) -> Optional[Dict[str, Any]]:
    """Generate a mixed view combining YTD and quarterly periods.
    
    Args:
        view_config: Configuration for the view
        ytd_periods: List of year-to-date periods
        quarterly_periods: List of quarterly periods
        
    Returns:
        Dictionary with view configuration if valid, None otherwise
    """
    if not ytd_periods or not quarterly_periods:
        return None
        
    mixed_keys = []
    
    # Add current YTD
    mixed_keys.append(ytd_periods[0]['key'])
    
    # Add recent quarters
    for q in quarterly_periods[:min(4, len(quarterly_periods))]:
        if q['key'] not in mixed_keys:
            mixed_keys.append(q['key'])
    
    if len(mixed_keys) >= view_config['requires_min_periods']:
        return {
            'name': view_config['name'],
            'description': view_config['description'],
            'period_keys': mixed_keys[:view_config['max_periods']]
        }
    
    return None


def get_period_views(xbrl_instance, statement_type: str) -> List[Dict[str, Any]]:
    """
    Get available period views for a statement type.
    
    Args:
        xbrl_instance: XBRL instance with context and entity information
        statement_type: Type of statement to get period views for
        
    Returns:
        List of period view options with name, description, and period keys
    """
    period_views = []
    
    # Get statement configuration
    config = STATEMENT_TYPE_CONFIG.get(statement_type)
    if not config:
        return period_views
        
    # Get useful entity info for period selection
    entity_info = xbrl_instance.entity_info
    fiscal_period_focus = entity_info.get('fiscal_period')
    annual_report = fiscal_period_focus == 'FY'
    
    # Get all periods
    all_periods = xbrl_instance.reporting_periods
    document_period_end_date = xbrl_instance.period_of_report
    
    # Filter and sort periods by type
    period_type = config['period_type']
    periods = filter_periods_by_type(all_periods, period_type)
    # Filter by document period end date to exclude periods after the reporting period
    periods = filter_periods_by_document_end_date(periods, document_period_end_date, period_type)
    periods = sort_periods(periods, period_type)
    
    # If this statement type allows annual comparison and this is an annual report,
    # filter for annual periods
    annual_periods = []
    if config.get('allow_annual_comparison') and annual_report:
        fiscal_month = entity_info.get('fiscal_year_end_month')
        fiscal_day = entity_info.get('fiscal_year_end_day')
        
        if fiscal_month is not None and fiscal_day is not None:
            for period in periods:
                try:
                    date_field = 'date' if period_type == 'instant' else 'end_date'
                    end_date = datetime.strptime(period[date_field], '%Y-%m-%d').date()
                    score = calculate_fiscal_alignment_score(end_date, fiscal_month, fiscal_day)
                    if score > 0:  # Any alignment is good enough for a view
                        annual_periods.append(period)
                except (ValueError, TypeError):
                    continue
    
    # Generate views based on configuration
    for view_config in config.get('views', []):
        if view_config.get('mixed_view'):
            # Special handling for mixed YTD/quarterly views
            ytd_periods = [p for p in periods if p.get('ytd')]
            quarterly_periods = [p for p in periods if p.get('quarterly')]
            view = generate_mixed_view(view_config, ytd_periods, quarterly_periods)
        elif view_config.get('annual_only'):
            # Views that should only show annual periods
            view = generate_period_view(view_config, annual_periods, annual_report)
        else:
            # Standard views using all periods
            view = generate_period_view(view_config, periods, annual_report)
            
        if view:
            period_views.append(view)
    
    return period_views
                
def determine_periods_to_display(
    xbrl_instance,
    statement_type: str,
    period_filter: Optional[str] = None,
    period_view: Optional[str] = None
) -> List[Tuple[str, str]]:
    """
    Determine which periods should be displayed for a statement.
    
    Args:
        xbrl_instance: XBRL instance with context and entity information
        statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
        period_filter: Optional period key to filter by specific reporting period
        period_view: Optional name of a predefined period view
        
    Returns:
        List of tuples with period keys and labels to display
    """
    periods_to_display = []
    
    # If a specific period is requested, use only that
    if period_filter:
        for period in xbrl_instance.reporting_periods:
            if period['key'] == period_filter:
                periods_to_display.append((period_filter, period['label']))
                break
        return periods_to_display
    
    # If a period view is specified, use that
    if period_view:
        available_views = get_period_views(xbrl_instance, statement_type)
        matching_view = next((view for view in available_views if view['name'] == period_view), None)
        
        if matching_view:
            for period_key in matching_view['period_keys']:
                for period in xbrl_instance.reporting_periods:
                    if period['key'] == period_key:
                        periods_to_display.append((period_key, period['label']))
                        break
            return periods_to_display
    
    # If no specific periods requested, use default logic based on statement type
    all_periods = xbrl_instance.reporting_periods
    entity_info = xbrl_instance.entity_info
    fiscal_period_focus = entity_info.get('fiscal_period')
    document_period_end_date = xbrl_instance.period_of_report
    
    # Filter periods by statement type
    if statement_type == 'BalanceSheet':
        instant_periods = filter_periods_by_type(all_periods, 'instant')
        # Filter by document period end date to exclude periods after the reporting period
        instant_periods = filter_periods_by_document_end_date(instant_periods, document_period_end_date, 'instant')
        instant_periods = sort_periods(instant_periods, 'instant')
        
        # Get fiscal information for better period matching
        fiscal_period_focus = entity_info.get('fiscal_period')
        fiscal_year_focus = entity_info.get('fiscal_year')
        fiscal_year_end_month = entity_info.get('fiscal_year_end_month')
        fiscal_year_end_day = entity_info.get('fiscal_year_end_day')
        
        if instant_periods:
            # Take latest instant period that is not later than document_period_end_date
            current_period = instant_periods[0]  # Most recent
            period_key = current_period['key']
            periods_to_display.append((period_key, current_period['label']))
            
            # Try to find appropriate comparison period
            try:
                current_date = datetime.strptime(current_period['date'], '%Y-%m-%d').date()
                
                # Use fiscal information if available for better matching
                if fiscal_year_end_month is not None and fiscal_year_end_day is not None:
                    # Check if this is a fiscal year end report
                    is_fiscal_year_end = False
                    if fiscal_period_focus == 'FY' or (
                            current_date.month == fiscal_year_end_month and
                            abs(current_date.day - fiscal_year_end_day) <= 7):
                        is_fiscal_year_end = True
                    
                    if is_fiscal_year_end and fiscal_year_focus:
                        # For fiscal year end, find the previous fiscal year end period
                        prev_fiscal_year = int(fiscal_year_focus) - 1 if isinstance(fiscal_year_focus, 
                                                                               (int, str)) and str(
                            fiscal_year_focus).isdigit() else current_date.year - 1
                        
                        # Look for a comparable period from previous fiscal year
                        for period in instant_periods[1:]:  # Skip the current one
                            try:
                                period_date = datetime.strptime(period['date'], '%Y-%m-%d').date()
                                # Check if this period is from the previous fiscal year and around fiscal year end
                                if (period_date.year == prev_fiscal_year and
                                        period_date.month == fiscal_year_end_month and
                                        abs(period_date.day - fiscal_year_end_day) <= 15):
                                    periods_to_display.append((period['key'], period['label']))
                                    break
                            except (ValueError, TypeError):
                                continue
                
                # If no appropriate period found yet, try generic date-based comparison
                if len(periods_to_display) == 1:
                    # Look for a period from previous year with similar date pattern
                    prev_year = current_date.year - 1
                    
                    for period in instant_periods[1:]:  # Skip the current one
                        try:
                            period_date = datetime.strptime(period['date'], '%Y-%m-%d').date()
                            # If from previous year with similar month/day
                            if period_date.year == prev_year:
                                periods_to_display.append((period['key'], period['label']))
                                break
                        except (ValueError, TypeError):
                            continue
                
                # Only add additional comparable periods (up to a total of 3)
                # For annual reports, only add periods that are also fiscal year ends
                is_annual_report = (fiscal_period_focus == 'FY')
                added_period_keys = [key for key, _ in periods_to_display]
                
                for period in instant_periods[1:]:  # Skip current period
                    if len(periods_to_display) >= 3:
                        break  # Stop when we have 3 periods
                    
                    # For annual reports, only add periods that are fiscal year ends
                    if is_annual_report and fiscal_year_end_month is not None and fiscal_year_end_day is not None:
                        try:
                            # Check if this period is close to the fiscal year end
                            period_date = datetime.strptime(period['date'], '%Y-%m-%d').date()
                            is_fiscal_year_end = (
                                    period_date.month == fiscal_year_end_month and
                                    abs(period_date.day - fiscal_year_end_day) <= 15  # Allow some flexibility
                            )
                            
                            # Only include this period if it's a fiscal year end
                            if not is_fiscal_year_end:
                                continue  # Skip non-fiscal-year-end periods
                        except (ValueError, TypeError):
                            continue  # Skip periods with invalid dates
                    
                    # Don't add periods we've already added
                    period_key = period['key']
                    if period_key not in added_period_keys:
                        periods_to_display.append((period_key, period['label']))
                        
            except (ValueError, TypeError):
                # If date parsing failed, still try to select appropriate periods
                # For annual reports, we should only show fiscal year end periods
                is_annual_report = (fiscal_period_focus == 'FY')
                
                added_count = 0
                for i, period in enumerate(instant_periods):
                    if i == 0:
                        continue  # Skip first period which should already be added
                    
                    if added_count >= 2:  # Already added 2 more (for a total of 3)
                        break
                    
                    # For annual reports, only add periods that are close to fiscal year end
                    if (is_annual_report and fiscal_year_end_month is not None and 
                            fiscal_year_end_day is not None):
                        try:
                            period_date = datetime.strptime(period['date'], '%Y-%m-%d').date()
                            # Only add periods close to fiscal year end
                            if (period_date.month != fiscal_year_end_month or 
                                    abs(period_date.day - fiscal_year_end_day) > 15):
                                continue  # Skip periods that aren't fiscal year ends
                        except (ValueError, TypeError):
                            continue  # Skip periods with invalid dates
                    
                    periods_to_display.append((period['key'], period['label']))
                    added_count += 1
    
    elif statement_type in ['IncomeStatement', 'CashFlowStatement']:
        duration_periods = filter_periods_by_type(all_periods, 'duration')
        # Filter by document period end date to exclude periods after the reporting period
        duration_periods = filter_periods_by_document_end_date(duration_periods, document_period_end_date, 'duration')
        duration_periods = sort_periods(duration_periods, 'duration')
        if duration_periods:
            # For annual reports, prioritize annual periods
            if fiscal_period_focus == 'FY':
                # Get fiscal year end information if available
                fiscal_year_end_month = entity_info.get('fiscal_year_end_month')
                fiscal_year_end_day = entity_info.get('fiscal_year_end_day')
                
                # First pass: Find all periods that are approximately a year long
                candidate_annual_periods = []
                for period in duration_periods:
                    try:
                        start_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
                        end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                        days = (end_date - start_date).days
                        if 350 <= days <= 380:  # ~365 days
                            # Add a score to each period for later sorting
                            # Default score is 0 (will be increased for fiscal year matches)
                            period_with_score = period.copy()
                            period_with_score['fiscal_alignment_score'] = 0
                            candidate_annual_periods.append(period_with_score)
                    except (ValueError, TypeError):
                        continue
                
                # Second pass: Score periods based on alignment with fiscal year pattern
                if fiscal_year_end_month is not None and fiscal_year_end_day is not None:
                    for period in candidate_annual_periods:
                        try:
                            # Check how closely the end date aligns with fiscal year end
                            end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                            
                            # Perfect match: Same month and day as fiscal year end
                            if end_date.month == fiscal_year_end_month and end_date.day == fiscal_year_end_day:
                                period['fiscal_alignment_score'] = 100
                            # Strong match: Same month and within 15 days
                            elif end_date.month == fiscal_year_end_month and abs(end_date.day - fiscal_year_end_day) <= 15:
                                period['fiscal_alignment_score'] = 75
                            # Moderate match: Month before/after and close to the day
                            elif abs(end_date.month - fiscal_year_end_month) <= 1 and abs(end_date.day - fiscal_year_end_day) <= 15:
                                period['fiscal_alignment_score'] = 50
                        except (ValueError, TypeError):
                            continue
                
                # Sort periods by fiscal alignment (higher score first) and then by recency (end date)
                annual_periods = sorted(
                    candidate_annual_periods,
                    key=lambda x: (x['fiscal_alignment_score'], x['end_date']),
                    reverse=True  # Highest score and most recent first
                )
                
                if annual_periods:
                    # Take up to 3 best matching annual periods (prioritizing fiscal year alignment)
                    for period in annual_periods[:3]:
                        periods_to_display.append((period['key'], period['label']))
                    return periods_to_display
            
            # If not annual or no annual periods found, take most recent periods
            for period in duration_periods[:3]:
                periods_to_display.append((period['key'], period['label']))
    
    # For other statement types (not covered by specific logic above)
    else:
        # Get configuration for this statement type, or use defaults
        statement_info = STATEMENT_TYPE_CONFIG.get(statement_type, {})
        
        if not statement_info:
            # For unknown statement types, use heuristics based on available periods
            
            # For unknown statement types, determine preferences based on fiscal period
            if fiscal_period_focus == 'FY':
                # For annual reports, prefer duration periods and show comparisons
                statement_info = {
                    'period_type': 'duration',
                    'max_periods': 3,
                    'allow_annual_comparison': True
                }
            else:
                # For interim reports, accept either type but limit to current period
                statement_info = {
                    'period_type': 'either',
                    'max_periods': 1,
                    'allow_annual_comparison': False
                }
        
        # Select periods based on determined preferences
        period_type = statement_info.get('period_type', 'either')
        max_periods = statement_info.get('max_periods', 1)
        
        if period_type == 'instant' or period_type == 'either':
            instant_periods = filter_periods_by_type(all_periods, 'instant')
            instant_periods = filter_periods_by_document_end_date(instant_periods, document_period_end_date, 'instant')
            instant_periods = sort_periods(instant_periods, 'instant')
            if instant_periods:
                for period in instant_periods[:max_periods]:
                    periods_to_display.append((period['key'], period['label']))
                    
        if (period_type == 'duration' or (period_type == 'either' and not periods_to_display)):
            duration_periods = filter_periods_by_type(all_periods, 'duration')
            duration_periods = filter_periods_by_document_end_date(duration_periods, document_period_end_date, 'duration')
            duration_periods = sort_periods(duration_periods, 'duration')
            if duration_periods:
                for period in duration_periods[:max_periods]:
                    periods_to_display.append((period['key'], period['label']))
    
    return periods_to_display
