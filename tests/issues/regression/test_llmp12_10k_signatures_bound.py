"""
Regression test for edgartools-llmp.12 (phase B): the last item of a 10-K ran
through the signature block.

The last TOC item has no next anchor, so it ran to the end of the document.
On a 10-Q the next bare SIGNATURES header has always ended it; on a 10-K that
bound was switched off, because a 10-K often files its financial statements
after the signature page and the same cut once took a modern Item 15 from
153,840 characters to 1,051. So Apple, Caterpillar, Bank of America,
FirstEnergy and Regions returned Item 16 ("Form 10-K Summary None.") with the
whole signature table, and Goldman's Item 15 the same.

The bound now applies to a 10-K too, but only at a SIGNATURES header that
nothing of substance follows: no financial-statement index, auditor's report,
F-page, schedule or exhibit list between it and the end of the document.
Talos files its F-pages after its signatures, so its header is passed over
rather than leave the statements in no section; the Item 8 rescue that runs
next gives them to Item 8. Netflix files its signatures last, after its
statements and exhibit index, so only the signature block is cut.
"""

from edgar.documents import HTMLParser, ParserConfig
from tests.paths import FIXTURES_DIR

ITEMS = [("1", "Business"), ("7", "Management's Discussion and Analysis"),
         ("8", "Financial Statements and Supplementary Data"),
         ("15", "Exhibits and Financial Statement Schedules"), ("16", "Form 10-K Summary")]
PARTS = {"7": "II", "15": "IV"}


def _ten_k(after_last: str) -> str:
    toc = "".join(f'<tr><td><a href="#item{n}">Item {n}.</a></td><td><a href="#item{n}">{t}</a></td><td>{i + 3}</td></tr>'
                  for i, (n, t) in enumerate(ITEMS))
    body = []
    for n, t in ITEMS:
        if n in PARTS:
            body.append(f"<p><b>PART {PARTS[n]}</b></p>")
        body.append(f'<div id="item{n}"></div><p><b>Item {n}. {t}</b></p><p>Body of item {n}.</p>')
    return ("<html><body><p><b>FORM 10-K</b></p><p><b>TABLE OF CONTENTS</b></p>"
            f"<table>{toc}</table><p><b>PART I</b></p>{''.join(body)}{after_last}</body></html>")


SIGNATURES = ("<p><b>SIGNATURES</b></p><p>Pursuant to the requirements of Section 13 or 15(d), the registrant "
              "has duly caused this report to be signed.</p><p>/s/ Jane Roe, Chief Executive Officer</p>")
STATEMENTS = ("<p><b>INDEX TO CONSOLIDATED FINANCIAL STATEMENTS</b></p>"
              "<p><b>Report of Independent Registered Public Accounting Firm</b></p><p>We have audited the balance sheets.</p>")


def _parse(html: str):
    return HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(html)


def test_a_10k_last_item_ends_at_signatures_when_only_signatures_follow():
    doc = _parse(_ten_k(SIGNATURES))
    text = doc.sections["part_iv_item_16"].text().rstrip()
    assert text.endswith("Body of item 16."), text[-120:]
    assert "Jane Roe" not in text and "Jane Roe" not in doc.sections["part_iv_item_16"].markdown()


def test_financial_statements_after_the_signatures_keep_the_last_item_open():
    # The statements would belong to no section if the cut were made.
    doc = _parse(_ten_k(SIGNATURES + STATEMENTS))
    text = doc.sections["part_iv_item_16"].text()
    assert "We have audited the balance sheets." in text


def test_signatures_after_the_financial_statements_are_still_cut():
    doc = _parse(_ten_k(STATEMENTS + SIGNATURES))
    text = doc.sections["part_iv_item_16"].text().rstrip()
    assert "We have audited the balance sheets." in text
    assert "Jane Roe" not in text


def test_an_exhibit_index_after_the_signatures_is_its_own_section():
    # Item 16 kept the index open until edgartools-llmp.12 gave an index printed
    # after Item 16 its own section; Item 16 now ends at its SIGNATURES.
    doc = _parse(_ten_k(SIGNATURES + "<p><b>EXHIBIT INDEX</b></p><p>3.1 Restated Certificate of Incorporation</p>"))
    item_16 = doc.sections["part_iv_item_16"].text()
    assert "Body of item 16." in item_16
    assert "Jane Roe" not in item_16
    assert "Restated Certificate of Incorporation" in doc.sections["exhibit_index"].text()


def test_an_exhibit_list_with_no_index_heading_also_keeps_the_last_item_open():
    # A 2003 10-K lists its exhibits after the signature table under a bare
    # "Exhibits" line and an "Exhibit Description" column header.
    doc = _parse(_ten_k(SIGNATURES + "<p>Exhibits</p><table><tr><td>Exhibit</td><td>Description</td></tr>"
                                     "<tr><td>3.1</td><td>Restated Certificate of Incorporation</td></tr></table>"))
    assert "Restated Certificate of Incorporation" in doc.sections["part_iv_item_16"].text()


def test_apple_item_16_is_the_summary_alone():
    doc = _parse((FIXTURES_DIR / "html" / "aapl" / "10k" / "aapl-10-k-2024-11-01.html").read_text())
    text = " ".join(doc.sections["part_iv_item_16"].text().split())
    assert text == "Item 16. Form 10-K Summary None.", text


def test_caterpillar_item_16_drops_the_signature_page_header():
    # A bare "Form 10-K" line heads the signature page; it is furniture.
    doc = _parse((FIXTURES_DIR / "html" / "cat" / "10k" / "cat-10-k-2025-02-14.html").read_text())
    text = " ".join(doc.sections["part_iv_item_16"].text().split())
    assert text == "Item 16. Form 10-K Summary. None.", text


def test_bank_of_america_item_16_is_the_summary_alone():
    doc = _parse((FIXTURES_DIR / "html" / "bac" / "10k" / "bac-10-k-2025-02-25.html").read_text())
    text = " ".join(doc.sections["part_iv_item_16"].text().split())
    assert text == "Item 16. Form 10-K Summary Not applicable.", text


def test_talos_statements_filed_after_the_signatures_are_never_left_in_no_section():
    # The signatures bound passes over this header; the statements then move to
    # Item 8 (test_llmp12_item8_trailing_statements), never to no section.
    doc = _parse((FIXTURES_DIR / "html" / "talo" / "10k" / "talo-10-k-2026-02-25.html").read_text())
    owners = [k for k, s in doc.sections.items() if "Report of Independent Registered Public Accounting Firm" in s.text()]
    assert owners == ["part_ii_item_8"], owners


def test_netflix_signature_block_is_in_no_item():
    doc = _parse((FIXTURES_DIR / "html" / "nflx" / "10k" / "nflx-10-k-2025-01-27.html").read_text())
    for key in ("part_ii_item_8", "part_iv_item_16"):
        text = " ".join(doc.sections[key].text().split())
        assert "/S/ ANNE SWEENEY" not in text, key
