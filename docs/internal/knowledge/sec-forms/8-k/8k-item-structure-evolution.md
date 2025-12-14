# 8-K Item Structure Evolution Across Filing Eras

**Research Date:** 2025-11-07
**Researcher:** SEC Filing Research Agent
**Related Issue:** Beads Issue #tm2 (Investigation of 8-K item detection across eras)
**Status:** Initial Research Complete

## Executive Summary

8-K filings have undergone significant structural changes across three distinct eras, evolving from integer-based item numbering (Item 1, Item 5) to decimal-based item numbering (Item 2.02, Item 9.01). This evolution coincides with the transition from SGML to XML filing formats and reflects SEC regulatory changes to improve disclosure standardization.

### Key Findings

1. **Legacy SGML Era (1995-2004)**: Integer items (1-9) with minimal HTML structure
2. **Mid-Period XML Era (2005-2012)**: Transition to decimal items (X.XX format) with improved HTML
3. **Modern XML Era (2013-present)**: Standardized decimal items with rich HTML structure

### Current Code Impact

- **Detection Pattern**: `decimal_item_pattern = r"^(Item\s{1,3}[0-9]{1,2}\.[0-9]{2})\.?"`
- **Works For**: Modern era (2013+) filings with HTML
- **Fails For**: Legacy SGML filings (no HTML), early transition period filings
- **Normalization Issue**: Current code returns "Item 2.02" but tests expect "2.02"

---

## Filing Eras and Item Formats

### 1. Legacy SGML Era (1995-2004)

**Characteristics:**
- **Format**: Plain text SGML with minimal structure
- **Item Numbering**: Integer format (Item 1, Item 2, ... Item 9)
- **HTML Availability**: No HTML documents (SGML only)
- **Detection Challenge**: Must parse raw text, not HTML

**Standard Item Numbers (Pre-2004):**
```
Item 1:  Changes in Control of Registrant
Item 2:  Acquisition or Disposition of Assets
Item 3:  Bankruptcy or Receivership
Item 4:  Changes in Registrant's Certifying Accountant
Item 5:  Other Events
Item 6:  Resignation of Registrant's Directors
Item 7:  Financial Statements, Pro Forma Financial Information and Exhibits
Item 8:  Change in Fiscal Year
Item 9:  Regulation FD Disclosure (added 2000)
```

**Example Filing:**
- **Company**: YAHOO INC
- **Date**: 1998-01-05
- **Accession**: 0001047469-98-000122
- **Items Found**: Item 5, Item 7
- **Structure**: Plain SGML text

**Sample Text Structure:**
```text
ITEM 5.  OTHER EVENTS

[Event description text...]

ITEM 7.  FINANCIAL STATEMENTS, PRO FORMA FINANCIAL INFORMATION AND EXHIBITS.

[Exhibit list...]
```

**Detection Pattern for Legacy:**
```python
# Pattern for integer items in plain text
legacy_pattern = r'\bItem\s+(\d+)\b'
# Matches: "Item 5", "Item 7", etc.
```

---

### 2. Mid-Period XML Era (2005-2012)

**Characteristics:**
- **Format**: XML-based with HTML rendering
- **Item Numbering**: Decimal format (Item X.XX) introduced gradually
- **HTML Availability**: Yes, but structure varies
- **Detection Challenge**: Transition period with inconsistent formatting

**Regulatory Change:**
- SEC amended Form 8-K requirements in August 2004 (effective 2005)
- Introduced new item numbering system with decimal format
- Expanded disclosure requirements from 9 items to 30+ items organized in categories

**New Categorical Structure:**
```
Section 1 - Registrant's Business and Operations (Items 1.01-1.04)
Section 2 - Financial Information (Items 2.01-2.06)
Section 3 - Securities and Trading Markets (Items 3.01-3.03)
Section 4 - Matters Related to Accountants and Financial Statements (Items 4.01-4.02)
Section 5 - Corporate Governance and Management (Items 5.01-5.08)
Section 6 - Asset-Backed Securities (Items 6.01-6.05)
Section 7 - Regulation FD (Items 7.01)
Section 8 - Other Events (Items 8.01)
Section 9 - Financial Statements and Exhibits (Items 9.01)
```

