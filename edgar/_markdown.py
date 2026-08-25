import re

from rich import box
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from edgar.richtools import repr_rich

__all__ = [
    'convert_table',
    'MarkdownContent',
    'markdown_to_rich',
    'text_to_markdown',
]


def _empty(row):
    if not row:
        return True
    chars = set(re.sub(r"\s", "", row.strip()))
    return chars == {'|'} or chars == {'-', '|'}


def convert_table(table_markdown: str, cell_highlighter=None):
    """Convert the markdown to a rich Table.

    Args:
        table_markdown: The markdown source for the table.
        cell_highlighter: Optional callable applied to each cell's text,
            returning a rich renderable (e.g. a styled ``Text``). Used to
            highlight search matches inside table cells.
    """
    all_rows = table_markdown.replace("| |", "|\n|").split("\n")

    # Just output a simple table with no headers
    table = Table(" " * all_rows[0].count("|"), box=box.SIMPLE)
    for row in all_rows:
        if not _empty(row):
            cells = [cell.strip() for cell in row[1:-1].strip().split("|")]
            if cell_highlighter is not None:
                cells = [cell_highlighter(cell) for cell in cells]
            table.add_row(*cells)
    return table


skip_tags = ["<DOCUMENT>", "<TYPE>", "<SEQUENCE>", "<FILENAME>", "<DESCRIPTION>", "<TEXT>"]


def markdown_to_rich(md: str, title: str = "") -> Panel:
    """Convert the markdown to rich .. handling tables better than rich"""
    content = []
    buf = ""
    table_buf = ""
    is_table = False
    for line in md.split("\n"):
        if is_table:
            if not line.strip():
                table = convert_table(table_buf)
                content.append(table)
                is_table = False
                table_buf = ""
            else:
                table_buf += line + "\n"
        else:
            if "|  |" in line:
                markdown = Markdown(buf)
                buf = ""
                table_buf = line + "\n"
                content.append(markdown)
                is_table = True
            else:
                buf += line + "\n"
    if buf:
        content.append(Markdown(buf))
    return Panel(Group(*content), title=title, subtitle=title, box=box.ROUNDED)


def text_to_markdown(text: str) -> str:
    """Convert the text to markdown"""
    return f"""
    <pre>{text}</pre>
    """


class MarkdownContent:

    def __init__(self,
                 markdown: str,
                 title: str = ""):
        self.md = markdown
        self.title = title

    def view(self):
        console = Console()
        console.print(self.__rich__())

    def __rich__(self):
        _renderable = markdown_to_rich(self.md, title=self.title)
        return _renderable

    def __repr__(self):
        return repr_rich(self.__rich__())
