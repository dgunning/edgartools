"""
Regression test for edgartools-llmp.12 (phase B): 10-K Item 4 ran through the
unnumbered executive-officer section.

Instruction 3 to Item 401(b) of Regulation S-K lets a filer print its
executive officers in Part I instead of the proxy statement. The section is
unnumbered, so no TOC anchor ended Item 4 before it, and "Not applicable." ran
on through the officer table and the Part II divider on eight of the tracked
10-Ks: Coca-Cola ("ITEM X. INFORMATION ABOUT OUR EXECUTIVE OFFICERS"), J&J
("Executive officers of the registrant"), P&G, Exxon (the heading opens the
officer table itself), Regions, Hertz, Union Pacific and Eversource.

``SECSectionExtractor._bound_item_4_at_executive_officers`` ends Item 4 at the
first short block past its heading that opens on one of the heading shapes;
when that block is the first cell of a table, the whole table belongs to the
officers and the section ends at the table. The trailing-furniture pass runs
after it, so page furniture left between "Not applicable." and the heading
(Hertz's page number, backlink and running headers) still goes.
"""

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


def _ten_k(after_item_4: str) -> str:
    toc = "".join(
        f'<tr><td><a href="#item{n.lower()}">Item {n}.</a></td>'
        f'<td><a href="#item{n.lower()}">{t}</a></td><td>{i + 3}</td></tr>'
        for i, (n, t) in enumerate(ITEMS)
    )
    body = []
    for n, t in ITEMS:
        if n in PARTS:
            body.append(f"<p><b>PART {PARTS[n]}</b></p>")
        body.append(f'<div id="item{n.lower()}"></div>')
        body.append(f"<p><b>Item {n}. {t}</b></p>")
        body.append(f"<p>Body of item {n}, sentence one.</p>")
        if n == "4":
            body.append(after_item_4)
    return (
        "<html><body><p><b>FORM 10-K</b></p><p><b>TABLE OF CONTENTS</b></p>"
        f"<table>{toc}</table><p><b>PART I</b></p>{''.join(body)}"
        "<p><b>SIGNATURES</b></p><p>Signed.</p></body></html>"
    )


def _parse(html: str):
    return HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(html)


OFFICERS = (
    "<p>The following are the executive officers of our Company as of February 20, 2025:</p>"
    "<table><tr><td>Name</td><td>Age</td><td>Position</td></tr>"
    "<tr><td>Jane Roe</td><td>57</td><td>Chief Executive Officer</td></tr></table>"
)


def _item_4_ends_on_content(doc):
    text = doc.sections["part_i_item_4"].text().rstrip()
    assert text.endswith("Body of item 4, sentence one."), text[-120:]
    assert "Jane Roe" not in text and "PART II" not in text
    assert "Jane Roe" not in doc.sections["part_i_item_4"].markdown()
    assert "Jane Roe" not in doc.sections["part_ii_item_5"].text()


def test_item_4_ends_at_information_about_our_executive_officers():
    _item_4_ends_on_content(_parse(_ten_k("<p><b>Information About Our Executive Officers</b></p>" + OFFICERS)))


def test_item_4_ends_at_executive_officers_of_the_registrant():
    _item_4_ends_on_content(_parse(_ten_k("<p><b>Executive Officers of the Registrant</b></p>" + OFFICERS)))


def test_item_4_ends_at_coca_colas_item_x_heading():
    _item_4_ends_on_content(_parse(_ten_k("<p><b>ITEM X. INFORMATION ABOUT OUR EXECUTIVE OFFICERS</b></p>" + OFFICERS)))


def test_item_4_ends_before_page_furniture_ahead_of_the_heading():
    doc = _parse(_ten_k('<p>43</p><p><a href="#toc">Table of Contents</a></p>'
                        "<p><b>INFORMATION ABOUT OUR EXECUTIVE OFFICERS</b></p>" + OFFICERS))
    _item_4_ends_on_content(doc)
    assert "Table of Contents" not in doc.sections["part_i_item_4"].text()


def test_item_4_ends_at_an_officer_table_that_opens_on_the_heading():
    doc = _parse(_ten_k("<table><tr><td>Information about our Executive Officers (positions and ages as of February 19, 2025)</td></tr>"
                        "<tr><td>Name</td><td>Age</td></tr><tr><td>Jane Roe</td><td>57</td></tr></table>"))
    _item_4_ends_on_content(doc)


def test_a_sentence_mentioning_executive_officers_is_not_a_heading():
    doc = _parse(_ten_k("<p>Information about our executive officers appears in the proxy statement.</p>"))
    text = doc.sections["part_i_item_4"].text().rstrip()
    assert text.endswith("appears in the proxy statement."), text[-120:]


def test_coca_cola_item_4_ends_at_not_applicable():
    doc = _parse((FIXTURES_DIR / "html" / "ko" / "10k" / "ko-10-k-2025-02-20.html").read_text())
    text = " ".join(doc.sections["part_i_item_4"].text().split())
    assert text == "ITEM 4. MINE SAFETY DISCLOSURES Not applicable.", text


def test_exxon_item_4_ends_before_the_officer_table():
    doc = _parse((FIXTURES_DIR / "html" / "xom" / "10k" / "xom-10-k-2025-02-19.html").read_text())
    text = " ".join(doc.sections["part_i_item_4"].text().split())
    assert text == "ITEM 4. MINE SAFETY DISCLOSURES Not applicable.", text


def test_hertz_item_4_ends_at_not_applicable():
    doc = _parse((FIXTURES_DIR / "html" / "htz" / "10k" / "htz-10-k-2025-02-18.html").read_text())
    text = " ".join(doc.sections["part_i_item_4"].text().split())
    assert text == "ITEM 4. MINE SAFETY DISCLOSURES Not applicable.", text


def test_jnj_item_4_ends_at_not_applicable():
    doc = _parse((FIXTURES_DIR / "html" / "jnj" / "10k" / "jnj-10-k-2025-02-13.html").read_text())
    text = " ".join(doc.sections["part_i_item_4"].text().split())
    assert text == "Item 4. Mine safety disclosures Not applicable.", text
