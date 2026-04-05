"""
Financial statement processing for XBRL data.

This module provides functions for working with financial statements.
"""

import re
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from rich import box
from rich.table import Table

from edgar.richtools import repr_rich
from edgar.xbrl.dimensions import is_breakdown_dimension
from edgar.xbrl.exceptions import StatementNotFound
from edgar.xbrl.presentation import StatementView, ViewType, normalize_view

# XBRL structural element patterns (Issue #03zg)
# These are XBRL metadata, not financial data, and should be filtered from user-facing output
STRUCTURAL_LABEL_PATTERNS = ['[Axis]', '[Domain]', '[Member]', '[Line Items]', '[Table]', '[Abstract]']
STRUCTURAL_CONCEPT_SUFFIXES = ('Axis', 'Domain', 'Member', 'LineItems', 'Table')


def is_xbrl_structural_element(item: Dict[str, Any]) -> bool:
    """
    Check if an item is an XBRL structural element that should be hidden from user output.

    XBRL structural elements include:
    - Axes: Dimensional axes like ProductOrServiceAxis
    - Domains: Domain members like ProductsAndServicesDomain
    - Tables: Hypercube tables like StatementTable
    - Line Items: Container elements like StatementLineItems
    - Root statement abstracts: Top-level abstract concepts with no proper label
      (e.g., StatementOfFinancialPositionAbstract where label equals concept)

    These are internal XBRL constructs, not actual financial data.

    Issue #03zg: Filter these from to_dataframe() output for cleaner presentation.
    Issue #416h: Filter root statement abstracts from rendered statements.
    """
    label = item.get('label', '')
    concept = item.get('concept', '')

    # Check label for bracket patterns (e.g., "[Axis]", "[Table]")
    if any(pattern in label for pattern in STRUCTURAL_LABEL_PATTERNS):
        return True

    # Check concept name suffix (e.g., "ProductOrServiceAxis", "StatementTable")
    if concept.endswith(STRUCTURAL_CONCEPT_SUFFIXES):
        return True

    # Issue #416h: Filter root statement abstracts where label equals concept
    # These are structural root nodes like "us-gaap_StatementOfFinancialPositionAbstract"
    # that have no proper label assigned. Section headers like "Assets" have proper labels
    # and should be kept.
    if concept.endswith('Abstract') and label == concept:
        return True

    return False


_FINANCIAL_WORDS = [
    # 14-letter words
    'POSTRETIREMENT',
    # 13-letter words
    'COMPREHENSIVE', 'CONTINGENCIES', 'ESTABLISHMENT', 'EXTRAORDINARY', 'RESTRUCTURING',
    'STOCKHOLDERS',
    # 12-letter words
    'ACQUISITIONS', 'ARRANGEMENTS', 'COMPENSATION', 'CONSOLIDATED', 'DIVESTITURES',
    'INSTRUMENTS', 'MEASUREMENTS', 'SHAREHOLDERS', 'SHAREOWNERS',
    # 11-letter words
    'COMMITMENTS', 'INFORMATION', 'INVESTMENTS', 'RECEIVABLES', 'SIGNIFICANT',
    # 10-letter words
    'ACCOUNTING', 'BORROWING', 'DEPRECIATION', 'INTANGIBLE', 'STATEMENTS',
    # 9-letter words
    'DOCUMENT', 'EARNINGS', 'ENTITY', 'EXPENSES', 'FINANCIAL', 'GOODWILL',
    'OPERATING', 'PROVISION', 'REPORTING', 'REVENUES', 'SEGMENTS',
    # 8-letter words
    'ACCRUED', 'BALANCES', 'BUSINESS', 'PAYABLE', 'POLICIES', 'PROPERTY',
    # 7-letter words
    'BALANCE', 'HEDGING', 'REVENUE', 'SUMMARY', 'SUPPLY',
    # 6-letter words
    'ASSETS', 'EQUITY', 'INCOME', 'LEASES', 'SHARES', 'STOCK',
    # 5-letter words
    'BASED', 'CHAIN', 'MONEY', 'OTHER', 'PLANS', 'TAXES', 'VALUE',
    # 4-letter words
    'CASH', 'DEBT', 'FAIR', 'FLOW', 'ITEM', 'LINE', 'LONG', 'LOSS', 'TERM',
    # 3-letter words
    'AND', 'FOR', 'NET', 'NON', 'PER', 'THE',
    # 2-letter words
    'OF',
]


def _split_allcaps(text: str) -> str:
    """
    Split an ALL-CAPS string into title-cased words using a greedy dictionary approach.

    Uses a dictionary of common financial terms to split strings like
    'INCOMETAXES' → 'Income Taxes' and 'DEBTANDBORROWINGARRANGEMENTS' → 'Debt And Borrowing Arrangements'.

    Non-ALL-CAPS strings are returned unchanged.
    """
    if not text or not text.isupper() or len(text) <= 1:
        return text

    remaining = text
    words = []
    while remaining:
        matched = False
        for word in _FINANCIAL_WORDS:
            if remaining.startswith(word):
                words.append(word.title())
                remaining = remaining[len(word):]
                matched = True
                break
        if not matched:
            # Take the next character as its own fragment
            words.append(remaining[0])
            remaining = remaining[1:]

    return ' '.join(words)


def _extract_topic_summary(stmts_in_category: List[Dict], max_shown: int = 4) -> str:
    """
    Extract unique root topic names from a list of statement dicts.

    Identifies root topics by finding definitions that are prefixes of other definitions
    (e.g. 'Debt' is a root because 'DebtTables' and 'DebtDetails' also exist).
    Inserts spaces into CamelCase names for readability.
    """
    defs = [s.get('definition', '') for s in stmts_in_category if s.get('definition')]
    if not defs:
        return ''

    # Find root topics: short definitions that are prefixes of longer ones
    roots = []
    seen = set()
    for d in sorted(defs, key=len):
        if d in seen:
            continue
        is_prefix = any(other.startswith(d) and other != d for other in defs)
        if is_prefix:
            # Skip if already a sub-topic of a found root
            if not any(d.startswith(r) and d != r for r in roots):
                roots.append(d)
                seen.add(d)

    # Fallback: use shortest unique definitions as topics
    if not roots:
        for d in sorted(defs, key=len):
            if d not in seen:
                roots.append(d)
                seen.add(d)
            if len(roots) >= max_shown:
                break

    # Insert spaces for readability (ALL-CAPS or CamelCase)
    result = []
    for r in roots:
        if r.isupper() and len(r) > 1:
            spaced = _split_allcaps(r)
        else:
            spaced = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', r)
            spaced = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', spaced)
            # Fix common lowercase joiners: "Summaryof" -> "Summary of"
            spaced = re.sub(r'(?<=[a-z])(of|and|for|to|the|in|by|or|on)(?=[A-Z ])', r' \1 ', spaced)
            # Collapse any double spaces
            spaced = re.sub(r'  +', ' ', spaced)
        result.append(spaced.strip())

    shown = result[:max_shown]
    extra = len(result) - max_shown
    line = ', '.join(shown)
    if extra > 0:
        line += f', +{extra} more topics'
    return line


@dataclass
class StatementInfo:
    name: str
    concept: str
    title: str


statement_to_concepts = {
    "IncomeStatement": StatementInfo(name="IncomeStatement",
                                     concept="us-gaap_IncomeStatementAbstract",
                                     title="Consolidated Statement of Income"),
    "BalanceSheet": StatementInfo(name="BalanceSheet",
                                  concept="us-gaap_StatementOfFinancialPositionAbstract",
                                  title="Consolidated Balance Sheets",
                                  ),
    "CashFlowStatement": StatementInfo(name="CashFlowStatement",
                                       concept="us-gaap_StatementOfCashFlowsAbstract",
                                       title="Consolidated Statement of Cash Flows"),
    "StatementOfEquity": StatementInfo(name="StatementOfEquity",
                                       concept="us-gaap_StatementOfStockholdersEquityAbstract",
                                       title="Consolidated Statement of Equity"
                                       ),
    "ComprehensiveIncome": StatementInfo(name="ComprehensiveIncome",
                                         concept="us-gaap_StatementOfIncomeAndComprehensiveIncomeAbstract",
                                         title="Consolidated Statement of Comprehensive Income"
                                         ),
    "CoverPage": StatementInfo(name="CoverPage",
                               concept="dei_CoverAbstract",
                                 title="Cover Page"
                                 ),
    # Fund-specific statements (for BDCs, closed-end funds, investment companies)
    "ScheduleOfInvestments": StatementInfo(name="ScheduleOfInvestments",
                                           concept="us-gaap_ScheduleOfInvestmentsAbstract",
                                           title="Consolidated Schedule of Investments"
                                           ),
    "FinancialHighlights": StatementInfo(name="FinancialHighlights",
                                         concept="us-gaap_InvestmentCompanyFinancialHighlightsAbstract",
                                         title="Financial Highlights"
                                         ),
}


class StatementValidationError(Exception):
    """Raised when statement validation fails."""
    pass


