# Form C File Number Discovery - Critical Implementation Detail

## The Problem

When implementing campaign lifecycle tracking for crowdfunding filings (Form C variants), we discovered that there are **TWO different file numbers** associated with each filing:

1. **Issuer's SEC File Number** (e.g., `'020-36531'`)
2. **Portal's Commission File Number** (e.g., `'007-00033'`)

This distinction is critical because using the wrong file number will fail to link related filings in a campaign lifecycle.

---

## File Number Types Explained

### 1. Issuer's SEC File Number (Offering Identifier)

**Access**: `filing.file_number` (EntityFiling only)
**Example**: `'020-36002'` (ViiT Health 2025 offering)

- **Unique to each offering** (not just each company)
- Assigned by SEC when the offering is filed
- Multiple offerings by same company have different issuer file numbers
- **CRITICAL for offering tracking** - links all related filings (C, C/A, C-U, C-AR, C-TR)
- This is what `filing.related_filings()` uses to find amendments and updates

### 2. Portal's Commission File Number

**Access**: `filing.obj().campaign_file_number` (requires parsing FormC)
**Example**: `'007-00033'`

- **Unique to each funding portal**
- The portal's SEC commission file number
- Appears in all filings for a specific campaign
- **Required for campaign lifecycle tracking**

---

## Real-World Examples

### Example 1: Multiple Offerings by Same Company (ViiT Health)

ViiT Health has filed **3 separate offerings**, each with a unique issuer file number:

| Offering | Filing Date | Issuer File # | Portal File # | Portal | Related Filings |
|----------|-------------|---------------|---------------|--------|-----------------|
| 2021 offering | 2021-10-08 | `020-28927` | `007-00033` | Wefunder | 1 C only |
| 2023 offering | 2023-06-07 | `020-32444` | `007-00033` | Wefunder | 1 C + 2 C/A |
| 2025 offering | 2025-06-11 | `020-36002` | `007-00033` | Wefunder | 1 C + 3 C/A |

