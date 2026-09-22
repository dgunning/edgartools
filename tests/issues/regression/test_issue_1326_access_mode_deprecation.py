"""EDGAR_ACCESS_MODE and its modes are deprecated; they never did anything.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1326

`NORMAL`, `CAUTION` and `CRAWL` advertise a timeout / connection-limit / retry
policy, and `docs/configuration.md` documented it as a table. None of it was ever
wired into the HTTP client: nothing in the package reads `edgar_mode`, `.retries`
or `EdgarSettings.limits`, so selecting a mode has never changed how edgartools
talks to SEC. What protects you is `EDGAR_RATE_LIMIT_PER_SEC`, with
`EDGAR_HTTP_TIMEOUT` for the request timeout.

The names stay importable until 6.0 and warn on use. Two properties matter and
each has a test below:

1. **Reaching for a mode warns, and the warning names both replacements.** A
   deprecation that does not say what to use instead just tells people they are
   wrong.
2. **`import edgar` does NOT warn.** The modes were re-exported eagerly from
   `edgar/__init__.py` and `edgar/core.py`. Had they stayed eager, adding the
   warning would have fired it once for every user on every import, naming the
   re-export site instead of the code that reached for a mode - noise that
   trains people to filter the warning rather than act on it.
"""
import os
import subprocess
import sys
import warnings

import pytest

import edgar
import edgar.core
import edgar.settings

MODE_NAMES = ["NORMAL", "CAUTION", "CRAWL", "edgar_mode"]


@pytest.fixture(autouse=True)
def _no_shadowing_globals():
    """Assigning `edgar.edgar_mode = x` shadows __getattr__ and kills the warning.

    That is correct PEP 562 behaviour - a real module global wins over the hook -
    but it makes these tests order-dependent, because any earlier test that
    assigns one leaves it set for the rest of the session. Clear the overrides
    before each test and restore them after.
    """
    import edgar as _pkg

    saved = {m: {n: vars(m)[n] for n in MODE_NAMES if n in vars(m)}
             for m in (_pkg, edgar.core, edgar.settings)}
    for module, names in saved.items():
        for n in names:
            vars(module).pop(n, None)
    yield
    for module, names in saved.items():
        vars(module).update(names)
REPLACEMENTS = ["EDGAR_RATE_LIMIT_PER_SEC", "EDGAR_HTTP_TIMEOUT"]


def _run(code: str, **env_overrides: str) -> subprocess.CompletedProcess:
    """Run `code` in a clean interpreter with deprecations made visible.

    EDGAR_ACCESS_MODE is stripped from the child's environment unless the caller
    asks for it. Inheriting it would fire the import-time deprecation inside the
    child, and under `-W error` that exits non-zero - so the silence tests would
    fail for exactly the users this deprecation is aimed at, the ones who already
    set the variable.
    """
    env = {**os.environ}
    env.pop("EDGAR_ACCESS_MODE", None)
    env.update(env_overrides)
    return subprocess.run(  # noqa: S603 -- sys.executable with a literal argv, no shell
        [sys.executable, "-W", "always::DeprecationWarning", "-c", code],
        capture_output=True, text=True, timeout=180, env=env,
    )


class TestReachingForAModeWarns:

    @pytest.mark.parametrize("name", MODE_NAMES)
    @pytest.mark.parametrize("module", [edgar, edgar.core, edgar.settings],
                             ids=["edgar", "edgar.core", "edgar.settings"])
    def test_every_path_to_a_mode_warns(self, module, name):
        with pytest.warns(DeprecationWarning) as caught:
            getattr(module, name)
        assert any(name in str(w.message) for w in caught), (
            f"the warning for {name} does not name it"
        )

    @pytest.mark.parametrize("name", MODE_NAMES)
    def test_the_warning_names_both_replacements(self, name):
        """Otherwise it says 'stop' without saying 'do this'."""
        with pytest.warns(DeprecationWarning) as caught:
            getattr(edgar.settings, name)
        message = str(caught[0].message)
        missing = [r for r in REPLACEMENTS if r not in message]
        assert not missing, f"{name} deprecation does not mention {missing}"

    @pytest.mark.parametrize("module", [edgar, edgar.core, edgar.settings],
                             ids=["edgar", "edgar.core", "edgar.settings"])
    def test_the_warning_points_at_the_caller_not_at_library_internals(self, module):
        """A deprecation that blames the library tells you nothing about your code.

        `edgar.core` is the path that gets this wrong by default: it installs its
        __getattr__ through `edgar._compat.deprecated_alias`, which adds a frame
        between the caller and the warn() call, so the default stacklevel reports
        `edgar/_compat.py` as the offender.
        """
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _ = module.NORMAL
        assert caught[0].filename == __file__, (
            f"warning blamed {caught[0].filename}, not the calling test file"
        )

    def test_the_warning_says_it_has_no_effect(self):
        with pytest.warns(DeprecationWarning) as caught:
            _ = edgar.settings.NORMAL
        assert "no effect" in str(caught[0].message)


