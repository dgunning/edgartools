# Design Document: Statement Matching

Develop a robust system to identify and classify financial statements and their components in XBRL-based SEC filings, distinguishing between parenthetical and non-parenthetical information. This system provides a multi-layered approach to statement identification using role names, primary concepts, content analysis, and contextual hints.

## Components to Classify

- **Financial Statements**: Core statements such as Income Statement, Balance Sheet, Cash Flow Statement, Statement of Equity, and Comprehensive Income.
- **Notes**: Detailed explanations and breakdowns accompanying the financial statements.
- **Disclosures**: Additional required disclosures, often overlapping with notes in XBRL filings.
- **Other Definitions**: Miscellaneous sections like Cover Page, signatures, or exhibits.
- **Parenthetical Statements**: Supplemental details embedded within financial statements (e.g., in parentheses), tagged separately in XBRL.
- **Non-Parenthetical Statements**: Primary line items or sections in financial statements without supplemental breakdowns.

## Current Implementation Assessment

Our current implementation has strengths in certain areas but can be improved:

### Strengths
- Multi-layered matching using primary concepts, role URIs, role names, and definitions
- Pre-building of lookup indices for faster retrieval
- Handling of parenthetical statements for balance sheets
- Centralized statement finder logic (`find_statement` method)
- Support for custom taxonomies

### Limitations
- Parenthetical handling is currently limited to balance sheets
- Limited fallback strategies when primary concepts aren't found
- Heavy reliance on specific US GAAP taxonomy patterns
- Potential for missed matches when companies use non-standard role naming
- No machine learning to improve matching over time

## Enhanced Matching Strategy

We propose a more comprehensive, flexible approach with additional layers of fallback:

### 1. Primary Concept Matching
- Continue to use the `statement_to_concepts` dictionary as the primary mechanism
- Extend with alternative/synonymous concepts for each statement type
- Add confidence scores for concept matches

### 2. Role URI and Custom Namespace Recognition
- Implement pattern-based matching for role URIs using regex
- Identify common patterns like `.../role/StatementOf`, `.../BalanceSheet`, etc.
- Handle company-specific namespaces (e.g., 'unp_CondensedConsolidatedStatementsOfIncomeUnauditedAbstract')
- Parse concept names to extract statement type regardless of namespace prefix
- Allow for company-specific patterns with optional configuration

### 3. Content-Based Analysis
- Analyze statement content for characteristic concepts (e.g., Assets, Revenue)
- Calculate a "fingerprint" of key concepts for each statement type
- Match statements by calculating similarity with known fingerprints
- Weight more important concepts higher (e.g., NetIncomeLoss for Income Statement)

### 4. Role Definition Text Analysis
- Apply NLP techniques to extract statement types from role definitions
- Create a dictionary of common statement name variations
- Implement fuzzy matching to handle spelling variations and word order

### 5. Statement Structure Analysis
- Analyze the hierarchy and relationships between concepts
- Use typical structural patterns (e.g., Balance Sheet has Assets, Liabilities, Equity sections)
- Leverage calculation relationships for additional validation

### 6. Combined Confidence Scoring
- Assign confidence scores from each matching method
- Weight and combine scores for final statement type determination
- Set configurable thresholds for accepting matches

## Detailed Implementation Design

### 1. Enhanced Statement Type Registry

Expand the current `statement_to_concepts` dictionary to include:

