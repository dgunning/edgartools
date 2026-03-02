# Table Width Example

This example demonstrates how to control table column width when extracting text from SEC filings.

## Important Note

When working with 10-K or 10-Q filings:

```python
filing = company.get_filings(form="10-K").latest(1)

# filing.obj() returns a TenK object (not a Document)
tenk = filing.obj()  

# To get the Document object with text() method:
doc = tenk.document

# Now you can use text() with table_max_col_width
text = doc.text(table_max_col_width=500)
```

## Running the Example

Make sure to set your SEC identity first:

```python
from edgar import set_identity
set_identity("Your Name your.email@example.com")
```

Then run:
```bash
python table_width_example.py
```
