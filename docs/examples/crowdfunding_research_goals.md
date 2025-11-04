# Crowdfunding Analysis Research Goals

## Overview
This document outlines research goals for analyzing SEC crowdfunding (Regulation CF) filings using EdgarTools. The primary objectives are to:
1. Develop AI-native workflows for working with crowdfunding data
2. Identify API improvements needed for effective crowdfunding analysis
3. Explore the specifics of Form C filings and their lifecycle

## Research Focus Areas

###1. Campaign Lifecycle Tracking  ⭐ (Current Focus)

**Goal**: Understand how to track a crowdfunding campaign from inception through completion or termination.

**Form C Lifecycle**:
```
Initial Filing (Form C)
    ↓
Amendments (Form C/A) - as needed
    ↓
Progress Updates (Form C-U) - at 50% and 100% of target
    ↓
Annual Reports (Form C-AR) - yearly compliance
    ↓
Termination (Form C-TR) - when campaign ends
```

**Research Questions**:
- How do we navigate between related filings for the same campaign?
- What data is available at each stage of the lifecycle?
- How can we visualize the campaign timeline?
- What status information can we derive (active, funded, terminated)?
- What's missing from the API for tracking campaigns end-to-end?

**API Capabilities to Explore**:
- `filing.related_filings()` - Get all filings with same file number
- `FormC` variants: C, C/A, C-U, C-U/A, C-AR, C-AR/A, C-TR
- File number tracking for campaign identification
- Data availability differences between form types

**Potential API Gaps**:
- No Campaign wrapper class to aggregate related filings
- No helper methods to identify campaign status
- Missing `progress_update` field in C-U forms
- No built-in timeline visualization
- No methods like `get_updates()` or `get_annual_reports()`

**Success Criteria**:
- [ ] Can retrieve all filings for a single campaign
- [ ] Can identify the current status of a campaign
- [ ] Can track progression through lifecycle stages
- [ ] Can access data from each stage appropriately
- [ ] Have documented what helper methods/classes would improve the workflow

---

### 2. Financial Analysis

**Goal**: Analyze offering amounts, funding progress, and financial metrics to understand campaign performance.

**Key Financial Data Points**:

**From Offering Information** (Form C, C-U):
- Target offering amount
- Maximum offering amount
- Price per security
- Number of securities offered
- Over-subscription handling
- Deadline date

**From Annual Report Disclosure** (Form C, C-U, C-AR):
- Total assets
- Cash and cash equivalents
- Accounts receivable
- Short-term debt
- Long-term debt
- Revenue
- Cost of goods sold
- Taxes paid
- Net income
- Number of employees

**Research Questions**:
- How do we calculate percent funded?
- How do financial metrics change year-over-year?
- What's the success rate (reaching target) across campaigns?
- How do we identify campaigns that exceeded their targets?
- What's the typical time to reach funding goals?
- How do we track amount raised at different progress points?

**Analysis Patterns to Develop**:
- Target vs. actual funding calculations
- Financial health scoring based on annual reports
- Success rate analytics across campaigns
- Time-to-funding metrics
- Revenue growth tracking
- Debt-to-equity analysis
- Geographic distribution of offerings

**Potential API Improvements**:
- `percent_funded()` property
- `days_to_deadline()` property
- `amount_raised` tracking from C-U updates
- `is_over_target()` helper
- `financial_trend()` for year-over-year comparison
- Aggregate statistics across multiple campaigns

**Success Criteria**:
- [ ] Can calculate funding progress
- [ ] Can compare financial metrics across years
- [ ] Can identify successful vs. unsuccessful campaigns
- [ ] Can analyze offering terms and pricing
- [ ] Can track financial health indicators
- [ ] Have identified what financial analysis helpers are needed

---

### 3. Document Content Extraction

**Goal**: Extract and analyze unstructured text from offering materials, business descriptions, and risk disclosures.

**Document Types in Crowdfunding Filings**:
- Offering circular (primary offering document)
- Business plan materials
- Financial statement exhibits
- Risk factor disclosures
- Use of proceeds descriptions
- Management team bios
- Market analysis documents

