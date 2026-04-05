# 8-K (EightK) UI Guide

A practical guide for rendering 8-K current report data in downstream applications, including the new earnings release financial parsing capabilities.

## Overview

8-K filings are "current reports" that public companies file to announce major events shareholders should know about. They are the real-time pulse of corporate America - from earnings announcements to executive departures.

| Property | Value |
|----------|-------|
| Class Name | `EightK` (alias: `CurrentReport`) |
| Forms Handled | `8-K`, `8-K/A`, `6-K`, `6-K/A` |
| Module | `edgar.company_reports` |
| Source Data | HTML document + XML exhibits |

---

## Quick Start

```python
from edgar import Company

# Get latest 8-K for a company
company = Company("AAPL")
filing = company.get_filings(form="8-K").latest()
eightk = filing.obj()

# Access basic metadata
print(eightk.company)           # "Apple Inc."
print(eightk.form)              # "8-K"
print(eightk.filing_date)       # "2025-01-23"
print(eightk.date_of_report)    # "January 22, 2025"

# Access items
print(eightk.items)             # ['Item 2.02', 'Item 9.01']
print(eightk['Item 2.02'])      # Item content text

# Access earnings data (new feature)
if eightk.has_earnings:
    earnings = eightk.earnings
    income = eightk.income_statement
```

---

## Data Model for App Screens

### Complete Screen Data Structure

```python
def get_eightk_screen_data(ticker: str, filing_date: str = None) -> dict:
    """Get all data needed to render an 8-K screen."""
    company = Company(ticker)

    if filing_date:
        filing = company.get_filings(form="8-K", date=f"{filing_date}:").latest()
    else:
        filing = company.get_filings(form="8-K").latest()

    if not filing:
        return {'error': 'no_filing', 'message': 'No 8-K filing found'}

    eightk = filing.obj()

    return {
        # Header section
        'header': _get_header_data(eightk, company, filing),

        # Items section (core 8-K structure)
        'items': _get_items_data(eightk),

        # Press releases
        'press_releases': _get_press_release_data(eightk),

        # Earnings data (if Item 2.02 present)
        'earnings': _get_earnings_data(eightk),

        # Exhibits
        'exhibits': _get_exhibits_data(filing),

        # Data availability flags
        'flags': {
            'has_press_release': eightk.has_press_release,
            'has_earnings': eightk.has_earnings,
            'has_income_statement': eightk.income_statement is not None,
            'has_balance_sheet': eightk.balance_sheet is not None,
            'has_cash_flow': eightk.cash_flow_statement is not None,
            'is_amendment': '/A' in eightk.form,
        },

        # Links
        'links': {
            'filing_url': filing.homepage_url,
            'sec_url': filing.filing_url,
        }
    }
```

---

## Header Section

```python
def _get_header_data(eightk, company: Company, filing) -> dict:
    return {
        'company_name': eightk.company,
        'ticker': company.get_ticker(),
        'form': eightk.form,
        'is_amendment': '/A' in eightk.form,
        'filing_date': str(filing.filing_date),
        'event_date': eightk.period_of_report,       # YYYY-MM-DD format
        'date_of_report': eightk.date_of_report,     # "January 22, 2025" format
        'cik': str(company.cik),
        'accession_number': filing.accession_number,
    }
```

### Header Display Component

```
┌─────────────────────────────────────────────────────────────┐
│  Apple Inc. (AAPL)                              8-K         │
│                                                             │
│  Event Date: January 22, 2025                               │
│  Filed: January 23, 2025                                    │
│                                                             │
│  Items: 2.02 - Results of Operations                        │
│         9.01 - Financial Statements and Exhibits            │
└─────────────────────────────────────────────────────────────┘
```

---

## Items Section (Core 8-K Structure)

### Getting Items Data

