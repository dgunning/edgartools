import gzip
import logging
import os
import shutil
import tarfile
import tempfile
import uuid
import zipfile
from functools import wraps
from io import BytesIO
from pathlib import Path
from typing import Optional, Union

import httpcore
import orjson as json
from httpx import AsyncClient, ConnectError, HTTPError, ReadTimeout, RequestError, Response, Timeout, TimeoutException
from stamina import retry
from tqdm import tqdm

from edgar.core import get_edgar_data_directory, text_extensions
from edgar.httpclient import async_http_client, http_client

"""
This module provides functions to handle HTTP requests with retry logic, throttling, and identity management.
"""
__all__ = [
    "get_with_retry",
    "get_with_retry_async",
    "stream_with_retry",
    "post_with_retry",
    "post_with_retry_async",
    "download_file",
    "download_file_async",
    "download_json",
    "download_json_async",
    "stream_file",
    "download_text",
    "download_text_between_tags",
    "download_bulk_data",
    "download_datafile",
    "decompress_gzip_with_retry",
    "SSLVerificationError",
]

attempts = 6

max_requests_per_second = 8
throttle_disabled = False
TIMEOUT = Timeout(30.0, connect=10.0)
RETRY_WAIT_INITIAL = 1  # Initial retry delay (seconds)
RETRY_WAIT_MAX = 60  # Max retry delay (seconds)

# Quick API requests - fail fast for responsive UX
QUICK_RETRY_ATTEMPTS = 5
QUICK_WAIT_MAX = 16  # max 16s delay

# Bulk downloads - very persistent for large files
BULK_RETRY_ATTEMPTS = 8
BULK_RETRY_TIMEOUT = None  # unlimited
BULK_WAIT_MAX = 120  # max 2min delay

# SSL errors - retry once in case of transient issues, then fail with helpful message
SSL_RETRY_ATTEMPTS = 2  # 1 retry = 2 total attempts
SSL_WAIT_MAX = 5  # Short delay for SSL retries

# Exception types to retry on - includes both httpx and httpcore exceptions
RETRYABLE_EXCEPTIONS = (
    # HTTPX exceptions
    RequestError, HTTPError, TimeoutException, ConnectError, ReadTimeout,
    # HTTPCORE exceptions that can slip through
    httpcore.ReadTimeout, httpcore.WriteTimeout, httpcore.ConnectTimeout,
    httpcore.PoolTimeout, httpcore.ConnectError, httpcore.NetworkError,
    httpcore.TimeoutException,
    # Gzip decompression exceptions - can occur with corrupted downloads
    EOFError, gzip.BadGzipFile
)


def is_ssl_error(exc: Exception) -> bool:
    """
    Detect if exception is SSL certificate verification related.

    Checks both the exception chain for SSL errors and error messages
    for SSL-related keywords.
    """
    import ssl

    # Check if any httpx/httpcore exception wraps an SSL error
    if isinstance(exc, (ConnectError, httpcore.ConnectError,
                       httpcore.NetworkError, httpcore.ProxyError)):
        cause = exc.__cause__
        while cause:
            if isinstance(cause, ssl.SSLError):
                return True
            cause = cause.__cause__

    # Check error message for SSL indicators
    error_msg = str(exc).lower()
    ssl_indicators = ['ssl', 'certificate', 'verify failed', 'certificate_verify_failed']
    return any(indicator in error_msg for indicator in ssl_indicators)


def should_retry(exc: Exception) -> bool:
    """
    Determine if an exception should be retried.

    SSL errors are not retried because they are deterministic failures
    that won't succeed on retry. All other retryable exceptions are retried.

    Args:
        exc: The exception to check

    Returns:
        True if the exception should be retried, False otherwise
    """
    # Don't retry SSL errors - fail fast with helpful message
    if isinstance(exc, (ConnectError, httpcore.ConnectError)):
        if is_ssl_error(exc):
            return False

    # Retry all other exceptions in the retryable list
    return isinstance(exc, RETRYABLE_EXCEPTIONS)


class TooManyRequestsError(Exception):
    def __init__(self, url, message="Too Many Requests"):
        self.url = url
        self.message = message
        super().__init__(self.message)


