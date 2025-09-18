from dataclasses import dataclass
from typing import Union

import numpy as np
import pandas as pd
import pyarrow as pa
from lxml import html as lxml_html

__all__ = [
    "compress_dataframe",
    "table_html_to_dataframe",
    "table_tag_to_dataframe",
    "markdown_to_dataframe",
    "dataframe_to_text",
    "clean_column_text",
    'convert_to_numeric',
    'describe_dataframe',
    'na_value',
    'replace_all_na_with_empty',
    'convert_to_pyarrow_backend',
    'drop_duplicates_pyarrow',
    'repr_df',
    'DataPager',
    'PagingState',
]


def clean_column_text(text: str):
    """Remove newlines and extra spaces from column text.
    ' Per     Share ' -> 'Per Share'
    'Per\nShare' -> 'Per Share'
    'Per     Share' -> 'Per Share'
    """
    text = ' '.join(text.strip().split())
    text = text.strip()
    return text


def compress_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Remove empty rows and columns from a DataFrame.

    Args:
        df: DataFrame to compress

    Returns:
        Compressed DataFrame with empty rows and columns removed
    """
    # Remove empty rows and columns
    df = (df.replace('', pd.NA)
          .dropna(axis=1, how="all")
          .dropna(axis=0, how="all"))
    # Fill na
    df = df.fillna('')
    return df


def repr_df(df: pd.DataFrame, hide_index: bool = True) -> str:
    """Return a string representation of a DataFrame.

    Args:
        df: DataFrame to represent as string
        hide_index: Whether to hide the index in the output

    Returns:
        String representation of the DataFrame
    """
    if hide_index:
        return df.to_string(index=False)
    return df.to_string()


@dataclass
class PagingState:
    """State for paginating through data."""
    page: int = 1
    page_size: int = 50
    total_items: int = 0

    @property
    def start_idx(self) -> int:
        """Get the start index for the current page."""
        return (self.page - 1) * self.page_size

    @property
    def end_idx(self) -> int:
        """Get the end index for the current page."""
        return min(self.start_idx + self.page_size, self.total_items)

    @property
    def has_more(self) -> bool:
        """Check if there are more pages."""
        return self.end_idx < self.total_items


class DataPager:
    """Class for paginating through data."""
    def __init__(self, data: Union[pd.DataFrame, pa.Table], page_size: int = 50):
        """Initialize the pager.

        Args:
            data: Data to paginate through
            page_size: Number of items per page
        """
        self.data = data
        self.state = PagingState(page_size=page_size, total_items=len(data))

    def get_page(self, page: int = 1) -> Union[pd.DataFrame, pa.Table]:
        """Get a specific page of data.

        Args:
            page: Page number to get (1-based)

        Returns:
            Slice of data for the requested page
        """
        self.state.page = page
        return self.data[self.state.start_idx:self.state.end_idx]

def adjust_column_headers(df: pd.DataFrame):
    """ Replace numeric column headers with blank strings. """
    # Check if column names are integers (default index names in pandas DataFrames)
    if all(isinstance(col, int) for col in df.columns):
        # Replace them with blank strings
        df.columns = ['' for _ in df.columns]
    return df


def should_promote_to_header(df: pd.DataFrame) -> bool:
    if df.shape[0] > 1:
        first_row = df.iloc[0]

        # Check for uniformity and non-numeric nature
        if all(isinstance(item, str) for item in first_row):
            # Pattern matching for typical header keywords
            header_keywords = {'title', 'name', 'number', 'description', 'date', 'total', 'id'}
            if any(any(keyword in str(cell).lower() for keyword in header_keywords) for cell in first_row):
                return True

            # Check distinctiveness compared to the second row (simple heuristic)
            second_row = df.iloc[1]
            difference_count = sum(1 for f, s in zip(first_row, second_row, strict=False) if f != s)
            if difference_count > len(first_row) / 2:  # Arbitrary threshold: more than half are different
                return True

    return False


def table_html_to_dataframe(html_str: str) -> pd.DataFrame:
    tree = lxml_html.fromstring(html_str)
    table_element = tree.xpath("//table")[0]
    rows = table_element.xpath(".//tr")

    data = []
    for row in rows:
        cols = row.xpath(".//td | .//th")  # Handle both 'td' and 'th' if present
        cols = [clean_column_text(lxml_html.tostring(c, method='text', encoding='unicode').strip()) for c in cols]
        data.append(cols)

    df = pd.DataFrame(data)
    df = adjust_column_headers(df)  # Adjust headers if not promoted
    df = compress_dataframe(df)
    return df


def table_tag_to_dataframe(table_tag):
    """Convert a BeautifulSoup table Tag to a DataFrame."""

    rows = table_tag.find_all('tr')

    data = []

    for row in rows:
        # Find all 'td' tags within each 'tr' tag
        cols = row.find_all('td')
        # Get the text from each 'td' tag, handling nested tags automatically
        cols = [clean_column_text(col.get_text(strip=True)) for col in cols]
        data.append(cols)

    df = pd.DataFrame(data)
    return df


def markdown_to_dataframe(markdown_table):
    # Split the markdown table into rows
    rows = markdown_table.split('\n')

    # Extract the header row
    header = rows[0].split('|')
    header = [col.strip() for col in header]

    # Extract the data rows
    data_rows = []
    for row in rows[2:]:
        if not row.strip():
            continue
        data_row = row.split('|')
        data_row = [col.strip() for col in data_row]
        data_rows.append(data_row)

    # Create a pandas DataFrame
    if len(data_rows) == 0:
        df = pd.DataFrame([header], columns=["" for col in header])
    else:
        df = pd.DataFrame(data_rows, columns=header)
    df = compress_dataframe(df)
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
        headers = [f"{col:<{width}}" for col, width in zip(df.columns, column_widths, strict=False)]
        text_output += '\t'.join(headers) + '\n'

    # Loop through each row of the dataframe
    for index, row in df.iterrows():
        # Include index if specified
        if include_index:
            text_output += f"{index:<{index_width}}\t"

        # Format each value according to the column width and concatenate
        row_values = [f"{val:<{width}}" for val, width in zip(row.astype(str), column_widths, strict=False)]
        text_output += '\t'.join(row_values) + '\n'

    return text_output


def convert_to_numeric(series):
    """Convert a pandas Series to numeric if possible, otherwise return the original series."""
    try:
        return pd.to_numeric(series)
    except ValueError:
        return series


def describe_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    # Get data types of columns
    dtypes = df.dtypes

    # Create a Series for the index dtype
    index_dtype = pd.Series(df.index.dtype, index=['Index'])

    # Concatenate the dtypes and index_dtype
    all_dtypes = pd.concat([index_dtype, dtypes])

    # Get memory usage of each column including the index, in kilobytes and round to 2 decimal places
    memory_usage = df.memory_usage(deep=True) / 1024
    memory_usage.index = memory_usage.index.astype(str)  # Ensure index labels are string type
    memory_usage = memory_usage.round(2)  # Round memory usage to 2 decimal places

    # Calculate total memory usage
    total_memory_usage = memory_usage.sum()

    # Create a DataFrame with the information
    description_df = pd.DataFrame({
        'Data type': all_dtypes.to_numpy(),
        'Memory Usage (KB)': memory_usage.to_numpy()
    }, index=all_dtypes.index)

    # Append the total memory usage as the last row
    total_row = pd.DataFrame({
        'Data type': [''],
        'Memory Usage (KB)': [total_memory_usage]
    }, index=['Total'])

    description_df = pd.concat([description_df, total_row])

    return description_df


def convert_to_pyarrow_backend(data:pd.DataFrame):
    # Convert dtypes carefully
    for col in data.columns:
        if data[col].dtype == 'object':
            # For object columns, convert to string
            data[col] = data[col].astype(str)
        elif data[col].dtype == 'float64':
            # For float columns, use float32 to match PyArrow's default
            data[col] = data[col].astype('float32')

    # Now convert to PyArrow
    return data.convert_dtypes(dtype_backend="pyarrow")


def replace_all_na_with_empty(df_or_series):
    if isinstance(df_or_series, pd.DataFrame):
        for column in df_or_series.columns:
            # Check if the column is all NA or None
            if df_or_series[column].isna().all():
                # Get the length of the DataFrame
                length = len(df_or_series)

                # Create a new Series of empty strings
                empty_series = pd.Series([''] * length, name=column)

                # Replace the column with the new Series
                df_or_series[column] = empty_series

        return df_or_series
    elif isinstance(df_or_series, pd.Series):
        # Check if the series is all NA or None
        if df_or_series.isna().all():
            # Create a new Series of empty strings with the same index and name
            return pd.Series('', index=df_or_series.index, name=df_or_series.name)
        else:
            # If not all NA, return the original series
            return df_or_series

def na_value(value, default_value:object=''):
    if pd.isna(value):
        return default_value
    return value


def drop_duplicates_pyarrow(table, column_name, keep='first'):
    """
    Drop duplicates from a PyArrow Table based on a specified column.

    Parameters:
    - table (pa.Table): The input PyArrow Table
    - column_name (str): The column to check for duplicates
    - keep (str): 'first' to keep first occurrence, 'last' to keep last occurrence

    Returns:
    - pa.Table: A new table with duplicates removed
    """
    if column_name not in table.column_names:
        raise ValueError(f"Column '{column_name}' not found in table")

    if keep not in ['first', 'last']:
        raise ValueError("Parameter 'keep' must be 'first' or 'last'")

    # Extract the column as an array
    column_array = table[column_name]

    # Convert to NumPy array and get unique indices
    np_array = column_array.to_numpy()
    unique_values, unique_indices = np.unique(np_array, return_index=True)

    if keep == 'first':
        # Sort indices to maintain original order for first occurrences
        sorted_indices = np.sort(unique_indices)
    else:  # keep == 'last'
        # Get the last occurrence by reversing the array logic
        reverse_indices = len(np_array) - 1 - np.unique(np_array[::-1], return_index=True)[1]
        sorted_indices = np.sort(reverse_indices)

    # Create a boolean mask to filter the table
    mask = np.zeros(len(table), dtype=bool)
    mask[sorted_indices] = True

    # Filter the table using the mask
    deduplicated_table = table.filter(pa.array(mask))

    return deduplicated_table
