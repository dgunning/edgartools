"""Pin `_FundCompanyInfo.from_html` before the lxml port.

edgartools-07lk.11.11. This is the page behind `direct_get_fund_with_filings`,
which `get_fund_with_filings()` and `FundSeries.get_filings()` both go through:
browse-edgar's company view for a class or series id, carrying the fund's name,
CIK, identifying information, addresses and a page of filings.

`_extract_filings` is exercised THROUGH `from_html` rather than directly,
because it takes an already-parsed tree whose type is exactly what this port
changes -- calling it directly would need the test to know which library is in
force, and would stop being a fair comparison the moment it did.

The corpus is committed as real HTML rather than fingerprinted: these pages only
exist over the network, and the local HTTP cache serves before a cassette, so a
cassette-driven gate proves nothing about CI.
"""
import json
import pathlib

import pytest

pytestmark = pytest.mark.fast

REPO = pathlib.Path(__file__).parent.parent
PAGES = REPO / "tests" / "fixtures" / "funds_company_pages"
BASELINE = REPO / "tests" / "fixtures" / "funds_company_info_baseline.json"


def _page(company_info: str, filings_rows: str = "", mailers: str = "") -> str:
    """A browse-edgar company page cut down to the parts this code reads."""
    return (
        "<html><body><div id='contentDiv'>"
        f"<div class='companyInfo'>{company_info}</div>"
        f"{mailers}"
        "<table class='tableFile2'>"
        "<tr><th>Filings</th><th>Format</th><th>Description</th><th>Filing Date</th></tr>"
        f"{filings_rows}"
        "</table></div></body></html>"
    )


_NAME = ("<span class='companyName'>KINETICS MUTUAL FUNDS INC "
         "<a href='/cgi-bin/browse-edgar?action=getcompany&CIK=0001083387'>"
         "0001083387 (see all company filings)</a></span>")
_IDENT = ("<p class='identInfo'>SIC: 0000 | State location: NY | "
          "State of Inc.: MD | Fiscal Year End: 1231</p>")
_ROW = ("<tr><td>N-CSR</td>"
        "<td><a href='/Archives/edgar/data/1083387/000123456725000001-index.htm'>"
        "Documents</a></td>"
        "<td>Annual report</td><td>2025-03-01</td></tr>")

