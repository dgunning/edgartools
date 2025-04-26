# User Journeys for edgartools

## Introduction

This document outlines key user journeys for edgartools, focusing on how AI agents can handle technical aspects while helping human users achieve their goals. Each journey represents a common workflow that users might undertake when working with SEC data.

## Core User Personas

1. **Financial Analysts** - Evaluating investment opportunities
2. **Investors** - Researching companies and funds
3. **Data Scientists** - Building models from financial data
4. **Compliance Officers** - Monitoring regulatory filings
5. **Academic Researchers** - Studying market patterns

## Key User Journeys

### 1. Company Financial Analysis Journey

**User Goal**: Understand a company's financial health

**Journey Steps**:
1. Find a specific company by ticker
2. Retrieve latest 10-K/10-Q filings
3. Extract financial statements
4. Calculate key financial ratios
5. Compare with previous periods

**AI Agent Role**:
- Handle API calls to find company and retrieve filings
- Extract and structure financial data
- Calculate ratios automatically
- Present findings in digestible format

**edgartools Components**:
- Company API
- Filings API
- XBRL API for financial data extraction

### 2. Investment Fund Research Journey

**User Goal**: Analyze investment funds for allocation decisions

**Journey Steps**:
1. Find funds by ticker or name
2. Understand fund structure (series, share classes)
3. Analyze fund holdings and strategy
4. Compare fee structures across share classes
5. Review historical performance

**AI Agent Role**:
- Navigate fund hierarchy (company → series → classes)
- Extract holdings from 13F filings
- Organize comparison of multiple share classes
- Highlight key differences between funds

**edgartools Components**:
- Fund Entity API
- Specialized fund getters
- ThirteenF API for holdings

### 3. Insider Trading Analysis Journey

**User Goal**: Monitor insider transactions for investment signals

**Journey Steps**:
1. Find insider transactions for specific companies
2. Identify patterns in insider buying/selling
3. Research context around significant transactions
4. Correlate with stock price movements

**AI Agent Role**:
- Continuously monitor Form 4 filings
- Identify unusual transaction patterns
- Calculate aggregate insider activity
- Correlate with other company events

**edgartools Components**:
- Ownership API
- Filings API with form=["3", "4", "5"] filters
- Company API

### 4. SEC Filing Discovery Journey

**User Goal**: Find specific types of filings across companies

**Journey Steps**:
1. Define filing search criteria (type, date range)
2. Filter results to relevant companies
3. Preview and evaluate filing content
4. Extract key information
5. Save or export findings

**AI Agent Role**:
- Translate high-level search intent to specific API calls
- Handle pagination through large result sets
- Pre-screen filings for relevance
- Extract requested information from filings

**edgartools Components**:
- Filings API
- Filter methods
- Filing content extraction

### 5. Financial Data Extraction Journey

**User Goal**: Extract structured financial data for analysis

**Journey Steps**:
1. Locate specific financial filings
2. Extract XBRL data into usable format
3. Create time series of financial metrics
4. Generate financial ratios
5. Prepare data for visualization or modeling

**AI Agent Role**:
- Handle technical aspects of XBRL parsing
- Standardize data across reporting periods
- Calculate derived metrics
- Export to desired format

**edgartools Components**:
- XBRL API
- Financial statements extraction
- Company.financials

### 6. Fund Holdings Analysis Journey

**User Goal**: Analyze what stocks funds are holding

**Journey Steps**:
1. Identify target funds
2. Retrieve latest 13F filings
3. Extract portfolio holdings
4. Analyze sector allocations and top positions
5. Track changes over time

**AI Agent Role**:
- Process 13F data structures
- Calculate portfolio statistics
- Track position changes quarter-over-quarter
- Identify sector exposures

**edgartools Components**:
- Fund Entity API
- ThirteenF API
- Portfolio holdings extraction

### 7. Regulatory Filing Monitoring Journey

**User Goal**: Stay updated on new filings from watched companies

**Journey Steps**:
1. Create watchlist of companies
2. Monitor for new filing types of interest
3. Get alerts and summaries of significant filings
4. Extract key information from new filings

**AI Agent Role**:
- Periodically check for new filings
- Filter to relevant filing types
- Generate concise summaries
- Highlight notable changes or disclosures

**edgartools Components**:
- Filings API
- Company.get_filings()
- Filing.obj()

## AI Agent Implementation Considerations

1. **Contextual Understanding**:
   - Maintain awareness of the user's overall goal
   - Remember previous steps in multi-stage processes

2. **Technical Abstraction**:
   - Hide API complexity from the user
   - Handle batch operations and pagination
   - Manage rate limiting and caching

3. **Domain Knowledge Application**:
   - Apply financial domain knowledge to interpret data
   - Highlight unusual or significant findings
   - Suggest related analyses based on initial findings

4. **Output Adaptation**:
   - Tailor detail level to user expertise
   - Provide explanatory context for non-expert users
   - Format results appropriately (tables, charts, summaries)

5. **Progressive Refinement**:
   - Start with broad searches, then progressively refine
   - Suggest filters or parameters based on initial results
   - Learn from user feedback on relevance

This framework can guide the development of AI agents that effectively leverage edgartools to fulfill user needs, handling the technical complexity while focusing on delivering valuable insights.