```python
def _get_items_data(eightk) -> list:
    """Get all items with their content."""
    items_data = []

    for item_name in eightk.items:
        item_num = item_name.replace('Item ', '')
        item_info = _get_item_info(item_num)

        items_data.append({
            'number': item_num,
            'name': item_name,
            'title': item_info['title'],
            'category': item_info['category'],
            'category_color': item_info['color'],
            'content': eightk[item_name],
            'description': item_info['description'],
        })

    return items_data

def _get_item_info(item_num: str) -> dict:
    """Get metadata for an item number."""
    ITEM_METADATA = {
        # Section 1 - Business Operations
        '1.01': {'title': 'Entry into a Material Definitive Agreement',
                 'category': 'Business', 'color': 'blue',
                 'description': 'New contracts, acquisitions, partnerships'},
        '1.02': {'title': 'Termination of a Material Definitive Agreement',
                 'category': 'Business', 'color': 'blue',
                 'description': 'End of significant contracts'},
        '1.03': {'title': 'Bankruptcy or Receivership',
                 'category': 'Business', 'color': 'red',
                 'description': 'Company enters bankruptcy'},
        '1.04': {'title': 'Mine Safety Violations',
                 'category': 'Business', 'color': 'orange',
                 'description': 'Mining companies only'},

        # Section 2 - Financial Information
        '2.01': {'title': 'Completion of Acquisition or Disposition',
                 'category': 'Financial', 'color': 'green',
                 'description': 'Completed M&A transactions'},
        '2.02': {'title': 'Results of Operations and Financial Condition',
                 'category': 'Financial', 'color': 'green',
                 'description': 'Earnings releases, quarterly results'},
        '2.03': {'title': 'Creation of Direct Financial Obligation',
                 'category': 'Financial', 'color': 'green',
                 'description': 'New debt, credit facilities'},
        '2.04': {'title': 'Triggering Events Accelerating Obligations',
                 'category': 'Financial', 'color': 'orange',
                 'description': 'Covenant violations, acceleration'},
        '2.05': {'title': 'Exit or Disposal Costs',
                 'category': 'Financial', 'color': 'green',
                 'description': 'Restructuring charges'},
        '2.06': {'title': 'Material Impairments',
                 'category': 'Financial', 'color': 'orange',
                 'description': 'Asset writedowns'},

        # Section 3 - Securities
        '3.01': {'title': 'Delisting or Listing Rule Failure',
                 'category': 'Securities', 'color': 'purple',
                 'description': 'Exchange compliance issues'},
        '3.02': {'title': 'Unregistered Sales of Equity',
                 'category': 'Securities', 'color': 'purple',
                 'description': 'Private placements'},
        '3.03': {'title': 'Modification to Security Holder Rights',
                 'category': 'Securities', 'color': 'purple',
                 'description': 'Charter/bylaw changes'},

        # Section 4 - Accountants
        '4.01': {'title': 'Change in Certifying Accountant',
                 'category': 'Accountant', 'color': 'orange',
                 'description': 'Auditor change'},
        '4.02': {'title': 'Non-Reliance on Prior Financial Statements',
                 'category': 'Accountant', 'color': 'red',
                 'description': 'Restatement announcement'},

        # Section 5 - Governance
        '5.02': {'title': 'Director/Officer Changes',
                 'category': 'Governance', 'color': 'cyan',
                 'description': 'Executive and board changes'},
        '5.03': {'title': 'Amendment to Charter/Bylaws',
                 'category': 'Governance', 'color': 'cyan',
                 'description': 'Governance document changes'},
        '5.07': {'title': 'Shareholder Vote Results',
                 'category': 'Governance', 'color': 'cyan',
                 'description': 'Annual meeting results'},

        # Section 7 & 8 - Disclosure
        '7.01': {'title': 'Regulation FD Disclosure',
                 'category': 'Disclosure', 'color': 'gray',
                 'description': 'Material non-public info'},
        '8.01': {'title': 'Other Events',
                 'category': 'Disclosure', 'color': 'gray',
                 'description': 'Voluntary disclosure'},

        # Section 9 - Exhibits
        '9.01': {'title': 'Financial Statements and Exhibits',
                 'category': 'Exhibits', 'color': 'lightgray',
                 'description': 'List of attached documents'},
    }

    return ITEM_METADATA.get(item_num, {
        'title': f'Item {item_num}',
        'category': 'Other',
        'color': 'gray',
        'description': ''
    })
```

### Item Category Badge Colors

| Category | Items | Color | Meaning |
|----------|-------|-------|---------|
| Financial | 2.01-2.06 | Green | Financial results, M&A, debt |
| Governance | 5.01-5.08 | Cyan | Leadership, board, bylaws |
| Accountant | 4.01-4.02 | Orange | Auditor issues, restatements |
| Securities | 3.01-3.03 | Purple | Stock/exchange matters |
| Business | 1.01-1.04 | Blue | Contracts, operations |
| Disclosure | 7.01, 8.01 | Gray | General announcements |
| Exhibits | 9.01 | Light Gray | Document listings |

