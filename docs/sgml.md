# SGML

The SEC EDGAR system uses a specialized subset of SGML (Standard Generalized Markup Language) for regulatory filings. 
While commonly referred to as SGML, it implements a simplified version with SEC-specific tags and structures. 
This format has been the backbone of SEC filings since the 1990s, chosen for its ability to maintain consistent document structure while supporting both structured data and free-form text.


## Understanding SGML Container Formats

You might be familiar with SGML from having seeing the **Full Text File (.txt)** or the **(.nc)** formats in SEC filings.

The SEC EDGAR system actually utilizes two distinct SGML container formats, each serving different purposes in the filing process:

### Complete Submission Text File (.txt)

The .txt format contains the complete submission as received by EDGAR, including all documents, headers, and content. This is the primary public-facing format that preserves the exact submission. A typical .txt container begins with:

```
<SEC-DOCUMENT>0000320193-24-000123.txt : 20241101
<SEC-HEADER>0000320193-24-000123.hdr.sgml : 20241101
<ACCEPTANCE-DATETIME>20241101060136
ACCESSION NUMBER:      0000320193-24-000123
```

The .txt container includes:
- Full document content
- SEC headers
- Metadata
- All exhibits and attachments
- Processing timestamps

### Non-Public Complete File (.nc)

The .nc format serves as a submission manifest or index file, containing metadata about the filing without the full content. This format is used for processing, validation, and internal SEC workflows. A typical .nc container starts with:

```
<SUBMISSION>
<ACCESSION-NUMBER>0002002260-24-000001
<TYPE>D
<PUBLIC-DOCUMENT-COUNT>1
<ITEMS>06b
<ITEMS>3C
```

The .nc container tracks:
- Submission type and status
- Document counts
- Reporting items
- Cross-reference information
- Processing instructions
- Special handling requirements

### Understanding the SEC Processing Pipeline

Understanding the relationship between these formats is crucial for processing SEC filings:

1. Initial submission includes both formats
2. .nc file is processed first for validation
3. .txt file is processed for content extraction
4. Both files are archived for record-keeping
5. Public access is primarily to the .txt content

This dual-format system enables the SEC to maintain separate processing pipelines for submission handling and public access while ensuring comprehensive record-keeping and validation.



## How edgartools uses SGML

The library uses the SGML to get the attachments and important metadata about the filing.

```python
filing.attachments
```
the library will get the SGML file and parse it to get the attachments. You will mostly work with the objects and attributes of the `Filing` class, rather than directly with the SGML file.

```python
    @property
    def attachments(self):
        # Return all the attachments on the filing
        sgml_filing: FilingSGML = self.sgml()
        return sgml_filing.attachments
```

The `sgml()` function will download the SGML file, or read from a file if using **LocalStorage**.

## The FilingSGML class

The `FilingSGML` class is used to parse the SGML file. It has a few methods to get the attachments, and the text of the filing.

### Parsing SGML from a file or a URL

The function `from_source` is used to create a `FilingSGML` object from a source. The source can be a string representing a file name or a URL, or it can be a `Path`

```python
sgml = FilingSGML.from_source("https://www.sec.gov/Archives/edgar/data/320193/000032019321000139/0000320193-21-000139.txt")

# OR

sgml = FilingSGML.from_source(Path("path/to/0001398344-24-000491.nc"))
```

This will parse either SGML format and return a `FilingSGML` object.

### Getting the attachments

The `attachments` property will return an `Attachments` class that contains the `Attachment`.

```python
attachments = sgml.attachments
```

### Getting the content of a file

You can get the content of a file using the `get_content` method.

```python
sgml.get_content("EX-101.INS")
```
### Getting html

You can get the html for the filing using the `html` method. This will find the primary HTML document in the `FilingSGML:` attachments, find the html and return it.

```python
html = sgml.html()
```

### Getting xml

You can get the xml for the filing using the `xml` method. This will find the primary XML document in the `FilingSGML:` attachments, find the xml and return it.
This function will return None if no XML document is found.

```python
sgml.xml()
```







