import re
import warnings
from dataclasses import dataclass
from functools import lru_cache, partial
from io import StringIO
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd
from rich import box
from rich.panel import Panel
from rich.table import Table

from edgar.core import pandas_version
from edgar.datatools import compress_dataframe
from edgar.files.html_documents import Block, HtmlDocument, LinkBlock, TableBlock, table_to_markdown
from edgar.richtools import repr_rich

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


int_item_pattern = r"^(Item\s{1,3}[0-9]{1,2}[A-Z]?)\.?"
decimal_item_pattern = r"^(Item\s{1,3}[0-9]{1,2}\.[0-9]{2})\.?"


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

def detect_part(text: pd.Series) -> pd.Series:
    """
    Detect and extract 'Part' sections such as 'PART I', 'Part II', etc., from the given text Series.

    Handles various formats found in SEC filings, including:
        - 'PART I. Financial Information'
        - 'Part II'
        - 'PART III — Executive Overview'
        - 'This section is PART IV'

    Returns:
        pd.Series: A series containing the extracted 'Part X' values (uppercase), or NaN if not found.
    """
    # Match patterns like 'PART I', 'Part II', 'PART III.', etc.
    part_pattern = r'^\b(PART\s+[IVXLC]+)\b'
    # Extract using case-insensitive matching and convert result to uppercase
    extracted = text.str.extract(part_pattern, flags=re.IGNORECASE | re.MULTILINE, expand=False)
    # Normalize to uppercase for consistency (e.g., 'Part I' → 'PART I')
    return extracted.str.upper().str.replace(r'\s+', ' ', regex=True)

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


def _render_blocks_using_old_markdown_tables(blocks:List[Block]):
    """
    This renders tables as the old style markdown tables
    Because thd item chunking uses these tables.
    So this is a split from the newer table rendering logic
    """
    return "".join([
        table_to_markdown(block.table_element) if isinstance(block, TableBlock) else block.get_text()
        for block in blocks
    ]).strip()

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
    chunk_df = pd.DataFrame([{'Text': _render_blocks_using_old_markdown_tables(blocks),
                              'Table': isinstance(blocks, TableBlock)}
                             for blocks in chunks]
                            ).assign(Chars=lambda df: df.Text.apply(len),
                                     Signature=lambda df: df.Text.apply(detect_signature).fillna(""),
                                     TocLink=lambda df: df.Text.str.match('^Table of Contents$',
                                                                          flags=re.IGNORECASE | re.MULTILINE),
                                     Toc=lambda df: df.Text.head(100).apply(detect_table_of_contents),
                                     Empty=lambda df: df.Text.str.contains('^$', na=True),
                                     Part=lambda df: detect_part(df.Text),
                                     Item=lambda df: item_detector(df.Text)
                                     )
    # If the row is 'toc' then set the item and part to empty
    chunk_df.loc[chunk_df.Toc.notnull() & chunk_df.Toc, 'Item'] = ""
    # if item_adjuster:
    # chunk_df = item_adjuster(chunk_df, **{'item_structure': item_structure, 'item_detector': item_detector})
    # Foward fill item and parts
    # Handle deprecation warning in fillna(method='ffill')
    if pandas_version >= (2, 1, 0):
        # Opt-in to pandas future behavior to avoid silent downcasting warnings
        with pd.option_context('future.no_silent_downcasting', True):
            chunk_df['Item'] = chunk_df['Item'].ffill()
            chunk_df['Part'] = chunk_df['Part'].ffill()
    else:
        chunk_df.Item = chunk_df.Item.fillna(method='ffill')
        chunk_df.Part = chunk_df.Part.fillna(method='ffill')

    # After forward fill handle the signature at the bottom
    signature_rows = chunk_df[chunk_df.Signature]
    if len(signature_rows) > 0:
        signature_loc = signature_rows.index[0]
        chunk_df.loc[signature_loc:, 'Item'] = pd.NA
        chunk_df.Signature = chunk_df.Signature.fillna("")

    # Fill the Item column with "" then set to title case
    chunk_df.Item = chunk_df.Item.fillna("").str.title()
    chunk_df.Part = chunk_df.Part.fillna("").str.title()

    # Normalize spaces in item
    chunk_df.Item = chunk_df.Item.apply(lambda item: re.sub(r'\s+', ' ', item))
    chunk_df.Part = chunk_df.Part.apply(lambda part: re.sub(r'\s+', ' ', part).strip())

    # Finalize the colums
    chunk_df = chunk_df[['Text', 'Table', 'Chars', 'Signature', 'TocLink', 'Toc', 'Empty', 'Part', 'Item']]

    return chunk_df


