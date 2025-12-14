# DEF 14A (Proxy Statement) Comprehensive Extraction Guide

**Research Date**: 2025-12-10
**Researcher**: SEC Filing Research Agent
**Sample Size**: 5 companies across diverse sectors (AAPL, MSFT, JPM, XOM, JNJ)
**Filing Dates**: 2025-01-10 to 2025-10-21

## Executive Summary

DEF 14A (Definitive Proxy Statement) filings contain rich, highly structured data about executive compensation, board of directors, corporate governance, and voting matters. **All sampled DEF 14A filings include XBRL data**, making them amenable to structured extraction via EdgarTools' XBRL API.

### Key Findings

- **XBRL Coverage**: 100% of sampled filings (5/5) include XBRL data
- **Common XBRL Concepts**: 25 concepts present across all companies
- **Primary Namespace**: `ecd:` (Executive Compensation Disclosure) - introduced by SEC in 2022
- **Data Availability**: Executive compensation, pay vs performance, and insider trading policies are highly standardized
- **HTML Sections**: All standard proxy sections present (compensation tables, beneficial ownership, proposals)

## Table of Contents

1. [Data Categories Overview](#data-categories-overview)
2. [XBRL Data Extraction](#xbrl-data-extraction)
3. [HTML Section Extraction](#html-section-extraction)
4. [Extraction Recommendations](#extraction-recommendations)
5. [Code Examples](#code-examples)
6. [Cross-Company Variations](#cross-company-variations)
7. [SaaS Application Recommendations](#saas-application-recommendations)

---

## Data Categories Overview

### 1. Executive Compensation

**Availability**: XBRL (highly structured) + HTML tables
**Standardization**: High - regulated by SEC Item 402
**Key Components**:
- Summary Compensation Table (3 years of data)
- Pay vs Performance disclosure (5 years of data)
- Compensation Actually Paid (CAP) calculation
- Named Executive Officers (NEOs)
- Principal Executive Officer (PEO) specific data

**XBRL Concepts Available** (present in all 5 companies):
```
ecd:PeoTotalCompAmt              - PEO total compensation (SCT)
ecd:PeoActuallyPaidCompAmt       - PEO compensation actually paid
ecd:NonPeoNeoAvgTotalCompAmt     - Average NEO total compensation (SCT)
ecd:NonPeoNeoAvgCompActuallyPaidAmt - Average NEO compensation actually paid
ecd:AdjToCompAmt                 - Adjustments to compensation (reconciliation)
ecd:PeoName                      - Name of PEO(s)
```

**Value Proposition**: Enables time-series analysis of executive pay, pay-for-performance alignment, and peer comparison.

### 2. Board of Directors Information

**Availability**: HTML narrative sections
**Standardization**: Medium - follows common patterns but not XBRL-tagged
**Key Components**:
- Director names, ages, backgrounds
- Committee memberships (Audit, Compensation, Governance)
- Director independence status
- Board tenure and diversity
- Director compensation (available in XBRL via pay vs performance disclosures)

**Extraction Approach**: HTML parsing with NLP for director bios and committee assignments.

### 3. Corporate Governance

**Availability**: HTML narrative + some XBRL flags
**Standardization**: Medium
**Key Components**:
- Board structure and leadership
- Committee charters
- Corporate governance guidelines
- Code of ethics and business conduct
- Related party transactions
- Audit committee report

**XBRL Concepts**:
```
ecd:InsiderTrdPoliciesProcAdoptedFlag - Insider trading policy adoption
```

### 4. Beneficial Ownership / Security Ownership

**Availability**: HTML tables (not in XBRL)
**Standardization**: Medium-High
**Section Presence**: 100% (found in all 5 companies)
**Key Components**:
- Principal shareholders (>5% ownership)
- Director and executive officer ownership
- Total shares owned and percent of class

**Extraction Approach**: HTML table parsing - look for tables near "beneficial ownership" or "security ownership" section headers.

### 5. Voting Matters and Proposals

**Availability**: HTML sections
**Standardization**: High - standardized proposal descriptions
**Section Presence**: 100% (all companies have "proposal" sections)
**Common Proposal Types**:
- Election of directors
- Ratification of auditors
- Say-on-pay (executive compensation approval)
- Shareholder proposals
- Equity plan approvals

**Extraction Approach**: Search for "PROPOSAL" headers in HTML, extract proposal number, title, and recommendation.

### 6. Pay vs Performance Metrics

**Availability**: XBRL (highly structured)
**Standardization**: Very High - mandated by SEC
**Time Series**: 5 years of data (2020-2024 in sampled filings)

**XBRL Concepts** (present in all companies):
```
ecd:TotalShareholderRtnAmt          - Company TSR
ecd:PeerGroupTotalShareholderRtnAmt - Peer group TSR
us-gaap:NetIncomeLoss               - Net income
ecd:CoSelectedMeasureAmt            - Company-selected performance measure
ecd:CoSelectedMeasureName           - Name of company-selected measure
ecd:MeasureName                     - Names of most important measures
```

**Value Proposition**: Enables analysis of pay-for-performance alignment and comparison to peer performance.

### 7. Audit Information

**Availability**: HTML sections
**Standardization**: Medium-High
**Section Presence**: Found in majority of filings
**Key Components**:
- Auditor name and fees (audit, tax, other services)
- Audit committee report
- Pre-approval policies

**Extraction Approach**: HTML section parsing near "audit" keywords.

---

## XBRL Data Extraction

### Universal XBRL Concepts (Present in ALL Companies)

The following 25 XBRL concepts are present in **all 5 sampled companies**, indicating high reliability for structured extraction:

#### Document Entity Information (DEI namespace)
```python
dei:AmendmentFlag           # Whether filing is an amendment
dei:DocumentType            # "DEF 14A"
dei:EntityCentralIndexKey   # Company CIK
dei:EntityRegistrantName    # Company legal name
```

#### Executive Compensation Disclosure (ECD namespace)

**Pay vs Performance Table:**
```python
ecd:PvpTableTextBlock                          # Pay vs Performance table (text block)
ecd:PeoTotalCompAmt                            # PEO total compensation from SCT
ecd:PeoActuallyPaidCompAmt                     # PEO compensation actually paid
ecd:NonPeoNeoAvgTotalCompAmt                   # Non-PEO NEO average total comp (SCT)
ecd:NonPeoNeoAvgCompActuallyPaidAmt            # Non-PEO NEO average actually paid
ecd:TotalShareholderRtnAmt                     # Company TSR
ecd:PeerGroupTotalShareholderRtnAmt            # Peer group TSR
ecd:CoSelectedMeasureAmt                       # Company-selected performance measure
ecd:CoSelectedMeasureName                      # Name of company-selected measure
```

**Compensation Reconciliation:**
```python
ecd:AdjToCompAmt                               # Adjustments to compensation
ecd:AdjToPeoCompFnTextBlock                    # PEO adjustment footnote
ecd:AdjToNonPeoNeoCompFnTextBlock              # Non-PEO NEO adjustment footnote
```

**Named Executives:**
```python
ecd:NamedExecutiveOfficersFnTextBlock          # NEO footnote
ecd:PeoName                                    # Name of PEO (with dimensions)
ecd:TabularListTableTextBlock                  # Tabular list (most important measures)
ecd:MeasureName                                # Performance measure names
```

**Other Disclosures:**
```python
ecd:InsiderTrdPoliciesProcAdoptedFlag          # Insider trading policy adopted
ecd:PeerGroupIssuersFnTextBlock                # Peer group issuers footnote
ecd:CompActuallyPaidVsTotalShareholderRtnTextBlock  # CAP vs TSR discussion
ecd:CompActuallyPaidVsNetIncomeTextBlock            # CAP vs Net Income discussion
ecd:CompActuallyPaidVsCoSelectedMeasureTextBlock    # CAP vs company measure discussion
```

**Financial Performance:**
```python
us-gaap:NetIncomeLoss                          # Net income (GAAP)
```

### XBRL Facts by Company (Sample Statistics)

| Company | Total Facts | Unique Concepts | Named Executives (dim) | Filing Date |
|---------|-------------|-----------------|------------------------|-------------|
| AAPL    | 84          | 26              | 5 (Tim Cook + 4 NEOs)  | 2025-01-10  |
| MSFT    | 73          | 26              | N/A (not dimensioned)  | 2025-10-21  |
| JPM     | 235         | 39              | 2 (Dimon, Pinto)       | 2025-04-07  |
| XOM     | 141         | 26              | N/A (not dimensioned)  | 2025-04-07  |
| JNJ     | 134         | 41              | 5 (Duato + 4 NEOs)     | 2025-03-12  |

**Key Observation**: Companies use dimensional data (`dim_ecd_IndividualAxis`) to tag individual executive compensation, but this is **not universal** (only 3/5 companies). For companies without dimensional tagging, compensation is aggregated (PEO vs Non-PEO NEO averages).

### XBRL Dimensional Data

**Dimensional Axes** (present when individual executive data is tagged):

```python
dim_ecd_ExecutiveCategoryAxis    # PEO vs Non-PEO NEO classification
dim_ecd_IndividualAxis           # Individual executive identifier (e.g., aapl:CookMember)
dim_ecd_AdjToCompAxis            # Type of compensation adjustment
dim_ecd_MeasureAxis              # Performance measure type
```

**Example**: Apple's XBRL includes individual executive members:
- `aapl:CookMember` (Tim Cook - PEO)
- `aapl:MaestriMember` (Luca Maestri - CFO)
- `aapl:AdamsMember` (Kate Adams)
- `aapl:OBrienMember` (Deirdre O'Brien)
- `aapl:WilliamsMember` (Jeff Williams)

### Company-Specific XBRL Extensions

Some companies include additional custom concepts:

**JPMorgan (JPM)** - 13 custom concepts:
```python
jpm:EquityAwardFairValueAssumptionsExpectedCommonStockPriceVolatility
jpm:EquityAwardFairValueAssumptionsExpectedDividendYield
jpm:EquityAwardFairValueAssumptionsRemainingExpectedLife
jpm:EquityAwardFairValueAssumptionsRiskFreeInterestRate
jpm:EquityAwardStrikePrice
jpm:StockPrice
jpm:StockPriceAverageOfHighAndLow
```

**Johnson & Johnson (JNJ)** - Award timing and MNPI disclosures:
```python
ecd:AwardTmgMnpiDiscTextBlock           # Award timing MNPI disclosure
ecd:MnpiDiscTimedForCompValFlag         # MNPI disclosure flag
ecd:AwardTmgPredtrmndFlag               # Predetermined award timing
ecd:AwardTmgMethodTextBlock             # Award timing method
ecd:AwardsCloseToMnpiDiscTableTextBlock # Awards close to MNPI table
ecd:AwardExrcPrice                      # Award exercise price
ecd:AwardGrantDateFairValue             # Grant date fair value
ecd:AwardUndrlygSecuritiesAmt           # Underlying securities amount
```

---

## HTML Section Extraction

### Standard Section Presence (across 5 companies)

| Section | Present | Extraction Difficulty |
|---------|---------|----------------------|
| Summary Compensation Table | 5/5 | Medium (tables) |
| Executive Compensation | 5/5 | Low (section text) |
| Director Compensation | 5/5 | Medium (tables) |
| Beneficial Ownership | 5/5 | Medium (tables) |
| Pay Versus Performance | 5/5 | Low (XBRL + tables) |
| Named Executive Officers | 5/5 | Low (text + XBRL) |
| Compensation Discussion & Analysis (CD&A) | 5/5 | High (narrative) |
| Board of Directors | 5/5 | Medium (structured narrative) |
| Corporate Governance | 5/5 | Medium (narrative) |
| Audit Committee | 5/5 | Medium (narrative + tables) |
| Proposals | 5/5 | Low-Medium (structured) |
| Outstanding Equity Awards | 4/5 | Medium (tables) |
| Pension Benefits | 3/5 | Medium (tables) |
| Nonqualified Deferred Compensation | 3/5 | Medium (tables) |
| Potential Payments Upon Termination | 3/5 | Medium (tables) |
| Security Ownership | 5/5 | Medium (tables) |
| Principal Shareholders | 5/5 | Medium (tables) |

### Section Identification Approach

**Method**: Search for section keywords in lowercase HTML text.

**Python Example**:
```python
html_content = filing.html()
html_lower = html_content.lower()

section_keywords = [
    'summary compensation table',
    'executive compensation',
    'director compensation',
    'beneficial ownership',
    'pay versus performance',
    'compensation discussion and analysis',
    'board of directors',
    'proposals'
]

sections_found = {}
for keyword in section_keywords:
    sections_found[keyword] = keyword in html_lower
```

### Table Extraction Challenges

**Finding**: Standard table search patterns (by headers/captions) did not reliably identify compensation tables in Apple's DEF 14A.

**Reason**: Modern proxy statements use complex HTML/CSS layouts with tables embedded in multi-column layouts, making simple header-based detection unreliable.

**Recommendation**:
1. **For XBRL-available data**: Use XBRL extraction (more reliable)
2. **For HTML tables**: Use context-aware search:
   - Find section headers first (e.g., "Summary Compensation Table")
   - Extract tables within the section
   - Validate table structure by checking for expected column patterns

### HTML Document Structure Observations

- **Total tables in Apple DEF 14A**: 321 tables
- **Many tables are layout tables**: Not data tables
- **Section navigation tables**: Table of contents, headers/footers
- **Data tables**: Embedded within sections, require context to identify

---

## Extraction Recommendations

### Priority 1: XBRL-First Approach for Compensation Data

**Recommended for**:
- Executive compensation (PEO and NEO aggregate data)
- Pay vs Performance metrics (5-year time series)
- Total Shareholder Return (company and peer group)
- Net Income
- Company-selected performance measures
- Insider trading policy adoption

**Advantages**:
- Highly reliable and structured
- Standardized across companies
- Multi-year time series (5 years)
- No HTML parsing complexity
- Supports dimensional analysis (when available)

**Limitations**:
- Individual executive detail varies by company (dimensional vs aggregated)
- Does not include narrative compensation discussion (CD&A)
- Missing some compensation components (detailed breakdown by executive)

### Priority 2: HTML Extraction for Non-XBRL Data

**Recommended for**:
- Beneficial ownership tables
- Board of Directors information
- Director biographies and backgrounds
- Committee memberships
- Voting proposals
- Audit fees
- Detailed compensation tables (individual executive breakdown)

**Approach**:
1. **Section Identification**: Search for standard section keywords
2. **Table Extraction**: Extract tables within identified sections
3. **Context Validation**: Verify table relevance using surrounding text
4. **Column Mapping**: Map table columns to expected data fields

### Priority 3: Hybrid Approach for Comprehensive Data

**Use Case**: SaaS application requiring both structured metrics and narrative context.

**Implementation**:
1. Extract XBRL for quantitative metrics (compensation amounts, TSR, performance measures)
2. Extract HTML for qualitative context (CD&A, governance policies, proposals)
3. Cross-reference XBRL named executives with HTML compensation tables
4. Validate consistency between XBRL and HTML data sources

---

## Code Examples

### Example 1: Extract Executive Compensation from XBRL

```python
from edgar import Company
import pandas as pd

# Get company and filing
company = Company("AAPL")
filing = company.get_filings(form="DEF 14A").head(1)[0]

# Get XBRL facts
xbrl = filing.xbrl()
facts_df = xbrl.facts.to_dataframe()

# Extract PEO compensation over time
peo_total = facts_df[facts_df['concept'] == 'ecd:PeoTotalCompAmt']
peo_actually_paid = facts_df[facts_df['concept'] == 'ecd:PeoActuallyPaidCompAmt']

# Sort by period and display
peo_comp = pd.merge(
    peo_total[['period_start', 'period_end', 'numeric_value']].rename(columns={'numeric_value': 'total_comp'}),
    peo_actually_paid[['period_end', 'numeric_value']].rename(columns={'numeric_value': 'actually_paid'}),
    on='period_end'
)
peo_comp = peo_comp.sort_values('period_end')

print("CEO Compensation (Summary Comp Table vs Actually Paid):")
print(peo_comp)

# Output:
#   period_start  period_end   total_comp  actually_paid
# 0   2020-09-27  2021-09-25   98,734,394    311,845,801
# 1   2021-09-26  2022-09-24   99,420,097    128,833,021
# 2   2022-09-25  2023-09-30   63,209,845    106,643,588
# 3   2023-10-01  2024-09-28   74,609,802    168,980,568
```

### Example 2: Extract Pay vs Performance Metrics

```python
from edgar import Company
import pandas as pd

company = Company("MSFT")
filing = company.get_filings(form="DEF 14A").head(1)[0]

xbrl = filing.xbrl()
facts_df = xbrl.facts.to_dataframe()

# Extract pay vs performance metrics
metrics = {
    'TSR': 'ecd:TotalShareholderRtnAmt',
    'Peer TSR': 'ecd:PeerGroupTotalShareholderRtnAmt',
    'Net Income': 'us-gaap:NetIncomeLoss',
    'PEO Comp': 'ecd:PeoActuallyPaidCompAmt'
}

pvp_data = {}
for label, concept in metrics.items():
    data = facts_df[facts_df['concept'] == concept]
    if len(data) > 0:
        pvp_data[label] = data[['period_end', 'numeric_value']].rename(
            columns={'numeric_value': label}
        )

# Merge all metrics by period
from functools import reduce
pvp_df = reduce(lambda left, right: pd.merge(left, right, on='period_end'), pvp_data.values())
pvp_df = pvp_df.sort_values('period_end')

print("Pay vs Performance (5-year trend):")
print(pvp_df)
```

### Example 3: Extract Named Executives with Dimensional Data

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="DEF 14A").head(1)[0]

xbrl = filing.xbrl()
facts_df = xbrl.facts.to_dataframe()

# Extract PEO names
peo_names = facts_df[facts_df['concept'] == 'ecd:PeoName']

if 'dim_ecd_IndividualAxis' in facts_df.columns:
    # Get unique executives
    executives = peo_names.groupby('dim_ecd_IndividualAxis')['value'].first()

    print("Named Executive Officers:")
    for exec_id, name in executives.items():
        print(f"  {name}: {exec_id}")

    # Output:
    # Named Executive Officers:
    #   Mr. Cook: aapl:CookMember
    #   Luca Maestri: aapl:MaestriMember
    #   Kate Adams: aapl:AdamsMember
    #   Deirdre O'Brien: aapl:OBrienMember
    #   Jeff Williams: aapl:WilliamsMember
else:
    print("Individual executive data not dimensionally tagged")
    print("Named executives:", peo_names['value'].unique())
```

### Example 4: Check for Standard HTML Sections

```python
from edgar import Company

company = Company("JPM")
filing = company.get_filings(form="DEF 14A").head(1)[0]

html_content = filing.html()
html_lower = html_content.lower()

# Define sections to search for
sections = {
    'Summary Compensation Table': 'summary compensation table',
    'Pay vs Performance': 'pay versus performance',
    'Beneficial Ownership': 'beneficial ownership',
    'Board of Directors': 'board of directors',
    'Proposals': 'proposal',
    'Audit Committee': 'audit committee',
    'Director Compensation': 'director compensation'
}

print("Section Availability:")
for section_name, keyword in sections.items():
    found = keyword in html_lower
    status = "✓ Found" if found else "✗ Not Found"
    print(f"  {status}: {section_name}")
```

### Example 5: Extract Company-Selected Performance Measures

```python
from edgar import Company

company = Company("XOM")
filing = company.get_filings(form="DEF 14A").head(1)[0]

xbrl = filing.xbrl()
facts_df = xbrl.facts.to_dataframe()

# Get company-selected measure name
measure_name = facts_df[facts_df['concept'] == 'ecd:CoSelectedMeasureName']
if len(measure_name) > 0:
    print(f"Company-Selected Performance Measure: {measure_name.iloc[0]['value']}")

# Get measure values over time
measure_values = facts_df[facts_df['concept'] == 'ecd:CoSelectedMeasureAmt']
measure_values = measure_values[['period_end', 'numeric_value']].sort_values('period_end')

print("\nMeasure Values (5 years):")
print(measure_values.to_string(index=False))

# Get list of most important measures
important_measures = facts_df[facts_df['concept'] == 'ecd:MeasureName']
if len(important_measures) > 0:
    print("\nMost Important Performance Measures:")
    for idx, row in important_measures.iterrows():
        print(f"  - {row['value']}")
```

---

## Cross-Company Variations

### XBRL Fact Count Variation

**Range**: 73 facts (MSFT) to 235 facts (JPM)

**Key Drivers of Variation**:
1. **Number of years reported**: All companies report 5 years, but some include more granular data
2. **Dimensional tagging**: Companies with individual executive dimensions have more facts
3. **Custom extensions**: JPM and JNJ include company-specific concepts (equity valuation assumptions, award timing)
4. **Multiple PEOs**: Companies with CEO transitions tag both PEOs

### Named Executive Tagging Approaches

**Approach 1: Dimensional Tagging** (AAPL, JPM, JNJ)
- Individual executives tagged using `dim_ecd_IndividualAxis`
- Each executive has a unique member (e.g., `aapl:CookMember`)
- Enables individual-level compensation extraction from XBRL

**Approach 2: Aggregated Reporting** (MSFT, XOM)
- Only aggregate metrics reported (PEO total, Non-PEO NEO average)
- Individual executive data only in HTML tables
- Simpler XBRL structure but less granular

### Company-Specific Concepts

**JPMorgan (JPM)**: Most extensive custom concepts (13 unique)
- Focus on equity award valuation methodology
- Detailed Black-Scholes assumptions
- Stock price information

**Johnson & Johnson (JNJ)**: MNPI and award timing disclosures
- Material Non-Public Information (MNPI) considerations
- Award timing methodologies
- Awards close to MNPI disclosures

**Recommendation**: For SaaS application, focus on universal concepts (25 common to all companies) for broad compatibility. Offer advanced features for company-specific data.

---

## SaaS Application Recommendations

### Feature Set: MVP (Minimum Viable Product)

**Data Sources**: XBRL only (high reliability, no HTML parsing)

**Features**:
1. **Executive Compensation Dashboard**
   - PEO total compensation (SCT) vs compensation actually paid
   - Non-PEO NEO average compensation
   - 5-year trend visualization

2. **Pay vs Performance Analysis**
   - Company TSR vs Peer Group TSR
   - Compensation Actually Paid vs TSR (correlation)
   - Compensation Actually Paid vs Net Income
   - Company-selected performance measure tracking

3. **Peer Comparison**
   - Compare executive compensation across peer companies
   - Benchmark TSR performance
   - Compare pay-for-performance alignment

4. **Time Series Analysis**
   - 5-year compensation trends
   - Year-over-year growth rates
   - Identify compensation spikes or reductions

**Technical Implementation**:
```python
# Core data extraction function
def extract_def14a_xbrl_data(ticker):
    company = Company(ticker)
    filing = company.get_filings(form="DEF 14A").head(1)[0]

    xbrl = filing.xbrl()
    facts_df = xbrl.facts.to_dataframe()

    # Extract key metrics
    data = {
        'ticker': ticker,
        'filing_date': filing.filing_date,
        'peo_comp': extract_concept_series(facts_df, 'ecd:PeoActuallyPaidCompAmt'),
        'neo_comp': extract_concept_series(facts_df, 'ecd:NonPeoNeoAvgCompActuallyPaidAmt'),
        'tsr': extract_concept_series(facts_df, 'ecd:TotalShareholderRtnAmt'),
        'peer_tsr': extract_concept_series(facts_df, 'ecd:PeerGroupTotalShareholderRtnAmt'),
        'net_income': extract_concept_series(facts_df, 'us-gaap:NetIncomeLoss'),
        'measure_name': extract_concept_value(facts_df, 'ecd:CoSelectedMeasureName'),
        'measure_values': extract_concept_series(facts_df, 'ecd:CoSelectedMeasureAmt')
    }

    return data
```

### Feature Set: Advanced

**Data Sources**: XBRL + HTML parsing

**Additional Features**:
1. **Individual Executive Profiles**
   - Detailed compensation breakdown by executive (when dimensionally tagged)
   - Career history and tenure
   - Committee memberships

2. **Beneficial Ownership Tracking**
   - Principal shareholders (>5%)
   - Director and executive holdings
   - Insider ownership changes over time

3. **Board Composition Analysis**
   - Director independence metrics
   - Board diversity (age, gender, background)
   - Committee structure and membership

4. **Voting Proposal Tracking**
   - Historical proposals and outcomes
   - Say-on-pay voting trends
   - Shareholder proposal analysis

5. **Governance Scoring**
   - Insider trading policy adoption
   - Board independence ratio
   - Pay-for-performance alignment score

**Technical Challenges**:
- HTML table parsing reliability
- NLP for director biographies
- Handling cross-company variation in table structures
- Entity resolution (matching executives across years)

### API Design Recommendation

**Endpoint Structure**:
```
GET /api/v1/companies/{ticker}/proxy/latest
GET /api/v1/companies/{ticker}/proxy/compensation
GET /api/v1/companies/{ticker}/proxy/pay-vs-performance
GET /api/v1/companies/{ticker}/proxy/board
GET /api/v1/companies/{ticker}/proxy/beneficial-ownership
GET /api/v1/companies/{ticker}/proxy/proposals
```

**Response Format** (example for compensation):
```json
{
  "ticker": "AAPL",
  "filing_date": "2025-01-10",
  "fiscal_year_end": "2024-09-28",
  "peo": {
    "name": "Mr. Cook",
    "total_compensation_sct": 74609802,
    "compensation_actually_paid": 168980568,
    "adjustments": [
      {"type": "Stock awards fair value", "amount": -58088946},
      {"type": "Fair value at vest", "amount": 75382825}
    ]
  },
  "neo_average": {
    "total_compensation_sct": 27178896,
    "compensation_actually_paid": 58633525
  },
  "performance_metrics": {
    "tsr": 31.2,
    "peer_tsr": 24.5,
    "net_income": 93736000000,
    "company_selected_measure": {
      "name": "Operating Cash Flow",
      "value": 118254000000
    }
  },
  "time_series": {
    "periods": [
      {"fiscal_year": 2024, "peo_cap": 168980568, "tsr": 31.2},
      {"fiscal_year": 2023, "peo_cap": 106643588, "tsr": 48.2},
      {"fiscal_year": 2022, "peo_cap": 128833021, "tsr": -27.7}
    ]
  }
}
```

### Data Quality Considerations

**Reliability Levels**:
- **High**: XBRL executive compensation, pay vs performance metrics
- **Medium**: HTML tables (beneficial ownership, director compensation)
- **Low**: Narrative sections (CD&A, governance policies)

**Validation Approach**:
1. Cross-validate XBRL compensation with HTML Summary Compensation Table
2. Check for consistency between PEO name in XBRL and HTML
3. Verify time series continuity (no gaps in 5-year data)
4. Flag unusual compensation changes (>100% year-over-year)

**Error Handling**:
- Handle missing dimensional data (fall back to aggregate metrics)
- Gracefully handle custom concepts (log but don't fail)
- Support both PEO and multiple PEO scenarios (CEO transitions)

---

## Appendix A: XBRL Concept Reference

### ECD Namespace (Executive Compensation Disclosure)

Complete list of concepts observed across 5 companies:

| Concept | Description | Present in |
|---------|-------------|------------|
| `ecd:PeoTotalCompAmt` | PEO total compensation (SCT) | 5/5 |
| `ecd:PeoActuallyPaidCompAmt` | PEO compensation actually paid | 5/5 |
| `ecd:NonPeoNeoAvgTotalCompAmt` | Non-PEO NEO average total comp | 5/5 |
| `ecd:NonPeoNeoAvgCompActuallyPaidAmt` | Non-PEO NEO average actually paid | 5/5 |
| `ecd:AdjToCompAmt` | Adjustments to compensation | 5/5 |
| `ecd:PeoName` | Name of PEO | 5/5 |
| `ecd:TotalShareholderRtnAmt` | Total shareholder return | 5/5 |
| `ecd:PeerGroupTotalShareholderRtnAmt` | Peer group TSR | 5/5 |
| `ecd:CoSelectedMeasureAmt` | Company-selected measure value | 5/5 |
| `ecd:CoSelectedMeasureName` | Company-selected measure name | 5/5 |
| `ecd:MeasureName` | Performance measure names | 5/5 |
| `ecd:InsiderTrdPoliciesProcAdoptedFlag` | Insider trading policy flag | 5/5 |
| `ecd:PvpTableTextBlock` | Pay vs Performance table | 5/5 |
| `ecd:TabularListTableTextBlock` | Tabular list table | 5/5 |
| `ecd:NamedExecutiveOfficersFnTextBlock` | NEO footnote | 5/5 |
| `ecd:PeerGroupIssuersFnTextBlock` | Peer group footnote | 5/5 |
| `ecd:AdjToPeoCompFnTextBlock` | PEO adjustment footnote | 5/5 |
| `ecd:AdjToNonPeoNeoCompFnTextBlock` | Non-PEO NEO adjustment footnote | 5/5 |
| `ecd:CompActuallyPaidVsTotalShareholderRtnTextBlock` | CAP vs TSR discussion | 5/5 |
| `ecd:CompActuallyPaidVsNetIncomeTextBlock` | CAP vs Net Income discussion | 5/5 |
| `ecd:CompActuallyPaidVsCoSelectedMeasureTextBlock` | CAP vs measure discussion | 5/5 |
| `ecd:TotalShareholderRtnVsPeerGroupTextBlock` | TSR vs peer discussion | 3/5 |
| `ecd:Additional402vDisclosureTextBlock` | Additional 402(v) disclosure | 2/5 |
| `ecd:AwardTmgMnpiDiscTextBlock` | Award timing MNPI disclosure | 2/5 |
| `ecd:MnpiDiscTimedForCompValFlag` | MNPI timed for comp value | 2/5 |
| `ecd:NonGaapMeasureDescriptionTextBlock` | Non-GAAP measure description | 1/5 |
| `ecd:EqtyAwrdsAdjFnTextBlock` | Equity awards adjustment footnote | 1/5 |

**Source**: SEC Executive Compensation Disclosure Taxonomy
**Effective Date**: 2023 proxy season (mandated for fiscal years ending on or after Dec 16, 2022)

---

## Appendix B: Sample Filing Details

| Company | Ticker | Filing Date | Accession | Fiscal Year End | XBRL Facts |
|---------|--------|-------------|-----------|-----------------|------------|
| Apple Inc. | AAPL | 2025-01-10 | 0001308179-25-000008 | 2024-09-28 | 84 |
| Microsoft | MSFT | 2025-10-21 | 0001193125-25-245150 | 2024-06-30 | 73 |
| JPMorgan Chase | JPM | 2025-04-07 | 0000019617-25-000321 | 2024-12-31 | 235 |
| ExxonMobil | XOM | 2025-04-07 | 0001193125-25-073986 | 2024-12-31 | 141 |
| Johnson & Johnson | JNJ | 2025-03-12 | 0000200406-25-000099 | 2024-12-29 | 134 |

**Sector Coverage**:
- Technology: AAPL, MSFT
- Financial Services: JPM
- Energy: XOM
- Healthcare: JNJ

---

## Appendix C: Research Methodology

### Sampling Approach
- **5 companies** selected across diverse sectors
- **Large-cap only** (S&P 100 constituents) for mature proxy statements
- **Most recent DEF 14A** filing as of 2025-12-10
- **XBRL analysis**: Complete fact extraction and concept mapping
- **HTML analysis**: Section identification and table structure examination

### Analysis Tools
- **EdgarTools** (v5.x): SEC filing retrieval and XBRL parsing
- **Python 3.11**: Data extraction and analysis
- **Pandas**: Data manipulation and summary statistics
- **BeautifulSoup**: HTML parsing and section detection

### Limitations
- **Sample size**: 5 companies (not exhaustive of all filing variations)
- **Time period**: 2025 proxy season only (may not reflect historical formats)
- **Company size**: Large-cap bias (small-cap filings may differ)
- **HTML parsing**: Limited to high-level section detection (detailed table extraction not fully tested)

### Future Research Recommendations
1. Expand sample to 20-30 companies (including mid-cap and small-cap)
2. Analyze historical DEF 14A filings (2020-2025) to identify format evolution
3. Test HTML table extraction algorithms on multiple company filings
4. Develop NLP models for director biography and CD&A analysis
5. Create validation dataset for pay-for-performance correlation analysis

---

## Related Research

- [Schedule 13D/13G Research](../ownership/2025-11-26-schedule-13d-13g-research.md) - Beneficial ownership filings
- [10-K Financial Statement Extraction](../10-k/) - Annual report financials
- [8-K Event Extraction](../8-k/) - Current events and material changes

---

**Document Version**: 1.0
**Last Updated**: 2025-12-10
**Next Review**: Upon SEC regulation changes or EdgarTools major version updates