# Schedule 13D/G XML Schema Reference

This document details the XML element structure for Schedule 13D and 13G submissions.

## Legend

- **Type**: Data type (`string`, `integer`, `date`, `boolean`, `decimal`, `NV` = no value/container)
- **Max Len**: Maximum character length
- **Max Occur**: Maximum occurrences allowed
- **13D/13G**: `m` = mandatory, `o` = optional, `NA` = not applicable

---

## Schedule 13D Structure

### Root Element

```xml
<edgarSubmission xmlns="http://www.sec.gov/edgar/schedule13d"
                 xmlns:com="http://www.sec.gov/edgar/common">
```

### Header Data

| Element Path | Type | Max Len | Max Occur | 13D | 13D/A |
|--------------|------|---------|-----------|-----|-------|
| `headerData` | NV | - | 1 | m | m |
| `headerData/submissionType` | string | - | 1 | m | m |
| `headerData/previousAccessionNumber` | string | 20 | 1 | NA | m |
| `headerData/filerInfo` | NV | - | 1 | m | m |
| `headerData/filerInfo/filer` | NV | - | 1 | m | m |
| `headerData/filerInfo/filer/filerCredentials` | NV | - | 1 | m | m |
| `headerData/filerInfo/filer/filerCredentials/cik` | string | 10 | 1 | m | m |
| `headerData/filerInfo/filer/filerCredentials/ccc` | string | 8 | 1 | m | m |
| `headerData/filerInfo/liveTestFlag` | string | - | 1 | m | m |
| `headerData/filerInfo/flags` | NV | - | 1 | m | m |
| `headerData/filerInfo/flags/overrideInternetFlag` | boolean | - | 1 | o | o |
| `headerData/filerInfo/contact` | NV | - | 1 | m | m |
| `headerData/filerInfo/contact/contactName` | string | 30 | 1 | m | m |
| `headerData/filerInfo/contact/contactPhoneNumber` | string | 20 | 1 | m | m |
| `headerData/filerInfo/contact/contactEmailAddress` | string | 80 | 1 | m | m |
| `headerData/filerInfo/notifications` | NV | - | 1 | o | o |
| `headerData/filerInfo/notifications/notificationEmailAddress` | string | 80 | 3 | o | o |

### Form Data - Cover Page Header

| Element Path | Type | Max Len | Max Occur | 13D | 13D/A |
|--------------|------|---------|-----------|-----|-------|
| `formData/coverPageHeader` | NV | - | 1 | m | m |
| `formData/coverPageHeader/amendmentNo` | string | 3 | 1 | NA | m |
| `formData/coverPageHeader/securitiesClassTitle` | string | 150 | 1 | m | m |
| `formData/coverPageHeader/dateOfEvent` | date | 17 | 1 | m | m |
| `formData/coverPageHeader/previouslyFiledFlag` | boolean | - | 1 | o | o |
| `formData/coverPageHeader/issuerInfo` | NV | - | 1 | m | m |
| `formData/coverPageHeader/issuerInfo/issuerCIK` | string | 10 | 1 | m | m |
| `formData/coverPageHeader/issuerInfo/issuerCUSIP` | string | 12 | 1 | m | m |
| `formData/coverPageHeader/issuerInfo/issuerName` | string | 150 | 1 | m# | m# |
| `formData/coverPageHeader/issuerInfo/address` | NV | - | 1 | m | m |
| `formData/coverPageHeader/issuerInfo/address/street1` | string | 40 | 1 | m | m |
| `formData/coverPageHeader/issuerInfo/address/street2` | string | 40 | 1 | o | o |
| `formData/coverPageHeader/issuerInfo/address/city` | string | 30 | 1 | m | m |
| `formData/coverPageHeader/issuerInfo/address/stateOrCountry` | string | 2 | 1 | m | m |
| `formData/coverPageHeader/issuerInfo/address/zipCode` | string | 10 | 1 | m | m |

### Authorized Persons (Optional)

| Element Path | Type | Max Len | Max Occur | 13D | 13D/A |
|--------------|------|---------|-----------|-----|-------|
| `formData/coverPageHeader/authorizedPersons` | NV | 40 | 1 | o | o |
| `authorizedPersons/notificationInfo` | NV | - | 100 | m | m |
| `notificationInfo/personName` | string | 30 | 1 | m | m |
| `notificationInfo/personPhoneNum` | string | 20 | 1 | m | m |
| `notificationInfo/personAddress` | NV | - | 1 | m | m |
| `personAddress/street1` | string | 40 | 1 | m | m |
| `personAddress/street2` | string | 40 | 1 | o | o |
| `personAddress/city` | string | 30 | 1 | m | m |
| `personAddress/stateOrCountry` | string | 2 | 1 | m | m |
| `personAddress/zipCode` | string | 10 | 1 | m | m |