class IdentityNotSetException(Exception):
    pass


class SSLVerificationError(Exception):
    """Raised when SSL certificate verification fails"""
    def __init__(self, original_error, url):
        self.original_error = original_error
        self.url = url
        message = f"""
SSL Certificate Verification Failed
====================================

URL: {self.url}
Error: {str(self.original_error)}

Common Causes:
  • Corporate network with SSL inspection proxy
  • Self-signed certificates in development environments
  • Custom certificate authorities

Solution:
---------
If you trust this network, disable SSL verification:

  export EDGAR_VERIFY_SSL="false"

Or in Python:

  import os
  os.environ['EDGAR_VERIFY_SSL'] = 'false'
  from edgar import Company  # Import after setting

⚠️  WARNING: Only disable in trusted environments.
    This makes connections vulnerable to attacks.

Alternative Solutions:
---------------------
  • Install your organization's root CA certificate
  • Contact IT for proper certificate configuration
  • Use a network without SSL inspection

For details: https://github.com/dgunning/edgartools/blob/main/docs/guides/ssl_verification.md
"""
        super().__init__(message)


def is_redirect(response):
    return response.status_code in [301, 302]


def with_identity(func):
    @wraps(func)
    def wrapper(url, identity=None, identity_callable=None, *args, **kwargs):
        if identity is None:
            if identity_callable is not None:
                identity = identity_callable()
            else:
                identity = os.environ.get("EDGAR_IDENTITY")
        if identity is None:
            raise IdentityNotSetException("User-Agent identity is not set")

        headers = kwargs.get("headers", {})
        headers["User-Agent"] = identity
        kwargs["headers"] = headers

        return func(url, identity=identity, identity_callable=identity_callable, *args, **kwargs)

    return wrapper


def async_with_identity(func):
    @wraps(func)
    def wrapper(client, url, identity=None, identity_callable=None, *args, **kwargs):
        if identity is None:
            if identity_callable is not None:
                identity = identity_callable()
            else:
                identity = os.environ.get("EDGAR_IDENTITY")
        if identity is None:
            raise IdentityNotSetException("User-Agent identity is not set")

        headers = kwargs.get("headers", {})
        headers["User-Agent"] = identity
        kwargs["headers"] = headers

        return func(client, url, identity=identity, identity_callable=identity_callable, *args, **kwargs)

    return wrapper


@retry(
    on=should_retry,
    attempts=QUICK_RETRY_ATTEMPTS,
    wait_initial=RETRY_WAIT_INITIAL,
    wait_max=QUICK_WAIT_MAX,
    wait_jitter=0.5,
    wait_exp_base=2
)
@with_identity
def get_with_retry(url, identity=None, identity_callable=None, **kwargs):
    """
    Sends a GET request with retry functionality and identity handling.

    Args:
        url (str): The URL to send the GET request to.
        identity (str, optional): The identity to use for the request. Defaults to None.
        identity_callable (callable, optional): A callable that returns the identity. Defaults to None.
        **kwargs: Additional keyword arguments to pass to the underlying httpx.Client.get() method.

    Returns:
        httpx.Response: The response object returned by the GET request.

    Raises:
        TooManyRequestsError: If the response status code is 429 (Too Many Requests).
        SSLVerificationError: If SSL certificate verification fails.
    """
    try:
        with http_client() as client:
            response = client.get(url, **kwargs)
            if response.status_code == 429:
                raise TooManyRequestsError(url)
            elif is_redirect(response):
                return get_with_retry(url=response.headers["Location"], identity=identity, identity_callable=identity_callable, **kwargs)
            return response
    except ConnectError as e:
        if is_ssl_error(e):
            raise SSLVerificationError(e, url) from e
        raise


