# User Journeys: Solve Real Problems with EdgarTools

This document showcases common workflows and tasks that financial professionals, developers, and researchers can accomplish using EdgarTools. Each journey addresses a specific problem and provides a concise code example.

<details>
<summary><H3>1. Company Financial Analysis</H3> - Analyze a company's financial health across multiple periods</summary>

**Problem:** Need to analyze a company's financial health across multiple periods.

```python
from edgar import find

# Get Microsoft's financial data for the last 3 years
company = find("MSFT")
financials = company.financials()

# Compare key metrics across years
revenue = financials.extract("Revenues")
net_income = financials.extract("NetIncomeLoss")

# Create a financial dashboard
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(10, 6))
revenue.plot(kind='bar', ax=ax, position=1, width=0.3, color='blue', alpha=0.7)
net_income.plot(kind='bar', ax=ax, position=0, width=0.3, color='green', alpha=0.7)

ax.set_title('Microsoft Financial Performance')
ax.legend(['Revenue', 'Net Income'])
ax.set_ylabel('USD (millions)')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
```

<!-- MEDIA PLACEHOLDER: Financial dashboard visualization -->
</details>

<details>
<summary><H3>2. Investment Fund Research</H3> - Analyze fund holdings and compare share classes</summary>

**Problem:** Need to analyze fund holdings and compare share classes.

```python
from edgar import find

# Find a fund by ticker
fund = find("VFIAX")  # Vanguard 500 Index Fund

# Get the fund's structure
classes = fund.get_classes()
print(f"Fund has {len(classes)} share classes")

# Get the latest portfolio holdings
portfolio = fund.get_portfolio()

# Show top 10 holdings by value
top_holdings = portfolio.sort_values('value', ascending=False).head(10)
top_holdings
```

<!-- MEDIA PLACEHOLDER: Fund portfolio visualization -->
</details>

<details>
<summary><H3>3. Insider Trading Analysis</H3> - Monitor insider transactions for investment signals</summary>

**Problem:** Monitor insider transactions for investment signals.

```python
from edgar import find, get_insider_transaction_filings

# Get recent insider transactions for Tesla
company = find("TSLA")
insider_filings = company.get_filings(form=[3, 4, 5], limit=20)

# Extract and analyze the transactions
transactions = []
for filing in insider_filings:
    form = obj(filing)
    if hasattr(form, 'transactions') and form.transactions is not None:
        for t in form.transactions:
            transactions.append({
                'date': t.transaction_date,
                'name': form.reporting_owner.name,
                'title': form.reporting_owner.title or 'Unknown',
                'type': t.transaction_code,
                'shares': t.shares,
                'price': t.price_per_share,
                'value': t.shares * t.price_per_share if t.price_per_share else None
            })

# Convert to DataFrame and analyze
import pandas as pd
tx_df = pd.DataFrame(transactions)

# Summarize by transaction type
tx_df.groupby('type').agg({
    'shares': 'sum',
    'value': 'sum'
}).sort_values('value', ascending=False)
```

<!-- MEDIA PLACEHOLDER: Insider trading visualization -->
</details>

<details>
<summary><H3>4. SEC Filing Discovery</H3> - Find specific types of filings across companies or time periods</summary>

**Problem:** Find specific types of filings across companies or time periods.

```python
from edgar import get_filings

# Get all 8-K filings (material events) from the last week
recent_8ks = get_filings(form="8-K", limit=50)

# Filter to find filings mentioning "acquisition"
acquisition_filings = []
for filing in recent_8ks:
    text = filing.text()
    if text and "acquisition" in text.lower():
        acquisition_filings.append({
            'company': filing.company_name,
            'date': filing.filing_date,
            'accession_no': filing.accession_no,
            'items': filing.items if hasattr(filing, 'items') else None
        })

# Convert to DataFrame
import pandas as pd
pd.DataFrame(acquisition_filings)
```

<!-- MEDIA PLACEHOLDER: Filing discovery results -->
</details>

<details>
<summary><H3>5. Financial Data Extraction</H3> - Extract structured financial data for analysis or modeling</summary>

**Problem:** Extract structured financial data for analysis or modeling.

