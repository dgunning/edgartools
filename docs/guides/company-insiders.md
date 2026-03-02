---
description: Get a list of company insiders from SEC filings including officers, directors, and 10%+ beneficial owners.
---

# Company Insiders: Find Officers, Directors, and Major Shareholders

This guide shows how to get a list of insiders for a company by writing a simple script to loop through their Form 4 filings and getting the **name** and **position**.


## 1. Deciding on an appropriate date range

The approach is to get all Form 4 Insider filings for the past 6 months. To specify the date range we use a use `timedelta` to subtract 6 months from `datetime.now()`

```python
from datetime import datetime, timedelta
from edgar import *

date_range = ((datetime.now() - timedelta(days=6*30)) # Approximate 6 months
              .strftime('%Y-%m-%d:'))  
```

## 2. Getting the company filings
Now we can use the `Company` class to get the company filings for the past 6 months.

```python
c: Company = Company(ticker)
filings: EntityFilings = c.get_filings(form='4', filing_date=date_range)
```

## 3. Collecting data from each Form 4

Now we loop through each filing and get the ownership summary, which contains the insider names and their positions. 
Each Form4 has an `OwnershipSummary` object that we can convert to a DataFrame.

```python
dfs = [] # List to hold DataFrames for each filing
for filing in tqdm(filings):
    form4: Form4 = filing.obj()
    summary = form4.get_ownership_summary()
    dfs.append(summary.to_dataframe()[['Insider', 'Position']])
```

## 4. Combining the DataFrames

Finally, we can concatenate all the DataFrames into a single DataFrame and drop duplicates to get a unique list of insiders.

```python
import pandas as pd
insiders = (pd.concat(dfs, ignore_index=True)
                 .drop_duplicates().reset_index(drop=True)
                 .sort_values(by='Position',
                              key=lambda col: col == 'Director', 
                              ascending=True)
            )
```

## 5. Putting it all together

The complete code to get the insiders for a company is as follows. Note that we put it inside a function so we can easily reuse it for different tickers.

```python
import pandas as pd
from rich import print
from tqdm.auto import tqdm

from edgar import *
from edgar.entity import EntityFilings
from edgar.ownership import Form4
from datetime import datetime, timedelta


# Calculate the date 6 months ago from today

date_range = ((datetime.now() - timedelta(days=6*30)) # Approximate 6 months
              .strftime('%Y-%m-%d:'))


def get_insiders(ticker):
    c: Company = Company(ticker)
    filings: EntityFilings = c.get_filings(form='4', filing_date=date_range)

    dfs = []

    for filing in tqdm(filings):
        form4: Form4 = filing.obj()
        summary = form4.get_ownership_summary()
        dfs.append(summary.to_dataframe()[['Insider', 'Position']])

    insiders = (pd.concat(dfs, ignore_index=True)
                 .drop_duplicates().reset_index(drop=True)
                 .sort_values(by='Position', key=lambda col: col == 'Director', ascending=True)
                 )
    return insiders

if __name__ == '__main__':
    insiders = get_insiders("NFLX")
    print(insiders)
```

!!! tip "See this on edgar.tools"
    The script above loops through Form 4 filings to build an insider list for one company. **edgar.tools** has this pre-computed across 186K+ insider filings with 802K+ transactions — including net buy/sell sentiment and executive profiles.

    - **[See Netflix's insiders and transactions instantly →](https://app.edgar.tools/companies/NFLX?utm_source=edgartools-docs&utm_medium=see-live&utm_content=company-insiders)**
    - **[See Apple's insider trading activity →](https://app.edgar.tools/companies/AAPL?utm_source=edgartools-docs&utm_medium=see-live&utm_content=company-insiders)**

    No loops, no waiting. Free tier available. [Pricing →](https://app.edgar.tools/pricing?utm_source=edgartools-docs&utm_medium=see-live&utm_content=company-insiders)