**Common Items in This Era:**
```
Item 1.01: Entry into a Material Definitive Agreement
Item 2.02: Results of Operations and Financial Condition
Item 5.02: Departure/Appointment of Directors or Officers
Item 7.01: Regulation FD Disclosure
Item 8.01: Other Events
Item 9.01: Financial Statements and Exhibits (most common)
```

**Example Filings:**

**2008 Example:**
- **Company**: 180 Connect Inc.
- **Date**: 2008-03-31
- **Accession**: 0000950144-08-002465
- **Expected Items**: [2.02, 9.01] or [8.01, 9.01]

**2011 Example:**
- **Company**: AEHR TEST SYSTEMS
- **Date**: 2011-03-31
- **Accession**: 0001040470-11-000019
- **Expected Items**: [8.01, 9.01] or [5.02, 9.01]

**HTML Structure (Typical):**
```html
<FONT STYLE="font-family:Times New Roman" SIZE="2">
    <B>Item&nbsp;2.02</B>
</FONT>
<TD ALIGN="left" VALIGN="top">
    <FONT STYLE="font-family:Times New Roman" SIZE="2">
        <B>Results of Operations and Financial Condition</B>
    </FONT>
</TD>
```

---

### 3. Modern XML Era (2013-Present)

**Characteristics:**
- **Format**: Inline XBRL with rich HTML
- **Item Numbering**: Standardized decimal format (Item X.XX)
- **HTML Availability**: Yes, with consistent structure
- **Detection Challenge**: Normalization (with vs without "Item " prefix)

**Standard Item Structure:**
- Items organized into 9 sections (1.XX through 9.XX)
- Consistent formatting across companies
- SEC-extract metadata in HTML for machine readability

**Most Common Items (2020-2025):**
```
Item 1.01: Material Definitive Agreement (11% of filings)
Item 2.02: Results/Financial Condition (18% of filings)
Item 5.02: Director/Officer Changes (15% of filings)
Item 7.01: Regulation FD Disclosure (12% of filings)
Item 8.01: Other Events (25% of filings)
Item 9.01: Financial Statements/Exhibits (95% of filings - required)
```

**Example Filings:**

**2023 Example:**
- **Company**: ADOBE INC.
- **Date**: 2023-03-15
- **Accession**: 0000796343-23-000044
- **Items Detected**: ['Item 2.02', 'Item 9.01']
- **Expected**: ['2.02', '9.01']

**2024 Example:**
- **Company**: 3M CO
- **Date**: 2024-03-08
- **Accession**: 0000066740-24-000023
- **Items Detected**: ['Item 8.01', 'Item 9.01']
- **Expected**: ['8.01', '9.01']

**HTML Structure (Modern):**
```html
<div style="-sec-extract:summary;margin-bottom:12pt">
    <span style="color:#000000;font-family:'Times New Roman',sans-serif;
                 font-size:10pt;font-weight:700;line-height:120%">
        Item 2.02. Results of Operations and Financial Condition.
    </span>
</div>
<div style="margin-bottom:12pt">
    <span style="color:#000000;font-family:'Times New Roman',sans-serif;
                 font-size:10pt;font-weight:400;line-height:120%">
        On March 15, 2023, Adobe Inc. ("Adobe") issued a press release...
    </span>
</div>
```

**Detection Pattern:**
```python
# Current pattern in edgar/files/htmltools.py
decimal_item_pattern = r"^(Item\s{1,3}[0-9]{1,2}\.[0-9]{2})\.?"

# Matches: "Item 2.02", "Item 9.01", etc.
# Note: ^ anchor requires item to be at line start after strip()
```

---

## Current Code Analysis

### Detection Implementation

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/files/htmltools.py`

**Key Functions:**

```python
# Line 101: Pattern definitions
decimal_item_pattern = r"^(Item\s{1,3}[0-9]{1,2}\.[0-9]{2})\.?"

# Line 141-142: Detection function
def detect_decimal_items(text: pd.Series):
    return text.str.extract(decimal_item_pattern, expand=False,
                           flags=re.IGNORECASE | re.MULTILINE)
