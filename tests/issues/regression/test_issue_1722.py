"""install_skill() and package_skill() shipped no ``funds`` skill.

The subdirectory lists in ``edgar/ai/__init__.py`` (symlink install),
``edgar/ai/exporters/claude_skills.py`` (copy install) and
``edgar/ai/exporters/claude_desktop.py`` (Desktop ZIP) named financials, holdings,
ownership, reports and xbrl. ``edgar/ai/skills/funds/skill.yaml`` exists, and the
installed ``core/collaboration.yaml`` and ``holdings/skill.yaml`` send readers to it.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1722
"""
import tempfile
from pathlib import Path
from zipfile import ZipFile

import pytest

import edgar.ai.skills as skills
from edgar.ai import install_skill, package_skill

SHIPPED_ID = "id: edgartools-funds"


@pytest.mark.fast
@pytest.mark.parametrize("use_symlinks", [True, False])
def test_install_skill_includes_funds(use_symlinks):
    with tempfile.TemporaryDirectory() as tmp:
        installed = install_skill(to=Path(tmp), quiet=True, use_symlinks=use_symlinks)
        skill_yaml = installed / "funds" / "skill.yaml"
        assert skill_yaml.is_file()
        assert skill_yaml.read_text(encoding="utf-8").startswith(SHIPPED_ID)


@pytest.mark.fast
def test_package_skill_zip_includes_funds():
    with tempfile.TemporaryDirectory() as tmp:
        archive = package_skill(output=Path(tmp), quiet=True)
        with ZipFile(archive) as z:
            names = [n for n in z.namelist() if "/funds/" in n]
            assert [Path(n).name for n in names] == ["skill.yaml"]
            assert z.read(names[0]).decode("utf-8").startswith(SHIPPED_ID)


@pytest.mark.fast
def test_the_skill_the_installers_must_copy_exists():
    assert (Path(skills.__file__).parent / "funds" / "skill.yaml").read_text(encoding="utf-8").startswith(SHIPPED_ID)
