# FormC Class Documentation

## Overview

The `FormC` class represents SEC Form C and its variants - crowdfunding offering documents filed under Regulation Crowdfunding (Reg CF). Form C filings allow private companies to raise capital from retail investors through SEC-registered crowdfunding portals.

**Key Features:**
- Parse and access crowdfunding offering information
- View financial disclosures and company metrics
- Track offering status, deadlines, and progress
- Access issuer and funding portal details
- Navigate complete offering lifecycle via related filings

## Quick Start

Get started with Form C in 3 lines:

```python
from edgar import Company

# Get a company with Form C filings
company = Company("1881570")  # ViiT Health (example company with crowdfunding)

# Get Form C filings
filings = company.get_filings(form="C")
filing = filings[0]

# Parse into FormC object
formc = filing.obj()

# Access offering information
print(f"Issuer: {formc.issuer_name}")
print(f"Target: ${formc.offering_information.target_amount:,.0f}")
print(f"Deadline: {formc.offering_information.deadline_date}")

# Get complete offering lifecycle
offering = formc.get_offering()
print(offering.timeline())
```

## Form C Variants

Form C has several variants that track the lifecycle of a crowdfunding campaign:

| Form Type | Description | Contains |
|-----------|-------------|----------|
| **C** | Initial Offering Statement | Offering terms, issuer info, portal info |
| **C/A** | Offering Amendment | Updates to initial offering |
| **C-U** | Progress Update | Amount raised, investor count updates |
| **C-U/A** | Progress Update Amendment | Corrections to progress update |
| **C-AR** | Annual Report | Financial performance, continued operations |
| **C-AR/A** | Annual Report Amendment | Corrections to annual report |
| **C-TR** | Termination Report | Campaign completion or cancellation |

## Common Actions

Quick reference for working with Form C filings:

### Access Form C from Filing
```python
# Get a Form C filing and parse it
from edgar import Company

company = Company("1881570")  # ViiT Health
filings = company.get_filings(form="C")
filing = filings[0]

# Parse into FormC object
formc = filing.obj()
```

### Access Offering Information
```python
# Get offering details
offering = formc.offering_information

# Key offering terms
print(offering.target_amount)              # Target raise amount
print(offering.maximum_offering_amount)    # Maximum raise amount
print(offering.deadline_date)              # Offering deadline
print(offering.security_description)       # Type of security
print(offering.price_per_security)         # Price per share/unit
print(offering.number_of_securities)       # Number of securities

# Computed metrics
print(offering.percent_to_maximum)         # Target as % of max
```

### Access Issuer Information
```python
# Company details
issuer = formc.issuer
print(issuer.name)                         # Company name
print(issuer.cik)                          # CIK number

# Get all offerings by this company
offerings = issuer.get_offerings()
latest = issuer.latest_offering()

# Convert to full Company object
company = issuer.as_company()
```

### Access Financial Disclosures
```python
# Annual report data (in C-AR and sometimes C forms)
if formc.annual_report_disclosure:
    fin = formc.annual_report_disclosure

    # Current year financials
    print(fin.revenues)                    # Revenue
    print(fin.net_income)                  # Net income
    print(fin.total_assets)                # Total assets
    print(fin.cash_and_cash_equivalents)   # Cash
    print(fin.number_of_employees)         # Employee count

    # Computed metrics
    print(fin.revenue_growth_yoy)          # YoY revenue growth %
    print(fin.debt_to_asset_ratio)         # Debt/asset ratio %
    print(fin.is_pre_revenue)              # True if no revenue
```

### Track Offering Status
```python
# Status information
print(formc.campaign_status)               # Human-readable status
print(formc.days_to_deadline)              # Days until deadline
print(formc.is_expired)                    # True if past deadline

# Status examples:
# - "Active (Initial)" - Original Form C
# - "Active (Amendment)" - Form C/A
# - "Progress Update" - Form C-U
# - "Annual Report" - Form C-AR
# - "Terminated" - Form C-TR
```

### Access Funding Portal
```python
# Portal information
if formc.portal_name:
    print(formc.portal_name)               # Portal name
    print(formc.portal_cik)                # Portal CIK
    print(formc.portal_file_number)        # Portal file number
```

### Get Complete Offering Lifecycle
```python
# Get all related filings for this offering
offering = formc.get_offering()

# Access offering timeline
print(offering.timeline())

# Get specific filing types
initial = offering.initial_filing()        # Original Form C
amendments = offering.amendments()         # All C/A filings
updates = offering.updates()               # All C-U filings
annual_reports = offering.annual_reports() # All C-AR filings
```

