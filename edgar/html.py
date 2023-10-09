from lxml import html as lxml_html
import pandas as pd
from unstructured.partition.html import partition_html
from dataclasses import dataclass
from typing import Any, Optional, List
from lxml.etree import HTMLParser
from io import StringIO
from functools import lru_cache

__all__ = [
    "Element",
    "extract_elements",
    "get_tables",
    "clean_dataframe",
    "html_to_text",
    "table_html_to_dataframe",
    "dataframe_to_text",
    "get_table_elements",
    "get_text_elements"
]


@dataclass
class Element:
    id: str
    type: str
    element: Any
    summary: Optional[str] = None
    table: Optional[pd.DataFrame] = None


def clean_dataframe(df: pd.DataFrame):
    # Remove empty rows and columns
    df = (df.dropna(axis=1, how="all")
          .dropna(axis=0, how="all"))
    # Fill na
    df = df.fillna('')
    return df


def get_tables(html_str: str,
               table_filters: List = None) -> List[pd.DataFrame]:
    table_filters = table_filters or [filter_small_table]
    tables = pd.read_html(StringIO(html_str))
    return [
        table for table in tables
        if not all([tf(table) for tf in table_filters])
    ]


def html_to_text(html_str: str,
                 ignore_tables: bool = True,
                 sep: str = '\n'
                 ) -> str:
    """Convert the html to text using the unstructured library"""
    elements = extract_elements(html_str)
    if ignore_tables:
        return sep.join([str(element.element)
                         for element in elements
                         if not element.type == 'table'])
    else:
        return sep.join([dataframe_to_text(element.table)
                         if element.type == 'table' else str(element.element)
                         for element in elements]
                        )


def table_html_to_dataframe(html_str):
    """Convert the table html to a dataframe """
    tree = lxml_html.fromstring(html_str)
    table_element = tree.xpath("//table")[0]
    rows = table_element.xpath(".//tr")

    data = []
    for row in rows:
        cols = row.xpath(".//td")
        cols = [c.text.strip() if c.text is not None else "" for c in cols]
        data.append(cols)

    df = clean_dataframe(pd.DataFrame(data[1:], columns=data[0]))
    return df


def dataframe_to_text(df, include_index=False, include_headers=False):
    """
    Convert a Pandas DataFrame to a plain text string, with formatting options for including
    the index and column headers.

    Parameters:
    - df (pd.DataFrame): The dataframe to convert
    - include_index (bool): Whether to include the index in the text output. Defaults to True.
    - include_headers (bool): Whether to include column headers in the text output. Defaults to True.

    Returns:
    str: The dataframe converted to a text string.
    """

    # Getting the maximum width for each column
    column_widths = df.astype(str).applymap(len).max()

    # If including indexes, get the maximum width of the index
    index_label = ''
    if include_index:
        index_label = "Index"
        index_width = max(df.index.astype(str).map(len).max(), len(index_label))
    else:
        index_width = 0

    # Initialize an empty string to store the text
    text_output = ""

    # Include column headers if specified
    if include_headers:
        # Add index label if specified
        if include_index:
            text_output += f"{index_label:<{index_width}}\t"

        # Create and add the header row
        headers = [f"{col:<{width}}" for col, width in zip(df.columns, column_widths)]
        text_output += '\t'.join(headers) + '\n'

    # Loop through each row of the dataframe
    for index, row in df.iterrows():
        # Include index if specified
        if include_index:
            text_output += f"{index:<{index_width}}\t"

        # Format each value according to the column width and concatenate
        row_values = [f"{val:<{width}}" for val, width in zip(row.astype(str), column_widths)]
        text_output += '\t'.join(row_values) + '\n'

    return text_output


def filter_small_table(table: pd.DataFrame, min_rows: int = 2, min_cols: int = 2):
    return len(table) >= min_rows and len(table.columns) >= min_cols


@lru_cache(maxsize=4)
def extract_elements(html_str: str, table_filters: List = None):
    table_filters = table_filters or [filter_small_table]
    elements = partition_html(text=html_str, parser=HTMLParser())
    output_els = []
    for idx, element in enumerate(elements):
        element_type = str(type(element))
        if "HTMLTable" in element_type:
            table_df = table_html_to_dataframe(str(element.metadata.text_as_html))
            should_keep = all([tf(table_df) for tf in table_filters])
            if should_keep:
                output_els.append(
                    Element(id=f"id_{idx}", type="table", element=element, table=table_df)
                )
            else:
                pass
        else:
            output_els.append(Element(id=f"id_{idx}", type="text", element=element))
    return output_els


def get_table_elements(elements):
    return [e for e in elements if e.type == "table"]


def get_text_elements(elements):
    return [e for e in elements if e.type == "text"]
