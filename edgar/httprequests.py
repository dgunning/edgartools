import gzip
import os
import time
import zipfile
from collections import deque
from functools import wraps
from io import BytesIO
from pathlib import Path
from threading import Lock
from typing import Union, Optional

import httpx
import orjson as json
from stamina import retry
from tqdm import tqdm

from edgar.core import text_extensions, edgar_mode, get_edgar_data_directory

__all__ = ["get_with_retry", "get_with_retry_async", "stream_with_retry", "post_with_retry", "post_with_retry_async",
           "download_file", "download_file_async", "download_json", "download_json_async", "stream_file",
           "download_text", "download_text_between_tags", "download_bulk_data"]

attempts = 6
retry_timeout = 40
wait_initial = 0.1
max_requests_per_second = 8


class TooManyRequestsError(Exception):
    def __init__(self, url, message="Too Many Requests"):
        self.url = url
        self.message = message
        super().__init__(self.message)


class IdentityNotSetException(Exception):
    pass


class RequestRate:
    """
    A simple class to represent a request rate, i.e., the maximum number of requests for a given time window
    """

    def __init__(self, max_requests: int, time_window: int):
        if max_requests <= 0:
            raise ValueError("max_requests must be a positive integer")
        if time_window <= 0:
            raise ValueError("time_window must be a positive integer")

        self.max_requests: int = max_requests
        self.time_window: int = time_window


class Throttler:
    """
    A simple throttler that limits the number of requests per time window
    """

    def __init__(self, request_rate: RequestRate, sleep_interval=0.1):
        self.request_rate = request_rate
        self.sleep_interval = sleep_interval
        self.request_timestamps = deque()
        self.lock = Lock()
        self.decorated_function = None
        self.total_calls = 0
        self.peak_call_rate: float = 0.0

    def get_ticket(self):
        with self.lock:
            current_time = time.monotonic()

            # Remove timestamps older than the time window
            while self.request_timestamps and self.request_timestamps[
                0] <= current_time - self.request_rate.time_window:
                self.request_timestamps.popleft()

            if len(self.request_timestamps) < self.request_rate.max_requests:
                self.request_timestamps.append(current_time)
                return True
            else:
                return False

    def wait_for_ticket(self):
        while not self.get_ticket():
            time.sleep(self.sleep_interval)

    def update_metrics(self):
        self.total_calls += 1
        current_call_rate: float = len(self.request_timestamps) / self.request_rate.time_window
        self.peak_call_rate = max(self.peak_call_rate, current_call_rate)

    def get_metrics(self):
        return {
            "decorated_function": self.decorated_function,
            "total_calls": self.total_calls,
            "peak_call_rate": self.peak_call_rate,
            "request_rate_limit": self.request_rate.max_requests,  # Include the request_rate limit
        }

    def print_metrics(self):
        metrics = self.get_metrics()
        print(f"Metrics for decorated function: {metrics['decorated_function']}")
        print(f"Total calls: {metrics['total_calls']}")
        print(f"Peak call rate: {metrics['peak_call_rate']:.2f} calls per second")


_throttler_instances = {}


def throttle_requests(request_rate=None, requests_per_second=None, **kwargs):
    if requests_per_second is not None:
        request_rate = RequestRate(max_requests=requests_per_second, time_window=1)
    elif request_rate is None:
        raise ValueError("Either request_rate or requests_per_second must be provided")

    throttler = Throttler(request_rate, **kwargs)

    def decorator(func):
        throttler.decorated_function = func.__name__  # Store the decorated function name

        @wraps(func)
        def wrapper(*args, **kwargs):
            throttler.wait_for_ticket()
            result = func(*args, **kwargs)
            throttler.update_metrics()
            return result

        return wrapper

    return decorator


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