@retry(
    on=should_retry,
    attempts=QUICK_RETRY_ATTEMPTS,
    wait_initial=RETRY_WAIT_INITIAL,
    wait_max=QUICK_WAIT_MAX,
    wait_jitter=0.5,
    wait_exp_base=2
)
@async_with_identity
async def get_with_retry_async(client: AsyncClient, url, identity=None, identity_callable=None, **kwargs):
    """
    Sends an asynchronous GET request with retry functionality and identity handling.

    Args:
        url (str): The URL to send the GET request to.
        identity (str, optional): The identity to use for the request. Defaults to None.
        identity_callable (callable, optional): A callable that returns the identity. Defaults to None.
        **kwargs: Additional keyword arguments to pass to the underlying httpx.AsyncClient.get() method.

    Returns:
        httpx.Response: The response object returned by the GET request.

    Raises:
        TooManyRequestsError: If the response status code is 429 (Too Many Requests).
        SSLVerificationError: If SSL certificate verification fails.
    """
    try:
        response = await client.get(url, **kwargs)
        if response.status_code == 429:
            raise TooManyRequestsError(url)
        elif is_redirect(response):
            return await get_with_retry_async(
                client=client, url=response.headers["Location"], identity=identity, identity_callable=identity_callable, **kwargs
            )
        return response
    except ConnectError as e:
        if is_ssl_error(e):
            raise SSLVerificationError(e, url) from e
        raise


@retry(
    on=should_retry,
    attempts=BULK_RETRY_ATTEMPTS,
    timeout=BULK_RETRY_TIMEOUT,
    wait_initial=RETRY_WAIT_INITIAL,
    wait_max=BULK_WAIT_MAX,
    wait_jitter=0.5,
    wait_exp_base=2
)
@with_identity
def stream_with_retry(url, identity=None, identity_callable=None, **kwargs):
    """
    Sends a streaming GET request with retry functionality and identity handling.

    Args:
        url (str): The URL to send the streaming GET request to.
        identity (str, optional): The identity to use for the request. Defaults to None.
        identity_callable (callable, optional): A callable that returns the identity. Defaults to None.
        **kwargs: Additional keyword arguments to pass to the underlying httpx.Client.stream() method.

    Yields:
        bytes: The bytes of the response content.

    Raises:
        TooManyRequestsError: If the response status code is 429 (Too Many Requests).
        SSLVerificationError: If SSL certificate verification fails.
    """
    try:
        with http_client() as client:
            with client.stream("GET", url, **kwargs) as response:
                if response.status_code == 429:
                    raise TooManyRequestsError(url)
                elif is_redirect(response):
                    response = stream_with_retry(response.headers["Location"], identity=identity, identity_callable=identity_callable, **kwargs)
                    yield from response
                else:
                    yield response
    except ConnectError as e:
        if is_ssl_error(e):
            raise SSLVerificationError(e, url) from e
        raise


@retry(
    on=should_retry,
    attempts=QUICK_RETRY_ATTEMPTS,
    wait_initial=RETRY_WAIT_INITIAL,
    wait_max=QUICK_WAIT_MAX,
    wait_jitter=0.5,
    wait_exp_base=2
)
@with_identity
def post_with_retry(url, data=None, json=None, identity=None, identity_callable=None, **kwargs):
    """
    Sends a POST request with retry functionality and identity handling.

    Args:
        url (str): The URL to send the POST request to.
        data (dict, optional): The data to include in the request body. Defaults to None.
        json (dict, optional): The JSON data to include in the request body. Defaults to None.
        identity (str, optional): The identity to use for the request. Defaults to None.
        identity_callable (callable, optional): A callable that returns the identity. Defaults to None.
        **kwargs: Additional keyword arguments to pass to the underlying httpx.Client.post() method.

    Returns:
        httpx.Response: The response object returned by the POST request.

    Raises:
        TooManyRequestsError: If the response status code is 429 (Too Many Requests).
        SSLVerificationError: If SSL certificate verification fails.
    """
    try:
        with http_client() as client:
            response = client.post(url, data=data, json=json, **kwargs)
            if response.status_code == 429:
                raise TooManyRequestsError(url)
            elif is_redirect(response):
                return post_with_retry(
                    response.headers["Location"], data=data, json=json, identity=identity, identity_callable=identity_callable, **kwargs
                )
            return response
    except ConnectError as e:
        if is_ssl_error(e):
            raise SSLVerificationError(e, url) from e
        raise


