# EightK Data Object Guide

Form 8-K is a "current report" that public companies file with the SEC to announce major events that shareholders should know about. This guide details all data available from the `EightK` class for building views.

---

## Overview

| Property | Type | Description |
|----------|------|-------------|
| Class Name | `EightK` (alias for `CurrentReport`) | |
| Forms Handled | `8-K`, `8-K/A`, `6-K`, `6-K/A` | |
| Module | `edgar.company_reports` | |
| Source Data | HTML document + XML exhibits | |

---

## Basic Metadata

Inherited from `CompanyReport` base class:

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `company` | `str` | Company name | `"ADOBE INC."` |
| `form` | `str` | Form type | `"8-K"` or `"8-K/A"` |
| `filing_date` | `str` | Date filed with SEC | `"2023-03-15"` |
| `period_of_report` | `str` | Event date (YYYY-MM-DD) | `"2023-03-14"` |
| `date_of_report` | `str` | Formatted event date | `"March 14, 2023"` |

---

## Items (Core 8-K Structure)

8-K filings are organized by numbered items. Each item type indicates a specific category of material event.

### Getting Items

```python
eightk = filing.obj()

# List all items reported in this filing
eightk.items  # Returns: ['Item 2.02', 'Item 9.01']

# Get content for a specific item
content = eightk['Item 2.02']  # Returns item text as string
```

### Item Access Methods

| Method | Input Formats | Returns |
|--------|---------------|---------|
| `eightk.items` | N/A | `List[str]` - e.g., `['Item 2.02', 'Item 9.01']` |
| `eightk[item]` | `'Item 5.02'`, `'5.02'`, `'item_502'` | `str` - item content or `None` |
| `eightk.sections` | N/A | `dict` - section key to Section object |

### Complete Item Reference

**Section 1 - Registrant's Business and Operations**

| Item | Title | Description |
|------|-------|-------------|
| **1.01** | Entry into a Material Definitive Agreement | New contracts, acquisitions, partnerships not in ordinary course |
| **1.02** | Termination of a Material Definitive Agreement | End of significant contracts or agreements |
| **1.03** | Bankruptcy or Receivership | Company enters bankruptcy or receivership |
| **1.04** | Mine Safety - Reporting of Shutdowns and Patterns of Violations | Mining companies only |

**Section 2 - Financial Information**

| Item | Title | Description |
|------|-------|-------------|
| **2.01** | Completion of Acquisition or Disposition of Assets | Completed M&A transactions |
| **2.02** | Results of Operations and Financial Condition | Earnings releases, preliminary results |
| **2.03** | Creation of a Direct Financial Obligation | New debt, credit facilities |
| **2.04** | Triggering Events That Accelerate Financial Obligations | Covenant violations, acceleration events |
| **2.05** | Costs Associated with Exit or Disposal Activities | Restructuring charges, plant closures |
| **2.06** | Material Impairments | Asset writedowns, goodwill impairment |

**Section 3 - Securities and Trading Markets**

| Item | Title | Description |
|------|-------|-------------|
| **3.01** | Notice of Delisting or Failure to Satisfy Listing Rules | Exchange compliance issues |
| **3.02** | Unregistered Sales of Equity Securities | Private placements, warrant exercises |
| **3.03** | Material Modification to Rights of Security Holders | Charter/bylaw changes affecting shareholders |

**Section 4 - Matters Related to Accountants and Financial Statements**

| Item | Title | Description |
|------|-------|-------------|
| **4.01** | Changes in Registrant's Certifying Accountant | Auditor change |
| **4.02** | Non-Reliance on Previously Issued Financial Statements | Restatement announcement |

**Section 5 - Corporate Governance and Management**

| Item | Title | Description |
|------|-------|-------------|
| **5.01** | Changes in Control of Registrant | Ownership/control change |
| **5.02** | Departure/Election of Directors; Appointment of Officers | Executive and board changes |
| **5.03** | Amendments to Articles of Incorporation or Bylaws | Governance document changes |
| **5.04** | Temporary Suspension of Trading Under Employee Benefit Plans | 401(k) blackout periods |
| **5.05** | Amendment or Waiver of Code of Ethics | Ethics policy changes |
| **5.06** | Change in Shell Company Status | Shell company status update |
| **5.07** | Submission of Matters to a Vote of Security Holders | Shareholder meeting results |
| **5.08** | Shareholder Director Nominations | Proxy access nominations |

