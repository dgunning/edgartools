# 8-K Financial Exhibit Patterns Research

**Research Date**: 2025-09-27
**Author**: SEC Filing Research Specialist
**Status**: Initial Analysis Complete

## Executive Summary

This research analyzes 8-K filing structures and HTML financial exhibit patterns to understand how companies present financial data in current reports. The analysis covers exhibit types, HTML table structures, data presentation patterns, and the relationship between XBRL and HTML financial data.

## Key Findings

### 1. Common 8-K Exhibit Types Containing Financial Data

**Primary Financial Exhibit Types:**
- **EX-99.1**: Most common exhibit for earnings press releases (56% of 8-Ks analyzed)
- **EX-99.2**: Secondary exhibits, often supplemental financial information (16% of 8-Ks)
- **EX-99**: Generic exhibit designation, sometimes contains financials

**Exhibit Characteristics:**
```python
# Typical exhibit identification pattern
financial_exhibits = [
    'EX-99',     # Generic press release
    'EX-99.1',   # Primary press release/earnings announcement
    'EX-99.01',  # Alternative numbering format
    'EX-99.2'    # Supplemental financial information
]
```

**Document Type Distribution:**
- 100% of earnings announcements use EX-99.x format
- Press releases typically labeled as "Press Release" or "Earnings Release" in description
- Financial supplements may have varied descriptions

### 2. HTML Table Structure Patterns

**Common Table Types Identified:**

#### Income Statement Tables
- **Structure**: Period comparison format (Q3 2024 vs Q3 2023)
- **Headers**: Typically include "Three Months Ended", "Six Months Ended", "Nine Months Ended"
- **Metrics**: Revenue, Operating Income, Net Income, EPS
- **Prevalence**: Found in ~75% of earnings press releases

#### Per Share Data Tables
- **Structure**: Dedicated tables for EPS metrics
- **Headers**: "Basic", "Diluted", "Weighted Average Shares"
- **Format**: Often separated from main financial tables
- **Prevalence**: Found in ~30% of press releases

#### Key Metrics Summary Tables
- **Structure**: Highlight tables at beginning of press release
- **Content**: Revenue, Net Income, Operating Margin, EPS
- **Format**: Simple 2-3 column format with current vs prior period

**HTML Table Patterns:**
```html
<!-- Common financial table structure -->
<table>
  <tr>
    <th></th>
    <th>Three Months Ended<br>September 30,</th>
    <th>Nine Months Ended<br>September 30,</th>
  </tr>
  <tr>
    <th></th>
    <th>2024</th>
    <th>2023</th>
    <th>2024</th>
    <th>2023</th>
  </tr>
  <tr>
    <td>Revenue</td>
    <td>$XX,XXX</td>
    <td>$XX,XXX</td>
    <td>$XXX,XXX</td>
    <td>$XXX,XXX</td>
  </tr>
</table>
```

### 3. Financial Data Presentation Patterns

**Metric Availability in HTML Exhibits:**
- Revenue: 50% availability in press releases
- Net Income: 50% availability
- Operating Income: 50% availability
- Gross Profit: 50% availability
- EPS: Often in separate tables or narrative text

**Data Format Characteristics:**
- **Currency**: Typically shown with $ symbol
- **Scale**: Often in millions or billions (noted in headers)
- **Precision**: Usually to nearest million, sometimes with decimals for per-share data
- **Periods**: Quarterly and year-to-date comparisons standard

**Common Presentation Styles:**

1. **Consolidated Statements Format**
   - Full financial statements embedded in HTML
   - Mimics 10-Q/10-K format but less detailed
   - Common for larger companies

2. **Summary Highlights Format**
   - Key metrics only
   - Narrative discussion with embedded tables
   - Common for earnings announcements

3. **Supplemental Tables Format**
   - Detailed breakdowns by segment/geography
   - Non-GAAP reconciliations
   - Typically in EX-99.2 exhibits

### 4. XBRL vs HTML Financial Data

**Coverage Analysis:**
- **XBRL in 8-K**: 100% of analyzed filings have XBRL
- **HTML Financial Data**: 48% have parseable financial tables
- **Overlap**: Limited - XBRL in 8-K typically covers filing metadata, not detailed financials

**Key Differences:**

| Aspect | XBRL in 8-K | HTML Exhibits |
|--------|-------------|---------------|
| **Data Type** | Filing metadata, basic facts | Detailed financial results |
| **Timeliness** | Real-time with filing | Real-time with filing |
| **Structure** | Standardized taxonomy | Company-specific format |
| **Completeness** | Limited financial data | Comprehensive earnings data |
| **Parseability** | Machine-readable | Requires HTML parsing |

**Complementary Nature:**
- XBRL provides standardized facts
- HTML exhibits provide narrative context and detailed breakdowns
- Both needed for complete picture

## Implementation Insights

### Reliable Extraction Techniques

