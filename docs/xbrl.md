# XBRL

**edgartools** has a sophisticated XBRL parser that can parse XBRL data from filings. This is mostly abstracted away behind the main classes you interact with in the library.

## Listing filings that have XBRL data 

The SEC has an index of filing that contain XBRL data. To get these filings you can use the `get_filings` function and pass `index="xbrl"` as an argument.

```python
filings = get_filings(index="xbrl")
```

## Getting XBRL from a filing

To get the XBRL data from a filing you can use the `xbrl` function of the `Filing` class.

```python
filing = filings[0]
xb = filing.xbrl()
```

If the filing does not have XBRL data, then `filing.xbrl()` will return `None`.

If the filing has only the XBRL instance document, then `filing.xbrl()` will return an `XbrlInstance` object.

If the filing has more complex XBRL data, especially for 10-K and 10-Q filings, the parser will return an `XbrlData` object which contains the `XbrlInstance` object, as well as other XBRL documents that are attached to the filing. In addition to the `XbrlInstance` document, these documents include *presentation, calculation, definition* and *label* documents.

## XbrlInstance

The main XBRL container for data is called XBRL instance. It contains the primary data reported for that filing.
The data is in a very well-structured XML format, but the EdgarTools XBRL parser unrolls that into a data frame.
For simple XBRL, the data inside an XBRL instance is self-contained, so it is straightforward to parse into data structures like data frames. 

## XBRLData

For more complicated XBRL, some aspects of the data will have to be resolved against the other XBRL files for that filing, such as the presentation and calculation files.
In this case, the parser will return an XBRLData container containing the XBRLInstance and the other XBRL files.

These files can include

- **presentation**: This file describes how the XBRL data is presented in the filing. It is used to resolve the hierarchy of the data.
- **calculation**: This file describes how the XBRL data is calculated. It is used to resolve the calculations of the data.
- **definition**: This file describes the definitions of the XBRL data. It is used to resolve the meaning of the data.
- **label**: This file describes the labels of the XBRL data. It is used to resolve the labels of the data.

