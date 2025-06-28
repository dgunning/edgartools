# Enhanced Statement Access Design for Cross-Company Standardization

## Executive Summary

This design document outlines improvements to the XBRL statements system to enable standardized access across different companies' filing patterns. Based on analysis of NVIDIA vs Apple 10-K filings, the current system has limitations in handling naming variations and accessing detailed business sections. The proposed enhancements will provide universal statement resolution, business section discovery, and attachment integration while maintaining backward compatibility.

## Current System Analysis

### Existing Architecture (edgar/xbrl/statements.py)

**Core Classes:**
- `Statement`: Individual statement wrapper with rendering and analysis
- `Statements`: High-level interface for statement collections
- `StitchedStatement`/`StitchedStatements`: Multi-period statement handling

**Current Strengths:**
- Well-structured OOP design
- Rich console output with categorization
- Period filtering and rendering capabilities
- Basic statement type mapping via `statement_to_concepts`
- Ratio calculation and trend analysis

### Identified Limitations

1. **Rigid Statement Type Mapping**
   - Hard-coded `statement_to_concepts` dictionary
   - Fails on NVIDIA's "CONSOLIDATEDSTATEMENTSOFINCOME" vs Apple's "CONSOLIDATEDSTATEMENTSOFOPERATIONS"
   - No fuzzy matching for statement name variations

2. **Basic Indexing System**
   - Simple string matching in `__getitem__` method
   - Limited fallback logic when exact matches fail
   - No confidence scoring for multiple matches

3. **No Business Section Discovery**
   - Cannot find detailed schedules like lease payment tables
   - No pattern-based section identification
   - Missing connection between summary statements and detailed breakdowns

4. **Limited Pattern Recognition**
   - No regex-based matching for statement variations
   - Inflexible to company-specific naming conventions
   - Poor handling of parenthetical vs non-parenthetical statements

5. **Missing Attachment Integration**
   - No connection to R-file detailed schedules
   - Cannot access granular data from HTML attachments
   - Missed opportunity for comprehensive financial analysis

## Proposed Design Improvements

### 1. Universal Statement Type Resolution System

**Objective**: Handle cross-company variations in statement naming

**Design**: Multi-tier pattern matching with confidence scoring

```python
UNIVERSAL_STATEMENT_PATTERNS = {
    "IncomeStatement": [
        r"CONSOLIDATEDSTATEMENTSOFINCOME",        # NVIDIA pattern
        r"CONSOLIDATEDSTATEMENTSOFOPERATIONS",    # Apple pattern
        r"STATEMENTSOFINCOME",
        r"STATEMENTSOFOPERATIONS",
        r"INCOMESTATEMENT"
    ],
    "BalanceSheet": [
        r"CONSOLIDATEDBALANCESHEETS?",
        r"BALANCESHEETS?",
        r"STATEMENTOFFINANCIALPOSITION"
    ],
    "CashFlowStatement": [
        r"CONSOLIDATEDSTATEMENTSOFCASHFLOWS?",
        r"STATEMENTSOFCASHFLOWS?",
        r"CASHFLOWSTATEMENTS?"
    ],
    "StatementOfEquity": [
        r"CONSOLIDATEDSTATEMENTSOFSHAREHOLDERSEQUITY",
        r"CONSOLIDATEDSTATEMENTSOFSTOCKHOLDERSEQUITY",
        r"STATEMENTSOFSHAREHOLDERSEQUITY",
        r"STATEMENTSOFSTOCKHOLDERSEQUITY"
    ],
    "ComprehensiveIncome": [
        r"CONSOLIDATEDSTATEMENTSOFCOMPREHENSIVEINCOME",
        r"STATEMENTSOFCOMPREHENSIVEINCOME"
    ]
}
```

**New Class**: `StatementResolver`
- Fuzzy matching with confidence scores
- Multiple pattern matching strategies
- Graceful fallback logic
- Cross-reference validation using multiple criteria

### 2. Business Section Discovery System

**Objective**: Enable discovery of detailed business sections across companies

**Design**: Pattern-based section categorization with standardized access

