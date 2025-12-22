# SEC Filing Data Objects

**Guide to form-specific data objects in EdgarTools**

---

## Overview

EdgarTools provides two layers for working with SEC filings:

### Layer 1: Filing (Metadata & Documents)
The `Filing` object provides: filing metadata (date, form type, company, accession number), document access (HTML, XML, exhibits), XBRL data access, search and filtering

**Use when**: You need metadata, documents, or are filtering/counting filings

### Layer 2: Data Objects (Parsed Structured Data)
Data objects provide: form-specific parsed data, structured fields for the form type, domain-specific methods/properties, type-safe access to form data

**Use when**: You need structured data specific to the form type

---

## The obj() Function

**Convert a Filing to its specialized data object:**

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]

# Layer 1: Filing (metadata)
print(filing.form)           # "10-K"
print(filing.filing_date)    # 2024-11-01

# Layer 2: Data Object (parsed data)
tenk = filing.obj()          # Returns TenK object
print(type(tenk))            # <class 'edgar.company_reports.TenK'>
# Access structured 10-K specific data...
```

**The `obj()` function automatically routes to the appropriate data object based on form type.**

---

## Data Objects Inventory

### Company Reports
Financial reporting forms with XBRL data

| Form | Data Object | Description | Primary Use |
|------|-------------|-------------|-------------|
| **10-K** | `TenK` | Annual report | Annual financials, full year results |
| **10-Q** | `TenQ` | Quarterly report | Quarterly financials, interim results |
| **8-K** | `EightK` | Current report | Material events, press releases |
| **20-F** | `TwentyF` | Foreign annual | International company annual reports |
| **6-K** | `CurrentReport` | Foreign current | International company current reports |

**Module**: `edgar.company_reports`

**Key Features**: XBRL financial statements, structured sections (Item 1, Item 2, etc.), financial data extraction

### Ownership & Insider Trading
Beneficial ownership and insider transaction forms

| Form | Data Object | Description | Primary Use |
|------|-------------|-------------|-------------|
| **3** | `Form3` | Initial ownership | New insider registration |
| **4** | `Form4` | Changes in ownership | Insider buy/sell transactions |
| **5** | `Form5` | Annual ownership | Year-end ownership summary |

**Module**: `edgar.ownership`

**Key Features**: Reporting person details, transaction details (shares, price, dates), holdings after transaction, derivative securities

#### Form4 Transaction DataFrames

Form4 objects provide pre-filtered pandas DataFrames for different transaction types:

```python
from edgar import Company

company = Company("TSLA")
filings = company.get_filings(form="4")

for filing in filings[:5]:
    form4 = filing.obj()

    # Get insider information
    print(f"{form4.insider_name} ({form4.position})")
    print(f"Reporting period: {form4.reporting_period}")

    # Sales DataFrame - already filtered for dispositions
    if form4.common_stock_sales is not None and not form4.common_stock_sales.empty:
        for idx, sale in form4.common_stock_sales.iterrows():
            shares = sale['Shares']
            price = sale['Price']
            date = sale['Date']
            value = shares * price
            print(f"  Sale: {shares:,} shares @ ${price:.2f} = ${value:,.2f} on {date}")

    # Purchases DataFrame - already filtered for acquisitions
    if form4.common_stock_purchases is not None and not form4.common_stock_purchases.empty:
        for idx, purchase in form4.common_stock_purchases.iterrows():
            shares = purchase['Shares']
            price = purchase['Price']
            date = purchase['Date']
            value = shares * price
            print(f"  Purchase: {shares:,} shares @ ${price:.2f} = ${value:,.2f} on {date}")
```

**Common DataFrame Columns**: `Security` (security type, e.g., "Common Stock"), `Date` (transaction date), `Shares` (number of shares), `Price` (price per share), `Remaining` (shares remaining after transaction), `Code` (transaction code: 'S' = sale, 'P' = purchase, etc.), `AcquiredDisposed` ('A' = acquired, 'D' = disposed)

**Filtering Large Transactions**:
```python
from edgar import Company
from datetime import datetime, timedelta

company = Company("AAPL")
start_date = datetime.now() - timedelta(days=180)

