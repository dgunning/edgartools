"""
XBRL fraction items must be the quotient, not the digits joined.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1766

A fact of type ``xbrli:fractionItemType`` is a numerator and a denominator
(XBRL 2.1 §5.1.1.3.2). Its value is that quotient, exact, and its precision is
INF because a fraction item carries no ``decimals`` attribute (§4.6.6). The
instance parser joined the children's text, and with blank text removed the
digits ran together, so numerator 1 and denominator 3 were read as 13.

The stored text is the decimal quotient, not a float. ``9007199254740993``
stays ``9007199254740993`` (the float of it is ``9007199254740992``), and the
division does not use the caller's decimal context.

Real filing: Apple Inc. FY2023 Form 10-K, accession 0000320193-23-000106,
instance ``aapl-20230930_htm.xml``. SEC full-text search for
``fractionItemType`` and for ``xbrli:numerator`` returned no hits, and this
instance contains neither, so it is not a fraction-item specimen. The control
is an ordinary fact read from that instance before it was parsed:
``us-gaap:Assets``, context ``c-22`` (instant 2023-09-30, no dimensions),
filed value ``352583000000``. The prior year, context ``c-23`` (instant
2022-09-24), is ``352755000000``.
"""
import decimal

import pytest

from edgar.httprequests import download_text
from edgar.xbrl import XBRL
from edgar.xbrl.parsers.instance import InstanceParser

INSTANCE = """<?xml version="1.0" encoding="utf-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xmlns:my="http://example.com/my">
  <xbrli:context id="C1">
    <xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period>
  </xbrli:context>
  <xbrli:unit id="pure"><xbrli:measure>xbrli:pure</xbrli:measure></xbrli:unit>
  <my:oneThird contextRef="C1" unitRef="pure">
    <xbrli:numerator>1</xbrli:numerator>
    <xbrli:denominator>3</xbrli:denominator>
  </my:oneThird>
  <my:oneHalf contextRef="C1" unitRef="pure">
    <xbrli:numerator>1</xbrli:numerator>
    <xbrli:denominator>2</xbrli:denominator>
  </my:oneHalf>
  <my:whole contextRef="C1" unitRef="pure">
    <xbrli:numerator>2</xbrli:numerator>
    <xbrli:denominator>1</xbrli:denominator>
  </my:whole>
  <my:negative contextRef="C1" unitRef="pure">
    <xbrli:numerator>-1</xbrli:numerator>
    <xbrli:denominator>4</xbrli:denominator>
  </my:negative>
  <my:negativeDenom contextRef="C1" unitRef="pure">
    <xbrli:numerator>1</xbrli:numerator>
    <xbrli:denominator>-4</xbrli:denominator>
  </my:negativeDenom>
  <my:bothNegative contextRef="C1" unitRef="pure">
    <xbrli:numerator>-1</xbrli:numerator>
    <xbrli:denominator>-2</xbrli:denominator>
  </my:bothNegative>
  <my:decimalParts contextRef="C1" unitRef="pure">
    <xbrli:numerator>1.5</xbrli:numerator>
    <xbrli:denominator>2.5</xbrli:denominator>
  </my:decimalParts>
  <my:negativeDecimal contextRef="C1" unitRef="pure">
    <xbrli:numerator>-1.5</xbrli:numerator>
    <xbrli:denominator>2</xbrli:denominator>
  </my:negativeDecimal>
  <my:zeroNumer contextRef="C1" unitRef="pure">
    <xbrli:numerator>0</xbrli:numerator>
    <xbrli:denominator>5</xbrli:denominator>
  </my:zeroNumer>
  <my:padded contextRef="C1" unitRef="pure">
    <xbrli:numerator>  2 </xbrli:numerator>
    <xbrli:denominator> 4 </xbrli:denominator>
  </my:padded>
  <my:strayDecimals contextRef="C1" unitRef="pure" decimals="-6">
    <xbrli:numerator>1</xbrli:numerator>
    <xbrli:denominator>2</xbrli:denominator>
  </my:strayDecimals>
  <my:zeroDenom contextRef="C1" unitRef="pure">
    <xbrli:numerator>1</xbrli:numerator>
    <xbrli:denominator>0</xbrli:denominator>
  </my:zeroDenom>
  <my:zeroOverZero contextRef="C1" unitRef="pure">
    <xbrli:numerator>0</xbrli:numerator>
    <xbrli:denominator>0</xbrli:denominator>
  </my:zeroOverZero>
  <my:notADecimal contextRef="C1" unitRef="pure">
    <xbrli:numerator>abc</xbrli:numerator>
    <xbrli:denominator>3</xbrli:denominator>
  </my:notADecimal>
  <my:nilFraction contextRef="C1" unitRef="pure" xsi:nil="true"/>
  <my:nilWithChildren contextRef="C1" unitRef="pure" xsi:nil="true">
    <xbrli:numerator>1</xbrli:numerator>
    <xbrli:denominator>3</xbrli:denominator>
  </my:nilWithChildren>
  <my:nilNumerator contextRef="C1" unitRef="pure">
    <xbrli:numerator xsi:nil="true"/>
    <xbrli:denominator>3</xbrli:denominator>
  </my:nilNumerator>
  <my:amount contextRef="C1" unitRef="pure" decimals="0">42</my:amount>
  <my:badText contextRef="C1" unitRef="pure">not-a-number</my:badText>
  <my:note contextRef="C1"><span>Hello</span><span>World</span></my:note>
</xbrli:xbrl>
"""