### Critical Item Indicators

Some items warrant special visual treatment:

```python
def get_item_severity(item_num: str) -> str:
    """Get severity level for visual emphasis."""
    CRITICAL_ITEMS = {
        '1.03': 'critical',    # Bankruptcy
        '4.02': 'critical',    # Financial restatement
        '3.01': 'warning',     # Delisting risk
        '2.04': 'warning',     # Debt triggers
        '2.06': 'warning',     # Impairments
        '4.01': 'info',        # Auditor change
    }
    return CRITICAL_ITEMS.get(item_num, 'normal')
```

---

## Earnings Section (Item 2.02)

The new earnings parsing feature extracts structured financial data from press release exhibits.

### Checking for Earnings Data

```python
def _get_earnings_data(eightk) -> dict:
    """Get parsed earnings data if available."""
    if not eightk.has_earnings:
        return {'available': False, 'reason': 'Not an earnings filing (no Item 2.02)'}

    earnings = eightk.earnings
    if not earnings:
        return {'available': False, 'reason': 'No EX-99.1 earnings exhibit found'}

    return {
        'available': True,
        'summary': _get_earnings_summary(earnings),
        'income_statement': _get_statement_data(eightk.income_statement),
        'balance_sheet': _get_statement_data(eightk.balance_sheet),
        'cash_flow': _get_statement_data(eightk.cash_flow_statement),
        'segment_data': _get_statement_data(earnings.segment_data),
        'eps_reconciliation': _get_statement_data(earnings.eps_reconciliation),
        'guidance': _get_statement_data(earnings.guidance),
        'all_tables': [_get_statement_data(t) for t in earnings.financial_tables],
    }

def _get_earnings_summary(earnings) -> dict:
    """Get high-level earnings summary."""
    return {
        'document': earnings.attachment.document,
        'detected_scale': earnings.detected_scale.name.lower(),
        'scale_factor': earnings.detected_scale.value,
        'table_count': len(earnings.financial_tables),
        'has_income_statement': earnings.income_statement is not None,
        'has_balance_sheet': earnings.balance_sheet is not None,
        'has_cash_flow': earnings.cash_flow_statement is not None,
        'has_segment_data': earnings.segment_data is not None,
        'has_guidance': earnings.guidance is not None,
    }
```

### Financial Table Data Structure

```python
def _get_statement_data(table) -> dict:
    """Convert FinancialTable to app-friendly dict."""
    if table is None:
        return None

    return {
        'statement_type': table.statement_type.value,
        'scale': table.scale.name.lower(),
        'scale_factor': table.scale.value,
        'title': table.title,
        'periods': table.periods,
        'shape': {
            'rows': table.dataframe.shape[0],
            'cols': table.dataframe.shape[1],
        },

        # Data in multiple formats
        'data': {
            'records': table.dataframe.to_dict(orient='index'),
            'columns': list(table.dataframe.columns),
            'row_labels': table.get_raw_labels(),
        },

        # Pre-formatted outputs
        'html': table.to_html(include_title=True),
        'json': table.to_json(include_metadata=True),
        'csv': table.to_csv(),
        'markdown': table.to_markdown(include_context=True),
    }
```

### Statement Type Reference

| Type | Value | Description |
|------|-------|-------------|
| Income Statement | `income_statement` | Revenue, expenses, net income |
| Balance Sheet | `balance_sheet` | Assets, liabilities, equity |
| Cash Flow | `cash_flow` | Operating, investing, financing |
| Segment Data | `segment_data` | Business unit breakdown |
| EPS Reconciliation | `eps_reconciliation` | GAAP to Non-GAAP EPS |
| GAAP Reconciliation | `gaap_reconciliation` | GAAP to Non-GAAP measures |
| Key Metrics | `key_metrics` | KPIs, operational metrics |
| Guidance | `guidance` | Forward-looking estimates |

### Scale Handling

Financial values are reported in various scales. Always display the scale to users.

