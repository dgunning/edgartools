"""13F compare_holdings() and holding_history() match a position by (Cusip, PutCall).

Bank of America Corp, 13F-HR for 2024-06-30 (accession 0001675365-24-000040) and for
2024-09-30 (accession 0001102113-24-000030). `holdings` already aggregates by
(Cusip, PutCall), but both methods merged on Cusip alone, so equity, Put and Call rows
on one CUSIP cross-joined (AFLAC 001055102: 3 x 3 = 9 rows) and 3M's new Put and Call
positions were reported as DECREASED against its common stock.

The fixture keeps the original information-table entries for three CUSIPs only; see
tests/fixtures/13f/bofa-1848/README.md. Offline.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1848
"""
from pathlib import Path

import pandas as pd
import pytest

from edgar import ThirteenF

pytestmark = pytest.mark.fast

DATA = Path(__file__).resolve().parents[2] / "fixtures" / "13f" / "bofa-1848"
Q2, Q3 = "q2-2024", "q3-2024"
ACCESSION = {Q2: "0001675365-24-000040", Q3: "0001102113-24-000030"}


@pytest.fixture
def reports(monkeypatch):
    import importlib
    from types import SimpleNamespace
    parser = importlib.import_module("edgar.thirteenf.parsers.infotable_xml")
    monkeypatch.setattr(parser, "cusip_ticker_mapping",
                        lambda **kwargs: pd.DataFrame({"Ticker": pd.Series(dtype=str)}))
    monkeypatch.setattr(ThirteenF, "_cache_provider", None)
    monkeypatch.setattr(ThirteenF, "_get_infotable_from_attachment",
                        lambda self: ((DATA / f"infotable-{self._tag}.xml").read_text(), "xml"))

    def make(tag):
        filing = SimpleNamespace(
            form="13F-HR", accession_no=ACCESSION[tag], filing_date="2024-11-14",
            xml=lambda: (DATA / f"primary-{tag}.xml").read_text())
        report = ThirteenF(filing)
        report._tag = tag
        return report

    previous, current = make(Q2), make(Q3)
    monkeypatch.setattr(current, "previous_holding_report", lambda: previous, raising=False)
    monkeypatch.setattr(previous, "previous_holding_report", lambda: None, raising=False)
    return previous, current


def _row(df, cusip, put_call):
    rows = df[(df["Cusip"] == cusip) & (df["PutCall"] == put_call)]
    assert len(rows) == 1, (cusip, put_call, len(rows))
    return rows.iloc[0]


def test_comparison_pairs_like_designations(reports):
    _, current = reports
    df = current.compare_holdings().data

    # 3M: common 3,334,472 -> 4,104,023; Put and Call are NEW in Q3 (filed Q3 Call 48,800).
    assert len(df[df["Cusip"] == "88579Y101"]) == 3
    common = _row(df, "88579Y101", "")
    assert (common["PrevShares"], common["Shares"], common["ShareChange"], common["Status"]) == (
        3_334_472, 4_104_023, 769_551, "INCREASED")
    call = _row(df, "88579Y101", "Call")
    assert call["Shares"] == 48_800 and pd.isna(call["PrevShares"]) and call["Status"] == "NEW"
    assert call["Value"] == 6_670_960
    assert _row(df, "88579Y101", "Put")["Status"] == "NEW"

    # AFLAC: three like-designation pairs, not nine.
    aflac = df[df["Cusip"] == "001055102"]
    assert len(aflac) == 3
    assert _row(df, "001055102", "Call")[["PrevShares", "Shares"]].tolist() == [100, 7_700]
    assert _row(df, "001055102", "Put")[["PrevShares", "Shares"]].tolist() == [2_300, 9_800]
    assert _row(df, "001055102", "")[["PrevShares", "Shares"]].tolist() == [3_831_934, 2_975_036]

    # ATA Creativity control: 400 -> 400 shares, value 327 -> 308, UNCHANGED.
    ata = _row(df, "00211V106", "")
    assert (ata["PrevShares"], ata["Shares"], ata["Status"]) == (400, 400, "UNCHANGED")

    # Equity rows survive and totals equal the filed rows instead of multiplying them.
    assert len(df) == 3 + 3 + 1
    assert df["Value"].sum() == current.holdings["Value"].sum()


