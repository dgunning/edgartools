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
    Prospectus424B,
    CoverPageData,
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
    def __init__(self, amount=None, price=None, security_description=None):
        self.offering_amount_float = amount
        self.offering_price_float = price
        self.security_description = security_description


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


# ---------------------------------------------------------------------------
# #1 — the IPO promotion requires an assertive 'this is an IPO' phrase
# ---------------------------------------------------------------------------

_IPO_COVER = _FakeDoc(
    "This is an initial public offering of common stock. "
    "The underwriters have a 30-day option to purchase additional shares."
)
# A follow-on that merely references its past IPO — same 'initial public
# offering' substring, but NOT 'this is an initial public offering'.
_FOLLOWON_COVER = _FakeDoc(
    "Since our initial public offering in 2021 we have grown. "
    "The underwriters have a 30-day option to purchase additional shares."
)


def test_ipo_promotion_on_ipo_form_with_assertive_phrase():
    result = classify_offering_type(_FakeFiling("424B4"), document=_IPO_COVER)
    assert result["type"] == "ipo"


def test_no_ipo_promotion_for_followon_reference():
    # 424B4, but the cover only references a past IPO -> stays firm_commitment.
    result = classify_offering_type(_FakeFiling("424B4"), document=_FOLLOWON_COVER)
    assert result["type"] == "firm_commitment"


def test_no_ipo_promotion_on_shelf_takedown_form():
    # Assertive IPO text but on a 424B5 takedown form -> stays firm_commitment.
    result = classify_offering_type(_FakeFiling("424B5"), document=_IPO_COVER)
    assert result["type"] == "firm_commitment"


# ---------------------------------------------------------------------------
# #4 — the fee exhibit is fetched at most once
# ---------------------------------------------------------------------------

class _CountingAttachment(_FakeAttachment):
    def __init__(self, content):
        super().__init__(content)
        self.downloads = 0

    def download(self):
        self.downloads += 1
        return self._content


def test_injected_filing_fees_avoids_download():
    """Passing pre-parsed fee data must not trigger an exhibit download."""
    att = _CountingAttachment(FIXTURE.read_bytes())
    filing = _FakeFiling("424B5", attachments=[att])
    neutral = _FakeDoc("Generic cover paragraph with no classifier keywords.")
    injected = {"has_exhibit": True, "offering_rows": [{"security_type": "Equity"}]}
    result = classify_offering_type(filing, document=neutral, filing_fees=injected)
    assert result["type"] == "firm_commitment"
    assert att.downloads == 0


def test_filing_fees_none_suppresses_fallback_fetch():
    """filing_fees=None suppresses the fallback entirely (no fetch, unknown)."""
    att = _CountingAttachment(FIXTURE.read_bytes())
    filing = _FakeFiling("424B5", attachments=[att])
    neutral = _FakeDoc("Generic cover paragraph with no classifier keywords.")
    result = classify_offering_type(filing, document=neutral, filing_fees=None)
    assert result["type"] == "unknown"
    assert att.downloads == 0


def test_default_fetches_exhibit_once():
    """Default (no filing_fees arg) fetches the exhibit exactly once."""
    att = _CountingAttachment(FIXTURE.read_bytes())
    filing = _FakeFiling("424B5", attachments=[att])
    neutral = _FakeDoc("Generic cover paragraph with no classifier keywords.")
    result = classify_offering_type(filing, document=neutral)
    assert result["type"] == "firm_commitment"  # fixture is Equity
    assert att.downloads == 1


# ---------------------------------------------------------------------------
# drzj — classifier confidence + signals are reachable on the public API
# ---------------------------------------------------------------------------

class _ProvenanceFakeProspectus:
    """Stand-in exposing everything Deal.to_dict reads, defaulting to None."""

    def __init__(self, confidence="low", signals=None,
                 offering_type=OfferingType.FIRM_COMMITMENT, is_atm=False):
        self.cover_page = _FakeCover()
        self.filing_fees = _FakeFees(None)
        self.pricing = None
        self.offering_terms = None
        self.underwriting = None
        self.dilution = None
        self.offering_type = offering_type
        self.offering_type_confidence = confidence
        self.offering_type_signals = list(signals or [])
        self.is_atm = is_atm


def test_prospectus_exposes_classifier_provenance():
    p = Prospectus424B(
        filing=_FakeFiling("424B5"),
        cover_page=CoverPageData(company_name="Test Co"),
        offering_type=OfferingType.FIRM_COMMITMENT,
        confidence="low",
        signals=["xbrl_security_type:equity"],
        sub_type=None,
    )
    assert p.offering_type_confidence == "low"
    assert p.offering_type_signals == ["xbrl_security_type:equity"]
    assert p.offering_type_sub_type is None
    # The accessor returns a copy — caller mutation can't corrupt the object.
    p.offering_type_signals.append("x")
    assert p.offering_type_signals == ["xbrl_security_type:equity"]


def test_prospectus_provenance_defaults_empty():
    p = Prospectus424B(
        filing=_FakeFiling("424B5"),
        cover_page=CoverPageData(company_name="X"),
        offering_type=OfferingType.UNKNOWN,
        confidence="low",
    )
    assert p.offering_type_signals == []
    assert p.offering_type_sub_type is None


def test_deal_delegates_provenance_and_serializes_it():
    d = Deal(_ProvenanceFakeProspectus(
        confidence="low", signals=["xbrl_security_type:equity"]))
    assert d.offering_type_confidence == "low"
    assert d.offering_type_signals == ["xbrl_security_type:equity"]
    out = d.to_dict()
    # The §4 tiering directive is now serializable: a consumer can see the
    # equity-prior provenance and exclude this row from issuer-proceeds sums.
    assert out["offering_type_confidence"] == "low"
    assert out["offering_type_signals"] == ["xbrl_security_type:equity"]


def test_deal_to_dict_omits_empty_signals():
    out = Deal(_ProvenanceFakeProspectus(confidence="high", signals=[])).to_dict()
    assert "offering_type_signals" not in out
    assert out["offering_type_confidence"] == "high"
