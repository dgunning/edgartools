# XBRL Concept Standardization Design

## Overview

Financial statements in XBRL use different concept names and labels across companies, making it difficult to compare statements between entities. The XBRL2 standardization module addresses this challenge by mapping company-specific concepts to a standardized set of concepts, enabling consistent presentation of financial statements regardless of the entity.

## Components

### StandardConcept

An enumeration defining canonical concept names for financial statements, organized by statement type:

```python
class StandardConcept(str, Enum):
    # Balance Sheet - Assets
    CASH_AND_EQUIVALENTS = "Cash and Cash Equivalents"
    TOTAL_ASSETS = "Total Assets"
    
    # Income Statement
    REVENUE = "Revenue"
    NET_INCOME = "Net Income"
    
    # Cash Flow Statement
    CASH_FROM_OPERATIONS = "Cash from Operating Activities"
```

### MappingStore

Storage system for concept mappings:

- Persists mappings in JSON format
- Maps standard concepts to sets of company-specific concepts
- Provides methods to add, retrieve, and update mappings

### ConceptMapper

Maps company-specific concepts to standard concepts using multiple approaches:

1. **Direct mapping**: Uses existing known mappings from the `MappingStore`
2. **Label similarity**: Compares concept labels to standard concept names
3. **Contextual rules**: Uses statement type, position, and calculation relationships
4. **Confidence scoring**: Evaluates mapping quality with confidence scores

### Integration with Rendering

The standardization system integrates with the existing statement rendering system via:

1. A `standard=True` parameter in `render_statement()` methods
2. The `standardize_statement()` function to transform statement data

## Implementation

### Usage Example

```python
from edgar.xbrl2.xbrl import XBRL
from edgar.xbrl2.statements import Statements

# Parse XBRL files
xbrl = XBRL.parse_directory('path/to/xbrl/files')
statements = Statements(xbrl)

# Display with company-specific labels
original_income_stmt = statements.income_statement()

# Display with standardized labels
standardized_income_stmt = statements.income_statement(standard=True)
```

### Default Mappings

The system comes with predefined mappings for common concepts:

```json
{
  "Revenue": [
    "us-gaap_Revenue", 
    "us-gaap_SalesRevenueNet",
    "us-gaap_Revenues"
  ],
  "Net Income": [
    "us-gaap_NetIncome",
    "us-gaap_NetIncomeLoss",
    "us-gaap_ProfitLoss"
  ]
}
```

## Future Enhancements

1. **Learning System**
   - Automated batch processing to learn from XBRL filings
   - Self-improving mappings based on statistical patterns

2. **Taxonomy Awareness**
   - Leverage taxonomic relationships in US-GAAP and IFRS
   - Use concept hierarchies to improve mapping accuracy

3. **ML-Based Similarity**
   - Replace simple string matching with ML embeddings
   - Train models on large datasets of financial statements

4. **User Feedback Loop**
   - Interface for analysts to validate proposed mappings
   - Progressive refinement based on expert feedback

5. **Cross-Company Analytics**
   - Enable ratio analysis across companies
   - Facilitate industry comparisons using standardized metrics