## AI-Native Workflow: to_context()

The `to_context()` method provides token-efficient documentation optimized for LLM context windows:

### Usage
```python
# Standard detail level (recommended)
context = formc.to_context()

# Minimal tokens (~100-200 tokens)
context = formc.to_context(detail='minimal')

# Full information (~600-1000 tokens)
context = formc.to_context(detail='full')

# Include filing date
context = formc.to_context(filing_date=filing.filing_date)
```

### Detail Levels

**Minimal** - Essential offering information only:
- Issuer name and form type
- Security type
- Target and maximum amounts (abbreviated)
- Deadline with days remaining
- Campaign status

**Standard** (default) - Most important data:
- Everything in minimal
- CIK, jurisdiction, website
- Funding portal details
- Price per security and units
- Current vs prior year financials
- Computed metrics (YoY growth, ratios)
- Available actions guide

**Full** - Comprehensive view:
- Everything in standard
- Business address
- Portal CRD number
- Over-subscription details
- Portal fee structure
- Employee count
- Detailed debt breakdown
- Offering jurisdictions
- Officer signatures

### Example Output

```python
formc.to_context(detail='standard')
```

Returns:
```
FORM C - FORM C - OFFERING (Filed: 2024-03-15)

ISSUER: ViiT Health LLC
  CIK: 1881570
  Legal: Delaware Limited Liability Company
  Website: https://viit.health

FUNDING PORTAL: StartEngine Crowdfunding, Inc.
  File Number: 007-00061

OFFERING:
  Security: Common Stock (Class A Membership Interests)
  Target: $50,000 | Maximum: $950,000
  Target is 5% of maximum
  Price: $1.20/unit | Units: 41,666
  Deadline: 2024-12-31
  Status: 247 days remaining

FINANCIALS (Current vs Prior Year):
  Revenue: $0 (pre-revenue)
  Net Income: -$125,000
  Assets: $50,000
  Total Debt: $0

CAMPAIGN STATUS: Active (Initial)

AVAILABLE ACTIONS:
  - Use .get_offering() for complete campaign lifecycle
  - Use .issuer for IssuerCompany information
  - Use .offering_information for offering terms
  - Use .annual_report_disclosure for financial data
```

## Properties and Attributes

### Core Information
```python
formc.form                     # Form type ("C", "C/A", etc.)
formc.description              # Full form description
formc.issuer_name              # Issuer company name
formc.issuer_cik               # Issuer CIK
```

### Offering Details
```python
formc.offering_information     # OfferingInformation object
formc.days_to_deadline         # Days until offering closes (int or None)
formc.is_expired               # True if deadline passed
formc.campaign_status          # User-friendly status string
```

### Portal Information
```python
formc.portal_name              # Funding portal name
formc.portal_cik               # Portal CIK
formc.portal_file_number       # Portal's file number (007-XXXXX)
```

### Financial Data
```python
formc.annual_report_disclosure # AnnualReportDisclosure object
```

### Related Entities
```python
formc.issuer                   # IssuerCompany object (cached)
formc.filer_information        # FilerInformation object
formc.issuer_information       # IssuerInformation object
formc.signature_info           # SignatureInfo object
```

## Working with OfferingInformation

When `offering_information` is available (Forms C, C/A):

### Basic Fields
```python
offering = formc.offering_information

offering.security_offered_type           # Security type
offering.security_offered_other_desc     # Additional description
offering.offering_amount                 # Target amount
offering.maximum_offering_amount         # Maximum amount
offering.deadline_date                   # Offering deadline
offering.price                           # Price as string
offering.no_of_security_offered          # Number as string
```

### Computed Properties
```python
# Cleaner data access
offering.security_description            # Combined type + description
offering.target_amount                   # Alias for offering_amount
offering.price_per_security              # Price as float
offering.number_of_securities            # Number as int
offering.percent_to_maximum              # Target/max as percentage
offering.offering_deadline               # Alias for deadline_date

# Over-subscription
offering.over_subscription_accepted      # "Y" or "N"
offering.over_subscription_allocation_type
offering.desc_over_subscription
```

## Working with AnnualReportDisclosure

When `annual_report_disclosure` is available (Forms C-AR, some C):