@retry(on=httpx.RequestError, attempts=attempts, timeout=retry_timeout, wait_initial=wait_initial)
@with_identity
@throttle_requests(requests_per_second=max_requests_per_second)
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
    """
    with httpx.Client(timeout=edgar_mode.http_timeout) as client:
        response = client.get(url, **kwargs)
        if response.status_code == 429:
            raise TooManyRequestsError(url)
        elif is_redirect(response):
            return get_with_retry(response.headers["Location"], identity=identity, identity_callable=identity_callable,
                                  **kwargs)
        return response


@retry(on=httpx.RequestError, attempts=attempts, timeout=retry_timeout, wait_initial=wait_initial)
@with_identity
@throttle_requests(requests_per_second=max_requests_per_second)
async def get_with_retry_async(url, identity=None, identity_callable=None, **kwargs):
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
    """
    async with httpx.AsyncClient(timeout=edgar_mode.http_timeout) as client:
        response = await client.get(url, **kwargs)
        if response.status_code == 429:
            raise TooManyRequestsError(url)
        elif is_redirect(response):
            return await get_with_retry_async(response.headers["Location"], identity=identity,
                                              identity_callable=identity_callable, **kwargs)
        return response


@retry(on=httpx.RequestError, attempts=attempts, timeout=retry_timeout, wait_initial=wait_initial)
@with_identity
@throttle_requests(requests_per_second=max_requests_per_second)
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
    """
    with httpx.Client(timeout=edgar_mode.http_timeout) as client:
        with client.stream("GET", url, **kwargs) as response:
            if response.status_code == 429:
                raise TooManyRequestsError(url)
            elif is_redirect(response):
                yield stream_with_retry(response.headers["Location"],
                                        identity=identity,
                                        identity_callable=identity_callable, **kwargs)
            else:
                yield response


@retry(on=httpx.RequestError, attempts=attempts, timeout=retry_timeout, wait_initial=wait_initial)
@with_identity
@throttle_requests(requests_per_second=max_requests_per_second)
def post_with_retry(url, data=None, json=None, identity=None, identity_callable=None,
                    **kwargs):
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
    """
    with httpx.Client(timeout=edgar_mode.http_timeout) as client:
        response = client.post(url, data=data, json=json, **kwargs)
        if response.status_code == 429:
            raise TooManyRequestsError(url)
        elif is_redirect(response):
            return post_with_retry(response.headers["Location"], data=data, json=json, identity=identity,
                                   identity_callable=identity_callable, **kwargs)
        return response


@retry(on=httpx.RequestError, attempts=attempts, timeout=retry_timeout, wait_initial=wait_initial)
@with_identity
@throttle_requests(requests_per_second=max_requests_per_second)
async def post_with_retry_async(url,
                                data=None,
                                json=None,
                                identity=None,
                                identity_callable=None, **kwargs):
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
    """
    async with httpx.AsyncClient(timeout=edgar_mode.http_timeout) as client:
        response = await client.post(url, data=data, json=json, **kwargs)
        if response.status_code == 429:
            raise TooManyRequestsError(url)
        elif is_redirect(response):
            return await post_with_retry_async(response.headers["Location"], data=data, json=json, identity=identity,
                                               identity_callable=identity_callable, **kwargs)
        return response


def inspect_response(response: httpx.Response):
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
        return content.decode('utf-8')
    except UnicodeDecodeError:
        return content.decode('latin-1')


def save_or_return_content(content: Union[str, bytes], path: Optional[Union[str, Path]]) -> Union[
    str, bytes, None]:
    """
    Save the content to a specified path or return the content.

    Args:
        content (str or bytes): The content to save or return.
        path (str or Path, optional): The path where the content should be saved. If None, return the content.
        as_text (bool): Whether the content is text or binary.

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

    response = get_with_retry(url=url)
    inspect_response(response)

    if not as_text:
        # Set the default to true if the url ends with a text extension
        as_text = any([url.endswith(ext) for ext in text_extensions])

    # Check if the content is gzip-compressed
    if url.endswith("gz"):
        binary_file = BytesIO(response.content)
        with gzip.open(binary_file, 'rb') as f:
            file_content = f.read()
            if as_text:
                file_content = decode_content(file_content)
    else:
        # If we explicitly asked for text or there is an encoding, try to return text
        if as_text:
            file_content = response.text
            # Should get here for jpg and PDFs
        else:
            file_content = response.content

    if path and path.is_dir():
        path = path / os.path.basename(url)
    return save_or_return_content(file_content, path)


