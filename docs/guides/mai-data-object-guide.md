# Municipal Advisor Form (MA-I) Data Object Guide

## Overview

**Form MA-I** is an SEC filing required for individuals who work as municipal advisors. Municipal advisors provide advice to state and local governments on bond issuances and other municipal financial products. The SEC requires registration of these individuals to protect municipalities from unqualified or unethical advisors.

The `MunicipalAdvisorForm` class in edgartools parses MA-I XML filings into structured Python objects, making it easy to extract applicant information, employment history, and critically, disclosure information about any regulatory or legal issues.

## Access Pattern

```python
from edgar import Filing

# Get an MA-I filing
filing = Filing(form="MA-I", ...)

# Parse into MunicipalAdvisorForm object
ma_form = filing.obj()
```

---

## Core Data Structure

### MunicipalAdvisorForm (Top-Level Object)

| Property | Type | Description |
|----------|------|-------------|
| `filing` | `Filing` | Reference to the original SEC filing |
| `filer` | `Filer` | CIK and CCC of the filing entity |
| `is_amendment` | `bool` | Whether this is an amendment (MA-I/A) |
| `is_individual` | `bool` | Whether applicant is an individual |
| `previous_accession_no` | `str` | Accession number of prior filing if amendment |
| `contact` | `Contact` | Filing contact information |
| `applicant` | `Applicant` | The individual applying for registration |
| `internet_notification_addresses` | `List[str]` | Email addresses for notifications |
| `municipal_advisor_offices` | `List[MunicipalAdvisorOffice]` | Firms where individual is employed |
| `employment_history` | `EmploymentHistory` | Current and previous employment |
| `disclosures` | `Disclosures` | All disclosure questions and answers |
| `signature` | `Signature` | Filing signature |

---

## Applicant Information

### Applicant

The individual seeking municipal advisor registration.

| Property | Type | Description | UI Usage |
|----------|------|-------------|----------|
| `name` | `Name` | Full legal name | Primary display |
| `other_names` | `List[Name]` | Aliases, maiden names, etc. | Name history |
| `crd` | `str` | FINRA CRD number | BrokerCheck link |
| `number_of_advisory_firms` | `int` | Count of associated MA firms | Employment scope |
| `full_name` | `str` (property) | Concatenated full name | Display convenience |

### Name

| Property | Type | Description |
|----------|------|-------------|
| `first_name` | `str` | First name |
| `middle_name` | `str` | Middle name |
| `last_name` | `str` | Last name |
| `suffix` | `str` | Name suffix (Jr., III, etc.) |
| `full_name` | `str` (property) | Complete formatted name |

### Contact

Filing contact person (may differ from applicant).

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Contact person name |
| `phone` | `str` | Phone number |
| `email` | `str` | Email address |

### Filer

| Property | Type | Description |
|----------|------|-------------|
| `cik` | `str` | SEC Central Index Key |
| `ccc` | `str` | EDGAR Filer ID confirmation code |

---

## Municipal Advisor Offices

### MunicipalAdvisorOffice

Firms where the individual works as a municipal advisor.

| Property | Type | Description | UI Usage |
|----------|------|-------------|----------|
| `cik` | `str` | Firm's SEC CIK | Link to firm filings |
| `firm_name` | `str` | Legal name of MA firm | Firm display |
| `is_independent_relationship` | `bool` | Independent contractor flag | Employment type badge |
| `recent_employment_commenced_date` | `str` | When employment started | Employment timeline |
| `file_number` | `str` | SEC registration file number | Registration link |
| `offices` | `List[Office]` | Physical office locations | Location display |

### Office

Physical office locations where the individual works.

| Property | Type | Description |
|----------|------|-------------|
| `start_date` | `str` | When work at this location began |
| `location_info` | `str` | Additional location details |
| `address` | `Address` | Full address |
| `street1` | `str` (property) | Street address line 1 |
| `street2` | `str` (property) | Street address line 2 |
| `city` | `str` (property) | City |
| `state_or_country` | `str` (property) | State/country code |
| `zipcode` | `str` (property) | Postal code |

---

## Employment History

### EmploymentHistory

Complete work history relevant to municipal advisory activities.

