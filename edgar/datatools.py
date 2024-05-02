import pandas as pd
from lxml import html as lxml_html

__all__ = ["compress_dataframe",
           "table_html_to_dataframe",
           "table_tag_to_dataframe",
           "markdown_to_dataframe",
           "dataframe_to_text",
           "clean_column_text"]


def clean_column_text(text: str):
    """Remove newlines and extra spaces from column text.
    ' Per     Share ' -> 'Per Share'
    'Per\nShare' -> 'Per Share'
    'Per     Share' -> 'Per Share'
    """
    text = ' '.join(text.strip().split())
    text = text.strip()
    return text


def compress_dataframe(df: pd.DataFrame):
    # Remove empty rows and columns
    df = (df.replace('', pd.NA)
          .dropna(axis=1, how="all")
          .dropna(axis=0, how="all"))
    # Fill na
    df = df.fillna('')
    return df


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
            difference_count = sum(1 for f, s in zip(first_row, second_row) if f != s)
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
