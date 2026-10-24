"""
XBRL fraction items must be the quotient, not the digits joined.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1766

A fact of type ``xbrli:fractionItemType`` is a numerator and a denominator
(XBRL 2.1 §5.1.1.3.2). Its value is that quotient, exact, and its precision is
INF because a fraction item carries no ``decimals`` attribute (§4.6.6). The
instance parser joined the children's text, and with blank text removed the
digits ran together, so numerator 1 and denominator 3 were read as 13.

No SEC filing is cited. The issue reports that no US GAAP, SRT or DEI concept
uses ``fractionItemType`` and that none appeared in 80 sampled SEC instances, so
the ground truth is the spec's own 1/3, not a filing value.
"""
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
    assert fact.value == "0.3333333333333333"
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


def test_fraction_outside_float_range_is_not_reported_as_zero_or_infinity():
    huge = "1" + "0" * 400
    xml = INSTANCE.replace(
        "</xbrli:xbrl>",
        f"""  <my:underflow contextRef="C1" unitRef="pure">
    <xbrli:numerator>1</xbrli:numerator>
    <xbrli:denominator>{huge}</xbrli:denominator>
  </my:underflow>
  <my:overflow contextRef="C1" unitRef="pure">
    <xbrli:numerator>{huge}</xbrli:numerator>
    <xbrli:denominator>1</xbrli:denominator>
  </my:overflow>
</xbrli:xbrl>""",
    )
    facts = {}
    InstanceParser({}, facts, {}, {}, {}, {}, [], {}).parse_instance_content(xml)
    underflow = facts["my_underflow|C1"]
    overflow = facts["my_overflow|C1"]
    assert underflow.value == f"1/{huge}"
    assert underflow.numeric_value is None
    assert overflow.value == f"{huge}/1"
    assert overflow.numeric_value is None


def test_non_fraction_facts_are_unchanged():
    facts = _facts()
    amount = facts["my_amount|C1"]
    assert (amount.value, amount.numeric_value, amount.decimals) == ("42", 42.0, "0")
    # Nested text that is not a numerator/denominator pair is still joined.
    note = facts["my_note|C1"]
    assert note.value == "HelloWorld"
    assert note.numeric_value is None
    assert note.decimals is None
