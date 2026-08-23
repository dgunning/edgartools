"""Characterization of the four small bs4 -> lxml ports (edgartools-07lk.11.10).

`lxml_cold_ports_baseline.json` is what these four files produced over the
repo's existing real fixtures, captured while they still ran on BeautifulSoup:

    edgar/company_reports/subsidiaries.py   3 EX-21 exhibits, 153 subsidiaries
    edgar/forms.py                          the SEC forms listing page
    edgar/storage/_local.py                 a real SEC feed directory listing
    edgar/company_reports/forty_f.py        plain-text extraction

Each file has only incidental bs4 use, so these are small ports in large files
-- but "small" is where a silent translation error hides best, since nobody
looks twice.

WHAT THE FIXTURES DO *NOT* COVER. Mutating each translated line showed 3 of 6
were exercised:

    subsidiaries  text_content() -> .text            CAUGHT
    _local        text_content() -> .text            CAUGHT
    forms         descendant-or-self -> .//          CAUGHT (raises)
    subsidiaries  descendant-or-self -> .//          not caught
    _local        descendant-or-self -> .//          not caught
    forms         text_content() -> .text            not caught

The tests after the golden-file section cover the other three.

The `descendant-or-self` axis is not defensive padding: it is a bug this port
hit. `lxml.html.fromstring` roots a document trimmed to a single <table> AT
that table, so `.//table` -- a descendant-only search -- finds nothing, while
bs4's `find("table")` matched it either way. The committed
`tests/fixtures/forms/sec_forms_page0.html` is exactly such a trimmed fragment,
which is how it was caught.
"""
import json
import pathlib
from unittest.mock import patch

import pytest

import edgar.storage._local as local_storage
from edgar.company_reports.forty_f import _html_to_text
from edgar.company_reports.subsidiaries import parse_subsidiaries
from edgar.forms import list_forms

pytestmark = pytest.mark.fast

REPO = pathlib.Path(__file__).parent.parent
FIX = REPO / "tests" / "fixtures"
BASELINE = FIX / "lxml_cold_ports_baseline.json"
EX21 = sorted(FIX.glob("ex21_*.html"))
FORMS_PAGE = FIX / "forms" / "sec_forms_page0.html"
LISTING = FIX / "sec_feed_directory_qtr1_2024.html"


@pytest.fixture(scope="module")
def baseline():
    return json.loads(BASELINE.read_text())


# ------------------------------------------------------------- golden file


@pytest.mark.parametrize("path", EX21, ids=lambda p: p.stem)
def test_subsidiaries_match_the_bs4_baseline(path, baseline):
    subs = parse_subsidiaries(path.read_text())
    got = [{"name": s.name, "jurisdiction": s.jurisdiction,
            "ownership": getattr(s, "ownership", None)} for s in subs]
    assert got == baseline[f"subsidiaries::{path.name}"]


def test_the_subsidiary_baseline_is_not_vacuous(baseline):
    """An extractor that found nothing would match a baseline of empty lists."""
    total = sum(len(v) for k, v in baseline.items() if k.startswith("subsidiaries::"))
    assert total == 153


def test_the_forms_listing_matches_the_bs4_baseline(baseline):
    with patch("edgar.forms.download_file", return_value=FORMS_PAGE.read_text()):
        list_forms.cache_clear()
        try:
            forms = list_forms()
            data = forms.data if hasattr(forms, "data") else forms
            assert len(data) == baseline["forms::rowcount"]
            assert data.head(40).to_dict(orient="records") == baseline["forms::page0"]
        finally:
            list_forms.cache_clear()


def test_the_directory_listing_matches_the_bs4_baseline(baseline):
    with patch("edgar.storage._local.download_text", return_value=LISTING.read_text()):
        df = local_storage.get_sec_file_listing("https://example/feed/")
    got = [{"Name": r.Name, "File": r.File, "Size": r.Size, "Modified": str(r.Modified)}
           for r in df.itertuples()]
    assert got == baseline["listing::records"]


@pytest.mark.parametrize("path", EX21, ids=lambda p: p.stem)
def test_plain_text_extraction_matches_the_bs4_baseline(path, baseline):
    assert _html_to_text(path.read_text()) == baseline["fortyf::text"][path.name]


