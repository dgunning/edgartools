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
    assert "NORA" in repr(markdown_content)


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
    assert ".\n Item 9.01" in md_fixed

    # Fix no spaces before Item
    md = """
        Repurchases under the September 2021 program may be made in open-market or 
    privately negotiated transactions.Item 6. ReservedItem 7. Management's 
    Discussion and Analysis of Financial Condition and Results of 
    """
    md_fixed = fix_markdown(md)
    assert " Item 7" in md_fixed


def test_that_markdown_has_proper_line_breaks():
    from edgar import Filing
    from markdownify import markdownify
    import re
    filing = Filing(form='10-K', filing_date='2023-09-21', company='CAMPBELL SOUP CO', cik=16732,
           accession_no='0000016732-23-000109')
    print()
    print(filing.markdown())
    #print(markdownify(filing.html()))
    md = """
    Repurchases under the September 2021 program may be made in open-market or 
privately negotiated transactions.Item 6. ReservedItem 7. Management's 
Discussion and Analysis of Financial Condition and Results of 
"""
    #md = re.sub(r"(\S)(Item)\s?(\d.\d{,2})", r"\1\n \2 \3", md)
    #print(md)