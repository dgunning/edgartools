# XBRL Table Deduplication

## Problem Statement

XBRL financial statements often contain redundant data due to the taxonomy structure. The same financial concepts appear in two places:

1. **Primary Context** - At the top level of the income statement
2. **Dimensional Context** - Under `Statement [Table]` → `Statement [Line Items]`

### Example of the Problem

Before deduplication:
```
Income Statement [Abstract]
  Total Revenue = $391B                     ← Primary context
  Net Income = $94B                         ← Primary context
  Statement [Table]
    Statement [Line Items]
      Total Revenue = $391B                 ← DUPLICATE (dimensional context)
      Net Income = $94B                     ← DUPLICATE (dimensional context)
```

This duplication occurs because:
- The XBRL US-GAAP taxonomy requires the table structure
- Companies must include both contexts for compliance
- When no actual dimensions exist (no segment breakdowns), the values are identical

## Solution

The `_deduplicate_table_items()` method in `enhanced_statement.py` removes these redundant table items when they provide no additional information.

### How It Works

1. **Collect Primary Concepts**: First pass identifies all concepts and values outside of table structures
2. **Identify Duplicates**: Second pass finds items within tables that have identical values to primary concepts
3. **Remove Redundant Items**: Removes table items that are pure duplicates
4. **Preserve Unique Data**: Keeps table items that have:
   - Different values (dimensional breakdowns)
   - Unique child concepts not in primary context
   - Additional analytical value

### Algorithm

```python
def _deduplicate_table_items(items):
    # Phase 1: Collect all non-table concepts
    primary_concepts = {}
    for item in items:
        if not in_table_structure(item):
            primary_concepts[item.concept] = item.values
    
    # Phase 2: Remove duplicates from tables
    for item in items:
        if in_table_structure(item):
            if item.concept in primary_concepts:
                if item.values == primary_concepts[item.concept]:
                    remove_item(item)  # It's a duplicate
```

## Results

### Before Deduplication
- 18+ items including duplicates
- Confusing repeated values
- Cluttered presentation

### After Deduplication
- 11 clean, unique items
- No redundant information
- Clear, concise presentation

## Edge Cases Handled

1. **Companies with Segments**: If dimensional data exists (different values by segment), it's preserved
2. **Partial Duplicates**: Items with some unique children are kept
3. **Empty Tables**: Completely redundant table structures are removed entirely
4. **Abstract Items**: Structural/organizational items are preserved for hierarchy

## Testing

Tested with multiple companies:
- **AAPL**: Statement [Table] completely removed (pure duplicates)
- **MSFT**: Statement [Table] completely removed (pure duplicates)  
- **GOOGL**: Statement [Table] completely removed (pure duplicates)

## Impact

This deduplication:
- **Improves readability** by removing redundant information
- **Reduces confusion** for users seeing the same values twice
- **Maintains compliance** as we're only affecting display, not data
- **Preserves valuable data** when dimensional breakdowns exist

## Technical Note

This addresses a fundamental quirk of XBRL where the presentation linkbase defines multiple valid presentation points for the same concept, leading to duplication when rendered naively. The SEC's own viewer handles this differently, but our approach provides a cleaner, more intuitive presentation for programmatic access.