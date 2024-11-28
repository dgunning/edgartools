from rich.console import Console
from rich.theme import Theme
from edgar.files.text import XMLHighlighter, XmlDocument
from rich import print

def test_highlight_xml():
    theme = Theme({
        "xml.tag": "bold cyan",
        "xml.attribute": "yellow",
        "xml.value": "green",
        "xml.comment": "dim italic",
        "xml.cdata": "bold red",
        "xml.processing": "bold magenta",
    })
    # Create console with highlighter and theme
    console = Console(highlighter=XMLHighlighter(), theme=theme)

    # Example usage
    xml_example = """<?xml version="1.0" encoding="UTF-8"?>
    <!-- This is a comment -->
    <root>
        <person id="123" type="employee">
            <name>John Doe</name>
            <age>30</age>
            <![CDATA[Some <raw> text]]>
        </person>
    </root>"""

    console.print(xml_example)

def test_xml_document():
    xml_example = """<?xml version="1.0" encoding="UTF-8"?>
        <!-- This is a comment -->
        <root>
            <person id="123" type="employee">
                <name>John Doe</name>
                <age>30</age>
                <![CDATA[Some <raw> text]]>
            </person>
        </root>"""
    doc = XmlDocument(xml_example)
    doc_repr = repr(doc)
    print(doc_repr)