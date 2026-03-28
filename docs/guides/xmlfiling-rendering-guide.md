# XML Filing Rendering Guide

Rendering specifications for SEC XML filing types handled by `XmlFiling` and `FundFeeNotice`. Each form section describes the data layout, table structures, and display logic needed to render the filing in a downstream UI.

All forms share the same access pattern:

```python
filing.obj()        # returns XmlFiling or FundFeeNotice
obj.form_data       # nested dict of all form fields
obj['fieldName']    # deep key lookup
obj.to_html()       # SEC's official XSLT-rendered HTML (fallback reference)
obj.header_data     # submission metadata
```

Common header properties available on every `XmlFiling`:

| Property | Source |
|----------|--------|
| Form type | `obj.form` |
| Company name | `obj.company` |
| Filing date | `obj.filing_date` |
| Accession number | `obj.accession_number` |
| Is amendment | `obj.is_amendment` |
| Form description | `obj.description` |

---

## 24F-2NT — Annual Notice of Securities Sold

**Class:** `FundFeeNotice` (typed subclass of `XmlFiling`)
**Volume:** ~2,100/year
**Purpose:** Investment companies report annual fund sales, redemptions, and SEC registration fees.

### Header Card

| Field | Property | Example |
|-------|----------|---------|
| Fund Name | `notice.fund_name` | ADVISORS' INNER CIRCLE FUND |
| Fiscal Year End | `notice.fiscal_year_end` | 12/31/2025 |
| ICA File Number | `notice.investment_company_act_file_number` | 811-06400 |
| Filed Late | `notice.is_filed_late` | False |
| Final Filing | `notice.is_final_filing` | False |

**Display note:** Highlight `is_final_filing == True` — it signals the fund is deregistering.

### Fee Calculation Table

Render as a right-aligned financial table. This is the core data.

| Row Label | Property | Format | Example |
|-----------|----------|--------|---------|
| Aggregate Sales | `notice.aggregate_sales` | Currency | $418,915,624.00 |
| Redemptions (Current Year) | `notice.redemptions_current_year` | Currency | $309,040,895.54 |
| Redemptions (Prior Years) | `notice.redemptions_prior_years` | Currency | $0.00 |
| Total Redemption Credits | `notice.total_redemption_credits` | Currency | $309,040,895.54 |
| **Net Sales** | `notice.net_sales` | Currency, bold | **$109,874,728.46** |
| Fee Multiplier | `notice.fee_multiplier` | Decimal (7 places) | 0.0001381 |
| Registration Fee | `notice.registration_fee` | Currency | $15,173.70 |
| Interest Due | `notice.interest_due` | Currency, hide if 0 | $0.00 |
| **Total Due** | `notice.total_due` | Currency, bold | **$15,173.70** |

**Display notes:**
- All values are in full dollars (not thousands).
- Hide Interest Due row when zero.
- Bold Net Sales and Total Due as the summary figures.
- The formula is: `net_sales = aggregate_sales - total_redemption_credits`, then `registration_fee = net_sales * fee_multiplier`.

### Series Table

Render when `notice.series` is non-empty.

| Column | Source | Description |
|--------|--------|-------------|
| Series ID | `s.series_id` | EDGAR identifier (S000XXXXXX) |
| Series Name | `s.series_name` | Human-readable fund name |
| All Classes | `s.include_all_classes` | Boolean — whether all share classes included |

**Display note:** The financial figures in the Fee Calculation table are aggregated across all series — they are not per-series.

### Fund Address

Available via `notice.fund_address` (dict):

| Field | Key |
|-------|-----|
| Street | `street1` |
| City | `city` |
| State | `state` |
| Zip | `zipCode` |
| Country | `country` (code, e.g. `X1` = USA) |

---

## X-17A-5 — Broker-Dealer Financial Report

**Class:** `XmlFiling`
**Volume:** ~1,900/year
**Purpose:** Annual broker-dealer report filing. The XML is a cover sheet only — the actual financial statements are in an attached PDF.