```python
statement_registry = {
    "BalanceSheet": {
        "primary_concepts": ["us-gaap_StatementOfFinancialPositionAbstract"],
        "alternative_concepts": ["us-gaap_BalanceSheetAbstract"],
        "concept_patterns": [
            r".*_StatementOfFinancialPositionAbstract$",
            r".*_BalanceSheetAbstract$",
            r".*_ConsolidatedBalanceSheetsAbstract$",
            r".*_CondensedConsolidatedBalanceSheetsUnauditedAbstract$"
        ],
        "key_concepts": ["us-gaap_Assets", "us-gaap_Liabilities", "us-gaap_StockholdersEquity"],
        "common_role_patterns": [
            r".*[Bb]alance[Ss]heet.*",
            r".*[Ss]tatement[Oo]f[Ff]inancial[Pp]osition.*",
            r".*StatementConsolidatedBalanceSheets.*"
        ],
        "title": "Consolidated Balance Sheets",
        "supports_parenthetical": True,
        "typical_weights": {"assets": 0.3, "liabilities": 0.3, "equity": 0.4}
    },
    "IncomeStatement": {
        "primary_concepts": ["us-gaap_IncomeStatementAbstract"],
        "alternative_concepts": ["us-gaap_StatementOfIncomeAbstract"],
        "concept_patterns": [
            r".*_IncomeStatementAbstract$",
            r".*_StatementOfIncomeAbstract$",
            r".*_ConsolidatedStatementsOfIncomeAbstract$", 
            r".*_CondensedConsolidatedStatementsOfIncomeUnauditedAbstract$"
        ],
        "key_concepts": ["us-gaap_Revenues", "us-gaap_NetIncomeLoss"],
        "common_role_patterns": [
            r".*[Ii]ncome[Ss]tatement.*",
            r".*[Ss]tatement[Oo]f[Ii]ncome.*",
            r".*StatementConsolidatedStatementsOfIncome.*"
        ],
        "title": "Consolidated Statement of Income",
        "supports_parenthetical": True,
        "typical_weights": {"revenues": 0.4, "netIncomeLoss": 0.6}
    },
    # Additional statement types...
}
```

### 2. Tiered Matching Algorithm

Implement a multi-tier matching process that tries progressively broader matching strategies:

```
1. Exact match by primary concept
2. Match by alternative concepts
3. Role URI pattern matching
4. Content analysis of key concepts
5. Role definition text analysis
6. Structural similarity analysis
7. Combined confidence scoring
```

Each tier assigns a confidence score, and we select the statement type with the highest combined score.

### 3. Parenthetical Statement Detection

Extend parenthetical detection beyond just Balance Sheets:

- Check for 'parenthetical' in role definition for all statement types
- Look for specific parenthetical-related concepts
- Check for patterns in the hierarchy suggesting parenthetical information
- Identify common parenthetical elements (e.g., shares outstanding, weighted average shares)

### 4. Caching and Performance Optimizations

- Pre-build multiple lookup indices for rapid statement retrieval
- Cache statement finding results for repeated access
- Use lazy loading for expensive statement analysis
- Optimize content analysis with vectorized operations

### 5. Statement Resolver Class

Create a dedicated `StatementResolver` class to encapsulate the matching logic:

```python
class StatementResolver:
    def __init__(self, xbrl):
        self.xbrl = xbrl
        self._cache = {}
        self._initialize_indices()
        
    def _initialize_indices(self):
        # Build lookup indices
        
    def find_statement(self, role_or_type, parenthetical=False):
        # Implement tiered matching algorithm
        
    def _match_by_primary_concept(self, statement_type, is_parenthetical=False):
        # Match using primary concepts with parenthetical consideration
        
    def _match_by_role_pattern(self, role_or_type):
        # Match using role URI patterns
        
    def _match_by_content(self, role_or_type):
        # Match by analyzing statement content
        
    def _calculate_confidence_score(self, statement, statement_type):
        # Calculate confidence score for a match
        
    def resolve(self, role_or_type, parenthetical=False):
        # Return best match with confidence score
```

## Implementation Plan

### Phase 1: Refactoring Current Implementation
- Extract statement matching logic into a dedicated module
- Improve existing primary concept matching
- Extend parenthetical detection to all statement types
- Add comprehensive unit tests for matching logic

### Phase 2: Enhanced Matching Methods
- Implement role pattern matching
- Add content-based analysis
- Develop confidence scoring system
- Create fallback mechanisms

### Phase 3: Advanced Features
- Add machine learning-based classification
- Implement custom taxonomy handling
- Support for combined statements
- User feedback mechanism to improve matching

### Phase 4: Optimization and Documentation
- Performance optimizations
- Comprehensive documentation
- Example usage patterns
- Extension points for custom matching rules

## Challenges and Mitigations

### Challenge: Custom Taxonomies
**Mitigation**: Implement a learning system that records custom taxonomy patterns encountered in filings and improves matching over time.

### Challenge: Combined Statements
**Mitigation**: Detect when a statement contains elements from multiple standard statement types and classify appropriately.

