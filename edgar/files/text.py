from rich.text import Text
from edgar.richtools import repr_rich

from rich.console import Console
from rich.highlighter import RegexHighlighter
from rich.theme import Theme

__all__ = ['PlainDocument', 'XmlDocument', 'JsonDocument', 'print_xml']



class PlainDocument:

    def __init__(self, content: str):
        self.content = content

    def __repr__(self):
        return repr_rich(Text(self.content))

    def __str__(self):
        return self.content


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
    "xml.tagname": "bold orange1",   # tag names after the namespace
    "xml.attribute": "grey70",  # gray for attributes like 'contextRef'
    "xml.value": "green",       # green for attribute values and URLs
    "xml.comment": "grey58",  # gray for comments
    "xml.url": "green",         # green for URLs in xmlns
})

def print_xml(xml: str):
    console = Console(highlighter=XMLHighlighter(), theme=xml_theme)
    console.print(xml)

class XmlDocument:

    def __init__(self, content: str):
        self.content = content

    def __rich__(self):
        return Text(self.content)

    def __repr__(self):
        return repr_rich(self.__rich__(), highlighter=XMLHighlighter(), theme=xml_theme)

    def __str__(self):
        return repr(self)



class JsonDocument:

    def __init__(self, content: str):
        self.content = content

    def __repr__(self):
        return repr_rich(Text(self.content))

    def __str__(self):
        return self.content



