# SEC Company Facts JSON Specification

## Overview
The SEC Company Facts JSON format provides standardized financial data for public companies. This document describes the structure, fields, and important considerations when working with this data.

## JSON Structure

```json
{
  "cik": 1640147,
  "entityName": "SNOWFLAKE INC.",
  "facts": {
    "taxonomy": {
      "ConceptName": {
        "label": "Human-readable label",
        "description": "Detailed description",
        "units": {
          "unit_type": [
            {
              // Individual fact records
            }
          ]
        }
      }
    }
  }
}
```

## Root Level Fields

- **`cik`**: Central Index Key - Unique identifier for the company
- **`entityName`**: Official company name as registered with SEC
- **`facts`**: Container for all financial facts, organized by taxonomy

## Taxonomy Level

Facts are organized by taxonomy namespace:
- **`us-gaap`**: US Generally Accepted Accounting Principles
- **`ifrs-full`**: International Financial Reporting Standards
- **`dei`**: Document and Entity Information
- **`invest`**: Investment company specific
- **`{company-specific}`**: Custom company extensions

## Concept Level

Each concept within a taxonomy contains:
- **`label`**: Human-readable name (can be null)
- **`description`**: Detailed explanation (can be null)
- **`units`**: Container for facts grouped by unit of measure

## Fact Record Fields

### Core Fields

- **`val`**: The actual value (number, string, or boolean)
- **`accn`**: Accession number - Unique filing identifier
- **`form`**: Form type (10-K, 10-Q, 8-K, etc.)
- **`filed`**: Date the filing was submitted to SEC (YYYY-MM-DD)

### Period Fields

For duration facts (e.g., revenue for a quarter):
- **`start`**: Period start date (YYYY-MM-DD)
- **`end`**: Period end date (YYYY-MM-DD)

For instant facts (e.g., assets at a point in time):
- **`end`**: Measurement date (YYYY-MM-DD)
- No `start` field

### Fiscal Period Identifiers

- **`fy`**: Fiscal year when the report was FILED (not the data period!)
  - Example: Q1 2024 data filed in May 2025 has `fy: 2025`
  - This is often misleading and should not be used for period labels
  
- **`fp`**: Fiscal period type
  - `FY`: Full fiscal year
  - `Q1`, `Q2`, `Q3`, `Q4`: Quarterly periods
  - `Q1Q2`, `Q2Q3`, etc.: Cumulative periods
  - `YTD`: Year-to-date

- **`frame`**: Calendar period reference (optional)
  - Format: `CY{YEAR}` for annual or `CY{YEAR}Q{QUARTER}` for quarterly
  - Example: `CY2024Q1` means calendar Q1 2024
  - More reliable than `fy` for determining actual data period

## Units

Common unit types:
- **`USD`**: US Dollars
- **`shares`**: Number of shares
- **`USD/shares`**: Dollars per share
- **`pure`**: Dimensionless numbers (ratios, percentages)
- **`Year`**, **`Month`**: Time periods

## Duplicate Facts and Filing Patterns

### Why Duplicates Exist

The same fact often appears multiple times because:

1. **Restatements**: Companies may revise previously reported numbers
2. **Multiple References**: The same historical fact is included in subsequent filings
3. **Amended Filings**: 10-K/A or 10-Q/A forms update previous filings
4. **Fiscal Year Transitions**: Facts filed in different fiscal years

### Example: Gross Profit Duplication

```json
// Same period, same value, different filings
{
  "start": "2024-02-01",
  "end": "2024-04-30",
  "val": 556192000,
  "accn": "0001640147-24-000135",
  "fy": 2025,  // Filed in FY2025
  "fp": "Q1",
  "form": "10-Q",
  "filed": "2024-05-31"
},
{
  "start": "2024-02-01",
  "end": "2024-04-30",
  "val": 556192000,
  "accn": "0001640147-25-000110",
  "fy": 2026,  // Same data, filed again in FY2026
  "fp": "Q1",
  "form": "10-Q",
  "filed": "2025-05-30",
  "frame": "CY2024Q1"
}
```

## Financial Statement Assembly Considerations

### 1. Fact Selection Strategy

When multiple facts exist for the same period, prioritize by:

1. **Most Recent Filing**: Latest `filed` date typically has the most accurate data
2. **Form Type Hierarchy**:
   - Audited annual reports (10-K) over quarterly (10-Q)
   - Original filings over amendments unless amendment is newer
3. **Frame Consistency**: Facts with matching `frame` values for period alignment

### 2. Period Labeling

**DO NOT** use `fy` for period labels - it represents filing year, not data period!

Instead:
- Use `end` date to determine actual period
- Map to calendar quarters based on month
- Use `frame` field when available for consistency

### 3. Handling Restatements

- Later filings may contain restated values
- Always use the most recent filing's value
- Track `accn` to identify which filing provided each fact

### 4. Quality Considerations

- Annual (FY) data is typically audited
- Quarterly data is usually unaudited
- Facts from 10-K forms have higher reliability
- Multiple consistent values across filings increase confidence

## Best Practices

1. **Always Check for Nulls**: `label` and `description` can be null
2. **Use Filing Date for Precedence**: Most recent filing usually has the best data
3. **Validate Period Consistency**: Ensure start/end dates align with fiscal periods
4. **Handle Scale Carefully**: Values may be pre-scaled (in thousands/millions)
5. **Track Provenance**: Keep `accn` and `filed` for audit trail

## Common Pitfalls

1. **Misusing `fy`**: It's the filing year, not the data year
2. **Ignoring Duplicates**: Not handling multiple facts for same period
3. **Missing Restatements**: Using old values when newer ones exist
4. **Period Misalignment**: Mixing fiscal and calendar periods
5. **Unit Confusion**: Not checking if values are already scaled

## Implementation Notes

When building financial statements:

1. Group facts by actual period (use `end` date)
2. Sort by filing date descending
3. Take the first (most recent) fact for each period
4. Use `frame` for consistent period alignment when available
5. Generate display labels from actual dates, not `fy`