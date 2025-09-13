# Issue #434 Resolution Report: S-4 Filing XBRL Data Structure

## Issue Summary
User reported that when extracting financial data from an S-4 filing (Ares Acquisition Corp II merging with Kodiak Robotics), only Ares Acquisition Corp's financial statements were being returned, not Kodiak Robotics' financial data.

**Filing Details:**
- Company: Kodiak Robotics, Inc. (CIK: 1747286) 
- Filing: S-4 form dated 2025-05-14
- Accession: 0001193125-25-119920
- URL: https://www.sec.gov/Archives/edgar/data/1747286/000119312525119920/

## Investigation Findings

### 1. XBRL Structure Analysis
- **Single Entity XBRL**: The XBRL data contains only one entity identifier: `0001853138` (Ares Acquisition Corp II)
- **Financial Statements**: All financial statements (Income Statement, Balance Sheet, Cash Flow) contain only Ares Acquisition Corp's data
- **Entity Name**: XBRL entity name is "Ares Acquisition Corporation II", not Kodiak Robotics

### 2. Filing Content Analysis  
- **Total Attachments**: 76 documents in the filing
- **Exhibits Examined**: EX-99 series exhibits contain narrative references to Kodiak Robotics
- **Financial Data Location**: Kodiak's financial data is in exhibits as HTML/text, not structured XBRL
- **XBRL Files**: Only one XBRL package (0001193125-25-119920-xbrl.zip) containing Ares data

### 3. S-4 Filing Structure Understanding
S-4 forms are registration statements for business combinations where:
- **Registrant Entity**: Ares Acquisition Corp II is the registrant and filer
- **XBRL Requirements**: Only the registrant's financial statements are required in XBRL format
- **Target Company Data**: Kodiak Robotics financial data is typically included as exhibits in narrative/HTML format
- **Multiple Entity XBRL**: Not standard practice for S-4 filings

## Root Cause
**This is not a bug in EdgarTools.** This is expected behavior for S-4 filings:

1. **SEC Filing Standards**: S-4 forms require XBRL financial statements only from the registrant (Ares), not the target company (Kodiak)
2. **Entity Structure**: XBRL data is designed around a single primary entity per filing
3. **Target Company Financials**: Kodiak's financial information exists in the filing but in exhibit format (HTML), not as structured XBRL data

## User Expectation vs Reality
- **User Expected**: Both companies' financial statements in XBRL format
- **Actual Structure**: Only registrant's (Ares) financials in XBRL; target company (Kodiak) financials in exhibits
- **EdgarTools Behavior**: Correctly extracting the available XBRL financial data (Ares only)

## Recommendations for User

### 1. For Kodiak Robotics Financial Data
To get Kodiak Robotics' financial statements, the user should:
```python
# Look up Kodiak's own filings directly
kodiak_company = Company("Kodiak Robotics")  # or use their actual CIK
kodiak_filings = kodiak_company.get_filings(form=["10-K", "10-Q"])

# Or examine the S-4 exhibits manually
s4_filing = filings[0]
exhibits = s4_filing.attachments
# Look for EX-99 series exhibits containing Kodiak financial data
```

### 2. Understanding S-4 Filings
- S-4 XBRL contains only the **registrant's** financial statements
- Target company financials are in **exhibits** (usually HTML format)
- For structured financial data from target companies, examine their **separate SEC filings**

## Conclusion
**Status**: Not a bug - Expected behavior  
**Resolution**: Educational clarification provided  
**Action Required**: Update issue with explanation and mark as resolved  

The EdgarTools library is working correctly. The user's expectation about S-4 filing structure was incorrect. S-4 filings do not typically contain multiple entities' financial statements in XBRL format.