from typing import Union, Optional

import pandas as pd
import pyarrow as pa
from rich import box
from rich.table import Table
from rich.text import Text
from rich.console import Console
from io import StringIO
import itertools
from rich.highlighter import RegexHighlighter
from rich.theme import Theme

__all__ = [
    'repr_rich',
    'rich_to_text',
    'df_to_rich_table',
    'colorize_words',
    'print_xml',
    'print_rich'
]

table_styles = {
    'form': 'dark_sea_green4',
    'filingDate': 'deep_sky_blue1',
    'filing_date': 'deep_sky_blue1',
    'filed': 'deep_sky_blue1',
    'Shares': 'deep_sky_blue1',
    'Reporting Owner': 'deep_sky_blue1',
    'issuer': 'deep_sky_blue1',
    'fact': 'deep_sky_blue1',
    'industry': 'deep_sky_blue1',
    'document': 'deep_sky_blue1'
}


def df_to_rich_table(
        df: Union[pd.DataFrame, pa.Table],
        index_name: Optional[str] = None,
        title: str = "",
        title_style: str = "",
        max_rows: int = 20,
        table_box:box.Box = box.SIMPLE) -> Table:
    """
    Convert a dataframe to a rich table


    :param index_name: The name of the index
    :param df: The dataframe to convert to a rich Table
    :param max_rows: The maximum number of rows in the rich Table
    :param title: The title of the Table
    :param title_style: The title of the Table
    :param table_box: The rich box style e.g. box.SIMPLE
    :return: a rich Table
    """
    if isinstance(df, pa.Table):
        # For speed, learn to sample the head and tail of the pyarrow table
        df = df.to_pandas()

    rich_table = Table(box=table_box, row_styles=["bold", ""], title=title, title_style=title_style or "bold")
    index_name = str(index_name) if index_name else ""
    index_style = table_styles.get(index_name)
    rich_table.add_column(index_name, style=index_style, header_style=index_style)

    for column in df.columns:
        style_name = table_styles.get(column)
        rich_table.add_column(column, style=style_name, header_style=style_name)

    if len(df) > max_rows:
        head = df.head(max_rows // 2)
        tail = df.tail(max_rows // 2)
        data_for_display = pd.concat([head,
                                      pd.DataFrame([{col: '...' for col in df.columns}], index=['...']),
                                      tail])
    else:
        data_for_display = df

    data_for_display = data_for_display.reset_index()

    for index, value_list in enumerate(data_for_display.values.tolist()):
        # row = [str(index)] if show_index else []
        row = [str(x) for x in value_list]
        rich_table.add_row(*row)

    return rich_table


def repr_rich(renderable, **console_args) -> str:
    """
    This renders a rich object to a string

    It implements one of the methods of capturing output listed here

    https://rich.readthedocs.io/en/stable/console.html#capturing-output

     This is the recommended method if you are testing console output in unit tests

        from io import StringIO
        from rich.console import Console
        console = Console(file=StringIO())
        console.print("[bold red]Hello[/] World")
        str_output = console.file.getvalue()

    :param renderable: A rich renderable object
    :param console_args: The console arguments
    :return: A string representation of the renderable object
    """
    from rich.console import Console
    console = Console(**console_args)
    with console.capture() as capture:
        console.print(renderable)
    str_output = capture.get()
    return str_output


def rich_to_text(rich_object, width=120) -> str:
    """
    Convert a Rich renderable object to plain text while preserving layout.

    Args:
        rich_object: Any Rich renderable object (Panel, Table, Tree, etc.)

    Returns:
        str: Plain text representation with layout preserved
    """
    # Create a string buffer to capture the output
    string_buffer = StringIO()

    # Create a Console that will write to our string buffer instead of stdout
    # force_terminal=False ensures we get plain text output
    # no_color=True removes all color codes
    console = Console(
        file=string_buffer,
        force_terminal=False,
        no_color=True,
        width=width  # Set desired width - adjust as needed
    )

    # Render the rich object to our console
    console.print(rich_object)

    # Get the resulting string and strip any trailing whitespace
    result = string_buffer.getvalue().rstrip()

    # Clean up
    string_buffer.close()

    return result

def colorize_words(words, colors=None) -> Text:
    """ Colorize a list of words with a list of colors"
    """
    colors = colors or ["deep_sky_blue3", "red3", "dark_sea_green4"]
    colored_words = []
    color_cycle = itertools.cycle(colors)

    for word in words:
        color = next(color_cycle)
        colored_words.append((word, color))

    return Text.assemble(*colored_words)


class XMLHighlighter(RegexHighlighter):
    """Apply style to XML syntax elements."""

    base_style = "xml."
    highlights = [
        # XML tags with namespaces
        r'(?P<namespace>[a-zA-Z0-9_-]+)(?=:)',  # matches the namespace prefix
        r'(?P<colon>:)',  # matches the colon separator
        r'(?P<tagname>[a-zA-Z0-9_-]+)(?:\s|>|/>)',  # matches the tag name after namespace
        # Attribute names and values
        r'(?P<attribute>\s[a-zA-Z0-9_-]+)(?==)',
        r'(?P<value>"[^"]*")',
        # Comments
        r'(?P<comment><!--[\s\S]*?-->)',
        # URLs in xmlns attributes
        r'(?P<url>http://[^\s<>"]+)',
    ]

# Define theme colors for different XML elements
xml_theme = Theme({
    "xml.namespace": "magenta",  # pink/magenta for namespaces like 'us-gaap'
    "xml.colon": "magenta",     # keeping the colon the same color as namespace
    "xml.tagname": "light_goldenrod3",   # tag names after the namespace
    "xml.attribute": "grey70",  # gray for attributes like 'contextRef'
    "xml.value": "green",       # green for attribute values and URLs
    "xml.comment": "grey58",  # gray for comments
    "xml.url": "green",         # green for URLs in xmlns
})

def print_xml(xml: str):
    console = Console(highlighter=XMLHighlighter(), theme=xml_theme)
    console.print(xml)

def print_rich(rich_object, **args):
    console = Console(**args)
    console.print(rich_object)