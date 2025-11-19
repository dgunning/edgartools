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

## Customization and Advanced Usage

For organizations managing custom XBRL taxonomies, company-specific concepts, or large-scale
standardization projects, see the comprehensive customization guide:

**[Customizing XBRL Standardization](../../../docs/advanced/customizing-standardization.md)**

This guide covers:
- CSV-based mapping workflows for Excel editing
- Validation techniques and quality assurance
- Handling ambiguous taxonomies and priority resolution
- CIK vs ticker-based mapping strategies
- Entity detection and automated mapping
- Production deployment patterns

### Utility Functions

The `utils` module provides tools for working with standardization mappings:

```python
from edgar.xbrl.standardization.utils import (
    export_mappings_to_csv,
    import_mappings_from_csv,
    validate_mappings
)

# Export mappings to CSV for editing in Excel
export_mappings_to_csv(store, 'mappings.csv', include_metadata=True)

# Import edited mappings back
mappings_dict = import_mappings_from_csv('mappings_edited.csv', validate=True)

# Validate mapping integrity
report = validate_mappings(store)
print(f"Valid: {report.is_valid}, Warnings: {len(report.warnings)}")
```

See the customization guide for complete documentation and examples.