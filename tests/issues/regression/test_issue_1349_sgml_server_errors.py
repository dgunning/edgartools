"""A failed SGML download must not cache a homepage-only header.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1349
GitHub Issue: https://github.com/dgunning/edgartools/issues/1351
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import httpcore
import httpx
import pytest

from edgar import Filing
from edgar.attachments import Attachments, FilingHomepage
from edgar.exceptions import TooManyRequestsError, TransportError, http_status
from edgar.httprequests import wrap_transport_errors
from edgar.sgml import sgml_common

pytestmark = pytest.mark.fast


@pytest.fixture(params=[False, True], ids=["legacy", "strict"])
def strict_errors(request, monkeypatch):
    monkeypatch.setenv("EDGARTOOLS_STRICT_ERRORS", "1" if request.param else "0")
    return request.param


@pytest.fixture
def filing(monkeypatch):
    # Exercise the network-source path regardless of the developer's storage settings.
    monkeypatch.setattr("edgar._filings.is_using_local_storage", lambda: False)
    monkeypatch.setattr("edgar.storage.datamule.is_using_datamule_storage", lambda: False)
    return Filing(
        form="10-K",
        company="Apple Inc.",
        cik=320193,
        filing_date="2024-11-01",
        accession_no="0000320193-24-000123",
    )


@pytest.fixture(scope="module")
def submission_text():
    return Path("data/sgml/0000320193-24-000123.txt").read_text(encoding="utf-8")


@pytest.fixture
def homepage(monkeypatch):
    page = Mock(spec=FilingHomepage)
    page.attachments = Mock(spec=Attachments)
    load = Mock(return_value=page)
    monkeypatch.setattr(FilingHomepage, "load", load)
    return load


@pytest.mark.parametrize("accessor", ["sgml", "header"])
@pytest.mark.parametrize("status", [403, 404, 429, 500, 502, 503, 504])
def test_http_error_leaves_filing_retryable(
    filing,
    homepage,
    submission_text,
    strict_errors,
    monkeypatch,
    accessor,
    status,
):
    request = httpx.Request("GET", filing.text_url)
    if status == 429:
        # The streaming boundary raises this domain error in both modes.
        error = TooManyRequestsError(filing.text_url, retry_after=120)
        expected_error = TooManyRequestsError
    else:
        error = httpx.HTTPStatusError(
            "SEC HTTP failure",
            request=request,
            response=httpx.Response(status, request=request),
        )
        expected_error = TransportError if strict_errors else httpx.HTTPStatusError
    read = Mock(side_effect=[error, submission_text])

    @wrap_transport_errors
    def download(source):
        return read(source)

    monkeypatch.setattr(sgml_common, "read_content_as_string", download)

    with pytest.raises(expected_error) as caught:
        if accessor == "header":
            _ = filing.header
        else:
            filing.sgml()

    assert http_status(caught.value) == status
    if strict_errors and status != 429:
        assert caught.value.__cause__ is error
    else:
        assert caught.value is error
    if status == 429:
        assert caught.value.retry_after == 120
    assert filing._sgml is None
    assert "header" not in filing.__dict__
    assert read.call_count == 1
    homepage.assert_not_called()

    # Simulate a later caller retry after resolving the refusal or waiting out the limit.
    header = filing.header
    assert header.accession_number == "0000320193-24-000123"
    assert header.acceptance_datetime == datetime(2024, 11, 1, 6, 1, 36)
    assert header.period_of_report == "2024-09-28"
    assert header.form == "10-K"
    assert filing.sgml().header is header
    assert filing.header is header
    assert read.call_count == 2
    homepage.assert_not_called()


@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.ReadTimeout])
def test_unreachable_error_propagates_in_both_modes(
    filing,
    homepage,
    strict_errors,
    monkeypatch,
    error_type,
):
    error = error_type("SEC unreachable")

    @wrap_transport_errors
    def download(source):
        raise error

    monkeypatch.setattr(sgml_common, "read_content_as_string", download)
    with pytest.raises(TransportError if strict_errors else error_type):
        filing.sgml()
    assert filing._sgml is None
    homepage.assert_not_called()


@pytest.mark.parametrize("error_type", [httpcore.ConnectError, httpcore.ReadTimeout])
def test_httpcore_errors_still_propagate(filing, homepage, monkeypatch, error_type):
    error = error_type("SEC unreachable")
    monkeypatch.setattr(sgml_common, "read_content_as_string", Mock(side_effect=error))
    with pytest.raises(error_type) as caught:
        filing.sgml()
    assert caught.value is error
    assert filing._sgml is None
    homepage.assert_not_called()
