"""Verification for both cassette defences (beads edgartools-j1ui).

vcrpy deserializes cassettes with PyYAML's unsafe loader, so a cassette bearing
a ``python/`` tag runs code when a test touches it. Two layers stop that:

* ``scripts/check_cassettes.py`` — the CI gate, which refuses a PR carrying such
  a cassette. Opt-in locally via ``hatch run check-cassettes``.
* ``tests/_vcr_safety.py`` — swaps in a SafeLoader-backed deserializer at
  conftest import, so a cassette cannot execute even when nobody ran the gate.
  This is the layer that covers reviewing a contributor's branch locally, which
  is the highest-privilege exposure.

The gate tests pin the property that motivated an allowlist over grepping for
the ``!!python/`` string: YAML spells the same tag three ways and only one of
them contains it. If someone later "simplifies" the gate to a grep, the three
bypass cases below fail.
"""
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

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


# --- Layer 2: the runtime deserializer, active for this very session ----------

@pytest.mark.fast
@pytest.mark.parametrize("variant", sorted(EXECUTABLE_CASSETTES))
def test_running_session_cannot_construct_python_objects(variant):
    """conftest installs the safe deserializer at import, so by the time any
    test runs, vcr must already be unable to execute a cassette. This asserts
    against the live vcr module — not a copy — so it fails if the patch is
    dropped or silently stops applying after a vcrpy bump."""
    import vcr.serializers.yamlserializer as yamlserializer

    with pytest.raises(yaml.YAMLError):
        yamlserializer.deserialize(EXECUTABLE_CASSETTES[variant])


@pytest.mark.fast
def test_running_session_still_loads_real_cassettes():
    """The safe loader must not break ordinary recorded traffic, including the
    !!binary response bodies the corpus actually uses."""
    import vcr.serializers.yamlserializer as yamlserializer

    loaded = yamlserializer.deserialize(LEGITIMATE_CASSETTE)

    assert loaded["interactions"][0]["response"]["body"] == b"hello world"


@pytest.mark.fast
def test_installer_no_ops_when_vcrpy_is_not_installed(monkeypatch):
    """Without vcrpy nothing can load a cassette, so there is no unsafe load to
    prevent and the installer must stay quiet. Conflating this with a moved
    yamlserializer turns a missing test dependency into a security error that
    hides the real cause — it broke the regression job, which never installed
    vcrpy at all."""
    from tests._vcr_safety import install_safe_yaml_deserializer

    # None in sys.modules makes `import vcr` raise ImportError, which is what a
    # machine without vcrpy installed does.
    monkeypatch.setitem(sys.modules, "vcr", None)

    assert install_safe_yaml_deserializer() is False


@pytest.mark.fast
def test_installer_raises_when_vcrpy_is_present_but_serializer_moved(monkeypatch):
    """The other half of the distinction above: vcrpy installed but its
    internals relocated is dangerous, because cassettes remain loadable through
    a deserializer this module no longer patches. That must still fail loudly."""
    from tests._vcr_safety import install_safe_yaml_deserializer

    monkeypatch.setitem(sys.modules, "vcr.serializers.yamlserializer", None)

    with pytest.raises(RuntimeError, match="not importable"):
        install_safe_yaml_deserializer()


@pytest.mark.fast
def test_installer_raises_rather_than_silently_failing(monkeypatch):
    """If vcrpy's internals move, the installer must fail loudly. A security
    control that quietly no-ops after a dependency bump is worse than none."""
    import vcr.serializers

    from tests._vcr_safety import install_safe_yaml_deserializer

    # Stand in for a vcrpy whose deserialize survives the patch — i.e. the
    # assignment appears to succeed but the unsafe loader is still live.
    class FrozenSerializer:
        deserialize = staticmethod(lambda s: {"canary": 1234})

        def __setattr__(self, name, value):  # assignment silently ignored
            pass

    # `import a.b.c as x` binds through the parent package attribute, so that
    # is what has to be replaced — patching sys.modules alone leaves the
    # installer looking at the real module.
    monkeypatch.setattr(vcr.serializers, "yamlserializer", FrozenSerializer())

    with pytest.raises(RuntimeError, match="still unsafe"):
        install_safe_yaml_deserializer()
