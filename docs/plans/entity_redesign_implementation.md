# Entity Hierarchy Redesign Implementation

## Overview

This document summarizes the implementation of the entity hierarchy redesign for the EdgarTools library. The redesign creates a cleaner, more intuitive interface for working with SEC filings, with specialized classes for different entity types.

## Key Changes

1. **Created a proper class hierarchy**:
   - `SecFiler` (abstract base class)
     - `Entity` (concrete class for any SEC filer)
       - `Company` (specialized for public companies)
       - `Fund` (specialized for investment funds)
         - `FundClass` (for specific fund share classes)

2. **Defined clear interfaces**:
   - `SecFiler` provides the base interface for all SEC filers.
   - Each subclass adds specialized functionality.
   - Methods have proper type annotations and documentation.

3. **Maintained backward compatibility**:
   - Factory functions (`get_entity`, `get_company`, `get_fund`) preserved.
   - Original method signatures were maintained.
   - Interface is consistent with the previous implementation.

4. **Improved encapsulation and delegation**:
   - Classes use composition to delegate to underlying data.
   - Data access is lazy-loaded and cached.
   - Specialized classes expose relevant specialized methods.

5. **Added clear documentation**:
   - All classes and methods are documented with docstrings.
   - Type annotations provide clear interfaces.
   - Tests verify the expected behavior.

## Design Decisions

### Duck Typing vs. Inheritance for EntityData

Initially, we planned to have a parallel hierarchy for the data classes:
- `EntityData` → `CompanyData` → `FundData`

However, this proved challenging due to the way the original implementation creates and uses these objects. Instead, we took a duck typing approach where:
- Company.data returns the same object type as Entity.data
- But through type annotations, IDE and type checkers will show specialized methods

This approach avoids compatibility issues while still providing type checking benefits.

### Lazy Loading Pattern

The lazy loading pattern for filings is preserved:
1. Initially, only the most recent filings are loaded.
2. When `trigger_full_load=True` (default), additional filings are loaded on-demand.
3. This happens only once per entity instance.

### Factory Functions

The factory functions:
- Maintain backward compatibility
- Provide a convenient way to create entities
- Handle special cases (like fund classes)

## Implementation Files

- `edgar/entities_new.py` - The new entity hierarchy implementation
- `edgar/entities_new_init.py` - The export module for the new implementation
- `tests/test_entity_redesign.py` - Tests for the new implementation

## Next Steps

1. **Integration**:
   - Rename `entities_new.py` to `entities.py`
   - Rename `entities_new_init.py` to `__init__.py` in the entities package
   - Update imports in other modules

2. **Documentation**:
   - Update user-facing documentation
   - Add examples to the README
   - Update docstrings in other modules

3. **Testing**:
   - Add more comprehensive tests for edge cases
   - Test with real-world data
   - Verify performance

4. **Fund Implementation**:
   - Complete the implementation of the Fund and FundClass classes
   - Integrate with existing fund-related functionality