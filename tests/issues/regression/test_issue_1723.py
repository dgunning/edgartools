"""install_skill() falls back to copying when the account cannot create symlinks.

``tests/ai/test_ai_skill_export.py::test_install_skill_uses_symlinks`` asserted
``SKILL.md.is_symlink()`` unconditionally, so it failed on Windows without the
symlink privilege although the installer copies there as documented ("Falls back
to copy on Windows without symlink permissions").

The test now branches on whether links can be made. This file forces the failure on
every platform by making ``Path.symlink_to`` raise the error Windows raises
(``OSError``, winerror 1314), so the fallback is exercised on macOS and Linux too.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1723
"""
import tempfile
from pathlib import Path

import pytest

from edgar.ai import install_skill


@pytest.mark.fast
def test_install_falls_back_to_a_copy_when_symlinks_are_refused(monkeypatch):
    def refuse(self, target, target_is_directory=False):
        raise OSError(1314, "A required privilege is not held by the client")

    monkeypatch.setattr(Path, "symlink_to", refuse)

    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = install_skill(to=Path(tmpdir), quiet=True, use_symlinks=True)

        skill_md = skill_dir / "SKILL.md"
        assert skill_md.is_file() and not skill_md.is_symlink()
        assert skill_md.read_text(encoding="utf-8").startswith("---")
        assert (skill_dir / "financials").is_dir()
        assert not (skill_dir / "financials").is_symlink()
        assert (skill_dir / "financials" / "skill.yaml").is_file()
