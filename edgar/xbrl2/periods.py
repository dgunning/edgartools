"""
Period handling functionality for XBRL statements.

This module provides functions for handling periods in XBRL statements, including:
- Determining available period views for different statement types
- Selecting appropriate periods for display
- Handling fiscal year and quarter information
"""

from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple


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
    
    # Get useful entity info for period selection
    entity_info = xbrl_instance.entity_info
    fiscal_period_focus = entity_info.get('fiscal_period')
    annual_report = fiscal_period_focus == 'FY'
    
    # Get all periods
    all_periods = xbrl_instance.reporting_periods
    
    # Sort periods by type
    instant_periods = sorted(
        [p for p in all_periods if p['type'] == 'instant'],
        key=lambda x: x['date'],
        reverse=True  # Latest first
    )
    
    duration_periods = sorted(
        [p for p in all_periods if p['type'] == 'duration'],
        key=lambda x: (x['end_date'], x['start_date']),
        reverse=True  # Latest first
    )
    
    # Generate views based on statement type
    if statement_type == 'BalanceSheet':
        if instant_periods:
            # For balance sheets, we want to show appropriate comparison periods
            if len(instant_periods) >= 3:
                period_views.append({
                    'name': 'Three Recent Periods',
                    'description': 'Shows three most recent reporting periods',
                    'period_keys': [p['key'] for p in instant_periods[:3]]
                })
            else:
                period_views.append({
                    'name': 'Current vs. Previous Period',
                    'description': 'Shows the current period and the previous period',
                    'period_keys': [p['key'] for p in instant_periods[:min(2, len(instant_periods))]]
                })
            
            # If we have more periods, show annual comparisons
            annual_periods = []
            for period in instant_periods:
                if annual_report and ('fiscal_year_end_month' in entity_info and 
                                    'fiscal_year_end_day' in entity_info):
                    # Check if this is an annual period (close to fiscal year end)
                    try:
                        period_date = datetime.strptime(period['date'], '%Y-%m-%d').date()
                        fiscal_month = entity_info.get('fiscal_year_end_month')
                        fiscal_day = entity_info.get('fiscal_year_end_day')
                        
                        # Check if this date is close to fiscal year end
                        if (abs(period_date.month - fiscal_month) <= 1 and 
                            abs(period_date.day - fiscal_day) <= 15):
                            annual_periods.append(period)
                    except (ValueError, TypeError):
                        pass
                else:
                    # Without fiscal info, just use the period
                    annual_periods.append(period)
            
            if len(annual_periods) >= 2:
                if len(annual_periods) >= 3:
                    period_views.append({
                        'name': 'Three-Year Annual Comparison',
                        'description': 'Shows three fiscal years for comparison',
                        'period_keys': [p['key'] for p in annual_periods[:3]]
                    })
                
                period_views.append({
                    'name': 'Annual Comparison',
                    'description': 'Shows two fiscal years for comparison',
                    'period_keys': [p['key'] for p in annual_periods[:min(2, len(annual_periods))]]
                })
                
    elif statement_type in ['IncomeStatement', 'CashFlowStatement']:
        # For Income Statement and Cash Flow, we need to consider duration periods
        annual_periods = []
        quarterly_periods = []
        ytd_periods = []
        
        for period in duration_periods:
            try:
                start_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
                end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                days = (end_date - start_date).days
                
                # Determine period type by duration
                if 350 <= days <= 380:  # Annual: 350-380 days
                    annual_periods.append(period)
                elif 85 <= days <= 95:  # Quarterly: 85-95 days
                    quarterly_periods.append(period)
                elif 175 <= days <= 190:  # Year-to-date (6 months): 175-190 days
                    ytd_periods.append(period)
                elif 265 <= days <= 285:  # Year-to-date (9 months): 265-285 days
                    ytd_periods.append(period)
            except (ValueError, TypeError):
                # Skip periods with invalid dates
                pass
        
        # Generate views based on available periods
        
        # Annual comparisons
        if len(annual_periods) >= 2:
            # Three-year view if available
            if len(annual_periods) >= 3:
                period_views.append({
                    'name': 'Three-Year Comparison',
                    'description': 'Compares three fiscal years',
                    'period_keys': [p['key'] for p in annual_periods[:3]]
                })
            
            # Default two-year view
            period_views.append({
                'name': 'Annual Comparison',
                'description': 'Compares recent fiscal years',
                'period_keys': [p['key'] for p in annual_periods[:min(2, len(annual_periods))]]
            })
        
        # Quarterly comparisons
        if len(quarterly_periods) >= 2:
            # Current quarter vs. same quarter previous year
            if len(quarterly_periods) >= 4:
                current_q = quarterly_periods[0]
                # Try to find same quarter from previous year
                prev_year_q = None
                for q in quarterly_periods[1:]:
                    try:
                        current_end = datetime.strptime(current_q['end_date'], '%Y-%m-%d').date()
                        q_end = datetime.strptime(q['end_date'], '%Y-%m-%d').date()
                        
                        # Check if the quarters are approximately 1 year apart
                        days_diff = abs((current_end - q_end).days - 365)
                        if days_diff <= 15:  # Within 15 days of being exactly 1 year apart
                            prev_year_q = q
                            break
                    except (ValueError, TypeError):
                        continue
                
                if prev_year_q:
                    period_views.append({
                        'name': 'Current Quarter vs. Prior Year Quarter',
                        'description': 'Compares the current quarter with the same quarter last year',
                        'period_keys': [current_q['key'], prev_year_q['key']]
                    })
            
            # Sequential quarters
            period_views.append({
                'name': 'Three Recent Quarters',
                'description': 'Shows three most recent quarters in sequence',
                'period_keys': [p['key'] for p in quarterly_periods[:min(3, len(quarterly_periods))]]
            })
        
        # YTD comparisons
        if len(ytd_periods) >= 2:
            if len(ytd_periods) >= 3:
                period_views.append({
                    'name': 'Three-Year YTD Comparison',
                    'description': 'Compares year-to-date figures across three years',
                    'period_keys': [p['key'] for p in ytd_periods[:3]]
                })
            
            period_views.append({
                'name': 'Year-to-Date Comparison',
                'description': 'Compares year-to-date figures across years',
                'period_keys': [p['key'] for p in ytd_periods[:min(2, len(ytd_periods))]]
            })
        
        # Mixed view - current YTD + quarterly breakdown
        if quarterly_periods and ytd_periods:
            mixed_keys = []
            if ytd_periods:
                mixed_keys.append(ytd_periods[0]['key'])  # Current YTD
                
            # Add recent quarters
            for q in quarterly_periods[:min(4, len(quarterly_periods))]:
                if q['key'] not in mixed_keys:
                    mixed_keys.append(q['key'])
            
            if len(mixed_keys) >= 2:
                period_views.append({
                    'name': 'YTD and Quarterly Breakdown',
                    'description': 'Shows YTD figures and quarterly breakdown',
                    'period_keys': mixed_keys[:5]  # Limit to 5 columns
                })
    
    # For all statement types, if no views have been created yet, add generic ones
    if not period_views and all_periods:
        if statement_type in ['BalanceSheet'] and instant_periods:
            # Use most recent instant periods for balance sheet
            period_keys = [p['key'] for p in instant_periods[:min(3, len(instant_periods))]]
            period_views.append({
                'name': 'Most Recent Periods',
                'description': 'Shows the most recent reporting periods',
                'period_keys': period_keys
            })
        elif statement_type in ['IncomeStatement', 'CashFlowStatement'] and duration_periods:
            # Use most recent duration periods for income/cash flow
            period_keys = [p['key'] for p in duration_periods[:min(3, len(duration_periods))]]
            period_views.append({
                'name': 'Most Recent Periods',
                'description': 'Shows the most recent reporting periods',
                'period_keys': period_keys
            })
    
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
                period_match = None
                # Find the period in our reporting periods
                for period in xbrl_instance.reporting_periods:
                    if period['key'] == period_key:
                        period_match = period
                        break
                
                if period_match:
                    periods_to_display.append((period_key, period_match['label']))
            return periods_to_display
    
    # If no specific periods requested, use default logic based on statement type
    all_periods = xbrl_instance.reporting_periods
    entity_info = xbrl_instance.entity_info
    fiscal_period_focus = entity_info.get('fiscal_period')
    
    # Filter periods by statement type
    if statement_type == 'BalanceSheet':
        instant_periods = sorted(
            [p for p in all_periods if p['type'] == 'instant'],
            key=lambda x: x['date'],
            reverse=True
        )
        if instant_periods:
            # Take up to 3 most recent periods
            for period in instant_periods[:3]:
                periods_to_display.append((period['key'], period['label']))
    
    elif statement_type in ['IncomeStatement', 'CashFlowStatement']:
        duration_periods = sorted(
            [p for p in all_periods if p['type'] == 'duration'],
            key=lambda x: (x['end_date'], x['start_date']),
            reverse=True
        )
        if duration_periods:
            # For annual reports, prioritize annual periods
            if fiscal_period_focus == 'FY':
                annual_periods = []
                for period in duration_periods:
                    try:
                        start_date = datetime.strptime(period['start_date'], '%Y-%m-%d').date()
                        end_date = datetime.strptime(period['end_date'], '%Y-%m-%d').date()
                        days = (end_date - start_date).days
                        if 350 <= days <= 380:  # ~365 days
                            annual_periods.append(period)
                    except (ValueError, TypeError):
                        continue
                
                if annual_periods:
                    # Take up to 3 most recent annual periods
                    for period in annual_periods[:3]:
                        periods_to_display.append((period['key'], period['label']))
                    return periods_to_display
            
            # If not annual or no annual periods found, take most recent periods
            for period in duration_periods[:3]:
                periods_to_display.append((period['key'], period['label']))
    
    return periods_to_display
