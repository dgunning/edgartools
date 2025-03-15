"""
Rendering functions for XBRL data.

This module provides functions for formatting and displaying XBRL data.
"""

from typing import Dict, List, Any, Optional, Tuple, Union

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table as RichTable
from rich.text import Text

from edgar.xbrl2.core import (
    determine_dominant_scale, format_value, format_date, parse_date
)
from edgar.xbrl2 import standardization
from edgar.richtools import rich_to_text
from edgar.files.html import Document
from datetime import datetime

share_concepts = [
    'us-gaap_CommonStockSharesOutstanding',
    'us-gaap_WeightedAverageNumberOfSharesOutstandingBasic',
    'us-gaap_WeightedAverageNumberOfSharesOutstandingDiluted',
    'us-gaap_WeightedAverageNumberOfDilutedSharesOutstanding',
    'us-gaap_CommonStockSharesIssued'
]


def _is_html(text: str) -> bool:
    """
    Simple check to determine if a string contains HTML content.
    
    Args:
        text: The string to check
        
    Returns:
        bool: True if the string appears to contain HTML, False otherwise
    """
    html_tags = ['<p', '<div', '<span', '<br', '<table', '<tr', '<td', '<th',
                '<ul>', '<li', '<ol>', '<h1>', '<h2>', '<h3>', '<h4>', '<h5>', '<h6>']
    
    text_lower = text.lower()
    return any(tag in text_lower for tag in html_tags)


def html_to_text(html: str) -> str:
    """
    Convert HTML to plain text.
    
    Args:
        html: HTML content to convert
        
    Returns:
        str: Plain text representation of the HTML
    """
    # Wrap in html tag if not present
    html = f"<html>{html}</html>" if not html.startswith("<html>") else html
    document = Document.parse(html)
    return rich_to_text(document.__str__())



