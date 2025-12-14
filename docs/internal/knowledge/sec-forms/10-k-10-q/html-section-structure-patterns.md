# SEC 10-K and 10-Q HTML Section Structure Patterns

*Research Date: 2025-01-28*
*Forms Analyzed: 10-K, 10-Q*
*Companies Sampled: AAPL, MSFT, IBM, JPM, GE*

## Executive Summary

SEC filings (10-K, 10-Q) follow evolving HTML structure patterns for organizing content into Items and Parts. Modern filings predominantly use inline XBRL (iXBRL) format, which adds complexity to the HTML structure but maintains consistent section delimitation patterns.

## Key Findings

### 1. Document Format Evolution

#### Current Standard: iXBRL (Inline XBRL)
- **Prevalence**: 100% of major company filings analyzed use iXBRL format as of 2024-2025
- **Structure**: HTML document with embedded XBRL tags (`<ix:*>` namespace)
- **Header Section**: Large XBRL header (`<ix:header>`) containing contexts, units, and references
- **Content Start**: Actual document content begins after `</ix:header>` tag

Example structure:
```html
<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
<head><title>aapl-20240928</title></head>
<body>
  <div style="display:none">
    <ix:header>
      <!-- XBRL contexts, units, references -->
    </ix:header>
  </div>
  <!-- Actual document content starts here -->
```

### 2. Section Delimitation Patterns

#### A. Anchor-Based Navigation (Most Common)

Modern filings use anchor tags with unique IDs for section navigation:

```html
<!-- Table of Contents -->
<a href="#i7bfbfbe54b9647b1b4ba4ff4e0aba09d_10">Part I</a>
<a href="#i7bfbfbe54b9647b1b4ba4ff4e0aba09d_13">Item 1.</a>
<a href="#i7bfbfbe54b9647b1b4ba4ff4e0aba09d_52">Item 1A.</a>

<!-- Section Headers -->
<div id="i7bfbfbe54b9647b1b4ba4ff4e0aba09d_13"></div>
<div style="margin-top:12pt">
  <span style="font-weight:700">Item 1. Business</span>
</div>
```

**Pattern Characteristics**:
- Unique hash-based IDs (e.g., `i7bfbfbe54b9647b1b4ba4ff4e0aba09d_13`)
- Links in TOC reference these IDs with `#` prefix
- Section headers immediately follow anchor divs

#### B. Hierarchical Structure

Standard 10-K/10-Q organization:
```
Part I
  Item 1. Business
  Item 1A. Risk Factors
  Item 1B. Unresolved Staff Comments
  Item 1C. Cybersecurity
  Item 2. Properties
  Item 3. Legal Proceedings
  Item 4. Mine Safety Disclosures

Part II
  Item 5. Market for Registrant's Common Equity
  Item 6. [Reserved]
  Item 7. Management's Discussion and Analysis
  Item 7A. Quantitative and Qualitative Disclosures
  Item 8. Financial Statements
  Item 9. Changes in and Disagreements
  Item 9A. Controls and Procedures
  Item 9B. Other Information
  Item 9C. Disclosure Regarding Foreign Jurisdictions

Part III
  Item 10. Directors, Executive Officers
  Item 11. Executive Compensation
  Item 12. Security Ownership
  Item 13. Certain Relationships
  Item 14. Principal Accountant Fees

Part IV
  Item 15. Exhibits and Financial Statement Schedules
  Item 16. Form 10-K Summary
```

### 3. HTML Patterns for Section Headers

#### Pattern 1: Bold Text in Styled Divs
```html
<div style="margin-top:12pt;padding-left:45pt;text-align:justify">
  <span style="font-weight:700">Item 1. Business</span>
</div>
```

#### Pattern 2: Table-Based TOC with Links
```html
<table>
  <tr>
    <td><a href="#item1">Item 1.</a></td>
    <td>Business</td>
    <td>Page 3</td>
  </tr>
</table>
```

