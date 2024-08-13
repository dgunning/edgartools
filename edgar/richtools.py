from typing import Union, Optional

import pandas as pd
import pyarrow as pa
from rich import box
from rich.table import Table
from rich.text import Text
import itertools

__all__ = [
    'repr_rich',
    'df_to_rich_table',
    'colorize_words'
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


def repr_rich(renderable) -> str:
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

    :param renderable:
    :return:
    """
    from rich.console import Console
    console = Console()
    with console.capture() as capture:
        console.print(renderable)
    str_output = capture.get()
    return str_output


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
