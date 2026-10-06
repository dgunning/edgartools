"""
Corrected ``gaap_mappings.json`` entries, checked as a table.

PR-3b is the 75 investing and financing cash-flow rows. This file holds only
that slice. PR-3a introduces the same test for the operating rows; the two
expected JSON files have to be combined when one branch is rebased onto the
other. A deleted entry is ``null``. ``lookup()`` returns ``None``, and the key is
gone from ``gaap_mappings.json``. One deleted tag,
``PaymentsRelatedToTaxWithholdingForShareBasedCompensation``, is excluded, so
``lookup()`` was already ``None`` before the row was removed.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1435
"""

import json
from pathlib import Path

import pytest

from edgar.xbrl.standardization.reverse_index import get_reverse_index

EXPECTED = json.loads((Path(__file__).parents[2] / "fixtures" / "standardization" / "issue_1417_expected.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


@pytest.mark.parametrize("tag", sorted(EXPECTED))
def test_corrected_entries(index, tag):
    expected = EXPECTED[tag]
    result = index.lookup(tag)
    if expected is None:
        assert result is None
        assert tag not in index._gaap_mappings
    else:
        assert result is not None and result.standard_concepts == expected