def _facts():
    facts = {}
    InstanceParser({}, facts, {}, {}, {}, {}, [], {}).parse_instance_content(INSTANCE)
    return facts


def test_one_third_is_the_quotient_not_the_digits_joined():
    fact = _facts()["my_oneThird|C1"]
    # Non-terminating: half-even to 50 significant digits. ROUND_UP would end in 4.
    assert fact.value == "0." + "3" * 50
    assert fact.numeric_value == 1 / 3
    assert fact.numeric_value != 13
    assert fact.decimals == "INF"


def test_fraction_edges_negative_decimal_parts_and_whole_numbers():
    facts = _facts()
    assert (facts["my_oneHalf|C1"].value, facts["my_oneHalf|C1"].numeric_value) == ("0.5", 0.5)
    assert (facts["my_whole|C1"].value, facts["my_whole|C1"].numeric_value) == ("2", 2.0)
    assert (facts["my_negative|C1"].value, facts["my_negative|C1"].numeric_value) == ("-0.25", -0.25)
    assert (facts["my_negativeDenom|C1"].value, facts["my_negativeDenom|C1"].numeric_value) == ("-0.25", -0.25)
    assert (facts["my_bothNegative|C1"].value, facts["my_bothNegative|C1"].numeric_value) == ("0.5", 0.5)
    assert (facts["my_decimalParts|C1"].value, facts["my_decimalParts|C1"].numeric_value) == ("0.6", 0.6)
    assert (facts["my_negativeDecimal|C1"].value, facts["my_negativeDecimal|C1"].numeric_value) == ("-0.75", -0.75)
    assert (facts["my_zeroNumer|C1"].value, facts["my_zeroNumer|C1"].numeric_value) == ("0", 0.0)
    assert (facts["my_padded|C1"].value, facts["my_padded|C1"].numeric_value) == ("0.5", 0.5)
    for key in (
        "my_oneHalf|C1", "my_whole|C1", "my_negative|C1", "my_negativeDenom|C1",
        "my_bothNegative|C1", "my_decimalParts|C1", "my_negativeDecimal|C1",
        "my_zeroNumer|C1", "my_padded|C1", "my_oneThird|C1",
    ):
        assert facts[key].decimals == "INF"


def test_zero_denominator_and_other_bad_fractions_are_not_numbers():
    facts = _facts()
    zero = facts["my_zeroDenom|C1"]
    assert zero.value == "1/0"
    assert zero.numeric_value is None
    assert zero.decimals is None
    undefined = facts["my_zeroOverZero|C1"]
    assert undefined.value == "0/0"
    assert undefined.numeric_value is None
    garbage = facts["my_notADecimal|C1"]
    assert garbage.value == "abc/3"
    assert garbage.numeric_value is None
    # A plain non-numeric fact keeps its text and stays non-numeric, same as before.
    bad = facts["my_badText|C1"]
    assert bad.value == "not-a-number"
    assert bad.numeric_value is None


def test_nil_fraction_has_no_value():
    facts = _facts()
    for key in ("my_nilFraction|C1", "my_nilWithChildren|C1", "my_nilNumerator|C1"):
        fact = facts[key]
        assert fact.value == ""
        assert fact.numeric_value is None
        assert XBRL._get_fact_precision(fact) == -2_000_000


