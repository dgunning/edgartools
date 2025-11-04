import itertools
import re
from io import StringIO
from typing import Optional, Union

import pandas as pd
import pyarrow as pa
from rich import box
from rich.console import Console
from rich.highlighter import RegexHighlighter
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

__all__ = [
    'repr_rich',
    'rich_to_text',
    'strip_ansi_text',
    'df_to_rich_table',
    'colorize_words',
    'print_xml',
    'print_rich',
    'Docs'
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

    for _index, value_list in enumerate(data_for_display.to_numpy().tolist()):
        # row = [str(index)] if show_index else []
        row = [str(x) for x in value_list]
        rich_table.add_row(*row)

    return rich_table


def strip_ansi_text(text: str) -> str:
    """
    Remove ANSI escape sequences from text

    :param text: Text containing ANSI escape sequences
    :return: Clean text without ANSI formatting
    """
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def repr_rich(renderable, strip_ansi:bool=False, **console_args) -> str:
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
    :param strip_ansi: Whether to strip ANSI escape sequences from the output
    :param console_args: The console arguments
    :return: A string representation of the renderable object
    """
    from rich.console import Console
    console = Console(**console_args)
    with console.capture() as capture:
        console.print(renderable)
    str_output = capture.get()
    if strip_ansi:
        str_output = strip_ansi_text(str_output)
    return str_output


def rich_to_text(rich_object, width:int=None) -> str:
    """
    Convert a Rich renderable object to plain text while preserving layout.

    Args:
        rich_object: Any Rich renderable object (Panel, Table, Tree, etc.)
        width: The width of the output in characters (default: None)

    Returns:
        str: Plain text representation with layout preserved
    """
    if width:
        text = repr_rich(rich_object, force_terminal=False, width=width)
    else:
        text = repr_rich(rich_object, force_terminal=False)
    text = strip_ansi_text(text)
    return text


def rich_to_svg(rich_object, width: int = 120) -> str:
    """
    Convert a Rich renderable object to SVG format while preserving layout and styling.

    This function uses Rich's built-in SVG export capabilities to convert any Rich
    renderable (Panel, Table, Tree, etc.) to an SVG string representation.

    Args:
        rich_object: Any Rich renderable object (Panel, Table, Tree, etc.)
        width: The width of the output in characters (default: 120)

    Returns:
        str: SVG representation of the Rich object with preserved layout and styling

    Example:
        >>> from rich.table import Table
        >>> table = Table(title="Example")
        >>> table.add_column("Name")
        >>> table.add_row("Alice")
        >>> svg_output = rich_to_svg(table)
    """
    from rich.console import Console

    # Create a console specifically for SVG export
    console = Console(
        file=StringIO(),
        force_terminal=True,  # Ensure styling is applied
        record=True,  # Enable recording for SVG export
        width=width,  # Set desired width
        color_system="standard"  # Use standard colors for better SVG compatibility
    )

    # Record the rich object rendering
    console.print(rich_object)

    # Export to SVG with default styling
    svg_output = console.export_svg()

    return svg_output


def rich_to_png(rich_object, width: int = 120, output_path: str = None) -> Optional[bytes]:
    """
    Convert a Rich renderable object to PNG format.

    This function first converts the Rich object to SVG using rich_to_svg,
    then converts that SVG to PNG using CairoSVG.

    Args:
        rich_object: Any Rich renderable object (Panel, Table, Tree, etc.)
        width: The width of the output in characters (default: 120)
        output_path: Optional path to save the PNG file. If not provided,
                    returns the PNG as bytes.

    Returns:
        bytes: PNG image data if output_path is None,
              None if output_path is provided (file is saved instead)

    Example:
        >>> from rich.table import Table
        >>> table = Table(title="Example")
        >>> table.add_column("Name")
        >>> table.add_row("Alice")
        >>> png_data = rich_to_png(table)
        >>> # Or save to file:
        >>> rich_to_png(table, output_path="output.png")
    """
    try:
        import cairosvg
    except ImportError:
        raise ImportError(
            "CairoSVG is required for PNG conversion. "
            "Install it with: pip install cairosvg"
        ) from None

    # First get the SVG output
    svg_content = rich_to_svg(rich_object, width=width)

    # Convert SVG to PNG
    if output_path:
        cairosvg.svg2png(
            bytestring=svg_content.encode('utf-8'),
            write_to=output_path
        )
        return None
    else:
        png_data = cairosvg.svg2png(bytestring=svg_content.encode('utf-8'))
        return png_data



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


class Docs:
    """
    A class that will show documentation for any class in edgartools

    Usage
    ```python
        filing = filings[0]

        filing.docs # Will create a Docs instance from the __docs__ attribute
    ```
    """

    def __init__(self, obj, docs_content: str = None):
        """
        Initialize the Docs class with an object and optional documentation content.

        Args:
            obj: The object to document
            docs_content: Optional documentation content string. If not provided,
                         will try to find markdown file, then __doc__
        """
        self.obj = obj
        self.docs_content = docs_content

        # If no docs_content provided, try to get from various sources in order of preference
        if not self.docs_content:
            # 1. Try to find markdown file with class name
            markdown_content = self._find_markdown_docs()
            if markdown_content:
                self.docs_content = markdown_content
            # 2. Fall back to __doc__ attribute
            elif hasattr(obj, '__doc__') and obj.__doc__:
                self.docs_content = obj.__doc__
            else:
                self.docs_content = f"No documentation available for {type(obj).__name__}"

    def _find_markdown_docs(self) -> Optional[str]:
        """
        Look for a markdown file with the same name as the class in a docs directory
        in the same package as the class.

        Returns:
            Optional[str]: The content of the markdown file if found, None otherwise
        """
        import inspect
        import os

        # Get the class name
        class_name = getattr(self.obj, '__name__', None) or type(self.obj).__name__

        # Get the module where the object is defined
        try:
            if hasattr(self.obj, '__module__'):
                module = inspect.getmodule(self.obj)
            else:
                module = inspect.getmodule(type(self.obj))

            if not module or not hasattr(module, '__file__') or not module.__file__:
                return None

            # Get the directory containing the module
            module_dir = os.path.dirname(os.path.abspath(module.__file__))

            # Look for docs directory in the same package
            docs_dir = os.path.join(module_dir, 'docs')

            if not os.path.exists(docs_dir):
                return None

            # Look for markdown file with class name
            markdown_file = os.path.join(docs_dir, f"{class_name}.md")

            if os.path.exists(markdown_file):
                try:
                    with open(markdown_file, 'r', encoding='utf-8') as f:
                        return f.read()
                except (IOError, OSError):
                    return None

        except Exception:
            # If anything goes wrong, silently return None
            return None

        return None

    def __rich__(self):
        """
        Return a Rich renderable representation of the documentation.
        """
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.text import Text

        # Get the object name for the title
        obj_name = getattr(self.obj, '__name__', None) or type(self.obj).__name__

        # Create the title
        title = Text.assemble((obj_name, "bold white"))

        # Try to render as markdown if it looks like markdown, otherwise as plain text
        if self.docs_content and ('```' in self.docs_content or '#' in self.docs_content or '*' in self.docs_content):
            content = Markdown(self.docs_content)
        else:
            content = Text(self.docs_content or "No documentation available")

        # Create a panel with the documentation
        return Panel(
            content,
            title=title,
            border_style="blue",
            padding=(1, 2),
            expand=False
        )

    def __repr__(self):
        """
        Return a string representation of the Docs object.
        """
        return repr_rich(self.__rich__())

    def _split_into_sections(self):
        """
        Split markdown content into sections by ## headings.

        Returns:
            List[str]: List of document sections, each starting with a ## heading
        """
        if not self.docs_content:
            return []

        lines = self.docs_content.split('\n')
        sections = []
        current_section = []

        for line in lines:
            # Check if this is a ## heading (but not # or ### or ####)
            if line.startswith('## ') and not line.startswith('### '):
                # Save previous section if it exists
                if current_section:
                    sections.append('\n'.join(current_section))
                # Start new section with this heading
                current_section = [line]
            else:
                # Add line to current section
                current_section.append(line)

        # Don't forget the last section
        if current_section:
            sections.append('\n'.join(current_section))

        return sections

    def search(self, query: str, use_bm25: bool = True):
        """
        Search documentation content for relevant sections.

        Uses BM25 semantic search by default to find sections matching the query.
        Splits documentation by ## headings and returns matching sections with scores.

        Args:
            query: Search query (e.g., "extract revenue", "query by period")
            use_bm25: Use semantic BM25 search (True) or regex pattern matching (False)

        Returns:
            SearchResults: Matching documentation sections with scores

        Example:
            >>> filing.docs.search("get attachments")
            # Returns sections about accessing filing attachments

            >>> xbrl.docs.search("extract revenue")
            # Returns sections about extracting revenue from statements

            >>> xbrl.docs.search(r"\.to_dataframe\(\)", use_bm25=False)
            # Regex search for exact pattern
        """
        from edgar.search.textsearch import BM25Search, RegexSearch

        # Split content into searchable sections
        sections = self._split_into_sections()

        if not sections:
            # Return empty results if no content
            from edgar.search.textsearch import SearchResults
            return SearchResults(query=query, sections=[], tables=False)

        # Use appropriate search method
        if use_bm25:
            searcher = BM25Search(sections)
        else:
            searcher = RegexSearch(sections)

        return searcher.search(query, tables=False)