**Key Sections to Extract**:
- Company overview and business model
- Products and services description
- Use of proceeds (how funds will be used)
- Risk factors
- Competition analysis
- Market opportunity
- Management team and experience
- Terms of the offering

**Research Questions**:
- How do we access offering circular documents?
- Can we parse structured sections from HTML/text?
- How do we extract tables from financial exhibits?
- What document search capabilities exist?
- How do we identify and classify document types?
- Can we extract key business metrics from prose?

**Document Parsing Approaches**:
- Use `filing.attachments` to access all documents
- Use `filing.document()` for primary document
- Apply `Document.parse()` for structure extraction
- Use `DocumentSearch` for keyword/semantic search
- Section extraction strategies (pattern, TOC, hybrid)
- Table extraction from HTML

**Potential API Improvements**:
- Specialized parsing for offering circulars
- Pre-defined section extractors (use of proceeds, risks, etc.)
- Business description summarization
- Risk factor enumeration
- Management team parsing
- Industry/market classification from text

**Use Cases**:
- Sentiment analysis of business descriptions
- Risk factor comparison across campaigns
- Use of proceeds categorization
- Management team experience scoring
- Market opportunity assessment
- Competitive landscape analysis

**Success Criteria**:
- [ ] Can access offering circular and key documents
- [ ] Can extract major sections from offering materials
- [ ] Can search for specific topics across documents
- [ ] Can extract tables and structured data
- [ ] Can identify key business information programmatically
- [ ] Have documented what document parsing helpers are needed

---

### 4. Portal & Issuer Analysis

**Goal**: Analyze patterns across funding portals, compare issuer campaigns, and identify trends in the crowdfunding ecosystem.

**Funding Portal Analysis**:

**Portal Information Available**:
- Portal name
- Portal CIK
- Portal CRD number
- Commission file number

**Research Questions**:
- How many campaigns does each portal host?
- What's the success rate per portal?
- What types of industries do portals specialize in?
- How do offering terms vary by portal?
- What's the average funding amount by portal?
- Which portals have the most repeat issuers?

**Issuer Analysis**:

**Multi-Campaign Issuers**:
- Companies that run multiple crowdfunding campaigns
- Success patterns across campaigns
- Financial progression over time
- Learning effects (better terms in later campaigns)

**Research Questions**:
- How do we find all campaigns from the same issuer?
- What's the relationship between first and subsequent campaigns?
- Do issuers improve success rates over time?
- What's the typical time between campaigns?
- How do financial metrics evolve across campaigns?

**Ecosystem Analysis**:

**Macro Trends**:
- Industry distribution of campaigns
- Geographic concentration
- Seasonal patterns in filing activity
- Success rates over time
- Average offering amounts trending
- Portal market share evolution

**Research Questions**:
- What industries dominate crowdfunding?
- Which states have the most campaigns?
- Are success rates improving over time?
- How has the market evolved since Regulation CF launched?
- What's the distribution of offering amounts?
- What percentage of campaigns reach their targets?

**Query Capabilities Needed**:
- Filter campaigns by portal
- Filter campaigns by issuer CIK
- Filter by industry (via SIC code or text classification)
- Filter by jurisdiction
- Filter by offering amount ranges
- Filter by status (active, funded, terminated)
- Time series queries for trend analysis

**Potential API Improvements**:
- Portal-based campaign querying
- Issuer campaign history lookup
- Industry classification helpers
- Geographic analysis tools
- Time series aggregation methods
- Success rate calculation utilities
- Comparative analysis tools across portals

**Success Criteria**:
- [ ] Can retrieve all campaigns for a given portal
- [ ] Can find all campaigns from the same issuer
- [ ] Can classify campaigns by industry
- [ ] Can perform geographic analysis
- [ ] Can calculate ecosystem-wide statistics
- [ ] Have documented what query and analysis tools are needed

---

## Data Sources & Methodology

### Sample Data Selection

**Criteria for Rich Examples**:
- Complete lifecycle (C → C-U → C-AR → C-TR)
- Multiple progress updates
- Multi-year annual reports
- Successful funding (reached target)
- Well-documented offering materials

