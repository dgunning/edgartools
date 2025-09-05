# Plan for Concept-Level Standardization in EdgarTools

## Current State Analysis

EdgarTools already has **sophisticated standardization infrastructure**:

1. **XBRL Standardization Package** (`edgar.xbrl.standardization`):
   - `StandardConcept` enum with 100+ predefined concepts
   - `ConceptMapper` with ML-based inference (similarity matching)
   - `MappingStore` with 352 lines of concept mappings
   - Company-specific mapping support
   - Automatic learning from filing patterns

2. **Facts API Integration** (`edgar.entity.entity_facts`):
   - Raw SEC CompanyFacts API data
   - Unit standardization (`_clean_unit()`)
   - No concept standardization currently

3. **Financials Module** (`edgar.financials`):
   - Uses `_get_standardized_concept_value()` 
   - Pattern-based label matching for key metrics
   - Limited to specific financial ratios

## Gap Analysis

**✅ What Works Well:**
- XBRL package has comprehensive concept standardization
- Company-specific mappings with priority system
- ML-based concept inference with confidence scoring
- Extensive mapping database (352 lines)

**❌ What's Missing:**
- Facts API doesn't use XBRL standardization
- No unified standardization across data sources
- Limited integration between packages
- No user-facing standardization controls

## Proposed Implementation Plan

### Phase 1: Bridge XBRL Standardization to Facts API

**1.1 Enhance EntityFacts with Standardization**
```python
# edgar/entity/entity_facts.py - Add standardization support
class EntityFacts:
    def __init__(self, cik: int, name: str, facts: List[FinancialFact], enable_standardization: bool = True):
        self._standardization_enabled = enable_standardization
        if enable_standardization:
            from edgar.xbrl.standardization import initialize_default_mappings, ConceptMapper
            self._mapping_store = initialize_default_mappings()
            self._concept_mapper = ConceptMapper(self._mapping_store)

    def get_standardized_fact(self, standard_concept: str, period: Optional[str] = None) -> Optional[FinancialFact]:
        """Get fact using standardized concept names."""
        if not self._standardization_enabled:
            return self.get_fact(standard_concept, period)
        
        # Map standard concept to company concepts
        company_concepts = self._mapping_store.get_company_concepts(standard_concept)
        
        for concept in company_concepts:
            fact = self.get_fact(concept, period)
            if fact:
                # Create standardized copy
                std_fact = fact.copy()
                std_fact.concept = standard_concept
                std_fact.label = standard_concept
                return std_fact
        
        return None
```

**1.2 Add Standardized Query Interface**
```python
# edgar/entity/query.py - Enhance FactQuery
class FactQuery:
    def by_standard_concept(self, standard_concept: str, exact: bool = True) -> 'FactQuery':
        """Filter by standardized concept name."""
        if hasattr(self._entity_facts, '_concept_mapper'):
            # Get all company concepts that map to this standard concept
            company_concepts = self._entity_facts._mapping_store.get_company_concepts(standard_concept)
            # Filter by any of these concepts
            return self.by_concept_list(list(company_concepts), exact=exact)
        else:
            # Fallback to direct concept matching
            return self.by_concept(standard_concept, exact=exact)
```

### Phase 2: Unified Standardization Configuration

**2.1 Global Standardization Settings**
```python
# edgar/core.py - Add standardization controls
_standardization_enabled = True
_standardization_mode = "aggressive"  # "conservative", "aggressive", "strict"

def enable_standardization(mode: str = "aggressive"):
    """Enable concept standardization globally."""
    global _standardization_enabled, _standardization_mode
    _standardization_enabled = True
    _standardization_mode = mode

def disable_standardization():
    """Disable concept standardization globally."""
    global _standardization_enabled
    _standardization_enabled = False

def get_standardization_config():
    return {
        'enabled': _standardization_enabled,
        'mode': _standardization_mode
    }
```

**2.2 Enhanced Concept Mapping**
```python
# edgar/xbrl/standardization/core.py - Extend mapping capabilities
class ConceptMapper:
    def get_all_standard_concepts_for_company(self, cik: int) -> Dict[str, List[str]]:
        """Get all standardized concepts available for a specific company."""
        # Analyze company's actual concepts and return mappings
        
    def suggest_mappings(self, unknown_concepts: List[str], context: Dict = None) -> Dict[str, List[Tuple[str, float]]]:
        """Suggest standard concept mappings for unknown concepts."""
        # ML-based suggestions with confidence scores
        
    def validate_mapping_quality(self, cik: int) -> Dict[str, Any]:
        """Assess mapping quality and coverage for a company."""
        # Return coverage stats, confidence scores, missing concepts
```

### Phase 3: User-Facing Standardization API

