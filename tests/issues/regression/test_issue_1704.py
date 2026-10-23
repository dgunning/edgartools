"""
Facts in different currencies are not interchangeable duplicates in a statement.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1704

A USD and a CAD fact for one concept and context were ranked on decimals alone, and
the first in document order won a tie, so a CAD amount replaced the USD one in a
USD statement. The statement path now narrows such duplicates to the filing's
reporting currency before ranking by precision.
"""
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.parsers.coordinator import XBRLParser


@pytest.fixture(scope="module")
def disney():
    # Walt Disney Co FY2025 10-K, accession 0001744489-25-000155
    return XBRL.from_directory(Path("tests/fixtures/xbrl/dis/10k_2025"))


def test_disney_canadian_debt_keeps_the_usd_amount(disney):
    both = disney.parser.get_facts_by_key('us-gaap_LongTermDebt', 'c-393')
    assert sorted((f.unit_ref, f.value) for f in both) == [('cad', '1300000000'), ('usd', '900000000')]

    kept = disney._find_facts_for_element('us-gaap_LongTermDebt')['c-393']['fact']
    assert (kept.unit_ref, kept.numeric_value) == ('usd', 900_000_000.0)


def test_disney_statement_row_reads_usd(disney):
    st = disney.get_statement('http://corporate.disney.go.com/role/BorrowingsAdditionalInformationDetail')
    rows = [r for r in st
            if 'Canadian' in str(r.get('label', '')) and r['units'].get('instant_2025-09-27') in ('usd', 'cad')]
    assert [(r['values']['instant_2025-09-27'], r['units']['instant_2025-09-27']) for r in rows] == [
        (900_000_000.0, 'usd')]


def test_ibm_euro_amount_no_longer_wins_on_decimals():
    # IBM FY2024 10-K fixture: USD 2.3B at decimals -8 vs EUR 2.13B at decimals -7
    x = XBRL.from_directory(Path("tests/fixtures/xbrl/ibm/10k_2024"))
    kept = x._find_facts_for_element('us-gaap_BusinessCombinationConsiderationTransferred1')['c-330']['fact']
    assert (kept.unit_ref, kept.numeric_value) == ('usd', 2_300_000_000.0)


INSTANCE = """<?xml version="1.0" encoding="utf-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:us-gaap="http://fasb.org/us-gaap/2024"
 xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
 <xbrli:context id="C1"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period></xbrli:context>
 <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
 <xbrli:unit id="mxn"><xbrli:measure>iso4217:MXN</xbrli:measure></xbrli:unit>
 <us-gaap:Assets contextRef="C1" unitRef="usd" decimals="-6">5000000</us-gaap:Assets>
 <us-gaap:LinesOfCreditCurrent contextRef="C1" unitRef="mxn" decimals="-6">327000000</us-gaap:LinesOfCreditCurrent>
 <us-gaap:LinesOfCreditCurrent contextRef="C1" unitRef="usd" decimals="-6">19000000</us-gaap:LinesOfCreditCurrent>
 <us-gaap:Cash contextRef="C1" unitRef="usd" decimals="-6">1000000</us-gaap:Cash>
 <us-gaap:Cash contextRef="C1" unitRef="usd" decimals="0">1000123</us-gaap:Cash>
</xbrli:xbrl>"""


def _synthetic():
    x = XBRL()
    x.parser = XBRLParser()
    x.parser.parse_instance_content(INSTANCE)
    return x


def test_tie_in_decimals_no_longer_decided_by_document_order():
    kept = _synthetic()._find_facts_for_element('us-gaap_LinesOfCreditCurrent')['C1']['fact']
    assert (kept.unit_ref, kept.value) == ('usd', '19000000')


def test_same_unit_duplicates_still_ranked_by_precision():
    kept = _synthetic()._find_facts_for_element('us-gaap_Cash')['C1']['fact']
    assert kept.value == '1000123'


def _ctx(context_id):
    return (f'<xbrli:context id="{context_id}"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">'
            '0000000001</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2025-12-31</xbrli:instant>'
            '</xbrli:period></xbrli:context>')


def _xbrl(body):
    x = XBRL()
    x.parser = XBRLParser()
    x.parser.parse_instance_content(
        '<?xml version="1.0" encoding="utf-8"?><xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" '
        'xmlns:us-gaap="http://fasb.org/us-gaap/2024" xmlns:iso4217="http://www.xbrl.org/2003/iso4217">'
        f'{body}</xbrli:xbrl>')
    return x


# Two undimensioned contexts for one instant: USD at -8 in A, CAD at -6 in B. The USD
# unit's measure is pretty-printed, which used to hide it from every iso4217: test.
CROSS_CONTEXT = f"""{_ctx("A")}{_ctx("B")}
<xbrli:unit id="usd"><xbrli:measure>
   iso4217:USD
</xbrli:measure></xbrli:unit>
<xbrli:unit id="cad"><xbrli:measure>iso4217:CAD</xbrli:measure></xbrli:unit>
<us-gaap:Assets contextRef="A" unitRef="usd" decimals="-6">5000000</us-gaap:Assets>
<us-gaap:Cash contextRef="A" unitRef="usd" decimals="-6">1000000</us-gaap:Cash>
<us-gaap:LongTermDebt contextRef="A" unitRef="usd" decimals="-8">900000000</us-gaap:LongTermDebt>
<us-gaap:LongTermDebt contextRef="B" unitRef="cad" decimals="-6">1300000000</us-gaap:LongTermDebt>"""


def test_pretty_printed_measure_is_stripped():
    x = _xbrl(CROSS_CONTEXT)
    assert x.parser.units["usd"] == {"type": "simple", "measure": "iso4217:USD"}
    assert x._reporting_currency() == "iso4217:USD"


@pytest.mark.parametrize("show_dimensions", [True, False])
def test_cross_context_cell_keeps_reporting_currency(show_dimensions):
    from edgar.xbrl.models import PresentationNode
    x = _xbrl(CROSS_CONTEXT)
    nodes = {"us-gaap_LongTermDebt": PresentationNode(element_id="us-gaap_LongTermDebt",
                                                      element_name="us-gaap_LongTermDebt")}
    rows = []
    x._generate_line_items("us-gaap_LongTermDebt", nodes, rows, should_display_dimensions=show_dimensions)
    assert [(r["values"], r["units"]) for r in rows] == [
        ({"instant_2025-12-31": 900_000_000.0}, {"instant_2025-12-31": "usd"})]


def test_currency_count_tie_goes_to_the_assets_currency():
    body = f"""{_ctx("A")}
<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
<xbrli:unit id="eur"><xbrli:measure>iso4217:EUR</xbrli:measure></xbrli:unit>
<us-gaap:Cash contextRef="A" unitRef="usd" decimals="-6">1000000</us-gaap:Cash>
<us-gaap:Assets contextRef="A" unitRef="eur" decimals="-6">5000000</us-gaap:Assets>"""
    assert _xbrl(body)._reporting_currency() == "iso4217:EUR"


def test_choice_is_logged_once_per_filing(caplog):
    x = _synthetic()
    with caplog.at_level("WARNING", logger="edgar.xbrl.xbrl"):
        x._find_facts_for_element('us-gaap_LinesOfCreditCurrent')
        x._find_facts_for_element('us-gaap_LinesOfCreditCurrent')
    messages = [r.getMessage() for r in caplog.records if "GH #1704" in r.getMessage()]
    assert len(messages) == 1
    assert "statements show the iso4217:USD amount" in messages[0] and "mxn" in messages[0]