### Challenge: Performance Impact
**Mitigation**: Use tiered matching with early exit when high confidence matches are found; cache results aggressively.

### Challenge: Evolving Taxonomies
**Mitigation**: Design the system to be taxonomy-version aware and include version-specific matching rules.

## Future Enhancements

### Machine Learning Classification
Implement a ML model trained on labeled XBRL data to classify statements with high accuracy.

### Self-Improving System
Record matches and user corrections to continuously improve matching accuracy.

### Custom Taxonomy Registry
Build a registry of company-specific taxonomy patterns for more accurate matching.

### Definition Linkbase Integration
Leverage relationships in the definition linkbase to supplement the presentation hierarchy analysis.

### Interactive Disambiguation
For low-confidence matches, provide an interactive interface for users to disambiguate statement types.

## Sample Implementation

The core of the implementation would center around an improved `find_statement` method:

```python
def find_statement(self, statement_type, is_parenthetical=False):
    """
    Find a statement by type, with multi-layered fallback approach.
    
    Args:
        statement_type: Statement type or identifier
        is_parenthetical: Whether to look for parenthetical version
        
    Returns:
        (matching_statements, found_role, confidence_score)
    """
    # If this is an exact match to a role URI we already know, return immediately
    if statement_type in self._statement_by_role_uri:
        return [self._statement_by_role_uri[statement_type]], statement_type, 1.0
    
    # Try primary concept matching first (highest confidence)
    match = self._match_by_primary_concept(statement_type, is_parenthetical)
    if match and match[2] > 0.8:  # High confidence threshold
        return match
    
    # Try custom namespace matching
    match = self._match_by_concept_pattern(statement_type, is_parenthetical)
    if match and match[2] > 0.8:  # High confidence for concept pattern matches
        return match
        
    # Try role pattern matching
    match = self._match_by_role_pattern(statement_type)
    if match and match[2] > 0.7:  # Good confidence threshold
        return match
        
    # Try content-based analysis
    match = self._match_by_content(statement_type)
    if match and match[2] > 0.6:  # Moderate confidence threshold
        return match
        
    # Try structure analysis as last resort
    match = self._match_by_structure(statement_type)
    if match and match[2] > 0.5:  # Lower confidence but still useful
        return match
        
    # No good match found, return best attempt with low confidence
    return self._get_best_guess(statement_type), None, 0.3
```

And here's how the concept pattern matching would be implemented:

```python
def _match_by_concept_pattern(self, statement_type, is_parenthetical=False):
    """
    Match statements using regex patterns on concept names to handle custom company namespaces.
    
    Args:
        statement_type: Statement type to match 
        is_parenthetical: Whether to look for parenthetical version
        
    Returns:
        (matching_statements, found_role, confidence_score)
    """
    # If we're looking for a standard statement type
    if statement_type in self.statement_registry:
        registry_entry = self.statement_registry[statement_type]
        concept_patterns = registry_entry.get("concept_patterns", [])
        
        if not concept_patterns:
            return None, None, 0.0
            
        # Get all statements to check against patterns
        all_statements = self.get_all_statements()
        
        # Check each statement's primary concept against our patterns
        matched_statements = []
        for stmt in all_statements:
            primary_concept = stmt.get('primary_concept', '')
            
            # Skip if no primary concept
            if not primary_concept:
                continue
                
            # Check if this concept matches any of our patterns
            for pattern in concept_patterns:
                if re.match(pattern, primary_concept):
                    # For parenthetical statements, check the role definition
                    if is_parenthetical:
                        role_def = stmt.get('definition', '').lower()
                        if 'parenthetical' not in role_def:
                            continue
                    # For non-parenthetical, skip if has parenthetical
                    elif not is_parenthetical:
                        role_def = stmt.get('definition', '').lower()
                        if 'parenthetical' in role_def:
                            continue
                            
                    matched_statements.append(stmt)
                    break  # Found a match, no need to check other patterns
                    
        # If we found matching statements, return the first one with high confidence
        if matched_statements:
            return matched_statements, matched_statements[0]['role'], 0.85
            
    return None, None, 0.0
```

This design provides a flexible, extensible framework for statement matching that will work across different companies, taxonomies, and statement variants while maintaining high performance.