@retry(
    on=should_retry,
    attempts=QUICK_RETRY_ATTEMPTS,
    wait_initial=RETRY_WAIT_INITIAL,
    wait_max=QUICK_WAIT_MAX,
    wait_jitter=0.5,
    wait_exp_base=2
)
@async_with_identity
async def post_with_retry_async(client: AsyncClient, url, data=None, json=None, identity=None, identity_callable=None, **kwargs):
    """
    Sends an asynchronous POST request with retry functionality and identity handling.

    Args:
        url (str): The URL to send the POST request to.
        data (dict, optional): The data to include in the request body. Defaults to None.
        json (dict, optional): The JSON data to include in the request body. Defaults to None.
        identity (str, optional): The identity to use for the request. Defaults to None.
        identity_callable (callable, optional): A callable that returns the identity. Defaults to None.
        **kwargs: Additional keyword arguments to pass to the underlying httpx.AsyncClient.post() method.

    Returns:
        httpx.Response: The response object returned by the POST request.

    Raises:
        TooManyRequestsError: If the response status code is 429 (Too Many Requests).
        SSLVerificationError: If SSL certificate verification fails.
    """
    try:
        response = await client.post(url, data=data, json=json, **kwargs)
        if response.status_code == 429:
            raise TooManyRequestsError(url)
        elif is_redirect(response):
            return await post_with_retry_async(
                client, response.headers["Location"], data=data, json=json, identity=identity, identity_callable=identity_callable, **kwargs
            )
        return response
    except ConnectError as e:
        if is_ssl_error(e):
            raise SSLVerificationError(e, url) from e
        raise


def inspect_response(response: Response):
    """
    Check if the response is successful and raise an exception if not.
    """
    if response.status_code != 200:
        response.raise_for_status()


def decode_content(content: bytes) -> str:
    """
    Decode the content of a file.
    """
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1")


@retry(
    on=should_retry,
    attempts=QUICK_RETRY_ATTEMPTS,
    wait_initial=RETRY_WAIT_INITIAL,
    wait_max=QUICK_WAIT_MAX,
    wait_jitter=0.5,
    wait_exp_base=2
)
def decompress_gzip_with_retry(url: str, as_text: bool) -> Union[str, bytes]:
    """
    Download and decompress a gzip file with retry logic.

    This handles cases where SEC serves corrupted gzip files that result in
    EOFError or BadGzipFile exceptions during decompression.

    Args:
        url: The URL of the gzip file to download
        as_text: Whether to return the content as text or bytes

    Returns:
        The decompressed content as text or bytes

    Raises:
        EOFError: If gzip decompression fails after all retries
        gzip.BadGzipFile: If the gzip file is invalid after all retries
    """
    # Download the file
    response = get_with_retry(url=url)
    inspect_response(response)

    # Validate content-length if available
    content_length = response.headers.get("Content-Length")
    actual_size = len(response.content)
    if content_length and int(content_length) != actual_size:
        logger.warning(
            "Content-Length mismatch for %s: expected %s, got %s",
            url, content_length, actual_size
        )

    # Decompress the gzip content
    binary_file = BytesIO(response.content)
    with gzip.open(binary_file, "rb") as f:
        file_content = f.read()
        if as_text:
            file_content = decode_content(file_content)

    return file_content


def save_or_return_content(content: Union[str, bytes], path: Optional[Union[str, Path]]) -> Union[str, bytes, None]:
    """
    Save the content to a specified path or return the content.

    Args:
        content (str or bytes): The content to save or return.
        path (str or Path, optional): The path where the content should be saved. If None, return the content.

    Returns:
        str or bytes or None: The content if not saved, or None if saved.
    """
    if path is not None:
        path = Path(path)

        # Determine if the path is a directory or a file
        if path.is_dir():
            file_name = "downloaded_file"  # Replace with logic to extract file name from URL if available
            file_path = path / file_name
        else:
            file_path = path

        # Save the file
        if isinstance(content, bytes):
            file_path.write_bytes(content)
        else:
            file_path.write_text(content)

        return None

    return content