filings = company.get_filings(form="4")
recent = filings.filter(filing_date=f"{start_date.strftime('%Y-%m-%d')}:")

large_sellers = []
for filing in recent:
    form4 = filing.obj()

    # Find sales over $1M
    if form4.common_stock_sales is not None and not form4.common_stock_sales.empty:
        for idx, sale in form4.common_stock_sales.iterrows():
            value = sale['Shares'] * sale['Price']

            if value > 1_000_000:
                large_sellers.append({
                    'name': form4.insider_name,
                    'title': form4.position,
                    'date': sale['Date'],
                    'value': value
                })

# Display results
for seller in large_sellers[:10]:
    print(f"{seller['name']} ({seller['title']})")
    print(f"  {seller['date']}: ${seller['value']:,.2f}")
```

### Private Offerings
Regulation D and crowdfunding offerings

| Form | Data Object | Description | Primary Use |
|------|-------------|-------------|-------------|
| **D** | `FormD` | Reg D offering | Private placements, exempt offerings |
| **C** | `FormC` | Crowdfunding | Reg CF crowdfunding offerings |
| **C-U** | `FormC` | Crowdfunding update | Progress updates |
| **C-AR** | `FormC` | Annual report | Crowdfunding annual report |
| **C-TR** | `FormC` | Termination | Crowdfunding termination |

**Module**: `edgar.offerings`

**Key Features**: Offering details (amount, type, exemption), issuer information, use of proceeds, investor information (Form D), campaign progress (Form C)

### Institutional Holdings
13F institutional investment manager holdings

| Form | Data Object | Description | Primary Use |
|------|-------------|-------------|-------------|
| **13F-HR** | `ThirteenF` | Holdings report | Quarterly institutional positions |
| **13F-NT** | `ThirteenF` | Notice filing | Confidential treatment notice |

**Module**: `edgar.thirteenf`

**Key Features**: Holdings table (security, shares, value), manager information, summary page data, both XML and TXT format support

### Other Specialized Forms

| Form | Data Object | Description | Primary Use |
|------|-------------|-------------|-------------|
| **144** | `Form144` | Notice of sale | Insider restricted stock sales |
| **MA-I** | `MunicipalAdvisorForm` | Municipal advisor | Muni advisor registration |
| **EFFECT** | `Effect` | Notice of effectiveness | Registration effectiveness |
| **NPORT-P** | `FundReport` | Fund holdings | Monthly fund portfolio |
| **NPORT-EX** | `FundReport` | Fund exhibit | Fund explanatory notes |

**Modules**: `edgar.form144`, `edgar.muniadvisors`, `edgar.effect`, `edgar.funds`

---

## When to Use Data Objects

### ✅ Use `filing.obj()` when:

1. **You need form-specific structured data**
   ```python
   form4 = filing.obj()  # Get insider transaction details

   # Access sales (returns pandas DataFrame)
   if form4.common_stock_sales is not None and not form4.common_stock_sales.empty:
       for idx, sale in form4.common_stock_sales.iterrows():
           shares = sale['Shares']
           price = sale['Price']
           print(f"Sale: {shares:,} shares at ${price:.2f}")
   ```

2. **Working with ownership, offerings, or specialized forms**
   ```python
   formd = filing.obj()  # Get private placement details
   print(f"Offering: ${formd.total_offering_amount:,}")
   ```

3. **Need domain-specific methods**
   ```python
   thirteenf = filing.obj()  # Get institutional holdings
   top_holdings = thirteenf.get_top_holdings(10)
   ```

### ❌ Use Filing API when:

1. **Just need metadata**
   ```python
   # Don't need obj() for this
   print(filing.filing_date)
   print(filing.company)
   print(filing.form)
   ```

2. **Filtering or counting filings**
   ```python
   # Don't need obj() for this
   filings = company.get_filings(form="4")
   count = len(filings)
   ```

3. **Checking existence**
   ```python
   # Don't need obj() for this
   has_10k = len(company.get_filings(form="10-K")) > 0
   ```

4. **Working with documents or XBRL directly**
   ```python
   # Access XBRL without obj()
   xbrl = filing.xbrl()
   income = xbrl.statements.income_statement()
   ```

---

## Quick Reference: Form → Data Object

### Company Filings
- **10-K** → `TenK` (annual report)
- **10-Q** → `TenQ` (quarterly report)
- **8-K** → `EightK` (current report)
- **20-F** → `TwentyF` (foreign annual)
- **6-K** → `CurrentReport` (foreign current)

### Insider Trading
- **Form 3** → `Form3` (initial ownership)
- **Form 4** → `Form4` (ownership changes)
- **Form 5** → `Form5` (annual ownership)
- **Form 144** → `Form144` (sale notice)

### Offerings
- **Form D** → `FormD` (private placement)
- **Form C/C-U/C-AR/C-TR** → `FormC` (crowdfunding)

### Institutional
- **13F-HR/13F-NT** → `ThirteenF` (institutional holdings)

### Other
- **EFFECT** → `Effect` (effectiveness notice)
- **MA-I** → `MunicipalAdvisorForm` (muni advisor)
- **NPORT-P/NPORT-EX** → `FundReport` (fund reports)

### Fallback
- **Any form with XBRL** → `XBRL` (if no specific object)

---

## Common Patterns

### Pattern 1: Check if data object available

```python
filing = company.get_filings(form="10-K")[0]
obj = filing.obj()