EDGE = {
    "missing-contentDiv": "<html><body><p>Nothing here.</p></body></html>",
    "minimal-complete-page": _page(_NAME + _IDENT, _ROW),
    # `.text` on an lxml element is the text BEFORE the first child.
    "company-name-split-across-tags": _page(
        "<span class='companyName'>KINETICS <b>MUTUAL</b> FUNDS INC "
        "<a href='/x'>0001083387 (see all company filings)</a></span>" + _IDENT, _ROW),
    # `company_name_tag.a` is find('a') -- the first <a> DESCENDANT.
    "cik-link-nested-inside-bold": _page(
        "<span class='companyName'>KINETICS "
        "<b><a href='/x'>0001083387 (see all company filings)</a></b></span>" + _IDENT, _ROW),
    "cik-link-text-split-across-tags": _page(
        "<span class='companyName'>KINETICS "
        "<a href='/x'><b>0001083387</b> (see all company filings)</a></span>" + _IDENT, _ROW),
    # bs4 matched class_= against the multi-valued class LIST.
    "classes-among-several": _page(
        "<span class='big companyName'>KINETICS "
        "<a href='/x'>0001083387 (see all company filings)</a></span>"
        "<p class='identInfo small'>State location: NY</p>", _ROW),
    # Every <br> is REPLACED by a newline before identInfo is read.
    "br-inside-ident-info": _page(
        _NAME + "<p class='identInfo'>SIC: 0000<br>State location: NY<br>"
        "State of Inc.: MD</p>", _ROW),
    "br-and-pipes-together": _page(
        _NAME + "<p class='identInfo'>SIC: 0000 | State location: NY<br>"
        "Fiscal Year End: 1231</p>", _ROW),
    "ident-value-with-nbsp": _page(
        _NAME + "<p class='identInfo'>State location:&nbsp;NY | SIC:&nbsp;0000</p>", _ROW),
    "ident-line-without-a-colon": _page(
        _NAME + "<p class='identInfo'>No colon here | State location: NY</p>", _ROW),
    "ident-info-split-across-tags": _page(
        _NAME + "<p class='identInfo'>State <b>location</b>: NY</p>", _ROW),
    "comment-inside-ident-info": _page(
        _NAME + "<p class='identInfo'>State location: N<!-- note -->Y</p>", _ROW),
    # Addresses: mailer text, with runs of indentation collapsed onto the newline.
    "mailer-divs": _page(_NAME + _IDENT, _ROW,
        "<div class='mailer'>Mailing Address\n      615 EAST MICHIGAN ST\n"
        "      MILWAUKEE WI 53202</div>"
        "<div class='mailer'>Business Address\n      615 EAST MICHIGAN ST\n"
        "      MILWAUKEE WI 53202\n      414-765-4124</div>"),
    "mailer-with-br-tags": _page(_NAME + _IDENT, _ROW,
        "<div class='mailer'>Mailing Address<br>615 EAST MICHIGAN ST<br>"
        "MILWAUKEE WI 53202</div>"),
    "no-mailer-divs": _page(_NAME + _IDENT, _ROW, ""),
    # The filings table.
    "no-filings-rows": _page(_NAME + _IDENT, ""),
    "two-filing-rows": _page(_NAME + _IDENT, _ROW + _ROW.replace("2025-03-01", "2024-03-01")),
    "form-name-split-across-tags": _page(_NAME + _IDENT,
        "<tr><td>N-<b>CSR</b></td>"
        "<td><a href='/Archives/edgar/data/1/0001-index.htm'>Documents</a></td>"
        "<td>x</td><td>2025-03-01</td></tr>"),
    "filing-date-split-across-tags": _page(_NAME + _IDENT,
        "<tr><td>N-CSR</td>"
        "<td><a href='/Archives/edgar/data/1/0001-index.htm'>Documents</a></td>"
        "<td>x</td><td>2025-<b>03</b>-01</td></tr>"),
    "documents-link-nested": _page(_NAME + _IDENT,
        "<tr><td>N-CSR</td>"
        "<td><b><a href='/Archives/edgar/data/1/0001-index.htm'>Documents</a></b></td>"
        "<td>x</td><td>2025-03-01</td></tr>"),
    # find_all('td') was recursive, so a nested table shifts every index.
    "nested-table-in-a-filing-row": _page(_NAME + _IDENT,
        "<tr><td>N-CSR</td>"
        "<td><table><tr><td>inner</td></tr></table>"
        "<a href='/Archives/edgar/data/1/0001-index.htm'>Documents</a></td>"
        "<td>x</td><td>2025-03-01</td></tr>"),
    # Shapes that raise. The exception IS the behaviour and must not change.
    "missing-companyInfo": (
        "<html><body><div id='contentDiv'><p>No company info.</p>"
        "<table class='tableFile2'><tr><th>h</th></tr></table></div></body></html>"),
    "missing-filings-table": (
        "<html><body><div id='contentDiv'>"
        f"<div class='companyInfo'>{_NAME}{_IDENT}</div></div></body></html>"),
    "filing-link-without-an-href": _page(_NAME + _IDENT,
        "<tr><td>N-CSR</td><td><a>Documents</a></td><td>x</td><td>2025-03-01</td></tr>"),
    "filing-date-not-a-date": _page(_NAME + _IDENT,
        "<tr><td>N-CSR</td>"
        "<td><a href='/Archives/edgar/data/1/0001-index.htm'>Documents</a></td>"
        "<td>x</td><td>not a date</td></tr>"),
    "script-inside-the-company-name": _page(
        "<span class='companyName'>KINETICS <script>var x='GHOST';</script>FUNDS "
        "<a href='/x'>0001083387 (see all company filings)</a></span>" + _IDENT, _ROW),
    # lxml roots a single-element fragment AT that element, so a page that IS
    # the contentDiv has no descendant matching it. bs4 searched from the soup,
    # which is the document rather than the element, and found it.
    "page-is-a-bare-contentDiv-fragment": (
        "<div id='contentDiv'>"
        f"<div class='companyInfo'>{_NAME}{_IDENT}</div>"
        "<table class='tableFile2'>"
        "<tr><th>Filings</th><th>Format</th><th>Description</th><th>Filing Date</th></tr>"
        f"{_ROW}</table></div>"
    ),
    # find() returned the FIRST match. These two only differ if it returns
    # another one.
    "two-companyName-spans": _page(
        "<span class='companyName'>FIRST FUND "
        "<a href='/x'>0001111111 (see all company filings)</a></span>"
        "<span class='companyName'>SECOND FUND "
        "<a href='/y'>0002222222 (see all company filings)</a></span>" + _IDENT, _ROW),
    "two-filings-tables": (
        "<html><body><div id='contentDiv'>"
        f"<div class='companyInfo'>{_NAME}{_IDENT}</div>"
        "<table class='tableFile2'>"
        "<tr><th>Filings</th><th>Format</th><th>Description</th><th>Filing Date</th></tr>"
        f"{_ROW}</table>"
        "<table class='tableFile2'>"
        "<tr><th>Filings</th><th>Format</th><th>Description</th><th>Filing Date</th></tr>"
        "<tr><td>N-PORT</td>"
        "<td><a href='/Archives/edgar/data/1/0009-index.htm'>Documents</a></td>"
        "<td>x</td><td>2020-01-01</td></tr></table>"
        "</div></body></html>"
    ),
    "two-identInfo-paragraphs": _page(
        _NAME + "<p class='identInfo'>State location: NY</p>"
        "<p class='identInfo'>State location: CA</p>", _ROW),
    "unclosed-tags": (
        "<html><body><div id='contentDiv'><div class='companyInfo'>" + _NAME + _IDENT +
        "</div><table class='tableFile2'><tr><th>h<tr><td>N-CSR"
        "<td><a href='/Archives/edgar/data/1/0001-index.htm'>Documents</a>"
        "<td>x<td>2025-03-01</table></div></body></html>"),
}