def download_file(url: str, as_text: bool = None, path: Optional[Union[str, Path]] = None) -> Union[str, bytes, None]:
    """
    Download a file from a URL.

    Args:
        url (str): The URL of the file to download.
        as_text (bool, optional): Whether to download the file as text or binary.
        path (str or Path, optional): The path where the file should be saved.
        If None, the default is determined based on the file extension. Defaults to None.

    Returns:
        str or bytes: The content of the downloaded file, either as text or binary data.
    """
    if as_text is None:
        # Set the default based on the file extension
        as_text = url.endswith(text_extensions)

    if not as_text:
        # Set the default to true if the url ends with a text extension
        as_text = any([url.endswith(ext) for ext in text_extensions])

    # Check if the content is gzip-compressed
    if url.endswith("gz"):
        # Use retry-enabled decompression for gzip files
        file_content = decompress_gzip_with_retry(url, as_text)
    else:
        response = get_with_retry(url=url)
        inspect_response(response)
        # If we explicitly asked for text or there is an encoding, try to return text
        if as_text:
            file_content = response.text
            # Should get here for jpg and PDFs
        else:
            file_content = response.content

    path = Path(path) if path else None
    if path and path.is_dir():
        path = path / os.path.basename(url)
    return save_or_return_content(file_content, path)


async def download_file_async(
    client: AsyncClient, url: str, as_text: bool = None, path: Optional[Union[str, Path]] = None
) -> Union[str, bytes, None]:
    """
    Download a file from a URL asynchronously.

    Args:
        url (str): The URL of the file to download.
        as_text (bool, optional): Whether to download the file as text or binary.
            If None, the default is determined based on the file extension. Defaults to None.
        path (str or Path, optional): The path where the file should be saved.

    Returns:
        str or bytes: The content of the downloaded file, either as text or binary data.
    """
    if as_text is None:
        # Set the default based on the file extension
        as_text = url.endswith(text_extensions)

    response = await get_with_retry_async(client, url)
    inspect_response(response)

    if as_text:
        # Download as text
        return response.text
    else:
        # Download as binary
        content = response.content

        # Check if the content is gzip-compressed
        if response.headers.get("Content-Encoding") == "gzip":
            content = gzip.decompress(content)

    if path and path.is_dir():
        path = path / os.path.basename(url)

    return save_or_return_content(content, path)


CHUNK_SIZE = 4 * 1024 * 1024  # 4MB
CHUNK_SIZE_LARGE = 8 * 1024 * 1024  # 8MB for files > 500MB
CHUNK_SIZE_MEDIUM = 4 * 1024 * 1024  # 4MB for files > 100MB
CHUNK_SIZE_SMALL = 2 * 1024 * 1024  # 2MB for files <= 100MB
CHUNK_SIZE_DEFAULT = CHUNK_SIZE


