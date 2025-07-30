"""
Query interface for the Entity Facts API.

This module provides a fluent query builder for filtering and analyzing
financial facts with AI-ready features.
"""

from datetime import date, datetime
from typing import List, Dict, Optional, Union, Callable, Any, TYPE_CHECKING
import pandas as pd
from collections import defaultdict

from edgar.entity.models import FinancialFact, DataQuality

if TYPE_CHECKING:
    from edgar.entity.statement import FinancialStatement


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
    
    def date_range(self, start: date, end: date) -> 'FactQuery':
        """
        Filter by date range.
        
        Args:
            start: Start date (inclusive)
            end: End date (inclusive)
            
        Returns:
            Self for method chaining
        """
        self._filters.append(
            lambda f: f.period_end and start <= f.period_end <= end
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
    
    def latest_periods(self, n: int = 4, prefer_annual: bool = True) -> 'FactQuery':
        """
        Get facts from the n most recent periods.
        
        Args:
            n: Number of recent periods to include
            prefer_annual: If True, prefer annual (FY) periods over interim periods
            
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
        
        if prefer_annual:
            # Separate annual and interim periods
            annual_periods = [(pk, info) for pk, info in period_list if info['is_annual']]
            interim_periods = [(pk, info) for pk, info in period_list if not info['is_annual']]
            
            # Sort annual periods by fiscal year (newest first)
            annual_periods.sort(key=lambda x: x[0][0], reverse=True)  # Sort by fiscal_year
            
            # Sort interim periods by end date (newest first) 
            interim_periods.sort(key=lambda x: x[1]['end_date'], reverse=True)
            
            # Be very aggressive about preferring annual periods
            selected_periods = []
            
            # First preference: Use only annual periods if we have at least 4
            if len(annual_periods) >= 4:
                selected_periods.extend([pk for pk, _ in annual_periods[:n]])
            elif len(annual_periods) >= n//2:
                # If we have at least half our target in annual periods, prioritize them heavily
                selected_periods.extend([pk for pk, _ in annual_periods])
                
                # Only add the most recent interim periods from years not covered by annual periods
                remaining = n - len(selected_periods)
                if remaining > 0:
                    annual_years = {pk[0] for pk, _ in annual_periods}
                    
                    # Filter to only the most recent periods from years without annual data
                    recent_years = sorted(set(pk[0] for pk, _ in interim_periods), reverse=True)
                    filtered_interim = []
                    
                    for year in recent_years[:remaining]:
                        if year not in annual_years:
                            # Get the longest period available for this year (prefer Q4 over Q1, etc.)
                            year_periods = [(pk, info) for pk, info in interim_periods if pk[0] == year]
                            if year_periods:
                                # Sort by period length (longer periods first), then by end date
                                year_periods.sort(key=lambda x: (x[1]['period_months'], x[1]['end_date']), reverse=True)
                                filtered_interim.append(year_periods[0])
                    
                    selected_periods.extend([pk for pk, _ in filtered_interim[:remaining]])
            else:
                # Fallback: use all annual periods and fill with interim periods
                selected_periods.extend([pk for pk, _ in annual_periods])
                
                remaining = n - len(selected_periods)
                if remaining > 0:
                    annual_years = {pk[0] for pk, _ in annual_periods}
                    filtered_interim = [(pk, info) for pk, info in interim_periods 
                                      if pk[0] not in annual_years]
                    
                    selected_periods.extend([pk for pk, _ in filtered_interim[:remaining]])
        else:
            # Sort all periods by end date (newest first)
            period_list.sort(key=lambda x: x[1]['end_date'], reverse=True)
            selected_periods = [pk for pk, _ in period_list[:n]]
        
        # Filter to only these periods
        self._filters.append(
            lambda f: (f.fiscal_year, f.fiscal_period) in selected_periods
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
            # Only warn about truly mixed displayed periods
            import warnings
            warnings.warn(
                f"Mixed period lengths in displayed data: {', '.join(sorted(displayed_period_types))}. "
                "Consider using prefer_annual=True or filtering to comparable periods for accurate analysis.",
                UserWarning
            )
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
    
    def __repr__(self) -> str:
        """String representation"""
        count = self.count()
        return f"FactQuery({count} facts matching filters)"