### Financial Metrics (Current Year)
```python
fin = formc.annual_report_disclosure

# Convenience aliases (most recent fiscal year)
fin.total_assets                         # Total assets
fin.cash_and_cash_equivalents            # Cash
fin.accounts_receivable                  # A/R
fin.short_term_debt                      # Short-term debt
fin.long_term_debt                       # Long-term debt
fin.revenues                             # Revenue
fin.cost_of_goods_sold                   # COGS
fin.taxes_paid                           # Taxes
fin.net_income                           # Net income
fin.number_of_employees                  # Employees
```

### Comparative Data (Two Years)
```python
# Current fiscal year
fin.total_asset_most_recent_fiscal_year
fin.revenue_most_recent_fiscal_year
fin.net_income_most_recent_fiscal_year

# Prior fiscal year
fin.total_asset_prior_fiscal_year
fin.revenue_prior_fiscal_year
fin.net_income_prior_fiscal_year
```

### Computed Metrics
```python
# Growth and performance
fin.revenue_growth_yoy                   # YoY revenue growth %
fin.asset_growth_yoy                     # YoY asset growth %
fin.burn_rate_change                     # Change in net income

# Financial health
fin.debt_to_asset_ratio                  # Debt/assets as %
fin.total_debt_most_recent               # Total debt (current year)
fin.total_debt_prior                     # Total debt (prior year)
fin.is_pre_revenue                       # True if no revenue

# Geographic scope
fin.offering_jurisdictions               # List of states
fin.is_offered_in_all_states            # True if all 50 states
```

## Working with IssuerCompany

The issuer property provides offering-specific company methods:

### Basic Usage
```python
issuer = formc.issuer

print(issuer.name)                       # Company name
print(issuer.cik)                        # CIK number
```

### Get All Offerings
```python
# Get all crowdfunding offerings by this company
offerings = issuer.get_offerings()       # List[Offering]

for offering in offerings:
    print(offering.file_number)
    print(offering.timeline())
```

### Get Latest Offering
```python
latest = issuer.latest_offering()        # Most recent offering
```

### Convert to Full Company
```python
# Get complete company data with all filings
company = issuer.as_company()
all_filings = company.get_filings()
```

## Offering Lifecycle

Track a complete offering from start to finish using the `Offering` class.

### Understanding the Offering Lifecycle

A crowdfunding offering goes through several stages:
1. **Initial Filing (C)** - Company announces offering terms
2. **Amendments (C/A)** - Updates to offering terms (optional)
3. **Progress Updates (C-U)** - Milestone reports at 50% and 100% of target (required)
4. **Annual Reports (C-AR)** - Yearly financial compliance (required)
5. **Termination (C-TR)** - Offering closes (required)

### Step-by-Step Workflow: Get Complete Offering Lifecycle

#### Method 1: From a FormC object (Easiest)
```python
# Start with any Form C filing
from edgar import Company

company = Company("1881570")  # ViiT Health
filing = company.get_filings(form="C")[0]
formc = filing.obj()

# Get the complete offering lifecycle
offering = formc.get_offering()

# Now you have access to all lifecycle stages
print(f"Offering File Number: {offering.issuer_file_number}")
print(f"Company: {offering.company.name}")
```

#### Method 2: Direct from Filing
```python
from edgar.offerings import Offering

# If you have a Filing object from any Form C variant
filing = company.get_filings(form="C")[0]
offering = Offering(filing)
```

#### Method 3: From File Number (Advanced)
```python
from edgar.offerings import Offering

# If you know the issuer file number (020-XXXXX)
offering = Offering('020-36002', cik='1881570')
```

#### Method 4: Get All Offerings for a Company
```python
from edgar import Company

company = Company("1881570")
issuer = company  # Can use Company directly

# Get IssuerCompany from any FormC
filing = company.get_filings(form="C")[0]
formc = filing.obj()
issuer = formc.issuer

# Get all offerings
offerings = issuer.get_offerings()  # Returns List[Offering]

for offering in offerings:
    print(f"Offering {offering.issuer_file_number}")
    print(offering.timeline())
    print()
```

### Access Lifecycle Stages

Once you have an `Offering` object, access different filing types:

```python
# Get filings by lifecycle stage
initial = offering.initial_offering        # Original Form C filing
amendments = offering.amendments           # List of C/A filings
updates = offering.updates                 # List of C-U filings
annual_reports = offering.annual_reports   # List of C-AR filings
termination = offering.termination         # C-TR filing (if closed)

# All filings in chronological order
all_filings = offering.all_filings        # List[Filing]

# Parsed FormC objects (cached for performance)
initial_formc = offering.initial_formc    # FormC from initial filing
```