class Statement:
    """
    A single financial statement extracted from XBRL data.

    This class provides convenient methods for rendering and manipulating a specific
    financial statement. It includes validation, normalization, and analysis capabilities.

    Features:
    - Statement structure validation
    - Error handling for missing/malformed data
    - Statement normalization across different companies
    - Common financial analysis methods
    - Ratio calculations and trend analysis
    """

    # Required concepts for each statement type
    REQUIRED_CONCEPTS = {
        'BalanceSheet': [
            'us-gaap_Assets',
            'us-gaap_Liabilities',
            'us-gaap_StockholdersEquity'
        ],
        'IncomeStatement': [
            'us-gaap_Revenues',
            'us-gaap_NetIncomeLoss'
        ],
        'CashFlowStatement': [
            'us-gaap_CashAndCashEquivalentsPeriodIncreaseDecrease',
            'us-gaap_CashAndCashEquivalentsAtCarryingValue'
        ]
    }

    def __init__(self, xbrl, role_or_type: str, canonical_type: Optional[str] = None,
               skip_concept_check: bool = False, include_dimensions: bool = False,
               view: ViewType = None):
        """
        Initialize with an XBRL object and statement identifier.

        Args:
            xbrl: XBRL object containing parsed data
            role_or_type: Role URI, statement type, or statement short name
            canonical_type: Optional canonical statement type (e.g., "BalanceSheet", "IncomeStatement")
                         If provided, this type will be used for specialized processing logic
            skip_concept_check: If True, skip checking for required concepts (useful for testing)
            include_dimensions: Deprecated. Use view parameter instead.
                              Default setting for whether to include dimensional segment data
                              when rendering or converting to DataFrame (default: False)
            view: StatementView controlling dimensional data display.
                  STANDARD: Face presentation matching SEC Viewer (display default)
                  DETAILED: All dimensional data included (to_dataframe default)
                  SUMMARY: Non-dimensional totals only

        Raises:
            StatementValidationError: If statement validation fails
        """
        self.xbrl = xbrl
        self.role_or_type = role_or_type
        self.canonical_type = canonical_type
        # Store both for backward compatibility during transition
        self._include_dimensions = include_dimensions
        self._view = normalize_view(view) if view is not None else None

    def is_segmented(self) -> bool:
        """
        Check if the statement is a segmented statement.

        Returns:
            True if the statement is segmented, False otherwise
        """
        return self.role_or_type.startswith("Segment")

    def render(self, period_filter: Optional[str] = None,
               period_view: Optional[str] = None,
               standard: bool = True,
               show_date_range: bool = False,
               view: ViewType = None,
               include_dimensions: Optional[bool] = None) -> Any:
        """
        Render the statement as a formatted table.

        Args:
            period_filter: Optional period key to filter facts
            period_view: Optional name of a predefined period view
            standard: Whether to use standardized concept labels
            show_date_range: Whether to show full date ranges for duration periods
            view: StatementView controlling dimensional data display.
                  STANDARD: Face presentation only (default for display)
                  DETAILED: All dimensional data included
                  SUMMARY: Non-dimensional totals only
            include_dimensions: Deprecated. Use view='standard'|'detailed'|'summary' instead.

        Returns:
            Rich Table containing the rendered statement
        """
        # Handle deprecated include_dimensions parameter
        if include_dimensions is not None:
            if view is not None:
                raise ValueError(
                    "Cannot specify both 'view' and 'include_dimensions'. "
                    "Use 'view' only (include_dimensions is deprecated)."
                )
            warnings.warn(
                "include_dimensions is deprecated and will be removed in v6.0. "
                "Use view='standard', 'detailed', or 'summary' instead.",
                DeprecationWarning,
                stacklevel=2
            )
            view = StatementView.DETAILED if include_dimensions else StatementView.STANDARD

        # Determine effective view - default to STANDARD for rendering (clean display)
        if view is not None:
            effective_view = normalize_view(view)
        elif self._view is not None:
            effective_view = self._view
        else:
            # Default to STANDARD for render (clean display matching SEC Viewer)
            effective_view = StatementView.STANDARD

        # Convert view to include_dimensions for render_statement:
        # - DETAILED: include_dimensions=True (show all dimensions)
        # - STANDARD: include_dimensions=False (filter breakdown dimensions)
        # - SUMMARY: include_dimensions=False (filter all dimensions - handled separately)
        effective_include_dimensions = effective_view == StatementView.DETAILED

        # Use the canonical type for rendering if available, otherwise use the role
        rendering_type = self.canonical_type if self.canonical_type else self.role_or_type

        return self.xbrl.render_statement(rendering_type,
                                          period_filter=period_filter,
                                          period_view=period_view,
                                          standard=standard,
                                          show_date_range=show_date_range,
                                          include_dimensions=effective_include_dimensions,
                                          view=effective_view)

    def __rich__(self) -> Any:
        """
        Rich console representation.

        Returns:
            Rich Table object if rich is available, else string representation
        """
        if Table is None:
            return str(self)

        # Matrix rendering for equity statements is opt-in via to_dataframe(matrix=True)
        # Automatic detection deferred to future release (Issue edgartools-uqg7)
        return self.render()

    def _is_matrix_statement(self) -> bool:
        """
        Check if this statement should be rendered as a matrix.

        Returns True for Statement of Equity with StatementEquityComponentsAxis
        that has detailed equity component members (not just aggregates).

        Matrix format requires detailed components like:
        - Common Stock / Additional Paid-in Capital
        - Retained Earnings
        - Accumulated Other Comprehensive Income/Loss
        - Treasury Stock

        If the axis only has aggregates (Total Stockholders' Equity, Noncontrolling Interests),
        the statement should be rendered as a list, not a matrix.
        """
        # Check if this is an equity statement by canonical type OR role URI
        statement_type = self.canonical_type if self.canonical_type else ''
        role_lower = self.role_or_type.lower() if self.role_or_type else ''

        is_equity_by_type = statement_type in (
            'StatementOfEquity', 'StatementOfStockholdersEquity',
            'StatementOfChangesInEquity'
        )
        is_equity_by_role = (
            ('equity' in role_lower or 'stockholder' in role_lower) and
            'parenthetical' not in role_lower and
            'disclosure' not in role_lower
        )

        if not (is_equity_by_type or is_equity_by_role):
            return False

        # Collect equity component member labels from DataFrame
        # DataFrame has more complete dimension info than raw_data's dimension_metadata
        try:
            df = self.to_dataframe()
            equity_axis_rows = df[
                df['dimension_axis'].fillna('').str.contains('StatementEquityComponentsAxis', case=False)
            ]
            equity_members = set(
                equity_axis_rows['dimension_member_label'].dropna().str.lower().unique()
            )
        except Exception:
            # Fallback to raw data if DataFrame fails
            raw_data = self.get_raw_data()
            equity_members = set()
            for item in raw_data:
                dim_meta = item.get('dimension_metadata', [])
                for dm in dim_meta:
                    if 'StatementEquityComponentsAxis' in dm.get('dimension', ''):
                        member_label = dm.get('member_label', '').lower()
                        equity_members.add(member_label)

        if not equity_members:
            return False

        # PRIMARY equity components that form matrix columns
        # These are the standard equity buckets that fit in a matrix format
        primary_component_patterns = [
            'common stock',
            'paid-in capital',
            'paid in capital',
            'apic',
            'retained earnings',
            'accumulated deficit',
            'accumulated other comprehensive',  # AOCI as single column
            'aoci',
            'treasury stock',
            'preferred stock',
            'noncontrolling interest',
            'non-controlling interest',
        ]

        # Sub-component patterns that indicate AOCI breakdown or other detailed views
        # If these exist as separate members, the company uses list format
        sub_component_patterns = [
            'unrealized gain',
            'unrealized loss',
            'translation adjustment',
            'foreign currency',
            'fair value hedge',
            'cash flow hedge',
            'pension',
            'opeb',
            'dva on fair value',
            'defined benefit',
        ]

        # Aggregate patterns that should NOT count as components
        aggregate_patterns = [
            'total stockholders',
            'total equity',
            'parent company',
            'redeemable',
            'adjustment',
        ]

        # Count primary components and sub-component breakdowns
        primary_components = set()
        sub_component_count = 0

        for member in equity_members:
            # Skip aggregates
            if any(agg in member for agg in aggregate_patterns):
                continue

            # Check if this is a sub-component breakdown (e.g., AOCI details)
            if any(sub in member for sub in sub_component_patterns):
                sub_component_count += 1
                continue

            # Check if this is a primary component
            for pattern in primary_component_patterns:
                if pattern in member:
                    primary_components.add(pattern)
                    break

        # Matrix format requires:
        # 1. At least 2 primary components
        # 2. No more than 7 primary components (otherwise too wide)
        # 3. Few AOCI sub-component breakdowns (<=3 can be aggregated, >3 needs list format)
        #    - GOOGL has 3 sub-components, uses matrix in SEC
        #    - JPM has 6 sub-components, uses list format in SEC
        has_enough_components = len(primary_components) >= 2
        not_too_many = len(primary_components) <= 7
        few_sub_components = sub_component_count <= 3

        return has_enough_components and not_too_many and few_sub_components

    def _render_matrix(self) -> Table:
        """
        Render Statement of Equity as a matrix table.

        Uses the matrix DataFrame to create a Rich table with equity components
        as columns and activities as rows.
        """
        from edgar.display import get_statement_styles
        from rich.text import Text

        # Get matrix DataFrame
        df = self.to_dataframe(matrix=True)
        if df is None or df.empty:
            return self.render()  # Fall back to standard rendering

        styles = get_statement_styles()

        # Build title with units note
        title = self.title if hasattr(self, 'title') else "Statement of Stockholders' Equity"
        title_parts = [f"[bold]{title}[/bold]", f"[{styles['metadata']['units']}](in millions)[/{styles['metadata']['units']}]"]
        full_title = "\n".join(title_parts)

        table = Table(title=full_title, box=box.SIMPLE, border_style=styles['structure']['border'])

        # Add label column (wider for activity names)
        table.add_column("", justify="left", min_width=30)

        # Get equity component columns (exclude metadata columns)
        metadata_cols = {'concept', 'label', 'level', 'abstract'}
        value_cols = [c for c in df.columns if c not in metadata_cols]

        # Abbreviate column headers for readability
        def abbreviate_member(member: str) -> str:
            """Abbreviate long equity component names for column headers."""
            member_lower = member.lower()

            # Common stock variants (with or without APIC)
            if 'common stock' in member_lower and 'paid-in capital' in member_lower:
                return 'Common\n& APIC'
            if 'common stock' in member_lower:
                return 'Common\nStock'
            if 'paid-in capital' in member_lower or 'paid in capital' in member_lower:
                return 'APIC'

            # Retained earnings / Accumulated income
            if 'retained earnings' in member_lower or 'accumulated deficit' in member_lower:
                return 'Retained\nEarnings'
            if 'accumulated income' in member_lower and 'comprehensive' not in member_lower:
                return 'Accum\nIncome'

            # AOCI
            if 'accumulated other comprehensive' in member_lower or 'aoci' in member_lower:
                return 'AOCI'

            # Treasury stock
            if 'treasury' in member_lower:
                return 'Treasury\nStock'

            # Noncontrolling interests
            if 'noncontrolling' in member_lower or 'non-controlling' in member_lower:
                return 'NCI'

            # Total
            if 'total stockholders' in member_lower or 'total equity' in member_lower:
                return 'Total\nEquity'

            # Preferred stock
            if 'preferred' in member_lower:
                return 'Preferred\nStock'

            # Right to recover (VISA specific)
            if 'right to recover' in member_lower:
                return 'Right to\nRecover'

            # Truncate unknown - use two lines if long
            if len(member) > 15:
                words = member.split()
                if len(words) >= 2:
                    mid = len(words) // 2
                    return ' '.join(words[:mid]) + '\n' + ' '.join(words[mid:])
            return member[:12] + '...' if len(member) > 12 else member

        # Add equity component columns with abbreviated headers
        # Columns are now just component names (no period suffix)
        for col in value_cols:
            header = abbreviate_member(col)
            table.add_column(header, justify="right", no_wrap=True)

        # Add rows
        for _, row in df.iterrows():
            label = row['label']
            level = row.get('level', 0)
            is_abstract = row.get('abstract', False)

            # Format label based on level using semantic styles
            indent = "  " * level

            if is_abstract:
                if level == 0:
                    label_text = label.upper()
                    style = styles['row']['abstract']  # cyan bold
                else:
                    label_text = f"{indent}{label}"
                    style = styles['header']['section']
            else:
                label_text = f"{indent}{label}"
                style = styles['row']['item']

            styled_label = Text(label_text, style=style) if style else Text(label_text)

            # Format cell values (scale to millions)
            cell_values = []
            for col in value_cols:
                value = row.get(col)
                if value is None or pd.isna(value):
                    cell_values.append(Text("—", justify="right", style=styles['value']['empty']))
                else:
                    try:
                        num_value = float(value) / 1_000_000  # Convert to millions
                        if abs(num_value) < 0.5:
                            # Very small values show as dash
                            cell_values.append(Text("—", justify="right", style=styles['value']['empty']))
                        elif num_value < 0:
                            formatted = f"({abs(num_value):,.0f})"
                            cell_values.append(Text(formatted, style=styles['value']['negative'], justify="right"))
                        else:
                            formatted = f"{num_value:,.0f}"
                            cell_values.append(Text(formatted, style=styles['value']['default'], justify="right"))
                    except (ValueError, TypeError):
                        cell_values.append(Text(str(value), justify="right"))

            table.add_row(styled_label, *cell_values)

        return table

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        """String representation using improved rendering with proper width."""
        # Matrix rendering is opt-in via to_dataframe(matrix=True)
        rendered_statement = self.render()
        return str(rendered_statement)  # Delegates to RenderedStatement.__str__()

    @property
    def docs(self):
        """
        Get comprehensive documentation for the Statement class.

        Returns a Docs object with detailed API documentation including usage patterns,
        examples, and guidance for working with financial statement data. The documentation
        is searchable using the .search() method.

        Returns:
            Docs: Documentation object with rich display and search capabilities

        Example:
            >>> statement.docs  # Display full documentation
            >>> statement.docs.search("convert to dataframe")  # Search for specific topics
        """
        from edgar.richtools import Docs
        return Docs(self)

    @property
    def primary_concept(self):
        data = self.get_raw_data()
        return data[0]['all_names'][0]

    def to_dataframe(self,
                     period_filter: Optional[str] = None,
                     period_view: Optional[str] = None,
                     standard: bool = True,
                     view: ViewType = None,
                     include_dimensions: Optional[bool] = None,
                     include_unit: bool = False,
                     include_point_in_time: bool = False,
                     include_standardization: bool = False,
                     presentation: bool = False,
                     matrix: bool = False) -> Any:
        """Convert statement to pandas DataFrame.

        Args:
            period_filter: Optional period key to filter facts
            period_view: Optional name of a predefined period view
            standard: Whether to use standardized concept labels
            view: StatementView controlling dimensional data display.
                  STANDARD: Face presentation only (Products/Services)
                  DETAILED: All dimensional data (iPhone, iPad, Mac, etc.) - DEFAULT
                  SUMMARY: Non-dimensional totals only
                  If None, defaults to DETAILED for complete data extraction.
            include_dimensions: Deprecated. Use view='standard'|'detailed'|'summary' instead.
                              If specified, emits DeprecationWarning.
            include_unit: If True, add a 'unit' column with unit information (e.g., 'usd', 'shares', 'usdPerShare')
            include_point_in_time: If True, add a 'point_in_time' boolean column (True for 'instant', False for 'duration')
            include_standardization: If True, add a 'standard_concept' column showing
                                    the mapped standard concept identifier (e.g., "CommonEquity").
                                    This is useful for cross-company analysis and filtering.
                                    Note: The 'standard_concept' column is always available in
                                    the DataFrame when standard=True; this parameter is deprecated.
            presentation: If True, apply HTML-matching presentation logic (Issue #463)
                         Cash Flow: outflows (balance='credit') shown as negative
                         Income: apply preferred_sign transformations
                         Default: False (raw instance values)
            matrix: If True, return matrix format for Statement of Equity (equity components
                   as columns, activities as rows). Ignored for non-equity statements.
                   Default: False (standard flat format for backwards compatibility).

        Returns:
            DataFrame with raw values + metadata (balance, weight, preferred_sign) by default.
            If matrix=True and this is a Statement of Equity, returns pivoted matrix format.

        Examples:
            >>> # Default: DETAILED view for complete data
            >>> df = statement.to_dataframe()
            >>>
            >>> # Explicit view control
            >>> df = statement.to_dataframe(view='standard')  # Clean, SEC Viewer style
            >>> df = statement.to_dataframe(view='detailed')  # All dimensional data
            >>> df = statement.to_dataframe(view='summary')   # Non-dimensional only
            >>>
            >>> # Matrix format for Statement of Equity
            >>> equity_df = equity_statement.to_dataframe(matrix=True)
        """
        # Handle deprecated include_dimensions parameter
        if include_dimensions is not None:
            if view is not None:
                raise ValueError(
                    "Cannot specify both 'view' and 'include_dimensions'. "
                    "Use 'view' only (include_dimensions is deprecated)."
                )
            warnings.warn(
                "include_dimensions is deprecated and will be removed in v6.0. "
                "Use view='standard', 'detailed', or 'summary' instead. "
                "include_dimensions=True maps to view='detailed', "
                "include_dimensions=False maps to view='standard'.",
                DeprecationWarning,
                stacklevel=2
            )
            # Map deprecated parameter to view
            view = StatementView.DETAILED if include_dimensions else StatementView.STANDARD

        # Determine effective view
        if view is not None:
            effective_view = normalize_view(view)
        elif self._view is not None:
            # Use instance default view if set
            effective_view = self._view
        else:
            # Default to DETAILED for to_dataframe (complete data for analysis)
            effective_view = StatementView.DETAILED

        # Convert view to include_dimensions for backward compatibility with internal methods
        # DETAILED and STANDARD both show dimensions, SUMMARY hides all
        effective_include_dimensions = effective_view != StatementView.SUMMARY

        try:
            # Build DataFrame from raw data (Issue #463)
            df = self._build_dataframe_from_raw_data(
                period_filter=period_filter,
                period_view=period_view,
                standard=standard,
                include_dimensions=effective_include_dimensions,
                include_unit=include_unit,
                include_point_in_time=include_point_in_time,
                include_standardization=include_standardization,
                view=effective_view
            )

            if df is None or isinstance(df, str) or df.empty:
                return df

            # Add metadata columns (balance, weight, preferred_sign) - Issue #463
            df = self._add_metadata_columns(df)

            # Apply presentation transformation if requested (Issue #463)
            if presentation:
                df = self._apply_presentation(df)

            # Apply matrix transformation for equity statements (Issue edgartools-uqg7)
            if matrix:
                df = self._pivot_to_matrix(df)

            return df

        except ImportError:
            return "Pandas is required for DataFrame conversion"

    def _build_dataframe_from_raw_data(
        self,
        period_filter: Optional[str] = None,
        period_view: Optional[str] = None,
        standard: bool = True,
        include_dimensions: bool = False,
        include_unit: bool = False,
        include_point_in_time: bool = False,
        include_standardization: bool = False,
        view: StatementView = StatementView.DETAILED
    ) -> pd.DataFrame:
        """
        Build DataFrame directly from raw statement data (Issue #463).

        This bypasses the rendering pipeline to get raw instance values.

        Args:
            view: StatementView controlling which dimensional data to include.
                  Used for STANDARD vs DETAILED filtering logic.
        """
        from edgar.xbrl.core import get_unit_display_name
        from edgar.xbrl.core import is_point_in_time as get_is_point_in_time
        from edgar.xbrl.periods import determine_periods_to_display

        # Get raw statement data with view-based filtering
        raw_data = self.get_raw_data(period_filter=period_filter, view=view)
        if not raw_data:
            return pd.DataFrame()

        # Determine which periods to display
        statement_type = self.canonical_type if self.canonical_type else self.role_or_type

        # Issue #583: Apply label standardization if requested
        # This transforms labels like "Ending balances" → "Total Stockholders' Equity"
        if standard:
            # Use XBRL instance's standardization cache (disable statement caching since
            # raw_data varies by view/period_filter parameters)
            raw_data = self.xbrl.standardization.standardize_statement_data(
                raw_data, statement_type, use_cache=False
            )

        # Determine which periods to display
        # determine_periods_to_display handles:
        # - period_filter: return only the specific period requested
        # - period_view: use predefined view names
        # - fallback: smart period selection when neither is specified
        periods_to_display = determine_periods_to_display(
            self.xbrl, statement_type,
            period_filter=period_filter,
            period_view=period_view
        )

        if not periods_to_display:
            return pd.DataFrame()

        # Build DataFrame rows
        df_rows = []

        # Issue #572: Track concept occurrences for Statement of Equity roll-forward logic
        # First occurrence = beginning balance, later occurrences = ending balance
        is_equity_statement = statement_type in (
            'StatementOfEquity', 'StatementOfStockholdersEquity',
            'StatementOfChangesInEquity', 'ComprehensiveIncome',
            'StatementOfComprehensiveIncome'
        )
        # Issue #583: Track by (concept, label) tuple to handle dimensional items correctly
        # Different dimensional items have same concept but different labels
        item_occurrence_count = {}  # Tracks total occurrences of each (concept, label) pair
        item_current_index = {}     # Tracks current occurrence during iteration

        # First pass: count total occurrences of each (concept, label) pair (needed for beginning/ending logic)
        if is_equity_statement:
            for item in raw_data:
                if is_xbrl_structural_element(item):
                    continue
                # SUMMARY view: skip ALL dimensional items
                if view == StatementView.SUMMARY and item.get('is_dimension'):
                    continue
                # STANDARD view: skip only breakdown dimensions
                if view == StatementView.STANDARD and item.get('is_dimension'):
                    if is_breakdown_dimension(item, statement_type=self.canonical_type,
                                              xbrl=self.xbrl, role_uri=self.role_or_type):
                        continue
                concept = item.get('concept', '')
                label = item.get('label', '')
                item_key = (concept, label)
                item_occurrence_count[item_key] = item_occurrence_count.get(item_key, 0) + 1

        for item in raw_data:
            # Issue #03zg: Skip XBRL structural elements (Axis, Domain, Table, Line Items)
            # These are internal XBRL constructs, not financial data
            if is_xbrl_structural_element(item):
                continue

            # StatementView filtering:
            # - SUMMARY: Skip ALL dimensional items (non-dimensional totals only)
            # - STANDARD: Skip breakdown dimensions, keep face-level (PPE type, equity components)
            # - DETAILED: Keep all dimensional items
            if item.get('is_dimension'):
                if view == StatementView.SUMMARY:
                    # SUMMARY view: hide all dimensional rows
                    continue
                elif view == StatementView.STANDARD:
                    # STANDARD view: hide only breakdown dimensions (geographic, segment, acquisition)
                    # Keep classification dimensions (PPE type, equity) on face
                    if is_breakdown_dimension(item, statement_type=self.canonical_type,
                                              xbrl=self.xbrl, role_uri=self.role_or_type):
                        continue
                # DETAILED view: keep all dimensional items (no filtering)

            # Issue #572: Track concept occurrence for roll-forward logic
            concept = item.get('concept', '')
            # Get base label
            base_label = item.get('label', '')

            # Issue #583: Track by (concept, label) for proper beginning/ending suffix
            if is_equity_statement:
                item_key = (concept, base_label)
                item_current_index[item_key] = item_current_index.get(item_key, 0) + 1

            # Issue #583: For Statement of Equity, add "Beginning balance" / "Ending balance"
            # to labels when (concept, label) pair appears multiple times
            # This handles dimensional items correctly - each unique label gets its own tracking
            label = base_label
            if is_equity_statement and concept:
                item_key = (concept, base_label)
                total_occurrences = item_occurrence_count.get(item_key, 1)
                current_occurrence = item_current_index.get(item_key, 1)

                if total_occurrences > 1:
                    if current_occurrence == 1:
                        label = f"{base_label} - Beginning balance"
                    elif current_occurrence == total_occurrences:
                        label = f"{base_label} - Ending balance"

            # Build base row
            row = {
                'concept': concept,
                'label': label,
                'standard_concept': item.get('standard_concept')  # Standard concept identifier for analysis
            }

            # Add period values (raw from instance document)
            values_dict = item.get('values', {})
            for period_key, period_label in periods_to_display:
                # Use end date as column name (more concise than full label)
                # Extract date from period_key (e.g., "duration_2016-09-25_2017-09-30" → "2017-09-30")
                start_date = None
                end_date = None
                if '_' in period_key:
                    parts = period_key.split('_')
                    if len(parts) >= 3:
                        # Duration period: duration_START_END
                        start_date = parts[1]
                        end_date = parts[2]
                        column_name = end_date
                    elif len(parts) == 2:
                        # Instant period: instant_DATE
                        end_date = parts[1]
                        column_name = end_date
                    else:
                        column_name = period_label
                else:
                    column_name = period_label

                # Use raw value from instance document
                value = values_dict.get(period_key)

                # Issue #572/#583: For Statement of Equity, match instant facts when duration key is empty
                # This mirrors the logic in rendering.py (Issue #450) for consistent DataFrame output
                # Roll-forward structure: first occurrence = beginning balance, later = ending balance
                # Issue #583: Use (concept, label) tracking for proper beginning/ending logic with dimensions
                if value is None and is_equity_statement:
                    item_key = (concept, base_label)
                    total_occurrences = item_occurrence_count.get(item_key, 1)
                    current_occurrence = item_current_index.get(item_key, 1)
                    is_first_occurrence = current_occurrence == 1

                    if is_first_occurrence and total_occurrences > 1 and start_date:
                        # Beginning balance: try instant at day before start_date
                        try:
                            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                            beginning_date = (start_dt - timedelta(days=1)).strftime('%Y-%m-%d')
                            instant_key = f"instant_{beginning_date}"
                            value = values_dict.get(instant_key)
                        except (ValueError, AttributeError):
                            pass  # Fall through to try end_date

                    # If still no value, try instant at end_date (ending balances and most facts)
                    if value is None and end_date:
                        instant_key = f"instant_{end_date}"
                        value = values_dict.get(instant_key)

                # General fallback: handle period type mismatch for disclosure notes (#635)
                # Notes/disclosures default to duration period selection, but balance-sheet-type
                # notes (PPE, Accrued Liabilities) have instant facts.
                # Try the instant key at the duration's end date.
                if value is None and period_key.startswith('duration_') and end_date:
                    instant_key = f"instant_{end_date}"
                    value = values_dict.get(instant_key)

                # Issue #582: Don't overwrite a valid value with None
                # Multiple periods can map to the same column (e.g., transition periods for
                # accounting standard changes). If we already have a value, don't overwrite with None.
                if value is not None or column_name not in row:
                    row[column_name] = value

            # Add unit if requested
            if include_unit:
                units_dict = item.get('units', {})
                # Get first available unit (should be same for all periods)
                unit_ref = None
                for period_key, _ in periods_to_display:
                    if period_key in units_dict and units_dict[period_key] is not None:
                        unit_ref = units_dict[period_key]
                        break
                row['unit'] = get_unit_display_name(unit_ref)

            # Add point_in_time if requested
            if include_point_in_time:
                period_types_dict = item.get('period_types', {})
                # Get first available period type
                period_type = None
                for period_key, _ in periods_to_display:
                    if period_key in period_types_dict and period_types_dict[period_key] is not None:
                        period_type = period_types_dict[period_key]
                        break
                row['point_in_time'] = get_is_point_in_time(period_type)

            # Add structural columns
            row['level'] = item.get('level', 0)
            row['abstract'] = item.get('is_abstract', False)
            row['dimension'] = item.get('is_dimension', False)
            # Issue #569: Add is_breakdown to distinguish breakdown vs face dimensions
            # Issue #577/cf9o: Pass xbrl and role_uri for definition linkbase-based filtering
            row['is_breakdown'] = is_breakdown_dimension(
                item, statement_type=self.canonical_type,
                xbrl=self.xbrl, role_uri=self.role_or_type
            ) if item.get('is_dimension') else False

            # Issue #574: Add structured dimension fields (axis, member, member_label)
            # dimension_metadata is a list of dicts with 'dimension', 'member', 'member_label' keys
            # Issue #603: Use PRIMARY (first) dimension consistently for all fields
            if item.get('is_dimension', False):
                dim_metadata = item.get('dimension_metadata', [])
                if dim_metadata:
                    # Use first dimension for axis/member/member_label (primary grouping)
                    # The first dimension is the primary breakdown axis (e.g., ProductOrServiceAxis)
                    primary_dim = dim_metadata[0]
                    row['dimension_axis'] = primary_dim.get('dimension', '')
                    row['dimension_member'] = primary_dim.get('member', '')
                    # Issue #603: Use PRIMARY dimension's member_label for consistency
                    # e.g., for GOOGL "YouTube ads" should show "YouTube ads", not "Google Services"
                    row['dimension_member_label'] = primary_dim.get('member_label', '')
                else:
                    row['dimension_axis'] = None
                    row['dimension_member'] = None
                    row['dimension_member_label'] = None
                # Preserve original dimension_label for backwards compatibility (Issue #522)
                row['dimension_label'] = item.get('full_dimension_label', '')
            else:
                row['dimension_axis'] = None
                row['dimension_member'] = None
                row['dimension_member_label'] = None
                row['dimension_label'] = None

            # Note: include_standardization parameter is deprecated.
            # The 'standard_concept' column is now always included when standard=True.
            # It contains the concept identifier (e.g., "CommonEquity") for cross-company analysis.

            df_rows.append(row)

        return pd.DataFrame(df_rows)

    def _to_df(self,
               columns: Optional[List[str]] = None,
               max_rows: Optional[int] = None,
               show_concept: bool = True,
               show_standard_concept: bool = True,
               **kwargs) -> 'pd.DataFrame':
        """
        Debug helper: Get a nicely formatted DataFrame for easy viewing.

        Formats numbers with commas, shows all columns/rows, and optionally
        filters to specific columns for cleaner output.

        Args:
            columns: Specific columns to include (default: label, standard_concept, period columns)
            max_rows: Limit number of rows displayed (default: all)
            show_concept: Include 'concept' column (default: True)
            show_standard_concept: Include 'standard_concept' column (default: True)
            **kwargs: Passed to to_dataframe()

        Returns:
            Formatted DataFrame ready for display

        Example:
            >>> bs = xbrl.statements.balance_sheet()
            >>> bs._to_df()  # Shows label, standard_concept, and period values
            >>> bs._to_df(columns=['label', '2024-09-30'])  # Specific columns
            >>> bs._to_df(max_rows=20)  # First 20 rows
        """
        import pandas as pd

        # Get the DataFrame
        df = self.to_dataframe(**kwargs)

        if df.empty:
            return df

        # Identify period columns (date-like columns)
        period_cols = [c for c in df.columns if '-' in str(c) and len(str(c)) == 10]

        # Default columns: label, optional concept/standard_concept, then periods
        if columns is None:
            columns = ['label']
            if show_concept and 'concept' in df.columns:
                columns.append('concept')
            if show_standard_concept and 'standard_concept' in df.columns:
                columns.append('standard_concept')
            columns.extend(period_cols)

        # Filter to requested columns (keep only those that exist)
        available_cols = [c for c in columns if c in df.columns]
        df = df[available_cols]

        # Limit rows if requested
        if max_rows is not None:
            df = df.head(max_rows)

        # Format numeric columns with commas and no decimals for large numbers
        def format_number(x):
            if pd.isna(x):
                return ''
            if isinstance(x, (int, float)):
                if abs(x) >= 1000:
                    return f'{x:,.0f}'
                elif x == 0:
                    return '0'
                else:
                    return f'{x:,.2f}'
            return x

        # Apply formatting to period columns
        for col in period_cols:
            if col in df.columns:
                df[col] = df[col].apply(format_number)

        # Set pandas display options for this DataFrame
        with pd.option_context(
            'display.max_rows', None,
            'display.max_columns', None,
            'display.width', None,
            'display.max_colwidth', 60
        ):
            # Return DataFrame with nice __repr__
            return df

    def _add_metadata_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add metadata columns (balance, weight, preferred_sign, parent_concept, parent_abstract_concept) to DataFrame.

        Issue #463: Users need access to XBRL metadata to understand value transformations.
        Issue #514: Users need parent_concept to understand hierarchy relationships.
        Issue #514 refinement: Distinguish between calculation parent (metric) and presentation parent (abstract).

        Note: preferred_sign comes from statement's raw data (presentation linkbase),
        not from facts. It's period-specific in raw data, but we use a representative
        value (from first period) for the metadata column.

        Parent concepts:
        - parent_concept: Calculation tree parent (always a metric concept for summation math)
        - parent_abstract_concept: Presentation tree parent (may be abstract, for display hierarchy)
        """
        if df.empty or 'concept' not in df.columns:
            return df

        # Get statement's raw data to access preferred_signs and parent
        raw_data = self.get_raw_data()
        # Build concept lookup using first occurrence to preserve parent info (Issue #542)
        # Same concept may appear multiple times due to dimensional data (Products, Services, regions)
        # First occurrence (main line item) has parent info; later dimensional occurrences may not
        raw_data_by_concept = {}
        for item in raw_data:
            concept = item.get('concept')
            if concept and concept not in raw_data_by_concept:
                raw_data_by_concept[concept] = item

        # Create metadata dictionaries to populate
        balance_map = {}
        weight_map = {}
        preferred_sign_map = {}
        parent_concept_map = {}  # Calculation tree parent (metric)
        parent_abstract_concept_map = {}  # Presentation tree parent (may be abstract)

        # For each unique concept in the DataFrame
        for concept in df['concept'].unique():
            if not concept:
                continue

            # Get balance and weight from facts (concept-level attributes)
            facts_df = self.xbrl.facts.query().by_concept(concept, exact=True).limit(1).to_dataframe()

            if not facts_df.empty:
                fact = facts_df.iloc[0]
                balance_map[concept] = fact.get('balance')
                weight_map[concept] = fact.get('weight')

            # Get preferred_sign and parent from statement raw data (presentation linkbase)
            if concept in raw_data_by_concept:
                item = raw_data_by_concept[concept]

                # preferred_sign is period-specific, so we take the first available value
                preferred_signs = item.get('preferred_signs', {})
                if preferred_signs:
                    # Use first period's preferred_sign as representative value
                    preferred_sign_map[concept] = next(iter(preferred_signs.values()))

                # parent_concept from calculation tree (Issue #514 refinement) - metric parent for math
                parent_concept_map[concept] = item.get('calculation_parent')

                # parent_abstract_concept from presentation tree (Issue #514) - may be abstract, for display
                parent_abstract_concept_map[concept] = item.get('parent')

        # Add metadata columns
        df['balance'] = df['concept'].map(balance_map)
        df['weight'] = df['concept'].map(weight_map)
        df['preferred_sign'] = df['concept'].map(preferred_sign_map)
        df['parent_concept'] = df['concept'].map(parent_concept_map)
        df['parent_abstract_concept'] = df['concept'].map(parent_abstract_concept_map)

        return df

    def _apply_presentation(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply presentation logic to match SEC HTML display.

        Issue #463: Transform values to match how they appear in official SEC filings.
        Uses preferred_sign from presentation linkbase (not balance attribute).
        - preferred_sign = -1: negate for display (expenses, dividends, outflows)
        - preferred_sign = 1: show as-is
        - preferred_sign = None: no transformation
        """
        if df.empty:
            return df

        result = df.copy()

        # Get period columns (exclude metadata and structural columns)
        # FIX (Issue #599): Include all metadata columns to prevent processing non-date columns
        metadata_cols = ['concept', 'label', 'balance', 'weight', 'preferred_sign', 'parent_concept',
                        'parent_abstract_concept', 'level', 'abstract', 'dimension', 'unit', 'point_in_time',
                        'standard_concept', 'is_breakdown', 'dimension_axis', 'dimension_member',
                        'dimension_member_label', 'dimension_label']
        period_cols = [col for col in df.columns if col not in metadata_cols]

        # Get statement type
        statement_type = self.canonical_type if self.canonical_type else self.role_or_type

        # For Income Statement and Cash Flow Statement: Use preferred_sign
        if statement_type in ('IncomeStatement', 'CashFlowStatement'):
            if 'preferred_sign' in result.columns:
                for col in period_cols:
                    if col not in result.columns:
                        continue
                    # Convert to numeric - handles object dtype columns with None values (Issue #556)
                    # This is needed because columns with None values become object dtype
                    numeric_col = pd.to_numeric(result[col], errors='coerce')
                    if pd.api.types.is_numeric_dtype(numeric_col):
                        # FIX (Issue #599): Convert entire column to numeric first to prevent
                        # pandas FutureWarning about assigning incompatible dtype to object column
                        result[col] = numeric_col
                        # Apply preferred_sign where it's not None and not 0
                        mask = result['preferred_sign'].notna() & (result['preferred_sign'] != 0)
                        result.loc[mask, col] = numeric_col[mask] * result.loc[mask, 'preferred_sign']

        # Balance Sheet: no transformation

        return result

    def _pivot_to_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pivot Statement of Equity DataFrame to SEC-style matrix format.

        Issue edgartools-uqg7: Transform equity statement to matrix format
        with equity components as columns (not multiplied by periods) and
        activities as rows. This matches how the SEC presents equity statements.

        Args:
            df: Standard flat DataFrame from _build_dataframe_from_raw_data

        Returns:
            Matrix-format DataFrame if this is an equity statement with
            detailed equity component members, otherwise returns original DataFrame unchanged.
        """
        # Use the same detection logic as _is_matrix_statement()
        if not self._is_matrix_statement():
            return df

        # Verify we have the required columns
        if 'dimension_axis' not in df.columns:
            return df

        # Identify period columns (date-like columns)
        metadata_cols = {
            'concept', 'label', 'level', 'abstract', 'dimension', 'is_breakdown',
            'dimension_axis', 'dimension_member', 'dimension_member_label',
            'dimension_label', 'balance', 'weight', 'preferred_sign',
            'parent_concept', 'parent_abstract_concept', 'unit', 'point_in_time'
        }
        period_cols = [col for col in df.columns if col not in metadata_cols]

        if not period_cols:
            return df

        # Get unique equity component members (column headers for matrix)
        all_members = df[
            df['dimension_axis'].str.contains('StatementEquityComponentsAxis', na=False)
        ]['dimension_member_label'].dropna().unique().tolist()

        if not all_members:
            return df

        # Filter to only PRIMARY equity components, exclude sub-breakdowns
        primary_patterns = [
            'common stock',
            'paid-in capital',
            'paid in capital',
            'apic',
            'retained earnings',
            'accumulated deficit',
            'accumulated other comprehensive',
            'treasury stock',
            'preferred stock',
            'accumulated income',
            'right to recover',
            'noncontrolling',
        ]

        # Sub-breakdown patterns to exclude
        exclude_patterns = [
            'foreign currency',
            'translation adjustment',
            'unrealized gain',
            'unrealized loss',
            'unrealized (gain',
            'pension',
            'benefit plan',
            'hedge',
            'reclassification',
            'derivative',
            'class a',  # Share class details
            'class b',
            'class c',
            'series a',
            'series b',
            'series c',
        ]

        def is_primary_member(member: str) -> bool:
            member_lower = member.lower()
            if any(excl in member_lower for excl in exclude_patterns):
                return False
            if any(prim in member_lower for prim in primary_patterns):
                return True
            return False  # Only include explicit primary patterns

        equity_members = [m for m in all_members if is_primary_member(m)]

        if not equity_members:
            return df

        # SEC-style matrix: components as columns, one value per row
        # Use only the most recent period for values
        primary_period = period_cols[0]  # Most recent period

        matrix_rows = []
        non_dim_df = df[~df['dimension'].fillna(False)]

        for _, row in non_dim_df.iterrows():
            concept = row['concept']
            label = row['label']

            matrix_row = {
                'concept': concept,
                'label': label,
                'level': row.get('level', 0),
                'abstract': row.get('abstract', False),
            }

            # Get dimensional values for this concept
            dim_values = df[
                (df['concept'] == concept) &
                (df['dimension_axis'].str.contains('StatementEquityComponentsAxis', na=False))
            ]

            # Fill in value for each equity component (single period)
            for member in equity_members:
                member_row = dim_values[dim_values['dimension_member_label'] == member]
                if not member_row.empty:
                    value = member_row[primary_period].iloc[0]
                else:
                    value = None
                matrix_row[member] = value

            matrix_rows.append(matrix_row)

        if not matrix_rows:
            return df

        result_df = pd.DataFrame(matrix_rows)

        # Reorder columns: metadata first, then equity components in order
        base_cols = ['concept', 'label', 'level', 'abstract']
        result_df = result_df[base_cols + equity_members]

        return result_df

    def _validate_statement(self, skip_concept_check: bool = False) -> None:
        """
        Validate the statement structure and required concepts.

        Args:
            skip_concept_check: If True, skip checking for required concepts (useful for testing)
        """
        data = self.get_raw_data()
        if not data:
            raise StatementValidationError(f"No data found for statement {self.role_or_type}")

        # Determine the statement type to validate against
        validate_type = self.canonical_type if self.canonical_type else self.role_or_type

        # Check for required concepts if this is a standard statement type
        if validate_type in self.REQUIRED_CONCEPTS and not skip_concept_check:
            missing_concepts = []
            for concept in self.REQUIRED_CONCEPTS[validate_type]:
                if not any(concept in item.get('all_names', []) for item in data):
                    missing_concepts.append(concept)

            if missing_concepts:
                raise StatementValidationError(
                    f"Missing required concepts for {validate_type}: {', '.join(missing_concepts)}")

    def validate(self, level: str = "fundamental") -> "ValidationResult":
        """
        Validate the financial statement for accounting compliance.

        For balance sheets, validates the fundamental accounting equation:
            Assets = Liabilities + Equity

        Args:
            level: Validation level - "fundamental", "sections", or "detailed"
                   - fundamental: Basic equation check
                   - sections: Also validates section subtotals
                   - detailed: Full line-item rollup validation

        Returns:
            ValidationResult with is_valid flag and any issues found

        Example:
            >>> bs = xbrl.statements.balance_sheet()
            >>> result = bs.validate()
            >>> print(result)
            ValidationResult: VALID (0 errors, 0 warnings)
            >>> if not result.is_valid:
            ...     for error in result.errors:
            ...         print(f"Error: {error.message}")
        """
        from edgar.xbrl.validation import validate_statement, ValidationLevel

        # Map string level to enum
        level_map = {
            "fundamental": ValidationLevel.FUNDAMENTAL,
            "sections": ValidationLevel.SECTIONS,
            "detailed": ValidationLevel.DETAILED,
        }
        validation_level = level_map.get(level.lower(), ValidationLevel.FUNDAMENTAL)

        return validate_statement(self, self.canonical_type, level=validation_level)

    def calculate_ratios(self) -> Dict[str, float]:
        """Calculate common financial ratios for this statement."""
        ratios = {}
        data = self.get_raw_data()

        # Use canonical type if available, otherwise use role_or_type
        statement_type = self.canonical_type if self.canonical_type else self.role_or_type

        if statement_type == 'BalanceSheet':
            # Calculate balance sheet ratios
            ratios.update(self._calculate_balance_sheet_ratios(data))
        elif statement_type == 'IncomeStatement':
            # Calculate income statement ratios
            ratios.update(self._calculate_income_statement_ratios(data))

        return ratios

    def _calculate_balance_sheet_ratios(self, data: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate balance sheet specific ratios."""
        ratios = {}

        # Current ratio
        current_assets = self._get_concept_value(data, 'us-gaap_CurrentAssets')
        current_liabilities = self._get_concept_value(data, 'us-gaap_CurrentLiabilities')
        if current_assets and current_liabilities:
            ratios['current_ratio'] = current_assets / current_liabilities

        # Quick ratio
        inventory = self._get_concept_value(data, 'us-gaap_Inventory')
        if current_assets and current_liabilities and inventory:
            ratios['quick_ratio'] = (current_assets - inventory) / current_liabilities

        return ratios

    def _calculate_income_statement_ratios(self, data: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate income statement specific ratios."""
        ratios = {}

        # Gross margin
        revenue = self._get_concept_value(data, 'us-gaap_Revenues')
        gross_profit = self._get_concept_value(data, 'us-gaap_GrossProfit')
        if revenue and gross_profit:
            ratios['gross_margin'] = gross_profit / revenue

        # Net margin
        net_income = self._get_concept_value(data, 'us-gaap_NetIncomeLoss')
        if revenue and net_income:
            ratios['net_margin'] = net_income / revenue

        return ratios

    def _get_concept_value(self, data: List[Dict[str, Any]], concept: str) -> Optional[float]:
        """Get the value for a specific concept from statement data."""
        for item in data:
            if concept in item.get('all_names', []):
                values = item.get('values', {})
                if values:
                    return float(next(iter(values.values())))
        return None

    def analyze_trends(self, periods: int = 4) -> Dict[str, List[float]]:
        """Analyze trends in key metrics over time."""
        trends = {}

        # Use canonical type if available, otherwise use role_or_type
        statement_type = self.canonical_type if self.canonical_type else self.role_or_type

        # Get data for multiple periods
        period_views = self.xbrl.get_period_views(statement_type)
        if not period_views:
            return trends

        periods_to_analyze = period_views[0].get('periods', [])[:periods]

        for period in periods_to_analyze:
            data = self.get_raw_data(period)

            if statement_type == 'BalanceSheet':
                self._analyze_balance_sheet_trends(data, trends, period)
            elif statement_type == 'IncomeStatement':
                self._analyze_income_statement_trends(data, trends, period)

        return trends

    def _analyze_balance_sheet_trends(self, data: List[Dict[str, Any]], 
                                     trends: Dict[str, List[float]], 
                                     period: str) -> None:
        """Analyze balance sheet trends."""
        metrics = {
            'total_assets': 'us-gaap_Assets',
            'total_liabilities': 'us-gaap_Liabilities',
            'equity': 'us-gaap_StockholdersEquity'
        }

        for metric_name, concept in metrics.items():
            value = self._get_concept_value(data, concept)
            if value:
                if metric_name not in trends:
                    trends[metric_name] = []
                trends[metric_name].append(value)

    def _analyze_income_statement_trends(self, data: List[Dict[str, Any]], 
                                        trends: Dict[str, List[float]], 
                                        period: str) -> None:
        """Analyze income statement trends."""
        metrics = {
            'revenue': 'us-gaap_Revenues',
            'gross_profit': 'us-gaap_GrossProfit',
            'net_income': 'us-gaap_NetIncomeLoss'
        }

        for metric_name, concept in metrics.items():
            value = self._get_concept_value(data, concept)
            if value:
                if metric_name not in trends:
                    trends[metric_name] = []
                trends[metric_name].append(value)

    def get_raw_data(self, period_filter: Optional[str] = None,
                     view: StatementView = None) -> List[Dict[str, Any]]:
        """
        Get the raw statement data.

        Args:
            period_filter: Optional period key to filter facts
            view: StatementView controlling dimensional filtering

        Returns:
            List of line items with values

        Raises:
            StatementValidationError: If data retrieval fails
        """
        # Use the canonical type if available, otherwise use the role
        statement_id = self.canonical_type if self.canonical_type else self.role_or_type

        data = self.xbrl.get_statement(statement_id, period_filter=period_filter, view=view)
        if data is None:
            raise StatementValidationError(f"Failed to retrieve data for statement {statement_id}")
        return data

    def text(self, raw_html: bool = False) -> Optional[str]:
        """Get narrative text content from a note/disclosure statement."""
        from edgar.xbrl.abstract_detection import is_textblock_concept
        from edgar.xbrl.rendering import _is_html, html_to_text

        try:
            data = self.get_raw_data()
        except Exception:
            return None

        text_parts = []
        for item in data:
            concept = item.get('concept', '').replace(':', '_')
            if not is_textblock_concept(concept):
                continue
            for value in item.get('values', {}).values():
                if value and isinstance(value, str) and value.strip():
                    if raw_html:
                        text_parts.append(value)
                    elif _is_html(value):
                        text_parts.append(html_to_text(value))
                    else:
                        text_parts.append(value)
                    break  # One value per TextBlock (same across periods)

        return "\n\n".join(text_parts) if text_parts else None

    @property
    def is_note(self) -> bool:
        """Check if this statement contains narrative TextBlock content."""
        from edgar.xbrl.abstract_detection import is_textblock_concept
        try:
            data = self.get_raw_data()
        except Exception:
            return False
        return any(
            is_textblock_concept(item.get('concept', '').replace(':', '_'))
            for item in data
        )


class Statements:
    """
    High-level interface for working with XBRL financial statements.

    This class provides a user-friendly way to access and manipulate 
    financial statements extracted from XBRL data.
    """

    def __init__(self, xbrl):
        """
        Initialize with an XBRL object.

        Args:
            xbrl: XBRL object containing parsed data
        """
        self.xbrl = xbrl
        self.statements = xbrl.get_all_statements()

        # Create statement type lookup for quick access
        self.statement_by_type = {}
        for stmt in self.statements:
            if stmt['type']:
                if stmt['type'] not in self.statement_by_type:
                    self.statement_by_type[stmt['type']] = []
                self.statement_by_type[stmt['type']].append(stmt)

    def _resolve_view(self, view: ViewType, include_dimensions: Optional[bool]) -> ViewType:
        """
        Resolve view parameter from deprecated include_dimensions.

        Args:
            view: Explicit view parameter (takes precedence)
            include_dimensions: Deprecated parameter

        Returns:
            Resolved view (may be None if neither specified)
        """
        if include_dimensions is not None:
            if view is not None:
                raise ValueError(
                    "Cannot specify both 'view' and 'include_dimensions'. "
                    "Use 'view' only (include_dimensions is deprecated)."
                )
            warnings.warn(
                "include_dimensions is deprecated and will be removed in v6.0. "
                "Use view='standard', 'detailed', or 'summary' instead.",
                DeprecationWarning,
                stacklevel=3
            )
            return StatementView.DETAILED if include_dimensions else StatementView.STANDARD
        return view

    @staticmethod
    def classify_statement(stmt: dict) -> str:
        """
        Classify a statement into a category based on its type, primary_concept, and definition.

        Uses a tiered approach:
        - Tier 0: Explicit category field
        - Tier 1: Infer from type (works when type is set)
        - Tier 2: Infer from primary_concept (reliable for type=None statements)
        - Tier 3: Infer from definition suffix

        Categories:
        - 'statement': Core financial statements (Income Statement, Balance Sheet, etc.)
        - 'note': Notes to financial statements
        - 'disclosure': Disclosure sections
        - 'document': Document sections (like CoverPage)
        - 'other': Everything else

        Args:
            stmt: Statement dictionary with 'type', 'primary_concept', 'definition',
                  and optional 'category' fields

        Returns:
            str: Category name ('statement', 'note', 'disclosure', 'document', or 'other')

        Example:
            >>> stmt = {'type': 'IncomeStatement', 'title': 'Income Statement'}
            >>> Statements.classify_statement(stmt)
            'statement'

            >>> stmt = {'type': None, 'primary_concept': 'DebtDisclosureAbstract'}
            >>> Statements.classify_statement(stmt)
            'disclosure'
        """
        # Tier 0: Use explicit category if provided
        category = stmt.get('category')
        if category:
            return category

        # Tier 1: Infer from type (existing logic, works when type is set)
        stmt_type = stmt.get('type', '') or ''
        if stmt_type:
            if 'Note' in stmt_type:
                return 'note'
            elif 'Disclosure' in stmt_type:
                return 'disclosure'
            elif stmt_type == 'CoverPage':
                return 'document'
            elif stmt_type in ('BalanceSheet', 'IncomeStatement', 'CashFlowStatement',
                               'StatementOfEquity', 'ComprehensiveIncome') or 'Statement' in stmt_type:
                return 'statement'

        # Tier 2: Infer from primary_concept (reliable for type=None statements)
        pc = stmt.get('primary_concept', '') or ''
        if 'Disclosure' in pc:
            return 'disclosure'
        if 'AccountingPolicies' in pc:
            return 'note'

        # Tier 3: Infer from definition suffix
        defn = stmt.get('definition', '') or ''
        if 'Parenthetical' in defn:
            return 'statement'

        return 'other'

    def get_statements_by_category(self) -> dict:
        """
        Get statements organized by category.

        Returns a dictionary with statements grouped into categories:
        - 'statement': Core financial statements
        - 'note': Notes to financial statements
        - 'disclosure': Disclosure sections
        - 'document': Document sections
        - 'other': Other sections

        Each statement in the lists includes an 'index' field for positional reference.

        Returns:
            dict: Dictionary with category keys, each containing a list of statement dicts

        Example:
            >>> categories = xbrl.statements.get_statements_by_category()
            >>> # Get all disclosures
            >>> disclosures = categories['disclosure']
            >>> for disc in disclosures:
            ...     print(f"{disc['index']}: {disc['title']}")
            >>>
            >>> # Get all notes
            >>> notes = categories['note']
            >>> # Get core financial statements
            >>> statements = categories['statement']
        """
        categories = {
            'statement': [],
            'note': [],
            'disclosure': [],
            'document': [],
            'other': []
        }

        for index, stmt in enumerate(self.statements):
            category = self.classify_statement(stmt)
            stmt_with_index = dict(stmt)
            stmt_with_index['index'] = index
            categories[category].append(stmt_with_index)

        return categories

    def _handle_statement_error(self, e: Exception, statement_type: str) -> Optional[Statement]:
        """
        Common error handler for statement resolution failures.

        Args:
            e: The exception that occurred
            statement_type: Type of statement that failed to resolve

        Returns:
            None (always, for consistency)
        """
        from edgar.core import log

        if isinstance(e, StatementNotFound):
            # Custom exception already has detailed context
            log.warning(str(e))
        else:
            # For other exceptions, extract context manually
            entity_name = getattr(self.xbrl, 'entity_name', 'Unknown')
            cik = getattr(self.xbrl, 'cik', 'Unknown')
            period_of_report = getattr(self.xbrl, 'period_of_report', 'Unknown')

            log.warning(
                f"Failed to resolve {statement_type.lower().replace('_', ' ')} for {entity_name} "
                f"(CIK: {cik}, Period: {period_of_report}): {type(e).__name__}: {str(e)}"
            )

        return None

    def find_statement_by_primary_concept(self, statement_type: str, is_parenthetical: bool = False) -> Optional[str]:
        """
        Find a statement by its primary concept.

        Args:
            statement_type: Statement type (e.g., 'BalanceSheet', 'IncomeStatement')
            is_parenthetical: Whether to look for a parenthetical statement
                             (only applicable for BalanceSheet)

        Returns:
            Role URI for the matching statement, or None if not found
        """
        if statement_type not in statement_to_concepts:
            return None

        # Get information about the statement's identifying concept
        concept_info = statement_to_concepts[statement_type]
        concept = concept_info.concept

        # Find all statements of the requested type
        matching_statements = self.statement_by_type.get(statement_type, [])

        if not matching_statements:
            return None

        # Parenthetical check is only relevant for BalanceSheet
        check_parenthetical = statement_type == 'BalanceSheet'

        # Try to find a statement containing the specific concept
        for stmt in matching_statements:
            role = stmt['role']

            # Check for parenthetical in the role name if it's a BalanceSheet
            if check_parenthetical:
                role_lower = role.lower()
                is_role_parenthetical = 'parenthetical' in role_lower

                # Skip if parenthetical status doesn't match what we're looking for
                if is_parenthetical != is_role_parenthetical:
                    continue

            # Examine the presentation tree for this role
            if role in self.xbrl.presentation_trees:
                tree = self.xbrl.presentation_trees[role]
                # Check if the identifying concept is in this tree
                normalized_concept = concept.replace(':', '_')
                for element_id in tree.all_nodes:
                    # Check both original and normalized form
                    if element_id == concept or element_id == normalized_concept:
                        return role

        # If no exact concept match, fall back to the first statement of the type
        # that matches the parenthetical requirement for BalanceSheet
        if check_parenthetical:
            for stmt in matching_statements:
                role = stmt['role']
                role_lower = role.lower()
                is_role_parenthetical = 'parenthetical' in role_lower

                if is_parenthetical == is_role_parenthetical:
                    return role

        # If still no match, return the first statement
        return matching_statements[0]['role']

    def __getitem__(self, item: Union[int, str]) -> Optional[Statement]:
        """
        Get a statement by index, type, or role.

        Args:
            item: Integer index, string statement type, or role URI

        Returns:
            Statement instance for the requested statement
        """
        if isinstance(item, int):
            if 0 <= item < len(self.statements):
                stmt = self.statements[item]
                # Get the canonical type if available
                canonical_type = None
                if stmt.get('type') in statement_to_concepts:
                    canonical_type = stmt.get('type')
                return Statement(self.xbrl, stmt['role'], canonical_type=canonical_type)
        elif isinstance(item, str):
            # Check if it's a standard statement type with a specific concept marker
            if item in statement_to_concepts:
                # Get the statement role using the primary concept
                role = self.find_statement_by_primary_concept(item)
                if role:
                    return Statement(self.xbrl, role, canonical_type=item)

                # If no concept match, fall back to the type
                return Statement(self.xbrl, item, canonical_type=item)

            # If it's a statement type with multiple statements, return the first one
            if item in self.statement_by_type and self.statement_by_type[item]:
                return Statement(self.xbrl, item, canonical_type=item)

            # Otherwise, try to use it directly as a role or statement name
            # Try to determine canonical type from the name
            canonical_type = None
            for std_type in statement_to_concepts.keys():
                if std_type.lower() in item.lower():
                    canonical_type = std_type
                    break
            return Statement(self.xbrl, item, canonical_type=canonical_type)

    def __len__(self):
        return len(self.statements)

    def __iter__(self):
        return iter(self.all())

    def to_context(self, detail: str = 'standard') -> str:
        """
        Returns AI-optimized text representation for language models.

        Provides structured information about available statements in Markdown-KV
        format optimized for LLM consumption and navigation.

        Args:
            detail: Level of detail to include:
                - 'minimal': Entity + count + core statement accessors (~150 tokens)
                - 'standard': Adds category breakdown and discovery methods (~300 tokens)
                - 'full': Adds all non-core statement names by category (~500+ tokens)

        Returns:
            Markdown-KV formatted context string optimized for LLMs
        """
        lines = []

        # Header with entity info
        entity_name = ''
        ticker = ''
        doc_type = ''
        if hasattr(self.xbrl, 'entity_info') and self.xbrl.entity_info:
            entity_name = self.xbrl.entity_info.get('entity_name', '')
            ticker = self.xbrl.entity_info.get('ticker', '')
            doc_type = self.xbrl.entity_info.get('document_type', '')

        header = "STATEMENTS"
        if entity_name:
            header += f": {entity_name}"
            if ticker:
                header += f" ({ticker})"
        if doc_type:
            header += f" {doc_type}"
        lines.append(header)
        lines.append("")
        lines.append(f"Total: {len(self.statements)} statements")

        # Core financial statements with accessor methods
        type_accessors = {
            'IncomeStatement': '.income_statement()',
            'BalanceSheet': '.balance_sheet()',
            'CashFlowStatement': '.cashflow_statement()',
            'StatementOfEquity': '.statement_of_equity()',
            'ComprehensiveIncome': '.comprehensive_income()',
            'CoverPage': '.cover_page()',
        }

        statements_by_category = self.get_statements_by_category()
        core_stmts = statements_by_category.get('statement', [])

        if core_stmts:
            lines.append("")
            lines.append("CORE STATEMENTS:")
            for stmt in core_stmts:
                stmt_type = stmt.get('type', '')
                accessor = type_accessors.get(stmt_type, '')
                definition = stmt.get('definition', '')
                if accessor:
                    lines.append(f"  {accessor:<40s} {definition}")
                else:
                    lines.append(f"  [{stmt.get('index', '')}] {definition}")

        if detail == 'minimal':
            return '\n'.join(lines)

        # Category breakdown
        category_display = [
            ('note', 'Notes'),
            ('disclosure', 'Disclosures'),
            ('document', 'Document'),
            ('other', 'Other'),
        ]

        category_parts = []
        for cat_key, cat_label in category_display:
            count = len(statements_by_category.get(cat_key, []))
            if count > 0:
                category_parts.append(f"{cat_label}: {count}")

        if category_parts:
            lines.append("")
            lines.append(f"OTHER: {' | '.join(category_parts)}")

        # Discovery methods
        lines.append("")
        lines.append("DISCOVERY:")
        lines.append("  .search('keyword')       Find statements by keyword")
        lines.append("  .get('name')             Get statement by type or name")
        lines.append("  .list_available()        Browse all as DataFrame")
        lines.append("  .all(category='note')    Filter by category")

        if detail == 'standard':
            return '\n'.join(lines)

        # Full: list statements in each non-core category
        for cat_key, cat_label in category_display:
            cat_stmts = statements_by_category.get(cat_key, [])
            if not cat_stmts:
                continue
            lines.append("")
            lines.append(f"{cat_label.upper()} ({len(cat_stmts)}):")
            for stmt in cat_stmts:
                definition = stmt.get('definition', stmt.get('role_name', ''))
                lines.append(f"  [{stmt.get('index', '')}] {definition}")

        return '\n'.join(lines)

    def __rich__(self) -> Any:
        """
        Rich console representation following the EdgarTools design language.

        Returns a Panel card with:
        - Title: entity name and ticker from XBRL metadata
        - Content: core financial statements table + category summary
        - Subtitle: hint for discovering more statements
        """
        if Table is None:
            return str(self)

        from rich.console import Group
        from rich.panel import Panel
        from rich.text import Text
        from edgar.display import get_style, SYMBOLS

        # Extract entity info from the XBRL object
        entity_name = ''
        ticker = ''
        if hasattr(self.xbrl, 'entity_info') and self.xbrl.entity_info:
            entity_name = self.xbrl.entity_info.get('entity_name', '')
            ticker = self.xbrl.entity_info.get('ticker', '')

        total = len(self.statements)

        # === Title ===
        title_parts = []
        title_parts.append((f"Statements ({total}) ", get_style("form_type")))
        if entity_name:
            title_parts.append((entity_name, get_style("company_name")))
        if ticker:
            title_parts.append((" ", ""))
            title_parts.append((f"({ticker})", get_style("ticker")))
        title = Text.assemble(*title_parts) if title_parts else Text("Statements")

        # === Subtitle ===
        subtitle = Text.assemble(
            (".search() ", get_style("hint")),
            (f"{SYMBOLS['bullet']} ", get_style("metadata")),
            (".list_available() ", get_style("hint")),
            (f"{SYMBOLS['bullet']} ", get_style("metadata")),
            (".get()", get_style("hint")),
        )

        # Group statements by category
        statements_by_category = self.get_statements_by_category()
        components = []

        # === Core financial statements table ===
        core_stmts = statements_by_category.get('statement', [])
        if core_stmts:
            # Friendly display names for statement types
            type_labels = {
                'IncomeStatement': 'Income Statement',
                'BalanceSheet': 'Balance Sheet',
                'CashFlowStatement': 'Cash Flow Statement',
                'StatementOfEquity': 'Equity',
                'ComprehensiveIncome': 'Comprehensive Income',
                'IncomeStatementParenthetical': 'Income (Parenthetical)',
                'BalanceSheetParenthetical': 'Balance Sheet (Parenthetical)',
                'CashFlowStatementParenthetical': 'Cash Flow (Parenthetical)',
                'StatementOfEquityParenthetical': 'Equity (Parenthetical)',
                'ComprehensiveIncomeParenthetical': 'Compr. Income (Parenthetical)',
                'CoverPage': 'Cover Page',
                'ScheduleOfInvestments': 'Schedule of Investments',
                'FinancialHighlights': 'Financial Highlights',
            }

            # Map statement types to their accessor method names
            type_accessors = {
                'IncomeStatement': '.income_statement()',
                'BalanceSheet': '.balance_sheet()',
                'CashFlowStatement': '.cashflow_statement()',
                'StatementOfEquity': '.statement_of_equity()',
                'ComprehensiveIncome': '.comprehensive_income()',
                'IncomeStatementParenthetical': '.income_statement(parenthetical=True)',
                'BalanceSheetParenthetical': '.balance_sheet(parenthetical=True)',
                'CashFlowStatementParenthetical': '.cashflow_statement(parenthetical=True)',
                'StatementOfEquityParenthetical': '.statement_of_equity(parenthetical=True)',
                'ComprehensiveIncomeParenthetical': '.comprehensive_income(parenthetical=True)',
                'CoverPage': '.cover_page()',
            }

            stmt_table = Table(
                box=box.SIMPLE_HEAD,
                show_edge=False,
                padding=(0, 1),
                expand=False,
            )
            stmt_table.add_column("#", style="dim", justify="right", width=4)
            stmt_table.add_column("Statement", no_wrap=True)
            stmt_table.add_column("Accessor", no_wrap=True)

            for stmt in core_stmts:
                idx = str(stmt['index'])
                stmt_type = stmt.get('type', '') or ''
                friendly = type_labels.get(stmt_type, stmt_type)
                accessor = type_accessors.get(stmt_type, f'[{stmt.get("index", "")}]')

                stmt_table.add_row(
                    idx,
                    Text(friendly, style=get_style("value_highlight")),
                    Text(accessor, style=get_style("hint")),
                )

            components.append(stmt_table)

        # === Other categories summary with topic samples ===
        category_display = [
            ('note', 'Notes'),
            ('disclosure', 'Disclosures'),
            ('document', 'Document'),
            ('other', 'Other'),
        ]

        summary_table = Table(box=None, show_header=False, padding=(0, 1), expand=False)
        summary_table.add_column("Category", style=get_style("label"), no_wrap=True)
        summary_table.add_column("Count", style=get_style("value_highlight"), justify="right", width=4)
        summary_table.add_column("Topics", style=get_style("metadata"), no_wrap=True)

        has_summary_rows = False
        for cat_key, cat_label in category_display:
            cat_stmts = statements_by_category.get(cat_key, [])
            count = len(cat_stmts)
            if count == 0:
                continue

            topics_str = _extract_topic_summary(cat_stmts, max_shown=4)
            summary_table.add_row(cat_label, str(count), topics_str)
            has_summary_rows = True

        if has_summary_rows:
            components.append(Text(""))
            components.append(summary_table)

        if not components:
            return Text("No statements found")

        return Panel(
            Group(*components),
            title=title,
            subtitle=subtitle,
            box=box.ROUNDED,
            border_style=get_style("border"),
            expand=False,
            padding=(0, 1),
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def cover_page(self) -> Statement:
        """
        Get the cover page statement.

        Returns:
            A cover page statement
        """
        role = self.find_statement_by_primary_concept("CoverPage")
        if role:
            return Statement(self.xbrl, role, canonical_type="CoverPage")

        # Try using the xbrl.render_statement with parenthetical parameter
        if hasattr(self.xbrl, 'find_statement'):
            matching_statements, found_role, _ = self.xbrl.find_statement("CoverPage")
            if found_role:
                return Statement(self.xbrl, found_role, canonical_type="CoverPage")

        return self["CoverPage"]

    def balance_sheet(self, parenthetical: bool = False,
                      view: ViewType = None,
                      include_dimensions: Optional[bool] = None) -> Optional[Statement]:
        """
        Get a balance sheet.

        Args:
            parenthetical: Whether to get the parenthetical balance sheet
            view: StatementView controlling dimensional data display.
                  STANDARD: Face presentation only (default for display)
                  DETAILED: All dimensional data (default for to_dataframe)
                  SUMMARY: Non-dimensional totals only
            include_dimensions: Deprecated. Use view parameter instead.

        Returns:
            A balance sheet statement, or None if unable to resolve the statement
        """
        # Handle deprecated include_dimensions parameter
        effective_view = self._resolve_view(view, include_dimensions)

        try:
            role = self.find_statement_by_primary_concept("BalanceSheet", is_parenthetical=parenthetical)
            if role:
                return Statement(self.xbrl, role, canonical_type="BalanceSheet", view=effective_view)

            # Try using the xbrl.render_statement with parenthetical parameter
            if hasattr(self.xbrl, 'find_statement'):
                matching_statements, found_role, _ = self.xbrl.find_statement("BalanceSheet", parenthetical)
                if found_role:
                    return Statement(self.xbrl, found_role, canonical_type="BalanceSheet", view=effective_view)

            return Statement(self.xbrl, "BalanceSheet", canonical_type="BalanceSheet", view=effective_view)
        except Exception as e:
            return self._handle_statement_error(e, "BalanceSheet")

    def income_statement(self, parenthetical: bool = False, skip_concept_check: bool = False,
                         view: ViewType = None,
                         include_dimensions: Optional[bool] = None) -> Optional[Statement]:
        """
        Get an income statement.

        Args:
            parenthetical: Whether to get the parenthetical income statement
            skip_concept_check: If True, skip checking for required concepts (useful for testing)
            view: StatementView controlling dimensional data display.
                  STANDARD: Face presentation only (default for display)
                  DETAILED: All dimensional data (default for to_dataframe)
                  SUMMARY: Non-dimensional totals only
            include_dimensions: Deprecated. Use view parameter instead.

        Returns:
            An income statement, or None if unable to resolve the statement
        """
        # Handle deprecated include_dimensions parameter
        effective_view = self._resolve_view(view, include_dimensions)

        try:
            # Try using the xbrl.find_statement with parenthetical parameter
            if hasattr(self.xbrl, 'find_statement'):
                matching_statements, found_role, _ = self.xbrl.find_statement("IncomeStatement", parenthetical)
                if found_role:
                    return Statement(self.xbrl, found_role, canonical_type="IncomeStatement",
                                   skip_concept_check=skip_concept_check,
                                   view=effective_view)

            return Statement(self.xbrl, "IncomeStatement", canonical_type="IncomeStatement",
                           skip_concept_check=skip_concept_check,
                           view=effective_view)
        except Exception as e:
            return self._handle_statement_error(e, "IncomeStatement")

    def cashflow_statement(self, parenthetical: bool = False,
                           view: ViewType = None,
                           include_dimensions: Optional[bool] = None) -> Optional[Statement]:
        """
        Get a cash flow statement.

        Args:
            parenthetical: Whether to get the parenthetical cash flow statement
            view: StatementView controlling dimensional data display.
                  STANDARD: Face presentation only (default for display)
                  DETAILED: All dimensional data (default for to_dataframe)
                  SUMMARY: Non-dimensional totals only
            include_dimensions: Deprecated. Use view parameter instead.

        Returns:
             The cash flow statement, or None if unable to resolve the statement
        """
        # Handle deprecated include_dimensions parameter
        effective_view = self._resolve_view(view, include_dimensions)

        try:
            # Try using the xbrl.find_statement with parenthetical parameter
            if hasattr(self.xbrl, 'find_statement'):
                matching_statements, found_role, _ = self.xbrl.find_statement("CashFlowStatement", parenthetical)
                if found_role:
                    return Statement(self.xbrl, found_role, canonical_type="CashFlowStatement",
                                   view=effective_view)

            return Statement(self.xbrl, "CashFlowStatement", canonical_type="CashFlowStatement",
                           view=effective_view)
        except Exception as e:
            return self._handle_statement_error(e, "CashFlowStatement")

    def cash_flow_statement(self, **kwargs):
        """Alias for cashflow_statement()."""
        return self.cashflow_statement(**kwargs)

    def statement_of_equity(self, parenthetical: bool = False,
                            view: ViewType = None,
                            include_dimensions: Optional[bool] = None) -> Optional[Statement]:
        """
        Get a statement of equity.

        Args:
            parenthetical: Whether to get the parenthetical statement of equity
            view: StatementView controlling dimensional data display.
                  STANDARD: Face presentation only (default for display)
                  DETAILED: All dimensional data (default for to_dataframe)
                  SUMMARY: Non-dimensional totals only
            include_dimensions: Deprecated. Use view parameter instead.

        Returns:
           The statement of equity, or None if unable to resolve the statement
        """
        # Handle deprecated include_dimensions parameter
        effective_view = self._resolve_view(view, include_dimensions)

        # Issue #571: Statement of Equity is inherently dimensional - default to include_dimensions=True
        # when neither view nor include_dimensions was explicitly set
        effective_include_dimensions = True if (view is None and include_dimensions is None) else (include_dimensions if include_dimensions is not None else False)

        try:
            # Try using the xbrl.find_statement with parenthetical parameter
            if hasattr(self.xbrl, 'find_statement'):
                matching_statements, found_role, _ = self.xbrl.find_statement("StatementOfEquity", parenthetical)
                if found_role:
                    return Statement(self.xbrl, found_role, canonical_type="StatementOfEquity",
                                   view=effective_view, include_dimensions=effective_include_dimensions)

            return Statement(self.xbrl, "StatementOfEquity", canonical_type="StatementOfEquity",
                           view=effective_view, include_dimensions=effective_include_dimensions)
        except Exception as e:
            return self._handle_statement_error(e, "StatementOfEquity")

    def comprehensive_income(self, parenthetical: bool = False,
                             view: ViewType = None,
                             include_dimensions: Optional[bool] = None) -> Optional[Statement]:
        """
        Get a statement of comprehensive income.

        Comprehensive income includes net income plus other comprehensive income items
        such as foreign currency translation adjustments, unrealized gains/losses on
        investments, and pension adjustments.

        Args:
            parenthetical: Whether to get the parenthetical comprehensive income statement
            view: StatementView controlling dimensional data display.
                  STANDARD: Face presentation only (default for display)
                  DETAILED: All dimensional data (default for to_dataframe)
                  SUMMARY: Non-dimensional totals only
            include_dimensions: Deprecated. Use view parameter instead.

        Returns:
            The comprehensive income statement, or None if unable to resolve the statement
        """
        # Handle deprecated include_dimensions parameter
        effective_view = self._resolve_view(view, include_dimensions)

        # Issue #571: Comprehensive Income is inherently dimensional - default to include_dimensions=True
        # when neither view nor include_dimensions was explicitly set
        effective_include_dimensions = True if (view is None and include_dimensions is None) else (include_dimensions if include_dimensions is not None else False)

        try:
            # Try using the xbrl.find_statement with parenthetical parameter
            if hasattr(self.xbrl, 'find_statement'):
                matching_statements, found_role, _ = self.xbrl.find_statement("ComprehensiveIncome", parenthetical)
                if found_role:
                    return Statement(self.xbrl, found_role, canonical_type="ComprehensiveIncome",
                                   view=effective_view, include_dimensions=effective_include_dimensions)

            return Statement(self.xbrl, "ComprehensiveIncome", canonical_type="ComprehensiveIncome",
                           view=effective_view, include_dimensions=effective_include_dimensions)
        except Exception as e:
            return self._handle_statement_error(e, "ComprehensiveIncome")

    def schedule_of_investments(self, parenthetical: bool = False) -> Optional[Statement]:
        """
        Get a Schedule of Investments statement.

        This statement shows investment holdings with fair values, cost basis,
        and other details. Common in fund filings (BDCs, closed-end funds) but
        also appears in regular company filings as investment/securities disclosures.

        Args:
            parenthetical: Whether to get the parenthetical version

        Returns:
            The Schedule of Investments statement, or None if not found
        """
        try:
            if hasattr(self.xbrl, 'find_statement'):
                matching_statements, found_role, _ = self.xbrl.find_statement(
                    "ScheduleOfInvestments", parenthetical
                )
                if found_role:
                    return Statement(self.xbrl, found_role, canonical_type="ScheduleOfInvestments")

            return self["ScheduleOfInvestments"]
        except Exception as e:
            return self._handle_statement_error(e, "ScheduleOfInvestments")

    def get_period_views(self, statement_type: str) -> List[Dict[str, Any]]:
        """
        Get available period views for a statement type.

        Args:
            statement_type: Type of statement to get period views for

        Returns:
            List of period view options
        """
        return self.xbrl.get_period_views(statement_type)

    def get_by_category(self, category: str) -> List[Statement]:
        """
        Get all statements of a specific category.

        Args:
            category: Category of statement to find ('statement', 'note', 'disclosure', 'document', or 'other')

        Returns:
            List of Statement objects matching the category
        """
        result = []

        # Find all statements with matching category
        for stmt in self.statements:
            if self.classify_statement(stmt) == category:
                result.append(Statement(self.xbrl, stmt['role']))

        return result

    def notes(self) -> List[Statement]:
        """
        Get all note sections.

        Returns:
            List of Statement objects for notes
        """
        return self.get_by_category('note')

    def disclosures(self) -> List[Statement]:
        """
        Get all disclosure sections.

        Returns:
            List of Statement objects for disclosures
        """
        return self.get_by_category('disclosure')

    def _make_statement(self, stmt: dict) -> Statement:
        """Create a Statement from a statement dict, resolving canonical type."""
        canonical_type = stmt.get('type') if stmt.get('type') in statement_to_concepts else None
        return Statement(self.xbrl, stmt['role'], canonical_type=canonical_type)

    def all(self, category: str = None) -> List[Statement]:
        """
        Get all statements as Statement objects, optionally filtered by category.

        Args:
            category: Optional category filter ('statement', 'note', 'disclosure', 'document', or 'other')

        Returns:
            List of Statement objects
        """
        results = []
        for stmt in self.statements:
            if category and self.classify_statement(stmt) != category:
                continue
            results.append(self._make_statement(stmt))
        return results

    def list_available(self, category: str = None) -> pd.DataFrame:
        """
        List all available statements as a DataFrame for browsing.

        Args:
            category: Optional category filter ('statement', 'note', 'disclosure', 'document', or 'other')

        Returns:
            DataFrame with columns: index, category, name, role_name, element_count
        """
        rows = []
        for index, stmt in enumerate(self.statements):
            stmt_category = self.classify_statement(stmt)
            if category and stmt_category != category:
                continue
            rows.append({
                'index': index,
                'category': stmt_category,
                'name': stmt.get('definition', ''),
                'role_name': stmt.get('role_name', ''),
                'element_count': stmt.get('element_count', 0),
            })
        return pd.DataFrame(rows)

    def search(self, keyword: str) -> List[Statement]:
        """
        Search for statements by keyword across definition, role_name, and type.

        Space-separated words use AND logic, case-insensitive.

        Args:
            keyword: Search keyword(s), e.g. 'debt', 'long term debt', 'revenue'

        Returns:
            List of matching Statement objects
        """
        if not keyword or not keyword.strip():
            return []
        words = keyword.lower().split()
        results = []
        for stmt in self.statements:
            searchable = ' '.join([
                stmt.get('definition') or '',
                stmt.get('role_name') or '',
                stmt.get('type') or '',
            ]).lower()
            if all(word in searchable for word in words):
                results.append(self._make_statement(stmt))
        return results

    def get(self, name: str) -> Optional[Statement]:
        """
        Get a statement by name with smart resolution.

        Searches in order: exact type match, role_name contains, definition contains.
        Returns the first match or None.

        Args:
            name: Statement name to search for (e.g. 'IncomeStatement', 'cash flow', 'debt')

        Returns:
            Statement if found, None otherwise
        """
        if not name or not name.strip():
            return None
        name_lower = name.lower()

        # Tier 1: Exact type match
        for stmt in self.statements:
            if (stmt.get('type') or '').lower() == name_lower:
                return self._make_statement(stmt)

        # Tier 2: role_name contains (case-insensitive)
        for stmt in self.statements:
            if name_lower in (stmt.get('role_name') or '').lower():
                return self._make_statement(stmt)

        # Tier 3: definition contains (case-insensitive)
        for stmt in self.statements:
            if name_lower in (stmt.get('definition') or '').lower():
                return self._make_statement(stmt)

        return None

    def to_dataframe(self,
                     statement_type: str,
                     period_view: Optional[str] = None,
                     standard: bool = True,
                     include_dimensions: bool = False) -> Optional[pd.DataFrame]:
        """
        Convert a statement to a pandas DataFrame.

        Args:
            statement_type: Type of statement to convert
            period_view: Optional period view name
            standard: Whether to use standardized concept labels (default: True)
            include_dimensions: Whether to include dimensional segment data (default: False)

        Returns:
            pandas DataFrame containing the statement data
        """
        statement = self[statement_type]
        return statement.render(period_view=period_view, standard=standard, include_dimensions=include_dimensions).to_dataframe()


class StitchedStatement:
    """
    A stitched financial statement across multiple time periods.

    This class provides convenient methods for rendering and manipulating a stitched
    financial statement from multiple filings.
    """

    def __init__(self, xbrls, statement_type: str, max_periods: int = 8, standard: bool = True,
                 use_optimal_periods: bool = True, include_dimensions: bool = False,
                 view: ViewType = None):
        """
        Initialize with XBRLS object and statement parameters.

        Args:
            xbrls: XBRLS object containing stitched data
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
            max_periods: Maximum number of periods to include
            standard: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            include_dimensions: Whether to include dimensional segment data (default: False for stitching)
            view: StatementView controlling dimensional filtering. If provided, overrides include_dimensions.
                  'detailed' → include_dimensions=True, 'standard'/'summary' → include_dimensions=False.
        """
        self.xbrls = xbrls
        self.statement_type = statement_type
        self.max_periods = max_periods
        self.standard = standard
        self.use_optimal_periods = use_optimal_periods
        # If view is provided, derive include_dimensions from it
        if view is not None:
            normalized = normalize_view(view)
            self.include_dimensions = (normalized == StatementView.DETAILED)
        else:
            self.include_dimensions = include_dimensions
        self.show_date_range = False  # Default to not showing date ranges

        # Statement titles
        self.statement_titles = {
            'BalanceSheet': 'CONSOLIDATED BALANCE SHEET',
            'IncomeStatement': 'CONSOLIDATED INCOME STATEMENT',
            'CashFlowStatement': 'CONSOLIDATED STATEMENT OF CASH FLOWS',
            'StatementOfEquity': 'CONSOLIDATED STATEMENT OF STOCKHOLDERS\' EQUITY',
            'ComprehensiveIncome': 'CONSOLIDATED STATEMENT OF COMPREHENSIVE INCOME'
        }
        self.title = self.statement_titles.get(statement_type, statement_type.upper())

        # Cache statement data
        self._statement_data = None

    @property
    def periods(self):
        return [
            period_id[-10:] for period_id, _ in self.statement_data['periods']
        ]

    @property
    def statement_data(self):
        """Get the underlying statement data, loading it if necessary."""
        if self._statement_data is None:
            self._statement_data = self.xbrls.get_statement(
                self.statement_type,
                self.max_periods,
                self.standard,
                self.use_optimal_periods,
                self.include_dimensions
            )
        return self._statement_data

    def render(self, show_date_range: bool = False) -> Table:
        """
        Render the stitched statement as a formatted table.

        Args:
            show_date_range: Whether to show full date ranges for duration periods

        Returns:
            Rich Table containing the rendered statement
        """
        from edgar.xbrl.stitching import render_stitched_statement

        # Update the render_stitched_statement function call to pass the show_date_range parameter
        return render_stitched_statement(
            self.statement_data,
            statement_title=self.title,
            statement_type=self.statement_type,
            entity_info=self.xbrls.entity_info,
            show_date_range=show_date_range
        )

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert the stitched statement to a pandas DataFrame.

        Returns:
            pandas DataFrame with periods as columns and concepts as rows
        """
        from edgar.xbrl.stitching import to_pandas

        return to_pandas(self.statement_data)

    def __rich__(self):
        """
        Rich console representation.

        Returns:
            Rich Table object
        """
        return self.render()

    def __repr__(self):
        return repr_rich(self.__rich__())


class StitchedStatements:
    """
    User-friendly access to stitched financial statements across multiple time periods.

    This class provides a simplified API for accessing and rendering stitched financial
    statements from multiple filings, without requiring detailed knowledge of the
    underlying stitching process.
    """

    def __init__(self, xbrls):
        """
        Initialize with an XBRLS object.

        Args:
            xbrls: The XBRLS object to extract stitched statements from
        """
        self.xbrls = xbrls

    def balance_sheet(self, max_periods: int = 8, standard: bool = True,
                      use_optimal_periods: bool = True, show_date_range: bool = False,
                      include_dimensions: bool = False, view: ViewType = None) -> Optional[StitchedStatement]:
        """
        Get a stitched balance sheet across multiple time periods.

        Args:
            max_periods: Maximum number of periods to include
            standard: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            show_date_range: Whether to show full date ranges for duration periods
            include_dimensions: Whether to include dimensional segment data (default: False)
            view: StatementView controlling dimensional filtering. Overrides include_dimensions if provided.

        Returns:
            StitchedStatement for the balance sheet
        """
        statement = StitchedStatement(self.xbrls, 'BalanceSheet', max_periods, standard,
                                     use_optimal_periods, include_dimensions, view=view)
        if show_date_range:
            statement.show_date_range = show_date_range
        return statement

    def income_statement(self, max_periods: int = 8, standard: bool = True,
                         use_optimal_periods: bool = True, show_date_range: bool = False,
                         include_dimensions: bool = False, view: ViewType = None) -> Optional[StitchedStatement]:
        """
        Get a stitched income statement across multiple time periods.

        Args:
            max_periods: Maximum number of periods to include
            standard: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            show_date_range: Whether to show full date ranges for duration periods
            include_dimensions: Whether to include dimensional segment data (default: False)
            view: StatementView controlling dimensional filtering. Overrides include_dimensions if provided.

        Returns:
            StitchedStatement for the income statement
        """
        statement = StitchedStatement(self.xbrls, 'IncomeStatement', max_periods, standard,
                                     use_optimal_periods, include_dimensions, view=view)
        if show_date_range:
            statement.show_date_range = show_date_range
        return statement

    def cashflow_statement(self, max_periods: int = 8, standard: bool = True,
                           use_optimal_periods: bool = True, show_date_range: bool = False,
                           include_dimensions: bool = False, view: ViewType = None) -> Optional[StitchedStatement]:
        """
        Get a stitched cash flow statement across multiple time periods.

        Args:
            max_periods: Maximum number of periods to include
            standard: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            show_date_range: Whether to show full date ranges for duration periods
            include_dimensions: Whether to include dimensional segment data (default: False)
            view: StatementView controlling dimensional filtering. Overrides include_dimensions if provided.

        Returns:
            StitchedStatement for the cash flow statement
        """
        statement = StitchedStatement(self.xbrls, 'CashFlowStatement', max_periods, standard,
                                     use_optimal_periods, include_dimensions, view=view)
        if show_date_range:
            statement.show_date_range = show_date_range
        return statement

    def cash_flow_statement(self, **kwargs):
        """Alias for cashflow_statement()."""
        return self.cashflow_statement(**kwargs)

    def statement_of_equity(self, max_periods: int = 8, standard: bool = True,
                            use_optimal_periods: bool = True, show_date_range: bool = False,
                            include_dimensions: bool = True, view: ViewType = None) -> Optional[StitchedStatement]:
        """
        Get a stitched statement of changes in equity across multiple time periods.

        Args:
            max_periods: Maximum number of periods to include
            standard: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            show_date_range: Whether to show full date ranges for duration periods
            include_dimensions: Whether to include dimensional segment data (default: True for
                              Statement of Equity since it's an inherently dimensional statement
                              that tracks changes across equity components)
            view: StatementView controlling dimensional filtering. Overrides include_dimensions if provided.

        Returns:
            StitchedStatement for the statement of equity
        """
        statement = StitchedStatement(self.xbrls, 'StatementOfEquity', max_periods, standard,
                                     use_optimal_periods, include_dimensions, view=view)
        if show_date_range:
            statement.show_date_range = show_date_range
        return statement

    def comprehensive_income(self, max_periods: int = 8, standard: bool = True,
                             use_optimal_periods: bool = True, show_date_range: bool = False,
                             include_dimensions: bool = True, view: ViewType = None) -> Optional[StitchedStatement]:
        """
        Get a stitched statement of comprehensive income across multiple time periods.

        Args:
            max_periods: Maximum number of periods to include
            standard: Whether to use standardized concept labels
            use_optimal_periods: Whether to use entity info to determine optimal periods
            show_date_range: Whether to show full date ranges for duration periods
            include_dimensions: Whether to include dimensional segment data (default: True for
                              Comprehensive Income since it's an inherently dimensional statement
                              that tracks components of other comprehensive income)
            view: StatementView controlling dimensional filtering. Overrides include_dimensions if provided.

        Returns:
            StitchedStatement for the comprehensive income statement
        """
        statement = StitchedStatement(self.xbrls, 'ComprehensiveIncome', max_periods, standard,
                                     use_optimal_periods, include_dimensions, view=view)
        if show_date_range:
            statement.show_date_range = show_date_range
        return statement

    def __getitem__(self, statement_type: str) -> StitchedStatement:
        """
        Get a statement by type using dictionary syntax.

        Args:
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)

        Returns:
            StitchedStatement for the requested statement type
        """
        return StitchedStatement(self.xbrls, statement_type, use_optimal_periods=True)

    def __rich__(self):
        """
        Rich console representation.

        Returns:
            Rich Table object
        """
        table = Table(title="Available Stitched Statements", box=box.SIMPLE)
        table.add_column("Statement Type")
        table.add_column("Periods")

        # Get information about available statements
        statement_types = set()
        for xbrl in self.xbrls.xbrl_list:
            statements = xbrl.get_all_statements()
            for stmt in statements:
                if stmt['type']:
                    statement_types.add(stmt['type'])

        # Get periods
        periods = self.xbrls.get_periods()
        period_count = len(periods)

        # Add rows for each statement type
        for stmt_type in sorted(statement_types):
            table.add_row(stmt_type, str(period_count))

        return table

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self) -> str:
        """
        String representation listing available statements.

        Returns:
            String representation
        """
        # Get information about available statements
        statement_types = set()
        for xbrl in self.xbrls.xbrl_list:
            statements = xbrl.get_all_statements()
            for stmt in statements:
                if stmt['type']:
                    statement_types.add(stmt['type'])

        # Get information about periods
        periods = self.xbrls.get_periods()
        period_count = len(periods)

        # Format output
        output = [f"Stitched statements across {period_count} periods:"]
        for stmt_type in sorted(statement_types):
            output.append(f"  - {stmt_type}")

        output.append("\nAvailable methods:")
        output.append("  - balance_sheet()")
        output.append("  - income_statement()")
        output.append("  - cash_flow_statement()")

        return "\n".join(output)
