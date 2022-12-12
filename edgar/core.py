from functools import lru_cache
import httpx
import gzip
from io import BytesIO
import os


__all__ = [
    'get_edgar_identity',
    'set_edgar_identity',
    'http_client',
    'download_text',
    'download_file',
    'decode_content'
]

default_http_timeout: int = 5
limits = httpx.Limits(max_connections=10)
edgar_identity = 'EDGAR_IDENTITY'


def set_edgar_identity(name: str, email: str):
    os.environ[edgar_identity] = f"{name} {email}"


def get_edgar_identity():
    identity = os.environ.get(edgar_identity)
    return identity


@lru_cache(maxsize=1)
def client_headers():
    return {'User-Agent': get_edgar_identity()}


def http_client():
    return httpx.Client(headers=client_headers(),
                        timeout=default_http_timeout,
                        limits=limits)


def decode_content(content: bytes):
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        return content.decode('latin-1')


def download_file(url: str,
                  client: httpx.Client | httpx.AsyncClient = None,
                  text: bool = None):
    # reason_phrase = 'Too Many Requests' status_code = 429
    if not client:
        client = http_client()
    r = client.get(url)
    if r.status_code == 200:
        if url.endswith("gz"):
            binary_file = BytesIO(r.content)
            with gzip.open(binary_file, 'rb') as f:
                file_content = f.read()
                if text:
                    return decode_content(file_content)
                return file_content
        else:
            if text or r.encoding == 'utf-8':
                return r.text
            return r.content
    else:
        r.raise_for_status()


def download_text(url: str, client: httpx.Client | httpx.AsyncClient = None):
    return download_file(url, client, text=True)
