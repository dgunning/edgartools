# Edgar Entity Facts API Assessment

## Current State Analysis

### Overview
The `edgar.entity.facts` module provides access to company facts data from the SEC's XBRL API. It serves as a bridge between raw SEC JSON data and usable Python objects for financial analysis.

### Current API Structure

#### Core Classes
1. **`EntityFacts` (alias `CompanyFacts`)**
   - Main container for company XBRL facts
   - Uses PyArrow Table for data storage
   - Contains metadata about facts
   - Rich display formatting

2. **`Fact`** 
   - Individual fact/data point
   - Simple data container with financial attributes
   - No methods beyond representation

3. **`CompanyConcept`**
   - Specific concept data for a company
   - Includes historical data for single concept
   - DataFrame-based storage

4. **`Concept`**
   - XBRL concept definition
   - Taxonomy, tag, label, description

#### Key Functions
- `get_company_facts(cik)` - Main entry point for company facts
- `get_concept(cik, taxonomy, concept)` - Single concept retrieval
- `parse_company_facts(fjson)` - JSON parsing logic
- `download_company_facts_from_sec(cik)` - SEC API interaction

### Strengths

#### 1. **Data Integration**
- ✅ Seamless integration with SEC's XBRL API
- ✅ Local caching mechanism for performance
- ✅ PyArrow backend for efficient data handling
- ✅ Rich formatting for interactive use

#### 2. **API Coverage**
- ✅ Covers both company facts and individual concepts
- ✅ Handles multiple units and time periods
- ✅ Error handling for missing data

#### 3. **Performance Optimizations**
- ✅ LRU caching on main functions
- ✅ PyArrow for columnar data efficiency
- ✅ Pandas integration for analysis

### Critical Issues

#### 1. **Inconsistent Data Model**
```python
# Current inconsistency:
class EntityFacts:
    def __init__(self, cik: int, name: str, facts: pa.Table, fact_meta: pd.DataFrame):
        # Mixed storage: PyArrow + Pandas
        
class CompanyConcept:
    def __init__(self, cik: str, entity_name: str, concept: Concept, data: pd.DataFrame):
        # Pure Pandas, different CIK type (str vs int)
```

**Problem**: Different classes use different storage backends and data types for the same concepts.

#### 2. **Poor Developer Experience**
```python
# Current usage is complex:
facts = get_company_facts(320193)  # Returns EntityFacts
df = facts.to_pandas()             # Convert to DataFrame
# Then manually filter/query the DataFrame

# vs CompanyConcept which is already filtered:
concept = get_concept(320193, "us-gaap", "Revenue")  # Returns CompanyConcept
df = concept.data                  # Already a DataFrame
```

**Problem**: Inconsistent APIs for similar operations, requiring different workflows.

#### 3. **Limited Query Capabilities**
```python
# Current approach requires manual filtering:
facts = get_company_facts(320193)
df = facts.to_pandas()
revenue_facts = df[df['fact'] == 'Revenue']  # Manual filtering
```

**Problem**: No built-in query/filtering capabilities on EntityFacts.

#### 4. **Type Safety Issues**
```python
# Mixed types throughout:
class EntityFacts:
    cik: int                    # Integer CIK
    
class CompanyConcept:
    cik: str                    # String CIK - inconsistent!
    
class Fact:
    value: object               # Untyped value - could be anything
```

#### 5. **Missing Investment-Focused Features**
- ❌ No built-in ratio calculations
- ❌ No time series analysis capabilities  
- ❌ No peer comparison features
- ❌ No data quality indicators
- ❌ No financial statement categorization

#### 6. **Poor Error Handling**
```python
# Current error handling is basic:
try:
    facts = get_company_facts(123456)
except NoCompanyFactsFound:
    # Only handles 404 errors, not data quality issues
```

**Problem**: No handling of malformed data, missing values, or data quality issues.

### Usage Patterns Analysis

#### Current Usage in Codebase
```python
# From core.py:
def get_facts(self) -> Optional[EntityFacts]:
    try:
        return get_company_facts(self.cik)
    except NoCompanyFactsFound:
        return None
```

**Analysis**: Simple pass-through pattern indicates the API is used but not deeply integrated.

#### Test Coverage Analysis
From `test_company.py`:
```python
def test_get_company_facts():
    company_facts: CompanyFacts = get_company_facts(1318605)  # Tesla
    assert company_facts
    assert len(company_facts) > 100
```

**Analysis**: Basic smoke tests only, no functional or integration testing.

### Performance Analysis

#### Data Storage Efficiency
- ✅ PyArrow provides columnar efficiency
- ⚠️ Mixed storage types create memory overhead
- ❌ No lazy loading for large datasets

#### Caching Strategy
```python
@lru_cache(maxsize=32)
def get_company_facts(cik: int):
```
- ✅ Function-level caching
- ❌ Small cache size (32) may cause thrashing
- ❌ No cache invalidation strategy
- ❌ No shared cache across processes

