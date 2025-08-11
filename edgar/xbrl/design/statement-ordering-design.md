# Statement Ordering Design for Multi-Period Stitching

## Problem Statement

When stitching financial statements across multiple periods, line items appear in inconsistent order due to:

1. **Different granularity** across periods (consolidated vs. detailed line items)
2. **Varying labels** for the same concepts across filings
3. **New line items** appearing in some periods but not others
4. **Current alphabetical sorting** destroying logical financial statement flow

### Example of the Issue

**Single Period (Correct Order):**
```
Revenue                     $391,035
Cost of Goods Sold        $(210,352)
Gross Profit                $180,683
Operating Expenses          $(57,467)
Operating Income            $123,216
Net Income                   $93,736
```

**Multi-Period Stitched (Incorrect Order):**
```
Revenue                     $391,035    $383,285
Cost of Goods Sold        $(210,352)   $(214,137)
Gross Profit                $180,683    $169,148
Income Before Tax            123,485     113,736
Net Income                   $93,736     $96,995
Operating Expenses          $(57,467)   $(54,847)  ← Wrong position
Operating Income            $123,216    $114,301
```

## Root Cause Analysis

The issue occurs in `/edgar/xbrl/stitching/core.py:440-443`:

```python
ordered_concepts = sorted(
    self.concept_metadata.items(),
    key=lambda x: (x[1]['level'], x[0])  # Sorts alphabetically by label within level
)
```

This destroys the original presentation order by sorting alphabetically, causing "Operating Expenses" to appear after "Net Income" instead of before "Operating Income".

## Design Goals

1. **Preserve logical financial statement flow** across multiple periods
2. **Handle varying granularity** between filings gracefully
3. **Position new concepts** semantically when they appear in some periods
4. **Maintain backward compatibility** with existing statement rendering
5. **Support different statement types** (Income Statement, Balance Sheet, Cash Flow)

## Proposed Solution: Hybrid Ordering System

### 1. Multi-Strategy Ordering Framework

Use multiple ordering strategies with fallback priorities:

```python
class StatementOrderingManager:
    """Manages consistent ordering across multi-period statements"""
    
    def __init__(self, statement_type: str):
        self.statement_type = statement_type
        self.template_order = self._load_template_order()
        self.reference_order = {}
        self.semantic_rules = self._load_semantic_rules()
    
    def determine_ordering(self, statements: List[Dict]) -> Dict[str, float]:
        """
        Determine unified ordering for all concepts across statements.
        
        Returns:
            Dict mapping concept -> sort_key (float for interpolation)
        """
        all_concepts = self._extract_all_concepts(statements)
        
        # Strategy 1: Template-based ordering (highest priority)
        template_positioned = self._apply_template_ordering(all_concepts)
        
        # Strategy 2: Reference statement ordering
        reference_positioned = self._apply_reference_ordering(
            all_concepts, statements, template_positioned
        )
        
        # Strategy 3: Semantic positioning for orphan concepts
        final_ordering = self._apply_semantic_positioning(
            all_concepts, template_positioned, reference_positioned
        )
        
        return final_ordering
```

### 2. Template-Based Ordering

Define canonical templates for each statement type:

