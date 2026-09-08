"""
XBRL Statement Stitching - Query Functionality

This module provides query functionality for stitched XBRL facts, allowing
users to query standardized, multi-period financial data.
"""

import re
from collections import defaultdict

from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd
from rich import box
from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.datatools import STR_DTYPE, apply_declared_schema, empty_declared_frame
from edgar.richtools import repr_rich
from edgar.xbrl.core import decimals_for_scaling
from edgar.xbrl.facts import FactQuery, _apply_transformations

if TYPE_CHECKING:
    from edgar.xbrl.stitching.xbrls import XBRLS


# Columns StitchedFactQuery.to_dataframe() declares, in the order it emits them.
#
# The rule (engineering/decisions/facts-dataframe-schema.md, beads edgartools-rsyt
# and edgartools-7wtj, extended here by edgartools-trhe): the column set is a
# function of the query's configuration, never of the rows that came back.
#
# This method is the third implementation of that construction and kept the
# `dropna(axis=1, how='all')` the other two had removed. Measured across five
# stitched pairs (AAPL, KO, MSFT), it deleted a column on every filer:
# `by_statement_type('IncomeStatement')` lost `period_instant` 5 times out of 5,
# because income-statement rows are all durations, and
# `by_statement_type('BalanceSheet')` lost `period_start` 5 times out of 5,
# because balance-sheet rows are all instants. Narrowing to a statement is not a
# statement about which columns exist.
#
# Dtypes are the ones these columns hold today when rows populate them, so an
# empty result is dtype-identical to a populated one. No column needs pinning:
# unlike the two sibling paths, nothing here flips dtype across queries (0 flips
# over 15 query/filer combinations) — the record dict is built unconditionally and
# `value` is cast to str explicitly.
_STITCHED_COLUMNS: Dict[str, Any] = {
    'concept': STR_DTYPE,
    'label': STR_DTYPE,
    'original_label': STR_DTYPE,
    'value': STR_DTYPE,
    'numeric_value': 'float64',
    'period_start': STR_DTYPE,
    'period_end': STR_DTYPE,
    'decimals': 'int64',
    'statement_type': STR_DTYPE,
    'fiscal_period': STR_DTYPE,
    'standard_concept': STR_DTYPE,
    'period_type': STR_DTYPE,
    'period_instant': STR_DTYPE,
    'period_label': STR_DTYPE,
    'level': 'int64',
    'is_abstract': 'bool',
    'is_total': 'bool',
    'filing_count': 'int64',
    'standardized': 'bool',
    'source_filing_index': 'Int64',
    'fiscal_year': STR_DTYPE,
}

# The dtype a column takes when no returned row populated it. Only the columns
# whose declared dtype cannot hold a null: casting an all-null column to `bool`
# yields False and to `int64` raises, so declaring those would make the one path
# that fabricates data the path taken when data is missing.
#
_STITCHED_NULL_DTYPES = {
    'decimals': 'Int64',
    'level': 'Int64',
    'filing_count': 'Int64',
    'is_abstract': 'boolean',
    'is_total': 'boolean',
    'standardized': 'boolean',
}

# `source_filing_index` is declared nullable `Int64` and pinned, rather than taking
# the int64 it infers when every row happens to have provenance.
# `_determine_source_filing` returns Optional[int], so nullable is what the column
# actually is, and without pinning it the empty frame and the populated frame
# disagree -- which is this bug again in the zero-row case.
#
# Pinning a populated column normally moves a null sentinel callers rely on, which
# is why the sibling paths hold theirs for 6.0. Not here: `dropna` deletes this
# column from every result today, so there is no dtype for a caller to be relying
# on and nothing to break.
_STITCHED_PINNED = frozenset({'source_filing_index'})

# Present on the fact dicts, deliberately not columns of the frame.
_STITCHED_SKIP_COLUMNS = frozenset({'fact_key', 'period_key'})


