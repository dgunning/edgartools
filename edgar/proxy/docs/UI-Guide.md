# Proxy Statement UI Guide

A practical guide for rendering proxy statement data in downstream applications, including how Company properties predict data availability.

## Data Availability Indicators

Before fetching proxy data, use Company properties to predict what data will be available.

### Filer Category Determines XBRL Availability

```python
company = Company("AAPL")

# These properties predict proxy XBRL data availability
company.filer_category           # Full FilerCategory object
company.is_large_accelerated_filer  # Public float >= $700M
company.is_accelerated_filer        # Public float >= $75M and < $700M
company.is_non_accelerated_filer    # Public float < $75M
company.is_smaller_reporting_company  # SRC qualification
company.is_emerging_growth_company    # EGC qualification
```

### XBRL Availability Matrix

| Filer Type | XBRL Required | Proxy Data Quality |
|------------|---------------|-------------------|
| Large Accelerated Filer | Yes | Full structured data |
| Accelerated Filer | Yes | Full structured data |
| Non-Accelerated Filer | No | Limited/None |
| Smaller Reporting Company | No | Limited/None |
| Emerging Growth Company | No | Limited/None |

### Pre-fetch Data Availability Check

```python
def get_proxy_data_expectation(company: Company) -> dict:
    """Predict what proxy data will be available before fetching."""
    return {
        'will_have_xbrl': company.is_large_accelerated_filer or company.is_accelerated_filer,
        'filer_status': _get_filer_status_label(company),
        'data_quality': 'full' if (company.is_large_accelerated_filer or company.is_accelerated_filer) else 'limited',
        'show_compensation_tables': company.is_large_accelerated_filer or company.is_accelerated_filer,
        'show_pvp_charts': company.is_large_accelerated_filer or company.is_accelerated_filer,
    }

def _get_filer_status_label(company: Company) -> str:
    if company.is_large_accelerated_filer:
        return "Large Accelerated Filer"
    elif company.is_accelerated_filer:
        return "Accelerated Filer"
    elif company.is_smaller_reporting_company:
        return "Smaller Reporting Company"
    elif company.is_emerging_growth_company:
        return "Emerging Growth Company"
    else:
        return "Non-Accelerated Filer"
```

## Company Screen: Proxy Data Supplement

Add these proxy-related elements to your Company detail screen.

### Company Header Enhancement

```python
company = Company("AAPL")

# Data for company header/summary
company_header_data = {
    'name': company.name,
    'ticker': company.get_ticker(),
    'cik': company.cik,
    'industry': company.industry,
    'sic_code': company.sic,

    # Filer classification (affects proxy data)
    'filer_category': company.filer_category.status.value,
    'is_large_accelerated': company.is_large_accelerated_filer,
    'is_src': company.is_smaller_reporting_company,
    'is_egc': company.is_emerging_growth_company,

    # These affect filing deadlines
    'filing_deadline_days': _get_10k_deadline_days(company),
}

def _get_10k_deadline_days(company: Company) -> int:
    """10-K filing deadline after fiscal year end."""
    if company.is_large_accelerated_filer:
        return 60
    elif company.is_accelerated_filer:
        return 75
    else:
        return 90
```

### Filer Status Badge

Display a badge/chip showing filer classification:

```python
def get_filer_badge(company: Company) -> dict:
    """Get badge configuration for filer status display."""
    if company.is_large_accelerated_filer:
        return {
            'label': 'Large Accelerated',
            'color': 'blue',
            'tooltip': 'Public float >= $700M. Full proxy disclosures required.',
            'icon': 'building-2'
        }
    elif company.is_accelerated_filer:
        return {
            'label': 'Accelerated',
            'color': 'green',
            'tooltip': 'Public float >= $75M. Full proxy disclosures required.',
            'icon': 'building'
        }
    elif company.is_smaller_reporting_company:
        return {
            'label': 'SRC',
            'color': 'orange',
            'tooltip': 'Smaller Reporting Company. Reduced disclosure requirements.',
            'icon': 'home'
        }
    elif company.is_emerging_growth_company:
        return {
            'label': 'EGC',
            'color': 'purple',
            'tooltip': 'Emerging Growth Company. Phased-in disclosure requirements.',
            'icon': 'rocket'
        }
    else:
        return {
            'label': 'Non-Accelerated',
            'color': 'gray',
            'tooltip': 'Public float < $75M. Reduced disclosure requirements.',
            'icon': 'store'
        }
```

### Quick Proxy Summary on Company Screen