# -------------------------------------------------------- the uncovered half


BARE_TABLE = (
    '<table><tr><th>Subsidiary</th><th>Jurisdiction</th></tr>'
    '<tr><td>Widget Holdings LLC</td><td>Delaware</td></tr>'
    '<tr><td>Widget Europe GmbH</td><td>Germany</td></tr></table>'
)


def test_an_exhibit_that_is_only_a_table_is_still_parsed():
    """`fromstring` roots this document AT the <table>, so a descendant-only
    `.//table` search returns nothing and the exhibit parses to zero
    subsidiaries. bs4's find_all('table') matched the root table."""
    subs = parse_subsidiaries(BARE_TABLE)
    assert [s.name for s in subs] == ["Widget Holdings LLC", "Widget Europe GmbH"]
    assert [s.jurisdiction for s in subs] == ["Delaware", "Germany"]


def test_a_listing_that_is_only_a_table_is_still_parsed():
    """Same axis, same failure: 'No table found in the page' on a page that
    plainly has one."""
    html = ('<table><tr><th>Name</th><th>Size</th><th>Modified</th></tr>'
            '<tr><td>20240102.nc.tar.gz</td><td>1.2K</td>'
            '<td>01/02/2024 10:30:00 PM</td></tr></table>')
    with patch("edgar.storage._local.download_text", return_value=html):
        df = local_storage.get_sec_file_listing("https://example/feed/")
    assert list(df["Name"]) == ["20240102.nc.tar.gz"]


def test_a_forms_cell_split_across_elements_keeps_every_word():
    """lxml's `.text` is a node's own leading text only; bs4's `.text` was every
    descendant's. A cell whose value sits in child elements loses everything but
    the first fragment -- and the SEC forms table wraps cell values in <a> and
    <span>, so `.text` would return '' for the ones that do."""
    html = ('<table><tbody>'
            '<tr><td><span>Number:</span><span>10-K</span></td>'
            '<td><a href="/f.html">Annual</a> report</td>'
            '<td>Last Updated: 2026</td><td>SEC Number: 001</td>'
            '<td>Topic(s): Reporting</td></tr>'
            '</tbody></table>')
    with patch("edgar.forms.download_file", return_value=html):
        list_forms.cache_clear()
        try:
            data = list_forms().data
        finally:
            list_forms.cache_clear()
    assert data.iloc[0]["Form"] == "10-K"
    assert data.iloc[0]["Description"] == "Annual report"
    assert data.iloc[0]["Url"].endswith("/f.html")


def test_plain_text_keeps_the_padding_bs4_kept():
    """`get_text()` with no arguments strips nothing and inserts nothing, which
    is `text_content()`. `get_text(strip=True)` is a different function and
    would run the words together."""
    assert _html_to_text('<p>Alpha </p><p>Beta</p>') == "Alpha Beta"


@pytest.mark.parametrize("content", ["", "   \n\t "])
def test_empty_input_keeps_its_old_answer_rather_than_raising(content):
    """bs4 built an empty soup for blank input; lxml raises ParserError. Each
    caller maps it back to whatever it produced before -- `parse_subsidiaries`
    already had a test for this, the other two did not."""
    assert parse_subsidiaries(content) == []
    assert _html_to_text(content) == ""
    with patch("edgar.storage._local.download_text", return_value=content):
        with pytest.raises(RuntimeError, match="No table found"):
            local_storage.get_sec_file_listing("https://example/feed/")


def test_html_is_accepted_as_bytes_as_well_as_str():
    """`download_file` hands the forms page back as BYTES. bs4 took either;
    encoding a bytes object raises AttributeError, which is how this was
    caught -- the characterization harness patched the download with a str and
    sailed straight past it."""
    html = b'<table><tbody><tr><td>10-K</td><td>Annual</td><td>2026</td>' \
           b'<td>001</td><td>Reporting</td></tr></tbody></table>'
    with patch("edgar.forms.download_file", return_value=html):
        list_forms.cache_clear()
        try:
            assert list_forms().data.iloc[0]["Form"] == "10-K"
        finally:
            list_forms.cache_clear()