| Property | Type | Description |
|----------|------|-------------|
| `current_employer` | `Employer` | Current employment |
| `previous_employers` | `List[Employer]` | Past 10 years of employment |

### Employer

| Property | Type | Description | UI Usage |
|----------|------|-------------|----------|
| `name` | `str` | Employer name | Company display |
| `start_date` | `str` | Employment start (formatted as "Jun 2015") | Timeline |
| `end_date` | `str` | Employment end (None if current) | Timeline |
| `ma_related` | `bool` | Municipal advisor related work | MA badge |
| `investment_related` | `bool` | Investment related work | Investment badge |
| `position` | `str` | Job title/position | Role display |
| `address` | `Address` | Employer location | Location context |

---

## Disclosures (Critical Section)

The disclosures section is the most important part of MA-I filings for due diligence. It contains yes/no answers to extensive questions about the applicant's regulatory, legal, and financial history.

### Disclosures (Container)

| Property | Type | Description |
|----------|------|-------------|
| `criminal_disclosure` | `CriminalDisclosure` | Criminal history questions |
| `regulatory_disclosure` | `RegulatoryDisclosure` | SEC/CFTC regulatory history |
| `civil_disclosure` | `CivilDisclosure` | Civil court proceedings |
| `complaint_disclosure` | `ComplaintDisclosure` | Customer complaints |
| `termination_disclosure` | `TerminationDisclosure` | Employment terminations |
| `financial_disclosure` | `FinancialDisclosure` | Bankruptcy/financial issues |
| `judgement_lien_disclosure` | `JudgementLienDisclosure` | Judgments and liens |
| `investigation_disclosure` | `InvestigationDisclosure` | Ongoing investigations |
| `any()` | method | Returns `True` if ANY disclosure is positive |

---

### CriminalDisclosure

Criminal history questions.

| Property | Type | Description | Red Flag Level |
|----------|------|-------------|----------------|
| `is_convicted_of_felony` | `bool` | Felony conviction | Critical |
| `is_charged_with_felony` | `bool` | Pending felony charges | Critical |
| `is_org_convicted_of_felony` | `bool` | Caused org felony conviction | High |
| `is_org_charged_with_felony` | `bool` | Caused org felony charges | High |
| `is_convicted_of_misdemeanor` | `bool` | Misdemeanor conviction (investment-related) | Medium |
| `is_charged_with_misdemeanor` | `bool` | Pending misdemeanor charges | Medium |
| `is_org_convicted_of_misdemeanor` | `bool` | Caused org misdemeanor conviction | Medium |
| `is_org_charged_with_misdemeanor` | `bool` | Caused org misdemeanor charges | Medium |
| `any()` | method | Returns `True` if any criminal disclosure | - |

---

### RegulatoryDisclosure

SEC, CFTC, and other regulatory agency actions.

| Property | Type | Description | Red Flag Level |
|----------|------|-------------|----------------|
| `is_made_false_statement` | `bool` | Made false statement to regulator | Critical |
| `is_violated_regulation` | `bool` | Violated SEC/CFTC regulation | High |
| `is_cause_of_denial` | `bool` | Caused denial of registration | High |
| `is_order_against` | `bool` | Order entered against individual | High |
| `is_imposed_penalty` | `bool` | Penalty imposed | High |
| `is_un_ethical` | `bool` | Found dishonest or unethical | Critical |
| `is_found_in_violation_of_regulation` | `bool` | Found in violation | High |
| `is_found_in_cause_of_denial` | `bool` | Found to cause denial | High |
| `is_order_against_activity` | `bool` | Order against activities | High |
| `is_denied_license` | `bool` | License denied/suspended/revoked | Critical |
| `is_found_made_false_statement` | `bool` | Found to have made false statement | Critical |
| `is_found_in_violation_of_rules` | `bool` | Found in violation of rules | High |
| `is_found_in_cause_of_suspension` | `bool` | Caused suspension | High |
| `is_discipliend` | `bool` | Disciplined (expelled/barred) | Critical |
| `is_authorized_to_act_attorney` | `bool` | Attorney authorization suspended | Medium |
| `is_regulatory_complaint` | `bool` | Regulatory complaint pending | Medium |
| `is_violated_security_act` | `bool` | Violated Securities Act | Critical |
| `is_will_fully_aided` | `bool` | Willfully aided violation | Critical |
| `is_failed_to_supervise` | `bool` | Failed to supervise | High |
| `is_found_will_fully_aided` | `bool` | Found to willfully aid violation | Critical |
| `is_association_bared` | `bool` | Barred from association | Critical |
| `is_final_order` | `bool` | Final order entered against | High |
| `is_will_fully_violated_security_act` | `bool` | Willfully violated Securities Act | Critical |
| `is_failed_resonably` | `bool` | Failed reasonably to supervise | High |
| `any()` | method | Returns `True` if any regulatory disclosure | - |