```python
BUSINESS_SECTION_PATTERNS = {
    "leases": {
        "main": [r"Leases(?!.*\(Tables\)|.*Details)"],
        "tables": [r"Leases.*\(Tables\)"],
        "payment_schedule": [
            r"Lease.*(?:Schedule|Payment|Maturities).*Details",
            r"Future.*Lease.*Payment.*Details",
            r"Lease.*Liability.*Maturities.*Details"
        ],
        "narrative": [r"Lease.*Narrative.*Details"],
        "rou_assets": [r"ROU.*Assets.*Lease.*Details"]
    },
    "stock_compensation": {
        "main": [r"(?:Stock.?Based|Share.?Based)\s*Compensation(?!.*\(Tables\)|.*Details)"],
        "tables": [r"(?:Stock.?Based|Share.?Based).*Compensation.*\(Tables\)"],
        "expense_details": [r"(?:Stock.?Based|Share.?Based).*Compensation.*Expense.*Details"],
        "award_details": [
            r"(?:Stock.?Based|Share.?Based).*(?:Equity|Awards?).*Details",
            r"Restricted.*Stock.*Unit.*Activity.*Details"
        ],
        "plan_details": [r"(?:Stock.?Based|Share.?Based).*(?:Incentive|Plans?).*Details"]
    },
    "segments": {
        "main": [r"Segment\s*Information(?!.*\(Tables\)|.*Details)"],
        "tables": [r"Segment.*Information.*\(Tables\)"],
        "geographic": [
            r"(?:Geographic|Region).*Details",
            r"Revenue.*Region.*Details",
            r"Long.?lived.*Assets.*Region.*Details"
        ],
        "reconciliation": [r".*Reconcil.*Segment.*Details"],
        "reportable": [r"Reportable.*Segment.*Details"]
    },
    "debt": {
        "main": [r"Debt(?!.*\(Tables\)|.*Details)"],
        "tables": [r"Debt.*\(Tables\)"],
        "schedule": [
            r"Debt.*(?:Schedule|Payment|Future).*Details",
            r"Future.*Principal.*Payment.*Details"
        ],
        "term_debt": [r"Term\s*Debt.*Details"],
        "commercial_paper": [r"Commercial.*Paper.*Details"]
    },
    "income_taxes": {
        "main": [r"Income\s*Taxes(?!.*\(Tables\)|.*Details)"],
        "tables": [r"Income\s*Taxes.*\(Tables\)"],
        "reconciliation": [r"Income\s*Tax.*Reconciliation.*Details"],
        "deferred": [r"Deferred\s*Tax.*Details"],
        "components": [r"Components.*Income.*Tax.*Details"],
        "unrecognized": [r"Unrecognized.*Tax.*Benefits.*Details"]
    },
    "financial_instruments": {
        "main": [r"Financial\s*Instruments(?!.*\(Tables\)|.*Details)"],
        "tables": [r"Financial\s*Instruments.*\(Tables\)"],
        "fair_value": [r"Fair.*Value.*Financial.*Details"],
        "derivatives": [r"Derivative.*Instruments.*Details"],
        "marketable_securities": [r"Marketable.*Securities.*Details"]
    }
}
```

**New Methods**:
- `statements.get_lease_schedule()` → detailed lease payment schedules
- `statements.get_stock_compensation_details()` → equity award breakdowns
- `statements.get_segment_geographic_breakdown()` → regional revenue data
- `statements.get_business_section(category, detail_type)` → generic section finder

### 3. Enhanced Statement Categorization

**Current**: Basic 5-category system (statement, note, disclosure, document, other)

**Enhanced**: Hierarchical categorization with business context

```python
ENHANCED_CATEGORIES = {
    'financial_statements': {
        'core': ['BalanceSheet', 'IncomeStatement', 'CashFlowStatement'],
        'supplementary': ['ComprehensiveIncome', 'StatementOfEquity'],
        'parenthetical': ['BalanceSheetParenthetical', 'IncomeStatementParenthetical']
    },
    'business_disclosures': {
        'operational': ['leases', 'stock_compensation', 'segments', 'revenue'],
        'financial': ['debt', 'derivatives', 'fair_value', 'financial_instruments'],
        'regulatory': ['income_taxes', 'commitments', 'contingencies'],
        'strategic': ['business_combinations', 'goodwill', 'intangibles']
    },
    'supporting_schedules': {
        'payment_schedules': ['lease_payments', 'debt_maturities', 'future_commitments'],
        'detailed_breakdowns': ['segment_details', 'geographic_revenue', 'product_revenue'],
        'reconciliations': ['tax_reconciliation', 'segment_reconciliation', 'eps_reconciliation']
    }
}
```

