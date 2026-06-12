"""
Regression test for Issue #850: Normalize currency unit identifiers to ISO 4217.

Problem: ``xbrl().facts.to_dataframe()`` exposed the raw XBRL ``unit_ref`` id for
every fact. For non-USD filers the unit id is an opaque token such as
``UNIT_STANDARD_HKD_MNUSOXGRF0O9R60JINVDUQ`` instead of a usable currency, which
made currency-based filtering and display unreliable for foreign companies.

Fix: the facts DataFrame now carries a ``currency`` column that resolves each
fact's unit to its ISO 4217 code (e.g. ``HKD``) via the parsed unit measure
(``iso4217:HKD``). The opaque ``unit_ref`` is preserved unchanged; non-monetary
units (shares, pure, custom) resolve to ``None`` rather than a misleading value.

Reporter: warzoo
See: https://github.com/dgunning/edgartools/issues/850
"""

from pathlib import Path

from edgar.xbrl import XBRL

# A minimal XBRL instance whose currency unit uses the opaque id from the issue.
FOREIGN_INSTANCE = """<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance"
      xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
      xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:us-gaap="http://fasb.org/us-gaap/2023">
  <context id="c1">
    <entity><identifier scheme="http://www.sec.gov/CIK">0001234567</identifier></entity>
    <period><startDate>2024-01-01</startDate><endDate>2024-12-31</endDate></period>
  </context>
  <unit id="UNIT_STANDARD_HKD_MNUSOXGRF0O9R60JINVDUQ">
    <measure>iso4217:HKD</measure>
  </unit>
  <us-gaap:Revenues contextRef="c1"
      unitRef="UNIT_STANDARD_HKD_MNUSOXGRF0O9R60JINVDUQ" decimals="-3">1500000</us-gaap:Revenues>
</xbrl>
"""


def test_unit_currency_helper():
    """``_unit_currency`` extracts the ISO 4217 code, ignoring non-currency units."""
    from edgar.xbrl.facts import _unit_currency

    assert _unit_currency({"type": "simple", "measure": "iso4217:HKD"}) == "HKD"
    assert _unit_currency({"type": "simple", "measure": "iso4217:USD"}) == "USD"
    # Per-share monetary units (currency / shares) report the numerator currency.
    assert _unit_currency({"type": "divide", "numerator": ["iso4217:USD"], "denominator": ["xbrli:shares"]}) == "USD"
    # Non-monetary or unknown units resolve to None, not a misleading value.
    assert _unit_currency({"type": "simple", "measure": "shares"}) is None
    assert _unit_currency({"type": "simple", "measure": "xbrli:pure"}) is None
    assert _unit_currency(None) is None


def test_opaque_unit_ref_resolves_to_iso4217_currency(tmp_path):
    """The issue's repro: an opaque HKD unit id resolves to ``HKD`` in ``currency``."""
    instance_file = tmp_path / "foreign.xml"
    instance_file.write_text(FOREIGN_INSTANCE)

    xbrl = XBRL.from_files(instance_file=instance_file)
    df = xbrl.facts.to_dataframe()

    assert "currency" in df.columns
    revenue = df[df["concept"].str.contains("Revenue", case=False, na=False)]
    assert len(revenue) == 1
    # The opaque unit_ref is preserved unchanged ...
    assert revenue["unit_ref"].iloc[0] == "UNIT_STANDARD_HKD_MNUSOXGRF0O9R60JINVDUQ"
    # ... and the currency is now the usable ISO 4217 code.
    assert revenue["currency"].iloc[0] == "HKD"


def test_currency_column_ground_truth_aapl():
    """A real filing (AAPL 10-K) resolves monetary facts to their currency codes."""
    aapl = XBRL.from_directory(Path("tests/fixtures/xbrl/aapl/10k_2023"))
    df = aapl.facts.to_dataframe()

    assert "currency" in df.columns
    # USD-denominated facts resolve to "USD" (not the raw "usd" unit id) ...
    usd = df[df["currency"] == "USD"]
    assert len(usd) > 100
    assert (usd["unit_ref"] == "usd").any()
    # ... and per-share amounts (unit_ref "usdPerShare") also resolve to USD.
    assert (df.loc[df["unit_ref"] == "usdPerShare", "currency"] == "USD").all()
    # Silence check: share-count facts are not a currency, so currency is None.
    shares = df[df["unit_ref"] == "shares"]
    assert len(shares) > 0
    assert shares["currency"].isna().all()
