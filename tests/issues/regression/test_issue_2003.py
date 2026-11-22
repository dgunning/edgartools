"""Exact text values in filing XBRL fact queries.

GitHub Issue: https://github.com/dgunning/edgartools/issues/2003
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL


@pytest.mark.fast
def test_by_value_matches_filed_document_type():
    fixture = Path(__file__).parents[2] / "fixtures" / "xbrl" / "tsla"
    xbrl = XBRL.from_directory(fixture)

    matches = (
        xbrl.query()
        .by_concept("dei:DocumentType", exact=True)
        .by_value("10-Q")
        .execute()
    )

    assert [fact["value"] for fact in matches] == ["10-Q"]
