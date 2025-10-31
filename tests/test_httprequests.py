import asyncio
import os
from unittest.mock import patch, MagicMock

import httpx
import pytest

from edgar.httpclient import async_http_client, get_edgar_verify_ssl, get_http_mgr

from edgar.httprequests import (
    get_with_retry,
    get_with_retry_async,
    stream_with_retry,
    post_with_retry,
    post_with_retry_async,
    TooManyRequestsError,
    IdentityNotSetException,
    SSLVerificationError,
    is_ssl_error,
    should_retry,
    download_file,
    download_text_between_tags,
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
            get_with_retry(url="http://example.com")
            mock_retry.assert_called_once_with(
                url="http://example.com/redirected",
                identity=os.environ["EDGAR_IDENTITY"],
                headers={"User-Agent": "Dev Gunning developer-gunning@gmail.com"},
                identity_callable=None,
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [200, 429])
async def test_get_with_retry_async(status_code):
    async with async_http_client() as client:
        mock_response = httpx.Response(status_code=status_code)
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            if status_code == 429:
                with pytest.raises(TooManyRequestsError):
                    await get_with_retry_async(client=client, url="http://example.com")
            elif status_code in [301, 302]:
                with patch("edgar.httprequests.get_with_retry_async") as mock_retry:
                    await get_with_retry_async(client=client, url="http://example.com")
                    mock_retry.assert_called_once()
            else:
                response = await get_with_retry_async(client=client, url="http://example.com")
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
            get_with_retry(url="http://example.com")
            mock_retry.assert_called_once_with(
                url="http://example.com/redirected",
                identity=os.environ["EDGAR_IDENTITY"],
                headers={"User-Agent": "Dev Gunning developer-gunning@gmail.com"},
                identity_callable=None,
            )


def test_post_with_retry():
    mock_response = httpx.Response(status_code=200)
    with patch("httpx.Client.post", return_value=mock_response):
        response = post_with_retry(url="http://example.com", data={"key": "value"})
        assert response == mock_response


@pytest.mark.asyncio
async def test_post_with_retry_async():
    async with async_http_client() as client:
        mock_response = httpx.Response(status_code=200)
        with patch("httpx.AsyncClient.post", return_value=mock_response):
            response = await post_with_retry_async(client=client, url="http://example.com", json={"key": "value"})
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
    async with async_http_client() as client:
        urls = [
            "https://www.sec.gov/Archives/edgar/daily-index/2024/QTR2/form.20240502.idx",
            "https://www.sec.gov/Archives/edgar/daily-index/2024/QTR2/form.20240502.idx",
        ]
        # Use asyncio to run get_with_retry_async
        tasks = [get_with_retry_async(client=client, url=url) for url in urls]
        results = await asyncio.gather(*tasks)
        for r in results:
            assert r.status_code == 200


def test_download_index_file():
    xbrl_gz = download_file("https://www.sec.gov/Archives/edgar/full-index/2021/QTR1/xbrl.gz")
    assert isinstance(xbrl_gz, bytes)
    assert len(xbrl_gz) > 10000

    xbrl_idx = download_file("https://www.sec.gov/Archives/edgar/full-index/2021/QTR1/xbrl.idx")
    assert isinstance(xbrl_idx, str)


def test_get_text_between_tags():
    text = download_text_between_tags("https://www.sec.gov/Archives/edgar/data/1009672/000156459018004771/0001564590-18-004771.txt", "SEC-HEADER")
    assert "ACCESSION NUMBER:		0001564590-18-004771" in text
    assert text.strip().endswith("77079")


def test_edgar_verify_ssl(monkeypatch):
    # True when env variable doesn't exist
    monkeypatch.delenv("EDGAR_VERIFY_SSL", raising=False)
    assert get_edgar_verify_ssl()

    # True when env variable set to true
    monkeypatch.setenv("EDGAR_VERIFY_SSL", "true")
    assert get_edgar_verify_ssl()

    # True when env variable set to undefined value
    monkeypatch.setenv("EDGAR_VERIFY_SSL", "unknown")
    assert not get_edgar_verify_ssl()

    # False when env variable set to false
    monkeypatch.setenv("EDGAR_VERIFY_SSL", "false")
    assert not get_edgar_verify_ssl()

    monkeypatch.setenv("EDGAR_VERIFY_SSL", "0")
    assert not get_edgar_verify_ssl()

    monkeypatch.setenv("EDGAR_VERIFY_SSL", "off")
    assert not get_edgar_verify_ssl()


def test_ssl_verification_applied_to_http_manager(monkeypatch):
    """Test that get_edgar_verify_ssl() is actually called and its value is used"""
    # Test default behavior (SSL verification enabled)
    monkeypatch.delenv("EDGAR_VERIFY_SSL", raising=False)
    http_mgr = get_http_mgr()
    assert http_mgr.httpx_params["verify"] is True
    assert isinstance(http_mgr.httpx_params["verify"], bool), "verify should be a boolean, not a function"

    # Test with SSL verification disabled
    monkeypatch.setenv("EDGAR_VERIFY_SSL", "false")
    http_mgr = get_http_mgr()
    assert http_mgr.httpx_params["verify"] is False
    assert isinstance(http_mgr.httpx_params["verify"], bool), "verify should be a boolean, not a function"

    # Test with SSL verification explicitly enabled
    monkeypatch.setenv("EDGAR_VERIFY_SSL", "true")
    http_mgr = get_http_mgr()
    assert http_mgr.httpx_params["verify"] is True
    assert isinstance(http_mgr.httpx_params["verify"], bool), "verify should be a boolean, not a function"


def test_is_ssl_error_detection():
    """Test SSL error detection logic"""
    import ssl

    # Create mock SSL error wrapped in ConnectError
    ssl_error = ssl.SSLCertVerificationError("certificate verify failed")
    connect_error = httpx.ConnectError("SSL error")
    connect_error.__cause__ = ssl_error

    assert is_ssl_error(connect_error)

    # Test non-SSL ConnectError
    non_ssl_error = httpx.ConnectError("Connection refused")
    assert not is_ssl_error(non_ssl_error)

    # Test error message based detection
    ssl_msg_error = httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED]")
    assert is_ssl_error(ssl_msg_error)


