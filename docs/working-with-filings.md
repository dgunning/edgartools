# Working with a Filing
A filing is a handle to a single SEC EDGAR filing. With it you can access all the documents and datafiles on the filing.

### Getting a Filing
You can get a filing using the `[]` operator. For example:

```python
filings = get_filings()
filing = filings[0]
```

### Open a Filing in your browser
The `open` method opens the main document of a filing in your browser
```python
filing.open()
``` 

### Open the Filing homepage
The filing homepage is the landing page for a filing. It links to all the documents and datafiles on the filing.
```python
filing.open_homepage()
```

### View the Filing
This downloads the filing's HTML content, parses it and displays it as close to the original as is possible in the console or in a Jupyter notebook. This is a good way to preview a filing, but won't be perfect so if you need a perfect copy of the filing, you should use the `open` method to view it in the browser.
```python
filing.view()
```

### Get the HTML of a Filing
This downloads the filing's HTML content and returns it as a string.
```python
html = filing.html()
```

### Getting the text of a Filing
The `text` method returns the text of a filing
```python
text = filing.text()
```

## Working with Attachments

The `attachments` attribute returns a list of the attachments on a filing
```python
attachments = filing.attachments
```

### Looping through Attachments
You can loop through attachments using the `for` loop.
```python
for attachment in filings.attachments:
    print(attachment)
```

### Getting an Attachment
The `[]` operator returns an attachment by index
```python
attachment = filing.attachments[0]
```

### Viewing an Attachment
The `view` method displays the text of an attachment in the console. This works for text and html attachments
```python
attachment.view()
```

### Downloading Attachments
The `download` method downloads all the attachments to a folder of your choice.
```python
filing.attachments.download(path)