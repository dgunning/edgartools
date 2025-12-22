# Facts API Strategic Comparison: Entity vs XBRL

## Executive Summary

EdgarTools has two parallel facts systems that serve different but overlapping purposes. This analysis identifies strategic opportunities for alignment while preserving their distinct value propositions.

## System Overview Comparison

### Edgar Entity Facts (`edgar.entity.facts`)
**Purpose**: Company-wide historical fact aggregation from SEC's bulk XBRL API  
**Data Source**: SEC CompanyFacts JSON API (`/api/xbrl/companyfacts/CIK.json`)  
**Scope**: All historical facts for a company across all filings  
**Primary Use Case**: Long-term analysis, trend identification, peer comparison

### Edgar XBRL Facts (`edgar.xbrl.facts`)
**Purpose**: Filing-specific fact querying with rich contextual information  
**Data Source**: Individual XBRL instance documents from filings  
**Scope**: Single filing with full presentation and calculation context  
**Primary Use Case**: Deep financial statement analysis, compliance validation

## API Design Philosophy Comparison

### Entity Facts: Collection-Based
```python
# Current entity facts approach
facts = get_company_facts(320193)  # Returns EntityFacts collection
df = facts.to_pandas()             # Convert entire collection
filtered = df[df['fact'] == 'Revenue']  # Manual filtering required
```

**Characteristics**:
- Data-centric approach (facts as data container)
- Minimal API surface 
- Manual manipulation required
- PyArrow/Pandas hybrid storage

### XBRL Facts: Query-First Design
```python
# XBRL facts approach
xbrl = XBRL.from_filing(filing)
facts = xbrl.facts.query()         # Fluent query builder
revenue = facts.by_concept('Revenue').to_dataframe()  # Built-in filtering
```

**Characteristics**:
- Query-centric approach (facts as queryable resource)
- Rich fluent API with method chaining
- Built-in filtering and transformation
- Comprehensive metadata access

## Data Model Differences

### Entity Facts Data Model
```python
class Fact:
    end: str        # Simple string date
    value: object   # Untyped value
    accn: str       # Accession number
    fy: str         # Fiscal year
    fp: str         # Fiscal period
    form: str       # Form type
    filed: str      # Filing date
    frame: str      # Time frame
    unit: str       # Unit of measure

class EntityFacts:
    cik: int                    # Integer CIK
    name: str                   # Company name
    facts: pa.Table             # PyArrow table
    fact_meta: pd.DataFrame     # Metadata in Pandas
```

**Issues**:
- Inconsistent typing (`object` values, string dates)
- Mixed storage backends (PyArrow + Pandas)
- Limited contextual information
- No dimensional support

### XBRL Facts Data Model
```python
class Fact(BaseModel):  # Pydantic model with validation
    element_id: str
    context_ref: str
    value: str
    unit_ref: Optional[str] = None
    decimals: Optional[Union[int, str]] = None
    numeric_value: Optional[float] = None  # Typed numeric value
    footnotes: List[str] = Field(default_factory=list)
    instance_id: Optional[int] = None

# Enriched fact dictionary from FactsView.get_facts()
{
    'concept': 'us-gaap:Revenue',
    'label': 'Revenue',
    'value': '365817000000',
    'numeric_value': 365817000000.0,  # Properly typed
    'period_start': '2023-10-01',
    'period_end': '2024-09-30',
    'period_type': 'duration',
    'statement_type': 'IncomeStatement',
    'fiscal_year': 2024,
    'fiscal_period': 'FY',
    'unit_ref': 'usd',
    'decimals': -6
}
```

**Advantages**:
- Strong typing with Pydantic validation
- Rich contextual metadata
- Statement type classification
- Dimensional qualifier support
- Proper numeric type conversion

## User Experience Analysis

### Current Pain Points for Users

#### Entity Facts Confusion
```python
# User expects this to work but gets confused:
facts = company.get_facts()  # Returns EntityFacts
# How do I get revenue? Users must:
df = facts.to_pandas()       # Convert to DataFrame
revenue = df[df['fact'].str.contains('Revenue', case=False)]  # Manual search
```

#### XBRL Facts Isolation
```python
# XBRL facts are rich but isolated to single filings:
xbrl = filing.xbrl()
revenue = xbrl.facts.query().by_concept('Revenue').to_dataframe()
# But no easy way to get historical trend across filings
```

#### Type Inconsistencies
```python
# Entity facts: CIK as int, mixed value types
entity_facts = get_company_facts(320193)  # int CIK

# XBRL concept: CIK as string  
concept = get_concept("0000320193", "us-gaap", "Revenue")  # string CIK

# Users face runtime errors from type mismatches
```

### Strategic User Expectations

Users expect these systems to work together seamlessly:

1. **Cross-System Concept Mapping**: Same concept should be queryable in both systems
2. **Consistent Data Types**: CIKs, values, dates should have consistent types
3. **Progressive Disclosure**: Start with entity overview, drill into filing details
4. **Investment-Focused Workflows**: Built-in calculations and comparisons

## Alignment Opportunities

### 1. Unified Fact Data Model

**Recommended Approach**: Create a common `FinancialFact` base class:

