# XBRL2 Rewrite Project: Developer Guide

## Overview

The XBRL2 module is a complete rewrite of the original XBRL implementation aimed at improving:
- Performance when handling large XBRL datasets
- Developer experience through a more intuitive API
- Filtering capabilities for financial analysis
- Statement type categorization
- Period-based view generation

This document provides guidance for developers continuing work on this module.

## Core Components

### Facts API

The Facts API is the central interface for querying XBRL facts:

- **FactQuery**: Fluent interface for building fact queries with chainable methods
- **FactsView**: Access point for all facts in an XBRL document 

### Key Filtering Capabilities

- **Statement Type Filtering**: Filter facts by financial statement (BalanceSheet, IncomeStatement, etc.)
- **Period View Filtering**: Filter facts by predefined time periods (Annual, Quarterly)
- **Text Search**: Search across multiple text fields
- **Value Filtering**: Filter by numeric values with proper null handling
- **Label Filtering**: Find facts by various label representations
- **Dimension Filtering**: Query by XBRL dimensions

## Recent Enhancements

1. **Fixed Statement Type Association**
   - Added `element_id.replace(':', '_')` to handle namespace format differences
   - Ensures facts properly associate with their statement types

2. **Improved Null Value Handling**
   - Enhanced `by_value()` to check if `f['numeric_value'] is not None` before comparison
   - Prevents errors when filtering on numeric fields that might be null

3. **Duplicate Facts Prevention**
   - Added tracking of processed facts using a fact signature based on element_id and context_ref
   - Prevents duplicate facts in query results

4. **Enhanced Label Field Access**
   - Improved `by_label()` to check both 'label' and 'element_label' fields with null safety
   - Makes label-based filtering more robust

5. **Period Filtering**
   - Implemented dedicated methods for period key filtering: `by_period_key()` and `by_period_keys()`
   - Added facts count metadata to period views

6. **Text Search**
   - Created a flexible search across multiple text fields with the `by_text()` method
   - Enables searching across labels, documentation, and element IDs

7. **Sorting Logic**
   - Fixed sorting to check that results is not empty before accessing results[0]
   - Prevents errors when no matching facts are found

8. **Calculation Weight Application**
   - Properly applies calculation weights from XBRL calculation linkbases
   - Elements with negative weights (e.g., -1.0) are automatically negated
   - Ensures correct presentation in financial statements (especially Cash Flow)

## Implementation Notes

### Element ID Handling

When working with element IDs, always handle both colon format and underscore format:

```python
# Convert from colon to underscore format when needed
element_id_underscore = element_id.replace(':', '_')
```

### Context References

Facts are associated with contexts through their `context_ref` property. Always ensure this relationship is maintained when filtering or transforming facts.

### Namespaces

XBRL elements exist within namespaces (commonly 'us-gaap', 'ifrs', etc.). When working with element IDs, be aware of namespace prefixes and handle them consistently.

### Calculation Weight Handling

The XBRL2 module now properly handles calculation weights from calculation linkbases:

```python
# In _apply_calculation_weights method (called after fact extraction)
def _apply_calculation_weights(self) -> None:
    """
    Apply calculation weights to facts based on calculation linkbase information.
    
    This method handles the application of negative weights from calculation arcs.
    Per XBRL specification, a negative weight should flip the sign of a fact value
    when used in calculations. This is particularly common with elements like
    "IncreaseDecreaseInInventories" which should be negated when contributing
    to cash flow calculations.
    """
    # Find elements with negative weights across all calculation trees
    for role_uri, calc_tree in self.calculation_trees.items():
        for element_id, node in calc_tree.all_nodes.items():
            if node.weight < 0:
                # Find and adjust all facts for this element
                for key, fact in self.facts.items():
                    if fact.element_id == element_id:
                        # Negate numeric value if present
                        if fact.numeric_value is not None:
                            fact.numeric_value = -fact.numeric_value
                        
                        # Also update string value for consistent display
                        if fact.value and not fact.value.startswith('-'):
                            fact.value = f"-{fact.value}"
```

This implementation ensures:
1. Cash flow statements present inflows and outflows with the correct sign
2. Elements like "IncreaseDecreaseInInventories" are displayed with the proper signage
3. Calculations like subtotals and totals in statements will sum correctly
4. Fact values properly reflect their contextual meaning in financial statements

## Testing Considerations

1. **Test with diverse XBRL datasets**:
   - US GAAP filings from different years
   - IFRS filings
   - Filings with different statement structures

2. **Test edge cases**:
   - Empty result sets
   - Missing statement types
   - Invalid period keys
   - Null values in various fields
   - Extremely large fact sets (performance testing)

3. **Test common workflows**:
   - Annual statement comparison
   - Quarterly trend analysis
   - Statement reconstruction from facts

## Future Improvements

1. **Performance Optimization**
   - Consider indexing strategies for large fact sets
   - Implement caching for frequent queries
   - Optimize memory usage for large XBRL documents

2. **Error Handling**
   - Add more robust error messages for common issues
   - Implement validation for user inputs
   - Add graceful fallbacks for missing data

3. **Visualization Integration**
   - Consider direct integration with plotting libraries
   - Add built-in visualization templates for common financial analyses

4. **Extended Documentation**
   - Add more example notebooks
   - Create reference documentation for all methods
   - Document common patterns and best practices

## Reference

For examples and additional documentation:
- See `notebooks/XBRL2-FactQueries.ipynb` for query examples
- See `notebooks/XBRL2-PeriodViews.ipynb` for period view examples
- See `notebooks/XBRL2-StandarizedStaments.ipynb` for statement examples