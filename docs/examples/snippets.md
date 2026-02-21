# EdgarTools SEO Code Snippets

Reusable, tested code snippets for use across blog posts, notebooks, README, and documentation.
Each snippet is self-contained, produces meaningful output, and works with edgartools 5.16+.

**Core message**: Free, no API key, 3 lines of Python.

---

## 1. Get a Company's Financial Statements

```python
from edgar import Company

tenk = Company("AAPL").get_filings(form="10-K")[0].obj()
print(tenk.financials.income_statement())
```

---

## 2. Search and Browse Filings

```python
from edgar import Company

filings = Company("MSFT").get_filings(form="10-K")
filing = filings[0]
filing.open()  # Opens in browser
```

---

## 3. Get Insider Trading Data

```python
from edgar import Company

form4s = Company("TSLA").get_filings(form="4").head(5)
for f in form4s:
    print(f.obj())
```

---

## 4. Track Hedge Fund Holdings (13F)

```python
from edgar import Company

thirteenf = Company(1423053).get_filings(form="13F-HR")[0].obj()  # Citadel Advisors
print(thirteenf.holdings)
```

---

## 5. Get Today's SEC Filings

```python
from edgar import get_current_filings

filings = get_current_filings().filter(form="8-K")
print(filings)
```

---

## 6. Get Revenue Across Years

```python
from edgar import Company

facts = Company("GOOG").get_facts()
print(facts.get_revenue())
```

---

## 7. Comparison: edgartools vs sec-api

```python
# edgartools — free, no API key, 3 lines
from edgar import Company

income = Company("AAPL").get_filings(form="10-K")[0].obj().financials.income_statement()
print(income)

# sec-api — $55-$239/month, API key required, 15+ lines
# from sec_api import QueryApi, XbrlApi
# api = QueryApi(api_key="YOUR_PAID_API_KEY")
# query = {"query": {"query_string": {"query": 'ticker:AAPL AND formType:"10-K"'}}}
# filings = api.get_filings(query)
# xbrl_api = XbrlApi(api_key="YOUR_PAID_API_KEY")
# xbrl_json = xbrl_api.xbrl_to_json(accession_no=filings[0]["accessionNo"])
# income = xbrl_json["StatementsOfIncome"]
# ... more parsing needed ...
```