```python
@dataclass
class FinancialFact:
    """Unified fact representation across both systems"""
    concept: str                    # Standardized concept identifier
    taxonomy: str                   # us-gaap, ifrs, etc.
    value: Union[float, int, str]   # Properly typed value
    numeric_value: Optional[float]  # Always available for numeric facts
    unit: str                       # USD, shares, etc.
    
    # Temporal information
    period_start: Optional[date]
    period_end: date
    period_type: Literal['instant', 'duration']
    
    # Filing context
    filing_date: date
    form_type: str
    accession: str
    
    # Investment metadata
    fiscal_year: int
    fiscal_period: str
    
    # Quality indicators
    data_quality_score: float       # 0-1 confidence
    is_calculated: bool            # Derived vs reported
    
    # XBRL-specific (optional)
    context_ref: Optional[str] = None
    dimensions: Dict[str, str] = field(default_factory=dict)
    statement_type: Optional[str] = None
```

### 2. Query Interface Standardization

**Both systems should support similar query patterns**:

```python
# Entity facts (enhanced)
company = Company("AAPL")
facts = company.get_facts()  # Returns enhanced EntityFacts

# Query interface matching XBRL patterns
revenue_history = facts.query().by_concept('Revenue').to_dataframe()
income_facts = facts.query().by_statement_type('IncomeStatement').to_dataframe()

# XBRL facts (existing)
xbrl = filing.xbrl()
revenue_current = xbrl.facts.query().by_concept('Revenue').to_dataframe()
```

### 3. Cross-System Integration

**Enable seamless workflows**:

```python
# Unified company analysis
company = Company("AAPL")

# Get historical context from entity facts
revenue_trend = company.facts.query().by_concept('Revenue').time_series(years=5)

# Get detailed breakdown from latest filing
latest_filing = company.latest_10k()
revenue_details = latest_filing.xbrl().facts.query().by_concept('Revenue').to_dataframe()

# System automatically matches concepts and enables comparison
comparison = company.facts.compare_with_filing(latest_filing, concept='Revenue')
```

### 4. Investment-Focused Enhancements

**Both systems should support investment workflows**:

```python
# Built-in ratio calculations
ratios = company.facts.calculate_ratios(['pe_ratio', 'debt_to_equity', 'current_ratio'])

# Peer comparison
peers = company.facts.get_peer_comparison(['MSFT', 'GOOGL'], metrics=['revenue', 'net_income'])

# Anomaly detection
red_flags = company.facts.detect_anomalies()
```

## Strategic Differentiation

### Preserve Distinct Value Propositions

#### Entity Facts: Historical & Comparative Analysis
- **Strength**: Multi-year trending and peer comparison
- **Enhancement**: Add investment-focused calculations and anomaly detection
- **Target Users**: Portfolio managers, research analysts, quantitative researchers

#### XBRL Facts: Deep Dive & Validation
- **Strength**: Rich context and filing-specific analysis
- **Enhancement**: Better integration with entity-level trends
- **Target Users**: Financial statement analysts, auditors, compliance professionals

### Recommended Positioning

```python
# Entity Facts: "The Timeline View"
company.facts.get_trend('Revenue', years=10)
company.facts.compare_to_peers(['MSFT', 'GOOGL'])
company.facts.detect_earnings_smoothing()

# XBRL Facts: "The Microscope View"  
filing.xbrl().facts.validate_calculations()
filing.xbrl().facts.get_dimensional_breakdown('Revenue', 'BusinessSegment')
filing.xbrl().facts.find_restatements()
```

## Implementation Roadmap

### Phase 1: Foundation (2-4 weeks)
- [ ] Create unified `FinancialFact` data model
- [ ] Standardize type system (int CIKs, proper date types)
- [ ] Add query interface to EntityFacts
- [ ] Create concept mapping between systems

### Phase 2: Integration (3-4 weeks)
- [ ] Cross-system concept resolution
- [ ] Historical context in XBRL facts
- [ ] Progressive disclosure patterns
- [ ] Comprehensive test coverage

### Phase 3: Investment Features (4-6 weeks)
- [ ] Built-in ratio calculations
- [ ] Peer comparison capabilities
- [ ] Anomaly detection algorithms
- [ ] Data quality scoring

### Phase 4: Polish & Performance (2-3 weeks)
- [ ] Performance optimization
- [ ] Documentation and examples
- [ ] Migration guides
- [ ] User experience validation

## Success Metrics

### Developer Experience
- **Reduce cognitive load**: Single mental model for facts across systems
- **Eliminate type errors**: Consistent data types prevent runtime failures
- **Accelerate workflows**: Common patterns work across both systems

### Investment Utility
- **Built-in analytics**: 20+ financial ratios calculated automatically
- **Peer comparison**: One-line peer analysis across industry groups
- **Quality indicators**: Confidence scores for all fact values

### System Health
- **Performance**: Sub-second queries for cached historical data
- **Reliability**: 99.9% uptime for fact retrieval operations
- **Consistency**: 100% concept mapping accuracy between systems

## Risk Mitigation

### Backward Compatibility
- Maintain existing APIs during transition period
- Provide clear deprecation timeline (6+ months)
- Offer automated migration tools

### Performance Regression
- Benchmark current performance before changes
- Implement incremental improvements with rollback capability
- Monitor query performance in production

### User Adoption
- Create comprehensive examples showing new capabilities
- Provide migration guides with before/after code samples
- Gather feedback from power users during beta period

## Conclusion

The entity facts and XBRL facts systems serve complementary purposes but suffer from inconsistencies that harm user experience. Strategic alignment around a unified data model and query interface will preserve their distinct strengths while eliminating friction.

The investment-focused enhancements will transform both systems from basic data access layers into powerful financial analysis tools, aligning with EdgarTools' strategic direction toward comprehensive investment workflows.

**Key Success Factor**: Maintain backward compatibility while progressively enhancing capabilities, ensuring users can adopt improvements at their own pace without disrupting existing workflows.