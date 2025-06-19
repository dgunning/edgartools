"""
XBRL Statement Stitching - Period Optimization

This module provides functionality to determine optimal periods for stitching
statements across multiple XBRL filings, handling period selection and
fiscal period matching.
"""

from collections import defaultdict
from datetime import date
from typing import Any, Dict, List

from edgar.xbrl.core import format_date, parse_date

from edgar.xbrl.xbrl import XBRL


def determine_optimal_periods(xbrl_list: List['XBRL'], statement_type: str, max_periods:int=8) -> List[Dict[str, Any]]:
    """
    Determine the optimal periods to display for stitched statements from a list of XBRL objects.
    
    This function analyzes entity info and reporting periods across multiple XBRL instances
    to select the most appropriate periods for display, ensuring consistency in period selection
    when creating stitched statements.
    
    Args:
        xbrl_list: List of XBRL objects ordered chronologically
        statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
        max_periods: Maximum number of periods to return (default is 8)
        
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
    if len(filtered_periods) > max_periods:
        filtered_periods = filtered_periods[:max_periods]
    
    return filtered_periods