# Navigating Filings

## Paginating filings
The `Filings` object is a container for a list of filings. The list of filings can  be large but by default you can only see the first page of filings. 

To change the page, you can paginate filings using the `next` and `prev` methods. For example:

```python
filings = get_filings()
filings.next()
filings.previous()
```

## Looping through filings

You can loop through filings using the `for` loop. For example:

```python

filings = get_filings()
for filing in filings:
    ...
    # Do something with the filing
```

## Getting Related Filings

Filings can be related to other filings using the file number. In some cases this relationship can be meaningful, as in they represent a group of filings for a specific securities offering.
The link between the filing is via the `file_number` attribute of the filing, which is an identifier that the SEC uses to group filings.

You can get related filings using the `get_related_filings` method. For example:

```python
filing = get_filing('0000320193-22-000002')
filings = filing.related_filings()
```


