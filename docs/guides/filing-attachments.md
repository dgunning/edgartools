# Attachments

Once you have a `Filing` instance you can access the attachments for the filing using the `attachments` property.

```python
filing.attachments
```

![attachments](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/attachments.png)

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


### Downloading an attachment

You can download the attachment using the `download()` method. This will download the attachment to the current working directory.

```python
attachment.download('/path/to/download')
```

If the path is a directory the attachment will be downloaded to that directory using the original name of the file.

If the path is a file the attachment will be downloaded to that file. This allows you to rename the attachment.

If you don't provide a path the content of the attachment will be returned as a string.