```python
class FinancialStatementTemplates:
    """Canonical ordering templates for financial statements"""
    
    INCOME_STATEMENT_TEMPLATE = [
        # Revenue Section (0-99)
        (0, "revenue_section", [
            "Product Revenue",
            "Service Revenue",
            "Subscription Revenue", 
            "Contract Revenue",
            "Total Revenue",
            "Revenue"
        ]),
        
        # Cost Section (100-199)
        (100, "cost_section", [
            "Cost of Goods Sold",
            "Cost of Sales", 
            "Cost of Revenue",
            "Cost of Goods and Services Sold"
        ]),
        
        # Gross Profit (200-299)
        (200, "gross_profit", ["Gross Profit"]),
        
        # Operating Expenses (300-399)
        (300, "operating_expenses", [
            "Research and Development Expense",
            "Selling, General and Administrative Expense",
            "Marketing Expense",
            "Sales Expense",
            "Operating Expenses"  # Consolidated version
        ]),
        
        # Operating Income (400-499)
        (400, "operating_income", ["Operating Income"]),
        
        # Non-Operating (500-599)
        (500, "non_operating", [
            "Interest Income",
            "Interest Expense", 
            "Other Income",
            "Nonoperating Income/Expense"
        ]),
        
        # Pre-Tax Income (600-699)
        (600, "pretax_income", [
            "Income Before Tax",
            "Income Before Tax from Continuing Operations"
        ]),
        
        # Tax (700-799)
        (700, "tax", ["Income Tax Expense"]),
        
        # Net Income (800-899)
        (800, "net_income", [
            "Net Income from Continuing Operations",
            "Net Income"
        ]),
        
        # Per Share Data (900-999)
        (900, "per_share", [
            "Earnings Per Share (Basic)",
            "Earnings Per Share (Diluted)",
            "Shares Outstanding (Basic)",
            "Shares Outstanding (Diluted)"
        ])
    ]
    
    BALANCE_SHEET_TEMPLATE = [
        # Current Assets (0-199)
        (0, "current_assets", [
            "Cash and Cash Equivalents",
            "Short-term Investments",
            "Accounts Receivable", 
            "Inventory",
            "Prepaid Expenses",
            "Total Current Assets"
        ]),
        
        # Non-Current Assets (200-399)
        (200, "noncurrent_assets", [
            "Property, Plant and Equipment",
            "Goodwill",
            "Intangible Assets", 
            "Long-term Investments",
            "Total Assets"
        ]),
        
        # Current Liabilities (400-599)
        (400, "current_liabilities", [
            "Accounts Payable",
            "Accrued Liabilities",
            "Short-term Debt",
            "Current Portion of Long-term Debt",
            "Total Current Liabilities"
        ]),
        
        # Non-Current Liabilities (600-799)
        (600, "noncurrent_liabilities", [
            "Long-term Debt",
            "Deferred Revenue",
            "Deferred Tax Liabilities",
            "Total Liabilities"
        ]),
        
        # Equity (800-999)
        (800, "equity", [
            "Common Stock",
            "Additional Paid-in Capital", 
            "Retained Earnings",
            "Accumulated Other Comprehensive Income",
            "Total Stockholders' Equity"
        ])
    ]
    
    def get_template_position(self, concept_label: str, statement_type: str) -> Optional[float]:
        """Get template position for a concept"""
        template = getattr(self, f"{statement_type.upper()}_TEMPLATE", None)
        if not template:
            return None
            
        for base_pos, section_name, concepts in template:
            for i, template_concept in enumerate(concepts):
                if self._concepts_match(concept_label, template_concept):
                    return base_pos + i
                    
        return None
    
    def _concepts_match(self, concept1: str, concept2: str) -> bool:
        """Check if two concepts represent the same financial item"""
        # Normalize for comparison
        norm1 = self._normalize_concept(concept1)
        norm2 = self._normalize_concept(concept2)
        
        # Exact match
        if norm1 == norm2:
            return True
            
        # Fuzzy matching for similar concepts
        from difflib import SequenceMatcher
        similarity = SequenceMatcher(None, norm1, norm2).ratio()
        return similarity > 0.85
    
    def _normalize_concept(self, concept: str) -> str:
        """Normalize concept for comparison"""
        import re
        # Remove common variations
        normalized = concept.lower()
        normalized = re.sub(r'\s+', ' ', normalized)  # Normalize whitespace
        normalized = re.sub(r'[,\.]', '', normalized)  # Remove punctuation
        normalized = re.sub(r'\(.*?\)', '', normalized)  # Remove parenthetical
        return normalized.strip()
```

### 3. Reference Statement Strategy

Use the most recent or most complete statement as ordering reference:

