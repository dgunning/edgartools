"""Coverage for `edgar.forms.list_forms()` and `SecForms`, ahead of the lxml port.

`list_forms()` scrapes seven pages of https://www.sec.gov/forms and is the only
description of what each SEC form *is*. It had no direct coverage: bead
edgartools-07lk.11.1 calls that out as a silent-regression risk, because
`edgar/forms.py` parses with BeautifulSoup and Phase 1 of edgartools-07lk.11 replaces
that with lxml. It is not an `xmltools` dependent — it parses HTML, not XML — so its
port is independent of edgartools-07lk.11.2, but the failure mode is the same: a
scraper that quietly returns fewer rows, or empty strings, still returns a DataFrame.

Two fixtures, deliberately:

  * `sec_forms_page0.html` is the real table as SEC served it on 2026-08-18, trimmed
    to the `<table>` element. It pins what the parser must do against real markup.
  * `LABELLED_TABLE` below is synthetic, and pins the defensive branches the live
    page no longer exercises — the `"Number:"`/`"Description:"` label prefixes from
    SEC's older responsive layout, and a row whose description carries no link.

No network: `download_file` is patched, which is also what keeps `list_forms`'s
`lru_cache` honest — it is cleared around every test here.
"""
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from edgar.config import SEC_BASE_URL
from edgar.forms import SecForm, SecForms, list_forms

FIXTURES = Path(__file__).parent / "fixtures" / "forms"
PAGE_0 = (FIXTURES / "sec_forms_page0.html").read_bytes()

# A page with a well-formed but empty table, standing in for pages 1-6.
EMPTY_PAGE = b"<html><body><table><thead><tr><th>Number</th></tr></thead><tbody></tbody></table></body></html>"

# The older responsive markup, where each cell repeated its column label inline,
# plus a description with no anchor. Neither shape appears on the live page today.
LABELLED_TABLE = b"""<html><body><table>
  <thead><tr><th>Number</th><th>Description</th><th>Last Updated</th><th>SEC Number</th><th>Topic(s)</th></tr></thead>
  <tbody>
    <tr>
      <td>Number: 10-K</td>
      <td>Description: <a href="/files/form10-k.pdf">Annual Report (PDF)</a></td>
      <td>Last Updated: Sept. 2024</td>
      <td>SEC Number: SEC1234</td>
      <td>Topic(s): Exchange Act Reporting</td>
    </tr>
    <tr>
      <td>  UNLINKED  </td>
      <td>  A form with no link  </td>
      <td>  Jan. 2020  </td>
      <td>  SEC9999  </td>
      <td>  Other Forms  </td>
    </tr>
  </tbody>
</table></body></html>"""


def _serve(page_0: bytes = PAGE_0, others: bytes = EMPTY_PAGE):
    """Answer the seven page fetches, recording the URLs asked for."""
    requested = []

    def download(url, *args, **kwargs):
        requested.append(url)
        return page_0 if url.endswith("page=0") else others

    download.requested = requested
    return download


@pytest.fixture(autouse=True)
def _clear_form_cache():
    """`list_forms` is `lru_cache(maxsize=1)`; a warm entry would leak between tests."""
    list_forms.cache_clear()
    yield
    list_forms.cache_clear()


@pytest.fixture
def forms():
    download = _serve()
    with patch("edgar.forms.download_file", download):
        yield list_forms()


# ------------------------------------------------------------------ scraping


def test_list_forms_fetches_all_seven_pages():
    download = _serve()
    with patch("edgar.forms.download_file", download):
        list_forms()

    assert download.requested == [f"https://www.sec.gov/forms?page={page}" for page in range(7)]


def test_list_forms_parses_every_body_row_and_no_header_row(forms):
    """25 rows on page 0, and the `<thead>` row is not one of them."""
    assert len(forms) == 25
    assert "Number" not in set(forms.data.Form)


def test_list_forms_declares_its_columns(forms):
    assert list(forms.data.columns) == [
        "Form",
        "Description",
        "Url",
        "LastUpdated",
        "SECNumber",
        "Topics",
    ]


def test_list_forms_reads_a_row_end_to_end(forms):
    """Ground truth: Form 1-A as SEC served it on 2026-08-18."""
    row = forms.data[forms.data.Form == "1-A"]
    assert len(row) == 1
    assert row.Description.item() == "Regulation A Offering Statement (PDF)"
    assert row.Url.item() == "https://www.sec.gov/files/form1a.pdf"
    assert row.LastUpdated.item() == "Feb. 2025"
    assert row.SECNumber.item() == "SEC486"
    assert row.Topics.item() == "Securities Act of 1933, Small Businesses"