### Reporting Persons (Schedule 13D)

| Element Path | Type | Max Len | Max Occur | 13D | 13D/A |
|--------------|------|---------|-----------|-----|-------|
| `formData/reportingPersons` | NV | - | 1 | m | m |
| `reportingPersons/reportingPersonInfo` | NV | - | 100 | m | m |
| `reportingPersonInfo/reportingPersonCIK` | string | 10 | 1 | o | o |
| `reportingPersonInfo/reportingPersonNoCIK` | string | 1 | 1 | o | o |
| `reportingPersonInfo/reportingPersonName` | string | 150 | 1 | m | m |
| `reportingPersonInfo/memberOfGroup` | string | 1 | 1 | o | o |
| `reportingPersonInfo/fundType` | string | 2 | 6 | m | o |
| `reportingPersonInfo/legalProceedings` | string | 1 | 1 | o | o |
| `reportingPersonInfo/citizenshipOrOrganization` | string | 2 | 1 | m | o |
| `reportingPersonInfo/soleVotingPower` | decimal | 17 | 1 | m | o |
| `reportingPersonInfo/sharedVotingPower` | decimal | 17 | 1 | m | o |
| `reportingPersonInfo/soleDispositivePower` | decimal | 17 | 1 | m | o |
| `reportingPersonInfo/sharedDispositivePower` | decimal | 17 | 1 | m | o |
| `reportingPersonInfo/aggregateAmountOwned` | decimal | 17 | 1 | m | o |
| `reportingPersonInfo/isAggregateExcludeShares` | string | 1 | 1 | o | o |
| `reportingPersonInfo/percentOfClass` | decimal | 5 | 1 | m | o |
| `reportingPersonInfo/typeOfReportingPerson` | string | 2 | 13 | m | o |
| `reportingPersonInfo/commentContent` | string | 20000 | 1 | o | o |

### Items 1-7 (Schedule 13D)

| Element Path | Type | Max Len | Max Occur | 13D | 13D/A |
|--------------|------|---------|-----------|-----|-------|
| `formData/items1To7` | NV | - | 1 | m | m |
| **Item 1** |||||
| `items1To7/item1` | NV | - | 1 | m | m |
| `item1/securityTitle` | string | 150 | 1 | m# | m# |
| `item1/issuerName` | string | 150 | 1 | m# | m# |
| `item1/issuerPrincipalAddress` | NV | - | 1 | m# | m# |
| `item1/commentText` | string | 20000 | 1 | o | o |
| **Item 2** |||||
| `items1To7/item2` | NV | - | 1 | m | o |
| `item2/filingPersonName` | string | 20000 | 1 | m | o |
| `item2/principalBusinessAddress` | string | 20000 | 1 | m | o |
| `item2/principalJob` | string | 20000 | 1 | m | o |
| `item2/hasBeenConvicted` | string | 20000 | 1 | m | o |
| `item2/convictionDescription` | string | 20000 | 1 | m | o |
| `item2/citizenship` | string | 2000 | 1 | m | o |
| **Item 3** |||||
| `items1To7/item3` | NV | - | 1 | m | o |
| `item3/fundsSource` | string | 20000 | 1 | m | o |
| **Item 4** |||||
| `items1To7/item4` | NV | - | 1 | m | o |
| `item4/transactionPurpose` | string | 20000 | 1 | m | o |
| **Item 5** |||||
| `items1To7/item5` | NV | - | 1 | m | o |
| `item5/percentageOfClassSecurities` | string | 20000 | 1 | m | o |
| `item5/numberOfShares` | string | 20000 | 1 | m | o |
| `item5/transactionDesc` | string | 20000 | 1 | m | o |
| `item5/listOfShareholders` | string | 20000 | 1 | m | o |
| `item5/date5PercentOwnership` | string | 20000 | 1 | m | o |
| **Item 6** |||||
| `items1To7/item6` | NV | - | 1 | m | o |
| `item6/contractDescription` | string | 20000 | 1 | m | o |
| **Item 7** |||||
| `items1To7/item7` | NV | - | 1 | m | o |
| `item7/filedExhibits` | string | 20000 | 1 | o | o |

### Signature (Schedule 13D)