```python
class ReferenceOrderingStrategy:
    """Extract ordering from reference statement"""
    
    def establish_reference_order(self, statements: List[Dict]) -> Dict[str, float]:
        """Establish reference ordering from best available statement"""
        
        # Strategy: Use most recent statement (statements are ordered newest first)
        reference_statement = statements[0]
        
        # Alternative strategies:
        # reference_statement = self._find_most_complete_statement(statements)
        # reference_statement = self._find_most_detailed_statement(statements)
        
        reference_order = {}
        for i, item in enumerate(reference_statement['data']):
            concept = item.get('concept')
            label = item.get('label')
            
            if concept:
                # Store by both concept ID and label for flexibility
                reference_order[concept] = float(i)
                if label:
                    reference_order[label] = float(i)
                    
        return reference_order
    
    def _find_most_complete_statement(self, statements: List[Dict]) -> Dict:
        """Find statement with most line items"""
        return max(statements, key=lambda s: len(s['data']))
    
    def _find_most_detailed_statement(self, statements: List[Dict]) -> Dict:
        """Find statement with most granular breakdown"""
        def detail_score(statement):
            # Score based on number of non-abstract items and depth
            score = 0
            for item in statement['data']:
                if not item.get('is_abstract', False):
                    score += 1
                # Add bonus for deeper hierarchy
                score += item.get('level', 0) * 0.1
            return score
            
        return max(statements, key=detail_score)
```

### 4. Semantic Positioning

Position new concepts based on financial statement semantics:

```python
class SemanticPositioning:
    """Position concepts based on financial statement semantics"""
    
    def __init__(self, statement_type: str):
        self.statement_type = statement_type
        self.semantic_rules = self._load_semantic_rules()
    
    def infer_position(self, concept: str, existing_order: Dict[str, float]) -> float:
        """Infer semantic position for a new concept"""
        
        # Rule-based positioning
        section = self._classify_concept_section(concept)
        if section:
            return self._position_in_section(concept, section, existing_order)
        
        # Parent-child relationship positioning
        parent = self._find_parent_concept(concept, existing_order)
        if parent:
            return existing_order[parent] + 0.1  # Just after parent
        
        # Similarity-based positioning
        similar_concept = self._find_most_similar_concept(concept, existing_order)
        if similar_concept:
            return existing_order[similar_concept] + 0.1
        
        # Default to end
        return 999.0
    
    def _classify_concept_section(self, concept: str) -> Optional[str]:
        """Classify concept into financial statement section"""
        concept_lower = concept.lower()
        
        if self.statement_type == "IncomeStatement":
            if any(term in concept_lower for term in ['revenue', 'sales', 'income']):
                if any(term in concept_lower for term in ['cost', 'expense']):
                    return None  # Could be cost or revenue - need more analysis
                return "revenue"
            elif any(term in concept_lower for term in ['cost', 'cogs']):
                return "cost"
            elif any(term in concept_lower for term in ['expense', 'r&d', 'research']):
                return "expense"
            elif 'gross profit' in concept_lower:
                return "gross_profit"
            elif 'operating income' in concept_lower:
                return "operating_income"
            elif 'net income' in concept_lower:
                return "net_income"
        
        return None
    
    def _position_in_section(self, concept: str, section: str, existing_order: Dict[str, float]) -> float:
        """Position concept within its identified section"""
        section_concepts = [
            (label, pos) for label, pos in existing_order.items()
            if self._classify_concept_section(label) == section
        ]
        
        if not section_concepts:
            # Section doesn't exist yet - use template defaults
            return self._get_default_section_position(section)
        
        # Find best position within section
        section_concepts.sort(key=lambda x: x[1])  # Sort by position
        
        # Simple strategy: place at end of section
        last_pos = section_concepts[-1][1]
        return last_pos + 0.1
    
    def _find_parent_concept(self, concept: str, existing_order: Dict[str, float]) -> Optional[str]:
        """Find parent concept in hierarchy"""
        # Look for hierarchical relationships
        # e.g., "Software Revenue" -> "Revenue"
        concept_words = set(concept.lower().split())
        
        candidates = []
        for existing_concept in existing_order.keys():
            existing_words = set(existing_concept.lower().split())
            
            # Check if existing concept is a parent (subset of words)
            if existing_words.issubset(concept_words) and len(existing_words) < len(concept_words):
                candidates.append((existing_concept, len(existing_words)))
        
        if candidates:
            # Return the most specific parent (most words in common)
            return max(candidates, key=lambda x: x[1])[0]
        
        return None
    
    def _find_most_similar_concept(self, concept: str, existing_order: Dict[str, float]) -> Optional[str]:
        """Find most similar existing concept"""
        from difflib import SequenceMatcher
        
        best_match = None
        best_similarity = 0.0
        
        for existing_concept in existing_order.keys():
            similarity = SequenceMatcher(None, concept.lower(), existing_concept.lower()).ratio()
            if similarity > best_similarity and similarity > 0.5:  # Minimum threshold
                best_similarity = similarity
                best_match = existing_concept
        
        return best_match
```

