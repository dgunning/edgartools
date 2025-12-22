import re

from rich import box
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from edgar.files.html_documents import HtmlDocument
from edgar.richtools import repr_rich

__all__ = [
    'convert_table',
    'MarkdownContent',
    'markdown_to_rich',
    'html_to_markdown',
    "fix_markdown",
    "text_to_markdown",
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


def fix_markdown(md: str):
    # Clean up issues with not spaces between sentences like "Condition.On"
    md = re.sub(r"([a-z]\.)([A-Z])", r"\1 \2", md)

    # Remove asterisks inside Items
    md = re.sub(r"\*\*(Item)\*\*\xa0\*\*(\d)", r"\1 \2", md, flags=re.IGNORECASE)

    # And fix split Item numbers e.g. "Item\n5.02"
    md = re.sub(r"(Item)[\n\xa0]\s?(\d)", r"\1 \2", md, flags=re.IGNORECASE)

    # Fix items not on newlines e.g. ". Item 5.02"
    md = re.sub(r"\. (Item)\s?(\d.\d{,2})", r".\n \1 \2", md, flags=re.IGNORECASE)

    # Fix items with no space before Item e.g. "ReservedItem 7"
    md = re.sub(r"(\S)(Item)\s?(\d.\d{,2})", r"\1\n\n \2 \3", md, flags=re.IGNORECASE)
    return md


def html_to_markdown(html: str) -> str:
    """Convert the html to markdown"""
    document: HtmlDocument = HtmlDocument.from_html(html)
    return document.markdown


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

    @classmethod
    def from_html(cls, html: str, title: str = ""):
        md = html_to_markdown(html)
        return cls(markdown=md, title=title)

    def view(self):
        console = Console()
        console.print(self.__rich__())

    def __rich__(self):
        _renderable = markdown_to_rich(self.md, title=self.title)
        return _renderable

    def __repr__(self):
        return repr_rich(self.__rich__())