@retry(
    on=should_retry,
    attempts=BULK_RETRY_ATTEMPTS,
    timeout=BULK_RETRY_TIMEOUT,
    wait_initial=RETRY_WAIT_INITIAL,
    wait_max=BULK_WAIT_MAX,
    wait_jitter=0.5,  # Add jitter to avoid synchronized retries
    wait_exp_base=2  # Exponential backoff (doubles delay each retry)
)
@with_identity
async def stream_file(
    url: str, as_text: bool = None, path: Optional[Union[str, Path]] = None, client: Optional[AsyncClient] = None, **kwargs
) -> Union[str, bytes, None]:
    """
    Download a file from a URL asynchronously with progress bar using httpx.

    Args:
        url (str): The URL of the file to download.
        as_text (bool, optional): Whether to download the file as text or binary.
            If None, the default is determined based on the file extension. Defaults to None.
        path (str or Path, optional): The path where the file should be saved.
        client: The httpx.AsyncClient instance

    Returns:
        str or bytes: The content of the downloaded file, either as text or binary data.
    """
    if as_text is None:
        # Set the default based on the file extension
        as_text = url.endswith(text_extensions)

    # Create temporary directory for atomic downloads
    temp_dir = tempfile.mkdtemp(prefix="edgar_")
    temp_file = Path(temp_dir) / f"download_{uuid.uuid1()}"

    try:
        async with async_http_client(client, timeout=TIMEOUT, bypass_cache=True) as async_client:
            async with async_client.stream("GET", url) as response:
                inspect_response(response)
                total_size = int(response.headers.get("Content-Length", 0))

                if as_text:
                    # Download as text
                    content = await response.text()
                    return content
                else:
                    # Download as binary - select optimal chunk size first
                    if total_size > 0:
                        if total_size > 500 * 1024 * 1024:  # > 500MB
                            chunk_size = CHUNK_SIZE_LARGE
                        elif total_size > 100 * 1024 * 1024:  # > 100MB
                            chunk_size = CHUNK_SIZE_MEDIUM
                        else:  # <= 100MB
                            chunk_size = CHUNK_SIZE_SMALL
                    else:
                        # Unknown size, use default
                        chunk_size = CHUNK_SIZE_DEFAULT

                    progress_bar = tqdm(
                        total=total_size / (1024 * 1024),
                        unit="MB",
                        unit_scale=True,
                        unit_divisor=1024,
                        leave=False,  # Force horizontal display
                        position=0,  # Lock the position
                        dynamic_ncols=True,  # Adapt to terminal width
                        bar_format="{l_bar}{bar}| {n:.2f}/{total:.2f}MB [{elapsed}<{remaining}, {rate_fmt}]",
                        desc=f"Downloading {os.path.basename(url)}",
                        ascii=False,
                    )

                    # Always stream to temporary file
                    try:
                        with open(temp_file, "wb") as f:
                            # For large files, update progress less frequently to reduce overhead
                            update_threshold = 1.0 if total_size > 500 * 1024 * 1024 else 0.1  # MB
                            accumulated_mb = 0.0

                            async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                                f.write(chunk)
                                chunk_mb = len(chunk) / (1024 * 1024)
                                accumulated_mb += chunk_mb

                                # Update progress bar only when threshold is reached
                                if accumulated_mb >= update_threshold:
                                    progress_bar.update(accumulated_mb)
                                    accumulated_mb = 0.0

                            # Update any remaining progress
                            if accumulated_mb > 0:
                                progress_bar.update(accumulated_mb)

                    finally:
                        progress_bar.close()

                # Handle the result based on whether path was provided
                if path is not None:
                    # Atomic move to final destination
                    final_path = Path(path)
                    if final_path.is_dir():
                        final_path = final_path / os.path.basename(url)

                    # Ensure parent directory exists
                    final_path.parent.mkdir(parents=True, exist_ok=True)

                    # Atomic move from temp to final location
                    shutil.move(str(temp_file), str(final_path))
                    return None
                else:
                    with open(temp_file, 'rb') as f:
                        content = f.read()
                    return content

    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning("Failed to clean up temporary directory %s: %s", temp_dir, e)


def download_json(data_url: str) -> dict:
    """
    Download JSON data from a URL.

    Args:
        data_url (str): The URL of the JSON data to download.

    Returns:
        dict: The parsed JSON data.
    """
    content = download_file(data_url, as_text=True)
    return json.loads(content)


def download_text(url: str) -> Optional[str]:
    return download_file(url, as_text=True)


async def download_json_async(client: AsyncClient, data_url: str) -> dict:
    """
    Download JSON data from a URL asynchronously.

    Args:
        data_url (str): The URL of the JSON data to download.

    Returns:
        dict: The parsed JSON data.
    """
    content = await download_file_async(client=client, url=data_url, as_text=True)
    return json.loads(content)


def download_text_between_tags(url: str, tag: str):
    """
    Download the content of a URL and extract the text between the tags
    This is mainly for reading the header of a filing

    :param url: The URL to download
    :param tag: The tag to extract the content from

    """
    tag_start = f"<{tag}>"
    tag_end = f"</{tag}>"
    is_header = False
    content = ""

    for response in stream_with_retry(url):
        for line in response.iter_lines():
            if line:
                # If line matches header_start, start capturing
                if line.startswith(tag_start):
                    is_header = True
                    continue  # Skip the current line as it's the opening tag

                # If line matches header_end, stop capturing
                elif line.startswith(tag_end):
                    break

                # If within header lines, add to header_content
                elif is_header:
                    content += line + "\n"  # Add a newline to preserve original line breaks
    return content


logger = logging.getLogger(__name__)