**Section 6 - Asset-Backed Securities**

| Item | Title | Description |
|------|-------|-------------|
| **6.01** | ABS Informational and Computational Material | ABS deal information |
| **6.02** | Change of Servicer or Trustee | ABS servicer changes |
| **6.03** | Change in Credit Enhancement or External Support | ABS credit support changes |
| **6.04** | Failure to Make a Required Distribution | ABS payment failures |
| **6.05** | Securities Act Updating Disclosure | ABS disclosure updates |

**Section 7 - Regulation FD**

| Item | Title | Description |
|------|-------|-------------|
| **7.01** | Regulation FD Disclosure | Material non-public information disclosure |

**Section 8 - Other Events**

| Item | Title | Description |
|------|-------|-------------|
| **8.01** | Other Events | Voluntary disclosure of any material event |

**Section 9 - Financial Statements and Exhibits**

| Item | Title | Description |
|------|-------|-------------|
| **9.01** | Financial Statements and Exhibits | List of attached documents |

---

## Press Releases

8-K filings often include press releases as exhibits (typically EX-99.1).

### Accessing Press Releases

```python
eightk = filing.obj()

# Check if press releases exist
if eightk.has_press_release:
    press_releases = eightk.press_releases  # PressReleases object

    # Iterate through press releases
    for i in range(len(press_releases)):
        pr = press_releases[i]  # PressRelease object
```

### PressReleases Collection

| Property/Method | Type | Description |
|-----------------|------|-------------|
| `len(press_releases)` | `int` | Number of press releases |
| `press_releases[i]` | `PressRelease` | Get press release by index |

### PressRelease Object

| Property/Method | Type | Description |
|-----------------|------|-------------|
| `document` | `str` | Filename (e.g., `"pressrelease3-8x24.htm"`) |
| `description` | `str` | SEC description (e.g., `"PRESS RELEASE DATED JANUARY 16, 2024"`) |
| `url()` | `str` | Full SEC URL to document |
| `html()` | `str` | Raw HTML content |
| `text()` | `str` | Extracted plain text |
| `to_markdown()` | `MarkdownContent` | Markdown formatted content |
| `open()` | N/A | Opens in browser |

---

## Exhibits

All attached documents including financial statements, agreements, and other materials.

### Accessing Exhibits

```python
# Via the underlying filing
exhibits = filing.exhibits  # Attachments object filtered to exhibits

# Iterate
for exhibit in filing.exhibits:
    print(exhibit.document_type, exhibit.description)
```

### Exhibit Object (Attachment)

| Property | Type | Description |
|----------|------|-------------|
| `sequence_number` | `str` | Order in filing (e.g., `"1"`, `"2"`) |
| `document` | `str` | Filename (e.g., `"ex10-1.htm"`) |
| `document_type` | `str` | SEC type (e.g., `"EX-10.1"`, `"EX-99.1"`) |
| `description` | `str` | Description text |
| `size` | `int` | File size in bytes |
| `url` | `str` | Full SEC URL |
| `ixbrl` | `bool` | Whether inline XBRL |
| `extension` | `str` | File extension (e.g., `".htm"`) |

### Exhibit Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `download()` | `str` or `bytes` | Download content |
| `download(path)` | `str` | Save to path, return filepath |
| `text()` | `str` | Extracted text content |
| `markdown()` | `str` | Markdown conversion (HTML only) |
| `is_html()` | `bool` | Check if HTML file |
| `is_binary()` | `bool` | Check if binary (PDF, image) |
| `is_text()` | `bool` | Check if text file |
| `open()` | N/A | Open in browser |

### Common Exhibit Types

| Type | Description |
|------|-------------|
| `EX-10.1`, `EX-10.2`, etc. | Material contracts |
| `EX-99.1` | Press releases (primary) |
| `EX-99.2`, `EX-99.3` | Additional press releases or presentations |
| `EX-101.*` | XBRL taxonomy files |
| `GRAPHIC` | Images, logos |