### 4. Smart Statement Resolution Engine

**New Class**: `StatementResolver`

```python
class StatementResolver:
    def resolve_statement_type(self, statement_name: str) -> ResolvedStatement:
        """Resolve statement with confidence scoring and multiple matches"""
        
    def find_best_match(self, patterns: List[str], candidates: List[str]) -> MatchResult:
        """Find best pattern match with confidence score"""
        
    def cross_validate_match(self, resolved_statement: ResolvedStatement) -> bool:
        """Validate match using multiple criteria (concepts, structure, etc.)"""
        
    def get_fallback_options(self, failed_match: str) -> List[ResolvedStatement]:
        """Provide alternative matches when primary resolution fails"""
```

**Features**:
- Fuzzy string matching for typos and variations
- Confidence scoring (0.0 to 1.0) for ranking matches
- Multiple validation criteria (name, concepts, structure)
- Graceful degradation with suggested alternatives
- Learning capability to improve matching over time

### 5. Attachment Integration Framework

**Objective**: Connect XBRL statements with detailed attachment schedules

**Design**: Bidirectional linking between statements and attachments

```python
class StatementWithAttachments(Statement):
    def get_supporting_attachments(self) -> List[Attachment]:
        """Find R-files that provide detailed breakdowns for this statement"""
        
    def get_detailed_schedules(self) -> Dict[str, Attachment]:
        """Get specific detailed schedules (payment schedules, breakdowns, etc.)"""
        
    def get_lease_payment_schedule(self) -> Optional[Attachment]:
        """Get detailed lease payment schedule from attachments"""
        
    def get_stock_compensation_breakdown(self) -> Optional[Attachment]:
        """Get detailed equity award information from attachments"""
        
    def get_segment_geographic_data(self) -> Optional[Attachment]:
        """Get geographic revenue breakdown from attachments"""
        
    def get_reconciliation_schedules(self) -> List[Attachment]:
        """Get reconciliation schedules related to this statement"""
```

**Attachment Discovery Logic**:
- Pattern matching between XBRL statement names and R-file descriptions
- Content analysis to identify supporting schedules
- Cross-reference validation using common data elements
- Hierarchical relationship mapping (summary → details)

### 6. Period View Enhancement

**Current**: Basic period filtering
**Enhanced**: Context-aware period selection

```python
class SmartPeriodManager:
    def get_optimal_periods(self, statement_type: str, context: str = "quarterly") -> List[str]:
        """Return best periods based on statement type and analysis context"""
        
    def align_periods_across_statements(self, statement_types: List[str]) -> Dict[str, List[str]]:
        """Ensure consistent period alignment for multi-statement analysis"""
        
    def detect_period_patterns(self, statements: List[Statement]) -> PeriodPattern:
        """Analyze and categorize period patterns (quarterly, annual, interim)"""
        
    def suggest_comparison_periods(self, base_period: str, statement_type: str) -> List[str]:
        """Suggest meaningful comparison periods for trend analysis"""
```

## New API Design

### Enhanced Statements Class