async def download_file_async(url: str, as_text: bool = None, path: Optional[Union[str, Path]] = None) -> Union[
    str, bytes, None]:
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

    response = await get_with_retry_async(url)
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


@retry(on=httpx.RequestError, attempts=attempts, timeout=retry_timeout, wait_initial=wait_initial)
@with_identity
@throttle_requests(requests_per_second=max_requests_per_second)
async def stream_file(url: str, as_text: bool = None, path: Optional[Union[str, Path]] = None, **kwargs) -> Union[str, bytes, None]:
    """
    Download a file from a URL asynchronously with progress bar using httpx.

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

    async with httpx.AsyncClient(timeout=edgar_mode.http_timeout, headers=kwargs['headers']) as client:
        async with client.stream('GET', url) as response:
            inspect_response(response)
            total_size = int(response.headers.get('Content-Length', 0))

            if as_text:
                # Download as text
                content = await response.text()
                return content
            else:
                # Download as binary
                content = b''
                progress_bar = tqdm(
                    total=total_size / (1024 * 1024),  # Convert to MB
                    unit='MB',
                    unit_scale=True,
                    unit_divisor=1024,
                    bar_format='{l_bar}{bar}| {n:.2f}/{total:.2f}MB [{elapsed}<{remaining}, {rate_fmt}]',
                    desc=f"Downloading {os.path.basename(url)}",
                    ascii=False  # Use Unicode characters for a nicer looking bar
                )
                downloaded = 0
                async for chunk in response.aiter_bytes(chunk_size=CHUNK_SIZE):
                    content += chunk
                    downloaded += len(chunk)
                    progress_bar.update(len(chunk) / (1024 * 1024))  # Update in MB
                progress_bar.close()

                # Check if the content is gzip-compressed
                if response.headers.get("Content-Encoding") == "gzip":
                    content = gzip.decompress(content)

            if path:
                if isinstance(path, str):
                    path = Path(path)
                if path.is_dir():
                    path = path / os.path.basename(url)

            return save_or_return_content(content, path)


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


async def download_json_async(data_url: str) -> dict:
    """
    Download JSON data from a URL asynchronously.

    Args:
        data_url (str): The URL of the JSON data to download.

    Returns:
        dict: The parsed JSON data.
    """
    content = await download_file_async(data_url, as_text=True)
    return json.loads(content)


def download_text_between_tags(url: str, tag: str):
    """
    Download the content of a URL and extract the text between the tags
    This is mainly for reading the header of a filing

    :param url: The URL to download
    :param tag: The tag to extract the content from

    """
    tag_start = f'<{tag}>'
    tag_end = f'</{tag}>'
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
                    content += line + '\n'  # Add a newline to preserve original line breaks
    return content


async def download_bulk_data(data_url:str) -> Path:
    """
    Download bulk data e.g. company facts, daily index, etc. from the SEC website
    e.g. "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"
    """
    filename = os.path.basename(data_url)
    local_dir = filename.split('.')[0]
    download_path = get_edgar_data_directory() / local_dir
    download_filename = download_path / filename

    # Create the directory if it doesn't exist
    if not download_path.exists():
        download_path.mkdir()

    # Now stream the file to the data directory
    await stream_file(data_url, as_text=False, path=download_path)
    if filename.endswith(".zip"):
        # Unzip the file to the data directory / file
        with zipfile.ZipFile(download_filename, 'r') as z:
            z.extractall(download_path)
        # Delete the zip file
        download_filename.unlink()
    return download_path