```python
from edgar.earnings import Scale

# Scale values
Scale.UNITS.value      # 1
Scale.THOUSANDS.value  # 1_000
Scale.MILLIONS.value   # 1_000_000
Scale.BILLIONS.value   # 1_000_000_000

# Get actual dollar values
def get_actual_value(table_value: float, scale: str) -> float:
    """Convert displayed value to actual USD."""
    scale_factors = {
        'units': 1,
        'thousands': 1_000,
        'millions': 1_000_000,
        'billions': 1_000_000_000,
    }
    return table_value * scale_factors.get(scale.lower(), 1)

# Display formatting
def format_financial_value(value: float, scale: str) -> str:
    """Format for display with scale indicator."""
    if value is None:
        return "—"

    if abs(value - round(value)) < 0.01:
        formatted = f"{int(round(value)):,}"
    else:
        formatted = f"{value:,.2f}"

    return formatted  # Scale shown in table header
```

### Earnings Display Components

#### Income Statement Card

```
┌─────────────────────────────────────────────────────────────┐
│  Income Statement (in millions)                             │
│                                                             │
│                          Q4 2025    Q4 2024    Change       │
│  ─────────────────────────────────────────────────────────  │
│  Net Revenue              124,300    119,575    +3.9%       │
│  Cost of Sales             66,651     64,720    +3.0%       │
│  Gross Profit              57,649     54,855    +5.1%       │
│  Operating Expenses        14,370     14,481    -0.8%       │
│  Operating Income          43,279     40,374    +7.2%       │
│  Net Income                36,330     33,916    +7.1%       │
│                                                             │
│  EPS (Diluted)              $2.40      $2.18    +10.1%      │
└─────────────────────────────────────────────────────────────┘
```

#### Financial Summary Row

For compact display in lists/feeds:

```python
def get_earnings_highlight(eightk) -> dict:
    """Get key metrics for compact display."""
    if not eightk.income_statement:
        return None

    df = eightk.income_statement.dataframe
    scale = eightk.earnings.detected_scale.name.lower()

    # Find revenue row (various label patterns)
    revenue_labels = ['Net revenue', 'Revenue', 'Net sales', 'Total revenue']
    revenue = None
    for label in revenue_labels:
        if label in df.index:
            revenue = df.loc[label].iloc[0]  # Most recent period
            break

    # Find net income
    income_labels = ['Net income', 'Net income (loss)', 'Net earnings']
    net_income = None
    for label in income_labels:
        if label in df.index:
            net_income = df.loc[label].iloc[0]
            break

    return {
        'revenue': revenue,
        'net_income': net_income,
        'scale': scale,
        'period': str(df.columns[0]) if len(df.columns) > 0 else None,
    }
```

---

## Press Releases Section

### Getting Press Release Data

```python
def _get_press_release_data(eightk) -> dict:
    """Get press release content."""
    if not eightk.has_press_release:
        return {'available': False}

    press_releases = []
    for i in range(len(eightk.press_releases)):
        pr = eightk.press_releases[i]
        press_releases.append({
            'index': i,
            'document': pr.document,
            'description': pr.description,
            'url': pr.url(),
            'text': pr.text(),
            'markdown': str(pr.to_markdown()),
            'html_available': True,
        })

    return {
        'available': True,
        'count': len(press_releases),
        'releases': press_releases,
    }
```

### Press Release Display

```
┌─────────────────────────────────────────────────────────────┐
│  📰 Press Release                                           │
│  pressrelease-q42025.htm                                    │
│                                                             │
│  Apple Reports Record Q4 Revenue                            │
│                                                             │
│  CUPERTINO, CALIFORNIA — January 22, 2025 — Apple Inc.     │
│  today announced financial results for its fiscal 2025      │
│  fourth quarter ended December 28, 2025...                  │
│                                                             │
│  [View Full Release] [Download]                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Exhibits Section

### Getting Exhibit Data

```python
def _get_exhibits_data(filing) -> list:
    """Get exhibit listing from filing."""
    exhibits = []

    for exhibit in filing.exhibits:
        exhibits.append({
            'sequence': exhibit.sequence_number,
            'type': exhibit.document_type,
            'document': exhibit.document,
            'description': exhibit.description,
            'size_bytes': exhibit.size,
            'size_display': _format_size(exhibit.size),
            'url': exhibit.url,
            'is_html': exhibit.is_html(),
            'is_binary': exhibit.is_binary(),
            'extension': exhibit.extension,
            'is_xbrl': exhibit.ixbrl,

            # Content type hints for UI
            'icon': _get_exhibit_icon(exhibit),
            'can_preview': exhibit.is_html() or exhibit.is_text(),
        })

    return exhibits

