from edgar.html2markdown import *
from pathlib import Path
from edgar import Company, Filing
from rich.markdown import Markdown
from rich import print

def test_parse_markdown():
    html_content = Path('data/NextPoint.8K.html').read_text()
    parser = SECHTMLParser(html_content)
    document = parser.parse()

    # Render to markdown
    renderer = MarkdownRenderer(document)
    markdown_content = renderer.render()
    print(markdown_content)


def test_filing_to_markdown():
    filing = Filing(company='Apple Inc.', cik=320193, form='8-K', filing_date='2024-10-31', accession_no='0000320193-24-000120')
    filing = Company("AAPL").latest("10-K")
    #filing.open()
    print(str(filing))
    html = filing.html()
    parser = SECHTMLParser(html)
    document = parser.parse()
    md = to_markdown(filing.html())
    #print(Markdown(md))
    print(md)

    """
    <div align='center'>UNITED STATES

SECURITIES AND EXCHANGE COMMISSION

Washington, D.C. 20549

FORM 8-K

CURRENT REPORT

Pursuant to Section 13 OR 15(d) of The Securities Exchange Act of 1934

October 31, 2024

Date of Report (Date of earliest event reported)

Apple Inc.

(Exact name of Registrant as specified in its charter)</div>

|  |  |  |  |  |
| :--- | :--- | :--- | :--- | :--- |
| California |  | 001-36743 |  | 94-2404110 |
| (State or other jurisdictionof incorporation) |  | (CommissionFile Number) |  | (I.R.S. EmployerIdentification No.) |

<div align='center'>One Apple Park Way 

Cupertino, California 95014 

(Address of principal executive offices) (Zip Code)

(408) 996-1010 

(Registrant’s telephone number, including area code)

Not applicable

(Former name or former address, if changed since last report.)</div>

Check the appropriate box below if the Form 8-K filing is intended to simultaneously satisfy the filing obligation of the Registrant under any of the following provisions:

|  |  |
| :--- | :--- |
| ☐ | Written communications pursuant to Rule 425 under the Securities Act (17 CFR 230.425) |

|  |  |
| :--- | :--- |
| ☐ | Soliciting material pursuant to Rule 14a-12 under the Exchange Act (17 CFR 240.14a-12) |

|  |  |
| :--- | :--- |
| ☐ | Pre-commencement communications pursuant to Rule 14d-2(b) under the Exchange Act (17 CFR 240.14d-2(b)) |

|  |  |
| :--- | :--- |
| ☐ | Pre-commencement communications pursuant to Rule 13e-4(c) under the Exchange Act (17 CFR 240.13e-4(c)) |

<div align='center'>Securities registered pursuant to Section 12(b) of the Act:</div>

|  |  |  |
| :--- | :--- | :--- |
| Title of each class | Trading symbol(s) | Name of each exchange on which registered |
| Common Stock, $0.00001 par value per share | AAPL | The Nasdaq Stock Market LLC |
| 0.000% Notes due 2025 | — | The Nasdaq Stock Market LLC |
| 0.875% Notes due 2025 | — | The Nasdaq Stock Market LLC |
| 1.625% Notes due 2026 | — | The Nasdaq Stock Market LLC |
| 2.000% Notes due 2027 | — | The Nasdaq Stock Market LLC |
| 1.375% Notes due 2029 | — | The Nasdaq Stock Market LLC |
| 3.050% Notes due 2029 | — | The Nasdaq Stock Market LLC |
| 0.500% Notes due 2031 | — | The Nasdaq Stock Market LLC |
| 3.600% Notes due 2042 | — | The Nasdaq Stock Market LLC |

Indicate by check mark whether the Registrant is an emerging growth company as defined in Rule 405 of the Securities Act of 1933 (§230.405 of this chapter) or Rule 12b-2 of the Securities Exchange Act of 1934 (§240.12b-2 of this chapter).

Emerging growth company        ☐

If an emerging growth company, indicate by check mark if the Registrant has elected not to use the extended transition period for complying with any new or revised financial accounting standards provided pursuant to Section 13(a) of the Exchange Act.  ☐

Item 2.02    Results of Operations and Financial Condition.

On October 31, 2024, Apple Inc. (“Apple”) issued a press release regarding Apple’s financial results for its fourth fiscal quarter ended September 28, 2024. A copy of Apple’s press release is attached hereto as Exhibit 99.1.

The information contained in this Current Report shall not be deemed “filed” for purposes of Section 18 of the Securities Exchange Act of 1934, as amended (the “Exchange Act”), or incorporated by reference in any filing under the Securities Act of 1933, as amended, or the Exchange Act, except as shall be expressly set forth by specific reference in such a filing.

Item 9.01    Financial Statements and Exhibits.

(d)Exhibits.

|  |  |  |
| :--- | :--- | :--- |
| ExhibitNumber |  | Exhibit Description |
| 99.1 |  | Press release issued by Apple Inc. on October 31, 2024. |
| 104 |  | Inline XBRL for the cover page of this Current Report on Form 8-K. |

<div align='center'>SIGNATURE</div>

Pursuant to the requirements of the Securities Exchange Act of 1934, the Registrant has duly caused this report to be signed on its behalf by the undersigned hereunto duly authorized.

|  |  |  |  |
| :--- | :--- | :--- | :--- |
| Date: | October 31, 2024 |  | Apple Inc. |
|  |  |  | By: |  | /s/ Luca Maestri |
|  |  |  |  |  | Luca Maestri |
|  |  |  |  |  | Senior Vice President,Chief Financial Officer |
    """