### Offering Status and Metrics

```python
# Current status
status = offering.current_status            # e.g., "Active", "Terminated", "Updated"

# Timeline metrics
days_active = offering.days_since_launch    # Days since initial filing
launch_date = offering.launch_date          # Date of initial filing
latest_date = offering.latest_activity_date # Date of most recent filing

# Status checks
is_active = offering.is_active              # True if offering is active
is_terminated = offering.is_terminated      # True if C-TR filed
is_expired = offering.is_expired            # True if past deadline

# File numbers
file_number = offering.file_number          # Issuer file number (020-XXXXX)
issuer_file_num = offering.issuer_file_number  # Alias for file_number
portal_file_num = offering.portal_file_number  # Portal file number (007-XXXXX) or None
```

### Display Offering Timeline

```python
# Print chronological timeline
print(offering.timeline())

# Example output:
# 2024-01-15: C    - Initial offering ($950K target)
# 2024-02-01: C/A  - Amendment
# 2024-03-15: C-U  - Progress update (50% milestone)
# 2024-06-20: C-U  - Progress update (100% milestone)
# 2025-01-15: C-AR - Annual report
```

### Working with Lifecycle Data

```python
# Analyze offering progression
offering = formc.get_offering()

# Check if offering has progress updates
if offering.updates:
    print(f"Found {len(offering.updates)} progress updates")
    for update in offering.updates:
        update_formc = update.obj()
        print(f"  Update filed: {update.filing_date}")

# Check annual compliance
if offering.annual_reports:
    print(f"Found {len(offering.annual_reports)} annual reports")
    latest_ar = offering.annual_reports[-1]  # Most recent
    ar_formc = latest_ar.obj()
    if ar_formc.annual_report_disclosure:
        fin = ar_formc.annual_report_disclosure
        print(f"  Latest revenue: ${fin.revenues:,.0f}")
        print(f"  Latest net income: ${fin.net_income:,.0f}")

# Check if offering is closed
if offering.termination:
    print(f"Offering terminated on {offering.termination.filing_date}")
```

### Complete Workflow Example

```python
from edgar import Company

# Step 1: Get company and find Form C filings
company = Company("1881570")  # ViiT Health
filings = company.get_filings(form=["C", "C/A", "C-U", "C-AR"])

print(f"Found {len(filings)} Form C filings")

# Step 2: Group filings by offering (by file number)
from edgar.offerings.formc import group_offerings_by_file_number
grouped = group_offerings_by_file_number(filings)

print(f"Company has {len(grouped)} distinct offerings")

# Step 3: Analyze each offering
from edgar.offerings import Offering

for file_num, offering_filings in grouped.items():
    print(f"\nAnalyzing Offering {file_num}")
    print(f"  Filings: {len(offering_filings)}")

    # Create Offering object
    offering = Offering(file_num, cik=company.cik)

    # Display timeline
    print(offering.timeline())

    # Get initial offering details
    initial_formc = offering.initial_formc
    if initial_formc.offering_information:
        offer = initial_formc.offering_information
        print(f"  Target: ${offer.target_amount:,.0f}")
        print(f"  Maximum: ${offer.maximum_offering_amount:,.0f}")
        print(f"  Deadline: {offer.deadline_date}")

    # Check latest financial data
    if offering.annual_reports:
        latest_ar = offering.annual_reports[-1].obj()
        if latest_ar.annual_report_disclosure:
            fin = latest_ar.annual_report_disclosure
            print(f"  Latest Financials:")
            print(f"    Revenue: ${fin.revenues:,.0f}")
            print(f"    Net Income: ${fin.net_income:,.0f}")
```

## Finding Form C Filings

### By Company
```python
from edgar import Company

company = Company("StartEngine")
offerings = company.get_filings(form="C")

# All Form C variants
all_formc = company.get_filings(form=["C", "C/A", "C-U", "C-AR", "C-TR"])
```

### By Search
```python
from edgar import get_filings

# All Form C filings in a period
filings = get_filings(2024, 1, form="C")

# Latest crowdfunding offerings
recent = get_filings(2024, 3, form="C")
```

### Group by Offering
```python
from edgar.offerings.formc import group_offerings_by_file_number

company = Company("1881570")
all_filings = company.get_filings(form=["C", "C/A", "C-U", "C-AR"])

# Group by offering (file number)
grouped = group_offerings_by_file_number(all_filings)

for file_num, offering_filings in grouped.items():
    print(f"Offering {file_num}: {len(offering_filings)} filings")
```

