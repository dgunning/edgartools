"""
Regression test for edgartools-llmp.12 (phase B): a title-only TOC's
"Form 10-K Summary" row never became Item 16.

Morgan Stanley's 10-K lists its items by title alone. "Exhibits and Financial
Statement Schedules" reached Item 15 through the 10-K text rules, but "Form
10-K Summary" matched no rule and none of the keywords the section-link check
accepts, so the row was dropped before normalisation: no section ended at its
anchor, ``part_iv_item_16`` did not exist, and Item 15 ran on through "Form
10-K Summary None." (and, before the page-furniture passes, the footer between).

The 10-K rules now map "form 10-k summary" to Item 16, and the section-link
check admits any title the form's text rules map to an item, so the two
decisions are one table (``_TEN_K_RULES``).
"""

from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.form_schema import get_form_schema
from tests.paths import FIXTURES_DIR

TITLES = [
    ("1", "Business"), ("1A", "Risk Factors"), ("2", "Properties"), ("3", "Legal Proceedings"),
    ("7", "Management's Discussion and Analysis of Financial Condition and Results of Operations"),
    ("8", "Financial Statements and Supplementary Data"),
    ("15", "Exhibits and Financial Statement Schedules"), ("16", "Form 10-K Summary"),
]
PARTS = {"7": "II", "15": "IV"}


def _title_only_ten_k() -> str:
    toc = "".join(f'<tr><td><a href="#s{n.lower()}">{t}</a></td><td>{i + 3}</td></tr>' for i, (n, t) in enumerate(TITLES))
    body = []
    for n, t in TITLES:
        if n in PARTS:
            body.append(f"<p><b>PART {PARTS[n]}</b></p>")
        body.append(f'<div id="s{n.lower()}"></div><p><b>{t}</b></p><p>Body of {t}, sentence one.</p>')
    return ("<html><body><p><b>FORM 10-K</b></p><p><b>TABLE OF CONTENTS</b></p>"
            f"<table>{toc}</table><p><b>PART I</b></p>{''.join(body)}<p><b>SIGNATURES</b></p><p>Signed.</p></body></html>")


def _parse(html: str):
    return HTMLParser(ParserConfig(form="10-K", detect_sections=True)).parse(html)


def test_the_ten_k_rules_map_the_summary_title_to_item_16():
    assert get_form_schema("10-K").match_text("form 10-k summary") == "Item 16"
    assert get_form_schema("10-Q").match_text("form 10-k summary") is None


def test_a_title_only_toc_emits_item_16_and_ends_item_15_before_it():
    doc = _parse(_title_only_ten_k())
    assert "part_iv_item_16" in doc.sections
    item_15 = doc.sections["part_iv_item_15"].text()
    assert item_15.rstrip().endswith("Body of Exhibits and Financial Statement Schedules, sentence one."), item_15[-120:]
    assert "Form 10-K Summary" not in item_15
    assert doc.sections["part_iv_item_16"].text().startswith("Form 10-K Summary")


def test_morgan_stanley_item_15_ends_before_its_form_10k_summary():
    doc = _parse((FIXTURES_DIR / "html" / "ms" / "10k" / "ms-10-k-2025-02-21.html").read_text())
    assert "part_iv_item_16" in doc.sections
    item_15 = " ".join(doc.sections["part_iv_item_15"].text().split())
    assert item_15.endswith("Securities and Exchange Commission upon request."), item_15[-120:]
    assert "Form 10-K Summary" not in item_15
    item_16 = " ".join(doc.sections["part_iv_item_16"].text().split())
    assert item_16 == "Form 10-K Summary None.", item_16
