# SEC Filing Header Structure Guide

## Overview

SEC filings contain structured SGML headers that provide metadata about the filing and identify the various parties involved. The `sgml_header.py` module parses these headers into structured Python objects that components can leverage for filing analysis.

## Technical Structure

### SGML Format

Headers appear between `<SEC-HEADER>` and `</SEC-HEADER>` tags with two main formats:

#### Modern Format (2000s+)
```sgml
<SEC-HEADER>
ACCESSION NUMBER:         0000950103-24-001234
CONFORMED SUBMISSION TYPE: 10-K
FILED AS OF DATE:         20240115
FILER:
    COMPANY DATA:
        COMPANY CONFORMED NAME:    APPLE INC
        CENTRAL INDEX KEY:         0000320193
        STANDARD INDUSTRIAL CLASS: 3571
    BUSINESS ADDRESS:
        STREET 1:                  ONE APPLE PARK WAY
        CITY:                      CUPERTINO
        STATE:                     CA
</SEC-HEADER>
```

#### Legacy Format (1990s)
```sgml
<ACCEPTANCE-DATETIME>19950612172243
<TYPE>10-K
<FILER>
    <COMPANY-DATA>
        <CONFORMED-NAME>MICROSOFT CORP
    </COMPANY-DATA>
</FILER>
```

### Python Data Model

#### Core Classes

```python
@dataclass(frozen=True)
class CompanyInformation:
    name: str                    # Company legal name
    cik: str                     # Central Index Key (10-digit identifier)
    sic: str                     # Standard Industrial Classification code
    irs_number: str              # IRS tax ID
    state_of_incorporation: str  # Two-letter state code
    fiscal_year_end: str         # MMDD format (e.g., "0930" for Sept 30)

@dataclass(frozen=True)
class FilingInformation:
    form: str                    # Form type (10-K, 8-K, etc.)
    file_number: str             # SEC file number (e.g., "001-38432")
    sec_act: str                 # Applicable SEC Act (e.g., "34" for Exchange Act)
    film_number: str             # Internal SEC document number

@dataclass(frozen=True)
class Address:
    street1: str
    street2: Optional[str]
    city: str
    state_or_country: str
    zipcode: str
```

## Entity Roles and Form Types

### 1. Filer
**Definition**: The primary entity submitting the filing to the SEC.

**Common Form Types**:
- **10-K/10-Q/8-K**: Public companies filing periodic reports
- **S-1/S-3**: Companies registering securities
- **DEF 14A**: Companies soliciting shareholder proxies
- **N-1A/N-CSR**: Investment companies/mutual funds

**Data Structure**:
```python
@dataclass(frozen=True)
class Filer:
    company_information: CompanyInformation
    filing_information: FilingInformation
    business_address: Address
    mailing_address: Address
    former_company_names: Optional[List[FormerCompany]]
```

**Header Example**:
```sgml
FILER:
    COMPANY DATA:
        COMPANY CONFORMED NAME:    TESLA INC
        CENTRAL INDEX KEY:         0001318605
        STANDARD INDUSTRIAL CLASS: 3711
        IRS NUMBER:                912197729
        STATE OF INCORPORATION:    DE
        FISCAL YEAR END:           1231
```

### 2. ReportingOwner
**Definition**: Individual or entity reporting beneficial ownership or transactions.

**Common Form Types**:
- **Forms 3/4/5**: Insider trading reports
- **Schedule 13D/G**: 5%+ beneficial ownership
- **Schedule 13F**: Institutional investment manager holdings

**Data Structure**:
```python
@dataclass(frozen=True)
class ReportingOwner:
    owner: Owner                        # Name and CIK of reporting person
    company_information: CompanyInformation  # May be empty for individuals
    filing_information: FilingInformation
    business_address: Address
    mailing_address: Address
```

**Key Differences**:
- Individuals have `owner.name` in "LASTNAME FIRSTNAME" format
- Entities have full `company_information` populated
- Form 4 includes transaction codes and amounts

### 3. Issuer
**Definition**: Company whose securities are the subject of the filing.

**Common Form Types**:
- **Forms 3/4/5**: Company whose stock insiders are trading
- **Schedule 13D/G**: Company whose shares are being accumulated
- **Form 144**: Company whose restricted securities are being sold

**Data Structure**:
```python
@dataclass(frozen=True)
class Issuer:
    company_information: CompanyInformation
    business_address: Address
    mailing_address: Address
    former_company_names: Optional[List[FormerCompany]]
```

**Relationship to Other Entities**:
- In Form 4: Issuer is the company, ReportingOwner is the insider
- In Schedule 13D: Issuer is target company, ReportingOwner is acquirer

### 4. SubjectCompany
**Definition**: Target company in M&A transactions or tender offers.

**Common Form Types**:
- **Schedule TO**: Tender offer target
- **Schedule 14D-9**: Target's response to tender offer
- **DEFM14A**: Merger proxy (target company)
- **Schedule 13E-3**: Going-private transaction target