| Element Path | Type | Max Len | Max Occur | 13D | 13D/A |
|--------------|------|---------|-----------|-----|-------|
| `formData/signatureInfo` | NV | - | 1 | m | m |
| `signatureInfo/signaturePerson` | NV | - | 100 | m | m |
| `signaturePerson/signatureReportingPerson` | string | 150 | 1 | m# | m# |
| `signaturePerson/signatureDetails` | NV | - | 50 | m | m |
| `signatureDetails/signature` | string | 150 | 1 | m | m |
| `signatureDetails/title` | string | 150 | 1 | m | m |
| `signatureDetails/date` | date | - | 1 | m | m |
| `signatureInfo/commentText` | string | 20000 | 1 | o | o |

---

## Schedule 13G Structure

### Root Element

```xml
<edgarSubmission xmlns="http://www.sec.gov/edgar/schedule13g"
                 xmlns:com="http://www.sec.gov/edgar/common">
```

### Header Data (Same as 13D)

Same structure as Schedule 13D header data.

### Form Data - Cover Page Header (13G)

| Element Path | Type | Max Len | Max Occur | 13G | 13G/A |
|--------------|------|---------|-----------|-----|-------|
| `formData/coverPageHeader` | NV | - | 1 | m | m |
| `coverPageHeader/amendmentNo` | integer | - | 1 | o | m |
| `coverPageHeader/securitiesClassTitle` | string | - | 1 | m | m |
| `coverPageHeader/eventDateRequiresFilingThisStatement` | date | - | 1 | m | m |
| `coverPageHeader/issuerInfo` | NV | - | 1 | m | m |
| `issuerInfo/issuerCik` | string | 10 | 1 | m | m |
| `issuerInfo/issuerName` | string | 150 | 1 | m | m |
| `issuerInfo/issuerCusip` | string | 12 | 1 | m | m |
| `issuerInfo/issuerPrincipalExecutiveOfficeAddress` | NV | - | 1 | m | m |
| `coverPageHeader/designateRulesPursuantThisScheduleFiled` | NV | - | 1 | o | o |
| `designateRulesPursuantThisScheduleFiled/designateRulePursuantThisScheduleFiled` | string | - | 3 | o | o |

### Cover Page Reporting Person Details (13G)

| Element Path | Type | Max Len | Max Occur | 13G | 13G/A |
|--------------|------|---------|-----------|-----|-------|
| `formData/coverPageHeaderReportingPersonDetails` | NV | - | 100 | m | m |
| `coverPageHeaderReportingPersonDetails/reportingCik` | string | 10 | 1 | o | o |
| `coverPageHeaderReportingPersonDetails/reportingCikNotPresentInEdgarFlag` | string | 1 | 1 | o | o |
| `coverPageHeaderReportingPersonDetails/reportingPersonName` | string | 150 | 1 | m | m |
| `coverPageHeaderReportingPersonDetails/memberGroup` | string | 1 | 1 | o | o |
| `coverPageHeaderReportingPersonDetails/citizenshipOrOrganization` | string | 2 | 1 | m | o |
| `coverPageHeaderReportingPersonDetails/reportingPersonBeneficiallyOwnedNumberOfShares` | NV | 17 | 1 | m | o |
| `reportingPersonBeneficiallyOwnedNumberOfShares/soleVotingPower` | decimal | 17 | 1 | m | o |
| `reportingPersonBeneficiallyOwnedNumberOfShares/sharedVotingPower` | decimal | 17 | 1 | m | o |
| `reportingPersonBeneficiallyOwnedNumberOfShares/soleDispositivePower` | decimal | 17 | 1 | m | o |
| `reportingPersonBeneficiallyOwnedNumberOfShares/sharedDispositivePower` | decimal | 17 | 1 | m | o |
| `coverPageHeaderReportingPersonDetails/reportingPersonBeneficiallyOwnedAggregateNumberOfShares` | decimal | 17 | 1 | m | o |
| `coverPageHeaderReportingPersonDetails/aggregateAmountExcludesCertainSharesFlag` | string | 1 | 1 | o | o |
| `coverPageHeaderReportingPersonDetails/classPercent` | decimal | 5 | 1 | m | o |
| `coverPageHeaderReportingPersonDetails/typeOfReportingPerson` | string | 2 | 14 | m | o |
| `coverPageHeaderReportingPersonDetails/comments` | string | 20000 | 1 | o | o |

### Items 1-10 (Schedule 13G)

