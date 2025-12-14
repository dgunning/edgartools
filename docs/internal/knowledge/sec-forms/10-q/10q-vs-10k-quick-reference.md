# 10-Q vs 10-K Quick Reference Guide

*Research Date: 2025-10-10*

## Purpose

Quick lookup table for understanding structural and content differences between Forms 10-Q and 10-K.

## High-Level Comparison

| Aspect | Form 10-Q | Form 10-K |
|--------|-----------|-----------|
| **Filing Type** | Quarterly Report | Annual Report |
| **Filing Frequency** | 3x per year (Q1, Q2, Q3) | 1x per year (fiscal year-end) |
| **Audit Status** | Reviewed (not audited) | Audited |
| **Number of Parts** | 2 Parts | 4 Parts |
| **Total Items** | 11 Items | 25+ Items |
| **Typical Length** | 30-80 pages | 100-300 pages |
| **Level of Detail** | Summary, interim | Comprehensive, annual |

## Part Structure Comparison

### 10-Q Structure (2 Parts)

```
Part I - Financial Information
Part II - Other Information
```

### 10-K Structure (4 Parts)

```
Part I - Business & Risk Information
Part II - Financial Information
Part III - Directors, Officers, Governance
Part IV - Exhibits & Schedules
```

**Key Difference**: 10-Q has only 2 parts vs 10-K's 4 parts. The focus and content of same-named parts differs.

## Item-by-Item Mapping

### Finding Same Content Across Forms

| Content Type | 10-Q Location | 10-K Location | Notes |
|--------------|---------------|---------------|-------|
| **Financial Statements** | Part I, Item 1 | Part II, Item 8 | 10-Q: Unaudited<br>10-K: Audited |
| **MD&A** | Part I, Item 2 | Part II, Item 7 | 10-Q: Quarterly<br>10-K: Annual |
| **Market Risk** | Part I, Item 3 | Part II, Item 7A | Same content, different item # |
| **Controls & Procedures** | Part I, Item 4 | Part II, Item 9A | 10-K more comprehensive |
| **Legal Proceedings** | Part II, Item 1 | Part I, Item 3 | Different Part AND Item # |
| **Risk Factors** | Part II, Item 1A | Part I, Item 1A | 10-Q: Changes only<br>10-K: Complete |
| **Exhibits** | Part II, Item 6 | Part IV, Item 15 | Different Part AND Item # |

**Critical Insight**: Same content appears in completely different Part/Item locations. Parsing logic must be form-aware.

## Detailed Item Structure

### Form 10-Q Items (11 Total)

#### Part I - Financial Information (4 items)
| Item | Title | Required? |
|------|-------|-----------|
| 1 | Financial Statements | Yes |
| 2 | Management's Discussion and Analysis | Yes |
| 3 | Quantitative and Qualitative Disclosures About Market Risk | Yes* |
| 4 | Controls and Procedures | Yes |

*Item 3 may be omitted by smaller reporting companies

#### Part II - Other Information (7 items)
| Item | Title | Required? |
|------|-------|-----------|
| 1 | Legal Proceedings | If applicable |
| 1A | Risk Factors | If material changes |
| 2 | Unregistered Sales of Equity Securities | If applicable |
| 3 | Defaults Upon Senior Securities | If applicable |
| 4 | Mine Safety Disclosures | If applicable |
| 5 | Other Information | If applicable |
| 6 | Exhibits | Yes |

### Form 10-K Items (25+ Total)

#### Part I - Business & Risk (8 items)
| Item | Title |
|------|-------|
| 1 | Business |
| 1A | Risk Factors |
| 1B | Unresolved Staff Comments |
| 1C | Cybersecurity |
| 2 | Properties |
| 3 | Legal Proceedings |
| 4 | Mine Safety Disclosures |
| 5 | (Reserved) |

#### Part II - Financial Information (9 items)
| Item | Title |
|------|-------|
| 5 | Market for Registrant's Common Equity |
| 6 | [Reserved] |
| 7 | Management's Discussion and Analysis |
| 7A | Quantitative and Qualitative Disclosures About Market Risk |
| 8 | Financial Statements and Supplementary Data |
| 9 | Changes in and Disagreements with Accountants |
| 9A | Controls and Procedures |
| 9B | Other Information |
| 9C | Disclosure Regarding Foreign Jurisdictions |

#### Part III - Governance (5 items)
| Item | Title |
|------|-------|
| 10 | Directors, Executive Officers and Corporate Governance |
| 11 | Executive Compensation |
| 12 | Security Ownership of Certain Beneficial Owners |
| 13 | Certain Relationships and Related Transactions |
| 14 | Principal Accountant Fees and Services |

#### Part IV - Exhibits (2 items)
| Item | Title |
|------|-------|
| 15 | Exhibits and Financial Statement Schedules |
| 16 | Form 10-K Summary |

## Item Number Reuse

### "Item 1" Appears 3 Times Across Forms

| Location | Content in 10-Q | Content in 10-K |
|----------|-----------------|-----------------|
| **Part I, Item 1** | Financial Statements | Business |
| **Part II, Item 1** | Legal Proceedings | (N/A - no Part II Item 1 in 10-K) |
| **10-K Part I, Item 1** | (N/A) | Business |

