# Cross Reference Index Format in 10-K Filings

## Overview

Some companies (e.g., GE, Citigroup) use a **Cross Reference Index** format instead of standard Item headings in their 10-K filings. This document analyzes the format and proposes an implementation approach.

## Problem Statement

**Standard Format:**
- Sections have headings like "Item 1A. Risk Factors"
- Content directly follows the heading
- Easy to extract by searching for the heading text

**Cross Reference Index Format:**
- Contains a table mapping Items to page numbers
- Actual content sections have NO Item headings
- Extraction requires:
  1. Detecting the Cross Reference Index table
  2. Parsing Item-to-page mappings
  3. Navigating to referenced pages (complex in HTML)

## Real Example: GE 10-K (Filed 2025-02-03)

### Table Structure

Located near the end of the filing (position ~3.39MB in a 3.44MB HTML file), the table has 3 columns:

```
| Item Number | Item Title                          | Page Numbers      |
|-------------|-------------------------------------|-------------------|
| Part I      |                                     |                   |
| Item 1.     | Business                            | 4-7, 9-11, 74-75  |
| Item 1A.    | Risk Factors                        | 26-33             |
| Item 1B.    | Unresolved Staff Comments           | Not applicable    |
| Item 1C.    | Cybersecurity                       | 25                |
| Item 2.     | Properties                          | 4                 |
| Item 3.     | Legal Proceedings                   | 73-74             |
| Item 4.     | Mine Safety Disclosures             | Not applicable    |
| Part II     |                                     |                   |
| Item 5.     | Market for Registrant's Common...   | 24                |
| ...         | ...                                 | ...               |
```

### HTML Structure

```html
<table>
  <tr>
    <td colspan="3"><span>Item 1A.</span></td>
    <td colspan="3"></td>
    <td colspan="3"><span>Risk Factors</span></td>
    <td colspan="3"></td>
    <td colspan="3"><span>26-33</span></td>
  </tr>
  <!-- More rows... -->
</table>
```

**Key Observations:**
- Item number in first column
- Item title in middle column
- Page numbers in last column
- Borders separate rows (1pt solid #000000)
- Part headers (e.g., "Part II") are in bold

### Page Number Formats

1. **Single page**: `"4"`, `"25"`
2. **Page range**: `"26-33"`, `"73-74"`
3. **Multiple ranges**: `"4-7, 9-11, 74-75"`
4. **Not applicable**: `"Not applicable"`

## Technical Challenges

### 1. Table Detection

**How to detect Cross Reference Index format:**

```python
def has_cross_reference_index(html: str) -> bool:
    """Detect if filing uses Cross Reference Index format."""
    # Look for the specific heading
    if 'Form 10-K Cross Reference Index' not in html:
        return False

    # Look for table with Item/page mapping pattern
    pattern = r'<td[^>]*>.*?Item\s+1A\..*?</td>.*?<td[^>]*>.*?Risk Factors.*?</td>.*?<td[^>]*>.*?\d+-\d+.*?</td>'
    return bool(re.search(pattern, html, re.DOTALL | re.IGNORECASE))
```

### 2. Table Parsing

**Extract Item-to-page mappings:**

```python
def parse_cross_reference_index(html: str) -> dict:
    """
    Parse Cross Reference Index table.

    Returns:
        dict: Mapping of item numbers to page numbers
        {
            '1': '4-7, 9-11, 74-75',
            '1A': '26-33',
            '1B': None,  # Not applicable
            ...
        }
    """
    # Find the table
    # Parse each row
    # Extract item number, title, and page numbers
    pass
```

### 3. Page-Based Navigation (HARD PROBLEM)

**Challenge**: HTML doesn't have explicit page breaks.

**Approaches:**

#### Option A: Use Page Break Hints (Most Reliable)
```python
# Look for page break indicators in HTML:
# - <hr style="page-break-after:always"/>
# - <div style="page-break-after:always"/>
# - iXBRL page tags

def find_page_breaks(html: str) -> list[int]:
    """Find positions of page breaks in HTML."""
    breaks = []
    # Search for page break elements
    return breaks

def extract_content_by_page_range(html: str, page_range: str) -> str:
    """
    Extract content from specified page range.

    Args:
        html: Full HTML content
        page_range: e.g., "26-33", "4-7, 9-11, 74-75"

    Returns:
        Extracted HTML content
    """
    page_breaks = find_page_breaks(html)
    # Parse page range (handle "26-33", "4-7, 9-11", etc.)
    # Extract HTML between page breaks
    pass
```

#### Option B: Heuristic Content Search (Fallback)
```python
def find_risk_factors_content(html: str) -> str:
    """
    Use heuristics to find Risk Factors content.

    Even without page numbers, look for:
    - Section with "risk" in heading
    - Between other known sections
    - Content patterns (bullet points, forward-looking statements)
    """
    pass
```

#### Option C: Use Document Structure (New Parser)
```python
from edgar.documents import parse_html

def extract_by_page_with_new_parser(html: str, page_range: str) -> str:
    """Use new HTMLParser's document model to navigate by pages."""
    doc = parse_html(html)
    # Use doc.search() or doc structure to find page breaks
    # Extract content
    pass
```

## Implementation Plan

### Phase 1: Detection and Parsing (Week 1)
- [ ] Implement `has_cross_reference_index()` detector
- [ ] Implement `parse_cross_reference_index()` table parser
- [ ] Add unit tests with GE 10-K example
- [ ] Document Item-to-page mapping format

### Phase 2: Page Break Analysis (Week 2)
- [ ] Research page break patterns across multiple filings
- [ ] Analyze GE, Citigroup, and other Cross Reference Index filings
- [ ] Document page break indicators (HTML tags, styles)
- [ ] Implement `find_page_breaks()` function
- [ ] Validate page break detection accuracy

### Phase 3: Content Extraction (Week 3)
- [ ] Implement page-range parser ("26-33", "4-7, 9-11, 74-75")
- [ ] Implement page-based content extraction
- [ ] Add heuristic fallback for when page breaks aren't reliable
- [ ] Test with multiple filings

### Phase 4: Integration (Week 4)
- [ ] Integrate with existing 10-K item extraction
- [ ] Update `TenK` class to handle Cross Reference Index format
- [ ] Add graceful degradation when page extraction fails
- [ ] Update documentation

### Phase 5: Testing and Validation (Week 5)
- [ ] Test with GE filings (multiple years)
- [ ] Test with Citigroup filings (GitHub issue #251)
- [ ] Test with other companies using this format
- [ ] Add regression tests
- [ ] Update test suite

## Related Issues

- **edgartools-zwd** (P3): Support Cross Reference Index format in 10-K filings
- **GitHub #215**: GE 10-K extraction returns None for all items
- **GitHub #251**: Citigroup 10-K extraction returns None for all items

## Example Filings

| Company    | CIK     | Form  | Filing Date  | Accession           |
|------------|---------|-------|--------------|---------------------|
| GE         | 40545   | 10-K  | 2025-02-03   | 0000040545-25-000015|
| Citigroup  | 831001  | 10-K  | TBD          | TBD                 |

## References

- GE 10-K HTML: Position 3,389,500 - 3,398,000 contains the Cross Reference Index table
- Table anchor ID: `id913165b39c64b39b915c0e0726aa953_310`
- Forward-looking statements section starts immediately after the table of contents

## Next Steps

1. Create sample test data with GE Cross Reference Index table
2. Implement table parser with regex patterns
3. Research page break detection strategies
4. Prototype page-based extraction with one Item (e.g., Item 1A)
5. Evaluate accuracy and decide on production approach
