"""
Regression test for GitHub issue #1252: entity_info['ticker'] was the cover's last symbol

A cover lists one dei:TradingSymbol per registered security. entity_info kept
DEI facts in a dict, so the last symbol won, and on every tracked filing whose
cover lists several securities that was a note or an ETN, not the common
stock: JPMorgan's FY2023 10-K came back as AMJB.

entity_info['ticker'] is now the first of the filer's own symbols in document
order, and entity_info['trading_symbols'] (also TenK/TenQ.trading_symbols)
lists all of them with the class-of-stock member that names each security.
The co-registrant rule of GH #1420 and #1710 still decides whose symbols count.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1252
"""

from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pytest

from edgar.company_reports import TenK, TenQ
from edgar.financials import Financials
from edgar.xbrl import XBRL
from edgar.xbrl.parsers import XBRLParser

FIXTURES = Path("tests/fixtures/xbrl")

# JPMorgan Chase FY2023 10-K, 0000019617-24-000225
JPM = FIXTURES / "jpm/10k_2024/jpm-20240216_htm.xml"
# Coca-Cola FY2023 10-K, 0000021344-24-000009
KO = FIXTURES / "ko/10k_2024/ko-20240220_htm.xml"
# Exxon Mobil FY2022 10-K, 0000034088-23-000020 (CapitalUnitsByClassAxis, not StatementClassOfStockAxis)
XOM = FIXTURES / "xom/10k_2023/xom-20221231_htm.xml"
# Netflix FY2023 10-K, 0001065280-24-000030: one symbol, in a context with no class-of-stock member
NFLX = FIXTURES / "nflx/10k_2024/nflx-20240126_htm.xml"


@lru_cache(maxsize=None)
def _xbrl(path):
    return XBRL.from_files(instance_file=path)


def _symbols(info):
    return [entry["symbol"] for entry in info["trading_symbols"]]


def test_jpm_ticker_is_the_common_stock_not_the_last_etn():
    info = _xbrl(JPM).entity_info
    assert info["ticker"] == "JPM"
    assert _symbols(info) == [
        "JPM", "JPM PR D", "JPM PR C", "JPM PR J", "JPM PR K", "JPM PR L", "JPM PR M", "AMJ", "JPM/32", "AMJB",
    ]


def test_jpm_symbols_carry_their_class_of_stock_member_and_context():
    symbols = _xbrl(JPM).entity_info["trading_symbols"]
    assert symbols[0] == {"symbol": "JPM", "class_of_stock": "us-gaap:CommonStockMember", "context_ref": "c-2"}
    assert symbols[1]["class_of_stock"] == (
        "jpm:DepositarySharesOneFourHundredthInterestinaShareof5.75NonCumulativePreferredStockSeriesDDMember"
    )
    assert symbols[-1] == {
        "symbol": "AMJB",
        "class_of_stock": "jpm:GuaranteeOfAlerianMLPIndexETNsDueJanuary282044OfJPMorganChaseFinancialCompanyLLCMember",
        "context_ref": "c-11",
    }


def test_ko_ticker_is_the_common_stock_of_sixteen_symbols():
    info = _xbrl(KO).entity_info
    assert info["ticker"] == "KO"
    assert _symbols(info) == [
        "KO", "KO24", "KO26", "KO26C", "KO27", "KO29A", "KO29B", "KO30B",
        "KO31", "KO33", "KO33A", "KO35", "KO36", "KO36A", "KO40B", "KO41",
    ]
    assert info["trading_symbols"][0]["class_of_stock"] == "ko:CommonStock0.25ParValueMember"


def test_xom_class_of_stock_comes_from_capital_units_by_class_axis():
    info = _xbrl(XOM).entity_info
    assert info["ticker"] == "XOM"
    assert _symbols(info) == ["XOM", "XOM24B", "XOM28", "XOM32", "XOM39A"]
    assert info["trading_symbols"][0]["class_of_stock"] == "us-gaap:CommonStockMember"
    assert info["trading_symbols"][-1]["class_of_stock"] == "xom:OnePointFourZeroEightPercentNotesDue2039Member"


def test_single_symbol_cover_is_unchanged():
    info = _xbrl(NFLX).entity_info
    assert info["ticker"] == "NFLX"
    assert info["trading_symbols"] == [{"symbol": "NFLX", "class_of_stock": None, "context_ref": "c-1"}]


# --- synthetic covers, cut down to the facts entity_info reads ---------------

