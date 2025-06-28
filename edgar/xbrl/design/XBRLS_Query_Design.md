# XBRLS Query Functionality Design

## Overview

This document outlines the design for adding query functionality to the XBRLS class that properly handles post-processed, standardized, and stitched financial data across multiple XBRL filings.

## Key Requirements

1. **Query standardized data**: Work with standardized labels and concepts, not raw company-specific terms
2. **Multi-period awareness**: Enable queries across multiple fiscal periods and filings
3. **Stitched data integrity**: Respect the stitching process that combines statements across periods
4. **Performance**: Efficient querying without reprocessing stitched data
5. **Consistency**: Similar API to existing XBRL.query() but enhanced for multi-filing scenarios

## Architecture

### Core Components

```
XBRLS
├── facts (property) → StitchedFactsView
├── query() → StitchedFactQuery
└── _stitched_facts_cache

StitchedFactsView
├── get_facts() → List[StitchedFact]
├── query() → StitchedFactQuery
└── _extract_facts_from_statements()

StitchedFactQuery (extends FactQuery)
├── Enhanced filters for multi-period data
├── Cross-period analysis methods
└── Standardized concept querying
```

## Implementation Design

### 1. StitchedFactsView Class

```python
class StitchedFactsView:
    """
    A view over stitched facts from multiple XBRL filings.
    
    This class extracts facts from stitched statements rather than raw XBRL facts,
    ensuring that queries operate on standardized, post-processed data.
    """
    
    def __init__(self, xbrls: XBRLS):
        self.xbrls = xbrls
        self._facts_cache = None
        self._last_cache_key = None
    
    def get_facts(self, 
                  max_periods: int = 8, 
                  standardize: bool = True, 
                  statement_types: List[str] = None) -> List[Dict[str, Any]]:
        """
        Extract facts from stitched statements.
        
        Args:
            max_periods: Maximum periods to include
            standardize: Whether to use standardized labels
            statement_types: List of statement types to include
            
        Returns:
            List of fact dictionaries with stitched/standardized data
        """
        # Create cache key
        cache_key = (max_periods, standardize, tuple(statement_types or []))
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
                    standardize=standardize
                )
                
                # Extract facts from stitched data
                facts = self._extract_facts_from_stitched_data(
                    stitched_data, statement_type
                )
                all_facts.extend(facts)
                
            except Exception as e:
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
                    'statement_type': statement_type,
                    
                    # Value information
                    'value': value,
                    'numeric_value': self._convert_to_numeric(value),
                    'decimals': item.get('decimals', {}).get(period_id, 0),
                    
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
    
    def _get_period_info(self, period_id: str, periods: List[Tuple[str, str]]) -> Dict[str, Any]:
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
        """Determine which filing this period came from."""
        # This would require enhanced tracking in the stitching process
        # For now, return None but this could be enhanced
        return None
    
    def _extract_fiscal_info(self, period_id: str) -> Dict[str, Any]:
        """Extract fiscal period and year information."""
        # This would leverage entity_info from the XBRL objects
        # Implementation would depend on available fiscal metadata
        return {}
    
    def query(self, **kwargs) -> 'StitchedFactQuery':
        """Create a new query for stitched facts."""
        return StitchedFactQuery(self, **kwargs)
```

### 2. StitchedFactQuery Class

