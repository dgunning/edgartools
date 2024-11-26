from bs4 import BeautifulSoup

from edgar.files.html_documents import table_to_markdown, table_to_text
from edgar import *
from edgar.files.htmltools import ChunkedDocument


def test_table_to_text():
    html = """
    <table>
        <tr><th></th><th>Total Number of<br>Shares Purchased</th><th colspan="2">Average Price<br>Paid per<br>Share</th><th>Total Number of<br>Shares Purchased as<br>Part of Publicly<br>Announced<br>Program</th><th>Approximate Dollar<br>Value of Shares that<br>May Yet Be<br>Purchased<br>Under the Program</th></tr>
        <tr><td>March 1, 2024—March 31, 2024</td><td>0.4</td><td>$</td><td>121.76</td><td>0.4</td><td>$</td><td>7,065.6</td></tr>
        <tr><td>April 1, 2024—April 30, 2024</td><td>0.4</td><td>$</td><td>119.95</td><td>0.4</td><td>$</td><td>7,014.0</td></tr>
        <tr><td>May 1, 2024—May 31, 2024</td><td>0.4</td><td>$</td><td>119.69</td><td>0.4</td><td>$</td><td>6,962.3</td></tr>
        <tr><td>Total</td><td>1.2</td><td>$</td><td>120.42</td><td>1.2</td><td>$</td><td>21,031.9</td></tr>
    </table>
    """

    soup = BeautifulSoup(html, 'html.parser')
    table_tag = soup.find('table')
    table_text = table_to_text(table_tag)
    print()
    print(table_text)


def test_basic_table():
    html = """
    <table>
        <tr><th>Header 1</th><th>Header 2</th></tr>
        <tr><td>Data 1</td><td>Data 2</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = table_to_text(soup.find('table'))
    print()
    print(result)
    expected = (
        "Header 1   Header 2\n"
        "-------------------\n"
        "Data 1     Data 2  "
    )
    assert result == expected


def test_empty_first_cell():
    html = """
    <table>
        <tr><th></th><th>Header</th></tr>
        <tr><td>Data 1</td><td>Data 2</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = table_to_text(soup.find('table'))
    print()
    print(result)
    expected = (
        "         Header\n"
        "---------------\n"
        "Data 1   Data 2"
    )
    assert result == expected


def test_multiline_header():
    html = """
    <table>
        <tr><th>Header 1<br>Line 2</th><th>Header 2</th></tr>
        <tr><td>Data 1</td><td>Data 2</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = table_to_text(soup.find('table'))
    print()
    print(result)
    expected = (
        "Header 1   Header 2\n"
        " Line 2            \n"
        "-------------------\n"
        "Data 1     Data 2  "
    )
    assert result == expected


def test_colspan():
    html = """
    <table>
        <tr><th>Header 1</th><th>Header 2</th><th>Header 3</th></tr>
        <tr><td colspan="2">Wide Data</td><td>Normal</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = table_to_text(soup.find('table'))
    print()
    print(result)
    expected = (
        "Header 1   Header 2   Header 3\n"
        "------------------------------\n"
        "Wide Data             Normal  "
    )
    assert result == expected


def test_empty_table():
    html = "<table></table>"
    soup = BeautifulSoup(html, 'html.parser')
    result = table_to_text(soup.find('table'))
    assert result == ""

def test_table_with_empty_cells():
   html = '<table><tr><td></td><td colspan="3"></td></tr></table>'
   soup = BeautifulSoup(html, 'html.parser')
   result = table_to_text(soup.find('table'))
   assert result == ''