def test_ssl_error_message_enhancement(monkeypatch):
    """Test that SSL errors are caught and enhanced with helpful message"""
    import ssl

    ssl_error = ssl.SSLCertVerificationError("self signed certificate")

    with patch("httpx.Client.get") as mock_get:
        # Make it raise ConnectError wrapping SSL error
        connect_err = httpx.ConnectError("SSL error")
        connect_err.__cause__ = ssl_error
        mock_get.side_effect = connect_err

        with pytest.raises(SSLVerificationError) as exc_info:
            get_with_retry("https://www.sec.gov")

        # Verify helpful message is present
        error_msg = str(exc_info.value)
        assert "EDGAR_VERIFY_SSL" in error_msg
        assert "export EDGAR_VERIFY_SSL" in error_msg
        assert "WARNING" in error_msg
        assert "https://www.sec.gov" in error_msg
        assert "Corporate network" in error_msg or "Self-signed certificates" in error_msg


def test_post_with_retry_ssl_error():
    """Test that POST requests catch SSL errors"""
    import ssl

    ssl_error = ssl.SSLCertVerificationError("certificate verify failed")

    with patch("httpx.Client.post") as mock_post:
        connect_err = httpx.ConnectError("SSL error")
        connect_err.__cause__ = ssl_error
        mock_post.side_effect = connect_err

        with pytest.raises(SSLVerificationError) as exc_info:
            post_with_retry("https://www.sec.gov", data={"key": "value"})

        error_msg = str(exc_info.value)
        assert "EDGAR_VERIFY_SSL" in error_msg
        assert "WARNING" in error_msg


@pytest.mark.asyncio
async def test_post_with_retry_async_ssl_error():
    """Test that async POST requests catch SSL errors"""
    import ssl

    ssl_error = ssl.SSLCertVerificationError("certificate verify failed")

    async with async_http_client() as client:
        with patch("httpx.AsyncClient.post") as mock_post:
            connect_err = httpx.ConnectError("SSL error")
            connect_err.__cause__ = ssl_error
            mock_post.side_effect = connect_err

            with pytest.raises(SSLVerificationError) as exc_info:
                await post_with_retry_async(client=client, url="https://www.sec.gov", data={"key": "value"})

            error_msg = str(exc_info.value)
            assert "EDGAR_VERIFY_SSL" in error_msg
            assert "WARNING" in error_msg


def test_httpcore_network_error_ssl_detection():
    """Test that httpcore.NetworkError wrapping SSL is detected"""
    import ssl
    import httpcore

    ssl_error = ssl.SSLError("SSL handshake failed")
    network_error = httpcore.NetworkError()
    network_error.__cause__ = ssl_error

    assert is_ssl_error(network_error)


def test_should_retry_predicate_ssl_errors():
    """Test that should_retry returns False for SSL errors"""
    import ssl

    # Create SSL error wrapped in ConnectError
    ssl_error = ssl.SSLCertVerificationError("certificate verify failed")
    connect_err = httpx.ConnectError("SSL error")
    connect_err.__cause__ = ssl_error

    # should_retry should return False for SSL errors
    assert not should_retry(connect_err)

    # should_retry should return True for non-SSL ConnectError
    non_ssl_err = httpx.ConnectError("Connection refused")
    assert should_retry(non_ssl_err)
