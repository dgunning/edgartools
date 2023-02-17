import re

from markdownify import markdownify
from rich import box
from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from edgar._rich import repr_rich

__all__ = [
    'convert_table',
    'MarkdownContent'
]


def _empty(row):
    if not row:
        return True
    chars = set(re.sub(r"\s", "", row.strip()))
    return chars == {'|'} or chars == {'-', '|'}


def convert_table(table_markdown: str):
    """Convert the markdown to a rich Table"""
    all_rows = table_markdown.replace("| |", "|\n|").split("\n")

    # Just output a simple table with no headers
    table = Table(" " * all_rows[0].count("|"), box=box.SIMPLE)
    for row in all_rows:
        if not _empty(row):
            row = [cell.strip() for cell in row[1:-1].strip().split("|")]
            table.add_row(*row)
    return table


skip_tags = ["<DOCUMENT>", "<TYPE>", "<SEQUENCE>", "<FILENAME>", "<DESCRIPTION>", "<TEXT>"]


class MarkdownContent:

    def __init__(self,
                 html: str,
                 title: str = ""):
        if "<DOCUMENT>" in html[:500]:
            html = "\n".join(line for line in html.split("\n")
                             if not any(line.startswith(tag) for tag in skip_tags))

        self.md = re.sub(r'(\n\s*)+\n', '\n\n', markdownify(html))
        self.title = title

    def __rich__(self):
        content = []
        buf = ""
        table_buf = ""
        is_table = False
        for line in self.md.split("\n"):
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
        return Panel(Group(*content), title=self.title, subtitle=self.title, box=box.ROUNDED)

    def __repr__(self):
        return repr_rich(self.__rich__())
