"""
Regression test for edgartools-mun2: 13F holdings Value wrong (+/-1000x) because the
thousands-vs-dollars reporting unit was chosen by a hard-coded report-period date cutoff.

Bug (FIXED): SEC Release 34-96734 switched Form 13F <value> reporting from *thousands* to
*whole dollars* for periods ending on/after 2022-12-31. The reporting unit is a property
of the individual *filing* (which schema/software the filer used), not of the report
period -- during and after the transition, filings for the same report period arrive in
BOTH units. The old code used a single date threshold (`report_period <= 2022-09-30 =>
thousands`), which mis-scaled a meaningful, non-shrinking fraction of filings in BOTH
directions:

  1. A post-cutover filing still reporting in thousands was left unscaled => 1000x too
     small (e.g. Boulder Wealth Advisors, AAPL, 5,896 sh at 2022-12-31: Value=766 returned
     as $766 instead of $766,000).
  2. A pre-cutover period with a late/amended dollar-convention filing was multiplied by
     1000 => 1000x too large (e.g. Voya/MetLife rows for report period 2022-09-30).

Fix: detect the unit per-filing from the holdings themselves. Under the
"as-reported = dollars" hypothesis the implied equity price is Value / SharesPrnAmount; a
real portfolio's median holding price is far above $1 while a thousands-misread one lands
~1000x lower, so the median cleanly separates the two hypotheses (they sit exactly 1000x
apart). The report-period date cutoff survives only as a fallback when a filing has no
priceable equity rows. See `edgar/thirteenf/models.py::_detect_value_in_thousands`.
"""

from datetime import datetime
from decimal import Decimal

import pandas as pd
import pytest

from edgar.thirteenf.models import (
    _13F_VALUE_IN_THOUSANDS_CUTOFF,
    _detect_value_in_thousands,
    _resolve_unit_fallback,
    _schema_implies_dollars,
)

PRE_CUTOVER = datetime(2022, 9, 30)   # <= cutoff: legacy date rule says "thousands"
POST_CUTOVER = datetime(2022, 12, 31)  # >  cutoff: legacy date rule says "dollars"


def _holdings(rows):
    """Build a raw (unscaled) infotable-shaped DataFrame from (value, shares) tuples."""
    return pd.DataFrame([
        {
            "Issuer": f"ISSUER {i}",
            "Cusip": f"{i:09d}",
            "Value": value,
            "SharesPrnAmount": shares,
            "Type": "Shares",
            "PutCall": "",
        }
        for i, (value, shares) in enumerate(rows)
    ])


# A portfolio whose holdings really trade around ~$130/sh, reported in WHOLE DOLLARS:
# implied price = Value / Shares ~ 130, well above $1 => not thousands.
DOLLARS_FILING = _holdings([
    (766_000, 5_896),     # ~$129.92
    (1_299_300, 10_000),  # ~$129.93
    (6_496_500, 50_000),  # ~$129.93
])

# The SAME portfolio reported in THOUSANDS (Value is 1000x smaller): implied price ~ 0.13,
# far below $1 => thousands, must be scaled up by 1000.
THOUSANDS_FILING = _holdings([
    (766, 5_896),     # ~$0.13
    (1_299, 10_000),  # ~$0.13
    (6_496, 50_000),  # ~$0.13
])


def test_dollars_filing_decided_by_prior_when_no_sub_dollar_holdings():
    """A whole-dollar portfolio has no sub-$1 implied prices, so price alone is NOT
    decisive -- it is mathematically indistinguishable from a thousands filing of >$1000
    shares. The unit comes from the prior: the new-schema (X0202) or post-cutover signal
    yields dollars (direction 2: the old rule would have multiplied a pre-cutover-period
    dollar amendment by 1000)."""
    assert _detect_value_in_thousands(DOLLARS_FILING, schema_version='X0202') is False
    assert _detect_value_in_thousands(DOLLARS_FILING, report_period_dt=POST_CUTOVER) is False


