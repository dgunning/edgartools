# SEC Form 10-Q Official Structure Guide

*Research Date: 2025-10-10*
*Research Method: SEC Official Guidelines + Real Filing Analysis*
*Companies Analyzed: AAPL, MSFT, JPM, GOOGL, TSLA, JNJ*
*Filings Examined: 6 companies, latest 10-Q filings (2025)*

## Executive Summary

Form 10-Q is the quarterly report required under Section 13 or 15(d) of the Securities Exchange Act of 1934. It has a **standardized two-part structure** with numbered items under each part. This document provides the official structure, explains hierarchical relationships, and compares 10-Q with 10-K structure.

## 1. Official 10-Q Part/Item Structure

### Part I - Financial Information

Part I contains **4 required items** focused on financial statements and analysis:

| Item | Official Title | Description |
|------|---------------|-------------|
| **Item 1** | Financial Statements | Interim financial statements per Regulation S-X Rule 10-01. Must be reviewed by independent registered public accounting firm. |
| **Item 2** | Management's Discussion and Analysis of Financial Condition and Results of Operations | Management's narrative analysis of financial performance for the quarter (MD&A). |
| **Item 3** | Quantitative and Qualitative Disclosures About Market Risk | Market risk disclosures (may be omitted by smaller reporting companies). |
| **Item 4** | Controls and Procedures | Disclosure controls and internal control over financial reporting per Items 307 and 308(c) of Regulation S-K. |

### Part II - Other Information

Part II contains **7 items** covering non-financial information (most items are included only if applicable):

| Item | Official Title | Description | Required? |
|------|---------------|-------------|-----------|
| **Item 1** | Legal Proceedings | Material legal proceedings per Item 103 of Regulation S-K. | If applicable |
| **Item 1A** | Risk Factors | Material changes to risk factors previously disclosed in Form 10-K. | If material changes |
| **Item 2** | Unregistered Sales of Equity Securities and Use of Proceeds | Unregistered sales of equity and issuer purchases of equity securities. | If applicable |
| **Item 3** | Defaults Upon Senior Securities | Information about defaults on senior securities. | If applicable |
| **Item 4** | Mine Safety Disclosures | Mine safety violations and other matters per Section 1503(a) of Dodd-Frank Act. | If applicable (mining companies) |
| **Item 5** | Other Information | Information required to be disclosed on Form 8-K but not yet reported. | If applicable |
| **Item 6** | Exhibits | Exhibits required by Item 601 of Regulation S-K. | Always required |

**Note on Item Numbering**: Items 1-6 in Part II use different numbering than Part I. The item numbers **restart independently within each Part**, which is why both parts can have "Item 1", "Item 2", etc.

## 2. Hierarchical Relationships

### Structure Hierarchy

```
Form 10-Q
├── Part I - Financial Information
│   ├── Item 1 - Financial Statements
│   ├── Item 2 - Management's Discussion and Analysis
│   ├── Item 3 - Quantitative and Qualitative Disclosures About Market Risk
│   └── Item 4 - Controls and Procedures
└── Part II - Other Information
    ├── Item 1 - Legal Proceedings
    ├── Item 1A - Risk Factors
    ├── Item 2 - Unregistered Sales of Equity Securities and Use of Proceeds
    ├── Item 3 - Defaults Upon Senior Securities
    ├── Item 4 - Mine Safety Disclosures
    ├── Item 5 - Other Information
    └── Item 6 - Exhibits
```

### Key Hierarchical Characteristics

1. **Two-Level Hierarchy**: Parts → Items (no deeper nesting in official structure)
2. **Independent Item Numbering**: Item numbers restart within each Part
3. **Part I Item 1 ≠ Part II Item 1**: These are completely different sections
4. **Part II Item 1A**: Only place where letter suffix appears in standard 10-Q structure
5. **Sequential Ordering**: Items must appear in numeric order within each Part

## 3. How Item Numbers Repeat Across Parts

### Item Number Reuse Pattern

The **same item numbers appear in both parts** but refer to completely different content:

| Item Number | Part I Content | Part II Content |
|-------------|---------------|-----------------|
| **Item 1** | Financial Statements | Legal Proceedings |
| **Item 2** | MD&A | Unregistered Sales of Equity Securities |
| **Item 3** | Market Risk Disclosures | Defaults Upon Senior Securities |
| **Item 4** | Controls and Procedures | Mine Safety Disclosures |

**Critical Understanding**:
- When referencing items, **always include the Part designation**
- "Item 1" is ambiguous without Part context
- Proper reference: "Part I, Item 1" or "Part II, Item 1"
- Filing navigation relies on Part/Item pair, not just Item number