def test_list_forms_takes_the_description_text_from_inside_the_link(forms):
    """The description lives in an `<a>` inside the cell, so cell text extraction has
    to reach into child elements — the axis a naive lxml `.text` port gets wrong."""
    assert forms.data[forms.data.Form == "1-A"].Description.item() == "Regulation A Offering Statement (PDF)"
    assert not forms.data.Description.str.strip().eq("").any()


def test_list_forms_builds_absolute_urls_from_relative_hrefs(forms):
    urls = forms.data.Url[forms.data.Url != ""]
    assert len(urls) > 0
    assert urls.str.startswith(f"{SEC_BASE_URL}/").all()
    assert not urls.str.contains(f"{SEC_BASE_URL}{SEC_BASE_URL}").any()


def test_list_forms_keeps_rows_whose_form_number_is_blank(forms):
    """The first two rows of page 0 are brochures with no form number. They are real
    rows with real descriptions, and dropping them would lose them silently."""
    blank = forms.data[forms.data.Form == ""]
    assert len(blank) == 2
    assert "Examination Brochure: Information about Examinations (PDF)" in set(blank.Description)


def test_list_forms_strips_whitespace_from_every_field(forms):
    for column in ("Form", "Description", "LastUpdated", "SECNumber", "Topics"):
        values = forms.data[column]
        assert values.equals(values.str.strip()), f"{column} carries untrimmed whitespace"


def test_list_forms_accepts_bytes_from_download_file():
    """`download_file` returns `bytes` for this URL, not `str`. Pinned because the
    port has to keep accepting bytes — passing them to the wrong lxml entry point
    raises, and passing decoded text to the right one can mangle the encoding."""
    assert isinstance(PAGE_0, bytes)  # what the fixture feeds, matching production
    with patch("edgar.forms.download_file", _serve()):
        assert len(list_forms()) == 25


# -------------------------------------------- defensive branches (synthetic)


@pytest.fixture
def labelled_forms():
    download = _serve(page_0=LABELLED_TABLE)
    with patch("edgar.forms.download_file", download):
        yield list_forms()


def test_inline_column_labels_are_stripped_from_every_cell(labelled_forms):
    """SEC's older responsive layout repeated the column label inside each cell."""
    row = labelled_forms.data.iloc[0]
    assert row.Form == "10-K"
    assert row.Description == "Annual Report (PDF)"
    assert row.LastUpdated == "Sept. 2024"
    assert row.SECNumber == "SEC1234"
    assert row.Topics == "Exchange Act Reporting"


def test_a_description_with_no_link_gets_an_empty_url_not_a_crash(labelled_forms):
    row = labelled_forms.data.iloc[1]
    assert row.Form == "UNLINKED"
    assert row.Description == "A form with no link"
    assert row.Url == ""


# -------------------------------------------------------------- SecForms API


def test_get_form_returns_a_populated_secform(forms):
    form = forms.get_form("1-A")

    assert isinstance(form, SecForm)
    assert form.form == "1-A"
    assert form.description == "Regulation A Offering Statement (PDF)"
    assert form.url == "https://www.sec.gov/files/form1a.pdf"
    assert form.sec_number == "SEC486"
    assert form.topics == "Securities Act of 1933, Small Businesses"
    assert str(form) == "Form 1-A: Regulation A Offering Statement (PDF)"


def test_getitem_is_get_form(forms):
    assert forms["1-A"] == forms.get_form("1-A")


def test_get_form_returns_none_for_an_unknown_form(forms):
    """Current behavior, pinned. This is a silent `None` of the kind edgartools-07lk.10
    commits to replacing with a typed exception in 6.0 — when that lands, this test
    is the one that has to change."""
    assert forms.get_form("NOT-A-FORM") is None


def test_summary_narrows_to_the_readable_columns(forms):
    summary = forms.summary()
    assert list(summary.columns) == ["Form", "Description", "Topics"]
    assert len(summary) == len(forms)


def test_repr_renders_without_error(forms):
    assert "1-A" in repr(forms)


def test_load_returns_usable_forms():
    """Regression for edgartools-07rg: `load()` used to wrap a `SecForms` in another
    `SecForms`, so `.data` was not a DataFrame and `summary()`/`repr()` raised a
    pandas `SyntaxError` that never mentioned forms."""
    with patch("edgar.forms.download_file", _serve()):
        loaded = SecForms.load()

    assert isinstance(loaded.data, pd.DataFrame)
    assert loaded.get_form("1-A").sec_number == "SEC486"
    assert list(loaded.summary().columns) == ["Form", "Description", "Topics"]
    assert "1-A" in repr(loaded)