```python
def get_proxy_summary_for_company(company: Company) -> dict:
    """Get proxy summary data to display on company screen."""
    filing = company.get_filings(form="DEF 14A").latest()

    if not filing:
        return {'available': False, 'reason': 'No proxy filing found'}

    proxy = filing.obj()

    if not proxy.has_xbrl:
        return {
            'available': False,
            'reason': 'No structured data (company exempt from XBRL requirements)',
            'filing_url': filing.homepage_url,
            'filing_date': str(filing.filing_date)
        }

    return {
        'available': True,
        'filing_date': proxy.filing_date,
        'fiscal_year_end': proxy.fiscal_year_end,
        'ceo_name': proxy.peo_name,
        'ceo_total_comp': float(proxy.peo_total_comp) if proxy.peo_total_comp else None,
        'ceo_actually_paid': float(proxy.peo_actually_paid_comp) if proxy.peo_actually_paid_comp else None,
        'company_tsr': float(proxy.total_shareholder_return) if proxy.total_shareholder_return else None,
        'has_detailed_data': True
    }
```

## Proxy Statement Screen

### Screen Data Model

```python
def get_proxy_screen_data(company: Company) -> dict:
    """Get all data needed to render a proxy statement screen."""
    filing = company.get_filings(form="DEF 14A").latest()

    if not filing:
        return {'error': 'no_filing', 'message': 'No DEF 14A filing found'}

    proxy = filing.obj()

    return {
        # Header section
        'header': _get_header_data(proxy, company),

        # Executive compensation section
        'compensation': _get_compensation_data(proxy),

        # Pay vs performance section
        'pay_vs_performance': _get_pvp_data(proxy),

        # Governance section
        'governance': _get_governance_data(proxy),

        # Data availability flags
        'flags': {
            'has_xbrl': proxy.has_xbrl,
            'has_individual_exec_data': proxy.has_individual_executive_data,
            'has_compensation_data': proxy.peo_total_comp is not None,
            'has_pvp_data': proxy.total_shareholder_return is not None,
        },

        # Links
        'links': {
            'filing_url': filing.homepage_url,
            'sec_url': f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={company.cik}&type=DEF%2014A"
        }
    }
```

### Header Section

```python
def _get_header_data(proxy, company: Company) -> dict:
    return {
        'company_name': proxy.company_name or company.name,
        'ticker': company.get_ticker(),
        'form_type': proxy.form,
        'is_amendment': '/A' in proxy.form,
        'filing_date': proxy.filing_date,
        'fiscal_year_end': proxy.fiscal_year_end,
        'cik': proxy.cik,
        'accession_number': proxy.accession_number,

        # Filer context
        'filer_status': _get_filer_status_label(company),
        'is_large_accelerated': company.is_large_accelerated_filer,
    }
```

### Executive Compensation Section

```python
def _get_compensation_data(proxy) -> dict:
    if not proxy.has_xbrl:
        return {'available': False}

    # Current year summary
    current_year = {
        'peo_name': proxy.peo_name,
        'peo_total_comp': _format_currency(proxy.peo_total_comp),
        'peo_total_comp_raw': float(proxy.peo_total_comp) if proxy.peo_total_comp else None,
        'peo_actually_paid': _format_currency(proxy.peo_actually_paid_comp),
        'peo_actually_paid_raw': float(proxy.peo_actually_paid_comp) if proxy.peo_actually_paid_comp else None,
        'neo_avg_total': _format_currency(proxy.neo_avg_total_comp),
        'neo_avg_total_raw': float(proxy.neo_avg_total_comp) if proxy.neo_avg_total_comp else None,
        'neo_avg_actually_paid': _format_currency(proxy.neo_avg_actually_paid_comp),
        'neo_avg_actually_paid_raw': float(proxy.neo_avg_actually_paid_comp) if proxy.neo_avg_actually_paid_comp else None,
    }

    # 5-year time series for table/chart
    comp_df = proxy.executive_compensation
    time_series = []

    if not comp_df.empty:
        for _, row in comp_df.iterrows():
            time_series.append({
                'fiscal_year_end': str(row['fiscal_year_end']),
                'year': _extract_year(row['fiscal_year_end']),
                'peo_total_comp': _safe_float(row['peo_total_comp']),
                'peo_actually_paid': _safe_float(row['peo_actually_paid_comp']),
                'neo_avg_total': _safe_float(row['neo_avg_total_comp']),
                'neo_avg_actually_paid': _safe_float(row['neo_avg_actually_paid_comp']),
            })

    # Named executives (if available)
    named_execs = []
    if proxy.has_individual_executive_data:
        for exec in proxy.named_executives:
            named_execs.append({
                'name': exec.name,
                'role': exec.role,
                'total_comp': _safe_float(exec.total_comp),
                'actually_paid': _safe_float(exec.actually_paid_comp),
            })

    return {
        'available': True,
        'current_year': current_year,
        'time_series': time_series,
        'named_executives': named_execs,
        'has_named_executives': len(named_execs) > 0,
    }
```

