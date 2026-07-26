"""Verification for the cassette safety gate (scripts/check_cassettes.py).

vcrpy deserializes cassettes with PyYAML's unsafe loader, so a cassette bearing
a ``python/`` tag runs code when a test touches it. The gate exists to stop that
reaching CI or a maintainer's machine (beads edgartools-j1ui).

These tests pin the property that motivated an allowlist over grepping for the
``!!python/`` string: YAML spells the same tag three ways and only one of them
contains it. If someone later "simplifies" the gate to a grep, the three
bypass cases below fail.
"""
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_cassettes.py"

# Every spelling below is accepted by vcrpy's loader and constructs a Python
# object. Only the first contains the literal string "!!python/".
EXECUTABLE_CASSETTES = {
    "shorthand": "c: !!python/object/apply:os.getpid []\n",
    "full_uri": "c: !<tag:yaml.org,2002:python/object/apply:os.getpid> []\n",
    "name_tag": "c: !!python/name:os.getpid\n",
    "tag_directive": (
        "%TAG !e! tag:yaml.org,2002:python/object/apply:\n"
        "---\n"
        "c: !e!os.getpid []\n"
    ),
}

LEGITIMATE_CASSETTE = (
    "interactions:\n"
    "- request:\n"
    "    uri: https://www.sec.gov/cgi-bin/browse-edgar\n"
    "    method: GET\n"
    "  response:\n"
    "    status: {code: 200, message: OK}\n"
    "    body: !!binary |\n"
    "      aGVsbG8gd29ybGQ=\n"
)


def _run_gate(target: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(target)],
        capture_output=True, text=True,
    )


@pytest.mark.fast
@pytest.mark.parametrize("variant", sorted(EXECUTABLE_CASSETTES))
def test_gate_rejects_every_spelling_of_a_python_tag(tmp_path, variant):
    """All four constructor spellings must be refused, not just the obvious one."""
    cassette = tmp_path / f"{variant}.yaml"
    cassette.write_text(EXECUTABLE_CASSETTES[variant], encoding="utf-8")

    result = _run_gate(tmp_path)

    assert result.returncode == 1, (
        f"{variant} was allowed through:\n{result.stdout}{result.stderr}"
    )
    assert "python/" in result.stderr


@pytest.mark.fast
def test_gate_accepts_an_ordinary_recorded_cassette(tmp_path):
    """A real cassette — strings, maps, and a base64 body — must pass."""
    (tmp_path / "legit.yaml").write_text(LEGITIMATE_CASSETTE, encoding="utf-8")

    result = _run_gate(tmp_path)

    assert result.returncode == 0, f"false positive:\n{result.stdout}{result.stderr}"


@pytest.mark.fast
def test_gate_fails_closed_on_an_unparseable_cassette(tmp_path):
    """A file the scanner can't read is a finding, not a pass — otherwise a
    malformed cassette is a way past the gate."""
    (tmp_path / "broken.yaml").write_text("c: [unclosed\n", encoding="utf-8")

    result = _run_gate(tmp_path)

    assert result.returncode == 1
    assert "unparseable" in result.stderr


@pytest.mark.fast
def test_committed_cassettes_pass_the_gate():
    """The corpus in the repo must stay clean — this is the check CI runs."""
    result = _run_gate(Path(__file__).resolve().parents[1] / "tests" / "cassettes")

    assert result.returncode == 0, (
        f"a committed cassette carries a disallowed tag:\n{result.stderr}"
    )
