import asyncio
import os
from unittest.mock import patch, MagicMock

import httpx
import pytest

from edgar.httprequests import (
    get_with_retry,
    get_with_retry_async,
    stream_with_retry,
    post_with_retry,
    post_with_retry_async,
    TooManyRequestsError,
    IdentityNotSetException,
    download_file,
    download_text_between_tags
)


@pytest.mark.parametrize("status_code", [200, 429])
def test_get_with_retry(status_code, monkeypatch):
    mock_response = httpx.Response(status_code=status_code)

    # Set the Location header for status codes 301 and 302
    if status_code in [301, 302]:
        mock_response.headers["Location"] = "http://example.com/redirected"

    with patch("httpx.Client.get", return_value=mock_response):
        if status_code == 429:
            with pytest.raises(TooManyRequestsError):
                get_with_retry("http://example.com")
        else:
            response = get_with_retry("http://example.com")
            assert response == mock_response


@pytest.mark.parametrize("status_code", [301, 302])
def test_get_with_retry_for_redirect(status_code, monkeypatch):
    mock_response = httpx.Response(status_code=status_code)

    # Set the Location header for status codes 301 and 302
    if status_code in [301, 302]:
        mock_response.headers["Location"] = "http://example.com/redirected"

    with patch("httpx.Client.get", return_value=mock_response):
        with patch("edgar.httprequests.get_with_retry") as mock_retry:
            get_with_retry("http://example.com")
            mock_retry.assert_called_once_with("http://example.com/redirected",
                                               identity=os.environ['EDGAR_IDENTITY'],
                                               headers={'User-Agent': 'Dev Gunning developer-gunning@gmail.com'},
                                               identity_callable=None)


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [200, 429])
async def test_get_with_retry_async(status_code):
    mock_response = httpx.Response(status_code=status_code)
    with patch("httpx.AsyncClient.get", return_value=mock_response):
        if status_code == 429:
            with pytest.raises(TooManyRequestsError):
                await get_with_retry_async("http://example.com")
        elif status_code in [301, 302]:
            with patch("edgar.httprequests.get_with_retry_async") as mock_retry:
                await get_with_retry_async("http://example.com")
                mock_retry.assert_called_once()
        else:
            response = await get_with_retry_async("http://example.com")
            assert response == mock_response


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [301, 302])
async def test_get_with_retry_async_for_redirect(status_code):
    mock_response = httpx.Response(status_code=status_code)

    # Set the Location header for status codes 301 and 302
    if status_code in [301, 302]:
        mock_response.headers["Location"] = "http://example.com/redirected"

    with patch("httpx.Client.get", return_value=mock_response):
        with patch("edgar.httprequests.get_with_retry") as mock_retry:
            get_with_retry("http://example.com")
            mock_retry.assert_called_once_with("http://example.com/redirected",
                                               identity=os.environ['EDGAR_IDENTITY'],
                                               headers={'User-Agent': 'Dev Gunning developer-gunning@gmail.com'},
                                               identity_callable=None)

def test_post_with_retry():
    mock_response = httpx.Response(status_code=200)
    with patch("httpx.Client.post", return_value=mock_response):
        response = post_with_retry("http://example.com", data={"key": "value"})
        assert response == mock_response


@pytest.mark.asyncio
async def test_post_with_retry_async():
    mock_response = httpx.Response(status_code=200)
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        response = await post_with_retry_async("http://example.com", json={"key": "value"})
        assert response == mock_response


def test_identity_not_set_exception(monkeypatch):
    # Remove the EDGAR_IDENTITY environment variable
    monkeypatch.delenv("EDGAR_IDENTITY", raising=False)
    with pytest.raises(IdentityNotSetException):
        get_with_retry("http://example.com")


def test_identity_from_parameter():
    mock_response = httpx.Response(status_code=200)
    with patch("httpx.Client.get", return_value=mock_response) as mock_get:
        get_with_retry("http://example.com", identity="test-identity")
        mock_get.assert_called_once_with("http://example.com", headers={"User-Agent": "test-identity"})


def test_identity_from_callable():
    mock_response = httpx.Response(status_code=200)
    identity_callable = MagicMock(return_value="test-identity")
    with patch("httpx.Client.get", return_value=mock_response) as mock_get:
        get_with_retry("http://example.com", identity_callable=identity_callable)
        mock_get.assert_called_once_with("http://example.com", headers={"User-Agent": "test-identity"})
        identity_callable.assert_called_once()


def test_identity_from_environment_variable(monkeypatch):
    monkeypatch.setenv("EDGAR_IDENTITY", "test-identity")
    mock_response = httpx.Response(status_code=200)
    with patch("httpx.Client.get", return_value=mock_response) as mock_get:
        get_with_retry("http://example.com")
        mock_get.assert_called_once_with("http://example.com", headers={"User-Agent": "test-identity"})


@pytest.mark.asyncio
async def test_get_daily_index_url_async():
    urls = ['https://www.sec.gov/Archives/edgar/daily-index/2024/QTR2/form.20240502.idx',
            'https://www.sec.gov/Archives/edgar/daily-index/2024/QTR2/form.20240502.idx']
    # Use asyncio to run get_with_retry_async
    tasks = [get_with_retry_async(url) for url in urls]
    results = await asyncio.gather(*tasks)
    for r in results:
        assert r.status_code == 200


def test_download_index_file():
    xbrl_gz = download_file('https://www.sec.gov/Archives/edgar/full-index/2021/QTR1/xbrl.gz')
    assert isinstance(xbrl_gz, bytes)
    assert len(xbrl_gz) > 10000

    xbrl_idx = download_file('https://www.sec.gov/Archives/edgar/full-index/2021/QTR1/xbrl.idx')
    assert isinstance(xbrl_idx, str)


def test_get_text_between_tags():
    text = download_text_between_tags(
        'https://www.sec.gov/Archives/edgar/data/1009672/000156459018004771/0001564590-18-004771.txt',
        'SEC-HEADER')
    assert 'ACCESSION NUMBER:		0001564590-18-004771' in text
    assert text.strip().endswith("77079")