def render_statement(
    statement_data: List[Dict[str, Any]],
    periods_to_display: List[Tuple[str, str]],
    statement_title: str,
    statement_type: str,
    entity_info: Dict[str, Any] = None,
    standard: bool = True,
    show_date_range: bool = False,
) -> RichTable:
    """
    Render a financial statement as a rich table.
    
    Args:
        statement_data: Statement data with items and values
        periods_to_display: List of period keys and labels
        statement_title: Title of the statement
        statement_type: Type of statement (BalanceSheet, IncomeStatement, etc.)
        entity_info: Entity information (optional)
        standard: Whether to use standardized concept labels (default: True)
        show_date_range: Whether to show full date ranges for duration periods (default: False)
        
    Returns:
        RichTable: A formatted table representation of the statement
    """
    entity_info = entity_info or {}
    
    # Apply standardization if requested
    if standard:
        # Create a concept mapper with default mappings
        mapper = standardization.ConceptMapper(standardization.initialize_default_mappings())
        
        # Add statement type to context for better mapping
        for item in statement_data:
            item['statement_type'] = statement_type
        
        # Standardize the statement data
        statement_data = standardization.standardize_statement(statement_data, mapper)
        
        # Indicate that standardization is being used in the title
        statement_title = f"{statement_title} (Standardized)"
    
    # Create the table
    table = RichTable(title=statement_title, box=box.SIMPLE)
    
    # Determine if this is likely a monetary statement
    is_monetary_statement = statement_type in ['BalanceSheet', 'IncomeStatement', 'CashFlowStatement']
    
    # Format period headers to be cleaner (just end dates with fiscal period indicator)
    formatted_periods = []
    fiscal_period_indicator = None
    
    # Get document_period_end_date from entity_info
    doc_period_end_date = entity_info.get('document_period_end_date')
    
    # First, determine the fiscal period type (annual, quarterly, etc.) based on the first period
    if periods_to_display:
        first_period_key = periods_to_display[0][0]
        
        # For instant periods (Balance Sheet)
        if first_period_key.startswith('instant_'):
            date_str = first_period_key.split('_')[1]
            try:
                date = parse_date(date_str)
                
                # Determine if this is fiscal year end or interim period
                if ('fiscal_year_end_month' in entity_info and 
                    'fiscal_year_end_day' in entity_info and
                    'fiscal_period' in entity_info):
                    
                    fiscal_month = entity_info.get('fiscal_year_end_month')
                    fiscal_day = entity_info.get('fiscal_year_end_day')
                    fiscal_period = entity_info.get('fiscal_period')
                    
                    if fiscal_period == 'FY' or (
                            date.month == fiscal_month and 
                            abs(date.day - fiscal_day) <= 7):
                        fiscal_period_indicator = "Fiscal Year Ended"
                    else:
                        # For quarterly periods
                        if fiscal_period in ['Q1', 'Q2', 'Q3']:
                            month_names = {
                                'Q1': 'First Quarter Ended',
                                'Q2': 'Second Quarter Ended',
                                'Q3': 'Third Quarter Ended'
                            }
                            fiscal_period_indicator = month_names.get(fiscal_period, "Quarter Ended")
                        else:
                            fiscal_period_indicator = "As of"
                else:
                    fiscal_period_indicator = "As of"
            except (ValueError, TypeError):
                fiscal_period_indicator = "As of"
        
        # For duration periods (Income Statement, Cash Flow)
        else:
            start_date_str, end_date_str = first_period_key.split('_')[1], first_period_key.split('_')[2]
            try:
                start_date = parse_date(start_date_str)
                end_date = parse_date(end_date_str)
                duration_days = (end_date - start_date).days
                
                # Determine period type based on duration
                if 85 <= duration_days <= 95:
                    fiscal_period_indicator = "Three Months Ended"
                elif 175 <= duration_days <= 190:
                    fiscal_period_indicator = "Six Months Ended"
                elif 265 <= duration_days <= 285:
                    fiscal_period_indicator = "Nine Months Ended"
                elif 355 <= duration_days <= 375:
                    fiscal_period_indicator = "Year Ended"
                else:
                    # Use fiscal period information if available
                    if 'fiscal_period' in entity_info:
                        fiscal_period = entity_info.get('fiscal_period')
                        if fiscal_period == 'FY':
                            fiscal_period_indicator = "Year Ended"
                        elif fiscal_period == 'Q1':
                            fiscal_period_indicator = "Three Months Ended"
                        elif fiscal_period == 'Q2':
                            fiscal_period_indicator = "Six Months Ended"
                        elif fiscal_period == 'Q3':
                            fiscal_period_indicator = "Nine Months Ended"
                        else:
                            fiscal_period_indicator = "Period Ended"
                    else:
                        fiscal_period_indicator = "Period Ended"
            except (ValueError, TypeError, IndexError):
                fiscal_period_indicator = "Period Ended"
    
    # Create formatted period columns
    for period_key, original_label in periods_to_display:
        # If we have a date-based label, ensure it uses abbreviated months
        # This handles both our internal date formatting and dates from XBRL data
        if original_label and ',' in original_label:
            # Check if it contains a full month name that needs to be abbreviated
            for full_month, abbr in [
                ('January', 'Jan'), ('February', 'Feb'), ('March', 'Mar'),
                ('April', 'Apr'), ('May', 'May'), ('June', 'Jun'),
                ('July', 'Jul'), ('August', 'Aug'), ('September', 'Sep'),
                ('October', 'Oct'), ('November', 'Nov'), ('December', 'Dec')
            ]:
                if full_month in original_label:
                    # Try to extract and reformat the date properly
                    try:
                        # Extract year from the original label
                        year = int(''.join(c for c in original_label.split(',')[1] if c.isdigit()))
                        # Extract day - find digits after the month
                        day_part = original_label.split(full_month)[1].strip()
                        day = int(''.join(c for c in day_part.split(',')[0] if c.isdigit()))
                        # Create a proper date and format it
                        month_num = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                                   'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}[abbr]
                        date_obj = None
                        try:
                            date_obj = datetime(year, month_num, day).date()
                            formatted_periods.append((period_key, format_date(date_obj)))
                            break
                        except ValueError:
                            # Handle invalid dates (like Sep 31) by using a valid date for that month
                            if day > 28:  # Potentially invalid day
                                # Use last day of month instead
                                if month_num == 2:  # February
                                    day = 28 if year % 4 != 0 else 29
                                elif month_num in [4, 6, 9, 11]:  # 30-day months
                                    day = 30
                                else:  # 31-day months
                                    day = 31
                                try:
                                    date_obj = datetime(year, month_num, day).date()
                                    formatted_periods.append((period_key, format_date(date_obj)))
                                    break
                                except ValueError:
                                    pass
                    except (ValueError, IndexError):
                        pass
            
            # If we couldn't extract and reformat, but it's already using abbreviated months, use as is
            if len(formatted_periods) == 0 or formatted_periods[-1][0] != period_key:
                for abbr in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']:
                    if abbr in original_label:
                        formatted_periods.append((period_key, original_label))
                        break
                else:
                    # If we get here, no month abbreviation was found, use original
                    formatted_periods.append((period_key, original_label))
            continue
            
        # For better clarity, prefer to use the original labels which include fiscal year information
        # This helps distinguish between periods like Sep 30, 2023 and Sep 24, 2022 in the rendering
        if original_label and len(original_label) > 4:
            # Get a cleaner version of the label if it's too verbose
            if len(original_label) > 30 and ':' in original_label:
                # Extract just the fiscal period and date information
                try:
                    if "Annual:" in original_label:
                        # Extract fiscal year end date
                        parts = original_label.split('to')
                        if len(parts) > 1:
                            end_date_str = parts[1].strip()
                            end_date = parse_date(end_date_str)
                            cleaner_label = format_date(end_date)
                            formatted_periods.append((period_key, cleaner_label))
                            continue
                    elif "Quarterly:" in original_label:
                        # Extract quarter end date
                        parts = original_label.split('to')
                        if len(parts) > 1:
                            end_date_str = parts[1].strip()
                            end_date = parse_date(end_date_str)
                            cleaner_label = format_date(end_date)
                            formatted_periods.append((period_key, cleaner_label))
                            continue
                except (ValueError, TypeError):
                    pass
                    
            # If we couldn't extract a cleaner version, use the original
            formatted_periods.append((period_key, original_label))
            continue
        
        # If we don't have a good original label, extract and format the date
        if period_key.startswith('instant_'):
            date_str = period_key.split('_')[1]
            try:
                date = parse_date(date_str)
                # For better comparison, use a consistent fiscal year date format
                formatted_date = format_date(date)
                formatted_periods.append((period_key, formatted_date))
                
                # Store period metadata for later filtering of similar periods
                period_metadata = {
                    'key': period_key, 
                    'type': 'instant',
                    'date': date
                }
            except (ValueError, TypeError, IndexError):
                # Fall back to original label if date parsing fails
                formatted_periods.append((period_key, original_label))
        else:  # duration
            # For duration periods, try to extract end date to show fiscal year
            parts = period_key.split('_')
            if len(parts) >= 3:
                try:
                    start_date_str = parts[1]
                    end_date_str = parts[2]
                    start_date = parse_date(start_date_str)
                    end_date = parse_date(end_date_str)
                    
                    # Determine if we should show the full date range or just the end date
                    if show_date_range:
                        # Show full date range for duration periods
                        formatted_date = f"{format_date(start_date)} - {format_date(end_date)}"
                    else:
                        # Use a consistent format focusing on the end date which is typically
                        # the fiscal period end that users care about
                        formatted_date = format_date(end_date)
                    
                    # For quarterly reports, include quarter information
                    duration_days = (end_date - start_date).days
                    if 80 <= duration_days <= 100:  # Quarterly
                        # Determine quarter number
                        month = end_date.month
                        if month <= 3 or month == 12:
                            q_num = "Q1"
                        elif month <= 6:
                            q_num = "Q2"
                        elif month <= 9:
                            q_num = "Q3"
                        else:
                            q_num = "Q4"
                            
                        # Only add quarter information if it adds clarity
                        if statement_type in ['IncomeStatement', 'CashFlowStatement']:
                            # If we're showing date range, put quarter in parentheses
                            if show_date_range:
                                formatted_date = f"{formatted_date} ({q_num})"
                            else:
                                formatted_date = f"{formatted_date} ({q_num})"
                    
                    formatted_periods.append((period_key, formatted_date))
                    
                    # Store period metadata for later filtering of similar periods
                    period_metadata = {
                        'key': period_key, 
                        'type': 'duration',
                        'start_date': start_date,
                        'end_date': end_date,
                        'duration_days': duration_days
                    }
                except (ValueError, TypeError, IndexError):
                    # Fall back to original label if date parsing fails
                    formatted_periods.append((period_key, original_label))
            else:
                # Fall back to original label for malformed period keys
                formatted_periods.append((period_key, original_label))
    
    # Determine the dominant scale for monetary values in this statement
    dominant_scale = determine_dominant_scale(statement_data, periods_to_display)
    
    # Determine the scale used for share amounts if present
    shares_scale = None

    # Look for share-related concepts to determine their scaling from the decimals attribute
    for item in statement_data:
        concept = item.get('concept', '')
        if concept in share_concepts:
            # Check decimals attribute to determine proper scaling
            for period_key, _ in periods_to_display:
                decimals = item.get('decimals', {}).get(period_key)
                if isinstance(decimals, int) and decimals <= 0:
                    # Use the decimals attribute to determine the scale
                    # For shares, decimals is typically negative
                    # -3 means thousands, -6 means millions, etc.
                    shares_scale = decimals
                    break
            if shares_scale is not None:
                break
    
    # Add the fiscal period indicator and note as a subtitle if available
    if formatted_periods:
        subtitles = []
        
        # Add fiscal period indicator if available
        if fiscal_period_indicator:
            subtitles.append(f"[bold]{fiscal_period_indicator}[/bold]")
        
        # Add units note
        if is_monetary_statement:
            monetary_scale_text = ""
            if dominant_scale == -3:
                monetary_scale_text = "thousands"
            elif dominant_scale == -6:
                monetary_scale_text = "millions"
            elif dominant_scale == -9:
                monetary_scale_text = "billions"
            
            shares_scale_text = ""
            if shares_scale is not None:
                if shares_scale == -3:
                    shares_scale_text = "thousands"
                elif shares_scale == -6:
                    shares_scale_text = "millions"
                elif shares_scale == -9:
                    shares_scale_text = "billions"
                elif shares_scale == 0:
                    shares_scale_text = "actual amounts"
                else:
                    # For other negative scales (like -4, -5, -7, etc.)
                    # Use a more generic description based on the scale
                    scale_factor = 10 ** (-shares_scale)
                    if scale_factor >= 1000:
                        shares_scale_text = f"scaled by {scale_factor:,}"
            
            # Construct appropriate units note
            if monetary_scale_text and shares_scale_text and shares_scale != dominant_scale:
                units_note = f"[italic](In {monetary_scale_text}, except shares in {shares_scale_text})[/italic]"
            elif monetary_scale_text:
                units_note = f"[italic](In {monetary_scale_text}, except per share data)[/italic]"
            else:
                units_note = ""
            
            if units_note:
                subtitles.append(units_note)
        
        # Apply subtitles to table title
        if subtitles:
            table.title = f"{statement_title}\n{' '.join(subtitles)}"
    
    # Extract period metadata for each period for better filtering
    period_metadatas = []
    for period_key, period_label in formatted_periods:
        # Try to extract dates from the period key
        if period_key.startswith('instant_'):
            try:
                date_str = period_key.split('_')[1]
                date = parse_date(date_str)
                period_metadatas.append({
                    'key': period_key,
                    'label': period_label,
                    'type': 'instant',
                    'date': date,
                    'end_date': date,  # Use same date as end_date for comparison
                    'has_metadata': True
                })
                continue
            except (ValueError, TypeError, IndexError):
                pass
        elif '_' in period_key and len(period_key.split('_')) >= 3:
            try:
                parts = period_key.split('_')
                start_date_str = parts[1]
                end_date_str = parts[2]
                start_date = parse_date(start_date_str)
                end_date = parse_date(end_date_str)
                duration_days = (end_date - start_date).days
                period_metadatas.append({
                    'key': period_key,
                    'label': period_label,
                    'type': 'duration',
                    'start_date': start_date,
                    'end_date': end_date,
                    'duration_days': duration_days,
                    'has_metadata': True
                })
                continue
            except (ValueError, TypeError, IndexError):
                pass
        
        # If we get here, we couldn't extract meaningful metadata
        period_metadatas.append({
            'key': period_key,
            'label': period_label,
            'type': 'unknown',
            'has_metadata': False
        })
    
    # Check if columns are mostly empty or all empty
    # Calculate the percentage of non-empty values for each period
    period_value_counts = {period_key: 0 for period_key, _ in formatted_periods}
    period_item_counts = {period_key: 0 for period_key, _ in formatted_periods}
    
    # Count non-empty values for each period
    for item in statement_data:
        # Skip abstract items as they typically don't have values
        if item.get('is_abstract', False):
            continue
        
        # Skip items with brackets in labels (usually axis/dimension items)
        if any(bracket in item['label'] for bracket in ['[Axis]', '[Domain]', '[Member]', '[Line Items]', '[Table]', '[Abstract]']):
            continue
        
        for period_key, _ in formatted_periods:
            # Count this item for the period
            period_item_counts[period_key] += 1
            
            # Check if it has a value
            value = item['values'].get(period_key)
            if value not in (None, "", 0):  # Consider 0 as a value for financial statements
                period_value_counts[period_key] += 1
    
    # Calculate percentage of non-empty values for each period
    period_value_percentages = {}
    for period_key, count in period_item_counts.items():
        if count > 0:
            period_value_percentages[period_key] = period_value_counts[period_key] / count
        else:
            period_value_percentages[period_key] = 0
    
    # Add data density to period metadata
    for metadata in period_metadatas:
        data_density = period_value_percentages.get(metadata['key'], 0)
        metadata['data_density'] = data_density
        metadata['num_values'] = period_value_counts.get(metadata['key'], 0)
        metadata['total_items'] = period_item_counts.get(metadata['key'], 0)
        
        # For debugging - useful when diagnosing period selection issues
        if metadata['has_metadata'] and data_density > 0.01:  # Only log periods with some data
            date_info = ""
            if metadata['type'] == 'instant':
                date_info = f"date: {metadata['date']}"
            elif metadata['type'] == 'duration':
                date_info = f"from {metadata['start_date']} to {metadata['end_date']} ({metadata['duration_days']} days)"
            
            # This print will only appear in debug output, not to the user
            # print(f"Period {metadata['key']}: {metadata['label']} - {metadata['type']} {date_info} - density: {data_density:.2%} ({metadata['num_values']}/{metadata['total_items']} items)")
    
    # Filter out periods that are too similar to others
    # 1. Filter by data density (keep periods with more data)
    # 2. Filter by appropriateness for statement type (instant for balance sheet, duration for income statement)
    # 3. Filter by date proximity (avoid almost identical end dates)
    
    # First, filter by data density threshold
    threshold = 0.08  # 2% non-empty values threshold for all statements
    
    # Filter periods that have enough data
    dense_periods = [m for m in period_metadatas if m['data_density'] >= threshold]
    
    # If we filtered out all periods, keep at least one (the most populated)
    if not dense_periods and period_metadatas:
        # Find period with most values
        best_metadata = max(period_metadatas, key=lambda x: x['data_density'])
        dense_periods = [best_metadata]
    
    # Next, filter by period type appropriateness for statement type
    # For balance sheets, prefer instant periods
    # For income statements, prefer duration periods
    appropriate_periods = []
    
    if statement_type == 'BalanceSheet':
        # For balance sheets, prefer instant periods
        instant_periods = [p for p in dense_periods if p['type'] == 'instant' and p['has_metadata']]
        if instant_periods:
            appropriate_periods = instant_periods
        else:
            appropriate_periods = dense_periods
    elif statement_type in ['IncomeStatement', 'CashFlowStatement']:
        # For income statements, prefer duration periods
        duration_periods = [p for p in dense_periods if p['type'] == 'duration' and p['has_metadata']]
        if duration_periods:
            appropriate_periods = duration_periods
        else:
            appropriate_periods = dense_periods
    else:
        # For other statement types, use the dense periods
        appropriate_periods = dense_periods
    
    # Finally, filter out periods that are too similar in date
    # Sort periods by end date (for proper chronological ordering)
    periods_with_dates = [p for p in appropriate_periods if p['has_metadata']]
    periods_without_dates = [p for p in appropriate_periods if not p['has_metadata']]
    
    # Only apply date filtering if we have periods with date metadata
    if periods_with_dates:
        # Sort by end date (most recent first), then by data density (descending)
        periods_with_dates.sort(key=lambda x: (x['end_date'], -x['data_density']), reverse=True)
        
        # Filter out periods that are too close to each other (within a few days)
        filtered_periods_by_date = []
        
        for period in periods_with_dates:
            # Check if this period is too close to any already included period
            too_close = False
            for included_period in filtered_periods_by_date:
                # Skip comparison if types don't match
                if period['type'] != included_period['type']:
                    continue
                
                # Calculate date difference
                days_diff = abs((period['end_date'] - included_period['end_date']).days)
                
                # Periods are too similar if they are of the same type and within 14 days
                if days_diff <= 14:
                    # If the current period has more data, replace the included one
                    # Being more aggressive about preferring periods with more data
                    if period['data_density'] > 1.2 * included_period['data_density']:
                        filtered_periods_by_date.remove(included_period)
                    else:
                        # Otherwise, consider this period too close
                        too_close = True
                    break
            
            # Add the period if it's not too close to any included period
            if not too_close:
                filtered_periods_by_date.append(period)
        
        # Combine filtered periods with those without dates
        appropriate_periods = filtered_periods_by_date + periods_without_dates
    
    # Convert metadata back to (key, label) format
    filtered_periods = [(m['key'], m['label']) for m in appropriate_periods]
    
    # If we filtered out all periods, keep at least one (the most populated)
    if not filtered_periods and formatted_periods:
        # Find period with most values
        best_period_key = max(period_value_percentages.items(), key=lambda x: x[1])[0]
        # Find the corresponding label
        best_period_label = next((label for key, label in formatted_periods if key == best_period_key), "")
        filtered_periods.append((best_period_key, best_period_label))
    
    # Update formatted_periods with the filtered list
    formatted_periods = filtered_periods
    
    # Add columns with right-alignment for numeric columns
    table.add_column("Line Item", justify="left")
    for _, period_label in formatted_periods:
        table.add_column(period_label)
    
    # Add rows
    for item in statement_data:
        # Skip rows with no values if they're abstract (headers without data)
        # But keep abstract items with children (section headers)
        if not item.get('has_values', False) and item.get('is_abstract') and not item.get('children'):
            continue
            
        # Skip non-abstract items without values (missing data)
        if not item.get('has_values', False) and not item.get('is_abstract') and not item.get('children'):
            continue
            
        # Skip axis/dimension items (they contain brackets in their labels)
        if any(bracket in item['label'] for bracket in ['[Axis]', '[Domain]', '[Member]', '[Line Items]', '[Table]', '[Abstract]']):
            continue
            
        # Format the label based on level and abstract status
        level = item['level']

        # Remove [Abstract] from label if present
        label = item['label'].replace(' [Abstract]', '')

        concept = item['concept']
        
        # Get values for each period
        period_values = []
        for period_key, _ in formatted_periods:
            value = item['values'].get(period_key, "")
            fact_decimals = item.get('decimals', {}).get(period_key, 0)
            
            # Determine if this value should be formatted as currency
            # Check label to identify non-monetary items like shares, ratios, etc.
            is_monetary = is_monetary_statement
            
            # Check for shares-related values by examining concept names
            label_lower = label.lower()
            is_share_value = False

            if concept in ['us-gaap_EarningsPerShareBasic', 'us-gaap_EarningsPerShareDiluted']:
                is_monetary = False
            elif concept in share_concepts:
                is_monetary = False
                is_share_value = True
            
            # Ratio-related items should not be monetary
            if any(keyword == word for keyword in ['ratio', 'percentage', 'per cent']
                   for word in label_lower.split()):
                is_monetary = False
            
            # Format numeric values
            if isinstance(value, (int, float)):
                # Handle share values differently
                if is_share_value and isinstance(fact_decimals, int):
                    # Use fact_decimals to determine the appropriate scaling for share values
                    # This ensures correct display for companies of all sizes
                    if fact_decimals <= -3:
                        # Apply appropriate scaling based on the actual decimals value
                        scale_factor = 10 ** (-fact_decimals)
                        scaled_value = value / scale_factor
                        # Always display share amounts with 0 decimal places for cleaner presentation
                        formatted_value = Text(f"{scaled_value:,.0f}", justify="right")
                    else:
                        # For smaller numbers or positive decimals, use unscaled values
                        formatted_value = Text(f"{value:,.0f}", justify="right")
                else:
                    # Format other values normally using the flexible format_value function
                    formatted_value = Text(format_value(value, is_monetary, dominant_scale, fact_decimals), justify="right")
            else:
                # Non-numeric values - check if it's HTML and convert if needed
                if value and isinstance(value, str) and _is_html(value):
                    formatted_value = html_to_text(value)
                else:
                    formatted_value = str(value) if value else "" # Empty string for empty values

            period_values.append(formatted_value)
        
        # Apply different formatting based on level and abstract status
        if item['is_abstract']:
            if level == 0:
                # Top-level header - full caps, bold
                styled_label = f"[bold]{label.upper()}[/bold]"
            elif level == 1:
                # Section header - bold
                styled_label = f"[bold]{label}[/bold]"
            else:
                # Sub-section header - indented, bold
                indent = "  " * (level - 1)  # Less aggressive indentation
                styled_label = f"[bold]{indent}{label}[/bold]"
            
            # Headers typically don't have values
            table.add_row(styled_label, *["" for _ in formatted_periods])
        else:
            # Regular line items - indented based on level
            indent = "  " * level
            styled_label = f"{indent}{label}"
            table.add_row(styled_label, *period_values)
    
    return table