---

## Document Sections

The parsed document structure with detected sections.

### Accessing Sections

```python
eightk = filing.obj()

# Get sections dictionary
sections = eightk.sections  # dict[str, Section]

# Section keys are normalized: 'item_502' for Item 5.02
for key, section in sections.items():
    print(f"{key}: {section.text()[:100]}...")
```

### Section Object

| Property/Method | Type | Description |
|-----------------|------|-------------|
| `text()` | `str` | Full section text |
| Key format | `str` | `'item_502'` for Item 5.02 |

---

## Text and Display

### Text Extraction

```python
eightk = filing.obj()

# Full text of all exhibits
full_text = eightk.text()  # Includes all exhibit content
```

### Display Methods

| Method | Description |
|--------|-------------|
| `repr(eightk)` | Rich formatted display with exhibit table + content |
| `str(eightk)` | Simple string: `"ADOBE INC. 8-K March 14, 2023"` |
| `eightk.view(item)` | Print specific item content |

---

## Financial Data (If Available)

Some 8-K filings include XBRL financial data (rare but possible).

| Property | Type | Description |
|----------|------|-------------|
| `financials` | `Financials` or `None` | XBRL financial extractor |
| `income_statement` | `Statement` or `None` | Income statement if available |
| `balance_sheet` | `Statement` or `None` | Balance sheet if available |
| `cash_flow_statement` | `Statement` or `None` | Cash flow if available |

---

## View Design Recommendations

### Primary View Components

1. **Header Section**
   - Company name
   - Form type (8-K or 8-K/A for amendment)
   - Filing date
   - Date of report (event date)

2. **Items Summary**
   - List of items with titles
   - Visual indicators for item categories (financial, governance, etc.)
   - Click to expand item content

3. **Press Release Panel** (if `has_press_release`)
   - Highlighted press release content
   - Option to view raw HTML or markdown

4. **Exhibits Table**
   - Document type, filename, description
   - Download links
   - Preview for text/HTML exhibits

5. **Item Content Panels**
   - Expandable/collapsible per item
   - Formatted text content

### Data Priority for Display

| Priority | Data | Reason |
|----------|------|--------|
| High | Items list + content | Core 8-K information |
| High | Press releases | Most readable, newsworthy content |
| Medium | Exhibits table | Supporting documents |
| Medium | Event date vs filing date | Timing context |
| Low | XBRL/financials | Rarely present in 8-K |

### Item Category Colors (Suggested)

| Category | Items | Suggested Color |
|----------|-------|-----------------|
| Financial | 2.01-2.06 | Green |
| Governance | 5.01-5.08 | Blue |
| Accountant | 4.01-4.02 | Orange |
| Securities | 3.01-3.03 | Purple |
| Disclosure | 7.01, 8.01 | Gray |
| Exhibits | 9.01 | Light gray |

---

## Example Data Structure

```python
{
    "company": "ADOBE INC.",
    "form": "8-K",
    "filing_date": "2023-03-15",
    "date_of_report": "March 14, 2023",
    "period_of_report": "2023-03-14",

    "items": [
        {
            "number": "2.02",
            "title": "Results of Operations and Financial Condition",
            "content": "On March 14, 2023, Adobe Inc. issued..."
        },
        {
            "number": "9.01",
            "title": "Financial Statements and Exhibits",
            "content": "Exhibit 99.1 - Press Release..."
        }
    ],

    "has_press_release": True,
    "press_releases": [
        {
            "document": "pressrelease.htm",
            "description": "Press Release dated March 14, 2023",
            "text": "Adobe Reports Record Q1 Revenue..."
        }
    ],

    "exhibits": [
        {
            "sequence": "1",
            "type": "8-K",
            "document": "adbe-20230314.htm",
            "description": "8-K Filing"
        },
        {
            "sequence": "2",
            "type": "EX-99.1",
            "document": "pressrelease.htm",
            "description": "Press Release"
        }
    ]
}
```
