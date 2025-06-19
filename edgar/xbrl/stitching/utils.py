"""
XBRL Statement Stitching - Utility Functions

This module contains utility functions for rendering and converting stitched
statement data.
"""

from typing import Any, Dict

import pandas as pd


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