**Potential Sample Campaigns**:
- TBD: Identify 3-5 exemplar campaigns with rich data
- Include variety: successful/unsuccessful, different industries, different portals
- Document file numbers for easy reference

### Test Filings for Development
```python
# Example: Get Q4 2025 filings
filings = get_filings(form='C', filing_date='2025-10-01:2025-12-31')

# Example: Access specific filing
filing = filings[5]
formc = filing.obj()

# Example: Get lifecycle
related = filing.related_filings()
```

---

## API Improvement Tracking

As we work through these research goals, we'll document:

### Missing Data Fields
- [ ] `progress_update` field in C-U forms (from XML but not parsed)
- [ ] Amount raised at different milestones
- [ ] Campaign status indicators
- [ ] ???

### Missing Helper Methods
- [ ] `percent_funded()` - calculate funding progress
- [ ] `days_to_deadline()` - time remaining calculation
- [ ] `is_active()` - campaign status check
- [ ] `get_updates()` - fetch all C-U filings
- [ ] `get_annual_reports()` - fetch all C-AR filings
- [ ] ???

### Missing Classes/Abstractions
- [ ] `Campaign` class - wrapper for related filings lifecycle
- [ ] `FundingPortal` enhancements - portal-level analytics
- [ ] `CrowdfundingCampaigns` collection class - batch operations
- [ ] ???

### Missing Query Capabilities
- [ ] Filter by portal
- [ ] Filter by status
- [ ] Filter by amount raised
- [ ] Industry classification
- [ ] Geographic filters
- [ ] ???

### Document Parsing Gaps
- [ ] Offering circular specialized parsing
- [ ] Section extraction (use of proceeds, risks, etc.)
- [ ] Business description summarization
- [ ] ???

---

## Implementation Notes

### Current Script: `crowdfunding.py`

**Starting Point**:
- Uses existing filing from Q4 2025 (`filings[5]`)
- Incremental exploration approach
- Inline comments documenting API usability
- Pause after each step to discuss findings

**Development Process**:
1. Add code for each analysis step
2. Run and observe results
3. Discuss what works well and what's awkward
4. Document API gaps in comments
5. Note potential improvements
6. Continue to next step

**Documentation**:
- Keep detailed comments about developer experience
- Note "this was easy" and "this was hard" moments
- Document workarounds for missing features
- Capture ideas for helper methods/classes as they arise

---

## Next Steps

### Immediate (Current Session)
- [x] Create this research goals document
- [ ] Begin Focus Area 1: Campaign Lifecycle Tracking
- [ ] Develop `crowdfunding.py` incrementally
- [ ] Document findings as we go

### Short Term
- [ ] Complete lifecycle tracking exploration
- [ ] Identify top 5 API improvements needed
- [ ] Create sample "ideal API" code snippets
- [ ] Choose exemplar campaigns for future research

### Medium Term
- [ ] Explore Focus Area 2: Financial Analysis
- [ ] Explore Focus Area 3: Document Content Extraction
- [ ] Explore Focus Area 4: Portal & Issuer Analysis
- [ ] Compile comprehensive API improvement proposal

### Long Term
- [ ] Implement high-priority API improvements
- [ ] Create crowdfunding analytics dashboard example
- [ ] Develop specialized crowdfunding analysis tools
- [ ] Build ML models for campaign success prediction

---

## Resources

### SEC Regulations
- [Regulation Crowdfunding](https://www.sec.gov/education/smallbusiness/exemptofferings/regcrowdfunding)
- Form C Instructions: [SEC.gov](https://www.sec.gov/files/formc.pdf)

### EdgarTools Documentation
- Form C API: `edgar/offerings/formc.py`
- Filing access: `edgar/_filings.py`
- Document parsing: `edgar/documents/`

### Test Suite
- Tests: `tests/test_formc_offerings.py`
- Batch tests: `tests/batch/batch_formc.py`
- Sample data: `data/` directory

---

**Last Updated**: 2025-11-04
**Status**: Living document - updated as research progresses
