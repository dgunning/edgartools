"""
Regression test for edgartools-llmp.12 (phase B): the last item of a Part runs
through the next Part's divider.

A TOC section ends at the next TOC anchor in document order. For the last item
of a Part that anchor belongs to the first item of the next Part and sits after
the Part divider, so the divider trailed the slice: 27 of the 32 tracked
10-Ks returned "Not applicable. PART II" for Item 4 (and "PART III" for 9C,
"PART IV" for 14), Chevron's rescued Item 8 ran through "PART IV" to Item 15's
anchor, and every 10-Q's Part I Item 4 carried "PART II. OTHER INFORMATION"
into its markdown. The text walk happened to drop the 10-Q line through the
navigation filter; the markdown slicer never did.

The TOC extractor now ends a section at the first block in its range whose
whole text is a Part divider for a Part later than the section's own. A
running page header repeating the section's own Part never cuts it, prose that
merely opens on "Part II" is not a divider, and when the divider opens a
contents-list table (Mastercard) the section ends at the table.
"""

from edgar.documents import HTMLParser, ParserConfig
from tests.paths import FIXTURES_DIR

ITEMS = [
    ("1", "Business"), ("1A", "Risk Factors"), ("2", "Properties"),
    ("3", "Legal Proceedings"), ("4", "Mine Safety Disclosures"),
    ("5", "Market for Registrant's Common Equity"), ("7", "Management's Discussion and Analysis"),
    ("8", "Financial Statements and Supplementary Data"), ("9A", "Controls and Procedures"),
    ("9C", "Disclosure Regarding Foreign Jurisdictions"),
    ("10", "Directors, Executive Officers and Corporate Governance"), ("14", "Principal Accountant Fees"),
    ("15", "Exhibits and Financial Statement Schedules"),
]
PARTS = {"5": "II", "10": "III", "15": "IV"}


def _ten_k(divider_html=None, contents_list: bool = False) -> str:
    """A 10-K whose Parts are divided by ``divider_html(part)`` blocks."""
    divider_html = divider_html or (lambda part: f"<p><b>PART {part}</b></p>")
    toc = "".join(
        f'<tr><td><a href="#item{n.lower()}">Item {n}.</a></td>'
        f'<td><a href="#item{n.lower()}">{t}</a></td><td>{i + 3}</td></tr>'
        for i, (n, t) in enumerate(ITEMS)
    )
    body = []
    for n, t in ITEMS:
        if n in PARTS:
            body.append(divider_html(PARTS[n]))
            if contents_list:
                body.append(
                    "<table><tr><td colspan='2'>PART " + PARTS[n] + "</td></tr>"
                    + "".join(f"<tr><td>Item {m}.</td><td>{u}</td></tr>"
                              for m, u in ITEMS if m >= n)
                    + "</table>"
                )
        body.append(f'<div id="item{n.lower()}"></div><p><b>Item {n}. {t}</b></p>')
        body.append(f"<p>Body of item {n}, sentence one.</p>")
        if n == "1":
            # A running page header repeats the section's own Part mid-body.
            body.append("<p>PART I</p>")
        if n == "3":
            # Prose that opens on a Part number is not a divider.
            body.append("<p>Part II of this report contains the financial statements.</p>")
        body.append(f"<p>Body of item {n}, sentence two.</p>")
    return (
        "<html><body><p><b>FORM 10-K</b></p><p><b>TABLE OF CONTENTS</b></p>"
        f"<table>{toc}</table><p><b>PART I</b></p>{''.join(body)}"
        "<p><b>SIGNATURES</b></p><p>Signed.</p></body></html>"
    )


def _parse(html: str, form: str = "10-K"):
    return HTMLParser(ParserConfig(form=form, detect_sections=True)).parse(html)


def test_last_item_of_each_part_ends_at_the_next_part_divider():
    doc = _parse(_ten_k())
    for key, part in (("part_i_item_4", "II"), ("part_ii_item_9c", "III"), ("part_iii_item_14", "IV")):
        text = doc.sections[key].text()
        assert doc.sections[key].detection_method == "toc"
        assert text.rstrip().endswith("sentence two."), f"{key} tail: {text[-120:]!r}"
        assert f"PART {part}" not in text, f"{key} ran through the Part {part} divider: {text[-120:]!r}"
        assert f"PART {part}" not in doc.sections[key].markdown()


def test_own_part_header_and_part_prose_do_not_cut_a_section():
    doc = _parse(_ten_k())
    item_1 = doc.sections["part_i_item_1"].text()
    assert "Body of item 1, sentence two." in item_1, item_1[-160:]
    item_3 = doc.sections["part_i_item_3"].text()
    assert "Part II of this report contains" in item_3
    assert "Body of item 3, sentence two." in item_3, item_3[-160:]


def test_a_titled_divider_ends_the_section_too():
    doc = _parse(_ten_k(lambda part: f"<div><span>PART {part}. OTHER INFORMATION</span></div>"))
    text = doc.sections["part_i_item_4"].text()
    assert text.rstrip().endswith("sentence two."), text[-120:]


def test_a_divider_split_across_inline_tags_ends_the_section():
    # Oracle: <p id="part_iv">PAR<a name="x"></a>T IV</p>
    doc = _parse(_ten_k(lambda part: f'<p>PAR<a name="p{part}"></a>T {part}</p>'))
    text = doc.sections["part_ii_item_9c"].text()
    assert text.rstrip().endswith("sentence two."), text[-120:]
    assert "T III" not in text


def test_a_contents_list_opened_by_the_divider_belongs_to_the_next_part():
    doc = _parse(_ten_k(contents_list=True))
    text = doc.sections["part_i_item_4"].text()
    assert text.rstrip().endswith("sentence two."), text[-200:]
    assert "Item 7." not in text


def test_apple_item_4_ends_before_part_ii():
    path = FIXTURES_DIR / "html" / "aapl" / "10k" / "aapl-10-k-2024-11-01.html"
    doc = _parse(path.read_text())
    text = doc.sections["part_i_item_4"].text()
    # The page footer before the divider is a running header, left to a later fix.
    assert text.rstrip().endswith("Apple Inc. | 2024 Form 10-K | 18"), text[-120:]
    assert "Not applicable." in text
    assert "PART II" not in text
    assert "PART III" not in doc.sections["part_ii_item_9c"].text()
    assert "PART IV" not in doc.sections["part_iii_item_14"].text()


def test_nvidia_item_9c_leaves_the_part_iii_preamble_to_part_iii():
    path = FIXTURES_DIR / "html" / "nvda" / "10k" / "nvda-10-k-2025-02-26.html"
    doc = _parse(path.read_text())
    text = doc.sections["part_ii_item_9c"].text()
    assert text.rstrip().endswith("Not Applicable."), text[-160:]
    assert "Certain information required by Part III" not in text


def test_mastercard_item_4_stops_before_the_part_ii_contents_list():
    path = FIXTURES_DIR / "html" / "ma" / "10k" / "ma-10-k-2025-02-12.html"
    doc = _parse(path.read_text())
    text = doc.sections["part_i_item_4"].text()
    assert "Item 7. Management" not in text, text[-300:]
    assert "PART II" not in text


def test_apple_10q_part_i_item_4_markdown_ends_before_part_ii():
    path = FIXTURES_DIR / "html" / "aapl" / "10q" / "aapl-10-q-2025-08-01.html"
    doc = _parse(path.read_text(), form="10-Q")
    md = doc.sections["part_i_item_4"].markdown()
    assert "OTHER INFORMATION" not in md, md[-200:]