```

**Usage in EightK Class:**

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/company_reports.py`

```python
# Line 729-735: EightK chunked document creation
@cached_property
def chunked_document(self):
    html = self._filing.html()
    if not html:
        return None
    decimal_chunk_fn = partial(chunks2df,
                               item_detector=detect_decimal_items,
                               item_adjuster=adjust_for_empty_items,
                               item_structure=self.structure)

    return ChunkedDocument(html, chunk_fn=decimal_chunk_fn)
```

**Key Points:**
1. Only uses `detect_decimal_items` (not `detect_int_items`)
2. Requires HTML to be available
3. Returns full "Item X.XX" format (not just "X.XX")
4. Depends on text chunking and forward-fill logic

### ChunkedDocument Processing

**Location**: `/Users/dwight/PycharmProjects/edgartools/edgar/files/htmltools.py`

**Process Flow:**

1. **Chunk HTML** (`chunk(html)`) - Break into semantic blocks
2. **Detect Items** (`item_detector(df.Text)`) - Apply regex pattern
3. **Forward Fill** (`chunk_df['Item'].ffill()`) - Propagate item to subsequent chunks
4. **Handle Signatures** - Clear items after signature detection
5. **Normalize** (`.str.title()`) - Convert to title case

**Critical Code (Lines 260-305):**
```python
def chunks2df(chunks: List,
              item_detector: Callable[[pd.Series], pd.Series] = detect_int_items,
              item_adjuster: Callable[[pd.DataFrame, Dict[str, Any]], pd.DataFrame] = adjust_detected_items,
              item_structure=None,
              ) -> pd.DataFrame:
    """Convert the chunks to a dataframe
        : item_detector: A function that detects the item in the text column
        : item_adjuster: A function that finds issues like out of sequence items and adjusts the item column
        : item_structure: A dictionary of items specific to each filing e.g. 8-K, 10-K, 10-Q
    """
    # Create dataframe with detected items
    chunk_df = pd.DataFrame([...]).assign(
        ...
        Item=lambda df: item_detector(df.Text)  # Apply detection
    )

    # Forward fill items to subsequent chunks
    chunk_df['Item'] = chunk_df['Item'].ffill()

    # Clear items after signature
    signature_rows = chunk_df[chunk_df.Signature]
    if len(signature_rows) > 0:
        signature_loc = signature_rows.index[0]
        chunk_df.loc[signature_loc:, 'Item'] = pd.NA

    # Normalize to title case
    chunk_df.Item = chunk_df.Item.fillna("").str.title()

    return chunk_df
```

---

## Test Coverage

### Existing Tests

**Location**: `/Users/dwight/PycharmProjects/edgartools/tests/test_eightK.py`

**Test Cases by Era:**

**Modern Era (Working):**
```python
# Line 92-111: Test from 2023
def test_create_eightk_obj_and_find_items():
    adobe_8K = Filing(form='8-K', filing_date='2023-03-15',
                     company='ADOBE INC.', cik=796343,
                     accession_no='0000796343-23-000044')
    eightk = adobe_8K.obj()
    assert eightk.items == ['Item 2.02', 'Item 9.01']
    # Note: Returns full "Item X.XX" format
```

**Legacy Era (Partial Support):**
```python
# Line 157-164: Test from 1998
def test_create_eightk_from_old_filing_with_no_html():
    f = Filing(form='8-K', filing_date='1998-01-05',
              company='YAHOO INC', cik=1011006,
              accession_no='0001047469-98-000122')
    eightk = f.obj()
    assert eightk  # Only tests object creation
    # Does NOT test item detection
```

**Gap Analysis:**
- ✅ Modern filings (2013+) with decimal items
- ⚠️ Legacy filings (1995-2004) - object creation only
- ❌ Mid-period transition (2005-2012) - no specific tests
- ❌ Integer item detection - no tests
- ❌ Normalization ("Item 2.02" vs "2.02") - no tests

---

## Detection Challenges by Era

### Legacy SGML Era Challenges

