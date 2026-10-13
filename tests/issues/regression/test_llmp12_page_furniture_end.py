"""
Regression test for edgartools-llmp.12 (phase B): a section ends on page
furniture instead of its last block of content.

The mirror of ``test_llmp12_page_furniture_start``. A section ends at the next
TOC anchor or at a Part divider, and the filer's page furniture sits between
the last block of content and that end: the backlink to the contents (a 2010
10-K's "Index to Financial Statements", AmEx, Chevron), the page number and the
running header of the page that follows (Microsoft's "31 PART I Item 2, 3, 4",
Hertz's company-name header, JPMorgan's "41 Parts III and IV"), or a page
footer (Apple's "Apple Inc. | 2024 Form 10-K | 18", Bank of America's "23 Bank
of America", Goldman's "126 Goldman Sachs 2024 Form 10-K" laid out as a table).
Measured over the truth set, trailing furniture was the largest end failure
left once the Part dividers were bound.

The TOC extractor now retreats ``end_element`` to the first block of the
furniture run that trails the section, using the same furniture rules as the
start pass, with two guards learned from the corpus: a date line ("February
20, 2025") closes an auditor's report and is never furniture although it
repeats through the filing, and a table is one unit, furniture only when every
cell is, so a numeric table is never cut and a footer table is dropped whole.
"""

import re

from edgar.documents import HTMLParser, ParserConfig
from tests.paths import FIXTURES_DIR

ITEMS = [
    ("1", "Business"), ("1A", "Risk Factors"), ("2", "Properties"),
    ("3", "Legal Proceedings"), ("4", "Mine Safety Disclosures"),
    ("5", "Market for Registrant's Common Equity"), ("7", "Management's Discussion and Analysis"),
    ("8", "Financial Statements and Supplementary Data"), ("9A", "Controls and Procedures"),
    ("10", "Directors, Executive Officers and Corporate Governance"),
    ("15", "Exhibits and Financial Statement Schedules"),
]
PARTS = {"5": "II", "10": "III", "15": "IV"}


def _ten_k(furniture, tail="") -> str:
    """A 10-K whose items end in ``furniture(page)`` blocks before the next anchor."""
    toc = "".join(
        f'<tr><td><a href="#item{n.lower()}">Item {n}.</a></td>'
        f'<td><a href="#item{n.lower()}">{t}</a></td><td>{i + 3}</td></tr>'
        for i, (n, t) in enumerate(ITEMS)
    )
    body = []
    for i, (n, t) in enumerate(ITEMS):
        if n in PARTS:
            body.append(f"<p><b>PART {PARTS[n]}</b></p>")
        body.append(f'<div id="item{n.lower()}"></div>')
        body.append(f"<p><b>Item {n}. {t}</b></p>")
        body.append(f"<p>Body of item {n}, sentence one.</p>")
        body.append(f"<p>Body of item {n}, sentence two.</p>")
        body.append(tail)
        body.append(furniture(i + 3))
    return (
        "<html><body><p><b>FORM 10-K</b></p><p><b>TABLE OF CONTENTS</b></p>"
        f"<table>{toc}</table><p><b>PART I</b></p>{''.join(body)}"
        "<p><b>SIGNATURES</b></p><p>Signed.</p></body></html>"
    )


def _parse(html: str, form: str = "10-K"):
    return HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(html)


def _ends_on_content(doc, key, item):
    text = doc.sections[key].text().rstrip()
    assert text.endswith(f"Body of item {item}, sentence two."), f"{key} ends on {text[-80:]!r}"
    md = doc.sections[key].markdown()
    assert "Table of Contents" not in md and "ACME" not in md, md[-200:]


def test_backlink_page_number_and_running_header_are_dropped():
    doc = _parse(_ten_k(lambda page: (
        f"<p>{page}</p>"
        '<p><a href="#toc">Table of Contents</a></p>'
        "<p>ACME HOLDINGS, INC. AND SUBSIDIARIES</p>"
    )))
    _ends_on_content(doc, "part_i_item_1a", "1A")
    _ends_on_content(doc, "part_i_item_4", "4")       # before the PART II divider
    _ends_on_content(doc, "part_ii_item_7", "7")
    _ends_on_content(doc, "part_iii_item_10", "10")


