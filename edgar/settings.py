"""Connection settings and SEC identity for edgartools.

This is the canonical home for everything a user is *told* to configure: the
identity functions the SEC requires you to set, and the local data directory.

The access modes (:data:`NORMAL`, :data:`CAUTION`, :data:`CRAWL`) still live here
but are deprecated and have no effect - see GH #1326 and the block below.

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
import warnings
from _thread import interrupt_main
from dataclasses import dataclass
from pathlib import Path

import httpx
from rich.prompt import Prompt

log = logging.getLogger(__name__)

__all__ = [
    'CAUTION',  # noqa: F822 -- served by the module __getattr__ (deprecated, GH #1326)
    'CRAWL',  # noqa: F822 -- served by the module __getattr__ (deprecated, GH #1326)
    'NORMAL',  # noqa: F822 -- served by the module __getattr__ (deprecated, GH #1326)
    'EdgarSettings',
    'ask_for_identity',
    'default_http_timeout',
    'default_max_connections',
    'default_page_size',
    'default_retries',
    'edgar_access_mode',  # noqa: F822 -- served by the module __getattr__ (deprecated, GH #1326)
    'edgar_data_dir',
    'edgar_identity',
    'edgar_mode',  # noqa: F822 -- served by the module __getattr__ (deprecated, GH #1326)
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

    def __eq__(self, othr):
        return (isinstance(othr, type(self))
                and (self.http_timeout, self.max_connections, self.retries) ==
                (othr.http_timeout, othr.max_connections, othr.retries))

    def __hash__(self):
        return hash((self.http_timeout, self.max_connections, self.retries))


# Modes of accessing edgar -- DEPRECATED, removed in 6.0 (GH #1326).
#
# The modes advertised a timeout / connection-limit / retry policy that was never
# wired into the HTTP client, so selecting one has never changed how edgartools
# talks to SEC. What actually protects you is EDGAR_RATE_LIMIT_PER_SEC, with
# EDGAR_HTTP_TIMEOUT for the request timeout; both work today.
#
# The objects stay module-level singletons built once, so `mode is NORMAL` and
# identity across the edgar / edgar.core / edgar.settings paths keep holding.
# They are resolved through the module __getattr__ below purely so that reaching
# for one raises a DeprecationWarning at the point of use.

_NORMAL = EdgarSettings(http_timeout=15, max_connections=10)
_CAUTION = EdgarSettings(http_timeout=20, max_connections=5)
_CRAWL = EdgarSettings(http_timeout=25, max_connections=2, retries=2)

_edgar_access_mode = os.getenv('EDGAR_ACCESS_MODE', 'NORMAL')
if _edgar_access_mode == 'CAUTION':
    _edgar_mode = _CAUTION
elif _edgar_access_mode == 'CRAWL':
    _edgar_mode = _CRAWL
else:
    _edgar_mode = _NORMAL

DEPRECATED_ACCESS_MODE_NAMES: dict = {
    'NORMAL': _NORMAL,
    'CAUTION': _CAUTION,
    'CRAWL': _CRAWL,
    'edgar_mode': _edgar_mode,
    'edgar_access_mode': _edgar_access_mode,
}

ACCESS_MODE_DEPRECATION_MESSAGE = (
    "{name} is deprecated and has no effect; it will be removed in edgartools 6.0. "
    "The access modes advertise a timeout, connection limit and retry policy that "
    "was never wired into the HTTP client, so selecting a mode has never changed "
    "how edgartools talks to SEC. Set EDGAR_RATE_LIMIT_PER_SEC to stay within SEC "
    "rate limits, and EDGAR_HTTP_TIMEOUT to set the request timeout."
)


def warn_access_mode_deprecated(name: str, stacklevel: int = 3) -> None:
    """Raise the deprecation for `name`, from the caller's frame."""
    warnings.warn(
        ACCESS_MODE_DEPRECATION_MESSAGE.format(name=name),
        DeprecationWarning,
        stacklevel=stacklevel,
    )


def __getattr__(name: str):
    """PEP 562 hook: serve the deprecated access modes, loudly.

    Only the names in DEPRECATED_ACCESS_MODE_NAMES route through here; everything
    else in this module is a normal module global and never reaches __getattr__.
    """
    if name in DEPRECATED_ACCESS_MODE_NAMES:
        warn_access_mode_deprecated(name)
        return DEPRECATED_ACCESS_MODE_NAMES[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(DEPRECATED_ACCESS_MODE_NAMES))


# Setting the env var is an explicit, deliberate act, so it earns a warning at
# import rather than waiting for someone to read one of the names back.
if os.getenv('EDGAR_ACCESS_MODE') is not None:
    warn_access_mode_deprecated('EDGAR_ACCESS_MODE', stacklevel=2)

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