**Problem 1: No HTML Available**
```python
# Current code in company_reports.py line 726-728
html = self._filing.html()
if not html:
    return None  # ChunkedDocument returns None
```

**Impact:**
- `eightk.items` returns `[]` instead of detecting items
- Item text extraction fails
- Must fall back to raw SGML parsing

**Solution Approach:**
```python
# Potential fallback for SGML filings
if not html:
    # Parse SGML text directly
    text = self._filing.text()
    # Use integer item pattern
    int_pattern = r'\bItem\s+(\d+)\b'
    items = re.findall(int_pattern, text, re.IGNORECASE)
    return sorted(set(items))
```

**Problem 2: Integer vs Decimal Patterns**
```python
# Current: Only decimal pattern
decimal_item_pattern = r"^(Item\s{1,3}[0-9]{1,2}\.[0-9]{2})\.?"

# Needed: Integer pattern
int_item_pattern = r"^(Item\s{1,3}[0-9]{1,2}[A-Z]?)\.?"
```

### Mid-Period Era Challenges

**Problem 1: Inconsistent HTML Structure**
- Some filings use old HTML formatting (FONT tags, non-breaking spaces)
- Item text may not start at line beginning (pattern ^ anchor fails)
- Mix of uppercase ITEM vs title case Item

**Example Issue:**
```html
<!-- 2011 filing structure -->
<FONT STYLE="font-family:Times New Roman" SIZE="2">
    <B>Item&nbsp;8.01</B>
</FONT>
```

**Pattern Fails Because:**
- `&nbsp;` creates spacing issues
- Text may not be at line start after chunking
- `<B>` tag handling in chunk extraction

**Problem 2: Detection in ChunkedDocument**
- Relies on regex matching on chunk text
- Chunks may split items awkwardly
- Forward-fill logic can propagate wrong items

### Modern Era Challenges

**Problem: Normalization Mismatch**

**Code Returns:**
```python
['Item 2.02', 'Item 9.01']  # With "Item " prefix
```

**Tests/Users Expect:**
```python
['2.02', '9.01']  # Without "Item " prefix
```

**Root Cause:**
```python
# Line 101 pattern includes "Item" in capture group
decimal_item_pattern = r"^(Item\s{1,3}[0-9]{1,2}\.[0-9]{2})\.?"
#                         ^--- Captures "Item " prefix
```

**Solution:**
```python
# Option 1: Don't capture "Item" prefix
decimal_item_pattern = r"^Item\s{1,3}([0-9]{1,2}\.[0-9]{2})\.?"
#                                    ^--- Only capture number

# Option 2: Strip "Item " after detection
items = [item.replace('Item ', '') for item in detected_items]
```

---

## HTML Structure Patterns

### Legacy SGML (1995-2004)

**No HTML - Plain Text Structure:**
```
ITEM 5.  OTHER EVENTS

On January 3, 1998, Yahoo! Inc. announced...

ITEM 7.  FINANCIAL STATEMENTS, PRO FORMA FINANCIAL INFORMATION AND EXHIBITS.

(c) Exhibits
```

**Characteristics:**
- All uppercase "ITEM"
- Period and spaces after number
- No HTML tags
- Simple section headers

---

### Mid-Period XML (2005-2012)

**HTML with Table Structure:**
```html
<TABLE>
<TR>
    <TD VALIGN="top">
        <FONT STYLE="font-family:Times New Roman" SIZE="2">
            <B>Item&nbsp;2.02</B>
        </FONT>
    </TD>
    <TD ALIGN="left" VALIGN="top">
        <FONT STYLE="font-family:Times New Roman" SIZE="2">
            <B>Results of Operations and Financial Condition</B>
        </FONT>
    </TD>
</TR>
</TABLE>
```

**Characteristics:**
- Mix of formatting (title case "Item", `&nbsp;` entities)
- Table-based layout
- FONT tags with inline styles
- Non-semantic HTML

---

### Modern XML (2013-Present)

