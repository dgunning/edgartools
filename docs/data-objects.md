# Data Objects

Data Objects are a concept used in edgartools to contain the data from a filing. For example, a `TenK` object contains the data from a 10-K filin, and a `ThirteenF` object contains the data from a 13F-HR filing and so on.

Data Objects are created by automatically downloading and parsing filings into data objects.
Currently, the following forms are supported:


| Form                       | Data Object                  | Description                           |
|----------------------------|------------------------------|---------------------------------------|
| 10-K                       | `TenK`                       | Annual report                         |
| 10-Q                       | `TenQ`                       | Quarterly report                      |
| 8-K                        | `EightK`                     | Current report                        |
| MA-I                       | `MunicipalAdvisorForm`       | Municipal advisor initial filing      |
| Form 144                   | `Form144`                    | Notice of proposed sale of securities |
| C, C-U, C-AR, C-TR         | `FormC`                      | Form C Crowdfunding Offering          |
| D                          | `FormD`                      | Form D Offering                       |
| 3,4,5                      | `Ownership`                  | Ownership reports                     |
| 13F-HR                     | `ThirteenF`                  | 13F Holdings Report                   |
| NPORT-P                    | `FundReport`                 | Fund Report                           |
| EFFECT                     | `Effect`                     | Notice of Effectiveness               |
| And other filing with XBRL | `FilingXbrl`                 |                                       |       


## Usage

To get a data object for a filing, you can use the `obj()` method on a `Filing` object.
For example, to get the data object for a **13F-HR** filing you can do the following:

```python
from edgar import get_filings
filings = get_filings()
filing = filings[0]
thirteen_f = filing.obj()
```