def generate_rich_representation(xbrl) -> Panel:
    """
    Generate a rich representation of the XBRL document.
    
    Args:
        xbrl: XBRL object
        
    Returns:
        Panel: A formatted panel with XBRL document information
    """
    components = []
    
    # Entity information
    if xbrl.entity_info:
        entity_table = RichTable(title="Entity Information", box=box.SIMPLE)
        entity_table.add_column("Property")
        entity_table.add_column("Value")
        
        for key, value in xbrl.entity_info.items():
            entity_table.add_row(key, str(value))
        
        components.append(entity_table)
    
    # Statements summary
    statements = xbrl.get_all_statements()
    if statements:
        statement_table = RichTable(title="Financial Statements", box=box.SIMPLE)
        statement_table.add_column("Type")
        statement_table.add_column("Definition")
        statement_table.add_column("Elements")
        
        for stmt in statements:
            statement_table.add_row(
                stmt['type'] or "Other",
                stmt['definition'],
                str(stmt['element_count'])
            )
        
        components.append(statement_table)
    
    # Facts summary
    fact_table = RichTable(title="Facts Summary", box=box.SIMPLE)
    fact_table.add_column("Category")
    fact_table.add_column("Count")
    
    fact_table.add_row("Total Facts", str(len(xbrl.facts)))
    fact_table.add_row("Contexts", str(len(xbrl.contexts)))
    fact_table.add_row("Units", str(len(xbrl.units)))
    fact_table.add_row("Elements", str(len(xbrl.element_catalog)))
    
    components.append(fact_table)
    
    # Reporting periods
    if xbrl.reporting_periods:
        period_table = RichTable(title="Reporting Periods", box=box.SIMPLE)
        period_table.add_column("Type")
        period_table.add_column("Period")
        
        for period in xbrl.reporting_periods:
            if period['type'] == 'instant':
                period_table.add_row("Instant", period['date'])
            else:
                period_table.add_row("Duration", f"{period['start_date']} to {period['end_date']}")
        
        components.append(period_table)
    
    return Panel(Group(*components), title="XBRL Document", border_style="green")