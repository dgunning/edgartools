from pathlib import Path
from edgar.xmltools import child_value, child_text, value_or_footnote, get_footnote_ids, value_with_footnotes, find_element, \
    optional_decimal, parse_xml, local_name
from decimal import Decimal


def test_child_value():
    root = parse_xml("""
        <root>
            <child>
            <value>Music</value>
            </child>
        </root>   
        """)
    assert child_value(root, "child") == "Music"
    assert child_text(root, "child").strip() == "Music"


def test_value_or_footnote():
    root = parse_xml("""
        <root>
            <child>
            <footnote id="F1"/>
            </child>
        </root>   
        """)
    child = root.find("child")
    assert value_or_footnote(child) == "F1"


holding_xml = Path("data/derivative_holding.xml").read_text()
holding_root = parse_xml(holding_xml)


def test_get_footnote_ids():
    tag = find_element(holding_root, 'underlyingSecurityTitle')
    assert "F2,F3" == get_footnote_ids(tag)
    assert "F2|F3" == get_footnote_ids(tag, sep="|")
    assert "F2\nF3" == get_footnote_ids(tag, sep="\n")


def test_get_value_with_footnotes():
    tag = find_element(holding_root, "securityTitle")
    assert value_with_footnotes(tag) == "Series E Preferred Stock"

    tag = find_element(holding_root, 'expirationDate')
    assert value_with_footnotes(tag) == "[F1]"

    tag = find_element(holding_root, 'underlyingSecurityTitle')
    assert value_with_footnotes(tag) == "Class B Common Stock [F2,F3]"


def test_find_element():
    xml_string = """
        <root>
            <child>
            <value>Music</value>
            </child>
        </root>   
        """
    root = find_element(xml_string, 'root')
    assert root is not None
    assert local_name(root) == "root"


def test_optional_decimal():
    xml_string = """
    <fundInfo>
      <totAssets>0</totAssets>
      <totLiabs>0</totLiabs>
      <netAssets>0</netAssets>
      <assetsAttrMiscSec>0</assetsAttrMiscSec>
      <assetsInvested>0</assetsInvested>
      <amtPayOneYrBanksBorr>0</amtPayOneYrBanksBorr>
      <amtPayOneYrCtrldComp>0</amtPayOneYrCtrldComp>
      <amtPayOneYrOthAffil>0</amtPayOneYrOthAffil>
      <amtPayOneYrOther>0</amtPayOneYrOther>
      <amtPayAftOneYrBanksBorr>0.018</amtPayAftOneYrBanksBorr>
      <amtPayAftOneYrCtrldComp>0</amtPayAftOneYrCtrldComp>
      <amtPayAftOneYrOthAffil>0</amtPayAftOneYrOthAffil>
      <amtPayAftOneYrOther>0</amtPayAftOneYrOther>
      <delayDeliv>0</delayDeliv>
      <standByCommit>0</standByCommit>
      <liquidPref>0</liquidPref>
    </fundInfo>
    """
    fund_info_tag = parse_xml(xml_string)
    assert optional_decimal(fund_info_tag, "amtPayAftOneYrBanksBorr") == Decimal("0.018")
    assert optional_decimal(fund_info_tag, "NOT_THERE") is None
