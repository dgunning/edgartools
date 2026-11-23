"""Serve committed SEC browse-edgar pages in place of `edgar.funds.data.download_text`.

The fund series tests for GH #888 and #1143 resolve a series through
browse-edgar's company view (`?CIK=<series id>[&type=<form>]&start=N&count=100`).
These pages are saved verbatim under tests/fixtures/funds/, so the tests run
offline against what SEC actually returned. A request for a page nobody
recorded fails the test instead of reaching the network.
"""
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

FUNDS_FIXTURES = Path(__file__).parent / "fixtures" / "funds"
SERIES_PAGES = FUNDS_FIXTURES / "browse_edgar_series_paging"   # no form filter
FORM_PAGES = FUNDS_FIXTURES / "browse_edgar_series_forms"      # one form per query


def page_path(url: str) -> Path:
    query = parse_qs(urlsplit(url).query)
    cik, start = query["CIK"][0], query["start"][0]
    form = query.get("type", [None])[0]
    if form is None:
        return SERIES_PAGES / f"{cik}-start{start}.html"
    return FORM_PAGES / f"{cik}-{form.replace(' ', '_')}-start{start}.html"


def serve_recorded_pages(requested: list):
    """A `download_text` stand-in that records each URL it is asked for."""

    def _download_text(url, *args, **kwargs):
        requested.append(url)
        path = page_path(url)
        if not path.is_file():
            raise AssertionError(f"no recorded browse-edgar page for {url} (expected {path.name})")
        return path.read_text(encoding="utf-8")

    return _download_text
