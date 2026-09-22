from pathlib import Path

from rich import print
from rich.panel import Panel

from edgar import Filing
from edgar._markdown import MarkdownContent, convert_table, markdown_to_rich
from edgar.datatools import markdown_to_dataframe
from edgar.documents import parse_html


def test_convert_markdown_table():
    markdown_str = "|  |  |  |  |  | | --- | --- | --- | --- | --- | | Title of each class |   | Trading Symbol(s) |   | Name of each exchange on which registered | | Common Shares |   | EFSH |   | NYSE American LLC |"
    table = convert_table(markdown_str)
    print()
    print(table)

    markdown_str = "|  | | --- | | (212) 417-9800 | | (Registrant's telephone number, including area code) |"
    print(convert_table(markdown_str))

    markdown_str = (
        "|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | |  |  |  | ALCON INC. | |  |  |  |  |  | | Date:"
        "| February 13, 2023 |  | By: | /s/ David J. Endicott | |  |  |  | Name: David J. Endicott | |  |  |  | Title: Authorized Representative | |  |  |  |  |  | |  |  |  |  |  | |  |  |  |  |  | | Date: | February 13, 2023 |  | By: | /s/"
        "Timothy C. Stonesifer | |  |  |  | Name: Timothy C. Stonesifer | |  |  |  | Title: Authorized Representative | |  |  |  |  |  |")
    print(convert_table(markdown_str))


def test_convert_empty_table():
    markdown_str = "|  |  |  | | --- | --- | --- | |  |  |  | |  |"
    print(convert_table(markdown_str))


def test_markdown_to_rich_for_plain_text():
    md = """
    <pre>This is a test of the markdown to rich conversion</pre>
    """
    print()
    renderable = markdown_to_rich(md)
    assert isinstance(renderable, Panel)
    print(renderable)


def test_markdown_content_renders_a_real_6k():
    """MarkdownContent wraps markdown for rich display; it must survive a real filing.

    Built through ``edgar.documents`` rather than the old
    ``MarkdownContent.from_html``, which was removed along with
    ``html_to_markdown``: its last production caller went in #1132 when
    ``PressRelease.to_markdown()`` moved off the legacy stack. This is how the
    remaining callers construct it.
    """
    html = Path('data/form.6k.Athena.html').read_text()
    markdown_content = MarkdownContent(parse_html(html).to_markdown(), title="6-K")

    text = repr(markdown_content)
    assert text
    assert markdown_content.title == "6-K"


def test_markdown_content_renders_a_6k_with_no_tables():
    """The table-splitting branch of markdown_to_rich must handle prose-only input."""
    html = Path('data/form6k.RoyalPhilips.html').read_text()
    markdown_content = MarkdownContent(parse_html(html).to_markdown())

    assert repr(markdown_content)


def test_markdown_to_dataframe():
    "Create a markdown table so we can test converting to a dataframe"
    markdown_table = """
    | Title of each class | Trading Symbol(s) | Exchange | 
    | --- | --- | --- | 
    | Common Shares       | EFSH              | NYSE American LLC |
    """.strip()
    df = markdown_to_dataframe(markdown_table)
    assert df.shape == (1, 3)


def test_dataframe_from_markdown_is_compressed():
    markdown_table = """
    | Name |     |City     | Exchange | 
    | ---- | --- | ------- | -------- | 
    | Mike |     |Boston   | X        | 
    |      |     |         |         | 
    | Kyra |     |New York | X        | 
    """.strip()
    df = markdown_to_dataframe(markdown_table)
    assert df.shape == (2, 3)


def test_dataframe_from_markdown_for_header_only_table():
    markdown_table = """
    | Name |     |City     | Exchange | 
    | ---- | --- | ------- | -------- | 
    """.strip()
    df = markdown_to_dataframe(markdown_table)
    assert df.shape == (1, 3)

def test_markdown_to_dataframe_for_header_only_table():
    md = """
    | SVB Leerink | Cantor |
    |-------------|--------|
    """.strip()
    df = markdown_to_dataframe(md)
    assert df.shape == (1, 2)

def test_markdown_text_has_correct_spaces():

    filing = Filing(company='Paramount Global', cik=813828, form='8-K', filing_date='2024-04-29',
                    accession_no='0000813828-24-000018')

    md = filing.markdown()
    print(md)


def test_obscure_filing_to_markdown():
    filing = Filing(form='TA-1/A', filing_date='2024-03-13', company='DB SERVICES AMERICAS INC /TA', cik=1018490, accession_no='0001018490-24-000008')
    md = filing.markdown()
    assert not md

def test_markdown_module_does_not_depend_on_legacy_edgar_files():
    """``edgar._markdown`` must stay off the legacy ``edgar.files`` stack.

    ``html_to_markdown`` used to call ``HtmlDocument.from_html`` from
    ``edgar.files.html_documents``, which made every rich markdown view --
    notably ``PressRelease.to_markdown()`` -- a live consumer of the parser
    that edgartools 6.0 removes (bead edgartools-07lk.3). It renders through
    ``edgar.documents`` now. This is a static check on the source rather than
    a runtime one, because ``edgar/__init__.py`` imports ``edgar.files``
    regardless, so the module object alone cannot tell us who asked for it.
    """
    import ast
    import pathlib

    import edgar._markdown

    tree = ast.parse(pathlib.Path(edgar._markdown.__file__).read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)

    legacy = {m for m in imported if m == "edgar.files" or m.startswith("edgar.files.")}
    assert not legacy, f"edgar._markdown re-acquired a legacy edgar.files dependency: {sorted(legacy)}"