def _get_exhibit_icon(exhibit) -> str:
    """Get icon identifier for exhibit type."""
    doc_type = exhibit.document_type.upper()

    if 'EX-99' in doc_type:
        return 'newspaper'        # Press release
    elif 'EX-10' in doc_type:
        return 'file-contract'    # Material contract
    elif 'EX-101' in doc_type:
        return 'code'             # XBRL
    elif 'GRAPHIC' in doc_type:
        return 'image'
    elif exhibit.is_binary():
        return 'file-pdf'
    else:
        return 'file-text'

def _format_size(size_bytes: int) -> str:
    """Format file size for display."""
    if size_bytes is None:
        return "—"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
```

### Exhibit Type Reference

| Type Pattern | Description | Typical Content |
|--------------|-------------|-----------------|
| `EX-10.X` | Material Contracts | Agreements, amendments |
| `EX-99.1` | Press Release (Primary) | Earnings announcement |
| `EX-99.2+` | Additional Exhibits | Presentations, supplements |
| `EX-101.*` | XBRL Taxonomy | Machine-readable data |
| `GRAPHIC` | Images | Logos, charts |

---

## Event Classification & Routing

### Automated Event Routing

Route 8-Ks to appropriate handlers based on items:

```python
def classify_eightk_event(eightk) -> dict:
    """Classify 8-K for routing and alerts."""
    items = [item.replace('Item ', '') for item in eightk.items]

    # Priority classification
    if any(i in items for i in ['1.03', '4.02']):
        priority = 'critical'
        alert_type = 'risk_alert'
    elif any(i in items for i in ['2.02']):
        priority = 'high'
        alert_type = 'earnings'
    elif any(i in items for i in ['5.02', '1.01', '2.01']):
        priority = 'high'
        alert_type = 'corporate_action'
    elif any(i in items for i in ['3.01', '2.04', '2.06']):
        priority = 'medium'
        alert_type = 'risk_event'
    else:
        priority = 'normal'
        alert_type = 'general'

    # Event categories
    categories = set()
    for item in items:
        if item.startswith('2.'):
            categories.add('financial')
        elif item.startswith('5.'):
            categories.add('governance')
        elif item.startswith('1.'):
            categories.add('business')
        elif item.startswith('3.'):
            categories.add('securities')
        elif item.startswith('4.'):
            categories.add('accounting')

    return {
        'priority': priority,
        'alert_type': alert_type,
        'categories': list(categories),
        'is_earnings': '2.02' in items,
        'is_management_change': '5.02' in items,
        'is_material_agreement': '1.01' in items,
        'is_ma_completion': '2.01' in items,
        'requires_review': priority in ['critical', 'high'],
    }
```

### Event-Based Views

```python
def get_view_config(eightk) -> dict:
    """Get recommended view configuration."""
    classification = classify_eightk_event(eightk)

    if classification['is_earnings'] and eightk.has_earnings:
        return {
            'primary_view': 'earnings_dashboard',
            'show_financial_tables': True,
            'show_press_release': True,
            'expanded_sections': ['income_statement', 'press_release'],
            'chart_type': 'earnings_comparison',
        }
    elif classification['is_management_change']:
        return {
            'primary_view': 'governance_update',
            'show_financial_tables': False,
            'show_press_release': True,
            'expanded_sections': ['item_502', 'press_release'],
            'chart_type': None,
        }
    elif classification['is_ma_completion']:
        return {
            'primary_view': 'corporate_action',
            'show_financial_tables': False,
            'show_press_release': True,
            'expanded_sections': ['item_201', 'exhibits'],
            'chart_type': None,
        }
    else:
        return {
            'primary_view': 'standard',
            'show_financial_tables': False,
            'show_press_release': eightk.has_press_release,
            'expanded_sections': ['items'],
            'chart_type': None,
        }