```python
class Statements:
    # Existing methods remain unchanged for backward compatibility
    
    # Universal access with intelligent resolution
    def get_statement(self, statement_identifier: str, confidence_threshold: float = 0.8) -> Statement:
        """Get statement with fuzzy matching and confidence scoring"""
        
    def find_statements(self, pattern: str) -> List[Tuple[Statement, float]]:
        """Find all statements matching pattern with confidence scores"""
    
    # Business section discovery
    def get_lease_details(self) -> BusinessSectionGroup:
        """Get all lease-related sections organized by detail level"""
        
    def get_lease_payment_schedule(self) -> Optional[Statement]:
        """Get specific lease payment schedule section"""
        
    def get_stock_compensation_breakdown(self) -> BusinessSectionGroup:
        """Get detailed stock compensation data"""
        
    def get_segment_analysis(self) -> BusinessSectionGroup:
        """Get comprehensive segment information"""
        
    def get_business_section(self, category: str, detail_type: str = None) -> BusinessSectionGroup:
        """Generic business section finder with category and detail type"""
    
    # Enhanced categorization
    def get_operational_disclosures(self) -> List[Statement]:
        """Get all operational business disclosures"""
        
    def get_financial_disclosures(self) -> List[Statement]:
        """Get all financial instrument and debt disclosures"""
        
    def get_supporting_schedules(self) -> List[Statement]:
        """Get all detailed supporting schedules"""
        
    def get_by_business_category(self, category: str) -> List[Statement]:
        """Get statements by enhanced business category"""
    
    # Cross-statement analysis
    def get_related_sections(self, statement_type: str) -> List[Statement]:
        """Find all sections that provide supporting detail for a statement"""
        
    def build_statement_hierarchy(self) -> StatementHierarchy:
        """Build hierarchical view showing relationships between statements"""
```

### Enhanced Statement Class

```python
class Statement:
    # Existing methods remain unchanged
    
    # Enhanced data access
    def get_concept_trends(self, concept_name: str, periods: int = 4) -> Dict[str, List[float]]:
        """Get trends for specific concepts across periods"""
        
    def find_related_disclosures(self) -> List[Statement]:
        """Find disclosure sections that provide detail for this statement"""
        
    def get_detailed_breakdowns(self) -> List[Attachment]:
        """Get attachment files that provide detailed breakdowns"""
        
    def get_supporting_attachments(self) -> List[Attachment]:
        """Get all attachments that support this statement"""
    
    # Smart period handling
    def render_optimal_periods(self, context: str = "quarterly") -> Any:
        """Render with automatically selected optimal periods"""
        
    def align_with_statement(self, other_statement: Statement) -> Tuple[Any, Any]:
        """Render both statements with aligned periods for comparison"""
        
    # Enhanced validation and quality checks
    def validate_completeness(self) -> ValidationResult:
        """Check statement completeness and data quality"""
        
    def suggest_related_analysis(self) -> List[AnalysisSuggestion]:
        """Suggest related analyses based on statement type and available data"""
```

### New Supporting Classes

```python
@dataclass
class ResolvedStatement:
    statement: Statement
    confidence: float
    match_method: str
    alternatives: List[Tuple[Statement, float]]

@dataclass 
class BusinessSectionGroup:
    category: str
    main_section: Statement
    tables: List[Statement]
    details: List[Statement]
    schedules: List[Statement]
    attachments: List[Attachment]

@dataclass
class MatchResult:
    matched_item: Any
    confidence: float
    match_type: str  # 'exact', 'fuzzy', 'pattern', 'fallback'
    explanation: str

class StatementHierarchy:
    def get_summary_statements(self) -> List[Statement]
    def get_supporting_details(self, statement: Statement) -> List[Statement]
    def get_detailed_schedules(self, statement: Statement) -> List[Statement]
    def visualize(self) -> str  # ASCII tree representation
```

## Implementation Strategy

### Phase 1: Universal Statement Resolution (2-3 weeks)
**Priority**: High - Fixes immediate cross-company compatibility issues

1. **Add Pattern Matching System**
   - Define `UNIVERSAL_STATEMENT_PATTERNS` dictionary
   - Implement regex-based matching logic
   - Add confidence scoring algorithm

2. **Enhance `__getitem__` Method**
   - Add fuzzy matching fallback
   - Implement confidence thresholding
   - Provide alternative suggestions for failed matches

3. **Create `StatementResolver` Class**
   - Centralize resolution logic
   - Add cross-validation methods
   - Implement match explanation system

4. **Backward Compatibility**
   - Ensure existing code continues to work
   - Add deprecation warnings for old patterns
   - Provide migration guide

### Phase 2: Business Section Discovery (3-4 weeks)
**Priority**: High - Enables access to detailed financial data

