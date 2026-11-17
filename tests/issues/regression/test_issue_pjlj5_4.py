"""Regression: fund lookups by class or series ID send a page size SEC accepts.

Bead: edgartools-pjlj5.4

Since 2026-11-16 SEC's browse-edgar accepts `count` only from {10, 20, ..., 100, 500}
and answers anything else with HTTP 400 "Invalid count, Received: 1". The class and
series resolver asked for count=1, logged the 400 as a warning and returned None, so
Fund("C000032628") and Fund("S000002277") returned None. It now asks for count=10, and
a refused request raises instead of reading as "no such fund".
"""
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from edgar.exceptions import TransportError
from edgar.funds import data

pytestmark = pytest.mark.fast

PAGES = Path(__file__).resolve().parents[2] / "fixtures" / "funds" / "browse_edgar_pjlj5_4"
ACCEPTED_COUNTS = {"10", "20", "30", "40", "50", "60", "70", "80", "90", "100", "500"}


def _serve(monkeypatch, identifier):
    requested = []

    def download_text(url):
        requested.append(url)
        return (PAGES / f"{identifier}.html").read_text(encoding="utf-8")

    monkeypatch.setattr(data, "download_text", download_text)
    return requested


@pytest.mark.parametrize(("identifier", "cik", "name"), [
    ("C000032628", "0001040587", "DIREXION FUNDS"),
    ("S000002277", "0000774556", "VAN KAMPEN TAX FREE TRUST"),
])
def test_resolver_asks_for_a_count_sec_accepts(monkeypatch, identifier, cik, name):
    requested = _serve(monkeypatch, identifier)
    assert data._resolve_company_cik(identifier) == (cik, name)
    [url] = requested
    query = parse_qs(urlparse(url).query)
    assert query["CIK"] == [identifier]
    assert query["count"][0] in ACCEPTED_COUNTS


def test_a_refused_request_raises_rather_than_reading_as_not_found(monkeypatch):
    def refused(url):
        raise TransportError("HTTP 400 from browse-edgar", url=url, status_code=400)

    monkeypatch.setattr(data, "download_text", refused)
    with pytest.raises(TransportError) as raised:
        data._resolve_company_cik("C000032628")
    assert raised.value.status_code == 400
