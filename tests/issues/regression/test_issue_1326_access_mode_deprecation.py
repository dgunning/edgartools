"""EDGAR_ACCESS_MODE and its modes are removed in 6.0; they never did anything.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1326

`NORMAL`, `CAUTION` and `CRAWL` advertised a timeout / connection-limit / retry
policy that was never wired into the HTTP client, so selecting a mode never
changed how edgartools talks to SEC. 5.x deprecated them; 6.0 removes them.

What is pinned here:

1. **Every name is gone from every path** (`edgar`, `edgar.core`,
   `edgar.settings`), as plain absence: `from edgar import CAUTION` is an
   ImportError and attribute access an AttributeError.
2. **`EDGAR_ACCESS_MODE` is not read and does not warn.** Leaving it set in an
   old environment must be harmless.
3. **The module-level `limits` object is untouched**: it is a different name.
"""
import os
import subprocess
import sys

import pytest

import edgar
import edgar.core
import edgar.settings

MODE_NAMES = ["NORMAL", "CAUTION", "CRAWL", "edgar_mode", "edgar_access_mode"]


def _run(code: str, **env_overrides) -> subprocess.CompletedProcess:
    env = {**os.environ, **env_overrides}
    return subprocess.run(  # noqa: S603 -- sys.executable with a literal argv, no shell
        [sys.executable, "-W", "error::DeprecationWarning", "-c", code],
        capture_output=True, text=True, timeout=180, env=env,
    )


@pytest.mark.parametrize("module", [edgar, edgar.core, edgar.settings])
@pytest.mark.parametrize("name", MODE_NAMES)
def test_mode_name_is_gone(module, name):
    assert not hasattr(module, name)
    assert name not in dir(module)
    with pytest.raises(AttributeError):
        getattr(module, name)


@pytest.mark.parametrize("module", ["edgar", "edgar.core", "edgar.settings"])
@pytest.mark.parametrize("name", MODE_NAMES)
def test_importing_a_mode_raises_import_error(module, name):
    result = _run(f"from {module} import {name}")
    assert result.returncode != 0
    assert "ImportError" in result.stderr, result.stderr[-800:]


def test_access_mode_env_var_is_ignored_silently():
    """Not read, not warned about: -W error would fail the import on a warning."""
    result = _run(
        "import edgar, edgar.settings\n"
        "assert not hasattr(edgar.settings, 'edgar_mode')\n",
        EDGAR_ACCESS_MODE="CRAWL",
    )
    assert result.returncode == 0, result.stderr[-1500:]


class TestTheBrokenLimitsPropertyIsGone:
    """`EdgarSettings.limits` ignored self.max_connections and returned the module
    default, so every mode reported 10 despite declaring 10 / 5 / 2."""

    def test_edgarsettings_no_longer_exposes_limits(self):
        assert not hasattr(edgar.settings.EdgarSettings(http_timeout=1, max_connections=1), "limits")

    def test_the_module_level_limits_object_is_untouched(self):
        """A different name with real re-export coverage; not part of this change."""
        assert edgar.settings.limits.max_connections == edgar.settings.default_max_connections