```python
class StitchedFactQuery(FactQuery):
    """
    Enhanced fact query for stitched/standardized multi-filing data.
    
    Extends the base FactQuery with capabilities specific to multi-period,
    standardized financial data.
    """
    
    def __init__(self, stitched_facts_view: StitchedFactsView, **kwargs):
        # Initialize with stitched facts view instead of regular facts view
        super().__init__(stitched_facts_view)
        self._stitched_facts_view = stitched_facts_view
        
        # Multi-filing specific options
        self._cross_period_only = False
        self._trend_analysis = False
        self._require_all_periods = False
    
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
            import re
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
        # Get base results
        results = super().execute()
        
        # Apply cross-period filtering if requested
        if self._cross_period_only:
            results = self._filter_cross_period_concepts(results)
        
        # Apply complete periods filtering if requested
        if self._require_all_periods:
            results = self._filter_complete_periods(results)
        
        # Apply trend analysis if requested
        if self._trend_analysis:
            results = self._prepare_trend_data(results)
        
        return results
    
    def _filter_cross_period_concepts(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter to concepts that appear in multiple periods."""
        from collections import defaultdict
        
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
        
        from collections import defaultdict
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
```

### 3. Enhanced XBRLS Integration

```python
class XBRLS:
    # ... existing code ...
    
    @property
    def facts(self) -> StitchedFactsView:
        """
        Get a view over stitched facts from all XBRL filings.
        
        Returns:
            StitchedFactsView for querying standardized, multi-period data
        """
        if not hasattr(self, '_stitched_facts_view'):
            self._stitched_facts_view = StitchedFactsView(self)
        return self._stitched_facts_view
    
    def query(self, 
              max_periods: int = 8,
              standardize: bool = True,
              statement_types: List[str] = None,
              **kwargs) -> StitchedFactQuery:
        """
        Start a new query for stitched facts across all filings.
        
        Args:
            max_periods: Maximum periods to include in stitched data
            standardize: Whether to use standardized labels
            statement_types: List of statement types to include
            **kwargs: Additional options passed to StitchedFactQuery
            
        Returns:
            StitchedFactQuery for building complex queries
        """
        # Ensure facts are loaded with correct parameters
        self.facts.get_facts(max_periods, standardize, statement_types)
        return self.facts.query(**kwargs)
```

## Usage Examples

### Basic Queries

```python
# Get all revenue facts across periods
revenue_facts = xbrls.query().by_standardized_concept("Revenue").execute()

# Get revenue trends as DataFrame
revenue_trends = xbrls.query().trend_analysis("Revenue").to_trend_dataframe()

# Query by original company labels
apple_revenue = xbrls.query().by_original_label("Net sales").execute()
```

### Multi-Period Analysis

```python
# Find concepts that appear in all periods
consistent_concepts = xbrls.query().complete_periods_only().execute()

# Find concepts that appear in at least 3 periods
multi_period = xbrls.query().across_periods(min_periods=3).execute()

# Get Q4 data only
q4_data = xbrls.query().by_fiscal_period("Q4").execute()
```

### Advanced Queries

```python
# Revenue trends with standardized labels
revenue_trends = (xbrls.query()
                  .by_standardized_concept("Revenue")
                  .trend_analysis("Revenue")
                  .to_trend_dataframe())

# High-value items across periods
high_value_items = (xbrls.query()
                   .by_value(lambda x: x > 1000000000)  # > $1B
                   .across_periods(min_periods=2)
                   .sort_by('numeric_value', ascending=False)
                   .execute())
```

## Benefits

1. **Standardization-Aware**: Queries work on standardized labels while preserving access to original labels
2. **Multi-Period Intelligence**: Built-in support for cross-period analysis and trend detection
3. **Performance**: Leverages existing stitching cache and adds fact-level caching
4. **Consistency**: Similar API to XBRL.query() but enhanced for multi-filing scenarios
5. **Flexibility**: Supports both standardized and original label querying

## Implementation Considerations

1. **Caching Strategy**: Cache stitched facts separately from stitched statements
2. **Source Attribution**: Track which filing each fact originated from for advanced filtering
3. **Fiscal Period Mapping**: Enhance period extraction to include fiscal context
4. **Performance**: Lazy loading of facts and efficient filtering
5. **Error Handling**: Graceful handling of filings that can't be stitched

This design ensures that XBRLS query functionality operates on the post-processed, standardized data that users expect while providing powerful multi-period analysis capabilities.