---

### CivilDisclosure

Civil court proceedings.

| Property | Type | Description | Red Flag Level |
|----------|------|-------------|----------------|
| `is_enjoined` | `bool` | Enjoined in connection with MA business | High |
| `is_found_violation_of_regulation` | `bool` | Court found violation | High |
| `is_dismissed` | `bool` | Civil action dismissed with settlement | Medium |
| `is_named_in_civil_proceeding` | `bool` | Currently named in civil proceeding | Medium |
| `any()` | method | Returns `True` if any civil disclosure | - |

---

### ComplaintDisclosure

Customer and regulatory complaints.

| Property | Type | Description | Red Flag Level |
|----------|------|-------------|----------------|
| `is_complaint_pending` | `bool` | MA-related complaint pending | Medium |
| `is_complaint_settled` | `bool` | MA-related complaint settled | Low |
| `is_fraud_case_pending` | `bool` | Fraud case pending | High |
| `is_fraud_case_resulting_award` | `bool` | Fraud case resulted in award | High |
| `is_fraud_case_settled` | `bool` | Fraud case settled | Medium |
| `any()` | method | Returns `True` if any complaint disclosure | - |

---

### TerminationDisclosure

Employment terminations under adverse circumstances.

| Property | Type | Description | Red Flag Level |
|----------|------|-------------|----------------|
| `is_violated_industry_standards` | `bool` | Terminated for violating standards | High |
| `is_involved_in_fraud` | `bool` | Terminated for fraud involvement | Critical |
| `is_failed_to_supervise` | `bool` | Terminated for supervision failure | High |
| `any()` | method | Returns `True` if any termination disclosure | - |

---

### FinancialDisclosure

Financial problems within past 10 years.

| Property | Type | Description | Red Flag Level |
|----------|------|-------------|----------------|
| `is_compromised` | `bool` | Made compromise with creditors | Medium |
| `is_bankruptcy_petition` | `bool` | Organization filed bankruptcy | Medium |
| `is_trustee_appointed` | `bool` | Trustee appointed for organization | Medium |
| `is_bond_revoked` | `bool` | Bonding company denied/revoked bond | High |
| `any()` | method | Returns `True` if any financial disclosure | - |

---

### JudgementLienDisclosure

| Property | Type | Description | Red Flag Level |
|----------|------|-------------|----------------|
| `is_lien_against` | `bool` | Currently has judgment liens | Medium |
| `any()` | method | Returns `True` if any lien disclosure | - |

---

### InvestigationDisclosure

| Property | Type | Description | Red Flag Level |
|----------|------|-------------|----------------|
| `is_investigated` | `bool` | Currently under investigation | High |

---

## Signature

### Signature

| Property | Type | Description |
|----------|------|-------------|
| `signature` | `str` | Signature text |
| `date_signed` | `str` | Date of signature |
| `title` | `str` | Signer's title |

---

## UI Component Recommendations

### Applicant Summary Card
- Full name prominently displayed
- CRD number (link to FINRA BrokerCheck)
- Number of advisory firms
- Amendment status badge
- Other names (expandable)

### Disclosure Summary Panel (Critical)
**This is the most important UI element for due diligence.**

Display a traffic-light style indicator:
- **Green**: No disclosures (`disclosures.any() == False`)
- **Red**: Has disclosures (`disclosures.any() == True`)

If disclosures exist, show breakdown by category:
- Criminal (red if any)
- Regulatory (red if any)
- Civil (yellow if any)
- Complaints (yellow if any)
- Terminations (orange if any)
- Financial (yellow if any)
- Liens (yellow if any)
- Under Investigation (red if true)