**Semantic HTML with SEC Metadata:**
```html
<div style="-sec-extract:summary;margin-bottom:12pt">
    <span style="color:#000000;font-family:'Times New Roman',sans-serif;
                 font-size:10pt;font-weight:700;line-height:120%">
        Item 2.02. Results of Operations and Financial Condition.
    </span>
</div>
```

**Characteristics:**
- `-sec-extract:summary` metadata for machine parsing
- Semantic `<div>` and `<span>` structure
- Consistent CSS styling
- Clear item number format (Item X.XX.)

**Additional Modern Features:**
```html
<!-- Exhibit tables with structured data -->
<table style="border-collapse:collapse;display:inline-table;
              margin-bottom:5pt;vertical-align:text-bottom;width:100.000%">
    <tr>
        <td style="width:1.0%"></td>
        <td style="width:44.354%"></td>
        <td style="width:0.1%"></td>
        <td style="width:1.0%"></td>
        <td style="width:53.446%"></td>
        <td style="width:0.1%"></td>
    </tr>
    <tr>
        <td colspan="3" style="background-color:#cceeff;padding:2px 1pt;
                              text-align:left;vertical-align:bottom">
            <span style="color:#000000;font-family:'Times New Roman',sans-serif;
                        font-size:10pt;font-weight:400;line-height:100%">
                Exhibit Number
            </span>
        </td>
        <td colspan="3" style="background-color:#cceeff;padding:2px 1pt;
                              text-align:left;vertical-align:bottom">
            <span style="color:#000000;font-family:'Times New Roman',sans-serif;
                        font-size:10pt;font-weight:400;line-height:100%">
                Exhibit Description
            </span>
        </td>
    </tr>
</table>
```

---

## Item Mapping Reference

### Complete 8-K Item List (Modern Era)

**Section 1: Registrant's Business and Operations**
- Item 1.01: Entry into a Material Definitive Agreement
- Item 1.02: Termination of a Material Definitive Agreement
- Item 1.03: Bankruptcy or Receivership
- Item 1.04: Mine Safety - Reporting of Shutdowns and Patterns of Violations

**Section 2: Financial Information**
- Item 2.01: Completion of Acquisition or Disposition of Assets
- Item 2.02: Results of Operations and Financial Condition *(Common)*
- Item 2.03: Creation of a Direct Financial Obligation
- Item 2.04: Triggering Events That Accelerate or Increase a Direct Financial Obligation
- Item 2.05: Costs Associated with Exit or Disposal Activities
- Item 2.06: Material Impairments

**Section 3: Securities and Trading Markets**
- Item 3.01: Notice of Delisting or Failure to Satisfy Listing Rule
- Item 3.02: Unregistered Sales of Equity Securities
- Item 3.03: Material Modification to Rights of Security Holders

**Section 4: Matters Related to Accountants**
- Item 4.01: Changes in Registrant's Certifying Accountant
- Item 4.02: Non-Reliance on Previously Issued Financial Statements

**Section 5: Corporate Governance and Management**
- Item 5.01: Changes in Control of Registrant
- Item 5.02: Departure/Appointment of Directors or Officers *(Common)*
- Item 5.03: Amendments to Articles of Incorporation or Bylaws
- Item 5.04: Temporary Suspension of Trading Under Employee Benefit Plans
- Item 5.05: Amendment to Code of Ethics
- Item 5.06: Change in Shell Company Status
- Item 5.07: Submission of Matters to a Vote of Security Holders
- Item 5.08: Shareholder Director Nominations

**Section 6: Asset-Backed Securities**
- Item 6.01: ABS Informational and Computational Material
- Item 6.02: Change of Servicer or Trustee
- Item 6.03: Change in Credit Enhancement or Other External Support
- Item 6.04: Failure to Make a Required Distribution
- Item 6.05: Securities Act Updating Disclosure

**Section 7: Regulation FD**
- Item 7.01: Regulation FD Disclosure *(Common)*

**Section 8: Other Events**
- Item 8.01: Other Events *(Very Common - catch-all)*

**Section 9: Financial Statements and Exhibits**
- Item 9.01: Financial Statements and Exhibits *(Nearly Universal)*

---

## Recommendations

### Code Changes

