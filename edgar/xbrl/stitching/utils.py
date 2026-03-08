"""
XBRL Statement Stitching - Utility Functions

This module contains utility functions for rendering and converting stitched
statement data.
"""

from typing import Any, Dict, Optional

import pandas as pd


def render_stitched_statement(
    stitched_data: Dict[str, Any],
    statement_title: str,
    statement_type: str,
    entity_info: Optional[Dict[str, Any]] = None,
    show_date_range: bool = False,
    xbrl_instance: Optional[Any] = None
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
    # Pass standard=False because stitcher already applied standardization
    return render_statement(
        statement_data=statement_data,
        periods_to_display=periods_to_display,
        statement_title=statement_title,
        statement_type=statement_type,
        entity_info=entity_info,
        standard=False,
        show_date_range=show_date_range,
        xbrl_instance=xbrl_instance
    )


def to_pandas(stitched_data: Dict[str, Any], presentation: bool = True) -> pd.DataFrame:
    """
    Convert stitched statement data to a pandas DataFrame.

    Args:
        stitched_data: Stitched statement data
        presentation: If True (default), apply preferred_sign to values so they match
                     SEC HTML display (e.g., cash outflows shown as negative).
                     If False, return raw XBRL instance values.

    Returns:
        DataFrame with periods as columns and concepts as index
    """
    # Extract periods and statement data
    statement_data = stitched_data['statement_data']

    # Create ordered list of period column names (preserving the original ordering)
    period_columns = []
    for period_id, _period_label in stitched_data['periods']:
        # Use the end_date in YYYY-MM-DD format as the column name
        col = period_id[-10:]
        period_columns.append(col)

    # Create a dictionary for the DataFrame with ordered columns
    # Start with metadata columns
    data = {}
    data['label'] = []
    data['concept'] = []
    data['standard_concept'] = []
    data['preferred_sign'] = []

    # Initialize period columns in the correct order (newest first)
    for col in period_columns:
        data[col] = []

    for _i, item in enumerate(statement_data):
        # Skip abstract items without values
        if item['is_abstract'] and not item['has_values']:
            continue

        data['label'].append(item['label'])
        data['concept'].append(item['concept'])
        data['standard_concept'].append(item.get('standard_concept'))

        # Extract concept-level preferred_sign (same for all periods)
        preferred_signs = item.get('preferred_signs', {})
        ps = next(iter(preferred_signs.values()), None) if preferred_signs else None
        data['preferred_sign'].append(ps)

        # Add values for each period in the correct order
        for period_id, _period_label in stitched_data['periods']:
            col = period_id[-10:]
            value = item['values'].get(period_id)
            # Apply preferred_sign if presentation mode is enabled
            if presentation and value is not None and ps is not None and ps != 0:
                value = value * ps
            data[col].append(value)

    # Create the DataFrame with columns in the correct order
    column_order = ['label', 'concept', 'standard_concept'] + period_columns + ['preferred_sign']
    df = pd.DataFrame(data, columns=column_order)

    return df
