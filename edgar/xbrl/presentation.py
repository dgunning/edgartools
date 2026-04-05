"""
StatementView enum for controlling dimensional data display in financial statements.

This module provides the StatementView enum which replaces the confusing
include_dimensions boolean parameter with semantic view modes.
"""
from enum import Enum
from typing import Union

__all__ = ['StatementView', 'ViewType', 'normalize_view']


class StatementView(str, Enum):
    """Controls dimensional data display in financial statements.

    STANDARD: Face presentation matching SEC Viewer.
              Shows face-level dimensions (Products/Services), hides breakdowns.
              Uses strict presentation-tree member filtering.
              Default for display/print.

    DETAILED: All dimensional data included.
              Shows all dimensional breakdowns (iPhone, iPad, Mac, etc.).
              Uses relaxed member filtering for complete data extraction.
              Default for to_dataframe().

    SUMMARY:  Non-dimensional totals only.
              Hides all dimensional rows.
              Useful for quick overview of main line items.

    Examples:
        >>> from edgar.xbrl import StatementView
        >>> # Display uses STANDARD by default
        >>> print(income_statement)
        >>>
        >>> # DataFrame uses DETAILED by default for complete data
        >>> df = income_statement.to_dataframe()
        >>>
        >>> # Explicit view control
        >>> df = income_statement.to_dataframe(view=StatementView.STANDARD)
        >>> df = income_statement.to_dataframe(view='detailed')  # string also works
    """

    STANDARD = "standard"
    DETAILED = "detailed"
    SUMMARY = "summary"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"StatementView.{self.name}"


# Type alias for parameter hints - accepts both enum and string
ViewType = Union[StatementView, str, None]


def normalize_view(view: ViewType) -> StatementView:
    """Convert string or enum to StatementView.

    Args:
        view: A StatementView enum value or string ('standard', 'detailed', 'summary')

    Returns:
        StatementView enum value

    Raises:
        ValueError: If view is not a valid StatementView value

    Examples:
        >>> normalize_view('standard')
        StatementView.STANDARD
        >>> normalize_view(StatementView.DETAILED)
        StatementView.DETAILED
        >>> normalize_view('SUMMARY')  # case-insensitive
        StatementView.SUMMARY
    """
    if view is None:
        return StatementView.STANDARD

    if isinstance(view, StatementView):
        return view

    if isinstance(view, str):
        try:
            return StatementView(view.lower())
        except ValueError:
            valid_values = ', '.join(v.value for v in StatementView)
            raise ValueError(
                f"Invalid view '{view}'. Must be one of: {valid_values}"
            )

    raise TypeError(
        f"view must be StatementView or str, got {type(view).__name__}"
    )
