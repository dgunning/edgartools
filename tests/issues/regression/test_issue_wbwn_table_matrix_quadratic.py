"""Regression test for edgartools-wbwn: TableMatrix dimension pass was O(rows^2).

Reported via Michael Gruening's 5.44.0 crawl of 1993-2009 and 2018. 425 of the
428 long-runtime warnings in that log are ABS-15G/A and ABS-15G filings from
Fannie Mae (0000310522) and Freddie Mac (0001026214), each showing the same
split - ``sgml:00:00:00.02, text:02:16:23`` - so SGML parsing was free and the
entire cost sat in text extraction.

The cause was dead work, not real work. ``_calculate_dimensions`` consults
``_is_occupied`` to skip grid positions covered by a rowspan from above, but it
runs *before* ``build_from_rows`` materialises ``self.matrix``. ``_is_occupied``
therefore walked ``range(row)`` finding nothing and returned False every single
time. Profiling accession 0000310522-18-000010 (25MB, 61,801 rows, 1,483,203
cells) at only 4,000 rows showed 95,976 ``_is_occupied`` calls driving
192,527,603 ``builtins.len`` calls - 18.4s of 24s total.

With the short-circuit, full ``FilingSGML.text()`` on that filing drops from
1h12m to ~24s, and the extracted text is byte-identical (sha256 verified at
500 / 2,000 / 6,000 rows).
"""

import time

import pytest

from edgar.documents.table_nodes import Cell, Row
from edgar.documents.utils.table_matrix import TableMatrix

# Shape of the Fannie Mae loan-level tables: many rows, ~24 columns.
COLUMNS = 24
LARGE_ROW_COUNT = 4000

# The fixed build takes ~0.26s; the quadratic one took ~4.2s on the same box.
# Tight enough that O(rows^2) cannot pass, and only meaningful on a machine that
# is not otherwise busy — see the marker on the test that asserts it.
BUILD_BUDGET_SECONDS = 2.0


def build_rows(row_count: int, columns: int = COLUMNS) -> list:
    return [
        Row(cells=[Cell(content=f"r{r}c{c}") for c in range(columns)])
        for r in range(row_count)
    ]


class CountingList(list):
    """A list that records how often its length is inspected."""

    len_calls = 0

    def __len__(self):
        type(self).len_calls += 1
        return super().__len__()


class TestDimensionPassDoesNotConsultAnUnbuiltGrid:
    """The specific defect: occupancy was queried before the grid existed."""

    def test_is_occupied_does_no_work_on_an_empty_matrix(self):
        """Deterministic proof of the short-circuit, independent of wall clock.

        Pre-fix this walked range(row) inspecting the empty grid each time:
        5,000 length checks to return the same False.
        """
        matrix = TableMatrix()
        matrix.matrix = CountingList()
        CountingList.len_calls = 0

        assert matrix._is_occupied(5000, 3) is False
        assert CountingList.len_calls <= 2, (
            f"scanned the empty grid {CountingList.len_calls} times"
        )

    def test_stale_grid_does_not_corrupt_a_rebuild(self):
        """Not just hygiene - a reused instance computed the wrong width.

        build_from_rows never cleared self.matrix, so the second build's
        dimension pass read the first build's rowspan as if it covered the new
        rows, and widened a 2-column table to 3.
        """
        matrix = TableMatrix()
        matrix.build_from_rows([], [
            Row(cells=[Cell(content="a", rowspan=2), Cell(content="b")]),
            Row(cells=[Cell(content="c")]),
        ])
        assert matrix.col_count == 2

        matrix.build_from_rows([], build_rows(2, columns=2))
        assert matrix.col_count == 2
        assert matrix.row_count == 2
        assert len(matrix.matrix) == 2


class TestLargeTablesBuildInLinearTime:
    # An absolute wall-clock budget measures the runner as much as the code, so
    # this one runs in the Regression Tests workflow, which runs pytest serially,
    # and not in the pull-request gate, which runs it under `-n auto`. On a
    # saturated 4-core runner the linear build measured 2.11-2.88s against a
    # 2.0s budget while still being linear — a false failure, and the discriminating
    # signal (0.26s fixed vs 4.2s quadratic) is what contention destroys first.
    # test_scaling_is_not_quadratic below is the pull-request guard: it compares
    # two builds on the same machine, so shared load cancels out of the ratio.
    @pytest.mark.slow
    def test_large_table_build_is_within_budget(self):
        rows = build_rows(LARGE_ROW_COUNT)

        start = time.perf_counter()
        matrix = TableMatrix().build_from_rows([], rows)
        elapsed = time.perf_counter() - start

        assert elapsed < BUILD_BUDGET_SECONDS, f"matrix build took {elapsed:.2f}s"
        assert matrix.row_count == LARGE_ROW_COUNT
        assert matrix.col_count == COLUMNS

    def test_scaling_is_not_quadratic(self):
        """Quadratic growth quadruples per doubling; linear roughly doubles."""

        def build_seconds(row_count: int) -> float:
            rows = build_rows(row_count)
            start = time.perf_counter()
            TableMatrix().build_from_rows([], rows)
            return time.perf_counter() - start

        baseline = build_seconds(1000)
        quadrupled = build_seconds(4000)

        # 4x the rows: ~4x if linear, ~16x if quadratic. Measured 6.7x before
        # the fix at these sizes and 2-3x after, so 8x separates them with room
        # for timer noise on a small baseline.
        assert quadrupled < baseline * 8, (
            f"4x rows cost {quadrupled / baseline:.1f}x the time "
            f"({baseline:.3f}s -> {quadrupled:.3f}s), which looks quadratic"
        )


class TestGridContentIsUnchanged:
    """Speed is only useful if the grid still comes out the same."""

    def test_plain_grid_is_laid_out_correctly(self):
        rows = build_rows(3, columns=3)
        matrix = TableMatrix().build_from_rows([], rows)

        assert [[c.text() if c else None for c in row]
                for row in matrix.to_cell_grid()] == [
            ["r0c0", "r0c1", "r0c2"],
            ["r1c0", "r1c1", "r1c2"],
            ["r2c0", "r2c1", "r2c2"],
        ]

    def test_rowspan_still_occupies_lower_rows(self):
        """_place_cells is where rowspan is genuinely resolved."""
        rows = [
            Row(cells=[Cell(content="span", rowspan=2), Cell(content="b")]),
            Row(cells=[Cell(content="c")]),
        ]
        matrix = TableMatrix().build_from_rows([], rows)

        grid = [[c.text() if c else None for c in row] for row in matrix.to_cell_grid()]
        assert grid[0] == ["span", "b"]
        # "c" must not land under the rowspan; it belongs in the second column.
        assert grid[1][1] == "c"

    @pytest.mark.parametrize("colspan", [1, 2, 3])
    def test_colspan_widens_the_grid(self, colspan):
        rows = [
            Row(cells=[Cell(content="wide", colspan=colspan), Cell(content="tail")]),
        ]
        matrix = TableMatrix().build_from_rows([], rows)
        assert matrix.col_count == colspan + 1