class StitchedFactsView:
    """
    A view over stitched facts from multiple XBRL filings.

    This class extracts facts from stitched statements rather than raw XBRL facts,
    ensuring that queries operate on standardized, post-processed data.
    """

    def __init__(self, xbrls: 'XBRLS'):
        self.xbrls = xbrls
        self._facts_cache = None
        self._last_cache_key = None
        # period_id -> index of the filing it came from, as resolved by the stitcher.
        self._period_sources: Dict[str, int] = {}

    def __len__(self):
        return len(self.get_facts())

    @property
    def entity_name(self):
        """Get entity name from the most recent XBRL filing."""
        if self.xbrls.xbrl_list:
            return getattr(self.xbrls.xbrl_list[0], 'entity_name', 'Unknown Entity')
        return 'Unknown Entity'

    @property
    def document_type(self):
        """Get document type from entity info."""
        return self.xbrls.entity_info.get('document_type', 'Multi-Period Stitched')

    def get_facts(self,
                  max_periods: int = 8,
                  standard: bool = True,
                  statement_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Extract facts from stitched statements.

        Args:
            max_periods: Maximum periods to include
            standard: Whether to use standardized labels
            statement_types: List of statement types to include

        Returns:
            List of fact dictionaries with stitched/standardized data
        """
        # Create cache key
        cache_key = (max_periods, standard, tuple(statement_types or []))
        if self._facts_cache and self._last_cache_key == cache_key:
            return self._facts_cache

        statement_types = statement_types or [
            'IncomeStatement', 'BalanceSheet', 'CashFlowStatement',
            'StatementOfEquity', 'ComprehensiveIncome'
        ]

        all_facts = []

        for statement_type in statement_types:
            try:
                # Get stitched statement data (this applies standardization)
                stitched_data = self.xbrls.get_statement(
                    statement_type=statement_type,
                    max_periods=max_periods,
                    standard=standard
                )

                # Extract facts from stitched data
                facts = self._extract_facts_from_stitched_data(
                    stitched_data, statement_type
                )
                all_facts.extend(facts)

            except Exception:
                # Skip statements that can't be stitched
                continue

        # Cache results
        self._facts_cache = all_facts
        self._last_cache_key = cache_key

        return all_facts

    def _extract_facts_from_stitched_data(self,
                                          stitched_data: Dict[str, Any],
                                          statement_type: str) -> List[Dict[str, Any]]:
        """
        Convert stitched statement data back to fact-like records for querying.

        Args:
            stitched_data: Output from StatementStitcher
            statement_type: Type of statement

        Returns:
            List of fact dictionaries
        """
        facts = []
        periods = stitched_data.get('periods', [])
        statement_data = stitched_data.get('statement_data', [])
        # Provenance for the periods in THIS stitched statement, as the stitcher
        # resolved it. Merged rather than replaced: get_facts() stitches each
        # statement type separately and a period can appear in more than one.
        self._period_sources.update(stitched_data.get('period_sources', {}) or {})

        for item in statement_data:
            # Skip abstract items without values
            if item.get('is_abstract', False) and not item.get('has_values', False):
                continue

            concept = item.get('concept', '')
            label = item.get('label', '')
            original_label = item.get('original_label', label)

            # Create a fact record for each period with data
            for period_id, value in item.get('values', {}).items():
                if value is None:
                    continue

                # Find period metadata
                period_info = self._get_period_info(period_id, periods)

                fact = {
                    # Core identification
                    'concept': concept,
                    'label': label,  # Standardized label
                    'original_label': original_label,  # Original company label
                    'standard_concept': item.get('standard_concept'),
                    'statement_type': statement_type,

                    # Value information
                    'value': value,
                    'numeric_value': self._convert_to_numeric(value),
                    # This frame declares 'decimals' as an integer column, so
                    # the 'INF' sentinel a statement now carries (GH #1229) is
                    # coerced here rather than breaking the declared schema.
                    'decimals': decimals_for_scaling(item.get('decimals', {}).get(period_id)),

                    # Period information
                    'period_key': period_id,
                    'period_type': period_info.get('period_type', 'duration'),
                    'period_start': period_info.get('period_start'),
                    'period_end': period_info.get('period_end'),
                    'period_instant': period_info.get('period_instant'),
                    'period_label': period_info.get('period_label', ''),

                    # Statement context
                    'level': item.get('level', 0),
                    'is_abstract': item.get('is_abstract', False),
                    'is_total': item.get('is_total', False),

                    # Multi-filing context
                    'filing_count': len(self.xbrls.xbrl_list),
                    'standardized': True,  # Mark as coming from standardized data

                    # Source attribution (which XBRL filing this came from)
                    'source_filing_index': self._determine_source_filing(period_id),
                }

                # Add fiscal period info if available
                fiscal_info = self._extract_fiscal_info(period_id)
                fact.update(fiscal_info)

                facts.append(fact)

        return facts

    def _get_period_info(self, period_id: str, periods: List[tuple]) -> Dict[str, Any]:
        """Extract period metadata from period_id and periods list."""
        period_info = {}

        # Find matching period
        for pid, label in periods:
            if pid == period_id:
                period_info['period_label'] = label
                break

        # Parse period_id to extract dates and type
        if period_id.startswith('instant_'):
            period_info['period_type'] = 'instant'
            date_str = period_id.replace('instant_', '')
            period_info['period_instant'] = date_str
            period_info['period_end'] = date_str
        elif period_id.startswith('duration_'):
            period_info['period_type'] = 'duration'
            parts = period_id.replace('duration_', '').split('_')
            if len(parts) >= 2:
                period_info['period_start'] = parts[0]
                period_info['period_end'] = parts[1]

        return period_info

    def _convert_to_numeric(self, value: Any) -> Optional[float]:
        """Convert value to numeric if possible."""
        if value is None:
            return None
        try:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                # Remove commas and try to convert
                cleaned = value.replace(',', '').replace('$', '').strip()
                return float(cleaned)
        except (ValueError, TypeError):
            pass
        return None

    def _determine_source_filing(self, period_id: str) -> Optional[int]:
        """Determine which filing this period came from.

        Previously returned None unconditionally, so `source_filing_index` was never
        populated and `by_filing_index()` -- a declared public filter -- matched
        nothing for any argument. A filter that silently returns no rows reads as
        "no matching data" (bead edgartools-qbm7, GH #1205).

        The answer comes from the stitcher, which already decides it when selecting
        periods, rather than being recomputed from each filing's reporting periods:
        the two would have to agree about which filing wins a period both report,
        and one rule with two implementations is how they stop agreeing.
        """
        return self._period_sources.get(period_id)

    def _extract_fiscal_info(self, period_id: str) -> Dict[str, Any]:
        """Extract fiscal period and year information for this period's own filing.

        This read `xbrl_list[0].entity_info` for *every* period, so all rows carried
        the newest filing's fiscal focus regardless of the period they covered: on
        ORCL's 10-K + 10-Q pair the quarter ended 2024-08-31 was reported as
        `fiscal_year=2026, fiscal_period=FY`, taken from a 10-K filed two years
        later. The fiscal focus now comes from the filing that reported the period.

        Note this still reads a filing's declared focus rather than deriving the
        period's identity from its own duration, which is the deeper fix tracked by
        edgartools-51xd; taking it from the right filing is what this bead covers.
        """
        fiscal_info: Dict[str, Any] = {}

        source_index = self._determine_source_filing(period_id)
        if source_index is None:
            # Unknown provenance: say nothing rather than assert another filing's
            # focus, which is the defect this replaces.
            return fiscal_info

        entity_info = self.xbrls.xbrl_list[source_index].entity_info
        if entity_info:
            fiscal_info['fiscal_period'] = entity_info.get('fiscal_period')
            fiscal_info['fiscal_year'] = entity_info.get('fiscal_year')

        return fiscal_info

    def query(self, **kwargs) -> 'StitchedFactQuery':
        """Create a new query for stitched facts."""
        return StitchedFactQuery(self, **kwargs)


class StitchedFactQuery(FactQuery):
    """
    Enhanced fact query for stitched/standardized multi-filing data.

    Extends the base FactQuery with capabilities specific to multi-period,
    standardized financial data.
    """

    def __init__(self, stitched_facts_view: StitchedFactsView, **kwargs):
        # Initialize with stitched facts view instead of regular facts view
        self._stitched_facts_view = stitched_facts_view

        # Initialize base FactQuery attributes manually since we're not calling super().__init__
        self._facts_view = stitched_facts_view  # For compatibility with base class
        self._filters = []
        self._transformations = []
        self._aggregations = []
        self._include_dimensions = False
        self._include_contexts = True
        self._include_element_info = True
        self._sort_by = None
        self._sort_ascending = True
        self._limit = None
        self._statement_type = None

        # Multi-filing specific options
        self._cross_period_only = False
        self._trend_analysis = False
        self._require_all_periods = False

        # Store query-specific parameters for get_facts
        self._max_periods = kwargs.get('max_periods', 8)
        # XBRLS.query() spells this option 'standardize'; the base FactQuery
        # spells it 'standard'.  Accept both, or the caller's standardize=False
        # is silently dropped and standardization stays on.
        self._standard = kwargs.get('standardize', kwargs.get('standard', True))
        self._statement_types = kwargs.get('statement_types', None)

    def __str__(self):
        return f"StitchedFactQuery(filters={len(self._filters)})"

    # Enhanced filtering methods for multi-filing scenarios

    def by_standardized_concept(self, concept_name: str) -> 'StitchedFactQuery':
        """
        Filter by standardized concept name (e.g., 'Revenue', 'Net Income').

        Args:
            concept_name: Standardized concept name

        Returns:
            Self for method chaining
        """
        # Query both the standardized label and original concept
        self._filters.append(
            lambda f: (f.get('label') == concept_name or
                      concept_name.lower() in f.get('label', '').lower() or
                      concept_name.lower() in f.get('concept', '').lower())
        )
        return self

    def by_original_label(self, pattern: str, exact: bool = False) -> 'StitchedFactQuery':
        """
        Filter by original company-specific labels before standardization.

        Args:
            pattern: Pattern to match against original labels
            exact: Whether to require exact match

        Returns:
            Self for method chaining
        """
        if exact:
            self._filters.append(lambda f: f.get('original_label') == pattern)
        else:
            regex = re.compile(pattern, re.IGNORECASE)
            self._filters.append(
                lambda f: f.get('original_label') and regex.search(f['original_label'])
            )
        return self

    def across_periods(self, min_periods: int = 2) -> 'StitchedFactQuery':
        """
        Filter to concepts that appear across multiple periods.

        Args:
            min_periods: Minimum number of periods the concept must appear in

        Returns:
            Self for method chaining
        """
        self._cross_period_only = True
        self._min_periods = min_periods
        return self

    def by_fiscal_period(self, fiscal_period: str) -> 'StitchedFactQuery':
        """
        Filter by fiscal period (FY, Q1, Q2, Q3, Q4).

        Args:
            fiscal_period: Fiscal period identifier

        Returns:
            Self for method chaining
        """
        self._filters.append(
            lambda f: f.get('fiscal_period') == fiscal_period
        )
        return self

    def by_filing_index(self, filing_index: int) -> 'StitchedFactQuery':
        """
        Filter facts by which filing they originated from.

        Args:
            filing_index: Index of the filing (0 = most recent)

        Returns:
            Self for method chaining
        """
        self._filters.append(
            lambda f: f.get('source_filing_index') == filing_index
        )
        return self

    def trend_analysis(self, concept: str) -> 'StitchedFactQuery':
        """
        Set up for trend analysis of a specific concept across periods.

        Args:
            concept: Concept to analyze trends for

        Returns:
            Self for method chaining
        """
        self._trend_analysis = True
        self.by_standardized_concept(concept)
        return self

    def complete_periods_only(self) -> 'StitchedFactQuery':
        """
        Only return concepts that have values in all available periods.

        Returns:
            Self for method chaining
        """
        self._require_all_periods = True
        return self

    def execute(self) -> List[Dict[str, Any]]:
        """
        Execute the query with enhanced multi-period processing.

        Returns:
            List of fact dictionaries
        """
        # Get base results from stitched facts with query parameters
        results = self._stitched_facts_view.get_facts(
            max_periods=self._max_periods,
            standard=self._standard,
            statement_types=self._statement_types
        )

        # Apply standard filters
        for filter_func in self._filters:
            results = [f for f in results if filter_func(f)]

        # Apply transformations.  Shared with FactQuery: this class inherits both
        # defects it used to duplicate, so the numeric-value fix (GH #1187) has to
        # land in one place or the stitched path silently keeps the old one.
        # _apply_transformations copies each row before writing to it, since
        # get_facts() hands back rows from the view's shared cache.
        results = _apply_transformations(results, self._transformations)

        # Apply aggregations
        if self._aggregations:
            aggregated_results = {}
            for agg in self._aggregations:
                dimension = agg['dimension']
                func = agg['function']

                # Group facts by dimension
                groups = {}
                for fact in results:
                    dim_value = fact.get(f'dim_{dimension}')
                    if dim_value and 'value' in fact and fact['value'] is not None:
                        if dim_value not in groups:
                            groups[dim_value] = []
                        groups[dim_value].append(fact['value'])

                # Apply aggregation function
                for dim_value, values in groups.items():
                    agg_value = 0.0  # Initialize with default value
                    if func == 'sum':
                        agg_value = sum(values)
                    elif func == 'average':
                        agg_value = sum(values) / len(values)

                    key = (dimension, dim_value)
                    if key not in aggregated_results:
                        aggregated_results[key] = {'dimension': dimension, 'value': dim_value, 'values': {}}
                    aggregated_results[key]['values'][func] = agg_value

            results = list(aggregated_results.values())

        # Apply cross-period filtering if requested
        if self._cross_period_only:
            results = self._filter_cross_period_concepts(results)

        # Apply complete periods filtering if requested
        if self._require_all_periods:
            results = self._filter_complete_periods(results)

        # Apply trend analysis if requested
        if self._trend_analysis:
            results = self._prepare_trend_data(results)

        # Apply sorting if specified
        sort_by = self._sort_by
        if results and sort_by and sort_by in results[0]:
            results.sort(key=lambda f: f.get(sort_by, ''),
                         reverse=not self._sort_ascending)

        # Apply limit if specified
        if self._limit is not None:
            results = results[:self._limit]

        return results

    def _filter_cross_period_concepts(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter to concepts that appear in multiple periods."""
        concept_periods = defaultdict(set)
        for fact in results:
            concept_key = (fact.get('concept', ''), fact.get('label', ''))
            concept_periods[concept_key].add(fact.get('period_key', ''))

        # Filter to concepts with minimum period count
        valid_concepts = {
            concept for concept, periods in concept_periods.items()
            if len(periods) >= getattr(self, '_min_periods', 2)
        }

        return [
            fact for fact in results
            if (fact.get('concept', ''), fact.get('label', '')) in valid_concepts
        ]

    def _filter_complete_periods(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter to concepts that have values in all periods."""
        # Get all available periods
        all_periods = set(fact.get('period_key', '') for fact in results)

        concept_periods = defaultdict(set)
        for fact in results:
            concept_key = (fact.get('concept', ''), fact.get('label', ''))
            concept_periods[concept_key].add(fact.get('period_key', ''))

        # Filter to concepts with complete period coverage
        complete_concepts = {
            concept for concept, periods in concept_periods.items()
            if periods == all_periods
        }

        return [
            fact for fact in results
            if (fact.get('concept', ''), fact.get('label', '')) in complete_concepts
        ]

    def _prepare_trend_data(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prepare data for trend analysis by sorting periods."""
        # Sort by period end date for trend analysis
        return sorted(results, key=lambda f: f.get('period_end', ''))

    def to_trend_dataframe(self) -> pd.DataFrame:
        """
        Create a DataFrame optimized for trend analysis.

        Returns:
            DataFrame with concepts as rows and periods as columns
        """
        results = self.execute()

        if not results:
            return pd.DataFrame()

        # Pivot data for trend analysis
        df = pd.DataFrame(results)

        # Create pivot table with concepts as rows and periods as columns
        if 'concept' in df.columns and 'period_end' in df.columns and 'numeric_value' in df.columns:
            trend_df = df.pivot_table(
                index=['label', 'concept'],
                columns='period_end',
                values='numeric_value',
                aggfunc='first'
            )
            return trend_df

        return df

    def _df_cache_key(self, columns: tuple) -> tuple:
        """The base key plus the stitching configuration.

        execute() here passes max_periods, standard and statement_types to
        get_facts(), so two queries identical in filters but differing in these
        return different populations. They are constructor kwargs rather than
        fluent setters, so they cannot change mid-object today — they are in the
        key so that stops being something the cache silently depends on.
        """
        return super()._df_cache_key(columns) + (
            self._max_periods,
            self._standard,
            tuple(self._statement_types) if isinstance(self._statement_types, list) else self._statement_types,
        )

    def to_dataframe(self, *columns) -> pd.DataFrame:
        """
        Execute the query and return results as a DataFrame.

        Args:
            columns: List of columns to include in the DataFrame

        Returns:
            pandas DataFrame with query results
        """
        cache_key = self._df_cache_key(columns)
        cache = getattr(self, '_df_cache', {})
        if cache_key in cache:
            return cache[cache_key]
        results = self.execute()

        declared = self._declared_columns()
        if columns:
            # Which names are valid used to depend on the rows, because the
            # projection ran after all-null columns had been deleted.
            unknown = [col for col in columns if col not in declared]
            if unknown:
                raise KeyError(
                    f"to_dataframe() does not emit {unknown}. "
                    f"Available: {sorted(declared)}")
            order = list(columns)
        else:
            order = None

        if not results:
            # Zero rows, but the declared columns and their dtypes. A bare
            # DataFrame() has no columns at all, so df['value'] raised KeyError on
            # an empty result -- reachable from a real query, e.g. across_periods(2)
            # against a single filing.
            return empty_declared_frame(declared, order or list(declared))

        df = pd.DataFrame(results)
        df['value'] = df['value'].astype(str)  # Ensure value is string for display

        if not self._include_dimensions:
            df = df.loc[:, [col for col in df.columns if not col.startswith('dim_')]]

        if not self._include_element_info:
            element_cols = ['element_id', 'element_name', 'element_type', 'element_period_type',
                            'element_balance', 'element_label']
            df = df.loc[:, [col for col in df.columns if col not in element_cols]]

        if order is None:
            # Whatever is present but undeclared is the per-axis dim_<axis> tail,
            # whose names depend on which axes the filer used. Sorted, because its
            # order otherwise follows whichever row first introduced each axis.
            extra = sorted(col for col in df.columns
                           if col not in declared and col not in _STITCHED_SKIP_COLUMNS)
            order = list(declared) + extra

        result = apply_declared_schema(df, declared, order,
                                       pinned=_STITCHED_PINNED,
                                       null_dtypes=_STITCHED_NULL_DTYPES)
        cache[cache_key] = result
        self._df_cache = cache
        return result

    def _declared_columns(self) -> Dict[str, Any]:
        """The columns this query's configuration emits, in emission order.

        `include_contexts` is the only flag that gates a declared column here:
        `period_type` is the one context column this path builds. The others it
        names (`context_ref`, `entity_identifier`, `entity_scheme`) are never on a
        stitched fact, and the `element_*` columns are not either.
        """
        declared = dict(_STITCHED_COLUMNS)
        if not self._include_contexts:
            declared.pop('period_type', None)
        return declared

    def __rich__(self):
        title = Text.assemble(("Stitched Facts Query"),
                              )
        subtitle = Text.assemble((self._stitched_facts_view.entity_name, "bold deep_sky_blue1"),
                                 " - ",
                                 (self._stitched_facts_view.document_type)
                                )
        df = self.to_dataframe().fillna('')
        columns = df.columns.tolist()
        description = Markdown(
            f"""
            Use *to_dataframe(columns)* to get a DataFrame of the results.

            e.g. `query.to_dataframe('concept', 'value', 'period_end')`

            Available columns:
            '{', '.join(columns)}'

            **Enhanced Multi-Period Methods:**
            - `across_periods(min_periods=2)` - Filter to concepts across multiple periods
            - `by_standardized_concept('Revenue')` - Filter by standardized labels
            - `by_original_label('Net sales')` - Filter by original company labels
            - `trend_analysis('Revenue')` - Set up trend analysis
            - `to_trend_dataframe()` - Get trend-optimized DataFrame
            """
        )

        display_columns = [col for col in ['label', 'concept', 'value', 'period_start', 'period_end', 'statement_type']
                           if col in columns]

        if not df.empty:
            df_display = df[display_columns].head(10)  # Show first 10 rows
            table = Table(*display_columns, show_header=True, header_style="bold", box=box.SIMPLE)
            for t in df_display.itertuples(index=False):
                row = []
                for i in t:
                    row.append(str(i)[:50])  # Truncate long values
                table.add_row(*row)
        else:
            table = Table("No results found", box=box.SIMPLE)

        panel = Panel(Group(description, table), title=title, subtitle=subtitle, box=box.ROUNDED)
        return panel

    def __repr__(self):
        return repr_rich(self.__rich__())