```

---

## AI Integration

### Feeding Data to AI Analysts

```python
def get_ai_context(eightk, detail: str = 'standard') -> str:
    """
    Get AI-optimized text representation for analysis.

    Args:
        eightk: EightK object
        detail: 'minimal', 'standard', or 'full'

    Returns:
        Text optimized for LLM consumption
    """
    lines = []

    # Header context
    lines.append(f"=== 8-K Filing: {eightk.company} ===")
    lines.append(f"Form: {eightk.form}")
    lines.append(f"Event Date: {eightk.date_of_report}")
    lines.append(f"Items Reported: {', '.join(eightk.items)}")
    lines.append("")

    # Item content
    for item_name in eightk.items:
        content = eightk[item_name]
        if content:
            lines.append(f"--- {item_name} ---")
            if detail == 'minimal':
                lines.append(content[:500] + "..." if len(content) > 500 else content)
            elif detail == 'standard':
                lines.append(content[:2000] + "..." if len(content) > 2000 else content)
            else:
                lines.append(content)
            lines.append("")

    # Earnings data
    if eightk.has_earnings and eightk.earnings:
        lines.append(eightk.earnings.to_context(detail=detail))

    return "\n".join(lines)
```

### AI Analysis Prompts

```python
# Example prompts for AI analysis

EARNINGS_ANALYSIS_PROMPT = """
Analyze this 8-K earnings release:

{context}

Provide:
1. Key financial highlights (revenue, earnings, EPS)
2. YoY and QoQ changes
3. Notable items or concerns
4. Forward guidance summary (if available)
"""

RISK_ANALYSIS_PROMPT = """
Analyze this 8-K filing for risk factors:

{context}

Identify:
1. Material risks disclosed
2. Potential impact on shareholders
3. Required follow-up items
4. Comparison to prior disclosures (if relevant)
"""

MANAGEMENT_CHANGE_PROMPT = """
Analyze this 8-K management/board change:

{context}

Summarize:
1. Who is departing/joining
2. Roles affected
3. Reason for change (if disclosed)
4. Potential implications
"""
```

### Standardization Support

Use AI to standardize financial labels:

```python
def get_standardization_request(table) -> dict:
    """Prepare data for AI-based label standardization."""
    return {
        'statement_type': table.statement_type.value,
        'raw_labels': table.get_raw_labels(),
        'sample_data': table.to_markdown(include_context=False),
        'prompt': """
Map these financial statement labels to standard terminology:

Raw Labels:
{labels}

For each label, provide:
- standard_label: The standardized name (e.g., "Revenue", "Cost of Revenue")
- confidence: high/medium/low
- notes: Any relevant context

Return as JSON: {"mappings": [{"original": "...", "standard": "...", "confidence": "..."}]}
""".format(labels="\n".join(f"- {l}" for l in table.get_raw_labels()))
    }

def apply_standardization(table, ai_response: dict):
    """Apply AI-suggested standardization."""
    label_mapping = {
        m['original']: m['standard']
        for m in ai_response.get('mappings', [])
        if m.get('confidence') in ['high', 'medium']
    }
    return table.with_standardized_labels(label_mapping)
```

---

## Filtering and Search

### Filing Discovery

```python
def get_eightk_filings(
    ticker: str,
    days: int = 90,
    item_filter: list = None,
    earnings_only: bool = False,
) -> list:
    """Get filtered 8-K filings for a company."""
    from datetime import datetime, timedelta

    company = Company(ticker)
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    filings = company.get_filings(form="8-K", date=f"{start_date}:")

    results = []
    for filing in filings[:50]:  # Limit iteration
        eightk = filing.obj()

        # Apply item filter
        if item_filter:
            items = [i.replace('Item ', '') for i in eightk.items]
            if not any(f in items for f in item_filter):
                continue

        # Earnings filter
        if earnings_only and not eightk.has_earnings:
            continue

        classification = classify_eightk_event(eightk)

        results.append({
            'filing_date': str(filing.filing_date),
            'event_date': eightk.period_of_report,
            'items': eightk.items,
            'classification': classification,
            'has_earnings': eightk.has_earnings,
            'has_press_release': eightk.has_press_release,
            'accession_number': filing.accession_number,
            'url': filing.homepage_url,
        })

    return results
```

### Common Filters

```python
# Earnings releases
earnings_filings = get_eightk_filings("AAPL", item_filter=['2.02'], earnings_only=True)

# Management changes
management_filings = get_eightk_filings("AAPL", item_filter=['5.02'])

# Material agreements
deal_filings = get_eightk_filings("AAPL", item_filter=['1.01', '2.01'])

