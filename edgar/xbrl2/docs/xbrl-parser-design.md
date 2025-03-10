# High-Level Design for XBRL Parser for SEC Filings

## 1. System Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  XBRL File      │────▶│  XBRL Parser    │────▶│  Data Model     │
│  Collection     │     │                 │     │                 │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │                 │
                                              │  Statement      │
                                              │  Generator      │
                                              │                 │
                                              └─────────────────┘
```

## 2. XBRL File Parser Component

### 2.1 Parse Instance Document
- **Parse XML Structure**: Use an XML parser to read the XBRL instance file
- **Extract Entity Information**: Company identifier, reporting period, etc.
- **Extract Contexts**:
  - Map context IDs to their associated entity, period, and scenario/segment information
  - Create a lookup table for period contexts (e.g., "2023-12-31", "2023-01-01 to 2023-12-31")
- **Extract Facts**: 
  - Each fact includes value, unit, decimals, context reference, and element reference
  - Store facts in a collection mapped by element ID and context
- **Extract Units**: Create mapping of unit IDs to their actual units (USD, shares, etc.)
- **Extract Footnotes**: If present, extract and map them to facts

### 2.2 Parse Taxonomy Schema (.xsd)
- **Parse Element Declarations**:
  - Extract element IDs, names, data types (monetary, string, etc.)
  - Identify period types (instant or duration)
  - Identify balance types (debit or credit)
  - Identify abstract elements (cannot contain values)
- **Map Namespaces**: Create namespace mappings for resolving element references

### 2.3 Parse Presentation Linkbase
- **Create Hierarchical Structure**:
  - Parse parent-child relationships
  - Maintain ordering information (order attribute)
  - Group by extended link roles (ELRs) which define statement sections
- **Capture Preferred Labels**: Identify special label roles for presentation
- **Build Presentation Tree**: Create a tree structure for each statement/disclosure

### 2.4 Parse Label Linkbase
- **Map Elements to Labels**:
  - Standard labels (default display)
  - Period start/end labels
  - Total labels
  - Negated labels
  - Terse labels
  - Documentation labels (definitions)
- **Handle Multiple Languages**: Support labels in different languages if present

### 2.5 Parse Calculation Linkbase
- **Extract Calculation Relationships**:
  - Parent-child calculation hierarchies
  - Weights (+1/-1) for addition/subtraction
  - Group by extended link roles
- **Build Calculation Trees**: Create calculation trees for validation and display

### 2.6 Parse Definition Linkbase
- **Parse Dimensional Relationships**:
  - Hypercubes (tables)
  - Dimensions (axes)
  - Domains and domain members
  - Default members
- **Build Dimensional Structure**: Create dimensional structure for complex tables

## 3. Data Model Construction

### 3.1 Core Data Structures
- **Element Catalog**:
  ```
  {
    "elementId": {
      "name": string,
      "dataType": string,
      "periodType": "instant"|"duration",
      "balance": "debit"|"credit"|null,
      "abstract": boolean,
      "labels": {
        "standard": string,
        "periodStart": string,
        "periodEnd": string,
        "negated": string,
        "documentation": string,
        ...
      }
    }
  }
  ```

- **Context Registry**:
  ```
  {
    "contextId": {
      "entity": {
        "identifier": string,
        "scheme": string
      },
      "period": {
        "type": "instant"|"duration",
        "instant": date|null,
        "startDate": date|null,
        "endDate": date|null
      },
      "dimensions": {
        "dimensionName": "memberName",
        ...
      }
    }
  }
  ```

- **Fact Database**:
  ```
  {
    "elementId_contextId": {
      "value": string,
      "decimals": number|"INF",
      "unitRef": string,
      "footnotes": [string]
    }
  }
  ```

### 3.2 Relationship Structures
- **Presentation Hierarchy**:
  ```
  {
    "roleUri": {
      "title": string,
      "root": {
        "elementId": string,
        "children": [
          {
            "elementId": string,
            "preferredLabel": string,
            "order": number,
            "children": [...]
          }
        ]
      }
    }
  }
  ```

- **Calculation Network**:
  ```
  {
    "roleUri": {
      "title": string,
      "calculations": [
        {
          "parent": "elementId",
          "children": [
            {
              "elementId": string,
              "weight": 1|-1,
              "order": number
            }
          ]
        }
      ]
    }
  }
  ```

- **Dimensional Structure**:
  ```
  {
    "roleUri": {
      "tables": [
        {
          "tableId": string,
          "axes": [
            {
              "axisId": string,
              "domain": string,
              "members": [string],
              "defaultMember": string
            }
          ],
          "lineItems": [string]
        }
      ]
    }
  }
  ```

## 4. Statement Construction Process

### 4.1 Identify Statement Structure
- **Locate Appropriate Presentation Network**:
  - Find presentation role URIs that correspond to desired statement
  - For example: "http://xbrl.abc.com/role/StatementOfFinancialPosition" for balance sheet

### 4.2 Select Time Period
- **Identify Relevant Contexts**:
  - For balance sheet: find contexts with instant periods for desired dates
  - For income statement: find contexts with duration periods for desired date ranges

### 4.3 Traverse Presentation Hierarchy
- **Walk the Presentation Tree**:
  - Start at the root element of the relevant presentation network
  - Process each element in the tree according to its presentation order
  - Handle abstract elements as headers/sections
  - Apply preferred labels (e.g., negated, period start/end, total)

### 4.4 Retrieve Facts for Elements
- **Map Elements to Facts**:
  - For each non-abstract element in the presentation hierarchy
  - Lookup facts using element ID and relevant context ID
  - Apply appropriate unit and decimal formatting

### 4.5 Apply Dimensional Filters
- **Handle Dimension-Qualified Facts**:
  - For tables with dimensions (axes and members)
  - Filter facts by dimensional qualifiers
  - Group related dimensional facts for display

### 4.6 Format Statement
- **Apply Styling and Indentation**:
  - Use presentation hierarchy to determine indentation levels
  - Format numeric values based on decimals attribute
  - Apply appropriate signage (based on balance type and negated labels)
  - Add totals and subtotals as indicated by calculation relationships

## 5. Specific Example: Reconstructing a Balance Sheet

### 5.1 Identify Balance Sheet Network
- Find presentation linkbase role that represents balance sheet
- Example: "http://xbrl.abc.com/role/BalanceSheet"

### 5.2 Select Contexts for Desired Dates
- Filter contexts to find those with:
  - Period type = "instant"
  - Period end date = desired reporting date (e.g., "2023-12-31")
  - No dimension qualifiers (for base statement)

### 5.3 Build Statement Structure
```
Statement of Financial Position
│
├── Assets [Abstract]
│   ├── Current Assets [Abstract]
│   │   ├── Cash and Cash Equivalents
│   │   ├── Accounts Receivable, Net
│   │   ├── Inventory, Net
│   │   └── Total Current Assets
│   │
│   ├── Non-current Assets [Abstract]
│   │   ├── Property, Plant and Equipment, Net
│   │   ├── Goodwill
│   │   └── Total Non-current Assets
│   │
│   └── Total Assets
│
└── Liabilities and Stockholders' Equity [Abstract]
    ├── Liabilities [Abstract]
    │   ├── Current Liabilities [Abstract]
    │   │   ├── Accounts Payable
    │   │   ├── Short-term Debt
    │   │   └── Total Current Liabilities
    │   │
    │   ├── Non-current Liabilities [Abstract]
    │   │   ├── Long-term Debt
    │   │   ├── Deferred Tax Liabilities
    │   │   └── Total Non-current Liabilities
    │   │
    │   └── Total Liabilities
    │
    ├── Stockholders' Equity [Abstract]
    │   ├── Common Stock
    │   ├── Additional Paid-in Capital
    │   ├── Retained Earnings
    │   └── Total Stockholders' Equity
    │
    └── Total Liabilities and Stockholders' Equity
```

### 5.4 Populate Statement with Facts
- For each non-abstract element in the hierarchy:
  - Look up element in Element Catalog to get its properties
  - Find the fact in the Fact Database using element ID and context ID
  - Format value using unit and decimals information
  - Apply appropriate sign based on element's balance type

### 5.5 Validate Totals Using Calculation Relationships
- Use calculation relationships to check that totals match their components
- Highlight any calculation inconsistencies

### 5.6 Generate Final Statement
- Output formatted balance sheet with:
  - Proper hierarchy/indentation
  - Correctly formatted values
  - Column(s) for each period
  - Appropriate signage
  - Computed subtotals and totals
