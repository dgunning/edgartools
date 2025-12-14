# Proxy Statement (DEF 14A) Research

Research on SEC proxy statement filings (DEF 14A) for data extraction and SaaS application development.

## Research Documents

### Comprehensive Guides

- **[def-14a-comprehensive-guide.md](./def-14a-comprehensive-guide.md)** - Complete DEF 14A extraction guide
  - 100+ page comprehensive analysis
  - XBRL data structure and concepts
  - HTML section identification patterns
  - Extraction recommendations for SaaS applications
  - Sample data from 5 diverse companies (AAPL, MSFT, JPM, XOM, JNJ)
  - API design recommendations

### Code Examples

- **[def14a_extraction_examples.py](./def14a_extraction_examples.py)** - Working Python examples
  - Executive compensation extraction
  - Pay vs performance analysis
  - Named executive officer identification
  - Comprehensive data extraction
  - Peer group comparison

## Key Findings Summary

### XBRL Data Availability

- **100% of sampled DEF 14A filings include XBRL data** (5/5 companies)
- **25 universal XBRL concepts** present across all companies
- **5-year time series data** for compensation and performance metrics
- **Primary namespace**: `ecd:` (Executive Compensation Disclosure)

### Data Categories

1. **Executive Compensation** (XBRL - High reliability)
   - PEO and NEO compensation (Summary Comp Table)
   - Compensation Actually Paid (Pay vs Performance)
   - Multi-year compensation trends

2. **Pay vs Performance** (XBRL - Very high reliability)
   - Total Shareholder Return (TSR)
   - Peer Group TSR
   - Net Income
   - Company-selected performance measures

3. **Named Executives** (XBRL + HTML)
   - PEO identification
   - NEO list (individual or aggregate)
   - Dimensional tagging (when available)

4. **Beneficial Ownership** (HTML tables)
   - Principal shareholders (>5%)
   - Director and executive holdings

5. **Board of Directors** (HTML narrative)
   - Director information and backgrounds
   - Committee memberships
   - Independence status

6. **Voting Proposals** (HTML sections)
   - Proposal descriptions
   - Board recommendations
   - Historical voting results

## Quick Start

### Extract Executive Compensation

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="DEF 14A").head(1)[0]

xbrl = filing.xbrl()
facts_df = xbrl.facts.to_dataframe()

# Get CEO compensation
peo_comp = facts_df[facts_df['concept'] == 'ecd:PeoActuallyPaidCompAmt']
print(peo_comp[['period_end', 'numeric_value']])
```

### Run Full Examples

```bash
python def14a_extraction_examples.py
```

## Universal XBRL Concepts (Present in ALL companies)

Essential concepts for reliable extraction:

```python
# Executive Compensation
'ecd:PeoTotalCompAmt'                    # PEO total compensation (SCT)
'ecd:PeoActuallyPaidCompAmt'             # PEO compensation actually paid
'ecd:NonPeoNeoAvgTotalCompAmt'           # Non-PEO NEO average total
'ecd:NonPeoNeoAvgCompActuallyPaidAmt'    # Non-PEO NEO average actually paid

# Performance Metrics
'ecd:TotalShareholderRtnAmt'             # Company TSR
'ecd:PeerGroupTotalShareholderRtnAmt'    # Peer TSR
'us-gaap:NetIncomeLoss'                  # Net Income
'ecd:CoSelectedMeasureAmt'               # Company-selected measure

# Other
'ecd:PeoName'                            # Named executives
'ecd:InsiderTrdPoliciesProcAdoptedFlag'  # Insider trading policy
```

## SaaS Application Recommendations

### MVP (Minimum Viable Product)

**Data Source**: XBRL only (no HTML parsing)

**Features**:
- Executive compensation dashboard (5-year trends)
- Pay vs performance analysis
- Peer comparison and benchmarking
- TSR correlation analysis

**Implementation**: Use `extract_comprehensive_def14a_data()` function from examples

### Advanced Features

**Data Source**: XBRL + HTML parsing

**Additional Features**:
- Individual executive profiles (when dimensionally tagged)
- Beneficial ownership tracking
- Board composition analysis
- Voting proposal history
- Governance scoring

## Sample Companies Analyzed

| Company | Ticker | Sector | Filing Date | XBRL Facts |
|---------|--------|--------|-------------|------------|
| Apple Inc. | AAPL | Technology | 2025-01-10 | 84 |
| Microsoft | MSFT | Technology | 2025-10-21 | 73 |
| JPMorgan Chase | JPM | Financial | 2025-04-07 | 235 |
| ExxonMobil | XOM | Energy | 2025-04-07 | 141 |
| Johnson & Johnson | JNJ | Healthcare | 2025-03-12 | 134 |

## Research Methodology

- **Sample size**: 5 large-cap companies (diverse sectors)
- **Time period**: 2025 proxy season
- **Tools**: EdgarTools v5.x, Python 3.11, Pandas, BeautifulSoup
- **Analysis**: Complete XBRL fact extraction, HTML section identification, cross-company comparison

## Related Research

- [Schedule 13D/13G Research](../../ownership/) - Beneficial ownership filings
- [10-K Research](../../10-k/) - Annual report financials
- [8-K Research](../../8-k/) - Current events

## Research Metadata

- **Research Date**: 2025-12-10
- **Researcher**: SEC Filing Research Agent
- **Status**: Complete (v1.0)
- **Next Review**: Upon SEC regulation changes or major EdgarTools updates

## Files

```
proxy/
├── README.md                           # This file
├── def-14a-comprehensive-guide.md      # Comprehensive research document
└── def14a_extraction_examples.py       # Working code examples
```