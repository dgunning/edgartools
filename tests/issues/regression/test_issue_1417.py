"""
Corrected ``gaap_mappings.json`` entries, checked as a table.

PR-3a starts the table with the 67 operating cash-flow rows. Later slices
append rows to ``issue_1417_expected.json``; this test stays as it is.
A deleted entry is ``null`` and ``lookup()`` returns ``None``.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1435
"""

import json
from pathlib import Path

import pytest

from edgar.xbrl.standardization.reverse_index import get_reverse_index

EXPECTED = json.loads(
    (Path(__file__).parents[2] / "fixtures" / "standardization" / "issue_1417_expected.json").read_text(
        encoding="utf-8"
    )
)


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


@pytest.mark.parametrize("tag", sorted(EXPECTED))
def test_corrected_entries(index, tag):
    expected = EXPECTED[tag]
    result = index.lookup(tag)
    if expected is None:
        assert result is None
    else:
        assert result is not None and result.standard_concepts == expected