### Pay vs Performance Section

```python
def _get_pvp_data(proxy) -> dict:
    if not proxy.has_xbrl:
        return {'available': False}

    # Current year metrics
    current_metrics = {
        'company_tsr': _safe_float(proxy.total_shareholder_return),
        'peer_group_tsr': _safe_float(proxy.peer_group_tsr),
        'tsr_vs_peer': _calculate_tsr_diff(proxy),
        'net_income': _format_currency(proxy.net_income),
        'net_income_raw': _safe_float(proxy.net_income),
        'company_measure_name': proxy.company_selected_measure,
        'company_measure_value': _format_currency(proxy.company_selected_measure_value),
        'company_measure_value_raw': _safe_float(proxy.company_selected_measure_value),
    }

    # Performance measures list
    performance_measures = proxy.performance_measures

    # 5-year time series for charts
    pvp_df = proxy.pay_vs_performance
    time_series = []

    if not pvp_df.empty:
        for _, row in pvp_df.iterrows():
            time_series.append({
                'fiscal_year_end': str(row['fiscal_year_end']),
                'year': _extract_year(row['fiscal_year_end']),
                'peo_actually_paid': _safe_float(row['peo_actually_paid_comp']),
                'neo_avg_actually_paid': _safe_float(row['neo_avg_actually_paid_comp']),
                'company_tsr': _safe_float(row['total_shareholder_return']),
                'peer_tsr': _safe_float(row['peer_group_tsr']),
                'net_income': _safe_float(row['net_income']),
                'company_measure': _safe_float(row['company_selected_measure_value']),
            })

    return {
        'available': True,
        'current_metrics': current_metrics,
        'time_series': time_series,
        'performance_measures': performance_measures,
        'outperforming_peers': _is_outperforming(proxy),
    }

def _calculate_tsr_diff(proxy) -> dict:
    """Calculate TSR difference vs peer group."""
    if proxy.total_shareholder_return is None or proxy.peer_group_tsr is None:
        return None

    diff = float(proxy.total_shareholder_return) - float(proxy.peer_group_tsr)
    return {
        'value': diff,
        'formatted': f"{diff:+.1f}%",
        'outperforming': diff > 0
    }

def _is_outperforming(proxy) -> bool:
    """Check if company TSR exceeds peer group."""
    if proxy.total_shareholder_return is None or proxy.peer_group_tsr is None:
        return None
    return float(proxy.total_shareholder_return) > float(proxy.peer_group_tsr)
```

### Governance Section

```python
def _get_governance_data(proxy) -> dict:
    return {
        'insider_trading_policy': {
            'adopted': proxy.insider_trading_policy_adopted,
            'status_text': _get_policy_status_text(proxy.insider_trading_policy_adopted),
            'status_color': 'green' if proxy.insider_trading_policy_adopted else 'red'
        }
    }

def _get_policy_status_text(adopted: bool) -> str:
    if adopted is None:
        return "Not disclosed"
    return "Policy Adopted" if adopted else "No Policy"
```

## Helper Functions

```python
from decimal import Decimal
from typing import Optional, Union
import pandas as pd

def _format_currency(value: Optional[Decimal], abbreviate: bool = True) -> str:
    """Format currency value for display."""
    if value is None:
        return "—"

    val = float(value)

    if not abbreviate:
        return f"${val:,.0f}"

    if abs(val) >= 1_000_000_000:
        return f"${val / 1_000_000_000:.1f}B"
    elif abs(val) >= 1_000_000:
        return f"${val / 1_000_000:.1f}M"
    elif abs(val) >= 1_000:
        return f"${val / 1_000:.0f}K"
    else:
        return f"${val:,.0f}"

def _safe_float(value) -> Optional[float]:
    """Safely convert value to float."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def _extract_year(date_str) -> Optional[int]:
    """Extract year from date string."""
    if date_str is None:
        return None
    try:
        return int(str(date_str)[:4])
    except (ValueError, IndexError):
        return None
```

## UI Component Recommendations

### Compensation Summary Card

Display on Company screen or as Proxy screen header:

```
┌─────────────────────────────────────────────────────────────┐
│  CEO Compensation (FY 2023)                                 │
│                                                             │
│  Tim Cook                                                   │
│  ┌──────────────────┬──────────────────┐                   │
│  │ Summary Comp     │ Actually Paid    │                   │
│  │ $63.2M           │ $143.5M          │                   │
│  └──────────────────┴──────────────────┘                   │
│                                                             │
│  NEO Average: $22.0M (SCT) / $49.8M (CAP)                  │
└─────────────────────────────────────────────────────────────┘
```

### Compensation Comparison Table

5-year table view:

```
┌──────────┬────────────────┬────────────────┬───────────────┬───────────────┐
│ Year     │ CEO Total      │ CEO Actually   │ NEO Avg       │ NEO Avg       │
│          │ Comp           │ Paid           │ Total         │ Actually Paid │
├──────────┼────────────────┼────────────────┼───────────────┼───────────────┤
│ 2023     │ $63.2M         │ $143.5M        │ $22.0M        │ $49.8M        │
│ 2022     │ $99.4M         │ -$5.9M         │ $26.9M        │ $5.0M         │
│ 2021     │ $98.7M         │ $474.1M        │ $26.8M        │ $137.8M       │
│ 2020     │ $14.8M         │ $281.9M        │ $9.4M         │ $67.4M        │
│ 2019     │ $11.6M         │ -$828.6M       │ $7.9M         │ -$191.3M      │
└──────────┴────────────────┴────────────────┴───────────────┴───────────────┘
```

### Pay vs Performance Chart

Dual-axis chart showing:
- Left axis: Compensation Actually Paid (bars or line)
- Right axis: Total Shareholder Return % (line)

Data points per year:
- CEO CAP
- NEO Avg CAP
- Company TSR
- Peer Group TSR

### TSR Comparison Visual

```
Company TSR vs Peer Group (5-Year Cumulative)

Company:    ████████████████████████████████ 205.3%
Peer Group: ██████████████████████████░░░░░░ 178.9%
                                            +26.4% ✓
```

### Governance Indicators

Simple status badges:

```
┌─────────────────────────────────────────┐
│ Governance                              │
│                                         │
│ ✓ Insider Trading Policy Adopted        │
│                                         │
│ Performance Measures:                   │
│ • Revenue                               │
│ • Operating Income                      │
│ • Return on Invested Capital            │
└─────────────────────────────────────────┘
```

## Handling Edge Cases

### No Proxy Filing

```python
filing = company.get_filings(form="DEF 14A").latest()
if not filing:
    # Show message: "No proxy statement filed"
    # This can happen for:
    # - Very new companies
    # - Companies that use other proxy forms
    # - Foreign private issuers (use Form 20-F)
```

### No XBRL Data

```python
if not proxy.has_xbrl:
    # Show limited view:
    # - Filing metadata (date, form type)
    # - Link to full filing document
    # - Explanation: "Structured compensation data not available.
    #   This company may be exempt from Pay vs Performance disclosure rules."
```

### Partial Data

```python
# Always check individual fields
if proxy.peo_total_comp is not None:
    # Show CEO compensation
else:
    # Show "Not disclosed" or hide section

if proxy.total_shareholder_return is not None:
    # Show TSR metrics
else:
    # Hide or show "TSR data not available"
```

### Negative Values

Compensation Actually Paid can be negative (when stock awards decline):

```python
cap = proxy.peo_actually_paid_comp
if cap is not None and cap < 0:
    # Display in red/parentheses: ($828.6M)
    # Add tooltip: "Negative value reflects decline in unvested equity awards"
```

## Data Refresh Strategy

```python
def should_refresh_proxy_data(company: Company, cached_date: str) -> bool:
    """Determine if proxy data should be refreshed."""
    from datetime import datetime, timedelta

    # Proxy statements are filed annually, typically 4 months after fiscal year end
    # Most are filed Feb-April for calendar year companies

    today = datetime.now().date()
    cached = datetime.strptime(cached_date, "%Y-%m-%d").date()

    # Refresh if cached data is > 30 days old during proxy season (Feb-May)
    if today.month in [2, 3, 4, 5] and (today - cached).days > 30:
        return True

    # Otherwise refresh if > 90 days old
    return (today - cached).days > 90
```

## Complete Example

```python
from edgar import Company

def render_proxy_screen(ticker: str) -> dict:
    """Complete example of gathering all proxy screen data."""
    company = Company(ticker)

    # Check data availability first
    expectation = get_proxy_data_expectation(company)

    # Get filing
    filing = company.get_filings(form="DEF 14A").latest()

    if not filing:
        return {
            'status': 'no_filing',
            'company': {'name': company.name, 'ticker': ticker},
            'expectation': expectation,
        }

    proxy = filing.obj()

    if not proxy.has_xbrl:
        return {
            'status': 'no_xbrl',
            'company': {'name': company.name, 'ticker': ticker},
            'expectation': expectation,
            'filing': {
                'date': proxy.filing_date,
                'url': filing.homepage_url
            }
        }

    # Full data available
    return {
        'status': 'ok',
        'company': {
            'name': company.name,
            'ticker': ticker,
            'filer_badge': get_filer_badge(company)
        },
        'expectation': expectation,
        'data': get_proxy_screen_data(company)
    }
```
