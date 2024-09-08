import re
from dataclasses import dataclass
from functools import lru_cache
from functools import partial
from io import StringIO
from typing import Any, Optional, Dict, List, Callable

import numpy as np
import pandas as pd
from rich import box
from rich.panel import Panel
from rich.table import Table

from edgar.richtools import repr_rich
from edgar.datatools import compress_dataframe
from edgar.datatools import table_html_to_dataframe, dataframe_to_text
from edgar.documents import HtmlDocument, Block, TableBlock

__all__ = [
    "Element",
    "extract_tables",
    'chunks2df',
    "html_to_text",
    'html_sections',
    'decimal_chunk_fn',
    "ChunkedDocument",
    'remove_bold_tags',
    'detect_decimal_items',
    'adjust_for_empty_items',
    "get_text_elements",
]


@dataclass
class Element:
    id: str
    type: str
    element: Any
    summary: Optional[str] = None
    table: Optional[pd.DataFrame] = None


def extract_tables(html_str: str,
                   table_filters: List = None) -> List[pd.DataFrame]:
    table_filters = table_filters or [filter_tiny_table]
    tables = pd.read_html(StringIO(html_str))
    # Compress and filter the tables
    tables = [
        compress_dataframe(table)
        for table in tables
        # if not all([tf(table) for tf in table_filters])
    ]
    # Filter out empty tables
    tables = [table for table in tables if len(table) > 0]
    return tables


def html_sections(html_str: str,
                  ignore_tables: bool = False) -> List[str]:
    """split the html into sections"""
    document = HtmlDocument.from_html(html_str)
    return list(document.generate_text_chunks(ignore_tables=ignore_tables))


def html_to_text(html_str: str,
                 ignore_tables: bool = True,
                 sep: str = '\n'
                 ) -> str:
    document = HtmlDocument.from_html(html_str)
    if not ignore_tables:
        return document.text
    return sep.join([chunk for chunk in document.generate_text_chunks(ignore_tables=True)])


def is_inline_xbrl(html: str) -> bool:
    return "xmlns:ix=" in html[:2000]


def filter_tiny_table(table: pd.DataFrame, min_rows: int = 1, min_cols: int = 1):
    return len(table) >= min_rows and len(table.columns) >= min_cols


def remove_bold_tags(html_content):
    # Replace <b>...</b> and <strong>...</strong> tags with their content
    html_content = re.sub(r'<b>(.*?)</b>', r'\1', html_content)
    html_content = re.sub(r'<strong>(.*?)</strong>', r'\1', html_content)
    return html_content


def get_text_elements(elements: List[Element]):
    return [e for e in elements if e.type == "text"]


@lru_cache(maxsize=8)
def chunk(html: str):
    document = HtmlDocument.from_html(html)
    return list(document.generate_chunks())


int_item_pattern = r"^(Item [0-9]{1,2}[A-Z]?)\.?"
decimal_item_pattern = r"^(Item [0-9]{1,2}\.[0-9]{2})\.?"


def detect_table_of_contents(text: str):
    """Find the table of contents in the text"""
    return text.lower().count('item') > 10


def detect_signature(text: str) -> bool:
    """Find the signature block in the text"""
    matched = re.match(pattern='^SIGNATURE', string=text, flags=re.IGNORECASE | re.MULTILINE) is not None
    # If no results are true in the series try anothr pattern
    if not matched:
        matched = 'to be signed on its behalf by the undersigned' in text
    return matched


def detect_int_items(text: pd.Series):
    return text.str.extract(int_item_pattern, expand=False, flags=re.IGNORECASE | re.MULTILINE)


def detect_decimal_items(text: pd.Series):
    return text.str.extract(decimal_item_pattern, expand=False, flags=re.IGNORECASE | re.MULTILINE)


def find_next_item(index, normalized_items):
    """Find the next available item in the DataFrame starting from a given index."""
    for i in range(index + 1, len(normalized_items)):
        if normalized_items[i]:
            return normalized_items[i]
    return None


def normalize_item(item):
    """Normalize item string to a comparable format."""
    if not pd.isna(item):
        return re.sub(r"[^0-9A-Za-z ]", "", item)  # Remove all but numbers and letters
    return item


def extract_numeric_alpha_parts(item):
    """Extract numeric and alphabetic parts from an item."""
    numeric_part = int(re.search(r"[0-9]+", item).group()) if item else 0
    alpha_part = re.search(r"[A-Z]$", item)
    alpha_part = alpha_part.group() if alpha_part else ''
    return numeric_part, alpha_part


