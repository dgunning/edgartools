"""
Regression test for edgartools-llmp.12 (phase B): a section runs through the
heading of an item its TOC never listed.

A TOC section ends at the next TOC anchor in document order. An item the TOC
omits (Item 16, "Form 10-K Summary", which filers may skip and many TOCs
leave out even when the body carries it) has no anchor, so the section before
it ran through its heading: AmEx, J&J, Chevron and Ondas all returned Item 15
with "Item 16. Form 10-K Summary" inside it, Chevron's rescued Item 8 ran on
through Items 15 and 16 to the end of the filing, and P&G's 10-Q Part I Item 4
swallowed Part II Item 1. The pattern tier later adds those items as sections
of their own, but the TOC section never learned where they begin.

The TOC extractor now ends a section at the first short block in its range
whose text opens on the heading of a canonical item that resolved to no
section in this Part or later and comes after the section's own item. Two
guards keep that to headings: a block inside a table holding two or more such
blocks is an index row, not a heading (GE's cross-reference index,
Mastercard's per-Part contents list), and on a unique-item form the item must
be later than the section's own.
"""

from edgar.documents import HTMLParser, ParserConfig
from tests.paths import FIXTURES_DIR

ITEMS_10K = [
    ("1", "Business"), ("1A", "Risk Factors"), ("1B", "Unresolved Staff Comments"),
    ("2", "Properties"), ("3", "Legal Proceedings"), ("4", "Mine Safety Disclosures"),
    ("5", "Market for Registrant's Common Equity"), ("6", "Reserved"),
    ("7", "Management's Discussion and Analysis"), ("7A", "Quantitative and Qualitative Disclosures"),
    ("8", "Financial Statements and Supplementary Data"), ("9", "Changes in and Disagreements"),
    ("9A", "Controls and Procedures"), ("9B", "Other Information"),
    ("10", "Directors, Executive Officers and Corporate Governance"), ("11", "Executive Compensation"),
    ("12", "Security Ownership"), ("13", "Certain Relationships"), ("14", "Principal Accountant Fees"),
    ("15", "Exhibits and Financial Statement Schedules"),
]


def _ten_k(listed, body_items, index_table_in_15: bool = False) -> str:
    """A 10-K whose TOC lists ``listed`` items while the body carries ``body_items``."""
    toc = "".join(
        f'<tr><td><a href="#item{n.lower()}">Item {n}.</a></td>'
        f'<td><a href="#item{n.lower()}">{t}</a></td><td>{i + 3}</td></tr>'
        for i, (n, t) in enumerate(body_items) if n in listed
    )
    parts = {"5": "PART II", "10": "PART III", "15": "PART IV"}
    body = []
    for n, t in body_items:
        if n in parts:
            body.append(f"<p><b>{parts[n]}</b></p>")
        body.append(f'<div id="item{n.lower()}"></div><p><b>Item {n}. {t}</b></p>')
        body.append(f"<p>Body of item {n}, sentence one. Body of item {n}, sentence two.</p>")
        if n == "15" and index_table_in_15:
            body.append(
                "<table>"
                + "".join(f"<tr><td>Item {m}.</td><td>{u}</td><td>{j + 3}</td></tr>"
                          for j, (m, u) in enumerate(body_items))
                + "</table><p>Exhibit list follows.</p>"
            )
    return (
        "<html><body><p><b>FORM 10-K</b></p><p><b>TABLE OF CONTENTS</b></p>"
        f"<table>{toc}</table><p><b>PART I</b></p>{''.join(body)}"
        "<p><b>SIGNATURES</b></p><p>Signed.</p></body></html>"
    )


def _parse(html: str, form: str = "10-K"):
    return HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(html)


def test_item_15_ends_at_the_unlisted_item_16_heading():
    body = ITEMS_10K + [("16", "Form 10-K Summary")]
    doc = _parse(_ten_k(listed={n for n, _ in ITEMS_10K}, body_items=body))

    item_15 = doc.sections["part_iv_item_15"]
    assert item_15.detection_method == "toc"
    text = item_15.text()
    assert text.startswith("Item 15. Exhibits"), text[:80]
    assert "Body of item 15, sentence two." in text
    assert "Item 16" not in text, f"Item 15 ran through the unlisted Item 16 heading: {text[-160:]!r}"
    assert "Body of item 16" not in text


def test_an_index_table_inside_the_section_is_not_a_heading():
    # Item 15's exhibit index lists every item, Item 16 included, in table rows.
    # Those rows are content; the section must not be cut at one of them.
    body = ITEMS_10K + [("16", "Form 10-K Summary")]
    doc = _parse(_ten_k(listed={n for n, _ in ITEMS_10K}, body_items=body, index_table_in_15=True))

    text = doc.sections["part_iv_item_15"].text()
    assert "Exhibit list follows." in text, f"Item 15 was cut inside its index table: {text[-200:]!r}"
    # ... but it still stops at the real Item 16 heading after the table.
    assert "Body of item 16" not in text


def test_a_fully_listed_toc_is_unchanged():
    body = ITEMS_10K + [("16", "Form 10-K Summary")]
    doc = _parse(_ten_k(listed={n for n, _ in body}, body_items=body))

    text = doc.sections["part_iv_item_15"].text()
    assert "Body of item 15, sentence two." in text
    assert "Item 16" not in text


def test_chevron_item_15_and_rescued_item_8_stop_at_item_16():
    path = FIXTURES_DIR / "html" / "cvx" / "10k" / "cvx-10-k-2025-02-21.html"
    doc = _parse(path.read_text())

    item_15 = doc.sections["part_iv_item_15"].text()
    assert item_15.startswith("Item 15. Exhibit"), item_15[:80]
    assert "Item 16. Form 10-K Summary" not in item_15
    item_8 = doc.sections["part_ii_item_8"].text()
    assert "Item 15. Exhibit and Financial Statement Schedules" not in item_8
    assert "Item 16. Form 10-K Summary" not in item_8


def test_amex_item_15_stops_at_item_16():
    path = FIXTURES_DIR / "html" / "axp" / "10k" / "axp-10-k-2025-02-07.html"
    doc = _parse(path.read_text())

    text = doc.sections["part_iv_item_15"].text()
    assert "FORM 10-K SUMMARY" not in text.upper(), text[-200:]
