# Schedule 13D/G XML Examples

This document provides complete XML examples for Schedule 13D and 13G submissions.

## Schedule 13D Example

```xml
<?xml version="1.0" ?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/schedule13d"
                 xmlns:com="http://www.sec.gov/edgar/common">
  <headerData>
    <submissionType>SCHEDULE 13D</submissionType>
    <filerInfo>
      <filer>
        <filerCredentials>
          <cik>0001685089</cik>
          <ccc>xxxxxxxx</ccc>
        </filerCredentials>
      </filer>
      <liveTestFlag>LIVE</liveTestFlag>
      <flags>
        <overrideInternetFlag>false</overrideInternetFlag>
      </flags>
      <contact>
        <contactName>John Smith</contactName>
        <contactPhoneNumber>2025551234</contactPhoneNumber>
        <contactEmailAddress>jsmith@example.com</contactEmailAddress>
      </contact>
      <notifications>
        <notificationEmailAddress>notify@example.com</notificationEmailAddress>
      </notifications>
    </filerInfo>
  </headerData>

  <formData>
    <coverPageHeader>
      <securitiesClassTitle>Common Stock, par value $0.001 per share</securitiesClassTitle>
      <dateOfEvent>05/22/2023</dateOfEvent>
      <previouslyFiledFlag>false</previouslyFiledFlag>
      <issuerInfo>
        <issuerCIK>0001315246</issuerCIK>
        <issuerCUSIP>04683R106</issuerCUSIP>
        <issuerName>Example Corp</issuerName>
        <address>
          <com:street1>123 Main Street</com:street1>
          <com:street2>Suite 100</com:street2>
          <com:city>New York</com:city>
          <com:stateOrCountry>NY</com:stateOrCountry>
          <com:zipCode>10001</com:zipCode>
        </address>
      </issuerInfo>
      <authorizedPersons>
        <notificationInfo>
          <personName>Jane Doe</personName>
          <personPhoneNum>2025555678</personPhoneNum>
          <personAddress>
            <com:street1>456 Oak Avenue</com:street1>
            <com:city>San Francisco</com:city>
            <com:stateOrCountry>CA</com:stateOrCountry>
            <com:zipCode>94102</com:zipCode>
          </personAddress>
        </notificationInfo>
      </authorizedPersons>
    </coverPageHeader>

    <reportingPersons>
      <reportingPersonInfo>
        <reportingPersonCIK>0001685089</reportingPersonCIK>
        <reportingPersonNoCIK>N</reportingPersonNoCIK>
        <reportingPersonName>ABC Investment Partners LP</reportingPersonName>
        <memberOfGroup>a</memberOfGroup>
        <fundType>WC</fundType>
        <legalProceedings>N</legalProceedings>
        <citizenshipOrOrganization>DE</citizenshipOrOrganization>
        <soleVotingPower>0.00</soleVotingPower>
        <sharedVotingPower>3026455.00</sharedVotingPower>
        <soleDispositivePower>0.00</soleDispositivePower>
        <sharedDispositivePower>3026455.00</sharedDispositivePower>
        <aggregateAmountOwned>3026455.00</aggregateAmountOwned>
        <isAggregateExcludeShares>N</isAggregateExcludeShares>
        <percentOfClass>7.5</percentOfClass>
        <typeOfReportingPerson>PN</typeOfReportingPerson>
      </reportingPersonInfo>
    </reportingPersons>

    <items1To7>
      <item1>
        <securityTitle>Common Stock, par value $0.001 per share</securityTitle>
        <issuerName>Example Corp</issuerName>
        <issuerPrincipalAddress>
          <com:street1>123 Main Street</com:street1>
          <com:street2>Suite 100</com:street2>
          <com:city>New York</com:city>
          <com:stateOrCountry>NY</com:stateOrCountry>
          <com:zipCode>10001</com:zipCode>
        </issuerPrincipalAddress>
        <commentText>Item 1 additional comments if any</commentText>
      </item1>
      <item2>
        <filingPersonName>ABC Investment Partners LP is a Delaware limited partnership.</filingPersonName>
        <principalBusinessAddress>789 Investment Drive, Suite 500, Boston, MA 02101</principalBusinessAddress>
        <principalJob>Investment management and advisory services</principalJob>
        <hasBeenConvicted>No</hasBeenConvicted>
        <convictionDescription>Not applicable</convictionDescription>
        <citizenship>United States</citizenship>
      </item2>
      <item3>
        <fundsSource>The Common Stock was acquired using working capital of the Reporting Persons.</fundsSource>
      </item3>
      <item4>
        <transactionPurpose>The Reporting Persons acquired the shares for investment purposes. The Reporting Persons may engage in discussions with management regarding strategy and operations.</transactionPurpose>
      </item4>
      <item5>
        <percentageOfClassSecurities>The Reporting Persons beneficially own 3,026,455 shares representing approximately 7.5% of the outstanding Common Stock.</percentageOfClassSecurities>
        <numberOfShares>3,026,455 shares of Common Stock</numberOfShares>
        <transactionDesc>See Schedule attached hereto as Exhibit 1.</transactionDesc>
        <listOfShareholders>Not applicable</listOfShareholders>
        <date5PercentOwnership>May 22, 2023</date5PercentOwnership>
      </item5>
      <item6>
        <contractDescription>Not applicable</contractDescription>
      </item6>
      <item7>
        <filedExhibits>Exhibit 1 - Transaction Schedule</filedExhibits>
      </item7>
    </items1To7>

    <signatureInfo>
      <signaturePerson>
        <signatureReportingPerson>ABC Investment Partners LP</signatureReportingPerson>
        <signatureDetails>
          <signature>/s/ John Smith</signature>
          <title>Managing Partner</title>
          <date>05/23/2023</date>
        </signatureDetails>
      </signaturePerson>
      <commentText>Signature comments if any</commentText>
    </signatureInfo>
  </formData>

  <documents>
    <com:document>
      <com:conformedName>exhibit1.txt</com:conformedName>
      <com:conformedDocumentType>EX-99</com:conformedDocumentType>
      <com:description>Transaction Schedule</com:description>
      <com:contents>VHJhbnNhY3Rpb24gU2NoZWR1bGUgQ29udGVudHM=</com:contents>
    </com:document>
  </documents>
</edgarSubmission>
```