def is_valid_sequence(current_item, last_valid_item, next_available_item):
    """
    Determine if the current item is valid considering the last and next available items.
    """
    if not current_item or pd.isna(current_item) or not next_available_item or pd.isna(next_available_item):
        return False

    current_item_num, current_item_alpha = extract_numeric_alpha_parts(current_item)
    last_item_num, last_item_alpha = extract_numeric_alpha_parts(last_valid_item)
    next_item_num, next_item_alpha = extract_numeric_alpha_parts(next_available_item)

    # Check if the current item is greater than the last valid item and less than or equal to the next available item
    if current_item_num == last_item_num:
        return current_item_alpha > last_item_alpha
    elif current_item_num == next_item_num:
        return current_item_alpha < next_item_alpha or next_item_alpha == ''
    else:
        return last_item_num < current_item_num <= next_item_num


def adjust_detected_items(chunk_df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """
    Ensure that the items are in sequence and filter out any out of sequence items.
    """
    chunk_df['NormalizedItem'] = chunk_df['DetectedItem'].apply(normalize_item)
    normalized_items = chunk_df['NormalizedItem'].replace([np.nan], [None]).tolist()

    last_valid_item = ""
    valid_items = pd.Series(index=chunk_df.index, dtype=object)  # Create a series to store valid items

    # First find the index of the table of contents toc.
    toc_index_rows = chunk_df[chunk_df.Toc.notnull() & chunk_df.Toc]
    # If not found set to 0
    toc_index = toc_index_rows.index[0] if len(toc_index_rows) > 0 else 0

    # Iterate only through rows with non-null 'Item' starting at toc_index + 1

    for index, row in chunk_df.iterrows():
        if index < toc_index + 1:
            continue
        current_item = row['NormalizedItem']
        next_available_item = find_next_item(index, normalized_items)

        if is_valid_sequence(current_item, last_valid_item, next_available_item):
            valid_items[index] = current_item
            last_valid_item = current_item  # Update the last valid item
        else:
            valid_items[index] = pd.NA  # Mark as invalid/out of sequence

    chunk_df['Item'] = valid_items
    return chunk_df


def adjust_for_empty_items(chunk_df: pd.DataFrame,
                           **kwargs) -> pd.DataFrame:
    chunk_df['Item'] = chunk_df.DetectedItem
    for index, row in chunk_df[chunk_df.DetectedItem.notnull()].iterrows():
        item = row.Item
        # Get item_structure from kwargs
        item_structure = kwargs.get('item_structure')
        structure = item_structure.get_item(item)
        if not structure:
            break
        title = structure.get('Title')
        text = row.Text
        # Look for Item NUM Description Item in the text
        pattern = rf"^({item}.? {title}\W+)"
        match = re.search(pattern + "Item [1-9]", text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)

        # extract the item from text using decimal_item_pattern
        match = re.search(decimal_item_pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            new_item = match.group(1)
            chunk_df.loc[index, 'Item'] = new_item

    return chunk_df


def chunks2df(chunks: List[List[Block]],
              item_detector: Callable[[pd.Series], pd.Series] = detect_int_items,
              item_adjuster: Callable[[pd.DataFrame, Dict[str, Any]], pd.DataFrame] = adjust_detected_items,
              item_structure=None,
              ) -> pd.DataFrame:
    """Convert the chunks to a dataframe
        : item_detector: A function that detects the item in the text column
        : item_adjuster: A function that finds issues like out of sequence items and adjusts the item column
        : item_structure: A dictionary of items specific to each filing e.g. 8-K, 10-K, 10-Q
    """
    # Create a dataframe from the chunks. Add columns as necessary
    chunk_df = pd.DataFrame([{'Text': HtmlDocument._render_blocks(blocks), 'Table': isinstance(blocks, TableBlock)}
                             for blocks in chunks]
                            ).assign(Chars=lambda df: df.Text.apply(len),
                                     Signature=lambda df: df.Text.apply(detect_signature).fillna(""),
                                     TocLink=lambda df: df.Text.str.match('^Table of Contents$',
                                                                          flags=re.IGNORECASE | re.MULTILINE),
                                     Toc=lambda df: df.Text.head(100).apply(detect_table_of_contents),
                                     Empty=lambda df: df.Text.str.contains('^$', na=True),
                                     Item=lambda df: item_detector(df.Text)
                                     )
    # If the row is 'toc' then set the item and part to empty
    chunk_df.loc[chunk_df.Toc.notnull() & chunk_df.Toc, 'Item'] = ""
    # if item_adjuster:
    # chunk_df = item_adjuster(chunk_df, **{'item_structure': item_structure, 'item_detector': item_detector})

    # Foward fill item and parts
    # Handle deprecation warning in fillna(method='ffill')
    pandas_version = tuple(map(int, pd.__version__.split('.')))
    if pandas_version >= (2, 1, 0):
        chunk_df.Item = chunk_df.Item.ffill().infer_objects(copy=False)
    else:
        chunk_df.Item = chunk_df.Item.fillna(method='ffill')

    # After forward fill handle the signature at the bottom
    signature_rows = chunk_df[chunk_df.Signature]
    if len(signature_rows) > 0:
        signature_loc = signature_rows.index[0]
        chunk_df.loc[signature_loc:, 'Item'] = pd.NA
        chunk_df.Signature = chunk_df.Signature.fillna("")

    # Fill the Item column with "" then set to title case
    chunk_df.Item = chunk_df.Item.fillna("").str.title()

    # Finalize the colums
    chunk_df = chunk_df[['Text', 'Table', 'Chars', 'Signature', 'TocLink', 'Toc', 'Empty', 'Item']]
    return chunk_df


# This function is used by 8-K and other filings that have the item form 1.02 for example
decimal_chunk_fn = partial(chunks2df,
                           item_detector=detect_decimal_items,
                           item_adjuster=adjust_for_empty_items)


def render_table(table_chunk):
    table_html = str(table_chunk.metadata.text_as_html)
    table_df = table_html_to_dataframe(table_html) if table_html else pd.DataFrame()
    return dataframe_to_text(table_df)


class RenderedHtml:

    def __init__(self, text: str):
        self.text = text

    def __eq__(self, other):
        if isinstance(other, str):
            return self.text == other
        return self.text == other.text

    def __contains__(self, text: str):
        return text in self.text

    def __hash__(self):
        return hash(self.text)

    def __rich__(self):
        return Panel(self.text, box=box.SIMPLE)

    def __repr__(self):
        return repr_rich(self.__rich__())


def render_chunks(chunks):
    text = '\n'.join([render_table(el)
                      if "HTMLTable" in str(type(el))
                      else el.text
                      for el in chunks])
    # if the text is empty return None
    if not text:
        return None
    return RenderedHtml(text.strip())


class ChunkedDocument:
    """
    Contains the html as broken into chunks
    """

    def __init__(self,
                 html: str,
                 chunk_fn: Callable[[List], pd.DataFrame] = chunks2df):
        """
        :param html: The filing html
        :param chunk_fn: A function that converts the chunks to a dataframe
        """
        self.chunks = chunk(html)
        self._chunked_data = chunk_fn(self.chunks)
        self.chunk_fn = chunk_fn

    @lru_cache(maxsize=4)
    def as_dataframe(self):
        return self.chunk_fn(self.chunks)

    def show_items(self, df_query: str, *columns):
        result = self._chunked_data.query(df_query)
        if len(columns) > 0:
            columns = ["Text"] + list(columns)
            result = result.filter(columns)

        return result

    def list_items(self):
        return [item for item in self._chunked_data.Item.drop_duplicates().tolist() if item]

    def _chunks_for(self, item_or_part: str, col: str = 'Item'):
        chunk_df = self._chunked_data

        # Handle cases where the item has the decimal point e.g. 5.02
        item_or_part = item_or_part.replace('.', '\.')
        pattern = re.compile(rf'^{item_or_part}$', flags=re.IGNORECASE)

        col_mask = chunk_df[col].str.match(pattern)
        toc_mask = ~(~chunk_df.Toc.notnull() & chunk_df.Toc)
        empty_mask = ~chunk_df.Empty

        mask = col_mask & toc_mask & empty_mask

        for i in mask[mask].index:
            yield self.chunks[i]

    def chunks_for_item(self, item: str):
        return self._chunks_for(item, col='Item')

    def chunks_for_part(self, part: str):
        return self._chunks_for(part, col='Part')

    def average_chunk_size(self):
        return int(self._chunked_data.Chars.mean())

    def __len__(self):
        return len(self.chunks)

    def __getitem__(self, item):
        if isinstance(item, int):
            chunks = [self.chunks[item]]
        elif isinstance(item, str):
            chunks = list(self.chunks_for_item(item))
        else:
            return None
        if len(chunks) == 0:
            return None
        # render the nested List of List [str]
        return "".join(["".join(block.get_text()
                                for block in chunk)
                        for chunk in chunks])

    def __iter__(self):
        return iter(self.chunks)

    def __rich__(self):
        table = Table("Chunks",
                      "Items",
                      "Avg Size", box=box.SIMPLE)
        table.add_row(str(len(self.chunks)),
                      ",".join(self.list_items()),
                      str(self.average_chunk_size()),
                      )
        return Panel(table, box=box.ROUNDED, title="HTML Document")

    def __repr__(self):
        return repr_rich(self.__rich__())