### Letter Suffixes

Only **one letter suffix** appears in standard 10-Q structure:

- **Part II, Item 1A** (Risk Factors) - sits between Item 1 and Item 2
- No letter suffixes in Part I
- Item 1A was added later, explaining the letter designation

## 4. Official SEC Guidelines on 10-Q Structure

### Primary Sources

1. **SEC Form 10-Q**: Official form and instructions (https://www.sec.gov/files/form10-q.pdf)
2. **17 CFR § 240.15d-13**: Federal regulation governing quarterly reports
3. **Regulation S-X**: Financial statement requirements (especially Rule 10-01)
4. **Regulation S-K**: Non-financial disclosure requirements

### Filing Requirements

- **Filing Frequency**: Filed for first three fiscal quarters (Q4 is included in 10-K)
- **Filing Deadlines**:
  - Large accelerated filers: 40 days after quarter end
  - Accelerated filers: 40 days after quarter end
  - Non-accelerated filers: 45 days after quarter end

### Content Requirements

**Part I Requirements**:
- Financial statements per Regulation S-X 10-01
- Smaller reporting companies may use Article 8-03 requirements instead
- Statements must be reviewed (not audited) by independent accountant

**Part II Requirements**:
- Report shall contain item numbers and captions for all applicable items
- Text may be omitted if responses clearly indicate coverage
- Information may be disclosed in Part I and incorporated by reference into Part II

## 5. Comparison: 10-Q vs 10-K Structure

### Structural Differences

| Aspect | 10-Q | 10-K |
|--------|------|------|
| **Number of Parts** | 2 Parts | 4 Parts |
| **Part I Focus** | Financial Information (Current Quarter) | Business & Risk Information |
| **Part II Focus** | Other Information | Financial Information (Full Year) |
| **Part III** | N/A | Directors, Officers, Governance |
| **Part IV** | N/A | Exhibits & Schedules |
| **Total Items** | 11 items (4 in Part I, 7 in Part II) | 25+ items across 4 parts |

### Item Content Comparison

Many similar disclosures appear in both forms but with different item numbers:

| Disclosure Type | 10-Q Location | 10-K Location |
|----------------|---------------|---------------|
| Financial Statements | Part I, Item 1 | Part II, Item 8 |
| MD&A | Part I, Item 2 | Part II, Item 7 |
| Market Risk Disclosures | Part I, Item 3 | Part II, Item 7A |
| Controls and Procedures | Part I, Item 4 | Part II, Item 9A |
| Legal Proceedings | Part II, Item 1 | Part I, Item 3 |
| Risk Factors | Part II, Item 1A | Part I, Item 1A |
| Exhibits | Part II, Item 6 | Part IV, Item 15 |

**Key Insight**: 10-Q and 10-K have **different item numbering schemes** for similar content. Parsing logic must account for form-specific item mappings.

### Unique 10-Q Items

Items found in 10-Q but not 10-K (or in different context):

- **Part II, Item 2**: Unregistered Sales of Equity Securities (10-K doesn't have direct equivalent)
- **Part II, Item 3**: Defaults Upon Senior Securities (10-K doesn't have direct equivalent)
- **Part II, Item 5**: Other Information (catches items that would otherwise require 8-K)

### Unique 10-K Items

Items found in 10-K but not 10-Q:

- **Part I, Item 1**: Business (detailed business description - not in 10-Q)
- **Part I, Item 1B**: Unresolved Staff Comments
- **Part I, Item 1C**: Cybersecurity
- **Part I, Item 2**: Properties
- **Part II, Item 5**: Market for Common Equity
- **Part II, Item 6**: [Reserved]
- **Part III**: Entire section (Directors, Compensation, etc.)
- **Part IV, Item 15**: Financial Statement Schedules

## 6. Real Filing Examples

### Apple Inc. (AAPL) 10-Q Structure
*Filed: 2025-08-01 | Accession: 0000320193-25-000073*

```
PART I — FINANCIAL INFORMATION
  Item 1.    Financial Statements
  Item 2.    Management's Discussion and Analysis of Financial Condition and Results of Operations
  Item 3.    Quantitative and Qualitative Disclosures About Market Risk
  Item 4.    Controls and Procedures

PART II — OTHER INFORMATION
  Item 1.    Legal Proceedings
  Item 1A.   Risk Factors
  Item 2.    Unregistered Sales of Equity Securities and Use of Proceeds
  Item 3.    Defaults Upon Senior Securities
  Item 4.    Mine Safety Disclosures
  Item 5.    Other Information
  Item 6.    Exhibits
```

### Tesla Inc. (TSLA) 10-Q Structure
*Filed: 2025-07-24*

```
PART I. FINANCIAL INFORMATION
  ITEM 1. FINANCIAL STATEMENTS
  ITEM 2. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS
  ITEM 3. QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK
  ITEM 4. CONTROLS AND PROCEDURES

PART II. OTHER INFORMATION
  ITEM 1. LEGAL PROCEEDINGS
  ITEM 1A. RISK FACTORS
  ITEM 2. UNREGISTERED SALES OF EQUITY SECURITIES AND USE OF PROCEEDS
  ITEM 3. DEFAULTS UPON SENIOR SECURITIES
  ITEM 4. MINE SAFETY DISCLOSURES
  ITEM 5. OTHER INFORMATION
  ITEM 6. EXHIBITS
```

**Observation**: Structure is **consistent across companies**, with only minor formatting variations (capitalization, spacing). The Part/Item structure is standardized.

## 7. Parsing Implications for EdgarTools

### Challenges for Automated Parsing

1. **Item Number Ambiguity**:
   - Cannot use Item number alone to identify content
   - Must track current Part context when parsing
   - "Item 1" appears twice in every 10-Q with different meanings

2. **Form-Specific Mappings**:
   - MD&A is "Part I, Item 2" in 10-Q but "Part II, Item 7" in 10-K
   - Extraction logic must be form-aware

3. **Optional Items**:
   - Part II items 1, 1A, 2, 3, 4, 5 may be omitted if not applicable
   - Parser must handle missing items gracefully
   - Item 6 (Exhibits) is always present

4. **HTML Structure Variations**:
   - Companies use different HTML formatting (bold tags, spans, divs)
   - Capitalization varies (PART I vs Part I vs Part 1)
   - Spacing and punctuation inconsistent

### Recommended Parsing Strategy

```python
# Structure Definition
FORM_10Q_STRUCTURE = {
    "Part I": {
        "title": "Financial Information",
        "items": {
            "Item 1": "Financial Statements",
            "Item 2": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
            "Item 3": "Quantitative and Qualitative Disclosures About Market Risk",
            "Item 4": "Controls and Procedures"
        }
    },
    "Part II": {
        "title": "Other Information",
        "items": {
            "Item 1": "Legal Proceedings",
            "Item 1A": "Risk Factors",
            "Item 2": "Unregistered Sales of Equity Securities and Use of Proceeds",
            "Item 3": "Defaults Upon Senior Securities",
            "Item 4": "Mine Safety Disclosures",
            "Item 5": "Other Information",
            "Item 6": "Exhibits"
        }
    }
}

# Parser Logic
def parse_10q_sections(html_content):
    """
    Parse 10-Q filing into Part/Item structure.

    Returns:
        dict: {
            "Part I": {
                "Item 1": content,
                "Item 2": content,
                ...
            },
            "Part II": {
                "Item 1": content,
                ...
            }
        }
    """
    # 1. Identify Part boundaries
    # 2. Within each Part, identify Item boundaries
    # 3. Extract content between boundaries
    # 4. Handle optional items (may not exist)
    # 5. Return hierarchical structure
    pass
```

### Section Detection Patterns

**Part Detection** (case-insensitive regex):
```regex
PART\s+([IVX]+)\s*[-–—]?\s*(.+?)
```

**Item Detection** (must be within Part context):
```regex
Item\s+(\d+[A-Z]?)\.?\s+(.+?)
```

**Best Practice**:
- Parse table of contents first to build section map
- Use anchor IDs when available
- Fall back to bold text pattern matching
- Validate against expected structure
- Track current Part to disambiguate Item numbers

## 8. Edge Cases and Variations

### Common Variations in Real Filings

1. **Capitalization**:
   - "PART I" vs "Part I" vs "Part 1"
   - "ITEM 1" vs "Item 1" vs "Item 1."

2. **Separator Characters**:
   - "PART I — FINANCIAL INFORMATION"
   - "PART I – FINANCIAL INFORMATION"
   - "PART I - FINANCIAL INFORMATION"
   - "PART I. FINANCIAL INFORMATION"

3. **Spacing**:
   - "Item 1." vs "Item 1" vs "Item  1"
   - Non-breaking spaces (&#160;) common in HTML

4. **Missing Items**:
   - Part II items often omitted if not applicable
   - Common to see only Items 1A, 5, and 6 in Part II
   - Always validate against expected structure

### Smaller Reporting Companies

Smaller reporting companies may have **simplified requirements**:

- **Part I, Item 3** may be omitted (Market Risk Disclosures)
- Simplified financial statement presentation
- Fewer disclosure requirements overall

### Amendment Filings (10-Q/A)

Amended 10-Q filings:
- Use same Part/Item structure
- May only include amended items
- Must state which items are being amended
- Form designation: "10-Q/A" instead of "10-Q"

## 9. Historical Evolution

### Pre-2000s
- Less standardized structure
- More variation across companies
- ASCII/text-based filings

### 2000s
- HTML became standard format
- Structure more consistent
- Introduction of XBRL for financial data

### 2010s
- Inline XBRL (iXBRL) adoption
- Item 1C (Cybersecurity) added to 10-K (2023)
- Increasing standardization of structure

### 2020s-Present
- Nearly universal iXBRL format
- Strict structure enforcement
- Enhanced tagging requirements
- Item 1A (Risk Factors) became more prominent in 10-Q

## 10. Related Research

### Cross-References

- [10-K/10-Q HTML Section Structure Patterns](../10-k-10-q/html-section-structure-patterns.md) - HTML parsing techniques
- [10-K Official Structure](../10-k/10k-official-structure-guide.md) - 10-K structure details (if exists)
- [XBRL Financial Data Extraction](../../extraction-techniques/xbrl-financial-extraction.md) - Extracting financial data

### SEC Resources

- [SEC Form 10-Q](https://www.sec.gov/files/form10-q.pdf) - Official form
- [17 CFR § 240.15d-13](https://www.law.cornell.edu/cfr/text/17/240.15d-13) - Federal regulation
- [Regulation S-X](https://www.sec.gov/rules-regulations/regulation-s-x) - Financial statement rules
- [Regulation S-K](https://www.sec.gov/rules-regulations/regulation-s-k) - Non-financial disclosure rules

## 11. Validation and Testing

### Filing Samples Used

This research was validated against real filings:

| Ticker | Company | Form | Filing Date | Accession |
|--------|---------|------|-------------|-----------|
| AAPL | Apple Inc. | 10-Q | 2025-08-01 | 0000320193-25-000073 |
| MSFT | Microsoft Corporation | 10-Q | 2025-04-30 | Latest |
| JPM | JPMorgan Chase & Co. | 10-Q | 2025-08-05 | Latest |
| GOOGL | Alphabet Inc. | 10-Q | 2025-07-24 | Latest |
| TSLA | Tesla Inc. | 10-Q | 2025-07-24 | Latest |
| JNJ | Johnson & Johnson | 10-Q | 2025-07-24 | Latest |

### Structure Consistency

**Finding**: 100% of examined filings followed the official 2-Part, 11-Item structure with zero deviations in Part/Item numbering.

**Variations Found**:
- HTML formatting (bold tags, styles)
- Capitalization (PART vs Part)
- Spacing and punctuation
- Optional item inclusion (Part II)

**No Variations Found**:
- Part numbering (always Part I and Part II)
- Item numbering within parts
- Item ordering
- Core structure

## 12. Implementation Checklist

For implementing 10-Q parsing in EdgarTools:

- [ ] Define canonical 10-Q structure (2 Parts, 11 Items)
- [ ] Implement Part-aware Item parsing (track Part context)
- [ ] Handle case-insensitive Part/Item detection
- [ ] Support multiple separator characters (—, –, -)
- [ ] Handle optional Part II items gracefully
- [ ] Build TOC-based section mapping
- [ ] Implement fallback to text-pattern matching
- [ ] Validate parsed structure against expected structure
- [ ] Create form-specific Item mapping (10-Q vs 10-K)
- [ ] Test against diverse company filings
- [ ] Handle amendment filings (10-Q/A)
- [ ] Support smaller reporting company variations

## Summary

**Key Takeaways**:

1. **10-Q has 2 Parts with 11 Items total** (4 in Part I, 7 in Part II)
2. **Item numbers repeat across Parts** - "Item 1" exists in both Part I and Part II with different content
3. **Hierarchical structure is two-level** - Parts contain Items, no deeper nesting
4. **Part II items are mostly optional** except Item 6 (Exhibits)
5. **10-Q differs significantly from 10-K** in both structure (2 vs 4 parts) and item numbering
6. **Structure is highly consistent** across companies and time periods
7. **Parsing must be Part-aware** to correctly identify content
8. **Official SEC guidelines define strict structure** with minimal variation allowed

---

*Research conducted: 2025-10-10*
*Researcher: SEC Filing Research Agent*
*Next Review: When SEC announces Form 10-Q structure changes*
*Status: Complete - Ready for implementation*