---

## Schedule 13D/A (Amendment) Example

```xml
<?xml version="1.0" ?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/schedule13d"
                 xmlns:com="http://www.sec.gov/edgar/common">
  <headerData>
    <submissionType>SCHEDULE 13D/A</submissionType>
    <previousAccessionNumber>0001234567-23-000001</previousAccessionNumber>
    <filerInfo>
      <filer>
        <filerCredentials>
          <cik>0001685089</cik>
          <ccc>xxxxxxxx</ccc>
        </filerCredentials>
      </filer>
      <liveTestFlag>LIVE</liveTestFlag>
      <flags>
        <overrideInternetFlag>false</overrideInternetFlag>
      </flags>
      <contact>
        <contactName>John Smith</contactName>
        <contactPhoneNumber>2025551234</contactPhoneNumber>
        <contactEmailAddress>jsmith@example.com</contactEmailAddress>
      </contact>
    </filerInfo>
  </headerData>

  <formData>
    <coverPageHeader>
      <amendmentNo>1</amendmentNo>
      <securitiesClassTitle>Common Stock, par value $0.001 per share</securitiesClassTitle>
      <dateOfEvent>06/15/2023</dateOfEvent>
      <issuerInfo>
        <issuerCIK>0001315246</issuerCIK>
        <issuerCUSIP>04683R106</issuerCUSIP>
        <issuerName>Example Corp</issuerName>
        <address>
          <com:street1>123 Main Street</com:street1>
          <com:city>New York</com:city>
          <com:stateOrCountry>NY</com:stateOrCountry>
          <com:zipCode>10001</com:zipCode>
        </address>
      </issuerInfo>
    </coverPageHeader>

    <reportingPersons>
      <reportingPersonInfo>
        <reportingPersonCIK>0001685089</reportingPersonCIK>
        <reportingPersonName>ABC Investment Partners LP</reportingPersonName>
        <!-- Fields may be optional in amendments -->
      </reportingPersonInfo>
    </reportingPersons>

    <items1To7>
      <item1>
        <securityTitle>Common Stock, par value $0.001 per share</securityTitle>
        <issuerName>Example Corp</issuerName>
        <issuerPrincipalAddress>
          <com:street1>123 Main Street</com:street1>
          <com:city>New York</com:city>
          <com:stateOrCountry>NY</com:stateOrCountry>
          <com:zipCode>10001</com:zipCode>
        </issuerPrincipalAddress>
      </item1>
      <!-- Items 2-7 are optional in amendments -->
    </items1To7>

    <signatureInfo>
      <signaturePerson>
        <signatureReportingPerson>ABC Investment Partners LP</signatureReportingPerson>
        <signatureDetails>
          <signature>/s/ John Smith</signature>
          <title>Managing Partner</title>
          <date>06/16/2023</date>
        </signatureDetails>
      </signaturePerson>
    </signatureInfo>
  </formData>
</edgarSubmission>
```