### Integration Points

#### With Other Edgar Modules
1. **edgar.entity.core**: Basic integration via `get_facts()` method
2. **edgar.xbrl**: Overlapping functionality but different data sources
3. **edgar.financials**: Could benefit from facts integration

#### Current Gaps
- No integration with filing-level XBRL data
- No connection to financial statement extraction
- No relationship to peer comparison features

## Recommended Revamp Strategy

### 1. **Unified Data Model**
```python
@dataclass
class FinancialFact:
    """Unified fact representation"""
    concept: str
    taxonomy: str  
    value: Union[float, int, str]
    unit: str
    period_start: Optional[date]
    period_end: date
    filing_date: date
    form: str
    accession: str
    
    # Investment-focused additions
    standardized_value: Optional[float]  # Scaled to common units
    data_quality_score: float            # 0-1 confidence score
    is_estimated: bool                   # Derived vs reported
```

### 2. **Query-First API Design**
```python
class CompanyFacts:
    """Investment-focused company facts API"""
    
    def query(self) -> FactQuery:
        """Fluent query interface"""
        return FactQuery(self._facts)
    
    # Investment-focused methods
    def get_income_statement_facts(self, periods: int = 4) -> pd.DataFrame:
    def get_balance_sheet_facts(self, periods: int = 4) -> pd.DataFrame:
    def calculate_ratios(self) -> Dict[str, float]:
    def get_growth_metrics(self, periods: int = 5) -> Dict[str, float]:
    
    # Time series analysis
    def get_trend(self, concept: str, periods: int = 8) -> pd.Series:
    def detect_anomalies(self) -> List[str]:
```

### 3. **Consistent Type System**
```python
# All CIKs as integers
# All values properly typed
# Consistent error handling
# Proper null handling
```

### 4. **Performance Optimization**
```python
class CompanyFactsCache:
    """Shared, intelligent caching system"""
    def __init__(self, ttl_hours: int = 24, max_size_gb: float = 1.0):
        
    async def get_facts(self, cik: int) -> CompanyFacts:
        """Async API with intelligent caching"""
        
    def invalidate(self, cik: int):
        """Manual cache invalidation"""
```

### 5. **Investment Analytics Integration**
```python
class InvestmentAnalytics:
    """Investment-focused analytics on facts"""
    
    def __init__(self, facts: CompanyFacts):
        self.facts = facts
        
    def calculate_financial_health_score(self) -> float:
        """Composite financial health indicator"""
        
    def get_peer_comparison(self, peer_ciks: List[int]) -> pd.DataFrame:
        """Compare key metrics to peers"""
        
    def detect_red_flags(self) -> List[str]:
        """Identify potential accounting issues"""
```

## Migration Strategy

### Phase 1: Foundation (Weeks 1-2)
- [ ] Create unified `FinancialFact` data model
- [ ] Implement consistent type system
- [ ] Add comprehensive error handling
- [ ] Create test suite with real data validation

### Phase 2: Core API (Weeks 3-4)  
- [ ] Implement new `CompanyFacts` class with query interface
- [ ] Add investment-focused convenience methods
- [ ] Implement intelligent caching system
- [ ] Ensure backward compatibility

### Phase 3: Analytics (Weeks 5-6)
- [ ] Add `InvestmentAnalytics` module
- [ ] Implement ratio calculations
- [ ] Add peer comparison capabilities
- [ ] Create data quality scoring

### Phase 4: Integration (Weeks 7-8)
- [ ] Integration with XBRL module
- [ ] Connection to financial statements
- [ ] Performance optimization
- [ ] Documentation and examples

## Success Metrics

### Developer Experience
- Reduce lines of code for common tasks by 50%
- Eliminate type-related runtime errors  
- Provide IntelliSense support for all methods

### Performance
- 10x faster queries through better caching
- 50% reduction in memory usage
- Sub-second response for cached data

### Investment Utility
- Built-in ratio calculations for 20+ common ratios
- Automated peer comparison capabilities
- Data quality indicators for all facts

## Risk Mitigation

### Backward Compatibility
- Maintain existing function signatures during transition
- Provide deprecation warnings for 2 releases
- Create migration guide with examples

### Data Quality
- Comprehensive validation of SEC data transformations
- Unit tests with real data from multiple companies
- Monitoring for API changes from SEC

### Performance Regression  
- Benchmark current performance
- Load testing with large datasets
- Memory profiling to prevent leaks

## Conclusion

The current facts API provides basic functionality but lacks the developer experience and investment-focused features needed for modern financial analysis. The revamp should focus on:

1. **Consistency**: Unified data models and APIs
2. **Investment Focus**: Built-in analytics and ratios  
3. **Performance**: Intelligent caching and optimization
4. **Developer Experience**: Fluent APIs and comprehensive typing

This revamp will transform the facts API from a basic data access layer into a powerful investment analysis tool that aligns with EdgarTools' strategic direction.