def test_thousands_filing_detected_regardless_of_period():
    """A thousands filing IS scaled from price alone, regardless of period or schema
    (direction 1: the old rule would have left a post-cutover thousands filing 1000x too
    small)."""
    assert _detect_value_in_thousands(THOUSANDS_FILING, report_period_dt=POST_CUTOVER) is True
    assert _detect_value_in_thousands(THOUSANDS_FILING, report_period_dt=PRE_CUTOVER) is True
    assert _detect_value_in_thousands(THOUSANDS_FILING, schema_version='X0202') is True


def test_high_price_holder_never_decided_by_magnitude():
    """A BRK.A-style holder must NEVER be forced to a unit by price magnitude (no upper
    cap, per edgartools-mun2): the identical 'no sub-$1 holdings' shape occurs both for a
    genuine high-price dollar portfolio AND for a thousands filer concentrated in >$1000
    shares. The prior decides."""
    # ~$468k/sh reported in dollars: dollars-era prior -> dollars.
    brk_dollars = _holdings([(468_000_000, 1_000), (936_000_000, 2_000)])
    assert _detect_value_in_thousands(brk_dollars, schema_version='X0202') is False
    assert _detect_value_in_thousands(brk_dollars, report_period_dt=POST_CUTOVER) is False
    # BRK.A ~$680k reported in THOUSANDS (value 680 per share) by an on-time pre-cutover
    # filer: fraction sub-$1 is 0, so it defers to the prior, which (old schema / pre-cutover
    # date) correctly yields thousands. The earlier confident-dollars shortcut got this
    # wrong; deferring to the prior fixes it.
    brk_thousands = _holdings([(680, 1), (1_360, 2)])
    assert _detect_value_in_thousands(brk_thousands, report_period_dt=PRE_CUTOVER) is True
    assert _detect_value_in_thousands(brk_thousands, schema_version='X0201') is True


def test_options_and_bonds_ignored_in_detection():
    """Option rows (notional Value) and bond rows (price ~ par ~= 1.0) must not drive the
    decision; only equity (SH) non-option rows are priced."""
    df = pd.DataFrame([
        # Real equity, reported in thousands (implied ~$0.13) -> should win.
        {"Value": 766, "SharesPrnAmount": 5_896, "Type": "Shares", "PutCall": ""},
        {"Value": 1_299, "SharesPrnAmount": 10_000, "Type": "Shares", "PutCall": ""},
        # Bond near par (would read ~1.0 and pollute the statistic) -> excluded.
        {"Value": 1_000_000, "SharesPrnAmount": 1_000_000, "Type": "Principal", "PutCall": ""},
        # Option with notional value -> excluded.
        {"Value": 5_000_000, "SharesPrnAmount": 100, "Type": "Shares", "PutCall": "Call"},
    ])
    assert _detect_value_in_thousands(df, report_period_dt=POST_CUTOVER) is True


def test_pre_split_megacap_thousands_filing_defers_to_prior_not_median():
    """A small THOUSANDS filing dominated by >$1000 pre-split mega-caps has a median
    implied price ABOVE $1 (which would fool a median rule into 'dollars'), but the
    *fraction* of sub-$1 holdings is only ~0.4 -> ambiguous, so it defers to the
    schema/date prior. This is the real-world ACTIAM N.V. (2020-12-31) failure mode.

    Holdings (in thousands): AAPL ~0.13, MSFT ~0.22, GOOGL ~1.75, AMZN ~3.3, BKNG ~2.0.
    Median ~1.75 (> $1); fraction sub-$1 = 2/5 = 0.40 (ambiguous band).
    """
    actiam = _holdings([
        (230, 1_733),  # AAPL  ~0.13
        (224, 1_009),  # MSFT  ~0.22
        (175, 100),    # GOOGL ~1.75 (pre-split)
        (152, 46),     # AMZN  ~3.30 (pre-split)
        (200, 100),    # BKNG  ~2.00
    ])
    # Old schema (no version) + pre-cutover period -> prior says thousands. Correct.
    assert _detect_value_in_thousands(actiam, report_period_dt=PRE_CUTOVER) is True
    # The same ambiguous portfolio under the new-schema prior would be read as dollars,
    # showing the tie is broken by the prior (not by the misleading median).
    assert _detect_value_in_thousands(actiam, schema_version='X0202') is False


