# XBRL

Some common filing types such as **10-K, 10-Q, 8-K** are generally filed with XBRL data, and you can get access to this data on the filing.



## Getting XBRL Filings

You can get the dataset of filings submitted with XBRL by passing `index="xbrl"` as a parameter to `get_filings`.

```python
filings = get_filings(2022,4, index="xbrl")
```
![XBL Filings](https://raw.githubusercontent.com/dgunning/edgartools/main/images/xbrl-filings.jpg)


## Extracted XBRL Documents

An XBRL filing can have the XBRL data in inline XBRL document, which is an XHTML document that can display as HTML in the browser,
or in extracted XML document, which is XML, or in both formats.

You can see the filing's extracted XBRL document using `filing.homepage.xbrl_document`

### Accessing the extracted XBRL document
```python
filing.homepage.xbrl_document
```

### Downloading the extracted XBRL document

You can download the raw XML using `download`
```python
xml = filing.homepage.xbrl_document.download()
```

### Parsing the XBRL into a FilingXBRL
Instead of downloading the XBRL as XML you can access it as a `FilingXBRL` object, which is the XML downloaded, parsed, and 
contained in a wrapper object. This object allows you to access the XBRL data as a pandas dataframe.

To get this, call `filing.xbrl()`
```python
filing_xbrl = filing.xbrl()
```
![XBRL Filings](https://raw.githubusercontent.com/dgunning/edgartools/main/images/extracted_xbrl.png)


## Getting the XBRL facts
The XBRL data is contained in a property called `facts`. You can work with this a a pandas dataframe
```python
filing_xbrl.facts
```