**3.1 Standardized Facts Interface**
```python
# edgar/standardization/__init__.py - New top-level module
from edgar.xbrl.standardization import StandardConcept, ConceptMapper, MappingStore

class StandardizedEntityFacts:
    """Wrapper for EntityFacts with standardization as first-class feature."""
    
    def __init__(self, entity_facts: EntityFacts):
        self.raw_facts = entity_facts
        self._mapper = ConceptMapper(initialize_default_mappings())
    
    def revenue(self, period: str = None) -> Optional[FinancialFact]:
        """Get revenue using standardized concept mapping."""
        return self.get_fact(StandardConcept.REVENUE, period)
    
    def net_income(self, period: str = None) -> Optional[FinancialFact]:
        """Get net income using standardized concept mapping."""
        return self.get_fact(StandardConcept.NET_INCOME, period)
    
    def get_fact(self, standard_concept: StandardConcept, period: str = None) -> Optional[FinancialFact]:
        """Get fact by standard concept enum."""
        return self.raw_facts.get_standardized_fact(standard_concept.value, period)
        
    def available_concepts(self) -> List[StandardConcept]:
        """Get all standard concepts available for this company."""
        # Return intersection of company concepts and standard mappings
```

**3.2 Comparison-Friendly Interface**
```python
# Cross-company standardized comparison
def compare_companies(tickers: List[str], concepts: List[StandardConcept], periods: int = 4) -> pd.DataFrame:
    """Compare standardized concepts across multiple companies."""
    data = []
    for ticker in tickers:
        company = Company(ticker)
        std_facts = StandardizedEntityFacts(company.facts)
        
        for concept in concepts:
            for i in range(periods):
                fact = std_facts.get_fact(concept, period_offset=i)
                if fact:
                    data.append({
                        'company': ticker,
                        'concept': concept.value,
                        'period': f"{fact.fiscal_year}-{fact.fiscal_period}",
                        'value': fact.numeric_value,
                        'unit': fact.unit
                    })
    
    return pd.DataFrame(data).pivot_table(
        index=['concept', 'period'],
        columns='company',
        values='value'
    )
```

### Phase 4: Enhanced Learning and Quality

**4.1 Automated Concept Discovery**
```python
# edgar/xbrl/standardization/learning.py
class ConceptLearner:
    def discover_new_concepts(self, companies: List[str]) -> Dict[str, List[str]]:
        """Discover frequently used concepts not in standard mappings."""
        
    def validate_existing_mappings(self) -> Dict[str, float]:
        """Validate mapping accuracy across sample companies."""
        
    def suggest_new_standard_concepts(self, threshold: float = 0.1) -> List[str]:
        """Suggest new standard concepts based on usage frequency."""
```

**4.2 Quality Metrics**
```python
# Standardization quality metrics
class StandardizationQuality:
    def coverage_score(self, cik: int) -> float:
        """Percentage of company concepts that have standard mappings."""
        
    def confidence_score(self, cik: int) -> float:
        """Average confidence of applied mappings."""
        
    def consistency_score(self, concept: str, companies: List[int]) -> float:
        """How consistently a concept is mapped across companies."""
```

## Integration Plan

### Step 1: Minimal Integration (Week 1)
- Add `enable_standardization=True` parameter to `EntityFacts`
- Implement `get_standardized_fact()` method
- Basic testing with AAPL, MSFT, TSLA

### Step 2: Enhanced Query Interface (Week 2)
- Extend `FactQuery` with `by_standard_concept()`
- Add standardization to income/balance/cashflow statement methods
- Documentation and examples

### Step 3: User-Facing API (Week 3)
- Create `StandardizedEntityFacts` wrapper
- Implement cross-company comparison tools
- Add standardization controls to `edgar.core`

### Step 4: Advanced Features (Week 4)
- Learning pipeline integration
- Quality metrics and validation
- Performance optimization and caching

## Usage Examples

```python
# Enable standardization globally
import edgar
edgar.enable_standardization(mode="aggressive")

# Standard concept access
company = edgar.Company("AAPL")
facts = company.facts

# Access by standard concept
revenue = facts.get_standardized_fact("Revenue")
net_income = facts.get_standardized_fact("Net Income")

# Enhanced query with standardization
revenue_series = facts.query().by_standard_concept("Revenue").latest(4).to_dataframe()

# Cross-company comparison
comparison = edgar.compare_companies(
    tickers=["AAPL", "MSFT", "GOOGL"],
    concepts=[StandardConcept.REVENUE, StandardConcept.NET_INCOME],
    periods=4
)

# Quality assessment
quality = edgar.assess_standardization_quality("AAPL")
print(f"Coverage: {quality['coverage']:.1%}")
print(f"Confidence: {quality['confidence']:.1%}")
```

## Benefits of This Approach

1. **Leverages Existing Infrastructure**: Uses the comprehensive XBRL standardization already built
2. **Backward Compatible**: Existing code continues to work unchanged
3. **Opt-in Standardization**: Users can enable/disable as needed
4. **Cross-Package Integration**: Unifies XBRL and Facts API standardization
5. **Extensible**: Easy to add new standard concepts and mappings
6. **Quality-Focused**: Built-in validation and confidence scoring

This plan provides a pathway to bring EdgarTools' existing sophisticated standardization capabilities to the concept level while maintaining the library's core principles of simplicity and user-friendliness.

## Implementation Context

This plan was developed based on analysis of EdgarTools' existing standardization infrastructure:

- **XBRL Package**: Comprehensive `StandardConcept` enum, `ConceptMapper` with ML inference, extensive mapping database (352 lines)
- **Facts API**: Raw SEC data with unit standardization but no concept standardization
- **Financials Module**: Limited pattern-based label matching for key metrics
- **Gap**: No unified standardization across data sources or user-facing controls

The proposed approach bridges these systems to provide concept-level standardization while maintaining EdgarTools' design principles.