def test_confident_thousands_overrides_dollars_schema_prior():
    """A high fraction of sub-$1 holdings is decisive and wins over the schema prior -- this
    is what lets a new-schema (X0202) filing that still reports in thousands be detected
    correctly (the real Bull Street / Abeille / GSA case)."""
    assert _detect_value_in_thousands(THOUSANDS_FILING, schema_version='X0202') is True
    assert _detect_value_in_thousands(
        THOUSANDS_FILING, schema_version='X0202', report_period_dt=POST_CUTOVER) is True


def test_schema_version_prior():
    """The schema-version prior maps versions to a unit, or None when unusable."""
    assert _schema_implies_dollars(None) is None
    assert _schema_implies_dollars('') is None
    assert _schema_implies_dollars('X0202') is True      # whole-dollar era
    assert _schema_implies_dollars('X0203') is True      # later versions too
    assert _schema_implies_dollars('X0201') is False     # older thousands era


def test_fallback_prefers_schema_then_date():
    """For unpriceable (bond-only) filings the fallback consults the schema prior first,
    then the report-period date cutoff."""
    bonds = pd.DataFrame([
        {"Value": 1_000_000, "SharesPrnAmount": 1_000_000, "Type": "Principal", "PutCall": ""},
        {"Value": 2_000_000, "SharesPrnAmount": 2_000_000, "Type": "Principal", "PutCall": ""},
    ])
    # Schema present -> it decides regardless of period.
    assert _detect_value_in_thousands(bonds, schema_version='X0202', report_period_dt=PRE_CUTOVER) is False
    assert _detect_value_in_thousands(bonds, schema_version='X0201', report_period_dt=POST_CUTOVER) is True
    # No schema -> fall back to the date cutoff in both directions.
    assert _detect_value_in_thousands(bonds, report_period_dt=PRE_CUTOVER) is True
    assert _detect_value_in_thousands(bonds, report_period_dt=POST_CUTOVER) is False
    # No schema and no period -> "not thousands" (no scaling).
    assert _detect_value_in_thousands(bonds) is False


def test_empty_holdings_fall_back_to_prior():
    empty = pd.DataFrame(columns=["Value", "SharesPrnAmount", "Type", "PutCall"])
    assert _detect_value_in_thousands(empty, report_period_dt=PRE_CUTOVER) is True
    assert _detect_value_in_thousands(empty, report_period_dt=POST_CUTOVER) is False
    assert _detect_value_in_thousands(empty, schema_version='X0202') is False


def test_cutoff_boundary_is_inclusive():
    """The date fallback cutoff is the documented Q3-2022 boundary, inclusive."""
    assert _resolve_unit_fallback(None, _13F_VALUE_IN_THOUSANDS_CUTOFF) is True


# ---------------------------------------------------------------------------
# End-to-end regression on real filings (both directions), VCR-backed.
# ---------------------------------------------------------------------------

from edgar import Filing  # noqa: E402
from edgar.thirteenf.models import ThirteenF  # noqa: E402


@pytest.mark.network
@pytest.mark.vcr
def test_post_cutover_thousands_filing_is_scaled_up():
    """Direction 1: a POST-cutover (period 2022-12-31) filing that still reports in
    thousands. The old date-cutoff rule left it unscaled => 1000x too small. Per-filing
    detection scales it to dollars.

    Ground truth: Bull Street Advisors, LLC (CIK 1790837), 13F-HR for 2022-12-31.
    Johnson & Johnson: 48,027 sh, raw Value 8,484 (thousands) => $8,484,000, implying
    ~$176.7/sh (JNJ closed 2022-12-30 at ~$176.65). Confirms whole-dollars output.
    """
    filing = Filing(form='13F-HR', filing_date='2023-02-28',
                    company='Bull Street Advisors, LLC', cik=1790837,
                    accession_no='0001790837-23-000002')
    tf = ThirteenF(filing)

    assert tf.report_period == '2022-12-31'  # post-cutover period
    assert tf._value_in_thousands is True    # detected as thousands despite the period

    jnj = tf.holdings[tf.holdings['Issuer'].str.contains('JOHNSON', case=False, na=False)].iloc[0]
    assert int(jnj['SharesPrnAmount']) == 48_027
    assert int(jnj['Value']) == 8_484_000  # scaled x1000 from raw 8,484
    implied_price = jnj['Value'] / jnj['SharesPrnAmount']
    assert 170 < implied_price < 185       # ~$176.7, a real JNJ share price

    assert tf.total_value == Decimal('192767000')