# Risk events
risk_filings = get_eightk_filings("AAPL", item_filter=['1.03', '4.02', '3.01'])
```

---

## Real-Time Monitoring

### Polling for New Filings

```python
def check_new_eightks(
    tickers: list,
    since_date: str,
    callback=None
) -> list:
    """Check for new 8-K filings since a date."""
    from edgar import get_filings

    new_filings = []

    # Get recent 8-Ks across all companies
    filings = get_filings(form="8-K", date=f"{since_date}:")

    for filing in filings:
        if filing.company_ticker in tickers:
            eightk = filing.obj()
            classification = classify_eightk_event(eightk)

            event_data = {
                'ticker': filing.company_ticker,
                'company': filing.company_name,
                'filing_date': str(filing.filing_date),
                'items': eightk.items,
                'classification': classification,
                'is_earnings': eightk.has_earnings,
            }

            new_filings.append(event_data)

            if callback:
                callback(event_data)

    return new_filings
```

### Alert Conditions

```python
def should_alert(classification: dict, user_preferences: dict) -> bool:
    """Determine if user should be alerted."""

    # Always alert on critical
    if classification['priority'] == 'critical':
        return True

    # Check user preferences
    if user_preferences.get('alert_earnings') and classification['is_earnings']:
        return True

    if user_preferences.get('alert_management') and classification['is_management_change']:
        return True

    if user_preferences.get('alert_deals') and classification['is_material_agreement']:
        return True

    return False
```

---

## Error Handling

### Common Edge Cases

```python
def safe_get_eightk_data(ticker: str) -> dict:
    """Get 8-K data with comprehensive error handling."""
    try:
        company = Company(ticker)
    except Exception as e:
        return {'error': 'invalid_ticker', 'message': f'Company not found: {ticker}'}

    try:
        filing = company.get_filings(form="8-K").latest()
    except Exception:
        filing = None

    if not filing:
        return {'error': 'no_filing', 'message': 'No 8-K filings found'}

    try:
        eightk = filing.obj()
    except Exception as e:
        return {'error': 'parse_error', 'message': f'Failed to parse filing: {e}'}

    # Safe earnings access
    earnings_data = None
    if eightk.has_earnings:
        try:
            earnings = eightk.earnings
            if earnings:
                earnings_data = {
                    'available': True,
                    'table_count': len(earnings.financial_tables),
                }
        except Exception as e:
            earnings_data = {'available': False, 'error': str(e)}

    return {
        'success': True,
        'header': _get_header_data(eightk, company, filing),
        'items': eightk.items,
        'earnings': earnings_data,
        'has_press_release': eightk.has_press_release,
    }
```

### Partial Data Handling

```python
def get_financial_statement_safe(eightk, statement_type: str) -> dict:
    """Safely get a financial statement with fallbacks."""

    getters = {
        'income_statement': (eightk.income_statement, eightk.get_income_statement),
        'balance_sheet': (eightk.balance_sheet, eightk.get_balance_sheet),
        'cash_flow': (eightk.cash_flow_statement, eightk.get_cash_flow_statement),
    }

    if statement_type not in getters:
        return {'available': False, 'reason': 'Unknown statement type'}

    prop, safe_method = getters[statement_type]

    try:
        if prop is not None:
            return {
                'available': True,
                'data': _get_statement_data(prop),
            }
        else:
            # Use safe method that returns empty DataFrame
            df = safe_method()
            return {
                'available': not df.empty,
                'data': {'dataframe': df.to_dict()} if not df.empty else None,
                'reason': 'No data found' if df.empty else None,
            }
    except Exception as e:
        return {
            'available': False,
            'reason': f'Error retrieving data: {e}',
        }
```

---

## Complete Example

```python
from edgar import Company

def render_eightk_page(ticker: str) -> dict:
    """Complete example of gathering all 8-K page data."""

    # Get company and filing
    company = Company(ticker)
    filing = company.get_filings(form="8-K").latest()

    if not filing:
        return {
            'status': 'no_filing',
            'company': {'name': company.name, 'ticker': ticker},
        }

    eightk = filing.obj()
    classification = classify_eightk_event(eightk)
    view_config = get_view_config(eightk)

    # Build page data
    page_data = {
        'status': 'ok',

        # Metadata
        'company': {
            'name': company.name,
            'ticker': ticker,
            'cik': str(company.cik),
        },

        # Classification
        'classification': classification,
        'view_config': view_config,

        # Core data
        'header': {
            'form': eightk.form,
            'filing_date': str(filing.filing_date),
            'event_date': eightk.date_of_report,
            'items': eightk.items,
        },

        # Items with content
        'items': _get_items_data(eightk),

        # Press release
        'press_release': _get_press_release_data(eightk),

        # Exhibits
        'exhibits': _get_exhibits_data(filing),

        # Links
        'links': {
            'sec_filing': filing.homepage_url,
            'company_page': f"/company/{ticker}",
        },
    }

    # Add earnings if available
    if classification['is_earnings']:
        page_data['earnings'] = _get_earnings_data(eightk)

        # Add earnings highlights for header
        if eightk.earnings:
            page_data['header']['earnings_highlight'] = get_earnings_highlight(eightk)

    return page_data


