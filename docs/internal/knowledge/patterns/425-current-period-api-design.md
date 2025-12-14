# GitHub Issue #425: Current Period Only API Implementation Plan

## Issue Summary

**User Request**: Need a straightforward way to get current period only data for 10-K, 10-Q, including:
1. Current period only (not comparative multi-period data)
2. Access to raw XBRL tags instead of just standardized labels
3. Same functionality for notes sections following financial statements

## Current State Analysis

### Existing Capabilities (Hidden/Hard to Discover)
1. **Period Filtering**: `period_filter` parameter exists but requires knowledge of specific period keys
2. **XBRL Tag Access**: `standard=False` parameter exposes raw concepts but poorly documented
3. **Notes Access**: `statements.notes()` method exists but lacks current-period and XBRL tag features

### Gap Analysis
- **Discovery Problem**: Users don't know about existing `period_filter` and `standard=False` parameters
- **Usability Problem**: Current period filtering requires manual period key lookup
- **API Inconsistency**: Notes don't support the same period/XBRL tag options as statements
- **Documentation Gap**: Raw XBRL tag access not well explained or demonstrated

## Proposed Solution Architecture

### Phase 1: Enhanced Current Period API

#### 1.1 Add `current_only` Parameter to Statement Methods
```python
# New signature for all statement methods
def income_statement(self, parenthetical: bool = False, 
                    current_only: bool = False,
                    xbrl_tags: bool = False) -> Optional[Statement]:
```

#### 1.2 Automatic Current Period Detection
```python
class Statements:
    def get_current_period(self) -> Optional[str]:
        """Get the most recent period key automatically."""
        # Logic to identify the document period end date
        # Return the period key for current reporting period
        
    def _apply_current_period_filter(self, statement_method, current_only: bool):
        """Internal method to apply current period filtering."""
        if current_only:
            period_key = self.get_current_period()
            if period_key:
                return statement_method(period_filter=period_key)
```

#### 1.3 Enhanced Notes API
```python
class Statements:
    def notes(self, current_only: bool = False, xbrl_tags: bool = False) -> List[Statement]:
        """Get note sections with current period and XBRL tag options."""
        
    def note(self, index_or_name: Union[int, str], 
             current_only: bool = False, 
             xbrl_tags: bool = False) -> Optional[Statement]:
        """Get a specific note with enhanced options."""
```

### Phase 2: XBRL Tag Access Enhancement

#### 2.1 Unified `xbrl_tags` Parameter
Replace confusing `standard=False` with clear `xbrl_tags=True`:
```python
# Current (confusing)
statement.render(standard=False)

# New (clear)
statement.render(xbrl_tags=True)
```

#### 2.2 XBRL Tag Metadata Enhancement
```python
@dataclass
class StatementRow:
    label: str
    level: int
    cells: List[StatementCell]
    metadata: Dict[str, Any]  # Enhanced with:
    # - concept: Raw XBRL concept name
    # - namespace: XBRL namespace 
    # - element_type: Element type (monetary, text, etc.)
    # - period_type: instant/duration
    xbrl_concept: Optional[str] = None  # Direct access to XBRL concept
```

#### 2.3 XBRL Concept Search and Access
```python
class Statement:
    def get_concept_value(self, concept: str, current_only: bool = False) -> Any:
        """Get value for a specific XBRL concept."""
        
    def search_concepts(self, pattern: str) -> List[str]:
        """Search available XBRL concepts in this statement."""
        
    def get_all_concepts(self) -> Dict[str, Any]:
        """Get all XBRL concepts and their values."""
```

### Phase 3: Enhanced Documentation and Examples

#### 3.1 Quick Start Examples
```python
# Example 1: Current period balance sheet with XBRL tags
balance_sheet = filing.xbrl.statements.balance_sheet(current_only=True, xbrl_tags=True)

# Example 2: Current period notes with raw concepts
notes = filing.xbrl.statements.notes(current_only=True, xbrl_tags=True)
current_note = filing.xbrl.statements.note("Revenue Recognition", current_only=True, xbrl_tags=True)

# Example 3: Access specific XBRL concepts
revenue_concept = income_stmt.get_concept_value("us-gaap:Revenues")
custom_revenue = income_stmt.get_concept_value("company:CustomRevenueMetric")
```

