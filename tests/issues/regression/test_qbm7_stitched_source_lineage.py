"""Stitched fact rows carried no source attribution, and every row reported the
newest filing's fiscal focus.

bead edgartools-qbm7, GH #1205 (reported by synfonia-llc).

Three defects on the XBRLS stitching path, all in the row construction:

* ``_determine_source_filing`` was a stub that returned ``None`` unconditionally,
  so ``source_filing_index`` -- a declared public field -- was never populated.
* ``by_filing_index(n)`` filters on that field, so the declared public filter
  matched nothing for any ``n``. A filter that silently returns no rows reads as
  "no matching data", which is worse than a missing feature.
* ``_extract_fiscal_info`` read ``xbrl_list[0].entity_info`` for *every* period,
  so all rows carried the newest filing's focus regardless of the period they
  covered. On ORCL's 10-K + 10-Q pair the quarter ended 2024-08-31 was reported
  as ``fiscal_year=2026, fiscal_period=FY``, taken from a 10-K filed two years
  later.

The attribution is read from the stitcher, which already decides it when
selecting periods (``StatementStitcher._get_all_periods``, "lower index wins"),
rather than recomputed from each filing's reporting periods. Those two do not
agree: a 10-K lists three years of comparatives in ``reporting_periods``, so
recomputing attributed all 183 AAPL rows to the newest filing, where the stitcher
knows 92 of the columns were supplied by the older one.

Still deliberately not fixed here: fiscal metadata is the source filing's declared
focus, not an identity derived from the period's own duration. That is
edgartools-51xd, and this bead is about taking it from the right filing.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL, XBRLS

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl" / "aapl"


@pytest.fixture(scope="module")
def stitched():
    """Two real AAPL 10-Ks from the tracked fixture corpus, newest first."""
    dirs = [FIXTURES / "10k_2023", FIXTURES / "10k_2022"]
    for d in dirs:
        assert d.exists(), f"missing fixture: {d}"
    return XBRLS([XBRL.from_directory(d) for d in dirs])


def test_every_stitched_row_names_its_source_filing(stitched):
    df = stitched.query().to_dataframe()
    assert len(df) > 0

    assert "source_filing_index" in df.columns, (
        "the field is declared public; it was absent entirely")
    assert df["source_filing_index"].notna().all(), "a row has no source attribution"
    assert set(df["source_filing_index"].unique()) == {0, 1}, (
        "attribution collapsed onto a single filing")


def test_by_filing_index_partitions_the_rows(stitched):
    """The public filter returned nothing for every argument."""
    total = len(stitched.query().to_dataframe())
    counts = [len(stitched.query().by_filing_index(i).to_dataframe()) for i in (0, 1)]

    assert all(c > 0 for c in counts), f"by_filing_index returned nothing: {counts}"
    assert sum(counts) == total, f"{counts} does not partition {total} rows"


def test_by_filing_index_rejects_nothing_silently(stitched):
    """An index no filing has must return no rows -- and that must be the truth."""
    assert len(stitched.query().by_filing_index(99).to_dataframe()) == 0


def test_fiscal_metadata_is_not_copied_from_the_newest_filing(stitched):
    """Every row used to carry xbrl_list[0]'s fiscal focus."""
    df = stitched.query().to_dataframe()
    combos = set(zip(df["fiscal_year"].astype(str), df["fiscal_period"].astype(str), strict=True))

    assert len(combos) > 1, (
        f"all rows share one fiscal focus {combos} -- it is being copied again")

    # Each row's focus is its own source filing's, not the newest filing's.
    for index, group in df.groupby("source_filing_index"):
        expected = stitched.xbrl_list[int(index)].entity_info
        assert set(group["fiscal_year"].astype(str)) == {str(expected.get("fiscal_year"))}
        assert set(group["fiscal_period"].astype(str)) == {str(expected.get("fiscal_period"))}


def test_attribution_follows_the_stitcher_not_the_reporting_periods(stitched):
    """The two disagree, and the stitcher is the one that chose the column.

    A 10-K lists its comparatives in `reporting_periods`, so "the lowest-indexed
    filing that reports this period" attributes every column to the newest filing.
    This pins the stitcher's answer instead.
    """
    df = stitched.query().to_dataframe()
    from_older = int((df["source_filing_index"] == 1).sum())
    assert from_older > 0, (
        "every column attributed to the newest filing -- the reporting_periods "
        "answer, not the stitcher's")


@pytest.mark.network
def test_ground_truth_oracle_quarter_reports_its_own_filings_focus():
    """The exact case in the report: ORCL 10-Q + a 10-K filed two years later."""
    from edgar import find

    tenq = find("0000950170-24-104905")
    tenk = find("0001193125-26-277521")
    assert (tenq.form, tenk.form) == ("10-Q", "10-K")

    xs = XBRLS.from_filings([tenk, tenq])
    df = xs.query().to_dataframe()

    assert len(df) == 215
    assert df["source_filing_index"].notna().all()
    counts = {i: len(xs.query().by_filing_index(i).to_dataframe()) for i in (0, 1)}
    assert counts == {0: 115, 1: 100}

    quarter = df[df["period_end"].astype(str).str.contains("2024-08-31", na=False)]
    assert len(quarter) == 100
    # The 10-Q filed it, so its focus is Q1 FY2025 -- not the 10-K's FY2026.
    assert set(quarter["fiscal_year"].astype(str)) == {"2025"}
    assert set(quarter["fiscal_period"].astype(str)) == {"Q1"}
