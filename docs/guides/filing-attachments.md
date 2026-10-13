# Attachments

Once you have a `Filing` instance you can access the attachments for the filing using the `attachments` property.

```python
filing.attachments
```

![attachments](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/attachments.png)

## Which of these need parentheses

The rule is worth learning once, because getting it wrong fails quietly rather
than loudly: **properties hand back something already there; methods do work.**

| | Shape | What you get |
|---|---|---|
| `attachment.content` | property | the raw document, as downloaded |
| `attachment.text()` | **method** | text extracted from HTML |
| `attachment.markdown()` | **method** | markdown, or `None` if not HTML |
| `filing.document` | property | the primary document, as an `Attachment` |
| `filing.text()` | **method** | text of the whole filing |

Two of these surprise people often enough to be worth calling out (GH #841):

**`attachment.text` without parentheses is a method object, not the text** — and
a method object is always truthy, so the mistake survives an `if`:

```python
if attachment.text:        # always True, even for an empty document
    ...
print(attachment.text)     # <bound method Attachment.text of ...>
print(attachment.text())   # the actual text
```

**`filing.document` is an `Attachment`, not a parsed `Document`.** The names are
close and the objects are not:

```python
filing.document              # Attachment — the primary document as filed
filing.document.text()       # its text

from edgar.documents import Document   # a different thing entirely:
filing.text()                          # the parsed-and-extracted text
```

`text()` stays a method deliberately rather than becoming a property. It takes
arguments — `Document.text(clean=..., include_tables=..., max_length=...)` — and
a property cannot. For the whole filing, `filing.text()` and `filing.markdown()`
are the entry points; reach for an individual `attachment` when you want one
exhibit rather than the document.

### Auto-Parsed Exhibits

Some exhibit types are automatically parsed when accessed through a data object:

- **EX-21** (Subsidiaries): `tenk.subsidiaries` returns a `SubsidiaryList` with name, jurisdiction, and ownership percentage for each subsidiary.

### Get an attachment by index
You can get an attachment by index using the `[]` operator and using the `Seq` number of the attachment.
The primary filing document is always at index **1**, and is usually HTML or XML.

```python
attachment = filing.attachments[1]
attachment
```

![attachments](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/snowflake-attachments.png)


### Viewing an attachment

You can view the attachment in a browser using the `view()` method. This works if the attachment is a text or html file.

```python
attachment.view()
```
![attachments](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/view-attachment.png)

This extracts the text of the attachment and renders it in the console. If you need to get the text use the `text()` method.

### Getting the text content of an attachment

You can get the text content of an attachment using the `text()` function.

```python
text = attachment.text()
print(text)
```

This will print the text content of the attachment.

### Converting HTML attachments to markdown

You can convert HTML attachments to markdown format using the `markdown()` method.

```python
# Convert a single HTML attachment to markdown
attachment = filing.attachments[1]  # Get the primary document
if attachment.is_html():
    markdown_content = attachment.markdown()
    print(markdown_content)
```

The `markdown()` method returns `None` for non-HTML attachments, so you can safely call it on any attachment. Images are rendered as Markdown image links with absolute SEC archive URLs, resolved against the attachment's own URL.

Page-break markers are not rendered. The parser treats page-break rules and
page-number footers as print layout and drops them; the `include_page_breaks`
and `start_page_number` arguments were removed in 6.0 (see the
[upgrade guide](../upgrade/6.0.md#page-breaks-are-not-rendered-any-more) for
what to use instead).

### Batch markdown conversion

You can convert all HTML attachments in a filing to markdown at once:

```python
# Convert all HTML attachments
markdown_dict = filing.attachments.markdown()

# Result is a dictionary: {"filename.htm": "markdown content", ...}
for filename, content in markdown_dict.items():
    print(f"--- {filename} ---")
    print(content[:500])  # Show first 500 characters
```

### Saving markdown content

You can save the markdown content to files:

```python
# Save individual attachment markdown
attachment = filing.attachments[1]
markdown_content = attachment.markdown()
if markdown_content:
    with open(f"{attachment.document}.md", "w") as f:
        f.write(markdown_content)

# Save all HTML attachments as markdown files
markdown_dict = filing.attachments.markdown()
for doc_name, markdown_content in markdown_dict.items():
    # Remove extension and add .md
    base_name = doc_name.rsplit('.', 1)[0]
    with open(f"{base_name}.md", "w") as f:
        f.write(markdown_content)
```


### Downloading an attachment

You can download the attachment using the `download()` method. This will download the attachment to the current working directory.

```python
attachment.download('/path/to/download')
```

If the path is a directory the attachment will be downloaded to that directory using the original name of the file.

If the path is a file the attachment will be downloaded to that file. This allows you to rename the attachment.

If you don't provide a path the content of the attachment will be returned as a string.