def _corpus() -> dict:
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(PAGES.glob("*.html"))}


def _cases() -> dict:
    cases = dict(_corpus())
    cases.update({f"EDGE-{k}": v for k, v in EDGE.items()})
    return cases


def _run(html: str):
    """Every field `from_html` produces, in a form JSON can hold.

    Exceptions are captured rather than allowed to propagate: several of these
    pages DO raise today, `direct_get_fund_with_filings` catches broadly, and a
    port must not quietly change which ones.
    """
    from edgar.funds.data import _FundCompanyInfo
    try:
        info = _FundCompanyInfo.from_html(html)
    except Exception as exc:  # noqa: BLE001 -- the exception IS the behaviour
        return f"{type(exc).__name__}: {exc}"
    if info is None:
        return None
    data = info.filings.data
    return {
        "name": info.name,
        "cik": info.cik,
        "ident_info": info.ident_info,
        "addresses": info.addresses,
        "filings": [
            {
                "form": data["form"][i].as_py(),
                "company": data["company"][i].as_py(),
                "cik": data["cik"][i].as_py(),
                "filing_date": str(data["filing_date"][i].as_py()),
                "accession_number": data["accession_number"][i].as_py(),
            }
            for i in range(len(data))
        ],
    }


# The three places the port deliberately changes the answer. The baseline keeps
# bs4's value so it stays a faithful record of what BeautifulSoup did.
DIVERGES_FROM_BS4 = {
    # Same exception, same place, different words: the message names whichever
    # library's method was called on the None. Both of these are precautionary
    # shapes -- a real browse-edgar company page always carries a companyInfo
    # div and a filings table -- and `direct_get_fund_with_filings` catches
    # broadly around them either way, so what matters is that an AttributeError
    # is still what comes out.
    "EDGE-missing-companyInfo": "AttributeError: 'NoneType' object has no attribute 'xpath'",
    "EDGE-missing-filings-table": "AttributeError: 'NoneType' object has no attribute 'xpath'",
    # `html.parser` does not auto-close <td>/<tr>, so it nested the row inside
    # its own first cell and the form name swallowed the cell after it --
    # "N-CSRDocuments" rather than "N-CSR". libxml2 closes them and reads the
    # row the filer wrote. The new answer is the right one, and it is the
    # OPPOSITE direction to edgartools-rck1, where bs4 was the lenient one.
    "EDGE-unclosed-tags": {
        "name": "KINETICS MUTUAL FUNDS INC 0001083387 (see all company filings)",
        "cik": "0001083387",
        "ident_info": {
            "SIC": "0000",
            "State location": "NY",
            "State of Inc.": "MD",
            "Fiscal Year End": "1231",
        },
        "addresses": [],
        "filings": [
            {
                "form": "N-CSR",
                "company": "KINETICS MUTUAL FUNDS INC 0001083387 (see all company filings)",
                "cik": 1083387,
                "filing_date": "2025-03-01",
                "accession_number": "0001",
            }
        ],
    },
}


@pytest.mark.parametrize("name", list(_cases()))
def test_from_html_matches_baseline(name):
    baseline = json.loads(BASELINE.read_text())
    assert name in baseline, f"{name} is missing from the baseline -- recapture it"
    assert _run(_cases()[name]) == DIVERGES_FROM_BS4.get(name, baseline[name])


@pytest.mark.parametrize("name", list(DIVERGES_FROM_BS4))
def test_recorded_divergences_really_diverge(name):
    baseline = json.loads(BASELINE.read_text())
    assert DIVERGES_FROM_BS4[name] != baseline[name]


def test_baseline_covers_every_case():
    assert set(json.loads(BASELINE.read_text())) == set(_cases())


def test_the_corpus_is_still_there():
    assert len(_corpus()) == 6
