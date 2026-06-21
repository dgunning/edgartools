"""Regression tests for the EX-FILING FEES XBRL *consumers*.

Three fixes that wire the already-parsed fee exhibit into the deal-sizing
and offering-type paths (edgartools-s9uo / 2l2i / ejk5). All tests run
network-free: the Deal cascade is exercised with lightweight fakes, and the
classifier's XBRL fallback reuses the committed exhibit fixture.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from edgar.offerings.prospectus import (
    Deal,
    OfferingType,
    _MIN_PLAUSIBLE_DEAL_SIZE,
)
from edgar.offerings._424b_classifier import (
    classify_offering_type,
    _classify_from_security_type,
)

FIXTURE = Path(__file__).parent / "fixtures" / "ex_filing_fees_0001193125-25-155880.html"


# ---------------------------------------------------------------------------
# ejk5 — the 'ipo' OfferingType
# ---------------------------------------------------------------------------

def test_ipo_offering_type_exists():
    assert OfferingType("ipo") is OfferingType.IPO
    assert OfferingType.IPO.display_name == "IPO"
    # IPOs are fixed-price equity offerings.
    assert OfferingType.IPO.is_equity is True
    assert OfferingType.IPO.has_fixed_price is True


# ---------------------------------------------------------------------------
# s9uo — Deal.gross_proceeds reads the authoritative XBRL total
# ---------------------------------------------------------------------------

class _FakeCover:
    def __init__(self, amount=None, price=None):
        self.offering_amount_float = amount
        self.offering_price_float = price


class _FakeFees:
    def __init__(self, total=None):
        self.total_offering_amount = total


class _FakeProspectus:
    """Minimal stand-in exposing only what Deal.gross_proceeds touches."""

    def __init__(self, cover_amount=None, cover_price=None, fees_total=None):
        self.cover_page = _FakeCover(cover_amount, cover_price)
        self.filing_fees = _FakeFees(fees_total)
        self.pricing = None
        self.offering_terms = None


def _gross(**kw):
    return Deal(_FakeProspectus(**kw)).gross_proceeds


def test_gross_proceeds_prefers_plausible_cover():
    # Clean equity cover value — used directly, no exhibit download needed.
    assert _gross(cover_amount=500_000_000.0) == 500_000_000.0


def test_gross_proceeds_falls_back_to_xbrl_when_cover_missing():
    # ATM: cover has no fixed amount; the XBRL total fills it (the Strategy
    # 424B5 case — $4.2B registered, "at-the-market" cover).
    assert _gross(cover_amount=None, fees_total="4,200,000,000") == 4_200_000_000.0


def test_gross_proceeds_xbrl_supersedes_denomination_artifact():
    # Cover regex grabbed a $1,000 per-note denomination; the authoritative
    # XBRL total must win over the artifact.
    assert _gross(cover_amount=1_000.0, fees_total="750,000,000") == 750_000_000.0


def test_gross_proceeds_nulls_artifact_when_no_other_source():
    # $1,000 is below the plausibility floor and there is nothing to fall back
    # to -> None, never the artifact value.
    assert _gross(cover_amount=1_000.0) is None
    assert 1_000.0 < _MIN_PLAUSIBLE_DEAL_SIZE


def test_gross_proceeds_none_when_no_signal():
    assert _gross() is None


# ---------------------------------------------------------------------------
# 2l2i — classify_offering_type consults the XBRL security type
# ---------------------------------------------------------------------------

def test_security_type_mapping():
    assert _classify_from_security_type(["Non-Convertible Debt"]) == (
        "debt_offering", "medium", ["xbrl_security_type:debt"])
    assert _classify_from_security_type(["Asset-Backed Securities"]) == (
        "debt_offering", "medium", ["xbrl_security_type:debt"])
    assert _classify_from_security_type(["Equity"]) == (
        "firm_commitment", "low", ["xbrl_security_type:equity"])
    assert _classify_from_security_type([None, ""]) is None


class _FakeDoc:
    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text


class _FakeAttachment:
    document_type = "EX-FILING FEES"
    url = "https://www.sec.gov/Archives/exhibit.htm"

    def __init__(self, content):
        self._content = content

    def download(self):
        return self._content


class _FakeFiling:
    def __init__(self, form, attachments=()):
        self.form = form
        self.attachments = list(attachments)


def test_classifier_falls_back_to_xbrl_security_type():
    """Inconclusive cover text -> resolve via the fee exhibit, not 'unknown'.

    Neutral cover text fires no keyword signal, so the cascade reaches the
    structural fallback, which reads the committed Equity exhibit.
    """
    neutral = _FakeDoc("Generic cover paragraph with no classifier keywords.")
    filing = _FakeFiling("424B5", attachments=[_FakeAttachment(FIXTURE.read_bytes())])
    result = classify_offering_type(filing, document=neutral)
    assert result["type"] == "firm_commitment"
    assert result["confidence"] == "low"
    assert "xbrl_security_type:equity" in result["signals"]


def test_classifier_unknown_when_no_text_and_no_exhibit():
    """Silence check: no signal and no fee exhibit still degrades to unknown."""
    neutral = _FakeDoc("Generic cover paragraph with no classifier keywords.")
    filing = _FakeFiling("424B5", attachments=[])
    result = classify_offering_type(filing, document=neutral)
    assert result["type"] == "unknown"
    assert result["confidence"] == "low"
