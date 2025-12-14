# 8-K Form Research

Research and documentation on Form 8-K (Current Report) structure, parsing, and data extraction.

## Documents

### [8k-item-structure-evolution.md](./8k-item-structure-evolution.md)
**Comprehensive analysis of 8-K item structure changes across three filing eras:**
- Legacy SGML Era (1995-2004): Integer items (1-9)
- Mid-Period XML Era (2005-2012): Decimal items (X.XX) with varied HTML
- Modern XML Era (2013-present): Standardized decimal items with semantic HTML

**Key Findings:**
- SEC regulatory change in August 2004 introduced decimal numbering
- Detection patterns must handle both integer and decimal formats
- HTML structure evolved significantly across eras
- Current code primarily supports modern era filings

**Includes:**
- Detection pattern analysis
- Code implementation review
- Sample filings for testing
- Recommendations for improvements

### [8k-financial-exhibit-patterns.md](./8k-financial-exhibit-patterns.md)
**Analysis of financial statement exhibits in 8-K filings**
- Exhibit attachment patterns
- Press release identification
- Financial data extraction techniques

## Quick Reference

### Common 8-K Items (Modern Era)

**Most Frequent:**
- Item 9.01: Financial Statements and Exhibits (95% of filings)
- Item 8.01: Other Events (25% of filings)
- Item 2.02: Results of Operations (18% of filings)
- Item 5.02: Director/Officer Changes (15% of filings)

### Detection Patterns

**Decimal Items (Modern):**
```python
decimal_item_pattern = r"^Item\s{1,3}([0-9]{1,2}\.[0-9]{2})\.?"
# Matches: Item 2.02, Item 9.01
```

**Integer Items (Legacy):**
```python
int_item_pattern = r"\bItem\s+(\d+)\b"
# Matches: Item 5, Item 7
```

## Research Status

- ✅ **Item Evolution**: Comprehensive documentation complete
- ✅ **Era Analysis**: Three eras documented with samples
- ✅ **Code Review**: Current implementation analyzed
- ⚠️ **Test Coverage**: Gaps identified, improvements needed
- 🔄 **Implementation**: Recommendations pending

## Related Files

**Code:**
- `/edgar/company_reports.py` - EightK class
- `/edgar/files/htmltools.py` - Item detection patterns
- `/tests/test_eightK.py` - Current test coverage

**Issues:**
- Beads #tm2 - Investigation of 8-K item detection

## Next Steps

1. Implement legacy SGML support
2. Add normalization for item format consistency
3. Expand test coverage for all eras
4. Batch validation across 1000+ filings

---

**Last Updated:** 2025-11-07
**Maintained By:** SEC Filing Research Agent