@pytest.mark.network
@pytest.mark.vcr
def test_pre_cutover_dollars_filing_is_not_scaled():
    """Direction 2: a PRE-cutover period (2021-12-31) filed late (2023-03-23) using the
    new whole-dollars convention. The old date-cutoff rule multiplied it by 1000 => 1000x
    too large. Per-filing detection leaves it unscaled.

    Ground truth: MetLife Investment Management (CIK 1099219), 13F-HR for 2021-12-31,
    filed 2023-03-23 -- the exact 'whole dollars' case cited in edgartools-mun2. Holdings
    are ETFs: SPDR S&P 500 (SPY) 9,866 sh, Value 4,245,201 => ~$430.3/sh (SPY ~ $430 at
    end-2021). Confirms the values are already in dollars.
    """
    filing = Filing(form='13F-HR', filing_date='2023-03-23',
                    company='METLIFE INC', cik=1099219,
                    accession_no='0001140361-23-013281')
    tf = ThirteenF(filing)

    assert tf.report_period == '2021-12-31'  # pre-cutover period
    assert tf._value_in_thousands is False   # detected as dollars (late dollar-convention filing)

    spy = tf.holdings[tf.holdings['Issuer'].str.contains('SPDR', case=False, na=False)].iloc[0]
    assert int(spy['SharesPrnAmount']) == 9_866
    assert int(spy['Value']) == 4_245_201   # unscaled
    implied_price = spy['Value'] / spy['SharesPrnAmount']
    assert 400 < implied_price < 480        # ~$430, a real SPY share price

    assert tf.total_value == Decimal('11019796')  # NOT 11,019,796,000


@pytest.mark.network
@pytest.mark.vcr
def test_presplit_megacap_thousands_filing_uses_fraction_not_median():
    """Direction 1, hard case: a small THOUSANDS filing concentrated in >$1000 pre-split
    mega-caps. Its median implied price is ABOVE $1, so a median-based rule would wrongly
    call it dollars and leave it 1000x too small. The fraction-of-sub-$1 statistic puts it
    in the ambiguous band, where the (absent) schema version + pre-cutover period correctly
    resolve it to thousands.

    Ground truth: ACTIAM N.V. (CIK 1619124), 13F-HR for 2020-12-31, only 5 share holdings.
    AAPL: 1,733,777 sh, raw Value 230,054 (thousands) => $230,054,000, implying ~$132.7/sh
    (AAPL closed 2020-12-31 at ~$132.69, split-adjusted). Confirms thousands.
    """
    filing = Filing(form='13F-HR', filing_date='2021-02-12',
                    company='ACTIAM N.V.', cik=1619124,
                    accession_no='0001619124-21-000002')
    tf = ThirteenF(filing)

    assert tf.report_period == '2020-12-31'
    assert tf._schema_version is None        # old schema: no <schemaVersion> element
    assert tf._value_in_thousands is True    # resolved via fraction + prior, not the median

    aapl = tf.holdings[tf.holdings['Issuer'].str.contains('APPLE', case=False, na=False)].iloc[0]
    assert int(aapl['SharesPrnAmount']) == 1_733_777
    assert int(aapl['Value']) == 230_054_000  # scaled x1000 from raw 230,054
    implied_price = aapl['Value'] / aapl['SharesPrnAmount']
    assert 125 < implied_price < 140          # ~$132.7, a real AAPL share price

    assert tf.total_value == Decimal('732158000')  # scaled x1000 (a median rule would give 732,158)
