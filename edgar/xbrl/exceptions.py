"""
XBRL-specific exceptions.

`StatementNotFound` is now `StatementNotFoundError` in `edgar.exceptions`
(bead edgartools-07lk.10), under the `NotFoundError` branch. It keeps the same
keyword signature and renders the same message; it is no longer a dataclass,
because a dataclass cannot pass its built message up to the base class.

The old name was a deprecated alias in 5.x and was removed in 6.0.
"""
from edgar.exceptions import StatementNotFoundError

__all__ = ["StatementNotFoundError"]
