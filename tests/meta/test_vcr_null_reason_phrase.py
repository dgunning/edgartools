"""Cassettes with no recorded reason phrase must replay on the pinned vcrpy.

79 of the suite's cassettes store ``message: null`` (they were recorded through
vcrpy's httpcore stub). vcrpy 8.2+ crashes replaying those until
kevin1024/vcrpy#1029 is released, so ``tests/_vcr_compat.py`` fills the phrase
in. These tests replay through a real VCR, the way a cassette-backed test does,
so they fail if that fix stops being applied.
"""
import httpx
import pytest
import vcr

from tests import _vcr_compat

pytestmark = pytest.mark.fast

URL = "http://127.0.0.1:9/edgartools-vcr-null-phrase/{name}.txt"

INTERACTION = """\
- request:
    body: ''
    headers: {{}}
    method: GET
    uri: {uri}
  response:
    body:
      string: {name}
    headers:
      Content-Type:
      - text/plain
    status:
      code: {code}
      message: {message}
"""

# name -> (status code, phrase as written in the cassette, phrase expected on replay)
CASES = {
    "null-ok": (200, "null", "OK"),
    "null-not-found": (404, "null", "Not Found"),
    "empty": (200, "''", "OK"),
    "recorded": (200, "Peachy", "Peachy"),
}


@pytest.fixture
def replay_only(tmp_path, vcr_config):
    interactions = "".join(
        INTERACTION.format(uri=URL.format(name=name), name=name, code=code, message=message)
        for name, (code, message, _) in CASES.items()
    )
    (tmp_path / "phrases.yaml").write_text(f"interactions:\n{interactions}version: 1\n")
    config = {**vcr_config, "cassette_library_dir": str(tmp_path), "record_mode": "none"}
    return vcr.VCR(**config)


@pytest.mark.parametrize("name", list(CASES))
def test_replay_supplies_the_reason_phrase(replay_only, name):
    code, _, expected_phrase = CASES[name]

    with replay_only.use_cassette("phrases.yaml", allow_playback_repeats=True):
        response = httpx.get(URL.format(name=name))

    assert response.status_code == code
    assert response.reason_phrase == expected_phrase
    assert response.text == name


def test_the_compat_fix_is_still_needed():
    """When this fails, the pinned vcrpy handles a null phrase by itself:
    delete tests/_vcr_compat.py and its call in tests/conftest.py."""
    from vcr.stubs import httpx_stubs

    assert httpx_stubs._deserialize_response.__module__ == _vcr_compat.__name__
