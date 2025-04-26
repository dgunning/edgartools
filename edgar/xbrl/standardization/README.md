# XBRL2 Standardization

This package provides functionality for standardizing XBRL concepts across different company filings.

## Overview

The standardization module maps company-specific XBRL concepts to standardized concept names, 
enabling consistent presentation of financial statements regardless of the filing entity.

This is particularly useful for:
- Comparing financial data across different companies
- Building standardized reports and visualizations
- Creating consistent financial datasets for analysis

## Components

- `StandardConcept`: An enumeration of standard financial statement concepts
- `MappingStore`: Storage for mappings between company-specific and standard concepts
- `ConceptMapper`: Maps company-specific concepts to standard concepts using various techniques
- `standardize_statement`: Function to standardize a statement's labels

## Usage

```python
from edgar.xbrl.standardization import StandardConcept, initialize_default_mappings, ConceptMapper,
    standardize_statement

# Get the default mappings
store = initialize_default_mappings()

# Create a mapper
mapper = ConceptMapper(store)

# Standardize a statement
standardized_data = standardize_statement(statement_data, mapper)
```

## Concept Mappings

The standardized concept mappings are stored in the `concept_mappings.json` file included 
in this package. This file maps standard concept names to lists of company-specific concept IDs.

The file is automatically loaded when initializing the `MappingStore` and can be extended 
with new mappings as needed.