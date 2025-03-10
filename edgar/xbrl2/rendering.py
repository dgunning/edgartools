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
    document = Document.parse(html)
    return rich_to_text(document.__str__())


def render_statement(
    statement_data: List[Dict[str, Any]],
    periods_to_display: List[Tuple[str, str]],
    statement_title: str,
    statement_type: str,
    entity_info: Dict[str, Any] = None,
    standard: bool = False,
) -> RichTable:
    """
    Render a financial statement as a rich table.
    
    Args:
        statement_data: Statement data with items and values
        periods_to_display: List of period keys and labels
        statement_title: Title of the statement
        statement_type: Type of statement (BalanceSheet, IncomeStatement, etc.)
        entity_info: Entity information (optional)
        standard: Whether to use standardized concept labels (default: False)
        
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
        # Extract the end date
        if period_key.startswith('instant_'):
            date_str = period_key.split('_')[1]
        else:  # duration
            date_str = period_key.split('_')[2]  # end date
            
        try:
            # Format the date in a more readable format
            date = parse_date(date_str)
            formatted_date = format_date(date)
            
            # Debug check - we shouldn't be displaying dates after document_period_end_date
            if doc_period_end_date and date > doc_period_end_date:
                # This should never happen due to our filtering above
                # If it does, fall back to document_period_end_date
                fallback_date = format_date(doc_period_end_date)
                formatted_periods.append((period_key, fallback_date))
            else:
                formatted_periods.append((period_key, formatted_date))
        except (ValueError, TypeError, IndexError):
            # Fall back to original label if date parsing fails
            formatted_periods.append((period_key, original_label))
    
    # Determine the dominant scale for monetary values in this statement
    dominant_scale = determine_dominant_scale(statement_data, periods_to_display)
    
    # Add the fiscal period indicator and units note as a subtitle if available
    if formatted_periods:
        subtitles = []
        
        # Add fiscal period indicator if available
        if fiscal_period_indicator:
            subtitles.append(f"[bold]{fiscal_period_indicator}[/bold]")
        
        # Add units note
        if is_monetary_statement:
            if dominant_scale == -3:
                units_note = "[italic](In thousands, except per share data)[/italic]"
            elif dominant_scale == -6:
                units_note = "[italic](In millions, except per share data)[/italic]"
            elif dominant_scale == -9:
                units_note = "[italic](In billions, except per share data)[/italic]"
            else:
                units_note = ""
            
            if units_note:
                subtitles.append(units_note)
        
        # Apply subtitles to table title
        if subtitles:
            table.title = f"{statement_title}\n{' '.join(subtitles)}"
    
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
        
        # Get values for each period
        period_values = []
        for period_key, _ in periods_to_display:
            value = item['values'].get(period_key, "")
            fact_decimals = item.get('decimals', {}).get(period_key, 0)
            
            # Determine if this value should be formatted as currency
            # Check label to identify non-monetary items like shares, ratios, etc.
            is_monetary = is_monetary_statement
            
            # Check for shares-related values by examining label
            label_lower = label.lower()
            if any(keyword in label_lower for keyword in [
                'earnings per share', 'per common share', 'per share', 'in shares', 'shares outstanding'
                'per basic', 'per diluted'
            ]):
                is_monetary = False

            # Ratio-related items should not be monetary
            if any(keyword == word for keyword in ['ratio', 'percentage', 'per cent']
                   for word in label_lower.split()):
                is_monetary = False
            
            # Format numeric values
            if isinstance(value, (int, float)):
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