1. **Define Business Section Patterns**
   - Create `BUSINESS_SECTION_PATTERNS` dictionary
   - Test patterns against NVIDIA and Apple filings
   - Validate pattern coverage across multiple companies

2. **Implement Section Discovery Engine**
   - Create `BusinessSectionGroup` class
   - Implement pattern matching logic
   - Add section relationship mapping

3. **Add Convenience Methods**
   - `get_lease_schedule()`, `get_stock_compensation_details()`
   - Generic `get_business_section()` method
   - Section-specific rendering and analysis

4. **Testing and Validation**
   - Test against multiple company filings
   - Validate data accuracy and completeness
   - Performance optimization for large statement sets

### Phase 3: Enhanced Categorization (2-3 weeks)
**Priority**: Medium - Improves usability and organization

1. **Implement Enhanced Category System**
   - Define `ENHANCED_CATEGORIES` hierarchy
   - Create category detection logic
   - Add business context awareness

2. **Add Category-Based Access Methods**
   - `get_operational_disclosures()`, `get_financial_disclosures()`
   - Category-filtered display methods
   - Smart grouping and organization

3. **Improve Display and Navigation**
   - Enhanced Rich console output
   - Hierarchical statement trees
   - Interactive navigation helpers

### Phase 4: Attachment Integration (4-5 weeks)
**Priority**: Medium - Provides comprehensive data access

1. **Design Attachment-Statement Linking**
   - Create attachment discovery algorithms
   - Implement relationship mapping
   - Add content validation logic

2. **Implement `StatementWithAttachments`**
   - Add attachment access methods
   - Create unified data views
   - Implement cross-reference validation

3. **Add Detailed Schedule Access**
   - Specific methods for common schedules
   - Generic attachment discovery
   - Data consistency validation

4. **Integration Testing**
   - Test with multiple filing types
   - Validate data accuracy
   - Performance optimization

### Phase 5: Period Management Enhancement (2-3 weeks)
**Priority**: Low - Nice-to-have for advanced analysis

1. **Implement `SmartPeriodManager`**
   - Context-aware period selection
   - Period alignment algorithms
   - Pattern detection and analysis

2. **Add Period Optimization**
   - Optimal period selection for different analyses
   - Automatic period alignment
   - Trend analysis enhancements

3. **Enhanced Rendering Options**
   - Context-sensitive period views
   - Comparative rendering
   - Period-aware formatting

## Benefits and Impact

### Immediate Benefits
1. **Cross-Company Compatibility**: Single API works across NVIDIA, Apple, and other companies
2. **Enhanced Data Discovery**: Easy access to detailed business sections and schedules
3. **Improved Usability**: Intelligent resolution reduces user friction
4. **Better Error Handling**: Confidence scoring and alternatives for failed matches

### Long-term Benefits
1. **Scalability**: Pattern-based approach adapts to new companies and filing variations
2. **Comprehensive Analysis**: Integration with attachments provides complete financial picture
3. **Future-Proof Design**: Flexible architecture accommodates SEC reporting changes
4. **Enhanced Analytics**: Deeper data access enables more sophisticated financial analysis

### Backward Compatibility
- All existing code continues to work unchanged
- Gradual migration path with deprecation warnings
- Enhanced functionality available through new methods
- No breaking changes to core APIs

## Success Metrics

1. **Coverage**: Successfully handle 95%+ of S&P 500 company statement variations
2. **Performance**: Statement resolution within 100ms for 95th percentile
3. **Accuracy**: 98%+ correct statement type identification with confidence > 0.8
4. **Usability**: 80% reduction in failed statement access attempts
5. **Adoption**: New business section discovery methods used in 50%+ of financial analyses

## Risk Mitigation

1. **Performance Impact**: Implement caching and lazy loading for pattern matching
2. **False Positives**: Require minimum confidence thresholds and validation
3. **Complexity**: Maintain simple primary APIs while adding advanced features
4. **Maintenance**: Create automated tests against multiple company filings
5. **User Adoption**: Provide comprehensive documentation and migration guides

This design provides a robust foundation for standardized financial statement access across companies while maintaining the flexibility to handle unique variations and provide deep analytical capabilities.