if obj:
    # Work with data object
    print(f"Got {type(obj).__name__} object")
else:
    # Fall back to Filing API
    print("No data object available")
```

### Pattern 2: Type-specific handling

```python
from edgar.company_reports import TenK, TenQ
from edgar.ownership import Form4

filing = get_filing_somehow()
obj = filing.obj()

if isinstance(obj, (TenK, TenQ)):
    # Handle financial reports
    xbrl = filing.xbrl()
    income = xbrl.statements.income_statement()

elif isinstance(obj, Form4):
    # Handle insider transactions
    if obj.common_stock_sales is not None and not obj.common_stock_sales.empty:
        for idx, sale in obj.common_stock_sales.iterrows():
            shares = sale['Shares']
            price = sale['Price']
            value = shares * price
            print(f"Insider {obj.insider_name} sold {shares:,} shares at ${price:.2f} (${value:,.2f})")
```

### Pattern 3: Batch processing with data objects

```python
filings = company.get_filings(form="4")  # Get all Form 4s

for filing in filings:
    form4 = filing.obj()
    if form4 and form4.transactions:
        for txn in form4.transactions:
            if txn.transaction_code == 'P':  # Purchase
                print(f"{filing.filing_date}: Bought {txn.shares} shares")
```

### Pattern 4: Direct access vs. obj()

```python
# Direct Filing access (faster for metadata)
filing_date = filing.filing_date
company_name = filing.company

# Data object access (for parsed data)
tenk = filing.obj()
# ... work with structured 10-K data
```

---

## Data Object Discovery

Most data objects support API discovery similar to EdgarTools core objects:

### Using repr()
```python
filing = company.get_filings(form="4")[0]
form4 = filing.obj()
print(form4)  # Shows formatted overview
```

### Using .docs (if available)
```python
# Some data objects have .docs property
obj.docs  # Show API guide
obj.docs.search("transaction")  # Find transaction-related methods
```

### Using dir() and help()
```python
# Inspect available attributes
print(dir(form4))

# Get help
help(form4.transactions)
```

---

## Architecture Notes

### The obj() Function Implementation

Located in `edgar/__init__.py`, the `obj()` function uses pattern matching to route form types to their data objects:

```python
def obj(sec_filing: Filing) -> Optional[object]:
    """Return the data object for the filing based on form type."""

    if matches_form(sec_filing, "10-K"):
        return TenK(sec_filing)
    elif matches_form(sec_filing, "4"):
        xml = sec_filing.xml()
        if xml:
            return Form4(**Ownership.parse_xml(xml))
    # ... more form type routing

    # Fallback: return XBRL if available
    filing_xbrl = sec_filing.xbrl()
    if filing_xbrl:
        return filing_xbrl