def test_fraction_precision_is_infinite_and_outranks_a_rounded_duplicate():
    fact = _facts()["my_oneThird|C1"]
    assert XBRL._get_fact_precision(fact) == 1_000_000
    # §4.6.6: a fraction's precision is INF even when a decimals attribute was filed.
    stray = _facts()["my_strayDecimals|C1"]
    assert stray.numeric_value == 0.5
    assert stray.decimals == "INF"

    class Rounded:
        decimals = "-6"
        value = "13"
        numeric_value = 13.0

    assert XBRL._select_most_precise_fact([Rounded(), fact]) is fact


def test_fraction_outside_float_range_keeps_the_exact_decimal():
    huge = "1" + "0" * 400
    facts = _with_facts(f"""
  <my:underflow contextRef="C1" unitRef="pure">
    <xbrli:numerator>1</xbrli:numerator>
    <xbrli:denominator>{huge}</xbrli:denominator>
  </my:underflow>
  <my:overflow contextRef="C1" unitRef="pure">
    <xbrli:numerator>{huge}</xbrli:numerator>
    <xbrli:denominator>1</xbrli:denominator>
  </my:overflow>
""")
    underflow = facts["my_underflow|C1"]
    overflow = facts["my_overflow|C1"]
    # 1/10**400 is the digit 1 four hundred places right of the decimal point.
    assert underflow.value == "0." + "0" * 399 + "1"
    assert underflow.numeric_value is None
    assert underflow.decimals == "INF"
    assert overflow.value == huge
    assert overflow.numeric_value is None
    assert overflow.decimals == "INF"


def test_fraction_value_is_exact_past_the_float_mantissa():
    sixty = "9" * 60
    facts = _with_facts(f"""
  <my:pastMantissa contextRef="C1" unitRef="pure">
    <xbrli:numerator>9007199254740993</xbrli:numerator>
    <xbrli:denominator>1</xbrli:denominator>
  </my:pastMantissa>
  <my:extraBit contextRef="C1" unitRef="pure">
    <xbrli:numerator>1.0000000000000001</xbrli:numerator>
    <xbrli:denominator>1</xbrli:denominator>
  </my:extraBit>
  <my:sixtyDigits contextRef="C1" unitRef="pure">
    <xbrli:numerator>{sixty}</xbrli:numerator>
    <xbrli:denominator>1</xbrli:denominator>
  </my:sixtyDigits>
""")
    past = facts["my_pastMantissa|C1"]
    assert past.value == "9007199254740993"
    assert past.numeric_value == 9007199254740992.0
    assert past.decimals == "INF"
    extra = facts["my_extraBit|C1"]
    assert extra.value == "1.0000000000000001"
    assert extra.numeric_value == 1.0
    assert facts["my_sixtyDigits|C1"].value == sixty
    # 10**60 still fits in a float, but not as this integer. The stored text
    # is the 60 nines; the float is only the numeric_value.
    assert facts["my_sixtyDigits|C1"].numeric_value == 1e60
    assert facts["my_sixtyDigits|C1"].value != str(facts["my_sixtyDigits|C1"].numeric_value)


def test_fraction_division_ignores_the_caller_decimal_context():
    tiny = "1" + "0" * 100
    with decimal.localcontext() as ctx:
        ctx.prec = 2
        ctx.rounding = decimal.ROUND_UP
        ctx.Emax = 2
        ctx.Emin = -9
        ctx.traps[decimal.Inexact] = True
        facts = _with_facts(f"""
  <my:pastMantissa contextRef="C1" unitRef="pure">
    <xbrli:numerator>9007199254740993</xbrli:numerator>
    <xbrli:denominator>1</xbrli:denominator>
  </my:pastMantissa>
  <my:thousand contextRef="C1" unitRef="pure">
    <xbrli:numerator>1000</xbrli:numerator>
    <xbrli:denominator>1</xbrli:denominator>
  </my:thousand>
  <my:tiny contextRef="C1" unitRef="pure">
    <xbrli:numerator>1</xbrli:numerator>
    <xbrli:denominator>{tiny}</xbrli:denominator>
  </my:tiny>
""")
        # ROUND_UP must not change the last digit of 1/3.
        assert facts["my_oneThird|C1"].value == "0." + "3" * 50
        assert facts["my_pastMantissa|C1"].value == "9007199254740993"
        # Emax=2 would overflow 1000/1. Emin=-9 would underflow 10^-100 to 0.
        thousand = facts["my_thousand|C1"]
        assert thousand.value == "1000"
        assert thousand.numeric_value == 1000.0
        assert thousand.decimals == "INF"
        tiny_fact = facts["my_tiny|C1"]
        assert tiny_fact.value == "0." + "0" * 99 + "1"
        assert tiny_fact.numeric_value == 1e-100
        assert tiny_fact.decimals == "INF"
        assert ctx.prec == 2
        assert ctx.rounding == decimal.ROUND_UP
        assert ctx.Emax == 2
        assert ctx.Emin == -9
        assert ctx.traps[decimal.Inexact]
        with pytest.raises(decimal.Inexact):
            decimal.Decimal(1) / decimal.Decimal(3)