### Header Card

| Field | Key Path | Example |
|-------|----------|---------|
| Broker-Dealer Name | `obj['brokerDealerName']` | ADVANCED ADVISOR GROUP, LLC |
| Registrant Type | `obj['typeOfBDRegistrant']` | Broker-dealer |
| Reporting Period Start | `obj['periodBegin']` | 01-01-2025 |
| Reporting Period End | `obj['periodEnd']` | 12-31-2025 |
| Material Weakness | `obj['materialWeakness']` | N |

### Business Address

| Field | Key Path |
|-------|----------|
| Street | `obj.form_data['registrantIdentification']['businessAddress']['street1']` |
| Street 2 | `...['street2']` |
| City | `...['city']` |
| State | `...['stateOrCountry']` |
| Zip | `...['zipCode']` |
| Contact | `obj['contactPersonName']` |
| Phone | `obj['contactPersonPhoneNumber']` |

### Accountant Information

| Field | Key Path |
|-------|----------|
| Accountant Name | `obj['accountantName']` |
| Type | `obj['accountantType']` (e.g. "Certified Public Accountant") |
| Address | `obj.form_data['accountantIdentification']['accountantAddress']` (same structure as above) |

### Signature

| Field | Key Path |
|-------|----------|
| Signed By | `obj['signPersonName']` |
| Title | `obj['oathTitle']` |
| Date | `obj['signDate']` |
| Entity | `obj['entityName']` |

**Display note:** The X-17A-5 XML is a cover form. The actual financial report is in an attached PDF (`filing.attachments` with `document_type='FULL'`). Consider linking to or displaying that PDF alongside the structured cover data.

---

## TA-1 — Transfer Agent Registration

**Class:** `XmlFiling`
**Volume:** ~55/year
**Purpose:** Initial registration or amendment for transfer agents (entities that maintain shareholder records).

### Registrant Card

| Field | Key Path | Example |
|-------|----------|---------|
| Entity Name | `obj['entityName']` | VALIC RETIREMENT SERVICES CO |
| Previous Name | `obj['previousEntityName']` | AIG RETIREMENT SERVICES CO |
| FINS Number | `obj['finsNumber']` | 502575 |
| Regulatory Agency | `obj['regulatoryAgency']` | SEC |
| Phone | `obj['telephoneNumber']` | 713-831-3150 |
| Is Self Transfer Agent | `obj['selfTransferAgent']` | N |
| Uses Service Company | `obj['engagedServiceCompany']` | N |

### Principal Office Address

| Field | Key Path |
|-------|----------|
| Street | `obj.form_data['registrant']['principalOfficeAddress']['street1']` |
| City | `...['city']` |
| State | `...['stateOrCountry']` |
| Zip | `...['zipCode']` |

### Control Persons Table

Source: `obj.form_data['independentRegistrant']['corporationPartnershipData']` (list)

| Column | Key | Example |
|--------|-----|---------|
| Entity/Person Name | `entityName` | The Variable Annuity Life Insurance Company (VALIC) |
| Relationship Start | `relationshipStartDate` | 11/18/1996 |
| Title/Status | `titleOrStatus` | Owner |
| Ownership Code | `ownershipCode` | E |
| Control Person | `controlPerson` | true |

### Disciplinary History

Source: `obj.form_data['disciplinaryHistory']`

Each sub-section (`felonyOrMisdemeanor`, `otherFelony`, `enjoinedInvestmentRelatedActivity`, `violationOfInvestmentRelatedRegulation`, `falseStatementOrOmission`) has:
- `involved`: Y/N
- If Y: detail records with `entityName`, `actionTitle`, `actionDate`, `courtOrBodyNameAndLocation`, `actionDescription`

**Display note:** Only render the disciplinary section when any `involved == "Y"`. Show the detail narrative when present.

---

## TA-2 — Transfer Agent Annual Report

