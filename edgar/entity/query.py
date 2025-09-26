"""
Query interface for the Entity Facts API.

This module provides a fluent query builder for filtering and analyzing
financial facts with AI-ready features.
"""

import re
from collections import defaultdict
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

import pandas as pd
from rich.box import SIMPLE, SIMPLE_HEAVY
from rich.console import Group
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.entity.models import DataQuality, FinancialFact

if TYPE_CHECKING:
    from edgar.entity.statement import FinancialStatement
    from edgar.enums import PeriodType


class FactQuery:
    """
    Fluent query builder for financial facts with AI-ready features.

    This class provides a chainable interface for building complex queries
    against financial facts, with support for filtering, sorting, and
    transforming results.
    """

    def __init__(self, facts: List[FinancialFact], indices: Dict[str, Dict]):
        """
        Initialize the query builder.

        Args:
            facts: List of all available facts
            indices: Pre-computed indices for efficient filtering
        """
        self._all_facts = facts
        self._indices = indices
        self._filters: List[Callable] = []
        self._sort_field: Optional[str] = None
        self._sort_ascending: bool = True
        self._limit: Optional[int] = None

    # Concept filtering
    def by_concept(self, concept: str, exact: bool = False) -> 'FactQuery':
        """
        Filter by concept name or pattern.

        Args:
            concept: Concept name or label to match
            exact: If True, require exact match; otherwise, use fuzzy matching

        Returns:
            Self for method chaining
        """
        if exact:
            # Use index for exact matching
            matching_facts = self._indices['by_concept'].get(concept, [])
            fact_ids = {id(f) for f in matching_facts}
            self._filters.append(lambda f: id(f) in fact_ids)
        else:
            # Case-insensitive partial matching
            concept_lower = concept.lower()
            self._filters.append(
                lambda f: concept_lower in f.concept.lower() or 
                         (f.label and concept_lower in f.label.lower())
            )
        return self

    def by_label(self, label: str, fuzzy: bool = True) -> 'FactQuery':
        """
        Filter by human-readable label.

        Args:
            label: Label to match
            fuzzy: If True, use fuzzy matching; otherwise, exact match

        Returns:
            Self for method chaining
        """
        if fuzzy:
            label_lower = label.lower()
            self._filters.append(lambda f: f.label and label_lower in f.label.lower())
        else:
            self._filters.append(lambda f: f.label == label)
        return self

    def by_text(self, pattern: str) -> 'FactQuery':
        """
        Search across concept names, labels, and other text fields for a pattern.

        This is a flexible search that looks for the pattern in all relevant text fields
        of the financial facts using case-insensitive regex matching.

        Args:
            pattern: Pattern to search for in various text fields (supports regex)

        Returns:
            Self for method chaining

        Example:
            # Find all revenue-related facts
            facts.query().by_text("revenue|sales")

            # Find facts with "cash" in any text field
            facts.query().by_text("cash")
        """
        regex = re.compile(pattern, re.IGNORECASE)

        def text_filter(fact):
            # Search in concept name
            if fact.concept and regex.search(fact.concept):
                return True

            # Search in label
            if fact.label and regex.search(fact.label):
                return True

            # Search in taxonomy (namespace)
            if fact.taxonomy and regex.search(fact.taxonomy):
                return True

            # Search in business context if available
            if hasattr(fact, 'business_context') and fact.business_context and regex.search(fact.business_context):
                return True

            # Search in statement type if available
            if fact.statement_type and regex.search(fact.statement_type):
                return True

            return False

        self._filters.append(text_filter)
        return self

    # Time-based filtering
    def by_fiscal_year(self, year: int) -> 'FactQuery':
        """
        Filter by fiscal year.

        Args:
            year: Fiscal year to filter by

        Returns:
            Self for method chaining
        """
        matching_facts = self._indices['by_fiscal_year'].get(year, [])
        fact_ids = {id(f) for f in matching_facts}
        self._filters.append(lambda f: id(f) in fact_ids)
        return self

    def by_fiscal_period(self, period: str) -> 'FactQuery':
        """
        Filter by fiscal period (FY, Q1, Q2, Q3, Q4).

        Args:
            period: Fiscal period to filter by

        Returns:
            Self for method chaining
        """
        matching_facts = self._indices['by_fiscal_period'].get(period, [])
        fact_ids = {id(f) for f in matching_facts}
        self._filters.append(lambda f: id(f) in fact_ids)
        return self

    def by_period_length(self, months: int) -> 'FactQuery':
        """
        Filter by period length in months.

        This is useful to ensure you're comparing comparable periods
        (e.g., only quarterly data or only annual data).

        Args:
            months: Number of months (3 for quarterly, 9 for YTD, 12 for annual)

        Returns:
            Self for method chaining

        Example:
            # Get only quarterly (3-month) income statements
            facts.query().by_statement_type('IncomeStatement').by_period_length(3)
        """
        def matches_period_length(fact):
            if fact.period_start and fact.period_type == 'duration':
                month_diff = (fact.period_end.year - fact.period_start.year) * 12
                month_diff += fact.period_end.month - fact.period_start.month + 1
                # Allow for slight variations (e.g., 90-92 days counts as 3 months)
                return abs(month_diff - months) <= 1
            return False

        self._filters.append(matches_period_length)
        return self

    def by_period_type(self, period_type: Union[str, 'PeriodType']) -> 'FactQuery':
        """
        Filter by period type using PeriodType enum for enhanced developer experience.

        This method provides a convenient way to filter facts by common period types
        like annual, quarterly, and monthly periods using either PeriodType enum values
        or string equivalents.

        Args:
            period_type: Period type - either PeriodType enum or string equivalent
                        ('annual', 'quarterly', 'monthly')

        Returns:
            Self for method chaining

        Example:
            # Using PeriodType enum (recommended)
            from edgar.enums import PeriodType
            annual_facts = facts.query().by_period_type(PeriodType.ANNUAL).get()
            quarterly_facts = facts.query().by_period_type(PeriodType.QUARTERLY).get()

            # Using string equivalents (also supported)
            annual_facts = facts.query().by_period_type('annual').get()
            quarterly_facts = facts.query().by_period_type('quarterly').get()

        Note:
            TTM and YTD period types require special calculation logic and are not yet
            supported by this method. Use .by_period_length(12) for 12-month periods
            or implement custom TTM/YTD calculation logic.
        """
        # Import here to avoid circular imports
        try:
            from edgar.enums import validate_period_type
        except ImportError:
            # Fallback if enums not available
            def validate_period_type(p):
                if isinstance(p, str) and p.lower() in ['annual', 'quarterly', 'monthly']:
                    return p.lower()
                raise ValueError(f"Invalid period type: {p}")

        validated_period = validate_period_type(period_type)

        # Map period types to period lengths (in months)
        period_mapping = {
            'annual': 12,
            'quarterly': 3,
            'monthly': 1
        }

        if validated_period in period_mapping:
            # Delegate to existing by_period_length method
            return self.by_period_length(period_mapping[validated_period])
        elif validated_period in ['ttm', 'ytd']:
            # TTM and YTD require special calculation logic not yet implemented
            raise NotImplementedError(
                f"Period type '{validated_period}' requires calculation logic not yet implemented. "
                f"For trailing twelve months data, use .by_period_length(12) to get 12-month periods, "
                f"or use facts.income_statement(annual=False, periods=4) for quarterly aggregation."
            )
        else:
            # This shouldn't happen if validate_period_type works correctly
            raise ValueError(f"Unsupported period type: {validated_period}")

    def date_range(self, start: Union[date, str, None] = None, end: Union[date, str, None] = None) -> 'FactQuery':
        """
        Filter by date range.

        Args:
            start: Start date (inclusive). Can be a date object or string in 'YYYY-MM-DD' format
            end: End date (inclusive). Can be a date object or string in 'YYYY-MM-DD' format

        Returns:
            Self for method chaining

        Raises:
            ValueError: If neither start nor end is provided, or if date string format is invalid
        """
        if start is None and end is None:
            raise ValueError("At least one of start or end date must be provided")

        # Parse string dates to date objects
        def parse_date(date_value: Union[date, str, None]) -> Optional[date]:
            if date_value is None:
                return None
            if isinstance(date_value, date):
                return date_value
            if isinstance(date_value, str):
                try:
                    return datetime.strptime(date_value, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError(f"Invalid date format '{date_value}'. Expected 'YYYY-MM-DD'") from None
            raise ValueError(f"Invalid date type: {type(date_value)}. Expected date object or string")

        parsed_start = parse_date(start)
        parsed_end = parse_date(end)

        # Create filter based on provided dates
        if parsed_start is not None and parsed_end is not None:
            # Both start and end provided
            self._filters.append(
                lambda f: f.period_end and parsed_start <= f.period_end <= parsed_end
            )
        elif parsed_start is not None:
            # Only start provided - filter for dates >= start
            self._filters.append(
                lambda f: f.period_end and f.period_end >= parsed_start
            )
        else:
            # Only end provided - filter for dates <= end
            self._filters.append(
                lambda f: f.period_end and f.period_end <= parsed_end
            )

        return self

    def as_of(self, as_of_date: date) -> 'FactQuery':
        """
        Get facts as of a specific date (point-in-time).

        Args:
            as_of_date: Date to get facts as of

        Returns:
            Self for method chaining
        """
        self._filters.append(
            lambda f: f.filing_date and f.filing_date <= as_of_date
        )
        return self

    # Quality filtering
    def high_quality_only(self) -> 'FactQuery':
        """
        Filter to only high-quality, audited facts.

        Returns:
            Self for method chaining
        """
        self._filters.append(
            lambda f: f.data_quality == DataQuality.HIGH and f.is_audited
        )
        return self

    def min_confidence(self, threshold: float) -> 'FactQuery':
        """
        Filter by minimum confidence score.

        Args:
            threshold: Minimum confidence score (0.0 to 1.0)

        Returns:
            Self for method chaining
        """
        self._filters.append(lambda f: f.confidence_score >= threshold)
        return self

    # Statement and form filtering
    def by_statement_type(self, statement_type: str) -> 'FactQuery':
        """
        Filter by financial statement type.

        Args:
            statement_type: Statement type (BalanceSheet, IncomeStatement, CashFlow)

        Returns:
            Self for method chaining
        """
        matching_facts = self._indices['by_statement'].get(statement_type, [])
        fact_ids = {id(f) for f in matching_facts}
        self._filters.append(lambda f: id(f) in fact_ids)
        return self

    def by_form_type(self, form_type: Union[str, List[str]]) -> 'FactQuery':
        """
        Filter by SEC form type.

        Args:
            form_type: Form type(s) to filter by

        Returns:
            Self for method chaining
        """
        if isinstance(form_type, str):
            form_types = [form_type]
        else:
            form_types = form_type

        # Collect all matching facts from index
        matching_facts = []
        for form in form_types:
            matching_facts.extend(self._indices['by_form'].get(form, []))

        fact_ids = {id(f) for f in matching_facts}
        self._filters.append(lambda f: id(f) in fact_ids)
        return self

    # Special queries
    def latest_instant(self) -> 'FactQuery':
        """
        Filter to only the most recent instant facts (for balance sheet items).

        Returns:
            Self for method chaining
        """
        self._filters.append(lambda f: f.period_type == 'instant')
        self._sort_field = 'period_end'
        self._sort_ascending = False

        # Group by concept and keep only latest
        def keep_latest(facts: List[FinancialFact]) -> List[FinancialFact]:
            latest_by_concept = {}
            for fact in facts:
                key = fact.concept
                if key not in latest_by_concept or fact.period_end > latest_by_concept[key].period_end:
                    latest_by_concept[key] = fact
            return list(latest_by_concept.values())

        # We'll apply this in execute()
        self._post_filter = keep_latest
        return self

    def latest_periods(self, n: int = 4, annual: bool = True) -> 'FactQuery':
        """
        Get facts from the n most recent periods.

        Args:
            n: Number of recent periods to include
            annual: If True, only use annual (FY) periods; if False, use all period types

        Returns:
            Self for method chaining
        """
        # First, get all unique periods
        all_facts = self._apply_current_filters()

        # Group facts by unique periods and calculate period info
        period_info = {}
        for fact in all_facts:
            period_key = (fact.fiscal_year, fact.fiscal_period)
            if period_key not in period_info:
                # Calculate period length if we have duration facts
                period_months = 12  # Default for FY
                if fact.period_start and fact.period_type == 'duration' and fact.period_end:
                    period_months = (fact.period_end.year - fact.period_start.year) * 12
                    period_months += fact.period_end.month - fact.period_start.month + 1

                period_info[period_key] = {
                    'end_date': fact.period_end or date.max,
                    'period_months': period_months,
                    'is_annual': fact.fiscal_period == 'FY',
                    'filing_date': fact.filing_date or date.min
                }

        # Create list of periods with their metadata
        period_list = []
        for period_key, info in period_info.items():
            period_list.append((period_key, info))

        if annual:
            # When annual=True, only use annual periods - no backfilling with interim periods
            annual_periods = [(pk, info) for pk, info in period_list if info['is_annual']]

            # Sort annual periods by fiscal year (newest first)
            annual_periods.sort(key=lambda x: x[0][0], reverse=True)  # Sort by fiscal_year

            # Select only annual periods, up to n
            selected_periods = [pk for pk, _ in annual_periods[:n]]
        else:
            # Sort all periods by end date (newest first)
            period_list.sort(key=lambda x: x[1]['end_date'], reverse=True)
            selected_periods = [pk for pk, _ in period_list[:n]]

        # Filter to only these periods
        self._filters.append(
            lambda f: (f.fiscal_year, f.fiscal_period) in selected_periods
        )
        return self

    # Enhanced filtering methods for structural metadata
    def by_section(self, section: str) -> 'FactQuery':
        """
        Filter by statement section (e.g., 'Current Assets', 'Operating Activities').

        Args:
            section: Section name to filter by

        Returns:
            Self for method chaining
        """
        section_lower = section.lower()
        self._filters.append(
            lambda f: f.section and section_lower in f.section.lower()
        )
        return self

    def by_depth(self, max_depth: int) -> 'FactQuery':
        """
        Filter by hierarchy depth in statement.

        Args:
            max_depth: Maximum depth to include

        Returns:
            Self for method chaining
        """
        self._filters.append(
            lambda f: f.depth is not None and f.depth <= max_depth
        )
        return self

    def totals_only(self) -> 'FactQuery':
        """
        Get only total/sum concepts.

        Returns:
            Self for method chaining
        """
        self._filters.append(lambda f: f.is_total)
        return self

    def concrete_only(self) -> 'FactQuery':
        """
        Exclude abstract/header concepts.

        Returns:
            Self for method chaining
        """
        self._filters.append(lambda f: not f.is_abstract)
        return self

    def abstracts_only(self) -> 'FactQuery':
        """
        Get only abstract/header concepts.

        Returns:
            Self for method chaining
        """
        self._filters.append(lambda f: f.is_abstract)
        return self

    def with_parent(self, parent_concept: str) -> 'FactQuery':
        """
        Filter by parent concept in hierarchy.

        Args:
            parent_concept: Parent concept name

        Returns:
            Self for method chaining
        """
        self._filters.append(
            lambda f: f.parent_concept and parent_concept in f.parent_concept
        )
        return self

    def root_items_only(self) -> 'FactQuery':
        """
        Get only root level items (no parent).

        Returns:
            Self for method chaining
        """
        self._filters.append(
            lambda f: f.parent_concept is None or f.depth == 0
        )
        return self

    # Sorting and limiting
    def sort_by(self, field: str, ascending: bool = True) -> 'FactQuery':
        """
        Sort results by field.

        Args:
            field: Field name to sort by
            ascending: Sort order

        Returns:
            Self for method chaining
        """
        self._sort_field = field
        self._sort_ascending = ascending
        return self

    def latest(self, n: int = 1) -> List[FinancialFact]:
        """
        Get the n most recent facts.

        Args:
            n: Number of facts to return

        Returns:
            List of facts
        """
        self._sort_field = 'filing_date'
        self._sort_ascending = False
        self._limit = n
        return self.execute()

    # Execution methods
    def execute(self) -> List[FinancialFact]:
        """
        Execute query and return matching facts.

        Returns:
            List of facts matching all filters
        """
        results = self._apply_current_filters()

        # Apply post-filter if set (e.g., for latest_instant)
        if hasattr(self, '_post_filter'):
            results = self._post_filter(results)

        # Apply sorting
        if self._sort_field:
            try:
                results.sort(
                    key=lambda f: getattr(f, self._sort_field) or (date.min if self._sort_field.endswith('date') else 0),
                    reverse=not self._sort_ascending
                )
            except AttributeError:
                pass  # Ignore if field doesn't exist

        # Apply limit
        if self._limit is not None:
            results = results[:self._limit]

        return results

    def with_hierarchy(self) -> 'HierarchicalFactsResult':
        """
        Return facts organized hierarchically based on parent-child relationships.

        Returns:
            HierarchicalFactsResult with tree structure
        """
        facts = self.execute()
        return HierarchicalFactsResult(facts)

    def to_dataframe(self, *columns) -> pd.DataFrame:
        """
        Convert results to pandas DataFrame.

        Args:
            columns: Optional list of columns to include

        Returns:
            DataFrame with query results
        """
        facts = self.execute()

        if not facts:
            return pd.DataFrame()

        # Convert to records
        records = []
        for fact in facts:
            record = {
                'concept': fact.concept,
                'label': fact.label,
                'value': fact.value,
                'numeric_value': fact.numeric_value,
                'unit': fact.unit,
                'scale': fact.scale,
                'period_start': fact.period_start,
                'period_end': fact.period_end,
                'period_type': fact.period_type,
                'fiscal_year': fact.fiscal_year,
                'fiscal_period': fact.fiscal_period,
                'filing_date': fact.filing_date,
                'form_type': fact.form_type,
                'accession': fact.accession,
                'data_quality': fact.data_quality.value,
                'confidence_score': fact.confidence_score,
                'is_audited': fact.is_audited,
                'is_estimated': fact.is_estimated,
                'statement_type': fact.statement_type
            }
            records.append(record)

        df = pd.DataFrame(records)

        # Select columns if specified
        if columns:
            available_columns = [col for col in columns if col in df.columns]
            if available_columns:  # Only select if there are matching columns
                df = df[available_columns]

        return df

    def to_llm_context(self) -> List[Dict[str, Any]]:
        """
        Convert results to LLM-friendly context.

        Returns:
            List of fact contexts for LLM consumption
        """
        facts = self.execute()
        return [f.to_llm_context() for f in facts]

    def pivot_by_period(self, return_statement: bool = True) -> Union['FinancialStatement', pd.DataFrame]:
        """
        Pivot facts to show concepts as rows and periods as columns.

        This method automatically deduplicates facts to ensure each concept
        has only one value per period in the resulting pivot table.

        Args:
            return_statement: If True, return FinancialStatement wrapper; 
                            if False, return raw DataFrame

        Returns:
            FinancialStatement or DataFrame with concepts as rows and periods as columns
        """
        # First deduplicate the facts to avoid pivot conflicts
        facts = self.execute()
        deduplicated_facts = self._deduplicate_facts(facts)

        if not deduplicated_facts:
            return pd.DataFrame()

        # Convert to DataFrame for pivoting
        records = []
        for fact in deduplicated_facts:
            # Generate professional period label
            period_label = self._format_period_label(fact)

            records.append({
                'label': fact.label,
                'numeric_value': fact.numeric_value,
                'period_key': period_label,
                'period_end': fact.period_end,
                'fiscal_period': fact.fiscal_period
            })

        df = pd.DataFrame(records)

        if df.empty:
            return df

        # Pivot table
        pivot = df.pivot_table(
            index='label',
            columns='period_key',
            values='numeric_value',
            aggfunc='first'  # Should be unique after deduplication
        )

        # Sort columns by period (newest first)
        # Create a mapping of column names to sort keys
        column_sort_keys = {}
        for _, row in df[['period_key', 'period_end', 'fiscal_period']].drop_duplicates().iterrows():
            key = row['period_key']
            end_date = row['period_end']
            fiscal_period = row['fiscal_period']

            # Sort by date, with annual periods last
            # Handle None dates
            if end_date is None:
                sort_key = (date.min, 0)
            elif fiscal_period == 'FY':
                sort_key = (end_date, 5)
            else:
                sort_key = (end_date, 0)
            column_sort_keys[key] = sort_key

        # Sort columns by date (newest first)
        sorted_columns = sorted(pivot.columns, 
                              key=lambda x: column_sort_keys.get(x, (date.min, 0)), 
                              reverse=True)
        pivot = pivot[sorted_columns]

        # Check for period consistency based on ACTUAL displayed periods, not all facts
        displayed_period_types = set()
        for col in pivot.columns:
            if 'FY' in col:
                displayed_period_types.add('12M')
            elif any(q in col for q in ['Q1', 'Q2', 'Q3', 'Q4']):
                displayed_period_types.add('3M')
            elif '9M' in col:
                displayed_period_types.add('9M')
            elif '6M' in col:
                displayed_period_types.add('6M')
            else:
                # Try to infer from the fiscal_period in the original data
                matching_rows = df[df['period_key'] == col]
                if not matching_rows.empty:
                    fp = matching_rows.iloc[0]['fiscal_period']
                    if fp == 'FY':
                        displayed_period_types.add('12M')
                    elif fp in ['Q1', 'Q2', 'Q3', 'Q4']:
                        displayed_period_types.add('3M')

        # Only warn if there are actually mixed period types in the displayed data
        if len(displayed_period_types) > 1:
            pivot.attrs['mixed_periods'] = True
            pivot.attrs['period_lengths'] = sorted(list(displayed_period_types))
        else:
            pivot.attrs['mixed_periods'] = False
            pivot.attrs['period_lengths'] = list(displayed_period_types) if displayed_period_types else []

        # Return appropriate format
        if return_statement:
            from edgar.entity.statement import FinancialStatement

            # Determine statement type from facts
            statement_types = {f.statement_type for f in deduplicated_facts if f.statement_type}
            statement_type = list(statement_types)[0] if len(statement_types) == 1 else "Statement"

            # Get entity name from facts (if available)
            entity_name = ""  # Could be passed in or extracted from facts

            return FinancialStatement(
                data=pivot,
                statement_type=statement_type,
                entity_name=entity_name,
                period_lengths=pivot.attrs.get('period_lengths', []),
                mixed_periods=pivot.attrs.get('mixed_periods', False)
            )
        else:
            # Set display format to avoid scientific notation for raw DataFrame
            pd.options.display.float_format = '{:,.0f}'.format
            return pivot

    def _format_period_label(self, fact: FinancialFact) -> str:
        """
        Format period label for professional investors.

        Hedge funds and institutional investors typically expect:
        - Quarterly (3M): "Q2 2024" 
        - Year-to-date (9M): "9M 2024" or "YTD Q3 2024"
        - Annual (12M): "FY 2024"
        - Clear indication of period length

        Args:
            fact: The financial fact to format

        Returns:
            Professional period label
        """
        if not fact.period_end:
            return f"{fact.fiscal_period} {fact.fiscal_year}"

        # Get the end date components
        end_date = fact.period_end
        year = end_date.year

        # PRIORITY: If the fiscal_period is explicitly "FY", trust it
        if fact.fiscal_period == 'FY':
            return f"FY {year}"

        # Calculate period length in months if we have start date for duration periods
        if fact.period_start and fact.period_type == 'duration':
            # Calculate the number of months in the period
            months_diff = (fact.period_end.year - fact.period_start.year) * 12
            months_diff += fact.period_end.month - fact.period_start.month
            # Add 1 to include both start and end months
            months_diff += 1

            # Determine period type based on length
            if months_diff <= 3:
                # Standard quarterly period (3 months)
                end_month = end_date.month
                if end_month in [1, 2, 3]:
                    quarter = 'Q1'
                elif end_month in [4, 5, 6]:
                    quarter = 'Q2'
                elif end_month in [7, 8, 9]:
                    quarter = 'Q3'
                else:
                    quarter = 'Q4'
                return f"{quarter} {year}"

            elif months_diff <= 6:
                # Half-year period
                return f"6M {year}"

            elif months_diff <= 9:
                # Year-to-date through Q3 (9 months)
                return f"9M {year}"

            elif months_diff >= 11:
                # Full year (allow 11-13 months for fiscal year variations)
                return f"FY {year}"

            else:
                # Non-standard period - show actual months
                return f"{months_diff}M {year}"

        # Fallback for instant facts or when no start date - use calendar-based quarters
        if fact.fiscal_period in ['Q1', 'Q2', 'Q3', 'Q4']:
            # Use calendar-based quarter determination from end date
            end_month = end_date.month
            if end_month in [1, 2, 3]:
                quarter = 'Q1'
            elif end_month in [4, 5, 6]:
                quarter = 'Q2'
            elif end_month in [7, 8, 9]:
                quarter = 'Q3'
            else:
                quarter = 'Q4'
            return f"{quarter} {year}"
        elif fact.fiscal_period == 'FY':
            return f"FY {year}"
        else:
            return f"{fact.fiscal_period} {year}"

    # Helper methods
    def _apply_current_filters(self) -> List[FinancialFact]:
        """Apply all current filters to the facts"""
        results = self._all_facts

        for filter_func in self._filters:
            results = [f for f in results if filter_func(f)]

        return results

    def count(self) -> int:
        """
        Get count of facts matching current filters.

        Returns:
            Number of matching facts
        """
        return len(self._apply_current_filters())

    def _deduplicate_facts(self, facts: List[FinancialFact]) -> List[FinancialFact]:
        """
        Remove duplicate facts for the same concept and period.

        When multiple facts exist for the same concept and period, this method
        selects the most appropriate one based on:
        1. Most recent filing date
        2. Preference for audited (10-K) over unaudited (10-Q) forms
        3. Original forms over amendments

        Args:
            facts: List of facts that may contain duplicates

        Returns:
            List of deduplicated facts
        """
        from collections import defaultdict

        # Group facts by concept and period
        grouped = defaultdict(list)
        for fact in facts:
            # Create a key that uniquely identifies the concept and period
            if fact.period_type == 'instant':
                period_key = (fact.concept, fact.period_end, 'instant')
            else:
                period_key = (fact.concept, fact.period_start, fact.period_end, 'duration')
            grouped[period_key].append(fact)

        # Select the best fact from each group
        deduplicated = []
        for group_facts in grouped.values():
            if len(group_facts) == 1:
                deduplicated.append(group_facts[0])
            else:
                # Sort by criteria (descending priority):
                # 1. Filing date (most recent first)
                # 2. Form type (10-K preferred over 10-Q)
                # 3. Non-amendments preferred
                sorted_facts = sorted(
                    group_facts,
                    key=lambda f: (
                        f.filing_date or date.min,
                        1 if f.form_type == '10-K' else 0,
                        0 if '/A' in f.form_type else 1
                    ),
                    reverse=True
                )
                deduplicated.append(sorted_facts[0])

        return deduplicated

    def __rich__(self):
        """Creates a rich representation showing the most useful facts information."""


        # Get the facts for this query
        facts = self.execute()

        # Title with count
        title = Text.assemble(
            "🔍 ",
            ("Query Results", "bold blue"),
            f" ({len(facts):,} facts)"
        )

        if not facts:
            # Empty results
            empty_panel = Panel(
                Text("No facts matching the current filters", style="dim"),
                title=title,
                border_style="blue"
            )
            return empty_panel

        # Limit results for display (show first 20, indicate if more exist)
        display_limit = 40
        display_facts = facts[:display_limit]
        has_more = len(facts) > display_limit

        # Create main results table
        results_table = Table(box=SIMPLE, show_header=True, padding=(0, 1))
        results_table.add_column("Concept", style="bold", max_width=80)
        results_table.add_column("Label", style="bold", max_width=80)
        results_table.add_column("Value", justify="right", max_width=15)
        results_table.add_column("Start")
        results_table.add_column("End", max_width=10)

        # Add rows
        for fact in display_facts:

            results_table.add_row(
                fact.concept,
                fact.label,
                str(fact.value) if fact.value else "N/A",
                str(fact.period_start) if fact.period_start else "N/A",
                str(fact.period_end) if fact.period_end else "N/A",
            )

        # Summary stats table
        stats_table = Table(box=SIMPLE_HEAVY, show_header=False, padding=(0, 1))
        stats_table.add_column("Metric", style="dim")
        stats_table.add_column("Value", style="bold")

        # Calculate stats
        unique_concepts = len(set(f.concept for f in facts))
        unique_periods = len(set((f.fiscal_year, f.fiscal_period) for f in facts if f.fiscal_year and f.fiscal_period))
        form_types = set(f.form_type for f in facts if f.form_type)

        # Get date range
        dates = [f.filing_date for f in facts if f.filing_date]
        if dates:
            date_range = f"{min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')}"
        else:
            date_range = "N/A"

        stats_table.add_row("Total Facts", f"{len(facts):,}")
        stats_table.add_row("Unique Concepts", f"{unique_concepts:,}")
        stats_table.add_row("Unique Periods", f"{unique_periods:,}")
        stats_table.add_row("Form Types", ", ".join(sorted(form_types)[:3]) + ("..." if len(form_types) > 3 else ""))
        stats_table.add_row("Date Range", date_range)

        stats_panel = Panel(
            stats_table,
            title="📊 Query Summary",
            border_style="bright_black"
        )

        # Main results panel
        if has_more:
            subtitle = f"Showing first {display_limit:,} of {len(facts):,} facts • Use .to_dataframe() for all results"
        else:
            subtitle = f"All {len(facts):,} facts shown"

        results_panel = Panel(
            results_table,
            title="📋 Facts",
            subtitle=subtitle,
            border_style="bright_black"
        )

        # Combine panels
        content = Group(
            Padding("", (1, 0, 0, 0)),
            stats_panel,
            results_panel
        )

        return Panel(
            content,
            title=title,
            border_style="blue"
        )

    def __repr__(self) -> str:
        """String representation using rich formatting."""
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())


