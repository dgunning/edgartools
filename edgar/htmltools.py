import re
from dataclasses import dataclass
from functools import lru_cache
from io import StringIO
from typing import Any, Optional, List

import pandas as pd
from lxml import html as lxml_html
from rich import box
from rich.panel import Panel
from rich.table import Table

from edgar._rich import repr_rich

__all__ = [
    "Element",
    "get_tables",
    "html_to_text",
    'html_sections',
    "ChunkedDocument",
    "extract_elements",
    "clean_dataframe",
    "dataframe_to_text",
    "get_text_elements",
    "get_table_elements",
    "table_html_to_dataframe",
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


def html_sections(html_str: str,
                  ignore_tables: bool = False) -> List[str]:
    """split the html into sections"""
    elements = extract_elements(html_str)
    if ignore_tables:
        return [str(element.element)
                for element in elements
                if not element.type == 'table']
    else:
        return [dataframe_to_text(element.table)
                if element.type == 'table' else str(element.element)
                for element in elements]


def html_to_text(html_str: str,
                 ignore_tables: bool = True,
                 sep: str = '\n'
                 ) -> str:
    """Convert the html to text using the unstructured library"""
    return sep.join(html_sections(html_str, ignore_tables=ignore_tables))


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

    df = clean_dataframe(pd.DataFrame(data, columns=data[0]))
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
    column_widths = df.apply(lambda col: col.astype(str).str.len().max())

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
def extract_elements(html_str: str):
    from unstructured.partition.html import partition_html
    elements = partition_html(text=html_str)
    output_els = []
    for idx, element in enumerate(elements):
        element_type = str(type(element))
        if "HTMLTable" in element_type:
            # Make sure the table is not empty
            table_html = str(element.metadata.text_as_html)
            table_df = table_html_to_dataframe(table_html) if table_html else pd.DataFrame()
            output_els.append(
                Element(id=f"id_{idx}", type="table", element=element, table=table_df)
            )
        else:
            output_els.append(Element(id=f"id_{idx}", type="text", element=element))
    return output_els


def get_table_elements(elements: List[Element],
                       min_table_rows: int = None,
                       min_table_cols: int = None):
    # Get the table elements
    return [e for e in elements
            if e.type == "table"
            and (min_table_rows is None or len(e.table) >= min_table_rows)
            and (min_table_cols is None or len(e.table.columns) >= min_table_cols)]


def get_text_elements(elements: List[Element]):
    return [e for e in elements if e.type == "text"]


def chunk(html, chunk_size: int = 1000, buffer=500):
    """
    Break html into chunks
    """
    # Use function import to avoid the startup time imposed by unstructured
    from unstructured.partition.html import partition_html
    from unstructured.chunking.title import chunk_by_title

    elements = partition_html(text=html)
    chunks = chunk_by_title(elements,
                            combine_text_under_n_chars=0,
                            new_after_n_chars=chunk_size,
                            max_characters=chunk_size + max(0, buffer))
    return chunks


def chunks2df(chunks):
    """Convert the chunks to a dataframe"""


    chunk_df = pd.DataFrame([
        {'text': el.text.strip(),
         'table': 'Table' in chunk.__class__.__name__}
        for el in chunks]
    ).assign(chars=lambda df: df.text.apply(len),
             item=lambda df: df.text.str.extract('^(Item \d+\.\d+|Item \d+[A-Z]?)', expand=False, flags=re.IGNORECASE),
             part=lambda df: df.text.str.extract('^(PART [IV]+)', flags=re.IGNORECASE),
             signature=lambda df: df.text.str.match('^SIGNATURE', re.IGNORECASE),
             toc=lambda df: df.text.str.match('^Table of Contents$', re.IGNORECASE),
             is_empty=lambda df: df.text.str.contains('^$', na=True)
             )
    # Foward fill item and parts
    # Handle deprecation warning in fillna(method='ffill')
    pandas_version = tuple(map(int, pd.__version__.split('.')))
    if pandas_version >= (2, 1, 0):
        chunk_df.loc[:, 'item'] = chunk_df.item.ffill().fillna("")
        chunk_df.loc[:, 'part'] = chunk_df.part.ffill().fillna("")
    else:
        chunk_df.loc[:, 'item'] = chunk_df.item.fillna(method='ffill').fillna("")
        chunk_df.loc[:, 'part'] = chunk_df.part.fillna(method='ffill').fillna("")


    signature_loc = chunk_df[chunk_df.signature].index[0]
    chunk_df.loc[signature_loc:, 'item'] = ""
    chunk_df.loc[signature_loc:, 'part'] = ""
    return chunk_df


def render_table(chunk):
    table_html = str(chunk.metadata.text_as_html)
    table_df = table_html_to_dataframe(table_html) if table_html else pd.DataFrame()
    return dataframe_to_text(table_df)


def render_chunks(chunks):
    return '\n'.join([render_table(chunk)
                      if "HTMLTable" in str(type(chunk))
                      else chunk.text
                      for chunk in chunks]
                     )


class ChunkedDocument:
    """
    Contains the html as broken into chunks
    """

    def __init__(self,
                 html: str,
                 chunk_size: int = 1000,
                 chunk_buffer: int = 500):
        """
        :param html: The filing html
        :param chunk_size: How large should the chunk be
        """
        self.chunks = chunk(html, chunk_size, chunk_buffer)
        self.chunk_size = chunk_size
        self.chunk_buffer = chunk_buffer

    @lru_cache(maxsize=4)
    def as_dataframe(self):
        return chunks2df(self.chunks)

    def list_items(self):
        df = self.as_dataframe()
        return [item for item in df.item.drop_duplicates().tolist() if item]

    def _chunks_for(self, item_or_part: str, col: str = 'item'):
        chunk_df = self.as_dataframe()

        # Handle cases where the item has the decimal point e.g. 5.02
        item_or_part = item_or_part.replace('.', '\.')
        pattern = re.compile(rf'^{item_or_part}$', flags=re.IGNORECASE)

        col_mask = chunk_df[col].str.match(pattern)
        toc_mask = ~chunk_df.toc
        empty_mask = ~chunk_df.is_empty

        mask = col_mask & toc_mask & empty_mask

        for i in mask[mask].index:
            yield self.chunks[i]

    def chunks_for_item(self, item: str):
        return self._chunks_for(item, col='item')

    def chunks_for_part(self, part: str):
        return self._chunks_for(part, col='part')

    def average_chunk_size(self):
        return int(self.as_dataframe().chars.mean())

    def __len__(self):
        return len(self.chunks)

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.chunks[item]
        elif isinstance(item, str):
            if item.startswith("Item"):
                return render_chunks(self.chunks_for_item(item))
            elif item.startswith("Part"):
                return render_chunks(self.chunks_for_part(item))

    def __iter__(self):
        return iter(self.chunks)

    def __rich__(self):
        table = Table("Chunks",
                      "Items",
                      "Chunk Size/Buffer",
                      "Avg Size", box=box.SIMPLE)
        table.add_row(str(len(self.chunks)),
                      ",".join(self.list_items()),
                      f"{str(self.chunk_size)}/{str(self.chunk_buffer)}",
                      str(self.average_chunk_size()),
                      )
        return Panel(table, box=box.ROUNDED, title="HTML Document")

    def __repr__(self):
        return repr_rich(self.__rich__())
