"""The upgrade-guide gate has to catch the PR it was written for, and stay quiet otherwise.

``scripts/check_upgrade_guide.py`` fails a pull request that stages a 6.0
change without touching ``docs/upgrade/6.0.md``. It exists because #1200/#1201
shipped the edgar.files deprecations in 5.55.0 with no guide entry, and that PR
warned through a module-local helper and the phrase "removed in edgartools 6.0"
rather than a bare ``DeprecationWarning`` — so the first test is that shape,
verbatim.

The patches here are the shape the GitHub pull-request files API returns, which
is what the workflow pipes into the script.

Bead: edgartools-07lk.14
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# Pure functions over strings, plus one call to main() with a temp file.
pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_upgrade_guide.py"


def _load():
    """Import the script by path — `scripts/` is not a package."""
    spec = importlib.util.spec_from_file_location("check_upgrade_guide", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_upgrade_guide"] = module
    spec.loader.exec_module(module)
    return module


gate = _load()

GUIDE = {"filename": "docs/upgrade/6.0.md", "status": "modified", "patch": "@@ -1 +1 @@\n+a line\n"}

# From #1201 (0878e3ce), edgar/files/markdown.py, trimmed to the lines that matter.
PR_1201_MARKDOWN = (
    "@@ -1,0 +2,9 @@\n"
    "+from edgar.files._deprecation import warn_legacy_html_usage\n"
    "+_MARKDOWN_DEPRECATION_MSG = (\n"
    '+    "removed in edgartools 6.0. Use Filing.markdown() / Attachment.markdown(), "\n'
    "+)\n"
    "+        warn_legacy_html_usage(_MARKDOWN_DEPRECATION_MSG)\n"
)


def _py(patch, name="edgar/files/markdown.py", status="modified"):
    return {"filename": name, "status": status, "patch": patch}


def test_the_pr_that_motivated_the_gate_fails_it():
    verdict = gate.evaluate([_py(PR_1201_MARKDOWN)])
    assert not verdict.ok
    # The message line and the helper call; the import line is not staging.
    assert [h.line.strip() for h in verdict.hits] == [
        '"removed in edgartools 6.0. Use Filing.markdown() / Attachment.markdown(), "',
        "warn_legacy_html_usage(_MARKDOWN_DEPRECATION_MSG)",
    ]


def test_touching_the_guide_passes_the_same_pr():
    assert gate.evaluate([_py(PR_1201_MARKDOWN), GUIDE]).ok


@pytest.mark.parametrize("line", [
    "warn_will_raise(section_not_found(report, item), stacklevel=4)",
    "warnings.warn(msg, DeprecationWarning, stacklevel=2)",
    "        FutureWarning,",
    "__getattr__ = deprecated_alias(InvalidDateException=InvalidDateError)",
    '"FilingHomepage(soup=...) is deprecated and will be removed in v6.0. "',
    '"""Deprecated: use edgar.exceptions.DataObjectError. Removed in 6.0.',
])
def test_each_staging_idiom_in_the_codebase_is_caught(line):
    assert gate.staged_lines("edgar/x.py", f"@@ -0,0 +1 @@\n+{line}\n")


@pytest.mark.parametrize("line", [
    "# Deliberately not warn_will_raise(): the parser's own error propagates",
    "def warn_will_raise(error, *, stacklevel=3):",
    "return parse_homepage_html(str(root))",
    "# removed in 6.0",
])
def test_comments_definitions_and_ordinary_code_are_not_staging(line):
    assert gate.staged_lines("edgar/x.py", f"@@ -0,0 +1 @@\n+{line}\n") == []


def test_removed_lines_never_count():
    patch = "@@ -1,2 +0,0 @@\n-warnings.warn(msg, DeprecationWarning)\n-# removed in 6.0\n"
    assert gate.evaluate([_py(patch)]).ok


def test_restructuring_an_existing_warning_nets_to_nothing():
    # #1037's shape: a multi-line warn_will_raise( call became a one-liner.
    patch = (
        "@@ -1,3 +1,2 @@\n"
        "-        warn_will_raise(\n"
        "-            ValidationError(msg))\n"
        "+        warn_will_raise(malformed)\n"
    )
    assert gate.evaluate([_py(patch, name="edgar/__init__.py")]).ok


def test_netting_works_across_files_and_does_not_over_forgive():
    moved_out = _py("@@ -1 +0,0 @@\n-    warnings.warn(m, FutureWarning)\n", name="edgar/a.py")
    moved_in_twice = _py(
        "@@ -0,0 +1,2 @@\n+    warnings.warn(m, FutureWarning)\n+    warnings.warn(n, FutureWarning)\n",
        name="edgar/b.py",
    )
    verdict = gate.evaluate([moved_out, moved_in_twice])
    assert len(verdict.hits) == 1  # one moved, one new


def test_a_deprecated_or_removed_changelog_fragment_is_staging():
    added = {"filename": "changelog.d/1326.deprecated.md", "status": "added"}
    assert not gate.evaluate([added]).ok
    assert gate.evaluate([{"filename": "changelog.d/1379.fixed.md", "status": "added"}]).ok


def test_files_outside_the_library_are_ignored():
    test_file = _py("@@ -0,0 +1 @@\n+    with pytest.warns(FutureWarning):\n", name="tests/test_x.py")
    assert gate.evaluate([test_file]).ok


def test_a_patch_the_api_omitted_is_reported_not_passed():
    verdict = gate.evaluate([{"filename": "edgar/_filings.py", "status": "modified", "patch": None}])
    assert not verdict.ok
    assert verdict.unreadable == ["edgar/_filings.py"]


def _run(tmp_path, files, monkeypatch, labels=""):
    path = tmp_path / "files.jsonl"
    path.write_text("\n".join(json.dumps(f) for f in files))
    monkeypatch.setenv("PR_LABELS", labels)
    return gate.main(["check_upgrade_guide.py", str(path)])


def test_main_fails_names_the_lines_and_says_what_to_do(tmp_path, monkeypatch, capsys):
    assert _run(tmp_path, [_py(PR_1201_MARKDOWN)], monkeypatch) == 1
    out = capsys.readouterr().out
    assert "does not touch docs/upgrade/6.0.md" in out
    assert "edgar/files/markdown.py: warn_legacy_html_usage(_MARKDOWN_DEPRECATION_MSG)" in out
    assert "no-upgrade-guide" in out


def test_the_label_passes_but_still_lists_what_it_skipped(tmp_path, monkeypatch, capsys):
    assert _run(tmp_path, [_py(PR_1201_MARKDOWN)], monkeypatch, labels="bug,no-upgrade-guide") == 0
    out = capsys.readouterr().out
    assert out.startswith("SKIPPED")
    assert "warn_legacy_html_usage" in out