---

## Schedule 13G Example

```xml
<?xml version="1.0" ?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/schedule13g"
                 xmlns:com="http://www.sec.gov/edgar/common">
  <headerData>
    <submissionType>SCHEDULE 13G</submissionType>
    <filerInfo>
      <filer>
        <filerCredentials>
          <cik>0001314805</cik>
          <ccc>xxxxxxxx</ccc>
        </filerCredentials>
      </filer>
      <liveTestFlag>LIVE</liveTestFlag>
      <contact>
        <contactName>Sarah Johnson</contactName>
        <contactPhoneNumber>2025556789</contactPhoneNumber>
        <contactEmailAddress>sjohnson@example.com</contactEmailAddress>
      </contact>
      <flags>
        <overrideInternetFlag>false</overrideInternetFlag>
      </flags>
    </filerInfo>
  </headerData>

  <formData>
    <coverPageHeader>
      <securitiesClassTitle>Class A Common Stock, par value $0.0001 per share</securitiesClassTitle>
      <eventDateRequiresFilingThisStatement>05/11/2023</eventDateRequiresFilingThisStatement>
      <issuerInfo>
        <issuerCik>0001118676</issuerCik>
        <issuerName>Target Corporation Inc.</issuerName>
        <issuerCusip>66573W107</issuerCusip>
        <issuerPrincipalExecutiveOfficeAddress>
          <com:street1>100 Corporate Drive</com:street1>
          <com:street2>Suite 200</com:street2>
          <com:city>New York</com:city>
          <com:stateOrCountry>NY</com:stateOrCountry>
          <com:zipCode>10174</com:zipCode>
        </issuerPrincipalExecutiveOfficeAddress>
      </issuerInfo>
      <designateRulesPursuantThisScheduleFiled>
        <designateRulePursuantThisScheduleFiled>Rule 13d-1(b)</designateRulePursuantThisScheduleFiled>
      </designateRulesPursuantThisScheduleFiled>
    </coverPageHeader>

    <coverPageHeaderReportingPersonDetails>
      <reportingCik>0001161286</reportingCik>
      <reportingCikNotPresentInEdgarFlag>N</reportingCikNotPresentInEdgarFlag>
      <reportingPersonName>First Trust Merger Arbitrage Fund</reportingPersonName>
      <memberGroup>b</memberGroup>
      <citizenshipOrOrganization>DE</citizenshipOrOrganization>
      <reportingPersonBeneficiallyOwnedNumberOfShares>
        <soleVotingPower>1237421.00</soleVotingPower>
        <sharedVotingPower>0.00</sharedVotingPower>
        <soleDispositivePower>1237421.00</soleDispositivePower>
        <sharedDispositivePower>0.00</sharedDispositivePower>
      </reportingPersonBeneficiallyOwnedNumberOfShares>
      <reportingPersonBeneficiallyOwnedAggregateNumberOfShares>1237421.00</reportingPersonBeneficiallyOwnedAggregateNumberOfShares>
      <aggregateAmountExcludesCertainSharesFlag>N</aggregateAmountExcludesCertainSharesFlag>
      <classPercent>10.5</classPercent>
      <typeOfReportingPerson>IV</typeOfReportingPerson>
    </coverPageHeaderReportingPersonDetails>

    <!-- Second reporting person example -->
    <coverPageHeaderReportingPersonDetails>
      <reportingCik>0001314805</reportingCik>
      <reportingCikNotPresentInEdgarFlag>N</reportingCikNotPresentInEdgarFlag>
      <reportingPersonName>First Trust Capital Management L.P.</reportingPersonName>
      <memberGroup>b</memberGroup>
      <citizenshipOrOrganization>DE</citizenshipOrOrganization>
      <reportingPersonBeneficiallyOwnedNumberOfShares>
        <soleVotingPower>10001.00</soleVotingPower>
        <sharedVotingPower>0.00</sharedVotingPower>
        <soleDispositivePower>10001.00</soleDispositivePower>
        <sharedDispositivePower>0.00</sharedDispositivePower>
      </reportingPersonBeneficiallyOwnedNumberOfShares>
      <reportingPersonBeneficiallyOwnedAggregateNumberOfShares>10001.00</reportingPersonBeneficiallyOwnedAggregateNumberOfShares>
      <aggregateAmountExcludesCertainSharesFlag>N</aggregateAmountExcludesCertainSharesFlag>
      <classPercent>5.2</classPercent>
      <typeOfReportingPerson>IA</typeOfReportingPerson>
      <comments>Additional comments about this reporting person.</comments>
    </coverPageHeaderReportingPersonDetails>

    <items>
      <item1>
        <issuerName>Target Corporation Inc.</issuerName>
        <issuerPrincipalExecutiveOfficeAddress>100 Corporate Drive, Suite 200, New York, NY 10174</issuerPrincipalExecutiveOfficeAddress>
      </item1>
      <item2>
        <filingPersonName>This Schedule 13G is being filed jointly by First Trust Merger Arbitrage Fund and First Trust Capital Management L.P.</filingPersonName>
        <principalBusinessOfficeOrResidenceAddress>225 W. Wacker Drive, Suite 2100, Chicago, IL 60606</principalBusinessOfficeOrResidenceAddress>
        <citizenship>United States</citizenship>
      </item2>
      <item3>
        <notApplicableFlag>N</notApplicableFlag>
        <typeOfPersonFiling>IV</typeOfPersonFiling>
        <typeOfPersonFiling>IA</typeOfPersonFiling>
      </item3>
      <item4>
        <amountBeneficiallyOwned>As investment adviser to the Client Accounts, FTCM has the authority to invest the funds of the Client Accounts in securities.</amountBeneficiallyOwned>
        <classPercent>10.5</classPercent>
        <numberOfSharesPersonHas>
          <solePowerOrDirectToVote>1237421.00</solePowerOrDirectToVote>
          <sharedPowerOrDirectToVote>0.00</sharedPowerOrDirectToVote>
          <solePowerOrDirectToDispose>1237421.00</solePowerOrDirectToDispose>
          <sharedPowerOrDirectToDispose>0.00</sharedPowerOrDirectToDispose>
        </numberOfSharesPersonHas>
      </item4>
      <item5>
        <notApplicableFlag>N</notApplicableFlag>
        <classOwnership5PercentOrLess>N</classOwnership5PercentOrLess>
      </item5>
      <item6>
        <notApplicableFlag>N</notApplicableFlag>
        <ownershipMoreThan5PercentOnBehalfOfAnotherPerson>See Item 4.</ownershipMoreThan5PercentOnBehalfOfAnotherPerson>
      </item6>
      <item7>
        <notApplicableFlag>N</notApplicableFlag>
        <subsidiaryIdentificationAndClassification>See Item 2.</subsidiaryIdentificationAndClassification>
      </item7>
      <item8>
        <notApplicableFlag>Y</notApplicableFlag>
      </item8>
      <item9>
        <notApplicableFlag>Y</notApplicableFlag>
      </item9>
    </items>

    <certifications>By signing below I certify that, to the best of my knowledge and belief, the securities referred to above were acquired and are held in the ordinary course of business and were not acquired and are not held for the purpose of or with the effect of changing or influencing the control of the issuer of the securities and were not acquired and are not held in connection with or as a participant in any transaction having that purpose or effect.</certifications>

    <exhibitInfo>No exhibits filed.</exhibitInfo>

    <signatureInformation>
      <reportingPersonName>First Trust Merger Arbitrage Fund</reportingPersonName>
      <signatureDetails>
        <signature>/s/ Sarah Johnson</signature>
        <title>Authorized Signatory</title>
        <date>05/12/2023</date>
      </signatureDetails>
    </signatureInformation>

    <signatureInformation>
      <reportingPersonName>First Trust Capital Management L.P.</reportingPersonName>
      <signatureDetails>
        <signature>/s/ Michael Brown</signature>
        <title>Chief Compliance Officer</title>
        <date>05/12/2023</date>
      </signatureDetails>
    </signatureInformation>

    <signatureComments>Additional signature comments if any.</signatureComments>
  </formData>

  <documents>
    <com:document>
      <com:conformedName>coverletter.txt</com:conformedName>
      <com:conformedDocumentType>COVER</com:conformedDocumentType>
      <com:contents>VGhpcyBpcyBjb3ZlciBsZXR0ZXI=</com:contents>
    </com:document>
  </documents>
</edgarSubmission>
```

