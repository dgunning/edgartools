"""Connection settings and SEC identity for edgartools.

This is the canonical home for everything a user is *told* to configure: the
access modes (:data:`NORMAL`, :data:`CAUTION`, :data:`CRAWL`), the identity
functions the SEC requires you to set, and the local data directory.

Historically all of this lived in ``edgar.core`` alongside quarter math, HTML
sniffing, a pager, thread helpers and the logger — only about a third of that
697-line module was settings. ``edgar.core`` still re-exports every name here so
existing imports keep working; that shim is removed in 6.0 (edgartools-07lk.12.1).

    from edgar.settings import get_identity, set_identity   # preferred
    from edgar.core import get_identity, set_identity       # works, removed in 6.0

Most users never import this module at all — :func:`set_identity` and the access
modes are re-exported on the top-level ``edgar`` namespace.
"""
import logging
import os
import threading
from _thread import interrupt_main
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import httpx
from rich.prompt import Prompt

log = logging.getLogger(__name__)

__all__ = [
    'CAUTION',
    'CRAWL',
    'NORMAL',
    'EdgarSettings',
    'ask_for_identity',
    'default_http_timeout',
    'default_max_connections',
    'default_page_size',
    'default_retries',
    'edgar_access_mode',
    'edgar_data_dir',
    'edgar_identity',
    'edgar_mode',
    'get_edgar_data_directory',
    'get_identity',
    'identity_prompt',
    'limits',
    'set_identity',
]

default_http_timeout: int = 12
default_page_size = 50
default_max_connections = 10
default_retries = 3

limits = httpx.Limits(max_connections=default_max_connections)


@dataclass
class EdgarSettings:
    http_timeout: int
    max_connections: int
    retries: int = 3

    @cached_property
    def limits(self):
        return httpx.Limits(max_connections=default_max_connections)

    def __eq__(self, othr):
        return (isinstance(othr, type(self))
                and (self.http_timeout, self.max_connections, self.retries) ==
                (othr.http_timeout, othr.max_connections, othr.retries))

    def __hash__(self):
        return hash((self.http_timeout, self.max_connections, self.retries))


# Modes of accessing edgar

# The normal mode of accessing edgar
NORMAL = EdgarSettings(http_timeout=15, max_connections=10)

# A bit more cautious mode of accessing edgar
CAUTION = EdgarSettings(http_timeout=20, max_connections=5)

# Use this setting when you have long-running jobs and want to avoid breaching Edgar limits
CRAWL = EdgarSettings(http_timeout=25, max_connections=2, retries=2)

edgar_access_mode = os.getenv('EDGAR_ACCESS_MODE', 'NORMAL')
if edgar_access_mode == 'CAUTION':
    # A bit more cautious mode of accessing edgar
    edgar_mode = CAUTION
elif edgar_access_mode == 'CRAWL':
    # Use this setting when you have long-running jobs and want to avoid breaching Edgar limits
    edgar_mode = CRAWL
else:
    # The normal mode of accessing edgar
    edgar_mode = NORMAL

edgar_identity = 'EDGAR_IDENTITY'

# Local storage directory - use centralized path configuration
from edgar.paths import get_data_directory as _get_data_directory  # noqa: E402

edgar_data_dir = str(_get_data_directory(create=False))


def set_identity(user_identity: str):
    """
    This function sets the environment variable EDGAR_IDENTITY to the identity you will use to call Edgar

    This user identity looks like

        "Sample Company Name AdminContact@<sample company domain>.com"

    See https://www.sec.gov/os/accessing-edgar-data

    :param user_identity:
    """
    os.environ[edgar_identity] = user_identity
    log.info("Identity of the Edgar REST client set to [%s]", user_identity)

    from edgar.httpclient import close_clients
    close_clients() # close any httpx clients, to reset the identity.


identity_prompt = """
[bold turquoise4]Identify your client to SEC Edgar[/bold turquoise4]
------------------------------------------------------------------------------

Before running [bold]edgartools[/bold] it needs to know the UserAgent string to send to Edgar.
See https://www.sec.gov/os/accessing-edgar-data

This can be set in the environment variable [bold green]EDGAR_IDENTITY[/bold green].

1. Set an OS environment variable
    [bold]EDGAR_IDENTITY=[green]Name email@domain.com[/green][/bold]
2. Or a Python environment variable
    import os
    [bold]os.environ['EDGAR_IDENTITY']=[green]"Name email@domain.com"[/green][/bold]
3. Or use [bold magenta]edgartools.set_identity[/bold magenta]
    from edgar import set_identity
    [bold]set_identity([green]'Name email@domain.com'[/green])[/bold]

But since you are already using [bold]edgartools[/bold] you can set it here

Enter your [bold green]EDGAR_IDENTITY[/bold green] e.g. [bold italic green]Name email@domain.com[/bold italic green]
"""


def ask_for_identity(user_prompt: str = identity_prompt,
                     timeout: int = 60):
    timer = threading.Timer(timeout, interrupt_main)
    timer.start()

    try:
        # Prompt the user for input
        input_str = Prompt.ask(user_prompt)

        # Strip the newline character from the end of the input string
        input_str = input_str.strip()
    except KeyboardInterrupt:
        # If the timeout is reached, raise a TimeoutError exception
        message = "You did not enter your Edgar user identity. Try again .. or set environment variable EDGAR_IDENTITY"
        log.warning(message)
        raise TimeoutError(message) from None
    finally:
        # Cancel the timer to prevent it from interrupting the main thread
        timer.cancel()

    return input_str


def get_identity() -> str:
    """
    Get the sec identity used to set the UserAgent string
    :return:
    """
    identity = os.environ.get(edgar_identity)
    if not identity:
        identity = ask_for_identity()
        os.environ[edgar_identity] = identity
    return identity


def get_edgar_data_directory() -> Path:
    """Get the edgar data directory.

    The directory can be customized via the EDGAR_LOCAL_DATA_DIR environment
    variable or by using edgar.paths.set_data_directory().

    Returns:
        Path to the Edgar data directory. Creates it if it doesn't exist.
    """
    from edgar.paths import get_data_directory
    return get_data_directory(create=True)