## Display and Output

### Rich Terminal Display
```python
# Display formatted output in terminal
print(formc)        # Shows all sections with tables

# Or explicitly
formc.__rich__()    # Rich panel display
```

### AI Context Export
```python
# For LLM workflows
context = formc.to_context()                    # Standard
context = formc.to_context(detail='minimal')    # Compact
context = formc.to_context(detail='full')       # Everything

# With filing date
context = formc.to_context(
    detail='standard',
    filing_date=filing.filing_date
)
```

## Understanding File Numbers

Form C uses two different file numbers:

### Issuer File Number (020-XXXXX)
- Identifies the specific **offering**
- Unique to each crowdfunding campaign
- All filings for one offering share this number
- Found in `Filing.file_number` or via `filing.as_company_filing().file_number`
- Used to track offering lifecycle

### Portal File Number (007-XXXXX)
- Identifies the **funding portal**
- Same portal used by many companies
- Found in `formc.portal_file_number`
- Used to identify the intermediary

```python
# Get issuer file number (specific to this offering)
filing = company.get_filings(form="C")[0]
company_filing = filing.as_company_filing()
issuer_file_num = company_filing.file_number  # "020-XXXXX"

# Get portal file number (identifies the portal)
formc = filing.obj()
portal_file_num = formc.portal_file_number    # "007-XXXXX"
```

## Parsing from XML

FormC can be parsed directly from XML:

```python
# From filing
formc = FormC.from_filing(filing)

# From XML string
xml_content = filing.xml()
formc = FormC.from_xml(xml_content, form="C")
```

## Best Practices

### Check Data Availability
```python
# Not all Form C variants have offering info
if formc.offering_information:
    print(formc.offering_information.target_amount)

# Not all have financial disclosures
if formc.annual_report_disclosure:
    print(formc.annual_report_disclosure.revenues)

# Portal info may be missing (especially in C-AR)
if formc.portal_name:
    print(f"Portal: {formc.portal_name}")
```

### Use Computed Properties
```python
# Instead of raw fields
offering = formc.offering_information

# Good - uses computed properties
price = offering.price_per_security      # Returns float
count = offering.number_of_securities    # Returns int

# Less ideal - raw strings
price_str = offering.price               # Returns string "1.20000"
count_str = offering.no_of_security_offered  # Returns string
```

### Efficient Context Usage
```python
# For LLM workflows, choose appropriate detail level

# Quick screening of many offerings
contexts = [f.obj().to_context(detail='minimal') for f in filings]

# Analysis of specific offering
context = formc.to_context(detail='full')
```

## Common Use Cases

### Screen Offerings by Size
```python
filings = get_filings(2024, 3, form="C")

large_offerings = []
for filing in filings:
    formc = filing.obj()
    if formc.offering_information:
        if formc.offering_information.maximum_offering_amount > 1_000_000:
            large_offerings.append((
                formc.issuer_name,
                formc.offering_information.maximum_offering_amount
            ))
```

### Track Offering Progress
```python
# Get all filings for an offering
offering = formc.get_offering()

# Show timeline
print(offering.timeline())

# Compare updates
updates = offering.updates()
if updates:
    for update in updates:
        update_formc = update.obj()
        print(f"Update on {update.filing_date}")
```

### Analyze Portal Activity
```python
filings = get_filings(2024, 1, form="C")

portal_stats = {}
for filing in filings:
    formc = filing.obj()
    portal = formc.portal_name
    if portal:
        portal_stats[portal] = portal_stats.get(portal, 0) + 1

# Most active portals
for portal, count in sorted(portal_stats.items(),
                           key=lambda x: x[1],
                           reverse=True)[:10]:
    print(f"{portal}: {count} offerings")
```

### Financial Health Screening
```python
filings = company.get_filings(form="C-AR")

for filing in filings:
    formc = filing.obj()
    if formc.annual_report_disclosure:
        fin = formc.annual_report_disclosure

        print(f"Report Date: {filing.filing_date}")
        print(f"Revenue: ${fin.revenues:,.0f}")
        print(f"Net Income: ${fin.net_income:,.0f}")
        if fin.revenue_growth_yoy:
            print(f"Growth: {fin.revenue_growth_yoy:.1f}%")
        print()
```

