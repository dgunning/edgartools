from pathlib import Path

from rich import print

from edgar._markdown import convert_table, MarkdownContent


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


def test_form4_to_markdown():
    html = Path('data/form4.Evans.html').read_text()
    markdown_content = MarkdownContent(html)
    print()
    print(markdown_content)
    assert markdown_content
    assert "SULLIVAN NORA" in repr(markdown_content)


def test_markdown_to_html():
    html = Path('data/form.6k.Athena.html').read_text()
    markdown_content = MarkdownContent(html)
    print()
    text = repr(markdown_content)
    print(text)
    assert text


def test_markdown_content_html_with_no_tables():
    html = Path('data/form6k.RoyalPhilips.html').read_text()
    markdown_content = MarkdownContent(html)
    print()
    text = repr(markdown_content)
    assert text