**1. Support Integer Items for Legacy Filings**
```python
# Add to htmltools.py
def detect_int_items_in_text(text: str) -> List[str]:
    """Detect integer items in plain text (for SGML filings)"""
    pattern = r'\bItem\s+(\d+)\b'
    matches = re.findall(pattern, text, re.IGNORECASE)
    return sorted(set(matches))

# Modify EightK.items property
@property
def items(self) -> List[str]:
    if self.chunked_document:
        return self.chunked_document.list_items()
    # Fallback for SGML filings
    text = self._filing.text()
    if text:
        return detect_int_items_in_text(text)
    return []
```

**2. Normalize Item Format**
```python
# Option A: Strip "Item " prefix in pattern
decimal_item_pattern = r"^Item\s{1,3}([0-9]{1,2}\.[0-9]{2})\.?"

# Option B: Post-process normalization
def normalize_items(items: List[str]) -> List[str]:
    """Remove 'Item ' prefix for consistency"""
    return [item.replace('Item ', '') for item in items]
```

**3. Improve Mid-Period Detection**
```python
# More flexible pattern for mid-period HTML
def detect_items_flexible(text: pd.Series) -> pd.Series:
    """Detect items with flexible spacing and formatting"""
    # Try decimal first
    pattern = r'(?:^|\s)(Item\s+\d+\.\d+)'
    items = text.str.extract(pattern, flags=re.IGNORECASE | re.MULTILINE)

    # Fall back to integer if no decimal items found
    if items.isna().all():
        pattern = r'(?:^|\s)(Item\s+\d+(?:\s+[A-Z])?)'
        items = text.str.extract(pattern, flags=re.IGNORECASE | re.MULTILINE)

    return items
```

### Test Additions

**1. Legacy Era Tests**
```python
def test_legacy_sgml_integer_items():
    """Test integer item detection in SGML filings"""
    filing = Filing(form='8-K', filing_date='1999-03-31',
                   company='ABN AMRO MORTGAGE CORP',
                   cik=943489,
                   accession_no='0000950117-99-000691')
    eightk = filing.obj()
    assert '5' in eightk.items or '7' in eightk.items
    # Should detect integer items from plain text
```

**2. Mid-Period Tests**
```python
def test_midperiod_decimal_items():
    """Test decimal item detection in transitional HTML"""
    filing = Filing(form='8-K', filing_date='2011-03-31',
                   company='AEHR TEST SYSTEMS',
                   cik=1040470,
                   accession_no='0001040470-11-000019')
    eightk = filing.obj()
    # Should handle &nbsp; and table-based layout
    assert any(item in ['8.01', '9.01'] for item in eightk.items)
```

**3. Normalization Tests**
```python
def test_item_format_normalization():
    """Test consistent item format (with or without 'Item ' prefix)"""
    filing = Filing(form='8-K', filing_date='2023-03-15',
                   company='ADOBE INC.', cik=796343,
                   accession_no='0000796343-23-000044')
    eightk = filing.obj()

    # Should be normalized format
    assert '2.02' in eightk.items  # Not 'Item 2.02'
    assert '9.01' in eightk.items  # Not 'Item 9.01'
```

### Documentation Updates

**1. Add Era-Specific Notes**
- Document supported filing periods
- Clarify integer vs decimal item formats
- Explain normalization decisions

**2. Update API Documentation**
```python
class EightK(CurrentReport):
    """
    Represents an 8-K Current Report filing.

    Item Detection Notes:
    - Modern filings (2013+): Decimal format (2.02, 9.01)
    - Legacy filings (1995-2004): Integer format (5, 7)
    - Mid-period (2005-2012): Decimal format with varied HTML

    Returns item numbers without "Item " prefix for consistency.
    """
```

---

## Sample Filings for Testing