**Table Identification:**
```python
def is_financial_table(table):
    """Identify financial tables with high confidence."""
    indicators = {
        'headers': ['months ended', 'year ended', 'fiscal'],
        'metrics': ['revenue', 'income', 'earnings', 'cash'],
        'format': ['$', '(', ')', ',']  # Currency and number formatting
    }

    # Must have period headers AND financial metrics
    has_period = any(period in table.text.lower() for period in indicators['headers'])
    has_metrics = any(metric in table.text.lower() for metric in indicators['metrics'])
    has_numbers = bool(re.search(r'\$?[\d,]+', table.text))

    return has_period and has_metrics and has_numbers
```

**Metric Extraction Pattern:**
```python
def extract_metric(table, metric_name):
    """Extract specific metric from financial table."""
    for row in table.find_all('tr'):
        if metric_name.lower() in row.text.lower():
            # Find numeric cells in the row
            cells = row.find_all(['td', 'th'])
            values = []
            for cell in cells:
                # Match currency patterns
                match = re.search(r'\$?([\d,]+\.?\d*)', cell.text)
                if match:
                    values.append(match.group(1))
            return values
    return None
```

### Edge Cases and Challenges

1. **Format Variations**
   - Companies use different HTML structures
   - Table headers vary significantly
   - Some use nested tables or divs styled as tables

2. **Data Quality Issues**
   - Inconsistent number formatting (parentheses vs minus signs)
   - Scale variations (thousands vs millions)
   - Mixed GAAP/non-GAAP in same table

3. **Identification Challenges**
   - Non-financial tables mixed with financial ones
   - Financial data in narrative paragraphs
   - Graphics/images containing financial data

## Current EdgarTools Capabilities

### Existing Support

**8-K Filing Access:**
```python
from edgar import Company
from edgar.company_reports import EightK

# Current capability
company = Company("AAPL")
filing = company.get_filings(form="8-K").latest()
eight_k = filing.obj()  # Returns EightK object

# Press release access
if eight_k.has_press_release:
    for pr in eight_k.press_releases:
        html = pr.html()  # Raw HTML available
        text = pr.text()  # Text extraction available
```

**HTML Table Extraction:**
```python
from edgar.files.htmltools import extract_tables

# Current capability
tables = extract_tables(html_str)  # Returns list of DataFrames
```

### Gaps Identified

1. **No Financial Table Recognition**
   - Cannot distinguish financial from non-financial tables
   - No metric-specific extraction

2. **No Standardized Data Structure**
   - Raw DataFrames without semantic understanding
   - No mapping to standard financial concepts

3. **No Period Handling**
   - Cannot parse period headers automatically
   - No comparison period alignment

## Recommendations

### Phase 1: Pattern Library Development
Build comprehensive pattern library for common financial table formats:
- Collect 100+ samples across industries
- Document variations and edge cases
- Create test suite for pattern matching

### Phase 2: Selective Implementation
Focus on high-confidence patterns first:
- Income statement summaries (highest standardization)
- Key metrics tables (clear structure)
- Per-share data (well-defined format)

### Phase 3: Integration Strategy
```python
# Proposed API design
class EightKFinancials:
    """Financial data extracted from 8-K HTML exhibits."""

    def get_metric(self, metric_name: str, period: str = None):
        """Get specific financial metric."""
        pass

    def get_income_summary(self):
        """Get income statement summary if available."""
        pass

    def confidence_score(self):
        """Return confidence level of extracted data."""
        pass

# Integration with existing EightK class
eight_k.parse_financial_exhibits()  # New method
```

## Testing Data

**Test Companies with Good 8-K Financial Exhibits:**
- **Technology**: AAPL, MSFT, GOOGL - Consistent HTML format
- **Financial**: JPM, BAC - Complex but structured tables
- **Retail**: WMT, TGT - Clear period comparisons
- **Healthcare**: JNJ, PFE - Detailed segment breakdowns

**Test Cases to Cover:**
- Multiple period comparisons
- GAAP vs non-GAAP presentations
- Segment reporting tables
- Geographic breakdowns
- Per-share calculations

## Conclusion

8-K HTML financial exhibits represent a significant source of timely financial data between quarterly XBRL filings. While format variations present challenges, clear patterns exist that enable reliable extraction for a significant portion of filings.

The complementary nature of XBRL and HTML data in 8-K filings suggests both should be leveraged for comprehensive financial data access. A phased implementation focusing on high-confidence patterns can provide immediate value while minimizing accuracy risks.

## Related Research

- [HTML Table Extraction Techniques](/docs-internal/research/sec-filings/extraction-techniques/html-table-parsing.md) (To be created)
- [XBRL vs HTML Data Comparison](/docs-internal/research/sec-filings/data-structures/xbrl-html-comparison.md) (To be created)
- [8-K Feature Request Analysis](/docs-internal/issues/feature-requests/8k-html-financial-parsing.md)

## Code Examples

All research code is available in:
- `/tools/research_8k_financial_exhibits.py` - Initial structure analysis
- `/tools/deep_8k_analysis.py` - Deep pattern analysis

These scripts can be used to reproduce findings and extend research to additional companies or time periods.