**Class:** `XmlFiling`
**Volume:** ~160/year
**Purpose:** Annual operational update for registered transfer agents.

### Summary Card

This is a simple form with only three sections:

| Field | Key Path | Example |
|-------|----------|---------|
| Service Company Used | `obj.form_data['engagedServiceCompany']['serviceCompany']` | All |
| Service Company Name | `obj['entityName']` (under serviceCompanyTransferAgent) | Broadridge Corporate Issuer Solutions, LLC |
| Service Company File No. | `obj['fileNumber']` (under serviceCompanyTransferAgent) | 084-01007 |
| Regulatory Agency | `obj['regulatoryAgency']` | Securities and Exchange Commission |
| Amendment Filed | `obj['amendmentFiled']` | Not applicable |

### Signature

| Field | Key Path |
|-------|----------|
| Signed By | `obj['signatureName']` |
| Title | `obj['signatureTitle']` |
| Phone | `obj['signaturePhoneNumber']` |
| Date | `obj['signatureDate']` |

---

## TA-W — Transfer Agent Withdrawal

**Class:** `XmlFiling`
**Volume:** ~1/year
**Purpose:** Notice of withdrawal from transfer agent registration.

### Withdrawal Card

| Field | Key Path | Example |
|-------|----------|---------|
| Entity Name | `obj['entityName']` | Harbor Digital Transfer Agent LLC |
| File Number | `obj['fileNumber']` | 084-06655 |
| Reason | `obj['withdrawalDescription']` | Registrant never conducted any transfer agent functions... |
| Last Action Date | `obj['lastActionDate']` | 02/27/2020 |
| Future TA Functions | `obj['futureTransferAgentFunctions']` | N |

### Address

Standard address block under `obj.form_data['registrant']['businessAddress']`.

### Legal & Records

| Field | Key Path |
|-------|----------|
| Legal Actions Involved | `obj.form_data['legalAction']['involved']` |
| Unsatisfied Judgments | `obj.form_data['legalAction']['unsatisfiedJudgmentsInvolved']` |
| Successor Transfer Agents | `obj.form_data['documentRetention']['successorTransferAgents']` |

---

## MA — Municipal Advisor Firm Registration

**Class:** `XmlFiling`
**Volume:** ~240/year
**Purpose:** Registration for municipal advisor firms (not individuals — MA-I has its own typed parser).

### Firm Card

| Field | Key Path | Example |
|-------|----------|---------|
| Firm Name | `obj['firmName']` | SOUTHSTATE SECURITIES CORP. |
| CRD Number | `obj['firmCrdNumber']` | 6950 |
| IRS Number | `obj['irsNum']` | 62-0804968 |
| Website | `obj['primaryWebAddress']` | southstatesec.com |
| Employees | `obj['numberOfEmployees']` | 95 |
| MA Employees | `obj['employeesEngagedInMAA']` | 2 |
| Fiscal Year End | `obj['monthOfFiscalYearEnd']` | December |
| Date Organized | `obj['dateOfOrganization']` | 03-27-1969 |
| Jurisdiction | `obj.form_data['organizedJurisdiction']['stateOrCountry']` | TN |

### Principal Office Address

Source: `obj.form_data['principalOfficeAddress']['addressInfo']['address']`

Standard address fields: `street1`, `street2`, `city`, `stateOrCountry`, `zipCode`.
Phone: `obj.form_data['principalOfficeAddress']['phoneNumber']`

### Additional Offices Table

Source: `obj.form_data['additionalOffices']['additionalOffice']` (list)

Each entry has `officeInfo.addressInfo.address` (standard address) and `officeInfo.phoneNumber`.
Also has `addDeleteAmend` indicating whether this is an add/amend/delete action.

| Column | Key Path |
|--------|----------|
| Address | `entry['officeInfo']['addressInfo']['address']` |
| Phone | `entry['officeInfo']['phoneNumber']` |
| Action | `entry['addDeleteAmend']` — keys: `add`, `amend`, or `delete` |