def test_a_footer_table_is_dropped_whole():
    doc = _parse(_ten_k(lambda page: (
        f"<table><tr><td>{page}</td><td>ACME HOLDINGS, INC. AND SUBSIDIARIES</td></tr></table>"
    )))
    _ends_on_content(doc, "part_i_item_2", "2")
    assert "ACME" not in doc.sections["part_i_item_2"].markdown()


def test_a_date_line_closing_an_auditors_report_is_kept():
    # The date repeats on every page's furniture too, and must still end Item 9A.
    doc = _parse(_ten_k(
        lambda page: f"<p>{page}</p><p>ACME HOLDINGS, INC. AND SUBSIDIARIES</p>",
        tail="<p>/s/ Auditor LLP</p><p>Atlanta, Georgia</p><p>February 20, 2025</p>",
    ))
    text = doc.sections["part_ii_item_9a"].text().rstrip()
    assert text.endswith("February 20, 2025"), text[-80:]
    assert "ACME" not in text


def test_a_numeric_table_at_the_end_is_kept_whole():
    doc = _parse(_ten_k(
        lambda page: f"<p>{page}</p><p>ACME HOLDINGS, INC. AND SUBSIDIARIES</p>",
        tail="<table><tr><td>Total</td><td>$</td><td>2,138</td><td>$</td><td>2,061</td></tr></table>",
    ))
    text = doc.sections["part_ii_item_8"].text().rstrip()
    assert text.endswith("2,061"), text[-80:]
    assert "ACME" not in text


def test_a_section_that_ends_on_content_is_left_alone():
    doc = _parse(_ten_k(lambda page: ""))
    text = doc.sections["part_i_item_3"].text().rstrip()
    assert text.endswith("Body of item 3, sentence two.")


def test_2010_filing_items_end_before_the_index_backlink():
    doc = _parse((FIXTURES_DIR / "parity_gate" / "10-K" / "0001193125-10-073212.html").read_text())
    for key in ("part_i_item_4", "part_ii_item_6", "part_ii_item_7a", "part_ii_item_9b"):
        text = " ".join(doc.sections[key].text().split())
        assert text.endswith("Not applicable.") or text.endswith("None."), f"{key}: {text[-80:]!r}"


def test_microsoft_item_1c_ends_before_the_next_pages_running_header():
    doc = _parse((FIXTURES_DIR / "html" / "msft" / "10k" / "msft-10-k-2025-07-30.html").read_text())
    text = " ".join(doc.sections["part_i_item_1c"].text().split())
    assert text.endswith("are expected to support our efforts."), text[-80:]
    text = " ".join(doc.sections["part_ii_item_9a"].text().split())
    assert text.endswith("Seattle, Washington July 30, 2025"), text[-80:]


def test_jpmorgan_item_9c_ends_before_the_parts_header():
    doc = _parse((FIXTURES_DIR / "html" / "jpm" / "10k" / "jpm-10-k-2025-02-14.html").read_text())
    text = " ".join(doc.sections["part_ii_item_9c"].text().split())
    assert text.endswith("Prevent Inspections. Not applicable."), text[-80:]


def test_goldman_mdna_ends_before_the_footer_table():
    doc = _parse((FIXTURES_DIR / "html" / "gs" / "10k" / "gs-10-k-2025-02-27.html").read_text())
    text = " ".join(doc.sections["part_ii_item_7"].text().split())
    assert text.endswith("of this Form 10-K."), text[-80:]
    assert not re.search(r"\d+ Goldman Sachs 2024 Form 10-K$", text)


def test_coca_cola_item_8_keeps_the_auditors_date():
    doc = _parse((FIXTURES_DIR / "html" / "ko" / "10k" / "ko-10-k-2025-02-20.html").read_text())
    text = " ".join(doc.sections["part_ii_item_8"].text().split())
    assert text.endswith("Atlanta, Georgia February 20, 2025"), text[-80:]


def test_mastercard_item_2_opens_on_its_heading_not_the_previous_items_running_header():
    doc = _parse((FIXTURES_DIR / "html" / "ma" / "10k" / "ma-10-k-2025-02-12.html").read_text())
    text = doc.sections["part_i_item_2"].text()
    assert text.startswith("Item 2. Properties"), text[:80]
