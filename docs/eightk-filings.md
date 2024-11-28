# Eight-K Filings

Imagine having instant access to a company's most critical corporate updates the moment they happen!

8-K filings are real-time windows into significant corporate events, revealing everything from 
leadership changes to major business transformations.

With **edgartools**, you can effortlessly retrieve and analyze these crucial SEC documents in just a few lines of Python code. 


## Getting 8-K filings for a company

The easiest way to get **8-K** filings is to get access to a company object and use the `latest` function.
You can restrict to the latest 5 filings by passing `n` as a parameter.

This returns a `Filings` object with multiple filings so to get a single filing use the bracket `[]` operator e.g. `filings[1]`.

```python
c = Company("AAPL")

filings = filings.latest("8-K", 5)
```

To get the last filing use `latest` without `n`. This returns a single `Filing` object.

```python
filing = filings.latest("8-K")
```
### Getting all 8-K filings

To get all filings use `get_filings(form="8-K")`

```python
filings = c.get_filings(form='8-K')
```

## Viewing the 8-K filing