@retry(
    on=should_retry,
    attempts=BULK_RETRY_ATTEMPTS,
    timeout=BULK_RETRY_TIMEOUT,
    wait_initial=RETRY_WAIT_INITIAL,
    wait_max=BULK_WAIT_MAX,
    wait_jitter=0.5,
    wait_exp_base=2
)
async def download_bulk_data(
        url: str,
        data_directory: Optional[Path] = None,
        client: Optional[AsyncClient] = None,
) -> Path:
    """
    Download and extract bulk data from zip or tar.gz archives

    Args:
        client: The httpx.AsyncClient instance
        url: URL to download from (e.g. "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip")
        data_directory: Base directory for downloads

    Returns:
        Path to the directory containing the extracted data

    Raises:
        ValueError: If the URL or filename is invalid
        IOError: If there are file system operation failures
        zipfile.BadZipFile: If the downloaded zip file is corrupted
        tarfile.TarError: If the downloaded tar.gz file is corrupted
    """
    if not url:
        raise ValueError("Data URL cannot be empty")

    # Get the data directory if not provided
    if data_directory is None:
        data_directory = get_edgar_data_directory()

    filename = os.path.basename(url)
    if not filename:
        raise ValueError("Invalid URL - cannot extract filename")

    local_dir = filename.split(".")[0]
    download_path = data_directory / local_dir
    download_filename = download_path / filename

    try:
        # Create the directory with parents=True and exist_ok=True to avoid race conditions
        download_path.mkdir(parents=True, exist_ok=True)

        # Download the file
        try:
            await stream_file(url, client=client, path=download_path)
        except Exception as e:
            raise IOError(f"Failed to download file: {e}") from e

        # Extract based on file extension
        try:
            if filename.endswith(".zip"):
                with zipfile.ZipFile(download_filename, "r") as z:
                    # Calculate total size for progress bar
                    total_size = sum(info.file_size for info in z.filelist)
                    extracted_size = 0

                    with tqdm(total=total_size, unit="B", unit_scale=True, desc="Extracting") as pbar:
                        for info in z.filelist:
                            z.extract(info, download_path)
                            extracted_size += info.file_size
                            pbar.update(info.file_size)

            elif any(filename.endswith(ext) for ext in (".tar.gz", ".tgz")):
                with tarfile.open(download_filename, "r:gz") as tar:
                    # Security check for tar files to prevent path traversal
                    def is_within_directory(directory: Path, target: Path) -> bool:
                        try:
                            return os.path.commonpath([directory, target]) == str(directory)
                        except ValueError:
                            return False

                    members = tar.getmembers()
                    total_size = sum(member.size for member in members)

                    with tqdm(total=total_size, unit="B", unit_scale=True, desc="Extracting") as pbar:
                        for member in members:
                            # Check for path traversal
                            member_path = os.path.join(str(download_path), member.name)
                            if not is_within_directory(Path(str(download_path)), Path(member_path)):
                                raise ValueError(f"Attempted path traversal in tar file: {member.name}")

                            # Extract file and update progress
                            try:
                                tar.extract(member, str(download_path), filter="tar")
                            except TypeError:
                                tar.extract(member, str(download_path))
                            pbar.update(member.size)
            else:
                raise ValueError(f"Unsupported file format: {filename}")

        except (zipfile.BadZipFile, tarfile.TarError) as e:
            raise type(e)(f"Failed to extract archive {filename}: {e}") from e

        finally:
            # Always try to clean up the archive file, but don't fail if we can't
            try:
                if download_filename.exists():
                    download_filename.unlink()
            except Exception as e:
                logger.warning("Failed to delete archive file %s: %s", download_filename, e)

        return download_path

    except Exception:
        # Clean up the download directory in case of any errors
        try:
            if download_path.exists():
                shutil.rmtree(download_path)
        except Exception as cleanup_error:
            logger.error("Failed to clean up after error: %s", cleanup_error)
        raise


def download_datafile(data_url: str, local_directory: Path = None) -> Path:
    """Download a file to the local storage directory"""
    filename = os.path.basename(data_url)
    # Create the directory if it doesn't exist
    local_directory = local_directory or get_edgar_data_directory()
    if not local_directory.exists():
        local_directory.mkdir()

    download_filename = local_directory / filename
    download_file(data_url, path=download_filename)
    return download_filename
