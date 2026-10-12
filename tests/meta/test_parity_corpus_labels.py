"""Every 10-K/10-Q fixture is measured by the parity ratchets, under its own key.

The markdown and section parity ratchets key their baselines on the labels
``parity_benchmark.build_corpus`` assigns, and ``build_corpus`` keeps the first
file per label. Labels used to be per *directory* (``c/10k``), so when GH #1346
added an FY2022 Citi 10-K beside the FY2024 one, the new file sorted first and
every ratchet keyed ``c/10k`` silently started measuring a different filing,
while the FY2024 filing dropped out of the corpus. The markdown ratchet then
failed on main against a baseline measured on the other filing.

These checks glob the fixture tree and build the corpus without parsing
anything, so they run in the fast lane and fail the moment a second fixture
in a directory would displace the first.
"""
import sys
from collections import Counter

import pytest

from tests.paths import FIXTURES_DIR

sys.path.insert(0, str(FIXTURES_DIR / "parser_corpus"))
import parity_benchmark  # noqa: E402

pytestmark = pytest.mark.fast

MODERN_FORMS = {"10-K": "10k", "10-Q": "10q"}


def _fixture_files():
    html = FIXTURES_DIR / "html"
    return {
        (form, path.resolve())
        for form, subdir in MODERN_FORMS.items()
        for path in html.glob(f"*/{subdir}/*.html")
    }


def test_the_corpus_has_no_duplicate_labels():
    corpus = parity_benchmark.build_corpus(parity_benchmark.GATE_FORMS)
    counts = Counter((entry["form"], entry["label"]) for entry in corpus)
    duplicates = sorted(key for key, n in counts.items() if n > 1)
    assert not duplicates, f"labels shared by more than one corpus entry: {duplicates}"


def test_every_modern_fixture_is_measured_exactly_once():
    fixtures = _fixture_files()
    assert len(fixtures) >= 60,f"only {len(fixtures)} 10-K/10-Q fixtures found"
    corpus = parity_benchmark.build_corpus(list(MODERN_FORMS))
    measured = Counter(
        (entry["form"], entry["path"].resolve())
        for entry in corpus if entry["era"] == "modern"
    )
    missing = sorted(str(path) for _form, path in fixtures - set(measured))
    repeated = sorted(str(key[1]) for key, n in measured.items() if n > 1)
    assert not missing, f"fixtures the parity ratchets never measure: {missing}"
    assert not repeated, f"fixtures measured more than once: {repeated}"


def test_a_directory_with_one_fixture_keeps_its_directory_label():
    """Existing baselines are keyed ``<ticker>/<subdir>``; that must not drift."""
    labels = {(entry["form"], entry["label"])
              for entry in parity_benchmark.build_corpus(["10-K"])}
    assert ("10-K", "aapl/10k") in labels
    assert ("10-K", "c/10k") not in labels
    assert ("10-K", "c/10k/c-10-k-2025-02-21") in labels
    assert ("10-K", "c/10k/c-10-k-2023-02-27") in labels


def test_every_tracked_fixture_has_a_frozen_legacy_record():
    """The ratchets compare against frozen legacy output; the keys must still match.

    ``edgar.files`` is gone, so both ratchets read the legacy side from
    ``parser_corpus/legacy_frozen/`` keyed by ``<form>|<label>``. A label that
    changes — the GH #1346 shape, a second fixture landing in a directory — would
    leave its filing with no reference, and the ratchets would stop guarding it
    without failing. Fast because it only builds the corpus and reads two files.
    """
    import gzip
    import json

    sections = json.loads(parity_benchmark.LEGACY_FROZEN.read_text())
    md_path = parity_benchmark.LEGACY_FROZEN.with_name("markdown.json.gz")
    with gzip.open(md_path, "rt", encoding="utf-8") as fh:
        markdown = json.load(fh)
    tracked = [entry for entry in parity_benchmark.build_corpus(parity_benchmark.GATE_FORMS)
               if entry["era"] in ("modern", "gate")]
    assert len(tracked) >= 70, f"tracked corpus shrank to {len(tracked)} fixtures"
    keys = {f"{entry['form']}|{entry['label']}" for entry in tracked}
    assert not keys - set(sections), sorted(keys - set(sections))
    assert not keys - set(markdown), sorted(keys - set(markdown))