#### 3.2 Migration Guide
- Document how `standard=False` maps to `xbrl_tags=True`
- Show period filtering evolution
- Provide concept lookup patterns

## Implementation Strategy

### Phase 1: Core API Enhancement (Week 1-2)
1. **Add `current_only` parameter** to all statement methods
2. **Implement automatic current period detection**
3. **Enhance notes API** with same parameters
4. **Create comprehensive tests** for new functionality

### Phase 2: XBRL Tag Access (Week 3)
1. **Add `xbrl_tags` parameter** (alias for `standard=False`)
2. **Enhance statement metadata** with XBRL concept information
3. **Add concept search and access methods**
4. **Update rendering** to show XBRL concepts when requested

### Phase 3: Documentation and Examples (Week 4)
1. **Create comprehensive examples** showing new patterns
2. **Update API documentation** with clear use cases
3. **Add troubleshooting guide** for common XBRL concept issues
4. **Create migration guide** from old to new patterns

## Backwards Compatibility

### Maintained Compatibility
- All existing `period_filter` and `standard` parameters continue to work
- No breaking changes to existing API
- Existing statement access patterns unchanged

### Deprecation Strategy
- `standard=False` becomes alias for `xbrl_tags=True`
- Add deprecation warnings in future versions
- Provide migration path in documentation

## Edge Cases and Challenges

### 1. Current Period Detection
- **Challenge**: Different filing types have different period structures
- **Solution**: Use document period end date from cover page as anchor
- **Fallback**: Most recent period if document period unavailable

### 2. XBRL Concept Variations
- **Challenge**: Company-specific extensions and namespaces
- **Solution**: Support both us-gaap and company-specific concepts
- **Enhancement**: Provide concept search functionality

### 3. Notes Structure Variability
- **Challenge**: Notes have diverse structures across companies
- **Solution**: Treat notes as generic statements with enhanced metadata
- **Documentation**: Provide examples of different note types

### 4. Performance Considerations
- **Challenge**: Period filtering may impact performance
- **Solution**: Cache current period detection results
- **Optimization**: Lazy evaluation of period data

## Success Metrics

### User Experience Metrics
1. **Discoverability**: New API patterns appear in top search results
2. **Usage Adoption**: `current_only` and `xbrl_tags` parameters show uptake
3. **Support Reduction**: Fewer questions about period filtering and XBRL concepts

### Technical Metrics  
1. **Test Coverage**: 100% coverage for new API patterns
2. **Performance**: No regression in existing statement rendering speed
3. **Compatibility**: All existing tests pass without modification

## Documentation Examples

### Before (Current State)
```python
# Hard to discover, requires knowledge of internals
filing = company.get_filings().latest()
xbrl = filing.obj()
statements = xbrl.statements

# Need to manually find current period
periods = xbrl.reporting_periods
current_period = periods[0]['key'] if periods else None

# Render with period filter (not obvious)
balance_sheet = statements.balance_sheet().render(period_filter=current_period, standard=False)
```

### After (Proposed State)
```python
# Clear, discoverable API
filing = company.get_filings().latest() 
xbrl = filing.obj()
statements = xbrl.statements

# Simple, clear API
balance_sheet = statements.balance_sheet(current_only=True, xbrl_tags=True)
notes = statements.notes(current_only=True, xbrl_tags=True)
```

## Risk Mitigation

### Technical Risks
1. **Breaking Changes**: Comprehensive testing prevents regressions
2. **Performance Impact**: Benchmarking ensures no slowdowns
3. **Complexity**: Phased rollout allows for course correction

### User Experience Risks
1. **API Confusion**: Clear naming and documentation prevent confusion
2. **Migration Difficulty**: Compatibility layer eases transition
3. **Feature Discovery**: Examples and documentation improve discoverability

## Conclusion

This implementation plan addresses all three user requests while:
- Maintaining full backwards compatibility
- Following EdgarTools philosophy of simplicity and beginner-friendliness  
- Providing a clear migration path for existing users
- Enhancing the overall developer experience for financial data access

The phased approach allows for iterative improvement and user feedback incorporation while delivering immediate value to users who need current-period-only access to financial statements and notes with raw XBRL concepts.