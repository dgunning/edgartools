# SEC Form 10-Q Research

This directory contains comprehensive research on SEC Form 10-Q (Quarterly Report) structure, content, and parsing techniques.

## Overview

Form 10-Q is the quarterly report filed by public companies for the first three fiscal quarters of each year. It provides unaudited financial statements and management discussion of company performance.

## Research Documents

### [10-Q Official Structure Guide](./10q-official-structure-guide.md)
**Comprehensive analysis of Form 10-Q structure**

Topics covered:
- Official 2-Part, 11-Item structure definition
- Part I (Financial Information) - 4 items
- Part II (Other Information) - 7 items
- Hierarchical relationships between Parts and Items
- How item numbers repeat across parts
- 10-Q vs 10-K structural differences
- Official SEC guidelines and regulations
- Real filing examples from 6 major companies
- Parsing implications and recommended strategies
- Edge cases and variations
- Historical evolution

**Status**: Complete | **Date**: 2025-10-10

## Key Findings

### 10-Q Structure Summary

```
Form 10-Q (2 Parts, 11 Items)
├── Part I - Financial Information (4 items)
│   ├── Item 1: Financial Statements
│   ├── Item 2: MD&A
│   ├── Item 3: Market Risk Disclosures
│   └── Item 4: Controls and Procedures
└── Part II - Other Information (7 items)
    ├── Item 1: Legal Proceedings
    ├── Item 1A: Risk Factors
    ├── Item 2: Unregistered Sales of Equity
    ├── Item 3: Defaults Upon Senior Securities
    ├── Item 4: Mine Safety Disclosures
    ├── Item 5: Other Information
    └── Item 6: Exhibits
```

### Critical Insights

1. **Item Number Ambiguity**: Item numbers repeat across parts. "Item 1" appears in both Part I (Financial Statements) and Part II (Legal Proceedings). Always reference with Part designation.

2. **Structural Consistency**: 100% of analyzed filings (AAPL, MSFT, JPM, GOOGL, TSLA, JNJ) follow identical Part/Item structure with zero deviations.

3. **10-Q vs 10-K**: Completely different structures:
   - 10-Q: 2 Parts, 11 Items
   - 10-K: 4 Parts, 25+ Items
   - Same content appears in different item numbers

4. **Optional Items**: Most Part II items are optional (included only if applicable). Item 6 (Exhibits) always required.

5. **Parsing Requirements**: Must be Part-aware to correctly identify sections. Cannot rely on Item number alone.

## Research Scripts

Analysis scripts used for this research:

- `analyze_10q_structure.py` - Initial structure frequency analysis
- `detailed_structure_analysis.py` - Detailed Part/Item extraction
- `manual_inspection.py` - Manual TOC and section header inspection
- `extract_multiple_structures.py` - Multi-company structure validation

All scripts are functional and can be re-run to validate findings or analyze additional companies.

## Validation

Research validated against:
- 6 companies across industries (Technology, Financial, Healthcare)
- Latest 10-Q filings from 2025
- Direct HTML inspection
- Official SEC guidelines and regulations
- Federal regulations (17 CFR § 240.15d-13)

## Applications

This research supports:
- EdgarTools 10-Q parsing implementation
- Automated section extraction
- Form-aware content mapping
- 10-Q vs 10-K content alignment
- Filing structure validation

## Related Research

- [10-K/10-Q HTML Section Structure Patterns](../10-k-10-q/html-section-structure-patterns.md)
- [XBRL Financial Data Extraction](../../extraction-techniques/) (if exists)

## Next Steps

Potential areas for future research:
- [ ] Detailed analysis of Part I, Item 1 financial statement structure
- [ ] MD&A section subsection patterns across companies
- [ ] Exhibit structure and types in Item 6
- [ ] 10-Q/A (amendment) handling specifics
- [ ] Smaller reporting company variations
- [ ] Historical structure evolution (pre-2000 filings)

---

*Last Updated: 2025-10-10*
*Maintained by: SEC Filing Research Agent*