# Usage
data = render_eightk_page("AAPL")
print(f"Filing: {data['header']['form']} on {data['header']['event_date']}")
print(f"Items: {', '.join(data['header']['items'])}")
print(f"Priority: {data['classification']['priority']}")

if data.get('earnings', {}).get('available'):
    print(f"Earnings tables: {data['earnings']['summary']['table_count']}")
```

---

## API Quick Reference

### EightK Properties

| Property | Type | Description |
|----------|------|-------------|
| `company` | `str` | Company name |
| `form` | `str` | `"8-K"` or `"8-K/A"` |
| `filing_date` | `str` | Date filed (YYYY-MM-DD) |
| `period_of_report` | `str` | Event date (YYYY-MM-DD) |
| `date_of_report` | `str` | Event date (formatted) |
| `items` | `List[str]` | Item numbers reported |
| `sections` | `dict` | Section key -> Section object |
| `has_press_release` | `bool` | Has EX-99 press release |
| `press_releases` | `PressReleases` | Press release collection |
| `has_earnings` | `bool` | Contains Item 2.02 |
| `earnings` | `EarningsRelease` | Parsed earnings data |
| `income_statement` | `FinancialTable` | Income statement shortcut |
| `balance_sheet` | `FinancialTable` | Balance sheet shortcut |
| `cash_flow_statement` | `FinancialTable` | Cash flow shortcut |
| `reports` | `Reports` or `None` | XBRL viewer report pages from FilingSummary.xml |

### EightK Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `eightk[item]` | `str` | Get item content by name/number |
| `eightk.view(item)` | `None` | Print item content |
| `eightk.text()` | `str` | Full text of all exhibits |
| `eightk.get_income_statement(default)` | `DataFrame` | Safe income statement access |
| `eightk.get_balance_sheet(default)` | `DataFrame` | Safe balance sheet access |
| `eightk.get_cash_flow_statement(default)` | `DataFrame` | Safe cash flow access |

### FinancialTable Properties

| Property | Type | Description |
|----------|------|-------------|
| `dataframe` | `DataFrame` | Raw table data |
| `scaled_dataframe` | `DataFrame` | Values scaled to actual USD |
| `scale` | `Scale` | Scale enum (UNITS/THOUSANDS/MILLIONS/BILLIONS) |
| `statement_type` | `StatementType` | Classification |
| `title` | `str` | Table title |
| `periods` | `List[str]` | Column period labels |

### FinancialTable Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_html(include_title)` | `str` | HTML table output |
| `to_json(include_metadata)` | `str` | JSON output |
| `to_csv()` | `str` | CSV output |
| `to_markdown(include_context)` | `str` | Markdown for AI |
| `to_context(detail)` | `str` | AI-optimized text |
| `get_raw_labels()` | `List[str]` | Original row labels |
| `with_standardized_labels(mapping)` | `FinancialTable` | Apply label mapping |
| `with_clean_columns(names)` | `FinancialTable` | Clean column names |

### EarningsRelease Properties

| Property | Type | Description |
|----------|------|-------------|
| `tables` | `List[FinancialTable]` | All tables |
| `financial_tables` | `List[FinancialTable]` | Tables with data (no definitions) |
| `detected_scale` | `Scale` | Primary document scale |
| `income_statement` | `FinancialTable` | Primary income statement |
| `balance_sheet` | `FinancialTable` | Balance sheet |
| `cash_flow_statement` | `FinancialTable` | Cash flow statement |
| `segment_data` | `FinancialTable` | Business segment breakdown |
| `eps_reconciliation` | `FinancialTable` | EPS GAAP/Non-GAAP |
| `guidance` | `FinancialTable` | Forward guidance |