def test_history_pairs_like_designations(reports):
    _, current = reports
    df = current.holding_history(periods=2).data

    assert len(df[df["Cusip"] == "001055102"]) == 3
    assert _row(df, "88579Y101", "")[["2024-06-30", "2024-09-30"]].tolist() == [3_334_472, 4_104_023]
    put = _row(df, "88579Y101", "Put")
    assert pd.isna(put["2024-06-30"]) and put["2024-09-30"] == 55_400
    assert len(df) == 7


def test_rendering_shows_put_call_only_when_present(reports):
    from rich.console import Console
    previous, current = reports

    def render(obj):
        console = Console(width=200, record=True, file=open("/dev/null", "w"))
        console.print(obj)
        return console.export_text()

    text = render(current.compare_holdings())
    assert "Put/Call" in text and "Call" in text and "Put" in text
    assert "Put/Call" in render(current.holding_history(periods=2))


def test_rendering_has_no_put_call_column_without_options():
    from rich.console import Console

    from edgar.thirteenf.models import HoldingsComparison
    from edgar.thirteenf.rendering import render_holdings_comparison
    df = pd.DataFrame([{
        "Cusip": "00211V106", "Ticker": None, "Issuer": "ATA CREATIVITY", "PutCall": "",
        "Shares": 400, "PrevShares": 400, "Value": 308, "PrevValue": 327, "ShareChange": 0,
        "ShareChangePct": 0.0, "ValueChange": -19, "ValueChangePct": -5.8, "Status": "UNCHANGED"}])
    console = Console(width=200, record=True, file=open("/dev/null", "w"))
    console.print(render_holdings_comparison(HoldingsComparison(df, "Q3", "Q2", "BofA")))
    assert "Put/Call" not in console.export_text()


@pytest.mark.asyncio
async def test_mcp_comparison_names_the_option_rows():
    """The MCP comparison payload says which of a CUSIP's rows is the Put or Call."""
    from unittest.mock import MagicMock, patch

    from edgar.ai.mcp.tools.ownership import edgar_ownership

    df = pd.DataFrame([
        {"Ticker": None, "Issuer": "3M CO", "Cusip": "88579Y101", "PutCall": "Call", "Status": "NEW",
         "Shares": 48_800, "Value": 6_670_960, "PrevShares": None, "PrevValue": None,
         "ShareChange": None, "ShareChangePct": None, "ValueChange": None},
        {"Ticker": None, "Issuer": "3M CO", "Cusip": "88579Y101", "PutCall": "", "Status": "INCREASED",
         "Shares": 4_104_023, "Value": 561_019_905, "PrevShares": 3_334_472, "PrevValue": 340_749_757,
         "ShareChange": 769_551, "ShareChangePct": 23.1, "ValueChange": 220_270_148},
    ])
    thirteen_f = MagicMock()
    thirteen_f.compare_holdings.return_value = MagicMock(
        data=df, current_period="2024-09-30", previous_period="2024-06-30")
    filing = MagicMock(filing_date="2024-11-14", accession_number=ACCESSION[Q3])
    filing.obj.return_value = thirteen_f
    filings = MagicMock()
    filings.__len__.return_value = 1
    filings.__getitem__.return_value = filing
    company = MagicMock(cik=70858)
    company.name = "BANK OF AMERICA CORP /DE/"
    company.get_filings.return_value = filings

    with patch("edgar.ai.mcp.tools.ownership.resolve_company", return_value=company):
        response = await edgar_ownership(identifier="70858", analysis_type="portfolio_diff", limit=10)

    changes = response.data["changes"]
    assert [c.get("put_call") for c in changes] == ["Call", None]