---

## Key XML Patterns

### Address Elements

```xml
<address>
  <com:street1>123 Main Street</com:street1>
  <com:street2>Suite 100</com:street2>  <!-- Optional -->
  <com:city>New York</com:city>
  <com:stateOrCountry>NY</com:stateOrCountry>
  <com:zipCode>10001</com:zipCode>
</address>
```

### Voting/Dispositive Power Block

```xml
<reportingPersonBeneficiallyOwnedNumberOfShares>
  <soleVotingPower>1000000.00</soleVotingPower>
  <sharedVotingPower>0.00</sharedVotingPower>
  <soleDispositivePower>1000000.00</soleDispositivePower>
  <sharedDispositivePower>0.00</sharedDispositivePower>
</reportingPersonBeneficiallyOwnedNumberOfShares>
```

### Document Attachment

```xml
<documents>
  <com:document>
    <com:conformedName>filename.pdf</com:conformedName>
    <com:conformedDocumentType>EX-99</com:conformedDocumentType>
    <com:description>Description of document</com:description>
    <com:contents>BASE64_ENCODED_CONTENT</com:contents>
  </com:document>
</documents>
```

### Multiple Reporting Person Types

```xml
<!-- Can specify up to 13 (13D) or 14 (13G) types -->
<typeOfReportingPerson>IA</typeOfReportingPerson>
<typeOfReportingPerson>HC</typeOfReportingPerson>
```

### Escaping Special Characters

```xml
<!-- Use escape sequences for special characters -->
<issuerName>Smith &amp; Jones Inc.</issuerName>
<description>Values &lt; 100 and &gt; 0</description>
<title>"Managing Partner"</title>  <!-- Use &quot; if needed -->
```

---

## Common Mistakes to Avoid

1. **Wrong element order**: Elements must appear in the sequence defined by the schema
2. **Missing namespace prefix**: Use `com:` prefix for common elements like address
3. **Unescaped special characters**: Always escape `&`, `<`, `>`, `"`
4. **Whitespace in values**: Don't add line breaks inside element values
5. **Wrong date format**: Use `MM/DD/YYYY` format
6. **Missing mandatory fields**: Check schema for required elements per submission type
7. **CIK format**: Include leading zeros (10 characters total)
8. **Decimal format**: Use `.00` suffix for whole numbers (e.g., `1000.00`)
