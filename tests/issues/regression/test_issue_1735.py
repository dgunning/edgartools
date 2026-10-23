"""
FactQuery.to_dataframe() must follow limit() and sort_by() changes after a first call.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1735

The to_dataframe() cache key covered filters, transforms, aggregations and flags, but
not _limit, _sort_by or _sort_ascending, so a query that had already built a frame
returned it again after limit() or sort_by() changed what execute() returns.
"""
from pathlib import Path

import pytest

from edgar.xbrl import XBRL

COLUMNS = ("concept", "period_instant", "numeric_value")


@pytest.fixture(scope="module")
def xbrl():
    # Auburn National Bancorporation FY2023 10-K, accession 0001193125-24-067944
    return XBRL.from_directory(Path("tests/fixtures/xbrl/aubn/10k_2023"))


def _assets(xbrl):
    return xbrl.facts.query().by_concept("us-gaap:Assets", exact=True).by_dimension(None)


def test_limit_after_first_frame(xbrl):
    q = _assets(xbrl)
    first = q.to_dataframe(*COLUMNS)
    assert len(first) == 2
    q.limit(1)
    assert len(q.execute()) == 1
    assert len(q.to_dataframe(*COLUMNS)) == 1

    c = _assets(xbrl)
    c.to_dataframe(*COLUMNS)
    c.limit(2).limit(1)
    assert len(c.to_dataframe(*COLUMNS)) == 1


def test_sort_direction_after_first_frame(xbrl):
    q = _assets(xbrl).sort_by("period_instant", ascending=True)
    assert q.to_dataframe(*COLUMNS)["period_instant"].tolist() == ["2022-12-31", "2023-12-31"]
    q.sort_by("period_instant", ascending=False)
    assert q.to_dataframe(*COLUMNS)["period_instant"].tolist() == ["2023-12-31", "2022-12-31"]


def test_sort_field_after_first_frame(xbrl):
    q = _assets(xbrl).sort_by("period_instant", ascending=True)
    assert q.to_dataframe(*COLUMNS)["numeric_value"].tolist() == [1_023_888_000.0, 975_255_000.0]
    q.sort_by("numeric_value", ascending=True)
    assert q.to_dataframe(*COLUMNS)["numeric_value"].tolist() == [975_255_000.0, 1_023_888_000.0]


def test_unchanged_query_still_reuses_its_frame(xbrl):
    q = _assets(xbrl).limit(1)
    assert q.to_dataframe(*COLUMNS) is q.to_dataframe(*COLUMNS)