## Troubleshooting

### No offering_information found

Some Form C variants don't have offering information:
- **C-AR** (Annual Report) - No offering info, only financials
- **C-TR** (Termination) - May not have offering info
- **C-U** (Update) - May have limited offering info

**Solution**: Check if `offering_information` exists before accessing:
```python
if formc.offering_information:
    target = formc.offering_information.target_amount
else:
    print("No offering information in this filing type")
```

### No annual_report_disclosure found

Financial data is only in certain forms:
- **C-AR** (Annual Report) - Always has financials
- **C** (Initial) - Usually has financials
- **C/A, C-U, C-TR** - Usually don't have financials

**Solution**: Check before accessing:
```python
if formc.annual_report_disclosure:
    revenue = formc.annual_report_disclosure.revenues
else:
    print("No financial disclosure in this filing")
```

### Portal information is None

Some filings don't specify a portal:
- **C-AR** - Often doesn't list portal (offering already closed)
- Some direct offerings

**Solution**: Always check portal existence:
```python
if formc.portal_name:
    print(f"Portal: {formc.portal_name}")
else:
    print("No portal information")
```

### Can't find Offering by file number

The Offering class needs the **issuer file number** (020-XXXXX), not the portal file number (007-XXXXX).

**Solution**: Get issuer file number from filing:
```python
filing = company.get_filings(form="C")[0]
company_filing = filing.as_company_filing()
issuer_file_num = company_filing.file_number  # This is 020-XXXXX

offering = Offering(issuer_file_num, cik=company.cik)
```

## Agent Implementation Guide

If you're an AI agent implementing an offering lifecycle workflow, follow these steps:

### Step 1: Get Form C Filings
```python
from edgar import Company

# Find company with crowdfunding
company = Company("TICKER_OR_CIK")
filings = company.get_filings(form=["C", "C/A", "C-U", "C-AR", "C-TR"])
```

### Step 2: Group by Offering
```python
from edgar.offerings.formc import group_offerings_by_file_number

# Group filings by offering (issuer file number)
grouped = group_offerings_by_file_number(filings)
# Returns: Dict[str, EntityFilings]
# Keys are issuer file numbers like "020-36002"
```

### Step 3: Create Offering Objects
```python
from edgar.offerings import Offering

offerings = []
for file_num, offering_filings in grouped.items():
    # Create from first filing in group for better initialization
    # (This caches the FormC object for faster access)
    first_filing = offering_filings[0]
    offering = Offering(first_filing)
    offerings.append(offering)
```

### Step 4: Access Lifecycle Data
```python
for offering in offerings:
    # Get parsed initial FormC (cached)
    initial_formc = offering.initial_formc

    # initial_formc could be None if no initial filing found
    if not initial_formc:
        print("  No initial Form C found")
        continue

    # Check offering terms
    if initial_formc.offering_information:
        offer_info = initial_formc.offering_information
        print(f"Target: ${offer_info.target_amount:,.0f}")
        print(f"Maximum: ${offer_info.maximum_offering_amount:,.0f}")

    # Check latest financials
    if offering.annual_reports:
        latest_ar = offering.annual_reports[-1].obj()
        if latest_ar.annual_report_disclosure:
            fin = latest_ar.annual_report_disclosure
            print(f"Revenue: ${fin.revenues:,.0f}")
            print(f"Net Income: ${fin.net_income:,.0f}")

    # Display timeline
    print(offering.timeline())
```

### Key Points for Agents

1. **Always check data availability** - Use `if` checks before accessing optional data
2. **Use computed properties** - Prefer `.price_per_security` over `.price` (cleaner data)
3. **Cache expensive operations** - `Offering.initial_formc` is cached, use it repeatedly
4. **File numbers matter** - Use issuer file number (020-XXXXX) for Offering, not portal (007-XXXXX)
5. **Different forms have different data** - Check form type to know what's available
6. **Use to_context() for LLM workflows** - Token-efficient summaries at different detail levels

## Related Classes

- **Offering** - Represents complete offering lifecycle (edgar.offerings.campaign)
- **IssuerCompany** - Offering-specific company wrapper
- **Company** - Full SEC entity data
- **Filing** - Base filing class
- **OfferingInformation** - Offering terms model
- **AnnualReportDisclosure** - Financial disclosure model

## See Also

- **Offering class documentation** - See `edgar.offerings.campaign` module docstring
- **Company class** - For general company operations
- **Filing class** - For base filing operations
