"""
Characterization tests for edgar.attachments (bs4 behaviour, pre-lxml port).

Pins Attachments.load() and FilingHomepage filer/date extraction on real SEC
filing index pages before the bs4 -> lxml.html port (#1102, part of #931).

Fixtures:
- tests/fixtures/attachments/indexes/apple-10q-index.html : 10-Q, iXBRL primary
  doc, GRAPHIC rows, complete-submission row, 6-file XBRL datafiles table
- tests/fixtures/attachments/indexes/fund-485-index.html  : 8-K with exhibits,
  graphics and a 5-file XBRL datafiles table
- data/troweprice.DEF14A.html                             : single-form proxy
  statement, no datafiles table, 66 filer divs

Every pinned value below is the observed output of the current bs4 code; the
port must keep these green unchanged.
"""

import pytest

from edgar._index_parsing import parse_index_html
from edgar.attachments import Attachment, Attachments, FilingHomepage

pytestmark = pytest.mark.fast


def _soup(name):
    from pathlib import Path

    if name.startswith("data/"):
        html = Path(name).read_text()
    else:
        html = Path(f"tests/fixtures/attachments/indexes/{name}").read_text()
    return parse_index_html(html)


def _load(name):
    return Attachments.load(_soup(name))


def _homepage(name):
    soup = _soup(name)
    return FilingHomepage(url="http://x/index.html", soup=soup,
                          attachments=Attachments.load(soup))


# --- Attachments.load: document table ---------------------------------------

def test_apple_10q_documents_pinned():
    atts = _load("apple-10q-index.html")
    assert [(a.sequence_number, a.description, a.document, a.ixbrl,
             a.document_type, a.size) for a in atts.documents] == [
        ("1", "10-Q", "aapl-20250329.htm", True, "10-Q", 889977),
        ("2", "EX-31.1", "a10-qexhibit31103292025.htm", False, "EX-31.1", 10524),
        ("3", "EX-31.2", "a10-qexhibit31203292025.htm", False, "EX-31.2", 10563),
        ("4", "EX-32.1", "a10-qexhibit32103292025.htm", False, "EX-32.1", 8356),
        ("10", "", "aapl-20250329_g1.jpg", False, "GRAPHIC", 10963),
        ("", "Complete submission text file", "0000320193-25-000057.txt",
         False, "", 5299807),
    ]
    assert isinstance(atts.documents[0], Attachment)
    assert atts.documents[0].path == (
        "/ix?doc=/Archives/edgar/data/320193/000032019325000057/"
        "aapl-20250329.htm")


def test_fund_485_documents_pinned():
    atts = _load("fund-485-index.html")
    docs = atts.documents
    assert len(docs) == 11
    assert docs[0].sequence_number == "1"
    assert docs[0].document == "ea191807-8k_datchat.htm"
    assert docs[0].ixbrl is True
    assert docs[0].description == "CURRENT REPORT"
    # Graphics keep their sequence numbers; the .txt row has none.
    assert [a.sequence_number for a in docs][-4:] == ["8", "9", "10", ""]
    assert docs[-1].document == "0001213900-24-004875.txt"
    assert docs[-1].description == "Complete submission text file"


def test_troweprice_single_form_proxy():
    atts = _load("data/troweprice.DEF14A.html")
    assert [(a.sequence_number, a.document, a.document_type, a.size)
            for a in atts.documents] == [
        ("1", "def14a.htm", "DEF 14A", 45348),
        ("2", "img_6aeea0a435944f2.jpg", "GRAPHIC", 10846),
        ("3", "img_9b20722f57ea4f2.jpg", "GRAPHIC", 9313),
        ("4", "img_b79bea2c076a4f3.jpg", "GRAPHIC", 10846),
        ("5", "img_ba5aa2940cb64f3.jpg", "GRAPHIC", 9313),
        ("", "0001741773-23-002051.txt", "", 256875),
    ]


def test_primary_documents_share_minimum_sequence():
    for name in ["apple-10q-index.html", "fund-485-index.html",
                 "data/troweprice.DEF14A.html"]:
        atts = _load(name)
        seqs = [a.sequence_number for a in atts.primary_documents]
        assert seqs == ["1"]


# --- Attachments.load: datafiles table --------------------------------------

def test_apple_10q_datafiles_pinned():
    atts = _load("apple-10q-index.html")
    assert [(a.sequence_number, a.document, a.document_type, a.size)
            for a in atts.data_files] == [
        ("5", "aapl-20250329.xsd", "EX-101.SCH", 33865),
        ("6", "aapl-20250329_cal.xml", "EX-101.CAL", 75630),
        ("7", "aapl-20250329_def.xml", "EX-101.DEF", 153714),
        ("8", "aapl-20250329_lab.xml", "EX-101.LAB", 494720),
        ("9", "aapl-20250329_pre.xml", "EX-101.PRE", 315516),
        ("63", "aapl-20250329_htm.xml", "XML", 758005),
    ]


def test_fund_485_datafiles_pinned():
    atts = _load("fund-485-index.html")
    assert [(a.sequence_number, a.document, a.document_type)
            for a in atts.data_files] == [
        ("11", "dats-20240116.xsd", "EX-101.SCH"),
        ("12", "dats-20240116_def.xml", "EX-101.DEF"),
        ("13", "dats-20240116_lab.xml", "EX-101.LAB"),
        ("14", "dats-20240116_pre.xml", "EX-101.PRE"),
        ("16", "ea191807-8k_datchat_htm.xml", "XML"),
    ]


def test_troweprice_has_no_datafiles_table():
    assert _load("data/troweprice.DEF14A.html").data_files is None


# --- FilingHomepage.get_filing_dates ----------------------------------------

def test_apple_10q_filing_dates():
    assert _homepage("apple-10q-index.html").get_filing_dates() == (
        "2025-05-02", "2025-05-02 06:00:46", "2025-03-29")


def test_fund_485_filing_dates():
    assert _homepage("fund-485-index.html").get_filing_dates() == (
        "2024-01-19", "2024-01-19 16:21:45", "2024-01-16")


def test_troweprice_filing_dates():
    assert _homepage("data/troweprice.DEF14A.html").get_filing_dates() == (
        "2023-06-16", "2023-06-16 12:18:40", "2023-07-24")


# --- FilingHomepage.get_filers ----------------------------------------------

def test_troweprice_66_filers_first_is_management_company():
    filers = _homepage("data/troweprice.DEF14A.html").get_filers()
    assert len(filers) == 66
    first = filers[0]
    assert first.company_name == "T. Rowe Price Small-Cap Stock Fund, Inc."
    assert first.cik == "0000075170"
    assert first.identification.startswith("IRS No.: 231622210")
