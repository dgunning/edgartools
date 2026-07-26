"""Force vcrpy to deserialize cassettes with PyYAML's *safe* loader.

vcrpy ships this (``vcr/serializers/yamlserializer.py``)::

    from yaml import CLoader as Loader
    def deserialize(cassette_string):
        return yaml.load(cassette_string, Loader=Loader)

``yaml.Loader``/``CLoader`` constructs arbitrary Python objects from
``python/`` tags, so a cassette is executable content rather than inert
recorded traffic — it runs the moment a test touches it, at whatever privilege
the test session holds. See beads edgartools-j1ui.

``scripts/check_cassettes.py`` gates this in CI, but that check is opt-in
locally (``hatch run check-cassettes``). The dangerous path is a maintainer
checking out a contributor's branch and running pytest to review it, at full
user privilege. This module closes that path: importing it makes every cassette
load in this test session safe, with no discipline required and no cassette
re-recording.

SafeLoader handles everything a real cassette contains — the corpus uses
strings, maps, sequences and ``!!binary`` bodies, all standard tags.
"""
from __future__ import annotations

import yaml

try:  # libyaml when available
    from yaml import CSafeLoader as _SafeLoader
except ImportError:  # pragma: no cover - depends on local libyaml
    from yaml import SafeLoader as _SafeLoader

# A cassette that would execute code under the unsafe loader. Used to prove the
# patch actually took effect rather than assuming it did.
_CANARY = "canary: !!python/object/apply:os.getpid []"


def _safe_deserialize(cassette_string: str):
    return yaml.load(cassette_string, Loader=_SafeLoader)


def install_safe_yaml_deserializer() -> None:
    """Replace vcrpy's YAML deserializer with a SafeLoader-backed one.

    Patches the serializer module attribute rather than registering a new
    serializer under a name: vcr resolves serializers by module object, so this
    covers every cassette load, including ``vcr.use_cassette`` calls that never
    go through the ``vcr_config`` fixture.

    Raises:
        RuntimeError: if vcrpy's internals moved, or if the patch did not
            actually block the canary. A security control that silently
            no-ops after a dependency bump is worse than none, so this fails
            loudly at import instead.
    """
    try:
        import vcr.serializers.yamlserializer as yamlserializer
    except ImportError as exc:  # pragma: no cover - vcrpy is a test dependency
        raise RuntimeError(
            "Cannot secure VCR cassette loading: vcr.serializers.yamlserializer "
            "is not importable. If vcrpy moved it, update tests/_vcr_safety.py "
            "before running the suite on an untrusted branch."
        ) from exc

    if not hasattr(yamlserializer, "deserialize"):  # pragma: no cover
        raise RuntimeError(
            "Cannot secure VCR cassette loading: yamlserializer has no "
            "'deserialize' to replace (vcrpy internals changed)."
        )

    yamlserializer.deserialize = _safe_deserialize

    # Self-verify. If the canary loads, cassettes are still executable and the
    # suite must not proceed to touch one.
    try:
        yamlserializer.deserialize(_CANARY)
    except yaml.YAMLError:
        return  # blocked, as intended
    raise RuntimeError(
        "VCR cassette loading is still unsafe after patching: the canary "
        "'!!python/object/apply' payload was constructed. Refusing to run "
        "tests that load cassettes."
    )