def test_terminating_quotient_of_one_over_two_to_the_hundred_is_exact():
    """1/2**100 terminates. 5**100 has 70 digits, so 50 significant digits would drop the tail."""
    power = 100
    digits = str(5 ** power)
    expected = "0." + "0" * (power - len(digits)) + digits
    facts = _with_facts(f"""
  <my:powerOfTwo contextRef="C1" unitRef="pure">
    <xbrli:numerator>1</xbrli:numerator>
    <xbrli:denominator>{2 ** power}</xbrli:denominator>
  </my:powerOfTwo>
""")
    fact = facts["my_powerOfTwo|C1"]
    assert len(digits) == 70
    assert fact.value == expected
    assert fact.numeric_value == 2 ** -power
    assert fact.decimals == "INF"


def test_fraction_operand_includes_text_around_a_comment_or_processing_instruction():
    facts = _with_facts("""
  <my:commented contextRef="C1" unitRef="pure">
    <xbrli:numerator>1<!--c-->2</xbrli:numerator>
    <xbrli:denominator>4</xbrli:denominator>
  </my:commented>
  <my:processingInstruction contextRef="C1" unitRef="pure">
    <xbrli:numerator>8<?pi ?>2</xbrli:numerator>
    <xbrli:denominator>2</xbrli:denominator>
  </my:processingInstruction>
""")
    commented = facts["my_commented|C1"]
    assert commented.value == "3"
    assert commented.numeric_value == 3.0
    assert commented.decimals == "INF"
    instructed = facts["my_processingInstruction|C1"]
    assert instructed.value == "41"
    assert instructed.numeric_value == 41.0


# Apple Inc. FY2023 Form 10-K. Ordinary-fact control: this instance has no
# fraction item (see the module docstring). Filed values, read from the
# instance XML: Assets 352583000000 at 2023-09-30 (context c-22) and
# 352755000000 at 2022-09-24 (context c-23).
APPLE_FY2023_10K_ACCESSION = "0000320193-23-000106"
APPLE_FY2023_10K_INSTANCE = (
    "https://www.sec.gov/Archives/edgar/data/320193/"
    + APPLE_FY2023_10K_ACCESSION.replace("-", "")
    + "/aapl-20230930_htm.xml"
)


@pytest.mark.vcr
def test_apple_fy2023_10k_ordinary_assets_are_unchanged():
    """Accession 0000320193-23-000106. us-gaap:Assets context c-22 is 352583000000."""
    xml = download_text(APPLE_FY2023_10K_INSTANCE)
    assert xml is not None and "352583000000" in xml
    assert "fractionItemType" not in xml
    # Default namespace and the xbrli prefix. This instance has neither.
    assert "<numerator" not in xml
    assert "<xbrli:numerator" not in xml
    facts = {}
    InstanceParser({}, facts, {}, {}, {}, {}, [], {}).parse_instance_content(xml)
    assets = facts["us-gaap_Assets|c-22"]
    assert assets.value == "352583000000"
    assert assets.numeric_value == 352583000000.0
    prior = facts["us-gaap_Assets|c-23"]
    assert prior.value == "352755000000"
    assert prior.numeric_value == 352755000000.0


def _with_facts(extra: str):
    facts = {}
    xml = INSTANCE.replace("</xbrli:xbrl>", extra + "</xbrli:xbrl>")
    InstanceParser({}, facts, {}, {}, {}, {}, [], {}).parse_instance_content(xml)
    return facts


def test_non_fraction_facts_are_unchanged():
    facts = _facts()
    amount = facts["my_amount|C1"]
    assert (amount.value, amount.numeric_value, amount.decimals) == ("42", 42.0, "0")
    # Nested text that is not a numerator/denominator pair is still joined.
    note = facts["my_note|C1"]
    assert note.value == "HelloWorld"
    assert note.numeric_value is None
    assert note.decimals is None
