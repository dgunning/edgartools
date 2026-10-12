"""Missing note-table metadata must serialize as null rather than bare NaN.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1489

The Apple record is an exact fragment of received MCP TextContent from 10-Q
0000320193-26-000020, Note 6 Debt, R24.htm. Its twenty-field record has absent
balance and weight metadata beyond the ten displayed column names. It is a
captured-record fixture, not a new SEC response or a complete filing replay.
The public handler receives a scoped upstream-data stub. Other cases are
explicit synthetic scalar and response-shape controls.
"""

import json
import socket
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio

from tests.paths import REPO_ROOT

pytestmark = [pytest.mark.fast, pytest.mark.regression]

FIXTURE = REPO_ROOT / "tests/fixtures/mcp/issue_1489/apple_0000320193-26-000020_debt_record.txt"


@pytest_asyncio.fixture(autouse=True)
async def no_network(monkeypatch):
    attempted = []

    def denied(*args, **kwargs):
        attempted.append(True)
        raise AssertionError("This regression uses offline upstream-data stubs")

    # Windows Proactor creates a socketpair during event-loop startup.
    # Block after this fixture's loop starts, and restore before loop teardown.
    with monkeypatch.context() as guard:
        guard.setattr(socket, "create_connection", denied)
        guard.setattr(socket, "getaddrinfo", denied)
        guard.setattr(socket.socket, "connect", denied)
        guard.setattr(socket.socket, "connect_ex", denied)
        yield
    assert not attempted


def _strict(text):
    def reject(constant):
        raise ValueError(f"Nonstandard JSON constant: {constant}")

    return json.loads(text, parse_constant=reject)


class _Notes:
    def __init__(self, note):
        self.note = note

    def __len__(self):
        return 1

    def search(self, topic):
        assert topic == "debt"
        return [self.note]


async def _invoke(monkeypatch, frames, *, detail="full", captured=False):
    from edgar.ai.mcp.tools import notes as notes_tool
    from edgar.ai.mcp.tools.base import call_tool_handler

    calls = []
    tables = []
    originals = [None if frame is None else frame.copy(deep=True) for frame in frames]

    for position, frame in enumerate(frames):

        def get_frame(frame=frame, position=position):
            calls.append(position)
            return frame

        tables.append(
            SimpleNamespace(
                role_or_type=("http://www.apple.com/role/DebtTables" if captured else f"urn:synthetic:notes:{position}"),
                render=lambda: SimpleNamespace(title="Debt (Tables)"),
                to_dataframe=get_frame,
            )
        )

    note = SimpleNamespace(
        number=6 if captured else 1,
        title="Debt" if captured else "Synthetic note-table control",
        expands=[],
        expands_statements=[],
        tables=tables,
        to_context=lambda detail: "Offline upstream-data conversion control",
    )
    obj = SimpleNamespace(notes=_Notes(note), period_of_report="2026-06-27")
    filing = SimpleNamespace(
        form="10-Q",
        filing_date="2026-07-31",
        obj=lambda: obj,
    )
    company = MagicMock()
    company.__str__.return_value = "Apple Inc." if captured else "Synthetic input"
    company.get_filings.return_value = [filing]
    monkeypatch.setattr(notes_tool, "resolve_company", lambda identifier: company)

    response = await call_tool_handler(
        "edgar_notes",
        {
            "identifier": "AAPL" if captured else "SYNTHETIC",
            "topic": "debt",
            "form": "10-Q",
            "detail": detail,
        },
    )
    assert response.success
    company.get_filings.assert_called_once_with(form="10-Q", amendments=False)
    for frame, original in zip(frames, originals, strict=True):
        if frame is not None:
            pd.testing.assert_frame_equal(frame, original)
    return _strict(response.to_json()), calls


@pytest.mark.asyncio
async def test_captured_apple_missing_metadata_is_null_beyond_display_columns(monkeypatch):
    # The TXT retains the actual nonstandard NaN constants. Permissive loading
    # only reconstructs the recorded upstream cells; output parsing is strict.
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(expected) == 20
    assert expected["concept"] == "aapl_CommercialPaperCashFlowSummaryTableTextBlock"
    frame = pd.DataFrame([expected])
    assert pd.isna(frame.loc[0, "balance"]) and pd.isna(frame.loc[0, "weight"])

    data, calls = await _invoke(monkeypatch, [frame], captured=True)
    assert calls == [0]
    assert data["data"]["filed"] == "2026-07-31"
    assert data["data"]["period"] == "2026-06-27"
    note = data["data"]["notes"][0]
    assert note["number"] == 6 and note["title"] == "Debt"
    table = note["tables"][0]
    assert table["role"] == "http://www.apple.com/role/DebtTables"
    assert table["rows"] == 1 and len(table["columns"]) == 10
    assert "balance" not in table["columns"] and "weight" not in table["columns"]
    row = table["data"][0]
    assert list(row) == list(expected)
    assert row["balance"] is None and row["weight"] is None
    assert {k: v for k, v in row.items() if k not in ("balance", "weight")} == {k: v for k, v in expected.items() if k not in ("balance", "weight")}
    assert row["abstract"] is False and row["dimension"] is False


