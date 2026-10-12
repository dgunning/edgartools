"""
Regression test for edgartools-llmp.12 (phase B): Item 8 was a pointer and the
financial statements sat in whichever section the filer printed last.

Some 10-Ks answer Item 8 with a sentence ("The consolidated financial
statements ... immediately following Part IV hereof", Netflix; "See the
Consolidated Financial Statements ... included in Part IV, Item 15", Talos)
and file the statements at the back, often after the signature page. The last
section then held them: Netflix's Item 16 ("Form 10-K Summary None.") ran 96k
characters, Talos's 172k, and a 2010 10-K's Item 15 held them too, while Item
8 was 120 to 290 characters. #1525 deliberately left them there, because
cutting them from the last section would have put them in no section at all.

``SECSectionExtractor._rescue_item_8_pointer_to_trailing_statements`` moves
Item 8 onto the first financial-statements heading after the start of the last
section, keeping the end that section had, and ends the last section at its
own SIGNATURES header or at the statements heading. A TOC "Signatures"
section that held them (915358, a 2016 10-K) keeps its signature block.
"""

from edgar.documents import HTMLParser, ParserConfig
from tests.paths import FIXTURES_DIR

ITEMS = [("1", "Business"), ("7", "Management's Discussion and Analysis"),
         ("8", "Financial Statements and Supplementary Data"),
         ("15", "Exhibits and Financial Statement Schedules"), ("16", "Form 10-K Summary")]
PARTS = {"7": "II", "15": "IV"}
POINTER = "The consolidated financial statements are included immediately following Part IV hereof."
STATEMENTS = ("<p>ACME, INC.</p><p>INDEX TO FINANCIAL STATEMENTS</p>"
              "<p><b>Report of Independent Registered Public Accounting Firm</b></p>"
              + "".join(f"<p>Note {i}. The company recognises revenue as described in this note, sentence {i}.</p>"
                        for i in range(200)))


def _ten_k(item_8_body: str, tail: str) -> str:
    toc = "".join(f'<tr><td><a href="#item{n}">Item {n}.</a></td><td><a href="#item{n}">{t}</a></td><td>{i + 3}</td></tr>'
                  for i, (n, t) in enumerate(ITEMS))
    body = []
    for n, t in ITEMS:
        if n in PARTS:
            body.append(f"<p><b>PART {PARTS[n]}</b></p>")
        text = item_8_body if n == "8" else f"Body of item {n}."
        body.append(f'<div id="item{n}"></div><p><b>Item {n}. {t}</b></p><p>{text}</p>')
    return ("<html><body><p><b>FORM 10-K</b></p><p><b>TABLE OF CONTENTS</b></p>"
            f"<table>{toc}</table><p><b>PART I</b></p>{''.join(body)}{tail}</body></html>")


SIGNATURES = "<p><b>SIGNATURES</b></p><p>Pursuant to the requirements, the registrant has signed.</p><p>/s/ Jane Roe</p>"


def _parse(html: str):
    return HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(html)


def test_item_8_takes_the_statements_filed_after_the_signatures():
    doc = _parse(_ten_k(POINTER, SIGNATURES + STATEMENTS))
    item_8 = doc.sections["part_ii_item_8"].text()
    assert item_8.startswith("ACME, INC."), item_8[:80]
    assert "INDEX TO FINANCIAL STATEMENTS" in item_8 and "sentence 199." in item_8
    item_16 = doc.sections["part_iv_item_16"].text().rstrip()
    assert item_16.endswith("Body of item 16."), item_16[-120:]
    assert "Jane Roe" not in item_8 and "Jane Roe" not in item_16


def test_item_8_takes_the_statements_filed_straight_after_the_last_item():
    doc = _parse(_ten_k(POINTER, STATEMENTS + SIGNATURES))
    assert "sentence 199." in doc.sections["part_ii_item_8"].text()
    assert "Jane Roe" not in doc.sections["part_ii_item_8"].text()
    assert doc.sections["part_iv_item_16"].text().rstrip().endswith("Body of item 16.")


def test_an_item_8_that_carries_its_statements_is_left_alone():
    doc = _parse(_ten_k("Revenue grew this year, and the statements follow in this item.", SIGNATURES))
    assert doc.sections["part_ii_item_8"].text().startswith("Item 8.")


def test_a_pointer_with_nothing_substantial_after_the_last_item_is_left_alone():
    doc = _parse(_ten_k(POINTER, SIGNATURES + "<p>INDEX TO FINANCIAL STATEMENTS</p><p>See above.</p>"))
    assert doc.sections["part_ii_item_8"].text().startswith("Item 8.")


def test_netflix_item_8_is_the_statements_and_item_16_the_summary():
    doc = _parse((FIXTURES_DIR / "html" / "nflx" / "10k" / "nflx-10-k-2025-01-27.html").read_text())
    item_8 = " ".join(doc.sections["part_ii_item_8"].text().split())
    assert item_8.startswith("NETFLIX, INC. INDEX TO FINANCIAL STATEMENTS"), item_8[:80]
    assert len(item_8) > 90_000
    assert " ".join(doc.sections["part_iv_item_16"].text().split()) == "Item 16. Form 10–K Summary None."


def test_talos_item_8_is_the_statements_and_item_16_the_summary():
    doc = _parse((FIXTURES_DIR / "html" / "talo" / "10k" / "talo-10-k-2026-02-25.html").read_text())
    item_8 = " ".join(doc.sections["part_ii_item_8"].text().split())
    assert item_8.startswith("Index to Consolidated Financial Statements"), item_8[:80]
    assert item_8.endswith("F- 46"), item_8[-80:]
    assert " ".join(doc.sections["part_iv_item_16"].text().split()) == "Item 16. Form 10-K Summary None."


def test_sigmatron_signatures_section_keeps_its_signature_block():
    doc = _parse((FIXTURES_DIR / "html" / "915358" / "10k" / "915358-10-k-2025-08-27.html").read_text())
    item_8 = " ".join(doc.sections["part_ii_item_8"].text().split())
    assert item_8.startswith("INDEX TO FINANCIAL STATEMENTS"), item_8[:80]
    signatures = " ".join(doc.sections["part_iv_signatures"].text().split())
    assert "SIGNATURES Pursuant to the requirements" in signatures
    assert "INDEX TO FINANCIAL STATEMENTS" not in signatures
