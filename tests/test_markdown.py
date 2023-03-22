from pathlib import Path

from rich import print

from edgar._markdown import convert_table, MarkdownContent, fix_markdown


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


def test_fix_markdown():
    # Fix no space between consecutive sentences
    md = """
    A copy of this press release is hereby incorporated as Exhibit 99.1  │
    Condition.On Match 23, 2023
    """
    assert "Condition.On" in md
    assert "Condition. On" in fix_markdown(md)

    md = """
    Item\n5.02 A copy of this press release is hereby incorporated as Exhibit 99.1  │
    Condition.On Match 23, 2023
    """
    assert "Item\n5.02" in md
    assert "Item 5.02" in fix_markdown(md)

    # Fix no newline between items
    md = """
    A copy of this press release is hereby incorporated as Exhibit 99.1  │
    │ hereto. Item 9.01. Financial Statements and Exhibits. (d) Exhibits Exhibit 99.1 - Press Release issued March 16,
    │ 2023Exhibit 104 – Cover Page Interactive Data File (embedded within Inline XBRL document)
    """
    assert ". Item 9.01" in md
    md_fixed = fix_markdown(md)
    assert ".\n Item 9.01" in md_fixed