@pytest.mark.asyncio
async def test_synthetic_finite_zero_false_and_text_values_are_preserved(monkeypatch):
    frame = pd.DataFrame(
        [
            {
                "zero": 0,
                "float_zero": 0.0,
                "false": False,
                "fraction": -24.5,
                "numpy_integer": np.int64(7),
                "numpy_fraction": np.float32(0.1),
                "empty": "",
                "literal_nan": "NaN",
                "whitespace": "  keep  ",
                "decimal": Decimal("1234.56"),
                "huge_decimal": Decimal("1E+1000"),
            }
        ],
        dtype=object,
    )
    output, _ = await _invoke(monkeypatch, [frame])
    row = output["data"]["notes"][0]["tables"][0]["data"][0]
    assert row == {
        "zero": 0,
        "float_zero": 0.0,
        "false": False,
        "fraction": -24.5,
        "numpy_integer": 7,
        "numpy_fraction": 0.10000000149011612,
        "empty": "",
        "literal_nan": "NaN",
        "whitespace": "  keep  ",
        "decimal": "1234.56",
        "huge_decimal": "1E+1000",
    }
    assert type(row["zero"]) is int
    assert type(row["float_zero"]) is float
    assert row["false"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [None, pd.NaT, pd.NA, np.float32("nan")])
async def test_synthetic_missing_cells_are_null(monkeypatch, missing):
    frame = pd.DataFrame({"missing": pd.Series([missing], dtype=object)})
    output, _ = await _invoke(monkeypatch, [frame])
    assert output["data"]["notes"][0]["tables"][0]["data"] == [{"missing": None}]


@pytest.mark.asyncio
async def test_missing_fields_are_normalized_in_every_record_and_table(monkeypatch):
    def frame(rows):
        return pd.DataFrame(
            [
                dict(
                    {f"visible_{i}": i for i in range(10)},
                    balance=float("nan"),
                    weight=float("nan"),
                )
                for _ in range(rows)
            ],
            dtype=object,
        )

    output, calls = await _invoke(monkeypatch, [frame(3), frame(2)])
    tables = output["data"]["notes"][0]["tables"]
    assert calls == [0, 1] and [len(t["data"]) for t in tables] == [3, 2]
    for table in tables:
        assert len(table["columns"]) == 10
        assert "balance" not in table["columns"] and "weight" not in table["columns"]
        for row in table["data"]:
            assert row["balance"] is None and row["weight"] is None
            assert row["visible_0"] == 0


@pytest.mark.asyncio
async def test_total_row_count_and_first_ten_row_limit_are_preserved(monkeypatch):
    frame = pd.DataFrame({"sequence": range(11)})
    output, _ = await _invoke(monkeypatch, [frame])
    table = output["data"]["notes"][0]["tables"][0]
    assert table["rows"] == 11
    assert table["data"] == [{"sequence": i} for i in range(10)]


@pytest.mark.asyncio
@pytest.mark.parametrize("detail", ["minimal", "standard"])
async def test_other_detail_modes_do_not_convert_dataframes(monkeypatch, detail):
    output, calls = await _invoke(monkeypatch, [pd.DataFrame({"value": [1]})], detail=detail)
    table = output["data"]["notes"][0]["tables"][0]
    assert calls == []
    assert table == {"role": "urn:synthetic:notes:0", "title": "Debt (Tables)"}


@pytest.mark.asyncio
@pytest.mark.parametrize("frame", [None, pd.DataFrame()])
async def test_absent_or_empty_frames_preserve_table_metadata(monkeypatch, frame):
    output, calls = await _invoke(monkeypatch, [frame])
    table = output["data"]["notes"][0]["tables"][0]
    assert calls == [0]
    assert table == {"role": "urn:synthetic:notes:0", "title": "Debt (Tables)"}
