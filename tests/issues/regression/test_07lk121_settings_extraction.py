"""Settings and identity live in `edgar.settings`; `edgar.core` re-exports them.

edgartools-07lk.12.1, staged under 07lk.23's "new paths behind import shims" row.

The bead proposed renaming `edgar/core.py` to `edgar/settings.py`. Measurement
said no: core.py was 697 lines across 56 top-level definitions and only about a
third was settings — the rest is quarter math, HTML sniffing, a pager, thread
helpers, `Result` and the logger. Renaming the file would have filed
`parallel_thread_map` and `has_html_content` under "settings", relabelling the
grab-bag instead of resolving it. So the settings third was *extracted* and the
rest left alone.

WHAT THIS FILE GUARDS, and why each half matters:

1. **The implementation MOVED; core.py is the wrapper.** This is the 07lk.23
   rename trap, and it is the whole reason the direction matters: if the code had
   stayed in core.py with settings.py aliasing *onto* it, the real implementation
   would still sit at the path 6.0 intends to delete, and dropping the shim would
   take the implementation with it. Asserted by module identity, not by value.

2. **The re-exports are the SAME objects, not copies.** 71 call sites import from
   `edgar.core`, every one of them a `from edgar.core import <name>` (measured by
   AST — zero `import edgar.core`, zero attribute access). A re-export therefore
   covers 100% of them, but only if identity holds: `NORMAL is CAUTION`-style
   comparisons and `isinstance(x, EdgarSettings)` must not care which path the
   name arrived by.
"""
import edgar
import edgar.core
import edgar.settings

SETTINGS_NAMES = [
    "CAUTION",
    "CRAWL",
    "NORMAL",
    "EdgarSettings",
    "ask_for_identity",
    "default_http_timeout",
    "default_max_connections",
    "default_page_size",
    "default_retries",
    "edgar_access_mode",
    "edgar_data_dir",
    "edgar_identity",
    "edgar_mode",
    "get_edgar_data_directory",
    "get_identity",
    "identity_prompt",
    "limits",
    "set_identity",
]


class TestTheImplementationMoved:
    """Not aliased onto the deprecated name — moved to the canonical one."""

    def test_functions_are_defined_in_edgar_settings(self):
        for name in ("set_identity", "get_identity", "ask_for_identity",
                     "get_edgar_data_directory"):
            fn = getattr(edgar.settings, name)
            assert fn.__module__ == "edgar.settings", (
                f"{name} reports __module__={fn.__module__!r}; the implementation "
                f"must live at the canonical name so 6.0 can drop the edgar.core "
                f"shim without taking the implementation with it"
            )

    def test_edgarsettings_class_is_defined_in_edgar_settings(self):
        assert edgar.settings.EdgarSettings.__module__ == "edgar.settings"


class TestCoreStillReExportsEverything:
    """The shim, removed in 6.0. Until then all 71 call sites keep working."""

    def test_every_settings_name_is_reachable_from_core(self):
        missing = [n for n in SETTINGS_NAMES if not hasattr(edgar.core, n)]
        assert not missing, f"edgar.core stopped re-exporting: {missing}"

    def test_re_exports_are_the_same_objects(self):
        """Identity, not equality.

        A copy would pass an equality check and still break
        `isinstance(x, EdgarSettings)` and `mode is NORMAL`.
        """
        for name in SETTINGS_NAMES:
            assert getattr(edgar.core, name) is getattr(edgar.settings, name), (
                f"edgar.core.{name} is a different object from edgar.settings.{name}"
            )

    def test_the_top_level_namespace_is_unaffected(self):
        """What the docs actually tell people to import."""
        for name in ("set_identity", "get_identity", "NORMAL", "CAUTION", "CRAWL"):
            assert getattr(edgar, name) is getattr(edgar.settings, name)

    def test_isinstance_still_works_across_both_paths(self):
        from edgar.core import NORMAL as core_normal
        from edgar.settings import EdgarSettings as settings_cls

        assert isinstance(core_normal, settings_cls)


class TestWhatDeliberatelyStayedInCore:
    """The other two thirds. Moving 34 files for one name (`log`) is churn with
    no user-visible benefit, and `edgar/logging.py` would sit confusingly beside
    stdlib logging."""

    def test_non_settings_names_did_not_move(self):
        for name in ("listify", "text_extensions", "binary_extensions",
                     "has_html_content", "is_probably_html", "strtobool",
                     "get_bool", "parallel_thread_map", "DataPager"):
            assert hasattr(edgar.core, name)
            assert not hasattr(edgar.settings, name), (
                f"{name} is not settings and should not have moved"
            )

    def test_settings_has_its_own_logger_rather_than_importing_cores(self):
        """`log` is the one name both modules define, and that is deliberate.

        34 files import `log` from `edgar.core`; it stays there. But
        `edgar.settings` cannot import it back, because core.py imports settings
        — the dependency runs one way only, and reversing it here would make the
        shim a cycle. So settings carries its own module logger. Two distinct
        loggers, correctly named after their own modules.
        """
        assert edgar.settings.log is not edgar.core.log
        assert edgar.settings.log.name == "edgar.settings"
        assert edgar.core.log.name == "edgar.core"

    def test_core_imports_settings_and_not_the_reverse(self):
        """The direction that lets 6.0 delete core.py's shim block cleanly.

        Checked by parsing, not by searching the text: `edgar/settings.py`
        mentions `from edgar.core import ...` twice in prose — once in its module
        docstring showing the old path, once inside the identity prompt string —
        and a substring search reports those as imports.
        """
        import ast

        def imported_modules(module) -> set:
            tree = ast.parse(open(module.__file__).read())
            return {
                n.module
                for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom) and n.module
            }

        assert "edgar.settings" in imported_modules(edgar.core)
        assert "edgar.core" not in imported_modules(edgar.settings), (
            "edgar.settings must not depend on edgar.core — that would make the "
            "deprecation shim a circular import"
        )
