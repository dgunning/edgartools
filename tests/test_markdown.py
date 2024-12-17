from pathlib import Path
from edgar import Filing, Document
from rich import print
from rich.panel import Panel

from edgar._markdown import convert_table, MarkdownContent, fix_markdown, markdown_to_rich
from edgar.datatools import markdown_to_dataframe


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


def test_markdown_to_html():
    html = Path('data/form.6k.Athena.html').read_text()
    markdown_content = MarkdownContent.from_html(html)
    print()
    text = repr(markdown_content)
    print(text)
    assert text


def test_markdown_content_html_with_no_tables():
    html = Path('data/form6k.RoyalPhilips.html').read_text()
    markdown_content = MarkdownContent.from_html(html)
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

    md = "ITEM\n1 - BUSINESS"
    assert "ITEM 1 - BUSINESS" in fix_markdown(md)

    # Cleanup Item\xa01
    md = fix_markdown("Item\xa01")
    assert "Item 1" in md

    # Cleanup double asterisks
    print(fix_markdown('**ITEM**\xa0**1'))
    import re
    print(re.sub(r'\*', '', '**ITEM**\xa0**1'))
    assert "ITEM 1" in fix_markdown('**ITEM**\xa0**1')

    # Fix no newline between items
    md = """
    A copy of this press release is hereby incorporated as Exhibit 99.1  │
    │ hereto. Item 9.01. Financial Statements and Exhibits. (d) Exhibits Exhibit 99.1 - Press Release issued March 16,
    │ 2023Exhibit 104 – Cover Page Interactive Data File (embedded within Inline XBRL document)
    """
    assert ". Item 9.01" in md
    md_fixed = fix_markdown(md)
    assert any(line.startswith(" Item 9.01") for line in md_fixed.splitlines())

    # Fix no spaces before Item
    md = """
        Repurchases under the September 2021 program may be made in open-market or 
    privately negotiated transactions.Item 6. ReservedItem 7. Management's 
    Discussion and Analysis of Financial Condition and Results of 
    """
    md_fixed = fix_markdown(md)
    assert any(line.startswith(" Item 7") for line in md_fixed.splitlines())


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
    html = filing.html()
    md = filing.markdown()
    assert not md