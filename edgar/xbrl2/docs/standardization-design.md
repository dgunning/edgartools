# XBRL Concept Standardization Design

## Overview

Financial statements in XBRL use different concept names and labels across companies, making it difficult to compare statements between entities. The XBRL2 standardization module addresses this challenge by mapping company-specific concepts to a standardized set of concepts, enabling consistent presentation of financial statements regardless of the entity.

## Revised Design

### 1. Single Source of Truth

The revised design establishes a clear hierarchy for concept mappings:

1. **Primary Source**: All mappings are defined in `concept_mappings.json`
   - This file contains all standard mappings between XBRL concepts and standardized names
   - The file is organized by standardized concept names (e.g., "Revenue") mapping to lists of XBRL concepts (e.g., "us-gaap_Revenue")
   - This is the ONLY place to add or modify simple concept mappings

2. **Programmatic Mappings**: Complex mapping logic remains in Python code
   - The `ConceptMapper` class in `standardization.py` handles complex mapping logic that can't be expressed in JSON
   - This includes contextual rules, similarity matching, and confidence scoring
   - No direct concept mappings should be defined in Python code

### 2. Components

#### StandardConcept

An enumeration defining canonical concept names for financial statements, organized by statement type:

```python
class StandardConcept(str, Enum):
    # Balance Sheet - Assets
    CASH_AND_EQUIVALENTS = "Cash and Cash Equivalents"
    TOTAL_ASSETS = "Total Assets"
    # Other concepts...
    
    @classmethod
    def get_from_label(cls, label: str) -> Optional['StandardConcept']:
        """Get a StandardConcept enum by its label value."""
        for concept in cls:
            if concept.value == label:
                return concept
        return None
```

- This enum serves as a reference for standard concept names
- The string values MUST match exactly with keys in `concept_mappings.json`
- Provides helper methods to:
  - Convert between string labels and enum members
  - Validate that JSON keys correspond to enum values
  - Get all available standard concepts
- New standard concepts should be added here first, then mappings added to JSON

#### MappingStore

Storage system for concept mappings:

- Loads mappings from `concept_mappings.json` at initialization
- Does not contain any hardcoded mappings in Python
- Provides methods to add, retrieve, and update mappings
- Saves changes back to JSON file when mappings are modified

#### ConceptMapper

Maps company-specific concepts to standard concepts using multiple approaches:

1. **Direct mapping**: Uses mappings from the `MappingStore` (loaded from JSON)
2. **Label similarity**: Compares concept labels to standard concept names
3. **Contextual rules**: Uses statement type, position, and calculation relationships
4. **Confidence scoring**: Evaluates mapping quality with confidence scores

### 3. Implementation Flow

The revised implementation follows this flow:

1. `StandardConcept` enum defines the canonical concept names
2. `MappingStore` loads mappings exclusively from JSON 
3. `ConceptMapper` uses these mappings and applies additional logic for complex cases
4. No default mappings are defined in Python code

### 4. Making Changes

When adding new mappings:

1. First check if the standard concept exists in `StandardConcept` enum
   - If not, add it to the enum
2. Add the mapping to `concept_mappings.json`
   - Use the exact string value from the enum as the key
   - Add company-specific concepts to the array of values
3. Only add complex mapping logic to `standardization.py` if needed

### Integration with Rendering

The standardization system integrates with the statement rendering system via:

1. A `standard=True` parameter in `render_statement()` methods
2. The `standardize_statement()` function to transform statement data

## Usage Example

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