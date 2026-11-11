"""
XBRL Statement Stitching - Utility Functions

This module contains utility functions for rendering and converting stitched
statement data.
"""

from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from edgar.exceptions import ValidationError


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


PERIOD_COLUMN_FORMATS = ("end_date", "interval")


def _interval_column(period_id: str) -> str:
    """The exact-interval column name of one stitched period id (GH #1741)."""
    parts = period_id.split('_')
    if parts[0] == 'instant' and len(parts) == 2:
        return parts[1]
    if parts[0] == 'duration' and len(parts) == 3:
        return f"{parts[1]} to {parts[2]}"
    raise ValidationError(
        f"Cannot name the stitched period {period_id!r} by its interval: expected "
        "'instant_<date>' or 'duration_<start>_<end>'",
        parameter="period_columns", invalid_value=period_id,
        suggestions=["Use period_columns='end_date' for periods without exact dates"])


def period_column_names(periods: List[Tuple[str, str]], period_columns: str = "end_date") -> List[str]:
    """Name the DataFrame column of each stitched ``(period_id, label)``, in order.

    ``"end_date"`` (the default) names a column by its end date, ``2023-07-01``, and
    falls back to the period label when two selected periods share an end date. A
    name can therefore depend on which other periods were selected, and a three-,
    six- and nine-month column look alike. ``"interval"`` names every column by its
    exact dates, whatever else was selected: ``2022-09-25 to 2023-07-01`` for a
    duration and ``2023-07-01`` for an instant (GH #1741).
    """
    if period_columns == "interval":
        return [_interval_column(period_id) for period_id, _ in periods]
    if period_columns != "end_date":
        raise ValidationError(
            f"period_columns must be one of {PERIOD_COLUMN_FORMATS}, got {period_columns!r}",
            parameter="period_columns", invalid_value=period_columns,
            suggestions=list(PERIOD_COLUMN_FORMATS))
    # When two periods share an end date (a 10-Q's discrete quarter and its YTD
    # under include_quarterly=True, GH #780), fall back to the period label.
    end_date_counts = Counter(period_id[-10:] for period_id, _ in periods)
    return [period_id[-10:] if end_date_counts[period_id[-10:]] == 1 else period_label
            for period_id, period_label in periods]


def to_pandas(stitched_data: Dict[str, Any], presentation: bool = True,
              period_columns: str = "end_date") -> pd.DataFrame:
    """
    Convert stitched statement data to a pandas DataFrame.

    Args:
        stitched_data: Stitched statement data
        presentation: If True (default), apply preferred_sign to values so they match
                     SEC HTML display (e.g., cash outflows shown as negative).
                     If False, return raw XBRL instance values.
        period_columns: ``"end_date"`` (default) or ``"interval"``; see
                     :func:`period_column_names`.

    Returns:
        DataFrame with periods as columns and concepts as index
    """
    # Extract periods and statement data
    statement_data = stitched_data['statement_data']

    # Column names in period order (newest first)
    period_columns = period_column_names(stitched_data['periods'], period_columns)
    period_id_to_col = {period_id: col
                        for (period_id, _), col in zip(stitched_data['periods'], period_columns, strict=True)}

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
            col = period_id_to_col[period_id]
            value = item['values'].get(period_id)
            # Apply preferred_sign if presentation mode is enabled
            if presentation and value is not None and ps is not None and ps != 0:
                value = value * ps
            data[col].append(value)

    # Create the DataFrame with columns in the correct order
    column_order = ['label', 'concept', 'standard_concept'] + period_columns + ['preferred_sign']
    df = pd.DataFrame(data, columns=column_order)

    return df
