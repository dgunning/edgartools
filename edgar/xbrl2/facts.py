"""
Facts module for querying XBRL facts.

This module provides a powerful interface for querying XBRL facts based on various
attributes including concept, value, dimension, dates, statement, and more.
It enables convenient retrieval of facts as pandas DataFrames for analysis.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Set, Tuple, Callable

import pandas as pd

from edgar.xbrl2.models import Fact, Context
from edgar.xbrl2.core import STANDARD_LABEL, format_date, parse_date


class FactQuery:
    """
    A query builder for XBRL facts that enables filtering by various attributes.
    
    This class provides a fluent interface for building queries against XBRL facts,
    allowing filtering by concept, value, period, dimensions, and other attributes.
    """
    
    def __init__(self, facts_view: FactsView):
        """
        Initialize a new fact query.
        
        Args:
            facts_view: The FactsView instance to query against
        """
        self._facts_view = facts_view
        self._filters = []
        self._include_dimensions = True
        self._include_contexts = True
        self._include_element_info = True
        self._sort_by = None
        self._sort_ascending = True
        self._limit = None

    def __str__(self):
        return f"FactQuery(filters={self._filters})"
        
    def by_concept(self, pattern: str, exact: bool = False) -> FactQuery:
        """
        Filter facts by concept name.
        
        Args:
            pattern: Pattern to match against concept names
            exact: If True, require exact match; otherwise, use regex pattern matching
            
        Returns:
            Self for method chaining
        """
        if exact:
            self._filters.append(lambda f: f['concept'] == pattern)
        else:
            regex = re.compile(pattern, re.IGNORECASE)
            self._filters.append(lambda f: bool(regex.search(f['concept'])))
        return self
    
    def by_label(self, pattern: str, exact: bool = False) -> FactQuery:
        """
        Filter facts by element label.
        
        Args:
            pattern: Pattern to match against element labels
            exact: If True, require exact match; otherwise, use regex pattern matching
            
        Returns:
            Self for method chaining
        """
        if exact:
            # Try multiple label fields with exact matching
            self._filters.append(lambda f: 
                ('label' in f and f['label'] == pattern) or
                ('element_label' in f and f['element_label'] == pattern)
            )
        else:
            # Use regex pattern matching across multiple label fields
            regex = re.compile(pattern, re.IGNORECASE)
            self._filters.append(lambda f: 
                ('label' in f and f['label'] is not None and bool(regex.search(str(f['label'])))) or
                ('element_label' in f and f['element_label'] is not None and bool(regex.search(str(f['element_label']))))
            )
        return self
    
    def by_value(self, value_filter: Union[Callable, str, int, float, list, tuple]) -> FactQuery:
        """
        Filter facts by value.
        
        Args:
            value_filter: Can be:
                - A callable predicate that takes a value and returns bool
                - A specific value to match exactly
                - A tuple or list of (min, max) for range filtering
                
        Returns:
            Self for method chaining
        """
        if callable(value_filter):
            self._filters.append(lambda f: 'numeric_value' in f and 
                               f['numeric_value'] is not None and 
                               value_filter(f['numeric_value']))
        elif isinstance(value_filter, (list, tuple)) and len(value_filter) == 2:
            min_val, max_val = value_filter
            self._filters.append(lambda f: 'numeric_value' in f and 
                               f['numeric_value'] is not None and 
                               min_val <= f['numeric_value'] <= max_val)
        else:
            self._filters.append(lambda f: 'numeric_value' in f and 
                               f['numeric_value'] is not None and 
                               f['numeric_value'] == value_filter)
        return self
    
    def by_period_type(self, period_type: str) -> FactQuery:
        """
        Filter facts by period type ('instant' or 'duration').
        
        Args:
            period_type: Period type to filter by
            
        Returns:
            Self for method chaining
        """
        self._filters.append(lambda f: 'period_type' in f and f['period_type'] == period_type)
        return self
        
    def by_period_key(self, period_key: str) -> FactQuery:
        """
        Filter facts by a specific period key.
        
        Args:
            period_key: Period key to filter by (e.g., "instant_2023-12-31")
            
        Returns:
            Self for method chaining
        """
        self._filters.append(lambda f: 'period_key' in f and f['period_key'] == period_key)
        return self
        
    def by_period_keys(self, period_keys: List[str]) -> FactQuery:
        """
        Filter facts by a list of period keys.
        
        Args:
            period_keys: List of period keys to filter by
            
        Returns:
            Self for method chaining
        """
        self._filters.append(lambda f: 'period_key' in f and f['period_key'] in period_keys)
        return self
    
    def by_instant_date(self, date_str: str, exact: bool = True) -> FactQuery:
        """
        Filter facts by instant date.
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            exact: If True, require exact match; if False, match facts with date less than or equal to date_str
            
        Returns:
            Self for method chaining
        """
        if exact:
            self._filters.append(lambda f: 'period_instant' in f and f['period_instant'] == date_str)
        else:
            date_obj = parse_date(date_str)
            self._filters.append(lambda f: 'period_instant' in f and 
                                    parse_date(f['period_instant']) <= date_obj)
        return self
    
    def by_date_range(self, start_date: Optional[str] = None, 
                     end_date: Optional[str] = None) -> FactQuery:
        """
        Filter facts by date range.
        
        Args:
            start_date: Optional start date string in YYYY-MM-DD format
            end_date: Optional end date string in YYYY-MM-DD format
            
        Returns:
            Self for method chaining
        """
        if start_date and end_date:
            # Match duration facts that fall within the date range
            start_obj = parse_date(start_date)
            end_obj = parse_date(end_date)
            self._filters.append(lambda f: 
                ('period_start' in f and 'period_end' in f and 
                 parse_date(f['period_start']) >= start_obj and 
                 parse_date(f['period_end']) <= end_obj))
        elif start_date:
            # Match duration facts that start on or after start_date
            start_obj = parse_date(start_date)
            self._filters.append(lambda f: 
                ('period_start' in f and 
                 parse_date(f['period_start']) >= start_obj))
        elif end_date:
            # Match duration facts that end on or before end_date
            end_obj = parse_date(end_date)
            self._filters.append(lambda f: 
                ('period_end' in f and 
                 parse_date(f['period_end']) <= end_obj))
        return self
    
    def by_dimension(self, dimension: str, value: Optional[str] = None) -> FactQuery:
        """
        Filter facts by dimension.
        
        Args:
            dimension: Dimension name
            value: Optional dimension value to filter by
            
        Returns:
            Self for method chaining
        """
        if value:
            self._filters.append(lambda f: f'dim_{dimension}' in f and f[f'dim_{dimension}'] == value)
        else:
            self._filters.append(lambda f: f'dim_{dimension}' in f)
        return self
    
    def by_statement_type(self, statement_type: str) -> FactQuery:
        """
        Filter facts by statement type.
        
        Args:
            statement_type: Statement type ('BalanceSheet', 'IncomeStatement', etc.)
            
        Returns:
            Self for method chaining
        """
        self._filters.append(lambda f: 'statement_type' in f and f['statement_type'] == statement_type)
        return self
    
    def by_fiscal_period(self, fiscal_period: str) -> FactQuery:
        """
        Filter facts by fiscal period (FY, Q1, Q2, Q3, Q4).
        
        Args:
            fiscal_period: Fiscal period identifier
            
        Returns:
            Self for method chaining
        """
        self._filters.append(lambda f: 'fiscal_period' in f and f['fiscal_period'] == fiscal_period)
        return self
    
    def by_fiscal_year(self, fiscal_year: Union[int, str]) -> FactQuery:
        """
        Filter facts by fiscal year.
        
        Args:
            fiscal_year: Fiscal year to filter by
            
        Returns:
            Self for method chaining
        """
        self._filters.append(lambda f: 'fiscal_year' in f and str(f['fiscal_year']) == str(fiscal_year))
        return self
    
    def by_unit(self, unit: str) -> FactQuery:
        """
        Filter facts by unit reference.
        
        Args:
            unit: Unit reference to filter by
            
        Returns:
            Self for method chaining
        """
        self._filters.append(lambda f: 'unit_ref' in f and f['unit_ref'] == unit)
        return self
    
    def by_custom(self, filter_func: Callable) -> FactQuery:
        """
        Add a custom filter function.
        
        Args:
            filter_func: Custom filter function that takes a fact dict and returns bool
            
        Returns:
            Self for method chaining
        """
        self._filters.append(filter_func)
        return self
        
    def by_text(self, pattern: str) -> FactQuery:
        """
        Search across concept names, labels, and element names for a pattern.
        
        This is a flexible search that looks for the pattern in all text fields.
        
        Args:
            pattern: Pattern to search for in various text fields
            
        Returns:
            Self for method chaining
        """
        regex = re.compile(pattern, re.IGNORECASE)
        
        def text_filter(f):
            # Search in concept name
            if 'concept' in f and f['concept'] is not None and regex.search(str(f['concept'])):
                return True
                
            # Search in label
            if 'label' in f and f['label'] is not None and regex.search(str(f['label'])):
                return True
                
            # Search in element_label
            if 'element_label' in f and f['element_label'] is not None and regex.search(str(f['element_label'])):
                return True
                
            # Search in element_name
            if 'element_name' in f and f['element_name'] is not None and regex.search(str(f['element_name'])):
                return True
                
            return False
            
        self._filters.append(text_filter)
        return self
    
    def exclude_dimensions(self) -> FactQuery:
        """
        Exclude dimension columns from results.
        
        Returns:
            Self for method chaining
        """
        self._include_dimensions = False
        return self
    
    def exclude_contexts(self) -> FactQuery:
        """
        Exclude context information from results.
        
        Returns:
            Self for method chaining
        """
        self._include_contexts = False
        return self
    
    def exclude_element_info(self) -> FactQuery:
        """
        Exclude element catalog information from results.
        
        Returns:
            Self for method chaining
        """
        self._include_element_info = False
        return self
    
    def sort_by(self, column: str, ascending: bool = True) -> FactQuery:
        """
        Set sorting for results.
        
        Args:
            column: Column name to sort by
            ascending: Sort order (True for ascending, False for descending)
            
        Returns:
            Self for method chaining
        """
        self._sort_by = column
        self._sort_ascending = ascending
        return self
    
    def limit(self, n: int) -> FactQuery:
        """
        Limit the number of results.
        
        Args:
            n: Maximum number of results to return
            
        Returns:
            Self for method chaining
        """
        self._limit = n
        return self
    
    def execute(self) -> List[Dict[str, Any]]:
        """
        Execute the query and return matching facts.
        
        Returns:
            List of fact dictionaries
        """
        results = self._facts_view.get_facts()
        
        # Apply filters
        for filter_func in self._filters:
            results = [f
                       for f in results
                       if filter_func(f)
                       ]
        
        # Apply sorting if specified
        if results and self._sort_by and self._sort_by in results[0]:
            results.sort(key=lambda f: f.get(self._sort_by, ''), 
                         reverse=not self._sort_ascending)
        
        # Apply limit if specified
        if self._limit is not None:
            results = results[:self._limit]
        
        return results
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Execute the query and return results as a DataFrame.
        
        Returns:
            pandas DataFrame with query results
        """
        results = self.execute()
        
        if not results:
            return pd.DataFrame()
        
        df = pd.DataFrame(results)
        
        # Filter columns based on inclusion flags
        if not self._include_dimensions:
            df = df.loc[:, [col for col in df.columns if not col.startswith('dim_')]]
        
        if not self._include_contexts:
            context_cols = ['context_ref', 'entity_identifier', 'entity_scheme', 
                           'period_type', 'period_instant', 'period_start', 'period_end']
            df = df.loc[:, [col for col in df.columns if col not in context_cols]]
        
        if not self._include_element_info:
            element_cols = ['element_name', 'element_type', 'element_period_type', 
                           'element_balance', 'element_label']
            df = df.loc[:, [col for col in df.columns if col not in element_cols]]

        # Drop empty columns
        df = df.dropna(axis=1, how='all')
        
        return df