| Element Path | Type | Max Len | Max Occur | 13G | 13G/A |
|--------------|------|---------|-----------|-----|-------|
| `formData/items` | NV | - | 1 | m | o |
| **Item 1** |||||
| `items/item1/issuerName` | string | 150 | 1 | m | o |
| `items/item1/issuerPrincipalExecutiveOfficeAddress` | string | 150 | 1 | m | o |
| **Item 2** |||||
| `items/item2/filingPersonName` | string | 20000 | 1 | m | o |
| `items/item2/principalBusinessOfficeOrResidenceAddress` | string | 20000 | 1 | m | o |
| `items/item2/citizenship` | string | 2000 | 1 | m | o |
| **Item 3** |||||
| `items/item3/notApplicableFlag` | string | 1 | 1 | m | o |
| `items/item3/typeOfPersonFiling` | string | 2 | 11 | m | o |
| `items/item3/otherTypeOfPersonFiling` | string | 20000 | 1 | m# | m# |
| **Item 4** |||||
| `items/item4/amountBeneficiallyOwned` | string | 20000 | 1 | m | o |
| `items/item4/classPercent` | string | 20000 | 1 | m | o |
| `items/item4/numberOfSharesPersonHas` | NV | - | 1 | m | o |
| `numberOfSharesPersonHas/solePowerOrDirectToVote` | string | 20000 | 1 | m | o |
| `numberOfSharesPersonHas/sharedPowerOrDirectToVote` | string | 20000 | 1 | m | o |
| `numberOfSharesPersonHas/solePowerOrDirectToDispose` | string | 20000 | 1 | m | o |
| `numberOfSharesPersonHas/sharedPowerOrDirectToDispose` | string | 20000 | 1 | m | o |
| **Item 5** |||||
| `items/item5/notApplicableFlag` | string | 1 | 1 | m | o |
| `items/item5/classOwnership5PercentOrLess` | string | 1 | 1 | m | o |
| **Item 6** |||||
| `items/item6/notApplicableFlag` | string | 1 | 1 | m | o |
| `items/item6/ownershipMoreThan5PercentOnBehalfOfAnotherPerson` | string | 20000 | 1 | m | o |
| **Item 7** |||||
| `items/item7/notApplicableFlag` | string | 1 | 1 | m | o |
| `items/item7/subsidiaryIdentificationAndClassification` | string | 20000 | 1 | m | o |
| **Item 8** |||||
| `items/item8/notApplicableFlag` | string | 1 | 1 | m | o |
| `items/item8/identificationAndClassificationOfGroupMembers` | string | 20000 | 1 | m | o |
| **Item 9** |||||
| `items/item9/notApplicableFlag` | string | 1 | 1 | m | o |
| `items/item9/groupDissolutionNotice` | string | 20000 | 1 | m | o |
| **Item 10** |||||
| `items/item10/notApplicableFlag` | string | 1 | 1 | m | o |
| `items/item10/certifications` | string | 2000 | 1 | m# | m# |

### Additional 13G Elements

| Element Path | Type | Max Len | Max Occur | 13G | 13G/A |
|--------------|------|---------|-----------|-----|-------|
| `formData/certifications` | string | 2000 | 1 | m# | m# |
| `formData/exhibitInfo` | string | 20000 | 1 | o | o |
| `formData/signatureInformation` | NV | - | 100 | m | m |
| `signatureInformation/reportingPersonName` | string | 150 | 1 | m | m |
| `signatureInformation/signatureDetails` | NV | - | 100 | m | m |
| `signatureDetails/signature` | string | 150 | 1 | m | m |
| `signatureDetails/title` | string | 150 | 1 | m | m |
| `signatureDetails/date` | date | - | 1 | m | m |
| `formData/signatureComments` | string | 20000 | 1 | o | o |

### Documents (Both 13D and 13G)

| Element Path | Type | Max Len | Max Occur | 13D/13G |
|--------------|------|---------|-----------|---------|
| `documents` | NV | - | 1 | o |
| `documents/document` | NV | - | unlimited | o |
| `document/conformedName` | string | 32 | 1 | o |
| `document/conformedDocumentType` | string | - | 1 | o |
| `document/description` | string | 255 | 1 | o |
| `document/contents` | string | - | 1 | o |

---

## Validation Rules

### Business Rules

1. **Filer CIK ≠ Issuer CIK**: The filer's CIK cannot be the same as the issuer's CIK
2. **Consistent Issuer Info**: Cover page header issuer information must match Item 1 issuer information
3. **Unique Reporting Persons**: No duplicate reporting person names allowed
4. **Signature Matching**: Each reporting person must have at least one signature
5. **Name Consistency**: Reporting person names must match between cover page and signature sections

### Schema Constraints

1. Elements must appear in the sequence defined by the schema
2. String values must not exceed maximum length
3. Choice list elements must use valid enumerated values
4. Mandatory elements must have non-empty values
5. Date, boolean, and decimal elements cannot have null/empty values
