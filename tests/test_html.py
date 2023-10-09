from edgar.html import extract_elements, table_html_to_dataframe, html_to_text, get_table_elements, get_text_elements
from pathlib import Path
from rich import print
import pandas as pd
pd.options.display.max_columns = 12

Nvidia_2021_10k = Path("data/Nvidia.10-K.html").read_text()

def test_html2df():
    table_html = """
    <table>
  <thead>
    <tr>
        <td>id</td><td>name</td><td>age</td>
    </tr>
  </thead>
  <tbody>
    <tr>
        <td>1</td><td>John</td><td>20</td>
    </tr>
    <tr>
        <td>2</td><td>Smith</td><td>30</td>
    </tr>
  </tbody>
</table>
    """
    df = table_html_to_dataframe(table_html)
    assert len(df) == 2
    print(df)


def test_extract_elements():
    elements = extract_elements(Nvidia_2021_10k)

    table_elements = get_table_elements(elements)
    assert all([e.table is not None for e in table_elements])

    text_elements = get_text_elements(elements)
    assert all([e.type == "text" for e in text_elements])

    assert len(table_elements) + len(text_elements) == len(elements)

def test_html2text():
    tenk_text = html_to_text(Nvidia_2021_10k)

    # Include tables
    tenk_text_with_tables = html_to_text(Nvidia_2021_10k, ignore_tables=False)

    assert len(tenk_text_with_tables) > len(tenk_text)
    print(tenk_text_with_tables)

