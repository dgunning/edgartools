"""The bundled AI skill files describe what edgartools does on main.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1591

The skill files under edgar/ai/skills are read by an agent before it writes
code, so a stale line teaches the wrong call. Four kinds of statement had fallen
behind main:

  1. A filing with no XBRL was said to raise the MCP error code NO_XBRL_DATA.
     Nothing raises XBRLFilingWithNoXbrlData on main: get_financials() returns
     None for such a filing (docs/upgrade/6.0.md, the get_financials row).
  2. filing.document was written as a method. It is a property that returns an
     Attachment, so filing.document() raises TypeError.
  3. A missing item was said to read as None (tenk['Item 15'], forty_f['Item 1']).
     Both raise SectionNotFoundError. report.get(item, default) is the form that
     never raises.
  4. Section text was read with .text (tenk.risk_factors.text). A section is a
     str, so it has no .text. And find('AAPL') returns an Entity, which has no
     get_financials().

The static tests read the example files (EXAMPLE_FILES) and fail while one of those
statements remains. The behaviour tests run the corrected forms against Apple's
FY2024 10-K (the SGML copy in data/sgml, accession 0000320193-24-000123, filed
2024-11-01), so each corrected example is checked against a real filing and not
only against the text that now describes it.
"""
import re
from types import SimpleNamespace

import pytest
import yaml

import edgar
from edgar import Company, Entity, Filing
from edgar.company_reports import FortyF
from edgar.exceptions import SectionNotFoundError
from edgar.financials import Financials
from edgar.xbrl.xbrl import XBRL
from tests.paths import REPO_ROOT

SKILLS_DIR = REPO_ROOT / "edgar" / "ai" / "skills"
APPLE_10K_SGML = REPO_ROOT / "data" / "sgml" / "0000320193-24-000123.txt"

# The agent-facing files the examples live in. core/validations.yaml is not
# scanned: it does not parse as YAML, and nothing loads it.
EXAMPLE_FILES = ("core/skill.yaml", "core/sharp-edges.yaml", "reports/skill.yaml", "reports/sharp-edges.yaml")


def _example_text() -> str:
    """Every string in the example files, including the regexes that match an agent's code.

    The ``pattern`` and ``detection_pattern`` keys are checked too. The ``avoid``
    entry's ``pattern`` names a call an agent must not write, so a stale call there
    would be taught as well as detected.
    """
    strings = []

    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str):
            strings.append(node)

    for name in EXAMPLE_FILES:
        walk(yaml.safe_load((SKILLS_DIR / name).read_text(encoding="utf-8")))
    return "\n".join(strings)


# ---------------------------------------------------------------------------
# Static: the skill text no longer carries the stale statements
# ---------------------------------------------------------------------------

def test_examples_do_not_name_the_no_xbrl_error_code():
    """NO_XBRL_DATA maps XBRLFilingWithNoXbrlData, and nothing raises that on main."""
    text = _example_text()
    assert "NO_XBRL_DATA" not in text
    assert "XBRLFilingWithNoXbrlData" not in text


@pytest.mark.parametrize("stale, why", [
    (r"\.document\(\)", "filing.document is a property, so calling it raises TypeError"),
    (r"risk_factors\.text", "tenk.risk_factors is a str and has no .text"),
    (r"\bitem\.(?:text|title)\b", "a section read by item key or convenience property is a str"),
    (r"Ticker\s*→\s*Company", "find() returns an Entity for a ticker, which has no get_financials()"),
    (r"\[['\"]Item[^\]\n]*['\"]\]\s*(?:→|is|->)\s*None",
     "a missing item raises SectionNotFoundError; it does not read as None"),
])
def test_skill_examples_do_not_repeat_the_stale_form(stale, why):
    match = re.search(stale, _example_text())
    assert match is None, f"{why}. Found {match.group(0)!r}"


# ---------------------------------------------------------------------------
# Behaviour: the corrected forms run on Apple's FY2024 10-K
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def apple_10k():
    """Apple's FY2024 10-K (accession 0000320193-24-000123), from its SGML copy."""
    return Filing.from_sgml(str(APPLE_10K_SGML))


def test_document_is_read_as_a_property(apple_10k):
    """filing.document.text() reads the filing; filing.document() is a call on an Attachment."""
    text = apple_10k.document.text()
    # Cover page: "15,115,823,000 shares of common stock were issued and outstanding"
    assert "15,115,823,000" in text
    with pytest.raises(TypeError):
        apple_10k.document()


def test_missing_item_raises_and_get_returns_the_default(apple_10k):
    tenk = apple_10k.obj()
    with pytest.raises(SectionNotFoundError, match="Item 99"):
        tenk["Item 99"]
    assert tenk.get("Item 99", "") == ""
    assert tenk.get("Item 99") is None


def test_section_text_is_a_string(apple_10k):
    tenk = apple_10k.obj()
    risk_factors = tenk.risk_factors
    assert isinstance(risk_factors, str)
    assert "Risk Factors" in risk_factors[:200]
    assert len(risk_factors) > 50_000
    assert tenk["Item 1A"] == risk_factors
    assert not hasattr(risk_factors, "text")


def test_ticker_lookup_builds_an_entity_without_financials(monkeypatch):
    """find('AAPL') constructs an Entity. Entity has no get_financials(); Company does."""
    built = []

    class _Entity:
        def __init__(self, identifier):
            built.append(identifier)

    monkeypatch.setattr(edgar, "Entity", _Entity)
    result = edgar.find.__wrapped__("AAPL")
    assert built == ["AAPL"]
    assert isinstance(result, _Entity)
    assert not hasattr(Entity, "get_financials")
    assert hasattr(Company, "get_financials")


def test_forty_f_missing_section_raises_and_get_returns_the_default():
    """A 40-F has no US Item numbers, so forty_f['Item 1'] raises like any missing section."""
    forty_f = object.__new__(FortyF)
    forty_f._filing = SimpleNamespace(accession_number="0001594805-24-000007")  # Shopify 40-F
    forty_f.__dict__["aif_text"] = ""  # no AIF text, so there are no section headers
    with pytest.raises(SectionNotFoundError, match="Item 1"):
        forty_f["Item 1"]
    assert forty_f.get("Item 1", "") == ""


def test_filing_without_xbrl_has_no_financials(apple_10k, monkeypatch):
    """Financials.extract, the step get_financials() takes, answers None rather than an empty object."""
    monkeypatch.setattr(XBRL, "from_filing", classmethod(lambda cls, filing: None))
    assert Financials.extract(apple_10k) is None
