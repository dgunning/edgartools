import gzip
import logging.config
import os
from functools import lru_cache
from io import BytesIO
from typing import Union

import httpx
from rich.logging import RichHandler

logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)

log = logging.getLogger("rich")

__all__ = [
    'get_identity',
    'set_identity',
    'http_client',
    'download_text',
    'download_file',
    'decode_content',
    'repr_df',
    'log'
]

default_http_timeout: int = 5
limits = httpx.Limits(max_connections=10)
edgar_identity = 'EDGAR_IDENTITY'


def set_identity(user_identity: str):
    """
    This function sets the environment variable EDGAR_IDENTITY to the identity you will use to call Edgar

    This user identity looks like

        "Sample Company Name AdminContact@<sample company domain>.com"

    See https://www.sec.gov/os/accessing-edgar-data

    :param user_identity:
    """
    os.environ[edgar_identity] = user_identity
    log.info(f"Identity of the Edgar REST client set to [{user_identity}]")


def get_identity():
    identity = os.environ.get(edgar_identity)
    assert identity, """
    Environment variable EDGAR_IDENTITY not found.
    
    Set environent variable `EDGAR_IDENTITY` to a string used to identify you to the SEC edgar service
    
    example
        EDGAR_IDENTITY=First Name name@email.com
    """
    return identity


@lru_cache(maxsize=1)
def client_headers():
    return {'User-Agent': get_identity()}


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
                  client: Union[httpx.Client, httpx.AsyncClient] = None,
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


def download_text(url: str, client: Union[httpx.Client, httpx.AsyncClient] = None):
    return download_file(url, client, text=True)


def repr_df(df, hide_index: bool = True):
    disp = df.style
    if hide_index:
        disp = disp.hide(axis="index")
    return disp._repr_html_()
