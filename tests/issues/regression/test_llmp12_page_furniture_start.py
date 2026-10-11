"""
Regression test for edgartools-llmp.12 (phase B): a section opens on page
furniture instead of its heading.

A TOC anchor often sits at the top of a page, before the backlink to the
contents, the page number and the running header the filer prints on every
page, and the section's heading comes after them. The text walk then opened
on "Table of Contents" (70 of the 138 start-wrong items in the truth set:
AmEx, Meta, Netflix, Regions, Union Pacific and more), on "THE GOLDMAN SACHS
GROUP, INC. AND SUBSIDIARIES" (Goldman), on "32 The Procter & Gamble Company"
(P&G), on a bare page number (a page-anchored 20-F), or on the Part divider
the anchor was placed on (Eversource). The navigation filter keeps the first
two occurrences of a repeated link per section text, so a backlink at the head
of every section always survived it, and the markdown slicer never filtered.

The TOC extractor now advances ``start_element`` past leading furniture: a
contents backlink, a bare page number, a Part divider for the section's own
Part or earlier, or a short line the document repeats on three or more pages.
The section's own "Item N" heading is never furniture, whatever it repeats.
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


def _ten_k(furniture, anchor_on_divider: bool = False) -> str:
    """A 10-K whose anchors sit at a page top, before ``furniture(n)`` blocks."""
    toc = "".join(
        f'<tr><td><a href="#item{n.lower()}">Item {n}.</a></td>'
        f'<td><a href="#item{n.lower()}">{t}</a></td><td>{i + 3}</td></tr>'
        for i, (n, t) in enumerate(ITEMS)
    )
    body = []
    for i, (n, t) in enumerate(ITEMS):
        if n in PARTS:
            if anchor_on_divider:
                body.append(f'<p id="item{n.lower()}"><b>PART {PARTS[n]}</b></p>')
            else:
                body.append(f"<p><b>PART {PARTS[n]}</b></p>")
        if not (anchor_on_divider and n in PARTS):
            body.append(f'<div id="item{n.lower()}"></div>')
        body.append(furniture(i + 3))
        body.append(f"<p><b>Item {n}. {t}</b></p>")
        body.append(f"<p>Body of item {n}, sentence one.</p>")
        body.append(f"<p>Body of item {n}, sentence two.</p>")
    return (
        "<html><body><p><b>FORM 10-K</b></p><p><b>TABLE OF CONTENTS</b></p>"
        f"<table>{toc}</table><p><b>PART I</b></p>{''.join(body)}"
        "<p><b>SIGNATURES</b></p><p>Signed.</p></body></html>"
    )


def _parse(html: str, form: str = "10-K"):
    return HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(html)


def _opens_on_heading(doc, key, item, title):
    text = doc.sections[key].text()
    assert text.startswith(f"Item {item}. {title}"), f"{key} opens on {text[:80]!r}"
    assert "sentence two." in text
    md = doc.sections[key].markdown()
    assert "Table of Contents" not in md and "ACME" not in md, md[:200]


def test_backlink_page_number_and_running_header_are_skipped():
    doc = _parse(_ten_k(lambda page: (
        '<p><a href="#toc">Table of Contents</a></p>'
        f"<p>{page}</p>"
        "<p>ACME HOLDINGS, INC. AND SUBSIDIARIES</p>"
    )))
    _opens_on_heading(doc, "part_i_item_1a", "1A", "Risk Factors")
    _opens_on_heading(doc, "part_ii_item_7", "7", "Management's Discussion and Analysis")
    _opens_on_heading(doc, "part_iii_item_10", "10", "Directors, Executive Officers and Corporate Governance")


def test_a_running_header_that_restates_the_heading_keeps_the_heading():
    # The furniture is the heading in capitals, repeated on every page.
    doc = _parse(_ten_k(lambda page: "<p>ITEM 1A. RISK FACTORS</p>"))
    text = doc.sections["part_i_item_1a"].text()
    assert text.startswith("Item 1A. Risk Factors"), text[:80]
    assert "ITEM 1A. RISK FACTORS" not in text


def test_an_anchor_placed_on_the_part_divider_starts_at_the_heading():
    doc = _parse(_ten_k(lambda page: "", anchor_on_divider=True))
    text = doc.sections["part_ii_item_5"].text()
    assert text.startswith("Item 5. Market"), text[:80]
    assert "PART II" not in text


def test_a_section_that_opens_on_content_is_left_alone():
    doc = _parse(_ten_k(lambda page: ""))
    text = doc.sections["part_i_item_2"].text()
    assert text.startswith("Item 2. Properties"), text[:80]
    assert text.count("Body of item 2") == 2


def test_amex_risk_factors_open_on_the_heading_not_the_backlink():
    doc = _parse((FIXTURES_DIR / "html" / "axp" / "10k" / "axp-10-k-2025-02-07.html").read_text())
    text = doc.sections["part_i_item_1a"].text()
    assert re.match(r"ITEM\s1A\.\s+RISK FACTORS", text), text[:80]
    assert not doc.sections["part_ii_item_7"].markdown().lstrip().startswith("Table of Contents")


def test_goldman_mdna_opens_on_the_heading_not_the_running_header():
    doc = _parse((FIXTURES_DIR / "html" / "gs" / "10k" / "gs-10-k-2025-02-27.html").read_text())
    text = doc.sections["part_ii_item_7"].text()
    assert text.startswith("Item 7."), text[:80]
    assert "THE GOLDMAN SACHS GROUP, INC. AND SUBSIDIARIES" not in text[:200]


def test_pg_item_8_opens_on_the_heading_not_the_page_footer():
    doc = _parse((FIXTURES_DIR / "html" / "pg" / "10k" / "pg-10-k-2025-08-04.html").read_text())
    text = doc.sections["part_ii_item_8"].text()
    assert text.startswith("Item 8."), text[:80]


def test_eversource_item_5_opens_on_the_heading_not_the_part_divider():
    doc = _parse((FIXTURES_DIR / "html" / "es" / "10k" / "es-10-k-2024-02-14.html").read_text())
    text = doc.sections["part_ii_item_5"].text()
    assert text.startswith("Item 5."), text[:80]