### 5. Integration with StatementStitcher

Update the core stitching logic to use the new ordering system:

```python
class StatementStitcher:
    """Enhanced StatementStitcher with improved ordering"""
    
    def __init__(self, concept_mapper: Optional[ConceptMapper] = None):
        # ... existing initialization ...
        self.ordering_manager = None
    
    def stitch_statements(self, statements: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """Enhanced stitching with proper ordering"""
        
        # ... existing setup code ...
        
        # Initialize ordering manager
        statement_type = statements[0].get('statement_type', 'IncomeStatement') if statements else 'IncomeStatement'
        self.ordering_manager = StatementOrderingManager(statement_type)
        
        # ... existing processing code ...
        
        return self._format_output_with_ordering()
    
    def _format_output_with_ordering(self) -> Dict[str, Any]:
        """Format output using intelligent ordering"""
        
        # Get unified ordering for all concepts
        concept_ordering = self.ordering_manager.determine_ordering(self.processed_statements)
        
        # Sort concepts using the unified ordering
        ordered_concepts = sorted(
            self.concept_metadata.items(),
            key=lambda x: (
                x[1]['level'],  # Primary: respect hierarchy levels
                concept_ordering.get(x[0], 999.0),  # Secondary: semantic ordering
                x[0]  # Tertiary: alphabetical fallback
            )
        )
        
        # ... rest of formatting logic ...
```

### 6. Implementation Plan

#### Phase 1: Core Infrastructure (Week 1-2)
1. Create `StatementOrderingManager` class
2. Implement `FinancialStatementTemplates` with Income Statement template
3. Add basic semantic positioning rules
4. Update `StatementStitcher._format_output()` to use new ordering

#### Phase 2: Template Expansion (Week 3)
1. Add Balance Sheet and Cash Flow templates
2. Implement fuzzy concept matching
3. Add comprehensive semantic rules
4. Create unit tests for ordering logic

#### Phase 3: Advanced Features (Week 4)
1. Implement reference statement strategy
2. Add parent-child relationship detection
3. Create fallback ordering strategies
4. Performance optimization and caching

#### Phase 4: Integration & Testing (Week 5)
1. Integration testing with real XBRL data
2. Performance benchmarking
3. Documentation updates
4. Backward compatibility verification

### 7. Configuration and Extensibility

```python
# Allow customization via configuration
ORDERING_CONFIG = {
    "strategy_priority": ["template", "reference", "semantic", "alphabetical"],
    "fuzzy_matching_threshold": 0.85,
    "enable_parent_child_detection": True,
    "enable_similarity_positioning": True,
    "section_spacing": 10.0  # Gap between major sections
}

class ConfigurableOrderingManager(StatementOrderingManager):
    """Configurable version for advanced users"""
    
    def __init__(self, statement_type: str, config: Dict = None):
        super().__init__(statement_type)
        self.config = {**ORDERING_CONFIG, **(config or {})}
    
    def add_custom_template(self, template: List[Tuple]):
        """Allow users to add custom ordering templates"""
        self.custom_templates.append(template)
    
    def set_semantic_rules(self, rules: Dict):
        """Allow custom semantic positioning rules"""
        self.semantic_rules.update(rules)
```

## Expected Benefits

1. **Consistent ordering** across multi-period statements
2. **Logical financial flow** preserved (Revenue → COGS → Gross Profit → Expenses → Operating Income → Net Income)
3. **Graceful handling** of varying granularity between periods
4. **Intelligent positioning** of new line items based on semantics
5. **Extensible design** for different statement types and custom rules

## Backward Compatibility

The new ordering system will be:
- **Opt-in initially** with a feature flag
- **Backward compatible** with existing statement rendering
- **Configurable** to allow customization
- **Non-breaking** for existing API consumers

This design provides a robust foundation for consistent multi-period statement ordering while maintaining the flexibility to handle real-world variations in XBRL filings.