### "Item 2" Appears Multiple Times

| Location | Content in 10-Q | Content in 10-K |
|----------|-----------------|-----------------|
| **Part I, Item 2** | MD&A | Properties |
| **Part II, Item 2** | Unregistered Sales of Equity | (N/A) |

**Parser Requirement**: Must track both Form type AND Part context to correctly identify content.

## Letter Suffixes (Items with A, B, C)

### 10-Q Letter Suffixes
- **Part II, Item 1A**: Risk Factors
- **No other letter suffixes in standard 10-Q**

### 10-K Letter Suffixes
- **Part I, Item 1A**: Risk Factors
- **Part I, Item 1B**: Unresolved Staff Comments
- **Part I, Item 1C**: Cybersecurity
- **Part II, Item 7A**: Market Risk Disclosures
- **Part II, Item 9A**: Controls and Procedures
- **Part II, Item 9B**: Other Information
- **Part II, Item 9C**: Foreign Jurisdictions Disclosure

**Observation**: 10-K has significantly more letter suffixes (7 items) vs 10-Q (1 item).

## Content Unique to Each Form

### Only in 10-Q
- Part II, Item 2: Unregistered Sales of Equity Securities
- Part II, Item 3: Defaults Upon Senior Securities
- Part II, Item 5: Other Information (8-K catchup)

### Only in 10-K
- Part I, Item 1: Business (comprehensive business description)
- Part I, Item 1B: Unresolved Staff Comments
- Part I, Item 1C: Cybersecurity
- Part I, Item 2: Properties
- Part II, Item 5: Market for Common Equity
- Part II, Item 9: Changes in Accountants
- Part II, Item 9C: Foreign Jurisdictions
- **Entire Part III**: Corporate Governance
- **Entire Part IV**: Exhibits and Schedules (more comprehensive)

## Parsing Strategy Implications

### Form Detection Required

```python
if form_type == "10-Q":
    structure = FORM_10Q_STRUCTURE  # 2 Parts, 11 Items
elif form_type == "10-K":
    structure = FORM_10K_STRUCTURE  # 4 Parts, 25+ Items
else:
    raise ValueError(f"Unknown form type: {form_type}")
```

### Content Mapping Example

```python
# To find MD&A content:
def get_mda_location(form_type):
    if form_type == "10-Q":
        return ("Part I", "Item 2")
    elif form_type == "10-K":
        return ("Part II", "Item 7")

# To find Financial Statements:
def get_financials_location(form_type):
    if form_type == "10-Q":
        return ("Part I", "Item 1")
    elif form_type == "10-K":
        return ("Part II", "Item 8")
```

### Context Tracking

```python
def parse_section(html, form_type):
    current_part = None
    current_item = None

    # Must track both Part and Item to identify content
    for section in sections:
        if is_part_header(section):
            current_part = extract_part_number(section)
        elif is_item_header(section):
            current_item = extract_item_number(section)
            # Use (form_type, current_part, current_item) as key
            content_type = CONTENT_MAP[form_type][current_part][current_item]
```

## Filing Timeline

| Quarter | 10-Q Due Date | 10-K Due Date |
|---------|---------------|---------------|
| **Q1** | 40-45 days after Q1 end | N/A |
| **Q2** | 40-45 days after Q2 end | N/A |
| **Q3** | 40-45 days after Q3 end | N/A |
| **Q4** | N/A | 60-90 days after fiscal year end |

**Note**: Q4 financial information is included in the annual 10-K rather than a separate 10-Q.

## Use Cases

### When to Use 10-Q vs 10-K

**Use 10-Q when you need**:
- Recent quarterly performance (more timely than 10-K)
- Interim financial statements
- Quarterly MD&A analysis
- Recent risk factor changes

**Use 10-K when you need**:
- Comprehensive annual overview
- Full business description
- Complete governance information
- Audited financial statements
- Full year performance

**Use Both when you need**:
- Complete year-to-date view (latest 10-K + subsequent 10-Qs)
- Trend analysis across quarters
- Tracking of risk factor evolution

## Summary Table

| Feature | 10-Q | 10-K |
|---------|------|------|
| Parts | 2 | 4 |
| Items | 11 | 25+ |
| Part I Focus | Financials | Business/Risk |
| Part II Focus | Other Info | Financials |
| Part III | N/A | Governance |
| Part IV | N/A | Exhibits |
| Letter Suffixes | 1 (Item 1A) | 7 (Items 1A-1C, 7A, 9A-9C) |
| Financial Statements Location | Part I, Item 1 | Part II, Item 8 |
| MD&A Location | Part I, Item 2 | Part II, Item 7 |
| Exhibits Location | Part II, Item 6 | Part IV, Item 15 |
| Business Description | None | Part I, Item 1 |
| Audit Status | Reviewed | Audited |
| Filing Frequency | Quarterly (×3) | Annual (×1) |

---

*Created: 2025-10-10*
*Purpose: Quick reference for form structure differences*
*See: [10-Q Official Structure Guide](./10q-official-structure-guide.md) for detailed analysis*
