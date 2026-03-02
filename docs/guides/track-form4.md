---
title: "Track Insider Trading: Analyze SEC Form 4 Buy and Sell Transactions"
description: "Monitor insider trading activity from SEC Form 4 filings. Track purchases, sales, and option exercises by company officers and directors."
category: "guides"
difficulty: "intermediate"
time_required: "20 minutes"
prerequisites: ["installation", "concepts/sec-filings"]
related: ["insider-filings", "data-objects"]
keywords: ["Form 4", "insider trading", "ownership", "transactions", "SEC filings", "directors", "officers", "buy", "sell"]
---

# Track Insider Trading: Analyze SEC Form 4 Buy and Sell Transactions

## Introduction

Form 4 filings provide valuable insights into insider trading activity. When corporate insiders (directors, officers, or beneficial owners of more than 10% of a company's stock) buy or sell shares of their company, they must report these transactions to the SEC via Form 4 filings. These filings can reveal important signals about insiders' confidence in their company's future.

edgartools makes it easy to retrieve, parse, and analyze Form 4 filings programmatically, allowing you to track insider trading patterns without manual effort.

## Understanding Form 4 Filings

Before diving into code, it's important to understand what Form 4 filings contain:

- **Reporting Person Information**: Name, relationship to the company (e.g., CEO, Director)
- **Transaction Details**: Date, type of security, number of shares, price per share
- **Transaction Codes**: Codes that indicate the nature of the transaction (e.g., P for purchase, S for sale)
- **Ownership Information**: Direct or indirect ownership, total shares held after transaction

## Retrieving Form 4 Filings

### By Company

To retrieve Form 4 filings for a specific company:

```python
from edgar import Company, get_filings

# Using Company object
company = Company("AAPL")
form4_filings = company.get_filings(form="4")

# Or using global get_filings
form4_filings = get_filings(form="4", ticker="AAPL")

# View the most recent filings
recent_filings = form4_filings.head(5)
for filing in recent_filings:
    print(f"Date: {filing.filing_date}, Person: {filing.reporting_owner_name}")
```

### By Date Range

To find Form 4 filings within a specific date range:

```python
# Get Form 4 filings from Jan 1, 2024 to present
form4_filings = get_filings(
    form="4",
    ticker="MSFT",
    start_date="2024-01-01",
    end_date="2024-07-01"
)

print(f"Found {len(form4_filings)} Form 4 filings")
```

### By Reporting Person

To focus on a specific insider's activity:

```python
form4_filings = get_filings(form="4", ticker="TSLA")

# Filter by reporting person's name
musk_filings = form4_filings.filter(reporting_owner_name="Musk Elon")

print(f"Found {len(musk_filings)} Form 4 filings by Elon Musk")
```

## Working with Form 4 Data Objects

edgartools provides a specialized `Form4` data object that makes it easy to access structured data from these filings:

```python
# Get a specific Form 4 filing
filing = form4_filings.latest()

# Convert to Form4 data object
form4 = filing.obj()

# Access basic metadata
print(f"Filing date: {form4.filing_date}")
print(f"Reporting owner: {form4.reporting_owner_name}")
print(f"Relationship: {form4.reporting_owner_relationship}")
print(f"Company: {form4.issuer_name} ({form4.issuer_ticker})")
```

### Accessing Transaction Details

Form 4 filings can contain multiple transactions. Access them through the `transactions` property:

```python
# Examine all transactions in the filing
for i, transaction in enumerate(form4.transactions):
    print(f"\nTransaction {i+1}:")
    print(f"Date: {transaction.transaction_date}")
    print(f"Type: {transaction.transaction_code} ({transaction.get_transaction_code_description()})")
    print(f"Shares: {transaction.shares}")
    print(f"Price: ${transaction.price_per_share:.2f}")
    print(f"Value: ${transaction.value:.2f}")
    print(f"Direct/Indirect: {transaction.ownership}")
    print(f"Shares owned after: {transaction.shares_owned_following_transaction}")
```

### Understanding Transaction Codes

Form 4 transactions use codes to indicate different types of transactions:

```python
# Common transaction codes and their meanings
transaction_codes = {
    'P': 'Open market or private purchase of securities',
    'S': 'Open market or private sale of securities',
    'A': 'Grant, award, or other acquisition',
    'D': 'Disposition to the issuer (e.g., forfeiture, cancellation)',
    'M': 'Exercise or conversion of derivative security',
    'G': 'Gift',
    'V': 'Voluntary transaction with issuer'
}

# Check what type of transaction this is
for transaction in form4.transactions:
    code = transaction.transaction_code
    description = transaction_codes.get(code, "Other transaction type")
    print(f"Transaction code {code}: {description}")
    print(f"Shares: {transaction.shares}")
```

## Analyzing Insider Transactions

### Calculating Net Shares Traded

Calculate whether an insider is buying or selling on net:

```python
# Calculate net shares traded in a filing
net_shares = form4.get_net_shares_traded()
if net_shares > 0:
    print(f"Insider BOUGHT a net {net_shares:,} shares")
elif net_shares < 0:
    print(f"Insider SOLD a net {abs(net_shares):,} shares")
else:
    print("Insider had no net change in position")
```

### Aggregating Transactions by Company

Track recent insider activity for a company:

```python
import pandas as pd
from datetime import datetime, timedelta

# Get all Form 4 filings for a company in the last 90 days
end_date = datetime.today()
start_date = end_date - timedelta(days=90)

company = Company("NVDA")
recent_form4 = company.get_filings(
    form="4",
    start_date=start_date.strftime("%Y-%m-%d"),
    end_date=end_date.strftime("%Y-%m-%d")
)

# Analyze all filings
transactions_data = []
for filing in recent_form4:
    try:
        form4 = filing.obj()
        net_shares = form4.get_net_shares_traded()
        
        transactions_data.append({
            'date': form4.filing_date,
            'name': form4.reporting_owner_name,
            'relationship': form4.reporting_owner_relationship,
            'net_shares': net_shares,
            'transaction_type': 'BUY' if net_shares > 0 else 'SELL' if net_shares < 0 else 'NEUTRAL'
        })
    except Exception as e:
        print(f"Error processing filing {filing.accession_number}: {e}")

# Create a DataFrame for analysis
df = pd.DataFrame(transactions_data)
if not df.empty:
    # Summarize by person
    person_summary = df.groupby('name').agg({
        'net_shares': 'sum',
        'date': 'count'
    }).rename(columns={'date': 'num_transactions'}).sort_values('net_shares')
    
    print("\nInsider Activity by Person:")
    print(person_summary)
    
    # Summarize by transaction type
    type_counts = df['transaction_type'].value_counts()
    print(f"\nTransaction Types: {dict(type_counts)}")
```

### Tracking Significant Transactions

Identify large or otherwise noteworthy transactions:

```python
def get_significant_transactions(company_ticker, min_value=1000000, days=180):
    """Find Form 4 transactions above a certain dollar value."""
    company = Company(company_ticker)
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)
    
    form4_filings = company.get_filings(
        form="4",
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d")
    )
    
    significant_transactions = []
    for filing in form4_filings:
        try:
            form4 = filing.obj()
            
            for transaction in form4.transactions:
                if transaction.value and transaction.value >= min_value:
                    significant_transactions.append({
                        'date': transaction.transaction_date,
                        'filing_date': form4.filing_date,
                        'name': form4.reporting_owner_name,
                        'relationship': form4.reporting_owner_relationship,
                        'shares': transaction.shares,
                        'price': transaction.price_per_share,
                        'value': transaction.value,
                        'type': transaction.transaction_code,
                        'accession': filing.accession_number
                    })
        except Exception as e:
            print(f"Error processing filing {filing.accession_number}: {e}")
    
    return pd.DataFrame(significant_transactions).sort_values('value', ascending=False)

# Find significant transactions for a company
significant_df = get_significant_transactions("AMZN", min_value=5000000)
print(f"\nFound {len(significant_df)} significant transactions")
if not significant_df.empty:
    print(significant_df.head())
```

## Advanced Analysis Techniques

### Correlating with Stock Price

Combine insider trading data with stock price data to identify patterns:

```python
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf  # You'll need to install this package

def analyze_insider_vs_price(ticker, days=180):
    """Compare insider transactions with stock price movement."""
    # Get stock price data
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)
    stock_data = yf.download(ticker, start=start_date, end=end_date)
    
    # Get insider transactions
    company = Company(ticker)
    form4_filings = company.get_filings(
        form="4",
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d")
    )
    
    # Process transactions
    insider_data = []
    for filing in form4_filings:
        try:
            form4 = filing.obj()
            net_shares = form4.get_net_shares_traded()
            
            if net_shares != 0:  # Only include actual buys or sells
                insider_data.append({
                    'date': pd.to_datetime(form4.filing_date),
                    'net_shares': net_shares,
                    'transaction_type': 'BUY' if net_shares > 0 else 'SELL'
                })
        except Exception as e:
            print(f"Error processing filing: {e}")
    
    insider_df = pd.DataFrame(insider_data)
    
    # Skip plotting if we don't have both datasets
    if insider_df.empty or stock_data.empty:
        print("Insufficient data for analysis")
        return
    
    # Create a plot
    plt.figure(figsize=(12, 6))
    
    # Plot stock price
    plt.plot(stock_data.index, stock_data['Close'], label='Stock Price')
    
    # Mark insider transactions
    for _, row in insider_df.iterrows():
        color = 'green' if row['transaction_type'] == 'BUY' else 'red'
        marker = '^' if row['transaction_type'] == 'BUY' else 'v'
        plt.scatter(row['date'], stock_data.loc[stock_data.index >= row['date']].iloc[0]['Close'], 
                   color=color, s=100, marker=marker)
    
    plt.title(f'{ticker} Stock Price vs Insider Transactions')
    plt.legend(['Stock Price', 'Insider Buy', 'Insider Sell'])
    plt.grid(True)
    plt.savefig(f'{ticker}_insider_analysis.png')
    plt.close()
    
    return insider_df, stock_data

# Run the analysis
analyze_insider_vs_price("MSFT")
```

## Best Practices and Tips

### Handling Transaction Complexities

Form 4 filings can have complexities to watch out for:

1. **Multiple Transactions**: A single Form 4 can contain multiple transactions
2. **Amended Filings**: Form 4/A filings are amendments to previous filings
3. **Indirect Ownership**: Transactions might involve indirect ownership through trusts or other entities
4. **Derivative Securities**: Some transactions involve options, warrants, or other derivatives

Handle these cases with careful code:

```python
def process_form4_safely(filing):
    try:
        # Check if this is an amended filing
        if filing.form_type == "4/A":
            print(f"This is an amended filing: {filing.accession_number}")
        
        form4 = filing.obj()
        
        # Handle multiple transactions
        transaction_count = len(form4.transactions)
        if transaction_count > 1:
            print(f"Filing has {transaction_count} transactions")
        
        # Check for indirect ownership
        for transaction in form4.transactions:
            if transaction.ownership == "I":  # Indirect ownership
                print(f"Indirect ownership transaction found: {transaction.ownership_nature}")
        
        # Check for derivative securities
        if hasattr(form4, 'derivative_transactions') and form4.derivative_transactions:
            print(f"Filing includes {len(form4.derivative_transactions)} derivative transactions")
            
        return form4
    except Exception as e:
        print(f"Error processing Form 4: {e}")
        return None
```

### Performance Considerations

When working with large volumes of Form 4 filings:

1. **Use Local Storage**: Store filings locally to avoid repeated downloads
2. **Process in Batches**: Process filings in manageable batches
3. **Filter Early**: Apply filters early in your pipeline to reduce the dataset size

```python
from edgar import enable_local_storage

# Enable local storage
enable_local_storage("/path/to/storage")

# Process filings in batches
all_filings = get_filings(form="4", year=2024)
batch_size = 100

for i in range(0, len(all_filings), batch_size):
    batch = all_filings[i:i+batch_size]
    print(f"Processing batch {i//batch_size + 1} ({len(batch)} filings)")
    
    # Process this batch
    for filing in batch:
        # Your processing code here
        pass
```

## Conclusion

Tracking insider trading with Form 4 filings can provide valuable insights into the sentiment of company insiders. edgartools makes it easy to retrieve, parse, and analyze these filings at scale, allowing you to incorporate insider trading data into your investment research or analysis workflows.

By understanding the structure of Form 4 filings and leveraging edgartools' data objects, you can efficiently extract meaningful insights about insider activity without manual effort.

Whether you're tracking transactions by company executives, monitoring significant purchases or sales, or correlating insider activity with stock price movements, edgartools provides the foundation for comprehensive insider trading analysis.

## Additional Resources

- [SEC Form 4 Guide](https://www.sec.gov/files/form4.pdf)
- [Insider Trading Legal Framework](https://www.sec.gov/Archives/edgar/data/25743/000138713113000737/ex14_02.htm)
- [Form 4 Data Objects API Reference](../data-objects.md)