### Chief Compliance Officer

Source: `obj.form_data['cco']`

| Field | Key Path |
|-------|----------|
| Name | `cco['name']` — `firstName`, `middleName`, `lastName` |
| Phone | `cco['phoneNumber']` |
| Email | `cco['email']` |
| Address | `cco['address']['address']` (standard) |

### Contact Person

Same structure as CCO under `obj.form_data['contactPerson']`, plus `titles.title`.

### Business Affiliates Table

Source: `obj.form_data['businessAffiliates']['businessAffiliate']` (list)

### Disclosure Answers

Source: `obj.form_data['disclosureAnswers']`

Sections: `criminalDisclosure`, `regulatoryActionDisclosure`, `civilJudicialActionDisclosure`.
Each section has Y/N flags. Only render detail if any flag is Y.

---

## MA-W — Municipal Advisor Withdrawal

**Class:** `XmlFiling`
**Volume:** ~7/year
**Purpose:** Notice of withdrawal from municipal advisor registration.

### Withdrawal Card

| Field | Key Path | Example |
|-------|----------|---------|
| Firm Name | `obj['fullLegalName']` | Warbird Municipal Advisors, LLC |
| File Number | `obj['fileNumber']` | 867-02349 |
| Advisory Contracts Outstanding | `obj['isAdvisoryContract']` | N |
| Unsatisfied Judgments | `obj['isUnsatisfiedJudgementsOrLiens']` | N |
| Prepaid Fees Received | `obj['isReceivedAnyPrepaidFee']` | N |
| Borrowed Not Repaid | `obj['isBorrowedNotRepaid']` | N |

### Contact Person

Source: `obj.form_data['contactPersonInfo']['nameAddressPhone']`

| Field | Key Path |
|-------|----------|
| Name | `individualName` — `firstName`, `middleName`, `lastName` |
| Address | `addressInfo.address` (standard) |
| Phone | `phoneNumber` |
| Email | `obj.form_data['contactPersonInfo']['email']` |

---

## CFPORTAL — Crowdfunding Portal Registration

**Class:** `XmlFiling`
**Volume:** ~6/year
**Purpose:** Registration for funding portals operating under Regulation Crowdfunding.

### Portal Card

| Field | Key Path | Example |
|-------|----------|---------|
| Portal Name | `obj['nameOfPortal']` | PicMii Crowdfunding LLC |
| IRS EIN | `obj['irsEmployerIdNumber']` | 84-3982617 |
| Contact Phone | `obj['portalContactPhone']` | 717-723-9145 |
| Contact Email | `obj['portalContactEmail']` | support@picmiicrowdfunding.com |
| Fiscal Year End | `obj['fiscalYearEnd']` | December |
| Previous Registrations | `obj['anyPreviousRegistrations']` | N |
| Foreign Registrations | `obj['anyForeignRegistrations']` | N |

### Portal Address

Source: `obj.form_data['identifyingInformation']['portalAddress']` — standard address fields.

### Other Names and Websites Table

Source: `obj.form_data['identifyingInformation']['otherNamesAndWebsiteUrls']` (list)

| Column | Key | Example |
|--------|-----|---------|
| Name | `otherNamesUsedPortal` | Highlander Crowdfunding |
| Website | `webSiteOfPortal` | www.highlander.ai |

### Organization

| Field | Key Path | Example |
|-------|----------|---------|
| Legal Status | `obj['legalStatusForm']` | Limited Liability Company |
| Jurisdiction | `obj['jurisdictionOrganization']` | PA |
| Date Incorporated | `obj['dateIncorporation']` | 06-03-2019 |

### Control Persons

Source: `obj.form_data['controlRelationships']['fullLegalNames']` (list)

Each entry has `fullLegalName` — render as a simple list of names.

### Escrow Agents Table

