"""
Regression test for Issue #856: Missing NullHandler in the edgar package logger.

A well-behaved library should attach a ``logging.NullHandler`` to its
package-root logger so that it never emits log output unless the consuming
application configures logging itself (see the Python logging HOWTO,
"Configuring Logging for a Library"). Without it, edgartools warnings have no
handler in their ancestry and fall back to the ``logging.lastResort`` handler,
which writes to stderr -- especially harmful in MCP / stdio environments where
stray stderr output corrupts the protocol stream.
"""

import logging

import edgar  # noqa: F401  (importing configures the package-root logger)


class TestPackageRootNullHandler:
    def test_edgar_logger_has_null_handler(self):
        """The 'edgar' package-root logger must carry a NullHandler."""
        handlers = logging.getLogger("edgar").handlers
        assert any(isinstance(h, logging.NullHandler) for h in handlers), (
            "edgartools must attach a logging.NullHandler to the 'edgar' logger "
            "so library logging stays silent until the application configures it"
        )

    def test_edgar_logger_adds_only_null_handler(self):
        """The library must not attach handlers other than NullHandler (HOWTO)."""
        handlers = logging.getLogger("edgar").handlers
        assert handlers, "the 'edgar' logger should have a NullHandler attached"
        assert all(isinstance(h, logging.NullHandler) for h in handlers), (
            "a library must not attach handlers other than NullHandler to its "
            "package-root logger; that is the application's responsibility"
        )