```python
from edgar import find, obj

# Get the latest 10-Q for Amazon
company = find("AMZN")
latest_10q = company.get_filings(form="10-Q")[0]
tenq = obj(latest_10q)

# Extract all financial statements
balance_sheet = tenq.financials.balance_sheet
income_statement = tenq.financials.income_statement
cash_flow = tenq.financials.cash_flow

# Calculate key financial ratios
current_ratio = balance_sheet.loc['AssetsCurrent'] / balance_sheet.loc['LiabilitiesCurrent']
debt_to_equity = balance_sheet.loc['Liabilities'] / balance_sheet.loc['StockholdersEquity']
net_margin = income_statement.loc['NetIncomeLoss'] / income_statement.loc['Revenues']

print(f"Current Ratio: {current_ratio.iloc[0]:.2f}")
print(f"Debt-to-Equity: {debt_to_equity.iloc[0]:.2f}")
print(f"Net Margin: {net_margin.iloc[0]:.2%}")
```

<!-- MEDIA PLACEHOLDER: Financial ratios dashboard -->
</details>

<details>
<summary><H3>6. Fund Holdings Analysis</H3> - Analyze what stocks funds are holding and track changes</summary>

**Problem:** Analyze what stocks funds are holding and track changes.

```python
from edgar import find

# Find a major investment manager
blackrock = find("BLK")

# Get their recent 13F filings
filings_13f = blackrock.get_filings(form="13F-HR", limit=2)

# Extract holdings from the two most recent quarters
current_quarter = obj(filings_13f[0])
previous_quarter = obj(filings_13f[1])

# Compare holdings between quarters
current_holdings = current_quarter.holdings
previous_holdings = previous_quarter.holdings

# Merge to compare
import pandas as pd
merged = pd.merge(current_holdings, previous_holdings, 
                   on='nameOfIssuer', suffixes=('_current', '_previous'))

# Calculate changes
merged['value_change'] = merged['value_current'] - merged['value_previous']
merged['value_change_pct'] = (merged['value_change'] / merged['value_previous']) * 100

# Show biggest position increases
merged.sort_values('value_change', ascending=False).head(10)
```

<!-- MEDIA PLACEHOLDER: Holdings change visualization -->
</details>

<details>
<summary><H3>7. Regulatory Filing Monitoring</H3> - Stay updated on new filings from watched companies</summary>

**Problem:** Stay updated on new filings from watched companies.

```python
from edgar import find, get_current_filings

# Define a watchlist of companies
watchlist = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
watchlist_ciks = [find(ticker).cik for ticker in watchlist]

# Get today's filings
today_filings = get_current_filings()

# Filter to only show filings from companies on our watchlist
watchlist_filings = today_filings[today_filings.cik.isin(watchlist_ciks)]

# Display the filings
watchlist_filings[['company_name', 'form', 'filing_date', 'html_link']]
```

<!-- MEDIA PLACEHOLDER: Filing monitoring dashboard -->
</details>

<details>
<summary><H3>8. AI/LLM Integration</H3> - Clean, structured text from SEC filings for AI analysis or LLM processing</summary>

**Problem:** Need clean, structured text from SEC filings for AI analysis or LLM processing.

```python
from edgar import find

# Get a 10-K filing
company = find("NVDA")  # NVIDIA
filing = company.get_filings(form="10-K")[0]

# Extract clean, readable text (not raw HTML)
clean_text = filing.text()

# View the formatted text in a notebook or terminal
filing.view()

# Extract specific sections for targeted analysis
risk_factors = filing.get_section("Item 1A", "Risk Factors")

# Chunk text for LLM context windows
chunks = filing.chunk_text(chunk_size=4000, overlap=200)

# Process with your favorite LLM library
from langchain.llms import OpenAI

llm = OpenAI()
for i, chunk in enumerate(chunks[:3]):  # Process first 3 chunks as example
    print(f"Analysis of chunk {i+1}:
")
    response = llm.generate([f"Summarize the key points in this SEC filing text: {chunk}"])
    print(response.generations[0][0].text)
    print("\n---\n")
```

<!-- MEDIA PLACEHOLDER: AI/LLM integration visualization -->
</details>