class HierarchicalFactsResult:
    """
    Results organized in hierarchical tree structure.

    This class organizes facts based on parent-child relationships
    to provide a tree view of the data.
    """

    def __init__(self, facts: List[FinancialFact]):
        """
        Initialize with flat list of facts.

        Args:
            facts: List of financial facts to organize
        """
        self.facts = facts
        self._build_hierarchy()

    def _build_hierarchy(self):
        """Build hierarchical structure from facts."""
        # Create lookup maps
        self.fact_map = {}
        self.children_map = defaultdict(list)
        self.roots = []

        # First pass: create map and identify relationships
        for fact in self.facts:
            concept = fact.concept.split(':')[-1] if ':' in fact.concept else fact.concept
            self.fact_map[concept] = fact

            if fact.parent_concept:
                self.children_map[fact.parent_concept].append(concept)
            elif fact.depth == 0 or fact.depth is None:
                self.roots.append(concept)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to nested dictionary structure."""
        def build_node(concept: str) -> Dict[str, Any]:
            fact = self.fact_map.get(concept)
            if not fact:
                return {'concept': concept, 'error': 'Fact not found'}

            node = {
                'concept': concept,
                'label': fact.label,
                'value': fact.numeric_value,
                'is_abstract': fact.is_abstract,
                'is_total': fact.is_total,
                'section': fact.section,
                'depth': fact.depth
            }

            # Add children
            children = self.children_map.get(concept, [])
            if children:
                node['children'] = [build_node(child) for child in children]

            return node

        return {
            'roots': [build_node(root) for root in self.roots],
            'total_facts': len(self.facts)
        }

    def to_dataframe(self, include_hierarchy: bool = True) -> pd.DataFrame:
        """
        Convert to DataFrame with optional hierarchy indicators.

        Args:
            include_hierarchy: Whether to include hierarchy columns

        Returns:
            DataFrame with facts and hierarchy info
        """
        records = []

        def process_node(concept: str, level: int = 0, parent: str = None):
            fact = self.fact_map.get(concept)
            if not fact:
                return

            record = {
                'concept': concept,
                'label': fact.label,
                'value': fact.numeric_value,
                'unit': fact.unit,
                'fiscal_year': fact.fiscal_year,
                'fiscal_period': fact.fiscal_period
            }

            if include_hierarchy:
                record['level'] = level
                record['parent'] = parent
                record['is_abstract'] = fact.is_abstract
                record['is_total'] = fact.is_total
                record['section'] = fact.section

            records.append(record)

            # Process children
            for child in self.children_map.get(concept, []):
                process_node(child, level + 1, concept)

        # Process all roots
        for root in self.roots:
            process_node(root)

        # Add orphaned facts (not in hierarchy)
        processed = set(r['concept'] for r in records)
        for fact in self.facts:
            concept = fact.concept.split(':')[-1] if ':' in fact.concept else fact.concept
            if concept not in processed:
                record = {
                    'concept': concept,
                    'label': fact.label,
                    'value': fact.numeric_value,
                    'unit': fact.unit,
                    'fiscal_year': fact.fiscal_year,
                    'fiscal_period': fact.fiscal_period
                }
                if include_hierarchy:
                    record['level'] = 0
                    record['parent'] = None
                    record['is_abstract'] = fact.is_abstract
                    record['is_total'] = fact.is_total
                    record['section'] = fact.section
                records.append(record)

        return pd.DataFrame(records) if records else pd.DataFrame()