**Key Insight**:
- All three offerings use Wefunder (same portal file # `007-00033`)
- Each offering has its own issuer file number (020-XXXXX)
- `filing.related_filings()` correctly groups by issuer file number
- `filing[3].related_filings()` returns 4 filings for 2025 offering only
- `filing[7].related_filings()` returns 3 filings for 2023 offering only

### Example 2: Multiple Companies Through Same Portal

Different companies using StartEngine portal:

| Company | Issuer File # | Portal File # | Portal |
|---------|---------------|---------------|--------|
| Acuitive Technologies | `020-36427` | `008-70060` | StartEngine |
| Epilog Imaging | `020-35641` | `008-70060` | StartEngine |

**Key Insight**: Same portal file number, but different offerings (different issuer file numbers).

---

## Why This Matters for Offering Tracking

### ✅ Correct Approach: Using Issuer File Number (Single Offering)

```python
# Method 1: Use built-in related_filings() (recommended)
related = filing.related_filings()
# Result: All filings for THIS offering only (C + C/A + C-U + C-AR + C-TR)

# Method 2: Use Campaign class (recommended)
campaign = filing.get_campaign()
related = campaign.all_filings
# Result: Same - all filings for THIS offering only

# Method 3: Manual query with issuer file number
issuer_file_number = filing.as_company_filing().file_number  # '020-36002'
related = company.get_filings(file_number=issuer_file_number)
# Result: All filings for THIS offering only
```

**Why it works**: The issuer file number (020-XXXXX) appears in **all** Form C filings for a specific offering:
- Initial offering (Form C)
- Amendments (Form C/A)
- Progress updates (Form C-U, C-U/A)
- Annual reports (Form C-AR, C-AR/A)
- Termination (Form C-TR)

**Verified**: ViiT Health's `filing[3].related_filings()` returns 4 filings for 2025 offering (020-36002), not the 8 filings across all offerings.

### ⚠️ Different Use Case: Portal-Level Analysis (All Offerings)

```python
# Get ALL offerings through a portal (not just one offering)
formc = filing.obj()
portal_file_number = formc.portal_file_number  # '007-00033'

# Search across ALL offerings using this portal
all_portal_filings = []
for f in company.get_filings(form=['C', 'C/A', 'C-U', 'C-AR', 'C-TR']):
    fc = f.obj()
    if fc.portal_file_number == portal_file_number:
        all_portal_filings.append(f)
# Result: ALL offerings through Wefunder (2021 + 2023 + 2025 for ViiT Health)
```

**Use case**: Portal analysis, not single offering tracking.

---

## Implementation Requirements

### In Campaign Class

The Campaign class correctly uses the **issuer file number** for single offering tracking:

```python
def __init__(self, filing_or_file_number: Union[Filing, str], cik: Optional[str] = None):
    """
    Initialize with early conversion and caching for performance.

    Uses ISSUER file number (020-XXXXX) to track ONE specific offering.
    """
    if isinstance(filing_or_file_number, Filing):
        # Do expensive operations once
        self._entity_filing = filing_or_file_number.as_company_filing()
        self._formc = filing_or_file_number.obj()

        # Extract BOTH file numbers
        self._issuer_file_number = self._entity_filing.file_number  # 020-XXXXX (offering ID)
        self._portal_file_number = self._formc.portal_file_number  # 007-XXXXX (portal ID)

        # Use issuer file number as primary identifier
        self._file_number = self._issuer_file_number

@cached_property
def all_filings(self) -> List[Filing]:
    """
    Get all filings for THIS offering using issuer file number.
    Direct query - no parsing loop needed!
    """
    filings = self.company.get_filings(
        file_number=self._issuer_file_number,  # 020-XXXXX
        sort_by=[("filing_date", "ascending")]
    )
    return list(filings) if filings else []
```

---

## Where Each File Number Comes From

### Issuer's SEC File Number

**XML Location**: Assigned by SEC at filing time, stored in submissions data

**Access**:
```python
entity_filing = filing.as_company_filing()
issuer_file_num = entity_filing.file_number
```

**Availability**:
- ✅ Available in EntityFiling
- ❌ NOT available in base Filing
- ❌ NOT stored in FormC object

### Portal's Commission File Number

**XML Location**: Inside the Form C XML structure
```xml
<issuerInformation>
  <companyName>Wefunder Portal LLC</companyName>
  <commissionCik>0001661779</commissionCik>
  <commissionFileNumber>007-00033</commissionFileNumber>
  <crdNumber>283503</crdNumber>
</issuerInformation>
```

**Access**:
```python
formc = filing.obj()
portal_file_num = formc.portal_file_number  # Extracts from XML
```

**Availability**:
- ✅ Available in Form C, C/A, C-U, C-U/A (has funding_portal)
- ❌ NOT available in Form C-AR, C-AR/A, C-TR (no funding_portal section)

### Special Case: C-AR Forms

Annual reports (Form C-AR) **don't include** the funding portal information in their XML. This means:

```python
formc_ar = c_ar_filing.obj()
formc_ar.portal_file_number  # Returns None!
```

**Workaround**: For C-AR forms, you must:
1. Find the initial Form C for that campaign
2. Extract the portal file number from the initial filing
3. Use that to search for related C-AR filings

---

## Testing the Discovery

To verify this works correctly:

```python
from edgar import get_filings

# Get Q4 2025 Form C filings
filings = get_filings(form='C', filing_date='2025-10-01:2025-12-31')

# Check different file numbers
for filing in list(filings)[:3]:
    entity_filing = filing.as_company_filing()
    formc = filing.obj()

    print(f"Company: {filing.company}")
    print(f"  Issuer file #:   {entity_filing.file_number}")
    print(f"  Campaign file #: {formc.campaign_file_number}")
    print(f"  Portal: {formc.issuer_information.funding_portal.name}")
    print()
```

**Expected Output**:
```
Company: Better Apparel LLC
  Issuer file #:   020-36531 (offering identifier)
  Portal file #:   007-00033 (Wefunder)

Company: Acuitive Technologies, Inc.
  Issuer file #:   020-36427 (offering identifier)
  Portal file #:   008-70060 (StartEngine)

Company: Carbon Country LLC
  Issuer file #:   020-36295 (offering identifier)
  Portal file #:   007-00223 (Vicinity)
```

---

## Impact on Campaign Class

The Campaign class **CORRECTED IMPLEMENTATION**:

1. ✅ Extract **issuer file number** via `filing.as_company_filing().file_number`
2. ✅ Extract **portal file number** via `filing.obj().campaign_file_number`
3. ✅ Use **issuer file number** as primary identifier for single offering tracking
4. ✅ Cache both file numbers and parsed FormC at initialization (performance optimization)
5. ✅ Use direct query `company.get_filings(file_number=issuer_file_number)` instead of parsing loop
6. ✅ Provide both file numbers as properties for analysis

**Key Implementation Detail**: The Campaign class uses the **issuer file number (020-XXXXX)** to track a **single offering**, not the portal file number. The portal file number is tracked for reference but not used as the primary identifier.

---

## Verified Test Results

### Test Case 1: ViiT Health 2025 Offering
```python
from edgar import Company

company = Company('0001656159')  # ViiT Health
filing = company.get_filings(form='C', filing_date='2025-06-11')[0]
campaign = filing.get_campaign()

print(f"Issuer file#: {campaign.issuer_file_number}")
# Output: 020-36002

print(f"Portal file#: {campaign.portal_file_number}")
# Output: 007-00033

print(f"Filings count: {len(campaign.all_filings)}")
# Output: 4 (only 2025 offering: 1 C + 3 C/A)
```

### Test Case 2: Carrick Rangers 2024 Offering
```python
from edgar import get_filings

filings = get_filings(2024, 4, form='C')
filing = list(filings)[0]  # Carrick Rangers Global
campaign = filing.get_campaign()

print(f"Issuer file#: {campaign.issuer_file_number}")
# Output: 020-35355

print(f"Portal file#: {campaign.portal_file_number}")
# Output: 007-00033 (same portal as ViiT Health)

print(f"Filings count: {len(campaign.all_filings)}")
# Output: 2 (only this offering: 1 C + 1 C/A)
```

**Key Observation**: Both ViiT Health and Carrick Rangers use Wefunder (portal file# 007-00033), but Campaign correctly isolates each company's specific offering using the issuer file number.

---

## Attribute Naming Correction

### The `campaign_file_number` Problem

The FormC property `campaign_file_number` was originally named based on the assumption that it identified a "campaign". However, through empirical testing, we discovered:

1. **What it actually returns**: The portal's commission file number (007-XXXXX)
2. **What it should identify**: A single offering (requires issuer file number 020-XXXXX)
3. **Why the name is misleading**: Multiple offerings share the same portal file number

### The Fix

**Property renamed** (EdgarTools 4.26+):
```python
formc.portal_file_number  # ✅ Clear, accurate name
```

The old `campaign_file_number` property has been **removed** to avoid confusion.

### Migration Guide

**Correct usage patterns**:

```python
# Option 1: Use Campaign class (recommended for single offering tracking)
campaign = filing.get_campaign()
print(campaign.issuer_file_number)  # 020-XXXXX - identifies ONE offering
print(campaign.portal_file_number)  # 007-XXXXX - portal reference
related = campaign.all_filings  # ✅ One offering only

# Option 2: Manual with issuer file number (single offering)
entity_filing = filing.as_company_filing()
issuer_file_num = entity_filing.file_number  # 020-XXXXX
related = company.get_filings(file_number=issuer_file_num)  # ✅ One offering

# Option 3: Portal-level analysis (all offerings through a portal)
formc = filing.obj()
portal_file_num = formc.portal_file_number  # 007-XXXXX
all_portal_offerings = company.get_filings(file_number=portal_file_num)  # All offerings
```

---

## Key Takeaways

1. **Two file numbers exist**: Issuer's (020-XXXXX) and Portal's (007-XXXXX)
2. **Use issuer file number** for single offering tracking (what Campaign class does)
3. **Portal file number** identifies the funding portal, not the specific offering
4. **Multiple offerings** by same company have different issuer file numbers
5. **Campaign class** performs early conversion and caching for performance
6. **Direct query** is more efficient than parsing loop
7. **Property renamed**: `campaign_file_number` removed, use `portal_file_number` instead
8. **This was discovered empirically** by examining actual filing data

---

**Date**: 2025-11-04
**Status**: Critical implementation detail documented
**Last Updated**: 2025-11-04 (removed `campaign_file_number`, added `portal_file_number`)
**Affected Files**:
- `edgar/offerings/campaign.py` (uses issuer file number correctly)
- `edgar/offerings/formc.py` (removed `campaign_file_number`, use `portal_file_number`)
- `docs/examples/campaign_lifecycle.py` (updated to use `portal_file_number`)