#### Pattern 3: Page Breaks Between Sections
```html
<hr style="page-break-after:always"/>
<div id="item2_section">
  <span style="font-weight:700">Item 2. Properties</span>
</div>
```

### 4. Section Identification Strategies

#### Reliable Patterns for Programmatic Extraction:

1. **Anchor ID Method** (Most Reliable)
   - Search for `id` attributes in divs
   - Map TOC `href="#id"` to corresponding `id="id"` locations
   - Extract text following the anchor div

2. **Bold Text Pattern**
   - Search for: `<span style="font-weight:700">Item \d+`
   - Or: `<b>Item \d+`
   - Usually preceded by spacing/formatting divs

3. **TOC Analysis**
   - Locate "Table of Contents" section
   - Extract all links with "Item" or "Part" text
   - Follow href anchors to actual sections

### 5. Content Extraction Challenges

#### iXBRL Complications
- Inline XBRL tags (`<ix:nonNumeric>`, `<ix:nonFraction>`) embedded throughout
- Must filter or parse around XBRL tags for clean text extraction
- Financial data often wrapped in XBRL tags with context references

Example:
```html
The Company had <ix:nonFraction contextRef="c-21"
  name="us-gaap:Assets" decimals="-6">123456</ix:nonFraction>
million in total assets.
```

#### Variation Across Companies
- Some companies use custom CSS classes
- Older filings may use HTML 3.2 constructs (`<font>` tags)
- Table-heavy layouts vs. div-based layouts

### 6. Best Practices for Parsing

#### Recommended Approach:
1. **Detect Format**: Check for `<ix:header>` to identify iXBRL documents
2. **Skip XBRL Header**: Start parsing after `</ix:header>` tag
3. **Build Section Map**: Extract TOC links and map to section IDs
4. **Clean Content**: Strip or parse XBRL tags based on needs
5. **Handle Variations**: Implement fallbacks for different HTML patterns

#### Code Pattern:
```python
def extract_sections(html_content):
    # Skip XBRL header if present
    header_end = html_content.find('</ix:header>')
    if header_end > 0:
        content = html_content[header_end:]
    else:
        content = html_content

    # Find all section anchors
    import re
    section_pattern = r'<div id="([^"]+)".*?Item\s+(\d+[A-Z]?)'
    sections = re.findall(section_pattern, content, re.DOTALL | re.IGNORECASE)

    # Map sections to content
    section_map = {}
    for section_id, item_num in sections:
        # Extract content between this section and next
        # Implementation details...
        pass

    return section_map
```

### 7. Evolution and Trends

#### Historical Changes:
- **Pre-2019**: Mixed HTML/ASCII, simpler structure
- **2019-2021**: Transition to iXBRL format
- **2022-Present**: Standardized iXBRL with consistent patterns

#### Future Considerations:
- SEC's EDGAR Next initiative may introduce new formats
- Increased structure through mandatory tagging
- Potential API-based access reducing HTML parsing needs

## Related Research

- [SGML XBRL Inline Parsing](../extraction-techniques/sgml-xbrl-inline-parsing.md) - Handling XBRL within SGML documents
- [8-K Financial Exhibit Patterns](../8-k/8k-financial-exhibit-patterns.md) - Similar patterns in 8-K filings

## Validation

Patterns validated against:
- Apple (AAPL) 10-K 2024 (0000320193-24-000123)
- Microsoft (MSFT) 10-K 2025 (0000950170-25-100235)
- IBM 10-K 2025 (0000051143-25-000015)
- JPMorgan Chase (JPM) 10-K/10-Q latest filings
- General Electric (GE) 10-K/10-Q latest filings

## Implementation Status

These patterns are currently used in EdgarTools for:
- Filing HTML content extraction
- Section navigation in filing viewers
- Table of contents generation

Areas for improvement:
- More robust section boundary detection
- Better handling of company-specific variations
- Automated section content extraction APIs

---

*Last Updated: 2025-01-28*
*Next Review: When SEC announces EDGAR format changes*