def test_complex_table():
    html = """
    <table>
        <tr><th>Date Range</th><th>Total Number of<br>Shares Purchased</th><th>Average Price<br>Paid per<br>Share</th><th>Total Number of<br>Shares Purchased as<br>Part of Publicly<br>Announced<br>Program</th><th>Approximate Dollar<br>Value of Shares that<br>May Yet Be<br>Purchased<br>Under the Program</th></tr>
        <tr><td>March 1, 2024—March 31, 2024</td><td>0.4</td><td>$</td><td>121.76</td><td>0.4</td><td>$</td><td>7,065.6</td></tr>
        <tr><td>April 1, 2024—April 30, 2024</td><td>0.4</td><td>$</td><td>119.95</td><td>0.4</td><td>$</td><td>7,014.0</td></tr>
        <tr><td>Total</td><td>1.2</td><td>$</td><td>120.42</td><td>1.2</td><td>$</td><td>14,079.6</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = table_to_text(soup.find('table'))
    print()
    print(result)
    expected = (
        "Date Range                      Total Number of   Average Price     Total Number of      Approximate Dollar  \n"
        "                                Shares Purchased    Paid per      Shares Purchased as   Value of Shares that \n"
        "                                                      Share         Part of Publicly         May Yet Be      \n"
        "                                                                       Announced             Purchased       \n"
        "                                                                        Program          Under the Program   \n"
        "-------------------------------------------------------------------------------------------------------------\n"
        "March 1, 2024—March 31, 2024                0.4         $121.76   0.4                                $7,065.6\n"
        "April 1, 2024—April 30, 2024                0.4         $119.95   0.4                                $7,014.0\n"
        "Total                                       1.2         $120.42   1.2                               $14,079.6"
    )
    #assert result == expected


def test_mismatched_columns():
    html = """
    <table>
        <tr><th>Header 1</th><th>Header 2</th></tr>
        <tr><td>Data 1</td><td>Data 2</td><td>Extra</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = table_to_text(soup.find('table'))
    expected = (
        "Header 1   Header 2         \n"
        "-----------------------------\n"
        "Data 1     Data 2     Extra "
    )
    #assert result == expected


def test_render_oracle_table():
    html ="""
    <table>
        <tr>
        <td>(in millions, except per share amounts)</td>
            <td></td>
            <td colspan="2">Total Number of<br/>Shares<br/>Purchased</td>
            <td></td>
            <td></td>
        <td colspan="2">Average Price<br/>Paid per<br/>Share</td>
            <td></td>
            <td></td>
        <td colspan="2">Total Number of<br/>Shares Purchased as<br/>Part of Publicly<br/>Announced<br/>Program</td>
            <td></td>
            <td></td>
        <td colspan="2">Approximate Dollar<br/>Value of Shares that<br/>May Yet Be<br/>Purchased<br/>Under the Program</td>
            <td></td>
        </tr>
    <tr>
    <td>March 1, 2024—March 31, 2024</td>
        <td></td>
        <td></td>
        <td>0.4</td>
        <td></td>
        <td></td>
        <td>$</td>
        <td>121.76</td>
        <td></td>
        <td></td>
        <td></td>
        <td>0.4</td>
        <td></td>
        <td></td>
        <td>$</td>
        <td>7,065.6</td>
        <td></td>
    </tr>
        <tr>
    <td>March 1, 2024—March 31, 2024</td>
        <td></td>
        <td></td>
        <td>0.4</td>
        <td></td>
        <td></td>
        <td>$</td>
        <td>121.76</td>
        <td></td>
        <td></td>
        <td></td>
        <td>0.4</td>
        <td></td>
        <td></td>
        <td>$</td>
        <td>7,065.6</td>
        <td></td>
    </tr>
    </table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = table_to_text(soup.find('table'))
    print()
    print(result)

def test_actual_filing():
    company = Company("MSFT")
    filing = company.get_filings(form="10-K").latest(1)
    html = filing.html()
    document:ChunkedDocument = ChunkedDocument(html)
    for table in document.tables():
        #print(table.table_element)
        print(table_to_text(table.table_element))
        print('\n')
        print("-" * 180)
        print('\n')

def test_broken_table():
    html = """
    <table cellpadding="0" cellspacing="0" style="font: 10pt Times New Roman, Times, Serif; width: 100%; margin-top: 0pt; margin-bottom: 0pt"><tr style="vertical-align: top; text-align: justify">
<td style="width: 0%"></td><td style="width: 0.75in; text-align: left"><span style="font-family: Times New Roman, Times, Serif; font-size: 10pt"><b>Item
                            5.02</b></span></td><td style="text-align: justify"><span style="font-family: Times New Roman, Times, Serif; font-size: 10pt"><b>Departure
of Directors or Certain Officers; Election of Directors; Appointment of Certain Officers. Compensatory Arrangements of Certain Officers.</b></span></td>
</tr></table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = table_to_markdown(soup.find('table'))
    print()
    print(result)