class FactsView:
    """
    A view over all facts in an XBRL instance, providing methods to query and analyze facts.
    """
    
    def __init__(self, xbrl):
        """
        Initialize the FactsView with an XBRL instance.
        
        Args:
            xbrl: XBRL instance containing facts, contexts, and elements
        """
        self.xbrl = xbrl
        self._facts_cache = None
        self._facts_df_cache = None
    
    def get_facts(self) -> List[Dict[str, Any]]:
        """
        Get all facts with enriched context and element information.
        
        Returns:
            List of enriched fact dictionaries
        """
        # Return cached facts if available
        if self._facts_cache is not None:
            return self._facts_cache
        
        # Build enriched facts from raw facts, contexts, and elements
        enriched_facts = []
        processed_facts = set()  # Track processed facts to avoid duplicates
        
        for fact_key, fact in self.xbrl.facts.items():
            # Skip if we've already processed this fact based on element ID and context
            fact_signature = f"{fact.element_id}__{fact.context_ref}"
            if fact_signature in processed_facts:
                continue
                
            processed_facts.add(fact_signature)
            
            fact_dict = fact.dict()
            fact_dict['fact_key'] = fact_key
            fact_dict['concept'] = fact.element_id
            
            # Split element name from context for better concept display
            # Don't override if element_id already has a namespace prefix with colon
            if "_" in fact_key and ":" not in fact_dict['concept']:
                parts = fact_key.split("_", 1)
                if len(parts) == 2:
                    fact_dict['concept'] = parts[0]
                    
            # Add context information
            if fact.context_ref in self.xbrl.contexts:
                context = self.xbrl.contexts[fact.context_ref]
                context_dict = context.dict()
                
                # Add period information
                if 'period' in context_dict and context_dict['period']:
                    fact_dict['period_type'] = context_dict['period'].get('type')
                    if fact_dict['period_type'] == 'instant':
                        fact_dict['period_instant'] = context_dict['period'].get('instant')
                    elif fact_dict['period_type'] == 'duration':
                        fact_dict['period_start'] = context_dict['period'].get('startDate')
                        fact_dict['period_end'] = context_dict['period'].get('endDate')
                
                # Add entity information
                if 'entity' in context_dict and context_dict['entity']:
                    fact_dict['entity_identifier'] = context_dict['entity'].get('identifier')
                    fact_dict['entity_scheme'] = context_dict['entity'].get('scheme')
                
                # Add dimensions
                if 'dimensions' in context_dict and context_dict['dimensions']:
                    for dim_name, dim_value in context_dict['dimensions'].items():
                        dim_key = f"dim_{dim_name.replace(':', '_')}"
                        fact_dict[dim_key] = dim_value
                        
                # Get period key from context_period_map if available
                period_key = self.xbrl.context_period_map.get(fact.context_ref)
                if period_key:
                    fact_dict['period_key'] = period_key
                    
                    # Get fiscal period and year from entity_info if available
                    for period in self.xbrl.reporting_periods:
                        if period['key'] == period_key:
                            if 'fiscal_period' in period:
                                fact_dict['fiscal_period'] = period['fiscal_period']
                            if 'fiscal_year' in period:
                                fact_dict['fiscal_year'] = period['fiscal_year']
                            break
            
            # Add element information
            element_id = fact.element_id.replace(':', '_')
            if element_id in self.xbrl.element_catalog:
                element = self.xbrl.element_catalog[element_id]
                fact_dict['element_name'] = element.name
                fact_dict['element_type'] = element.data_type
                fact_dict['element_period_type'] = element.period_type
                fact_dict['element_balance'] = element.balance
                
                # Add label
                label = None
                if element.labels:
                    # Try standard label first
                    label = element.labels.get(STANDARD_LABEL)
                    if not label:
                        # Take first available label
                        label = next(iter(element.labels.values()), None)
                fact_dict['label'] = label
            
            # Determine statement type if possible by checking presentation trees
            for role, tree in self.xbrl.presentation_trees.items():
                if element_id in tree.all_nodes:
                    # Find the statement type for this role
                    statements = self.xbrl.get_all_statements()
                    for stmt in statements:
                        if stmt['role'] == role and stmt['type']:
                            fact_dict['statement_type'] = stmt['type']
                            fact_dict['statement_role'] = role
                            break
                    # Break once we've found a statement containing this element
                    if 'statement_type' in fact_dict:
                        break
            
            enriched_facts.append(fact_dict)
        
        self._facts_cache = enriched_facts
        return enriched_facts
    
    def query(self) -> FactQuery:
        """
        Start building a query against facts.
        
        Returns:
            FactQuery: A new query builder
        """
        return FactQuery(self)
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert all facts to a DataFrame.
        
        Returns:
            pandas DataFrame containing all facts
        """
        if self._facts_df_cache is not None:
            return self._facts_df_cache
        
        facts = self.get_facts()
        df = pd.DataFrame(facts)
        self._facts_df_cache = df
        return df
    
    def get_statement_facts(self, statement_type: str) -> pd.DataFrame:
        """
        Get facts belonging to a specific statement.
        
        Args:
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
            
        Returns:
            pandas DataFrame with facts for the specified statement
        """
        return self.query().by_statement_type(statement_type).to_dataframe()
    
    def get_facts_by_concept(self, concept_pattern: str, exact: bool = False) -> pd.DataFrame:
        """
        Get facts matching a concept name pattern.
        
        Args:
            concept_pattern: Pattern to match against concept names
            exact: If True, perform exact matching; otherwise, use regex
            
        Returns:
            pandas DataFrame with matching facts
        """
        return self.query().by_concept(concept_pattern, exact).to_dataframe()
    
    def search_facts(self, text_pattern: str) -> pd.DataFrame:
        """
        Search for facts containing a text pattern in any text field.
        
        This is a flexible search that looks across concept names, labels,
        and element names for matching text.
        
        Args:
            text_pattern: Text pattern to search for
            
        Returns:
            pandas DataFrame with matching facts
        """
        return self.query().by_text(text_pattern).to_dataframe()
    
    def get_facts_with_dimensions(self) -> pd.DataFrame:
        """
        Get facts that have dimensional qualifiers.
        
        Returns:
            pandas DataFrame with dimensionally-qualified facts
        """
        return self.query().by_custom(
            lambda f: any(key.startswith('dim_') for key in f.keys())
        ).to_dataframe()
    
    def get_facts_by_period(self, period_key: str) -> pd.DataFrame:
        """
        Get facts for a specific reporting period.
        
        Args:
            period_key: Period key from reporting_periods
            
        Returns:
            pandas DataFrame with facts for the specified period
        """
        return self.query().by_period_key(period_key).to_dataframe()
    
    def get_facts_by_period_view(self, statement_type: str, period_view_name: str) -> pd.DataFrame:
        """
        Get facts for a specific period view (e.g., "Annual Comparison", "Three-Year Comparison").
        
        Args:
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
            period_view_name: Name of the period view as defined in get_period_views
            
        Returns:
            pandas DataFrame with facts for the specified period view
        """
        # Get available period views for this statement type
        period_views = self.xbrl.get_period_views(statement_type)
        
        # Find the requested view
        matching_view = next((view for view in period_views if view['name'] == period_view_name), None)
        
        if not matching_view:
            # If view not found, return empty DataFrame
            return pd.DataFrame()
        
        # Get the period keys for this view
        period_keys = matching_view['period_keys']
        
        # Query facts that match any of these period keys and the statement type
        query = self.query()
        
        # Filter by statement type
        if statement_type:
            query = query.by_statement_type(statement_type)
            
        # Filter by the period keys
        query = query.by_period_keys(period_keys)
        
        return query.to_dataframe()
    
    def get_facts_by_fiscal_period(self, fiscal_year: Union[int, str], 
                                  fiscal_period: str) -> pd.DataFrame:
        """
        Get facts for a specific fiscal period.
        
        Args:
            fiscal_year: Fiscal year
            fiscal_period: Fiscal period ('FY', 'Q1', 'Q2', 'Q3', 'Q4')
            
        Returns:
            pandas DataFrame with facts for the specified fiscal period
        """
        return self.query().by_fiscal_year(fiscal_year).by_fiscal_period(fiscal_period).to_dataframe()
    
    def summarize(self) -> Dict[str, Any]:
        """
        Generate a summary of facts in the XBRL instance.
        
        Returns:
            Dictionary with fact summary statistics
        """
        facts = self.get_facts()
        
        # Count total facts
        total_facts = len(facts)
        
        # Count by data type
        types = {}
        for fact in facts:
            element_type = fact.get('element_type', 'unknown')
            types[element_type] = types.get(element_type, 0) + 1
        
        # Count by statement
        by_statement = {}
        for fact in facts:
            stmt_type = fact.get('statement_type', 'unknown')
            by_statement[stmt_type] = by_statement.get(stmt_type, 0) + 1
        
        # Count by period type
        by_period_type = {}
        for fact in facts:
            period_type = fact.get('period_type', 'unknown')
            by_period_type[period_type] = by_period_type.get(period_type, 0) + 1
        
        # List unique dimensions
        dimensions = set()
        for fact in facts:
            for key in fact.keys():
                if key.startswith('dim_'):
                    dimensions.add(key.replace('dim_', ''))
        
        # List unique periods
        periods = set()
        for fact in facts:
            if 'period_key' in fact:
                periods.add(fact['period_key'])
        
        return {
            'total_facts': total_facts,
            'by_type': types,
            'by_statement': by_statement,
            'by_period_type': by_period_type,
            'dimensions': sorted(list(dimensions)),
            'periods': sorted(list(periods))
        }
    
    def get_unique_concepts(self) -> List[str]:
        """
        Get list of unique concept names in the facts.
        
        Returns:
            List of unique concept names
        """
        facts = self.get_facts()
        concepts = {fact.get('concept') for fact in facts if 'concept' in fact}
        return sorted(list(concepts))
    
    def get_unique_dimensions(self) -> Dict[str, Set[str]]:
        """
        Get unique dimensions and their values.
        
        Returns:
            Dictionary mapping dimension names to sets of possible values
        """
        facts = self.get_facts()
        dimensions = {}
        
        for fact in facts:
            for key, value in fact.items():
                if key.startswith('dim_'):
                    dim_name = key.replace('dim_', '')
                    if dim_name not in dimensions:
                        dimensions[dim_name] = set()
                    dimensions[dim_name].add(value)
        
        return dimensions
        
    def get_available_period_views(self, statement_type: str) -> List[Dict[str, Any]]:
        """
        Get available period views for a statement type.
        
        This method returns the period views that can be used with get_facts_by_period_view.
        
        Args:
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
            
        Returns:
            List of period view metadata with name, description, and period keys
        """
        period_views = self.xbrl.get_period_views(statement_type)
        
        # Add facts count for each period view
        for view in period_views:
            # Count facts for each period key in this view
            period_keys = view.get('period_keys', [])
            if period_keys:
                facts_count = len(self.query()
                                 .by_statement_type(statement_type)
                                 .by_period_keys(period_keys)
                                 .execute())
                view['facts_count'] = facts_count
            else:
                view['facts_count'] = 0
                
        return period_views
    
    def pivot_by_period(self, concept_pattern: str = None, 
                        statement_type: str = None) -> pd.DataFrame:
        """
        Create a pivoted view of facts by period.
        
        Args:
            concept_pattern: Optional concept pattern to filter by
            statement_type: Optional statement type to filter by
            
        Returns:
            pandas DataFrame with concepts as rows and periods as columns
        """
        query = self.query()
        
        if concept_pattern:
            query = query.by_concept(concept_pattern)
        
        if statement_type:
            query = query.by_statement_type(statement_type)
        
        df = query.to_dataframe()
        
        if df.empty:
            return pd.DataFrame()
        
        # Create concept-period pivot
        if 'period_key' in df.columns and 'concept' in df.columns and 'numeric_value' in df.columns:
            pivot = df.pivot_table(
                values='numeric_value',
                index=['concept', 'label'],
                columns='period_key',
                aggfunc='first'  # Take first occurrence for each concept-period combo
            )
            
            # Reset index to make 'concept' and 'label' regular columns
            pivot = pivot.reset_index()
            
            return pivot
        
        return df  # Return original DataFrame if pivoting isn't possible
    
    def pivot_by_dimension(self, dimension: str, 
                          concept_pattern: str = None,
                          period_key: str = None) -> pd.DataFrame:
        """
        Create a pivoted view of facts by dimension values.
        
        Args:
            dimension: Dimension to pivot by
            concept_pattern: Optional concept pattern to filter by
            period_key: Optional period key to filter by
            
        Returns:
            pandas DataFrame with concepts as rows and dimension values as columns
        """
        query = self.query()
        
        # Apply filters if provided
        if concept_pattern:
            query = query.by_concept(concept_pattern)
        
        if period_key:
            query = query.by_custom(lambda f: 'period_key' in f and f['period_key'] == period_key)
        
        # Ensure we only get facts with this dimension
        query = query.by_dimension(dimension)
        
        df = query.to_dataframe()
        
        if df.empty:
            return pd.DataFrame()
        
        dim_col = f"dim_{dimension}"
        
        # Create concept-dimension pivot
        if dim_col in df.columns and 'concept' in df.columns and 'numeric_value' in df.columns:
            pivot = df.pivot_table(
                values='numeric_value',
                index=['concept', 'label'],
                columns=dim_col,
                aggfunc='first'  # Take first occurrence for each concept-dimension combo
            )
            
            # Reset index to make 'concept' and 'label' regular columns
            pivot = pivot.reset_index()
            
            return pivot
        
        return df  # Return original DataFrame if pivoting isn't possible
    
    def time_series(self, concept: str, exact: bool = True) -> pd.DataFrame:
        """
        Create a time series view for a specific concept.
        
        Args:
            concept: Concept name to create time series for
            exact: If True, require exact concept match; otherwise, use pattern matching
            
        Returns:
            pandas DataFrame with time series data for the concept
        """
        df = self.query().by_concept(concept, exact).to_dataframe()
        
        if df.empty:
            return pd.DataFrame()
        
        # For instant periods, use the instant date
        # For duration periods, use the end date
        df['date'] = df.apply(
            lambda row: row.get('period_instant') if row.get('period_type') == 'instant' 
                       else row.get('period_end') if row.get('period_type') == 'duration'
                       else None, 
            axis=1
        )
        
        # Drop rows without valid dates
        df = df.dropna(subset=['date'])
        
        # Sort by date
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Select relevant columns
        columns = ['date', 'numeric_value', 'unit_ref']
        if 'label' in df.columns:
            columns.append('label')
        if 'fiscal_period' in df.columns:
            columns.append('fiscal_period')
        if 'fiscal_year' in df.columns:
            columns.append('fiscal_year')
            
        # Add any dimension columns that exist
        dim_cols = [col for col in df.columns if col.startswith('dim_')]
        columns.extend(dim_cols)
        
        return df[columns]
    
    def facts_history(self, concept: str, date_col: str = 'period_end',
                     include_dimensions: bool = True) -> pd.DataFrame:
        """
        Get the history of a concept across time, optionally including dimensions.
        
        Args:
            concept: Concept name to track
            date_col: Date column to use for time series ('period_end', 'period_instant')
            include_dimensions: Whether to include dimensional breakdowns
            
        Returns:
            pandas DataFrame with time series data
        """
        df = self.query().by_concept(concept, True).to_dataframe()
        
        if df.empty:
            return pd.DataFrame()
        
        # Filter to only rows with the date column
        df = df.dropna(subset=[date_col])
        
        # Convert to datetime
        df[date_col] = pd.to_datetime(df[date_col])
        
        # If including dimensions, create a more complex view
        if include_dimensions:
            # Convert dimension columns to category names
            dimension_cols = [col for col in df.columns if col.startswith('dim_')]
            
            if dimension_cols:
                # Create a combined dimension key
                if len(dimension_cols) > 0:
                    df['dimension_key'] = df.apply(
                        lambda row: '-'.join(str(row.get(col, '')) for col in dimension_cols), 
                        axis=1
                    )
                else:
                    df['dimension_key'] = 'No dimensions'
                
                # Pivot to show time series by dimension
                pivot = df.pivot_table(
                    values='numeric_value',
                    index=[date_col],
                    columns=['dimension_key'],
                    aggfunc='first'
                )
                
                return pivot.sort_index()
        
        # Simple time series without dimensions
        result = df.sort_values(date_col)[['concept', 'label', date_col, 'numeric_value', 'unit_ref']]
        if 'fiscal_period' in df.columns:
            result['fiscal_period'] = df['fiscal_period']
        if 'fiscal_year' in df.columns:
            result['fiscal_year'] = df['fiscal_year']
            
        return result
    
    def clear_cache(self) -> None:
        """Clear cached data."""
        self._facts_cache = None
        self._facts_df_cache = None


    def __str__(self):
        return f"Facts for {self.xbrl}"



def add_facts_view(xbrl):
    """
    Add a FactsView instance to an XBRL object.
    
    Args:
        xbrl: XBRL instance
    
    Returns:
        FactsView instance
    """
    facts_view = FactsView(xbrl)
    xbrl.facts_view = facts_view
    return facts_view