### Employment History Timeline
- Visual timeline showing employment progression
- Badges for "MA Related" and "Investment Related" work
- Current employer highlighted
- Employer names and positions

### Municipal Advisor Firm Details
- Firm name and CIK
- SEC file number (link to SEC)
- Independent contractor badge
- Office locations (expandable)

### Disclosure Detail Panels
For each disclosure category, show individual questions with Yes/No answers:
- Group by severity (Critical, High, Medium, Low)
- Highlight any "Yes" answers prominently
- Provide context/explanation for each question

---

## Common Queries and Filters

For SAAS features, consider enabling filters by:

1. **Clean Record** - Filter where `disclosures.any() == False`
2. **Has Disclosures** - Filter where `disclosures.any() == True`
3. **Criminal Issues** - Filter by `criminal_disclosure.any()`
4. **Regulatory Issues** - Filter by `regulatory_disclosure.any()`
5. **Under Investigation** - Filter by `investigation_disclosure.is_investigated`
6. **MA Firm** - Filter by `municipal_advisor_offices[].firm_name`
7. **State** - Filter by office state
8. **Amendment vs New** - Filter by `is_amendment`

---

## Due Diligence Use Cases

### Red Flag Detection
```python
# Check for any disclosures
if ma_form.disclosures.any():
    print("WARNING: Applicant has disclosures")

# Check specific high-severity items
if ma_form.disclosures.criminal_disclosure.is_convicted_of_felony:
    print("CRITICAL: Felony conviction")

if ma_form.disclosures.regulatory_disclosure.is_association_bared:
    print("CRITICAL: Barred from association")
```

### Employment Verification
```python
# Get current employer
current = ma_form.employment_history.current_employer
print(f"Currently at: {current.name} as {current.position}")

# Check MA experience
for employer in ma_form.employment_history.previous_employers:
    if employer.ma_related:
        print(f"MA experience at: {employer.name}")
```

### Firm Association
```python
# List all MA firms
for office in ma_form.municipal_advisor_offices:
    print(f"Firm: {office.firm_name}")
    print(f"  CIK: {office.cik}")
    print(f"  File #: {office.file_number}")
    print(f"  Independent: {office.is_independent_relationship}")
```

---

## Data Quality Notes

1. **Disclosure answers** - All stored as booleans; `True` indicates a positive disclosure
2. **Employment dates** - Formatted as "Mon YYYY" (e.g., "Jun 2015")
3. **CRD numbers** - May be empty for new registrants
4. **Other names** - May include maiden names, aliases, prior legal names
5. **Multiple offices** - An individual may work at multiple MA firm offices

---

## Example Data Access

```python
# Get filing and parse
ma_form = filing.obj()

# Access applicant info
print(ma_form.applicant.full_name)
print(f"CRD: {ma_form.applicant.crd}")

# Check for disclosures (most important!)
if ma_form.disclosures.any():
    print("Has disclosures - review required")

    # Check specific categories
    if ma_form.disclosures.criminal_disclosure.any():
        print("  - Criminal disclosures present")
    if ma_form.disclosures.regulatory_disclosure.any():
        print("  - Regulatory disclosures present")
else:
    print("Clean record - no disclosures")

# Employment history
print(f"Current employer: {ma_form.employment_history.current_employer.name}")
for emp in ma_form.employment_history.previous_employers:
    print(f"  Previous: {emp.name} ({emp.start_date} - {emp.end_date})")

# MA firm associations
for office in ma_form.municipal_advisor_offices:
    print(f"Associated with: {office.firm_name}")

# Signature verification
print(f"Signed by: {ma_form.signature.signature} on {ma_form.signature.date_signed}")
```

---

## Form Variants

The `MunicipalAdvisorForm` class handles these form types:

| Form | Description |
|------|-------------|
| `MA-I` | Individual municipal advisor initial registration |
| `MA-I/A` | Amendment to individual registration |
| `MA` | Firm municipal advisor registration |
| `MA/A` | Amendment to firm registration |

Check `filing.form` or `is_amendment` to determine the filing type.