Source: `obj.form_data['escrowArrangements']['investorFundsContacts']` (list)

| Column | Key | Example |
|--------|-----|---------|
| Name | `investorFundsContactName` | Enterprise Bank and Trust |
| Phone | `investorFundsContactPhone` | 949-373-7335 |
| Address | `investorFundsAddress` (standard) | San Juan Capistrano, CA |

### Disclosures

Same pattern as MA: `criminalDisclosure`, `regulatoryActionDisclosure`, `civilJudicialActionDisclosure`, `financialDisclosure`. All Y/N flags. Only render detail when Y.

---

## SBSE — Security-Based Swap Entity Registration

**Class:** `XmlFiling`
**Volume:** ~4/year
**Purpose:** Registration of security-based swap dealers and major swap participants under Dodd-Frank.

### Entity Card

| Field | Key Path | Example |
|-------|----------|---------|
| Name | `obj['fullApplicantName']` | CAPITOLIS LIQUID GLOBAL MARKETS LLC |
| Tax ID | `obj['taxIdentificationNo']` | 88-4400323 |
| CIK | `obj['applicantCik']` | 0002094379 |
| Phone | `obj['businessTelephoneNumber']` | 646-831-5471 |
| Website | `obj['websiteUrl']` | capitolis.com |
| Is Swap Dealer | `obj['isSwapDealer']` | Y |
| Is Major Swap Participant | `obj['isSwapParticipant']` | N |
| Non-Resident Entity | `obj['isNonResidentEntity']` | N |
| Business Description | `obj['descriptionBusiness']` | (narrative text) |
| Legal Status | `obj['legalStatus']` | Limited Liability Company |
| State of Formation | `obj['stateOfFormation']` | DE |
| Date of Formation | `obj['dateOfFormation']` | 12-14-2022 |
| Fiscal Year End Month | `obj['monthApplicantFiscalEnds']` | January |

### Addresses

Main and mailing addresses under `applicantDataPageOne` — standard `street1`, `city`, `stateOrCountry`, `zipCode`.

### CCO and Contact

| Field | Source |
|-------|--------|
| Contact Name | `contactEmployee.contactEmployeeName` — `firstName`, `lastName` |
| Contact Title | `contactEmployee.title` |
| Contact Phone | `contactEmployee.phone` |
| Contact Email | `contactEmployee.emailAddress` |
| CCO Name | `chiefComplianceOfficer.officerName` — same structure |
| CCO Title/Phone/Email | Same pattern |

### Prudential Regulators

Source: `obj.form_data['applicant']['applicantDataPageTwo']['prudentialRegulators']['prudentialRegulator']` (list of strings)

Render as a bullet list. Examples: "The Federal Reserve Board", "The Federal Deposit Insurance Corporation".

### Disclosures

Spread across `applicantDataPageThree` and `applicantDataPageFour`:
- `criminalDisclosure` — standard Y/N flags
- `regulatoryActionDisclosure` — standard Y/N flags

---

## SBSE-A — Security-Based Swap Entity Annual Amendment

**Class:** `XmlFiling`
**Volume:** ~27/year
**Purpose:** Annual amendment to SBSE registration with updated personnel and business data.

Follows the same structure as SBSE with these additions:

### Schedule A — Principals Table

Source: `obj.form_data['scheduleA']['scheduleAInfo']` (list)

| Column | Key | Example |
|--------|-----|---------|
| Name | `individualName` — `firstName`, `middleName`, `lastName` | Robert Edward Lynch |
| Title/Status | `titleOrStatus` | Head of a Business Unit |
| Date Acquired | `dateTitleOrStatusAcquired` | 04/2020 |
| Date Began | `dateBeganWorking` | 11/2013 |
| Ownership Interest | `haveOwnershipInterest` | N |
| NFA ID | `nfaIdentificationNo` | 494793 |
| CRD Number | `crdNo` | 002981333 |

This is often the largest table in an SBSE-A — can have 20+ rows.