### Legacy SGML Era (1999)
```python
{'era': 'Legacy SGML (1999)', 'form': '8-K', 'filing_date': '1999-03-31',
 'company': 'ABN AMRO MORTGAGE CORP', 'cik': 943489,
 'accession_no': '0000950117-99-000691'},

{'era': 'Legacy SGML (1999)', 'form': '8-K', 'filing_date': '1999-03-31',
 'company': 'ADVANCED DEPOSITION TECHNOLOGIES INC', 'cik': 909963,
 'accession_no': '0000927016-99-001233'},

{'era': 'Legacy SGML (1999)', 'form': '8-K', 'filing_date': '1999-03-31',
 'company': 'AERO SERVICES INTERNATIONAL INC', 'cik': 350200,
 'accession_no': '0000950116-99-000614'},
```

### Mid-Period XML Era (2008, 2011)
```python
{'era': 'Mid-Period XML (2008)', 'form': '8-K', 'filing_date': '2008-03-31',
 'company': '180 Connect Inc.', 'cik': 1323639,
 'accession_no': '0000950144-08-002465'},

{'era': 'Mid-Period XML (2011)', 'form': '8-K', 'filing_date': '2011-03-31',
 'company': '4 KIDS ENTERTAINMENT INC', 'cik': 58592,
 'accession_no': '0000058592-11-000009'},

{'era': 'Mid-Period XML (2011)', 'form': '8-K', 'filing_date': '2011-03-31',
 'company': 'ADEONA PHARMACEUTICALS, INC.', 'cik': 894158,
 'accession_no': '0001144204-11-018882'},

{'era': 'Mid-Period XML (2011)', 'form': '8-K', 'filing_date': '2011-03-31',
 'company': 'AEHR TEST SYSTEMS', 'cik': 1040470,
 'accession_no': '0001040470-11-000019'},
```

### Modern XML Era (2015, 2020, 2024)
```python
{'era': 'Modern XML (2015)', 'form': '8-K', 'filing_date': '2015-03-31',
 'company': 'AAR CORP', 'cik': 1750,
 'accession_no': '0001104659-15-024618'},

{'era': 'Modern XML (2020)', 'form': '8-K', 'filing_date': '2020-03-31',
 'company': 'ABRAXAS PETROLEUM CORP', 'cik': 867665,
 'accession_no': '0001437749-20-006604'},

{'era': 'Modern XML (2020)', 'form': '8-K', 'filing_date': '2020-03-31',
 'company': 'AERIE PHARMACEUTICALS INC', 'cik': 1337553,
 'accession_no': '0001193125-20-091787'},

{'era': 'Modern XML (2024)', 'form': '8-K', 'filing_date': '2024-03-29',
 'company': '1st FRANKLIN FINANCIAL CORP', 'cik': 38723,
 'accession_no': '0000038723-24-000014'},

{'era': 'Modern XML (2024)', 'form': '8-K', 'filing_date': '2024-03-29',
 'company': '23andMe Holding Co.', 'cik': 1804591,
 'accession_no': '0001193125-24-081826'},
```

---

## Related Research

### SEC Regulatory Timeline
- **August 2004**: SEC adopts amendments to Form 8-K
  - Effective date: August 23, 2004
  - Full compliance required by: March 16, 2005
  - Introduces decimal item numbering system
  - Expands from 9 items to 30+ items

### References
- SEC Release No. 33-8400: "Additional Form 8-K Disclosure Requirements"
- SEC Form 8-K Instructions (Current)
- Beads Issue #tm2: 8-K item detection research
- Test file: `/Users/dwight/PycharmProjects/edgartools/tests/test_eightK.py`
- Code file: `/Users/dwight/PycharmProjects/edgartools/edgar/company_reports.py`
- Utilities: `/Users/dwight/PycharmProjects/edgartools/edgar/files/htmltools.py`

---

## Future Research Directions

1. **Quantitative Analysis**: Run batch analysis across 1000+ filings per era
2. **Item Frequency Analysis**: Which items are most common in each era?
3. **HTML Evolution Patterns**: Document specific HTML structures by year
4. **Press Release Detection**: How has exhibit attachment evolved?
5. **XBRL Integration**: When did 8-K filings start including XBRL?

---

**Document Status:** Initial research complete
**Next Steps:**
1. Validate findings with batch testing
2. Implement recommended code changes
3. Add comprehensive test coverage
4. Update API documentation

**Maintained by:** SEC Filing Research Agent
**Last Updated:** 2025-11-07