def _parse(*facts, contexts=()):
    body = "\n".join(contexts) + "\n" + "\n".join(facts)
    parser = XBRLParser()
    parser.parse_instance_content(f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:dei="http://xbrl.sec.gov/dei/2025"
      xmlns:us-gaap="http://fasb.org/us-gaap/2025" xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
      xmlns:pld="http://www.prologis.com/20251231">
{body}
</xbrl>
""")
    return parser.entity_info


def _context(context_id, *dimensions):
    members = "".join(f'<xbrldi:explicitMember dimension="{axis}">{member}</xbrldi:explicitMember>'
                      for axis, member in dimensions)
    segment = f"<segment>{members}</segment>" if members else ""
    return (f'<context id="{context_id}"><entity><identifier scheme="http://www.sec.gov/CIK">0001045609</identifier>'
            f'{segment}</entity><period><startDate>2025-01-01</startDate><endDate>2025-12-31</endDate></period>'
            "</context>")


def _symbol(context_id, value):
    return f'<dei:TradingSymbol contextRef="{context_id}">{value}</dei:TradingSymbol>'


CLASS = "us-gaap:StatementClassOfStockAxis"
LP = ("dei:LegalEntityAxis", "pld:PrologisLimitedPartnershipMember")


def test_co_registrant_symbols_stay_out_while_the_filer_has_its_own():
    # Prologis FY2025 10-K (0001193125-26-051453): the notes belong to the
    # co-registrant Prologis, L.P. (GH #1420).
    info = _parse(
        _symbol("common", "PLD"), _symbol("notes-2029", "PLD/29"), _symbol("notes-2040", "PLD/40"),
        contexts=[
            _context("common", (CLASS, "us-gaap:CommonStockMember")),
            _context("notes-2029", (CLASS, "pld:NotesDue2029Member"), LP),
            _context("notes-2040", (CLASS, "pld:NotesDue2040Member"), LP),
        ],
    )
    assert info["ticker"] == "PLD"
    assert info["trading_symbols"] == [
        {"symbol": "PLD", "class_of_stock": "us-gaap:CommonStockMember", "context_ref": "common"},
    ]


def test_co_registrant_symbols_are_used_when_the_filer_has_none():
    info = _parse(_symbol("lp", "PLD/29"), contexts=[_context("filer"), _context("lp", LP)])
    assert info["ticker"] == "PLD/29"
    assert _symbols(info) == ["PLD/29"]


def test_a_repeated_symbol_keeps_its_document_position():
    # A duplicated fact is re-keyed when its second copy is read, which moves
    # its first copy behind the facts in between; document order must not.
    info = _parse(
        _symbol("common", "ABC"), _symbol("notes", "ABC27"), _symbol("common", "ABC"),
        contexts=[_context("common", (CLASS, "us-gaap:CommonStockMember")),
                  _context("notes", (CLASS, "pld:NotesDue2027Member"))],
    )
    assert info["ticker"] == "ABC"
    assert _symbols(info) == ["ABC", "ABC27", "ABC"]


def test_no_symbol_means_no_ticker_and_an_empty_list():
    info = _parse('<dei:DocumentType contextRef="filer">10-K</dei:DocumentType>', _symbol("filer", ""),
                  contexts=[_context("filer")])
    assert info["ticker"] is None
    assert info["trading_symbols"] == []


# --- TenK / TenQ -------------------------------------------------------------

def _report(cls, form, xbrl):
    report = cls(SimpleNamespace(form=form))
    report.__dict__["financials"] = Financials(xbrl) if xbrl is not None else None
    return report


def test_tenk_trading_symbols_reuse_the_loaded_xbrl():
    tenk = _report(TenK, "10-K", _xbrl(JPM))
    assert [s["symbol"] for s in tenk.trading_symbols][:2] == ["JPM", "JPM PR D"]
    assert tenk.trading_symbols[0]["class_of_stock"] == "us-gaap:CommonStockMember"
    # a copy: editing it does not change the XBRL
    tenk.trading_symbols[0]["symbol"] = "edited"
    assert _xbrl(JPM).entity_info["trading_symbols"][0]["symbol"] == "JPM"


@pytest.mark.parametrize("cls, form", [(TenK, "10-K"), (TenQ, "10-Q")])
def test_trading_symbols_without_xbrl_is_an_empty_list(cls, form):
    assert _report(cls, form, None).trading_symbols == []
