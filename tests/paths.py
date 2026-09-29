"""Locations in the repository, resolved once, so a test does not encode its own depth.

Every path here used to be spelled ``Path(__file__).parent / ...`` in the test that
needed it, which silently ties the file to the directory it happens to sit in: move
``tests/test_x.py`` one level down and ``Path(__file__).parent / "fixtures"`` points
at a directory that does not exist. That made the test tree expensive to reorganise
for no reason anyone had chosen -- 65 of the loose files carried such a reference
(bead edgartools-07lk.12.2).

Import what you need instead. These are absolute and correct from any depth:

    from tests.paths import FIXTURES_DIR
    html = (FIXTURES_DIR / "html" / "aapl" / "10k" / "aapl-10-k-2024-11-01.html").read_text()

``pytest.main([__file__])`` in a ``__main__`` block is unaffected and stays as it is;
that one wants the file's own path and gets it right at any depth.
"""
from pathlib import Path

#: The `tests/` directory itself.
TESTS_DIR = Path(__file__).resolve().parent

#: The repository root -- the directory holding `pyproject.toml`, `edgar/` and `tests/`.
REPO_ROOT = TESTS_DIR.parent

#: Test fixtures: `html/`, `parser_corpus/`, `attachments/`, `xbrl/`, `funds/`, ...
FIXTURES_DIR = TESTS_DIR / "fixtures"

#: Recorded VCR cassettes.
CASSETTES_DIR = TESTS_DIR / "cassettes"

#: Sample data kept beside the tests. NOT the same tree as the repository-root
#: `data/` directory, which is older and larger; that one is `REPO_ROOT / "data"`.
DATA_DIR = TESTS_DIR / "data"

__all__ = ["TESTS_DIR", "REPO_ROOT", "FIXTURES_DIR", "CASSETTES_DIR", "DATA_DIR"]