class TestTheNamesStillWorkUntilSixPointOh:
    """Deprecated, not removed. Identity is what `mode is NORMAL` relies on."""

    @pytest.mark.parametrize("name", MODE_NAMES)
    def test_the_same_object_arrives_by_every_path(self, name):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert getattr(edgar, name) is getattr(edgar.settings, name)
            assert getattr(edgar.core, name) is getattr(edgar.settings, name)

    def test_repeated_access_returns_one_singleton(self):
        """Rebuilt per access, `mode is NORMAL` would silently become False."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert edgar.settings.NORMAL is edgar.settings.NORMAL

    def test_the_declared_values_are_unchanged(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert (edgar.settings.NORMAL.http_timeout, edgar.settings.NORMAL.max_connections) == (15, 10)
            assert (edgar.settings.CAUTION.http_timeout, edgar.settings.CAUTION.max_connections) == (20, 5)
            assert (edgar.settings.CRAWL.http_timeout, edgar.settings.CRAWL.max_connections) == (25, 2)
            assert edgar.settings.CRAWL.retries == 2

    def test_unknown_names_still_raise_attributeerror(self):
        for module in (edgar, edgar.core, edgar.settings):
            with pytest.raises(AttributeError):
                _ = module.NoSuchSetting


class TestImportingEdgarIsSilent:
    """The property that made this a lazy re-export rather than a one-line warn."""

    def test_plain_import_emits_no_deprecation(self):
        r = _run("import warnings; warnings.simplefilter('error', DeprecationWarning); import edgar")
        assert r.returncode == 0, (
            f"`import edgar` raised a DeprecationWarning:\n{r.stderr}"
        )

    def test_importing_edgar_core_emits_no_deprecation(self):
        r = _run("import warnings; warnings.simplefilter('error', DeprecationWarning); import edgar.core")
        assert r.returncode == 0, f"`import edgar.core` warned:\n{r.stderr}"

    def test_setting_the_env_var_warns_at_import(self):
        """Setting it is deliberate, so it does not wait to be read back."""
        r = _run(
            "import warnings\n"
            "with warnings.catch_warnings(record=True) as caught:\n"
            "    warnings.simplefilter('always')\n"
            "    import edgar.settings\n"
            "msgs = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]\n"
            "assert any('EDGAR_ACCESS_MODE' in m for m in msgs), msgs\n"
            "assert any('EDGAR_RATE_LIMIT_PER_SEC' in m for m in msgs), msgs\n"
            "print('OK')",
            EDGAR_ACCESS_MODE="CRAWL",
        )
        assert r.returncode == 0, f"env-var deprecation did not fire:\n{r.stdout}\n{r.stderr}"


class TestTheImportSurfaceIsUnchanged:
    """Deprecating a name must not move it. Every name reachable before is
    reachable now, and no name became reachable that was not before."""

    def test_the_top_level_namespace_exposes_exactly_what_it_did(self):
        """`edgar_access_mode` has never been reachable from `edgar` itself.

        Serving it here would widen the public surface in a change whose whole
        purpose is to narrow it, and `dir()`-based guards like
        test_public_api_surface.py would then have a name to classify that the
        package never exported.
        """
        for name in ("CAUTION", "CRAWL", "NORMAL", "edgar_mode"):
            assert hasattr(edgar, name), f"edgar.{name} stopped being reachable"
            assert name in dir(edgar), f"edgar.{name} is readable but invisible to dir()"
        assert not hasattr(edgar, "edgar_access_mode")
        assert "edgar_access_mode" not in dir(edgar)

    def test_the_settings_and_core_paths_still_carry_all_five(self):
        for module in (edgar.core, edgar.settings):
            for name in (*MODE_NAMES, "edgar_access_mode"):
                assert hasattr(module, name), f"{module.__name__}.{name} was dropped"


class TestAssigningAModeShadowsTheWarning:
    """Documented, not a defect: a real module global wins over PEP 562 __getattr__.

    Worth pinning because it is the failure mode that made the suite
    order-dependent - `tests/display/test_core.py::test_settings` assigned
    `edgar.edgar_mode` and did not restore it, which silently suppressed this
    deprecation for every test that ran after it.
    """

    def test_an_assigned_mode_no_longer_warns(self):
        import edgar as _pkg

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            crawl = edgar.settings.CRAWL
        try:
            _pkg.edgar_mode = crawl
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                assert _pkg.edgar_mode is crawl
            assert not [w for w in caught if issubclass(w.category, DeprecationWarning)], (
                "an explicitly assigned value should not warn - the user owns it"
            )
        finally:
            vars(_pkg).pop('edgar_mode', None)

    def test_clearing_the_override_restores_the_warning(self):
        import edgar as _pkg

        _pkg.edgar_mode = object()
        vars(_pkg).pop('edgar_mode', None)
        with pytest.warns(DeprecationWarning):
            _ = _pkg.edgar_mode


class TestTheBrokenLimitsPropertyIsGone:
    """`EdgarSettings.limits` ignored self.max_connections and returned the module
    default, so NORMAL, CAUTION and CRAWL all reported 10 despite declaring
    10 / 5 / 2. It is dropped with the rest rather than repaired - nothing read it."""

    def test_edgarsettings_no_longer_exposes_limits(self):
        assert not hasattr(edgar.settings.EdgarSettings(http_timeout=1, max_connections=1), "limits")

    def test_the_module_level_limits_object_is_untouched(self):
        """A different name with real re-export coverage; not part of this change."""
        assert edgar.settings.limits.max_connections == edgar.settings.default_max_connections