```

### Why Two Layers?

**Separation of concerns**:
- **Filing layer**: Generic filing operations (metadata, documents, search)
- **Data object layer**: Form-specific business logic (parsed fields, domain methods)

**Benefits**:
- Filing API stays simple and consistent
- Form-specific complexity isolated in data objects
- Easy to add new form types without changing Filing
- Type safety for form-specific fields

---

## Token Efficiency

### Filing vs Data Object

| Access Method | Token Cost | Use When |
|---------------|------------|----------|
| `repr(filing)` | ~125 tokens | Need filing metadata |
| `filing.text()` | N/A* | Need document content |
| `repr(obj)` | Varies** | Need data object overview |
| `obj.text()` | Varies** | Need AI-optimized data |

*Filing.text() returns full document content (50K+ tokens)
**Depends on data object type and implementation

### Data Object Token Estimates

| Data Object | repr() | .text() (if available) |
|-------------|--------|------------------------|
| TenK | ~2,000 | TBD |
| TenQ | ~2,000 | TBD |
| Form4 | ~500 | TBD |
| FormD | ~1,200 | TBD |
| ThirteenF | ~800 | TBD |

*Note: .text() methods may not be implemented for all data objects yet*

---

## Future Enhancements

### Planned Improvements

1. **Individual Data Object Documentation**
   - Detailed guides for each data object type
   - Located in module docs folders (e.g., `edgar/ownership/docs/Form4.md`)

2. **Consistent .docs Support**
   - Add `.docs` property to all data objects
   - Searchable API documentation like Company, Filing, XBRL

3. **AI-Optimized .text() Methods**
   - Markdown-KV format for each data object
   - Token-efficient representations

4. **Enhanced Type Hints**
   - Return type hints for obj() function
   - Better IDE support

---

## See Also

**Tutorial Documentation**:
- [skill.md](./skill.md) - Main EdgarTools patterns
- [workflows.md](./workflows.md) - End-to-end analysis examples
- [objects.md](./objects.md) - Core EdgarTools objects (Company, Filing, XBRL)

**Reference Documentation**:
- [form-types-reference.md](./form-types-reference.md) - Complete SEC form catalog
- [api-reference/](./api-reference/) - Detailed API docs for core objects

**External Resources**:
- [SEC Form Types](https://www.sec.gov/forms) - Official SEC form descriptions
- [EdgarTools Docs](https://edgartools.readthedocs.io) - Complete library documentation

---

## Quick Examples by Use Case

### Insider Trading Analysis
```python
from edgar import Company

company = Company("AAPL")
form4s = company.get_filings(form="4")

for filing in form4s[:10]:  # First 10 filings
    form4 = filing.obj()
    if form4:
        print(f"{filing.filing_date}: {form4.insider_name} ({form4.position})")

        # Check sales
        if form4.common_stock_sales is not None and not form4.common_stock_sales.empty:
            for idx, sale in form4.common_stock_sales.iterrows():
                shares = sale['Shares']
                price = sale['Price']
                print(f"  Sale: {shares:,} shares @ ${price:.2f}")

        # Check purchases
        if form4.common_stock_purchases is not None and not form4.common_stock_purchases.empty:
            for idx, purchase in form4.common_stock_purchases.iterrows():
                shares = purchase['Shares']
                price = purchase['Price']
                print(f"  Purchase: {shares:,} shares @ ${price:.2f}")
```

### Private Placement Tracking
```python
from edgar import get_filings

formd_filings = get_filings(form="D")

for filing in formd_filings:
    formd = filing.obj()
    if formd:
        print(f"{filing.company}: ${formd.total_offering_amount:,}")
        print(f"  Use: {formd.use_of_proceeds}")
```

### Institutional Holdings
```python
from edgar import Company

company = Company("BRK-A")  # Berkshire Hathaway
filing = company.get_filings(form="13F-HR")[0]

thirteenf = filing.obj()
if thirteenf:
    top_holdings = thirteenf.get_top_holdings(10)
    for holding in top_holdings:
        print(f"{holding.name}: {holding.shares:,} shares, ${holding.value:,}")
```

### Financial Reports
```python
from edgar import Company

company = Company("MSFT")
tenk = company.get_filings(form="10-K")[0].obj()

if tenk:
    # TenK provides access to XBRL and structured sections
    xbrl = tenk.filing.xbrl()  # Access underlying XBRL
    income = xbrl.statements.income_statement()
    print(income)
```

---

**Last Updated**: 2025-10-31
**Version**: 1.0