# This function is used by 8-K and other filings that have the item form 1.02 for example
decimal_chunk_fn = partial(chunks2df,
                           item_detector=detect_decimal_items,
                           item_adjuster=adjust_for_empty_items)


class ChunkedDocument:
    """
    Contains the html as broken into chunks
    """

    def __init__(self,
                 html: str,
                 chunk_fn: Callable[[List], pd.DataFrame] = chunks2df,
                 prefix_src: str = ""):
        """
        :param html: The filing html
        :param chunk_fn: A function that converts the chunks to a dataframe
        :param file_path: The path to the filing
        """
        self.chunks = chunk(html)
        self._chunked_data = chunk_fn(self.chunks)
        self.chunk_fn = chunk_fn
        self.prefix_src = prefix_src
        self.document_id_parse:Dict = {}

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
        item_or_part = item_or_part.replace('.', r'\.')
        pattern = re.compile(rf'^{item_or_part}$', flags=re.IGNORECASE)

        col_mask = chunk_df[col].str.match(pattern)
        toc_mask = ~(~chunk_df.Toc.notnull() & chunk_df.Toc)
        empty_mask = ~chunk_df.Empty

        mask = col_mask & toc_mask & empty_mask

        for i in mask[mask].index:
            yield self.chunks[i]

    def _chunks_mul_for(self, part: str, item: str):
        chunk_df = self._chunked_data

        # Handle cases where the item has the decimal point e.g. 5.02
        part = part.replace('.', r'\.')
        item = item.replace('.', r'\.')
        pattern_part = re.compile(rf'^{part}$', flags=re.IGNORECASE)
        pattern_item = re.compile(rf'^{item}$', flags=re.IGNORECASE)

        item_mask = chunk_df["Item"].str.match(pattern_item)
        part_mask = chunk_df["Part"].str.match(pattern_part)
        toc_mask = ~(~chunk_df.Toc.notnull() & chunk_df.Toc)
        empty_mask = ~chunk_df.Empty
        mask = part_mask & item_mask & toc_mask & empty_mask

        # Process to keep only consecutive indices, discard non-consecutive head/tail indices with warning
        index_list = mask[mask].index.to_list()
        if not index_list:
            return

        continuous_segments = []
        current_segment = [index_list[0]]

        for i in range(1, len(index_list)):
            if index_list[i] <= current_segment[-1] + 5:
                current_segment.append(index_list[i])
            else:
                continuous_segments.append(current_segment)
                current_segment = [index_list[i]]

        continuous_segments.append(current_segment)

        # retain only the longest continuous segment
        longest_segment = max(continuous_segments, key=len)

        # warning dity content
        if len(continuous_segments) > 1:
            discarded_indices = []
            for segment in continuous_segments:
                if segment != longest_segment:
                    discarded_indices.extend(segment)
            warnings.warn(
                f"Discarded non-continuous indices: {discarded_indices}. "
                f"""content: {''.join([
                        ''.join(block.get_text() for block in self.chunks[idx])
                        for idx in discarded_indices
                    ])}"""
            )
        for i in longest_segment:
            yield self.chunks[i]

    def chunks_for_item(self, item: str):
        """
        Returns chunks of text for a given item from the document.

        Args:
            item (str): The item name to retrieve chunks for.

        Returns:
            List[str]: List of text chunks corresponding to the specified item.
        """
        return self._chunks_for(item, col='Item')

    def chunks_for_part(self, part: str):
        return self._chunks_for(part, col='Part')

    def average_chunk_size(self):
        return int(self._chunked_data.Chars.mean())

    def tables(self):
        for chunk in self.chunks:
            for block in chunk:
                if isinstance(block, TableBlock):
                    yield block

    def assemble_block_text(self, chunks: List[Block]):

        if self.prefix_src:
            for chunk in chunks:
                for block in chunk:
                    if isinstance(block, LinkBlock):
                        yield block.to_markdown(prefix_src=self.prefix_src)
                    else:
                        yield block.get_text()
        else:
            for chunk in chunks:
                yield "".join([block.get_text() for block in chunk])

    def assemble_block_markdown(self, chunks: List[Block]):
        if self.prefix_src:
            for chunk in chunks:
                for block in chunk:
                    if isinstance(block, LinkBlock):
                        yield block.to_markdown(prefix_src=self.prefix_src)
                    else:
                        yield block.to_markdown()
        else:
            for chunk in chunks:
                yield "".join([block.to_markdown() for block in chunk])

    def get_item_with_part(self, part: str, item: str, markdown:bool=False):
        if isinstance(part, str):
            chunks = list(self._chunks_mul_for(part, item))
            if markdown:
                return self.clean_part_line("".join([text for text in self.assemble_block_markdown(chunks)]))
            else:
                return self.clean_part_line("".join([text for text in self.assemble_block_text(chunks)]))

    @staticmethod
    def clean_part_line(text:str):
        res = text.rstrip("\n")
        last_line = res.split("\n")[-1]
        if re.match(r'^\b(PART\s+[IVXLC]+)\b', last_line):
            res = res.rstrip(last_line).rstrip()
        return res

    def get_signature(self, markdown:bool=False):
        sig_index = self._chunked_data[self._chunked_data.Signature].index
        if markdown:
            res = "".join(
            [text for text in
                self.assemble_block_markdown(
                    [self.chunks[idx] for idx in sig_index]
            )])
        else:
            res = "".join(
                [text for text in
                    self.assemble_block_text(
                        [self.chunks[idx] for idx in sig_index]
                )])
        return self.clean_part_line(res)


    def get_introduction(self, markdown:bool=False):
        """
        Extract and return the introduction section of the filing document.

        The introduction is defined as all content before the first valid Part or Item.

        Returns:
            str: The extracted introduction text, or an empty string if none found.
        """
        # Find the first index where Part or Item appears
        part_indices = self._chunked_data[self._chunked_data.Part != ""].index
        item_indices = self._chunked_data[self._chunked_data.Item != ""].index

        if len(part_indices) == 0 and len(item_indices) == 0:
            return ""

        # Use the last one
        intro_index = max(
            part_indices[0] if len(part_indices) else 0,
            item_indices[0] if len(item_indices) else 0
        )

        if intro_index == 0:
            return ""

        # Reuse __getitem__ to extract chunks up to min_index
        if markdown:
            res = "".join(
            [text for text in
                self.assemble_block_markdown(
                    [self.chunks[idx] for idx in range(intro_index)]
            )])
        else:
            res = "".join(
                [text for text in
                    self.assemble_block_text(
                        [self.chunks[idx] for idx in range(intro_index)]
                )])
        return self.clean_part_line(res)

    def __len__(self):
        return len(self.chunks)

    def __getitem__(self, item, markdown:bool=False):
        if isinstance(item, int):
            chunks = [self.chunks[item]]
        elif isinstance(item, str):
            chunks = list(self.chunks_for_item(item))
        else:
            return None
        if len(chunks) == 0:
            return None
        # render the nested List of List [str]
        if markdown:
            return "".join([text for text in self.assemble_block_markdown(chunks)])
        else:
            return "".join([text for text in self.assemble_block_text(chunks)])

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