**Data Structure**:
```python
@dataclass(frozen=True)
class SubjectCompany:
    company_information: CompanyInformation
    filing_information: FilingInformation
    business_address: Address
    mailing_address: Address
    former_company_names: Optional[List[FormerCompany]]
```

## Form-Specific Header Patterns

### Annual/Quarterly Reports (10-K, 10-Q, 8-K)
```
Entities Present: Filer only
Key Metadata:
- CONFORMED PERIOD OF REPORT: End date of reporting period
- FILED AS OF DATE: Submission date
- EFFECTIVENESS DATE: When filing becomes effective
Primary Focus: Filer's financial condition and operations
```

### Insider Trading (Forms 3, 4, 5)
```
Entities Present: ReportingOwner + Issuer
Key Metadata:
- REPORTING-OWNER: Insider conducting transaction
  - Relationship: Officer/Director/10% Owner
  - Transaction details in <TABLE> sections
- ISSUER: Public company whose securities are traded
Primary Focus: Insider's transactions in issuer's securities
```

### Beneficial Ownership (Schedule 13D/G)
```
Entities Present: ReportingOwner + SubjectCompany
Key Metadata:
- REPORTING-OWNER: Person/group acquiring shares
  - Ownership percentage
  - Purpose of transaction
- SUBJECT COMPANY: Company being accumulated
Primary Focus: Significant ownership positions and intentions
```

### Tender Offers (Schedule TO)
```
Entities Present: Filer + SubjectCompany
Key Metadata:
- FILER: Bidder making the offer
- SUBJECT COMPANY: Target company
- Offer terms, expiration dates
Primary Focus: Acquisition attempt and terms
```

### Proxy Statements (DEF 14A)
```
Entities Present: Filer (+ SubjectCompany if merger)
Key Metadata:
- Meeting date and agenda items
- Record date for voting
- DEFM14A includes merger terms
Primary Focus: Shareholder voting matters
```

### Investment Company (N-1A, N-CSR)
```
Entities Present: Filer (fund complex)
Key Metadata:
- Series and class information
- Investment adviser details
- Portfolio statistics
Primary Focus: Fund operations and holdings
```

## Special Considerations

### Multiple Entities
Some filings have multiple instances of the same entity type:
- Joint filings: Multiple Filers
- Group filings: Multiple ReportingOwners in Schedule 13D
- Fund complexes: Multiple series under one Filer

### Entity Resolution
The parser handles entity identification:
- Converts individual names from "LASTNAME FIRSTNAME" to readable format
- Links CIKs to Entity database for company/individual determination
- Preserves historical company names with change dates

### Data Extraction Patterns

```python
# Accessing filing metadata
header.form                    # Form type
header.accession_number        # Unique filing ID
header.filing_date            # When filed
header.period_of_report       # Period covered

# Identifying primary entity
if header.filers:
    primary_entity = header.filers[0].company_information
elif header.reporting_owners:
    primary_entity = header.issuer.company_information
    reporter = header.reporting_owners[0].owner

# Checking for M&A activity
if header.subject_companies:
    target = header.subject_companies[0]
    acquirer = header.filers[0] if header.filers else None
```

## Component Development Guidelines

When building components that use header data:

1. **Identify Required Entities**: Determine which entity roles are relevant
2. **Handle Missing Data**: Not all fields are always populated
3. **Check Form Type**: Different forms have different data patterns
4. **Consider Relationships**: Understand entity relationships for the form
5. **Use Type-Specific Logic**: Implement form-specific parsing when needed

### Example: Insider Trading Component
```python
def process_insider_filing(header: FilingHeader):
    if header.form not in ['3', '4', '5']:
        return None
    
    insider = header.reporting_owners[0] if header.reporting_owners else None
    company = header.issuer
    
    return {
        'insider_name': insider.owner.name,
        'insider_cik': insider.owner.cik,
        'company_name': company.company_information.name,
        'company_cik': company.company_information.cik,
        'filing_date': header.filing_date
    }
```

### Example: M&A Activity Component
```python
def process_merger_filing(header: FilingHeader):
    if not header.subject_companies:
        return None  # Not an M&A filing
    
    target = header.subject_companies[0]
    acquirer = header.filers[0] if header.filers else None
    
    return {
        'target': target.company_information.name,
        'acquirer': acquirer.company_information.name if acquirer else 'Unknown',
        'form_type': header.form,
        'announcement_date': header.filing_date
    }
```

## Data Quality Notes

- **CIK Format**: Always 10 digits with leading zeros
- **Dates**: Various formats (YYYYMMDD, YYYY-MM-DD, etc.)
- **SIC Codes**: 4-digit industry classification
- **State Codes**: Standard 2-letter abbreviations
- **Fiscal Year End**: MMDD format without year
- **Addresses**: May have incomplete fields, especially for individuals
- **Former Names**: Include date of change for tracking corporate history