---

## SBSE-W — Security-Based Swap Entity Withdrawal

**Class:** `XmlFiling`
**Volume:** ~2/year
**Purpose:** Notice of withdrawal from SBSE registration.

### Withdrawal Card

| Field | Key Path | Example |
|-------|----------|---------|
| Name | `obj['fullName']` | CAPITOLIS LIQUID GLOBAL MARKETS LLC |
| Tax ID | `obj['irsEmplIdentNo']` | 88-4400323 |
| SEC File Number | `obj['secFileNumber']` | 026-00226 |
| Registration Type | `obj['registrationType']` | Security-based Swap Dealer |
| Date Ceased Business | `obj['dateCeasedBusiness']` | 02-26-2026 |
| Reason | `obj.form_data['sbseW']['reasonsToWithdraw']['reasonToWithdraw']` | Other |
| Description | `obj['description']` | (narrative) |
| Holds Collateral | `obj['isHoldCollateral']` | Y |
| Number of Counterparties | `obj['numberOfCounterparties']` | 6 |
| Amount of Money | `obj['amountOfMoney']` | 0.00 |
| Market Value | `obj['marketValue']` | 186093434.00 |

---

## ATS-N-C — ATS Cessation of Operations

**Class:** `XmlFiling`
**Volume:** ~2/year
**Purpose:** Notice that an Alternative Trading System is ceasing operations.

**Special case:** This form has all meaningful data in `header_data`, not `form_data`. The `formData` element is empty.

### Cessation Card

| Field | Source | Example |
|-------|--------|---------|
| ATS Name | `obj.header_data` → `filerInfo.filer.NMSStockATSName` | Luminex ATS |
| MPID | `obj.header_data` → `filerInfo.filer.MPID` | LMNX |
| CIK | `obj.header_data` → `filerInfo.filer.filerCredentials.cik` | 0001609177 |
| Date Cease to Operate | `obj.header_data['dateCeaseToOperate']` | 03/27/2026 |
| Contact Name | `obj.header_data` → `filerInfo.contact.contactName` | James C. Dolan |
| Contact Phone | `obj.header_data` → `filerInfo.contact.contactPhoneNumber` | 6172868082 |
| Contact Email | `obj.header_data` → `filerInfo.contact.contactEmailAddress` | james.dolan@levelmarkets.com |

**Display note:** Since `form_data` is empty, the generic `XmlFiling` Rich display will show no Form Data table. The rendering code should check `header_data` for ATS-N-C forms.

---

## Common Rendering Patterns

### Address Block

Many forms share the same address structure. Render as a compact block:

```
street1
street2 (if present)
city, stateOrCountry zipCode
```

State codes follow SEC conventions (two-letter US state codes, `X1` = USA for country field).

### Y/N Boolean Fields

XML booleans appear as `"Y"`, `"N"`, `"true"`, `"false"`. Render as:
- `Y` / `true` → checkmark or "Yes"
- `N` / `false` → dash or "No"

### Disclosure Sections

Most registration forms (MA, CFPORTAL, SBSE, TA-1) have disclosure sections with identical patterns:
- `criminalDisclosure` — felony/misdemeanor convictions and charges
- `regulatoryActionDisclosure` — SEC/regulatory actions
- `civilJudicialActionDisclosure` — injunctions and civil proceedings
- `financialDisclosure` — bankruptcy, liens, bonds

Default rendering: collapse all disclosures when all flags are N. Expand and highlight when any flag is Y, showing the detail narrative.

### Signature Block

Most forms end with a signature. Render as:

```
Signed by: [name]
Title:     [title]
Date:      [date]
```

### XSLT Fallback

Every form can be rendered via the SEC's XSLT endpoint as a fallback:

```python
html = obj.to_html()  # Returns the SEC's official HTML rendering
```

This is the authoritative rendering. Use it as a reference or as a "View original" link when the structured rendering above doesn't cover edge cases.
