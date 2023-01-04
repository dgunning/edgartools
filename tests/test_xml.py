from bs4 import BeautifulSoup
from pathlib import Path
from edgar.xml import child_value, child_text, value_or_footnote, get_footnote_ids, value_with_footnotes


def test_child_value():
    soup = BeautifulSoup(
        """
        <root>
            <child>
            <value>Music</value>
            </child>
        </root>   
        """, features="xml"
    )
    root = soup.find("root")
    assert child_value(root, "child") == "Music"
    assert child_text(root, "child").strip() == "Music"


def test_value_or_footnote():
    soup = BeautifulSoup(
        """
        <root>
            <child>
            <footnote id="F1"/>
            </child>
        </root>   
        """, features="xml"
    )
    root = soup.find("root")
    child = root.find("child")
    assert value_or_footnote(child) == "F1"


holding_xml = Path("data/derivative_holding.xml").read_text()
holding_soup = BeautifulSoup(holding_xml, "xml")


def test_get_footnote_ids():
    tag = holding_soup.find('underlyingSecurityTitle')
    assert "F2,F3" == get_footnote_ids(tag)
    assert "F2|F3" == get_footnote_ids(tag, sep="|")
    assert "F2\nF3" == get_footnote_ids(tag, sep="\n")


def test_get_value_with_footnotes():
    tag = holding_soup.find("securityTitle")
    assert value_with_footnotes(tag) == "Series E Preferred Stock"

    tag = holding_soup.find('expirationDate')
    assert value_with_footnotes(tag) == "[F1]"

    tag = holding_soup.find('underlyingSecurityTitle')
    assert value_with_footnotes(tag) == "Class B Common Stock [F2,F3]"



