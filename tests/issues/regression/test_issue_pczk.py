"""
Regression test for edgartools-pczk (GH #794 side note): expose
``edgar.__version__`` at the package root.

Before this fix, ``import edgar; edgar.__version__`` raised AttributeError
because the version lived only in ``edgar/__about__.py`` and was never
re-exported from ``edgar/__init__.py``. Downstream consumers couldn't
programmatically detect which version they had installed, which is a
near-universal Python convention (``pkg.__version__``).

Fix: re-export ``__version__`` from ``edgar/__init__.py``.
"""
import re

import edgar
import edgar.__about__


def test_version_exported_at_package_root():
    """``edgar.__version__`` is accessible (no AttributeError)."""
    assert hasattr(edgar, "__version__"), (
        "edgar.__version__ is not exported at the package root"
    )
    assert isinstance(edgar.__version__, str)
    assert edgar.__version__  # non-empty


def test_version_matches_canonical_source():
    """The re-exported value is the single source of truth in __about__.py."""
    assert edgar.__version__ == edgar.__about__.__version__


def test_version_is_pep440_like():
    """Version is a sane dotted release string (e.g. '5.34.0')."""
    assert re.match(r"^\d+\.\d+", edgar.__version__), (
        f"Unexpected version format: {edgar.__version__!r}"
    )
