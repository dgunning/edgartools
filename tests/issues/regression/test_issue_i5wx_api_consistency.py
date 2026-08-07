"""
Contract tests for beads issue edgartools-i5wx: data-object API consistency.

The issue reported three classes of inconsistency that forced downstream
consumers (edgar-storage) to write defensive ``hasattr`` / dual-key access:

1. 13F infotable column-name drift (PascalCase vs SEC lowercase)
2. Form4 table / remarks attribute presence varying by parse path
3. FilingStatement.period_end returning a mixed date/string type

Investigation found the current public API is already consistent on all three.
These tests LOCK those guarantees so a future refactor cannot silently
reintroduce the drift:

- 13F: every parse path (XML and legacy TXT) emits the single canonical
  PascalCase schema; the SEC lowercase names never appear as columns.
- Form4: ``non_derivative_table`` / ``derivative_table`` / ``remarks`` are always
  present and correctly typed (empty table / "" when the XML element is absent),
  never raising AttributeError.
- period_end: the entity-facts date parser always yields a ``date`` or ``None``,
  never a leaked raw string.
"""
from datetime import date, datetime

import pandas as pd
import pytest

from edgar import Filing
from edgar.ownership.forms import Ownership

# The canonical 13F infotable schema (PascalCase) shared by all parse paths.
CANONICAL_13F_COLUMNS = {
    'Issuer', 'Class', 'Cusip', 'Value', 'SharesPrnAmount',
    'Type', 'PutCall', 'InvestmentDiscretion',
    'SoleVoting', 'SharedVoting', 'NonVoting', 'Ticker',
}
# SEC raw-XML lowercase names that must NOT leak into infotable columns.
SEC_LOWERCASE_ALIASES = {
    'nameOfIssuer', 'titleOfClass', 'cusip', 'value',
    'sshPrnamt', 'investmentDiscretion',
}


# ---------------------------------------------------------------------------
# Part 1: 13F infotable canonical column schema
# ---------------------------------------------------------------------------

@pytest.mark.network
def test_13f_xml_path_uses_canonical_pascalcase_schema():
    """Modern XML-path 13F (MetLife 2023) emits canonical PascalCase columns only."""
    filing = Filing(form='13F-HR', company='METLIFE INC', cik=1099219,
                    filing_date='2023-02-14', accession_no='0001140361-23-013281')
    infotable = filing.obj().infotable
    cols = set(infotable.columns)

    # Canonical columns are present; no SEC lowercase alias leaks through
    assert CANONICAL_13F_COLUMNS.issubset(cols), f"missing canonical columns: {CANONICAL_13F_COLUMNS - cols}"
    assert not (cols & SEC_LOWERCASE_ALIASES), f"lowercase aliases leaked: {cols & SEC_LOWERCASE_ALIASES}"


@pytest.mark.network
def test_13f_txt_path_uses_canonical_pascalcase_schema():
    """Legacy TXT-path 13F (Berkshire 2012) emits the SAME canonical schema as XML."""
    filing = Filing(form='13F-HR', company='BERKSHIRE HATHAWAY INC', cik=1067983,
                    filing_date='2012-11-14', accession_no='0001193125-12-470800')
    infotable = filing.obj().infotable
    cols = set(infotable.columns)

    # The legacy TXT path must agree with the XML path (Ticker + core fields),
    # so consumers never branch on parse path. OtherManager is XML-only and is
    # intentionally not required here.
    core = CANONICAL_13F_COLUMNS - {'PutCall'}  # PutCall present but may be blank
    assert core.issubset(cols), f"TXT path missing canonical columns: {core - cols}"
    assert not (cols & SEC_LOWERCASE_ALIASES), f"lowercase aliases leaked: {cols & SEC_LOWERCASE_ALIASES}"


# ---------------------------------------------------------------------------
# Part 2: Form4 attribute presence
# ---------------------------------------------------------------------------

# Minimal Form 4 XML with NO nonDerivativeTable, derivativeTable, or remarks.
# Exercises the empty-but-present fallback in Ownership.parse_xml.
_MINIMAL_FORM4_XML = """<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <periodOfReport>2024-01-15</periodOfReport>
  <issuer>
    <issuerCik>0000320193</issuerCik>
    <issuerName>APPLE INC</issuerName>
    <issuerTradingSymbol>AAPL</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerCik>0001214156</rptOwnerCik>
      <rptOwnerName>DOE JANE</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>1</isDirector>
      <isOfficer>0</isOfficer>
    </reportingOwnerRelationship>
    <reportingOwnerAddress></reportingOwnerAddress>
  </reportingOwner>
</ownershipDocument>
"""


def test_form4_tables_and_remarks_always_present_when_xml_omits_them():
    """Tables and remarks are present-and-empty (never absent) even when the XML omits them."""
    from edgar.ownership.forms import Form4

    form4 = Form4(**Ownership.parse_xml(_MINIMAL_FORM4_XML))

    # Attributes exist (no AttributeError / no hasattr guard needed)
    assert form4.non_derivative_table is not None
    assert form4.derivative_table is not None
    # Empty tables, but the .transactions / .holdings sub-objects are always present
    assert form4.non_derivative_table.empty
    assert form4.derivative_table.empty
    assert form4.non_derivative_table.transactions is not None
    assert form4.non_derivative_table.holdings is not None
    assert form4.derivative_table.transactions is not None
    assert form4.derivative_table.holdings is not None
    # remarks is always a string ("" when absent), never None
    assert form4.remarks == ""
    assert isinstance(form4.remarks, str)


@pytest.mark.network
def test_form4_attributes_present_on_real_filing():
    """A real Form 4 exposes the same always-present, correctly-typed attributes."""
    from edgar import Company
    from edgar.ownership.forms import Form4
    from edgar.ownership.table_containers import DerivativeTable, NonDerivativeTable

    # Use the latest Apple Form 4 to avoid pinning a volatile accession number.
    filing = Company('AAPL').get_filings(form='4').latest()
    form4 = filing.obj()

    assert isinstance(form4, Form4)
    assert isinstance(form4.non_derivative_table, NonDerivativeTable)
    assert isinstance(form4.derivative_table, DerivativeTable)
    assert isinstance(form4.remarks, str)
    for table in (form4.non_derivative_table, form4.derivative_table):
        assert table.transactions is not None
        assert table.holdings is not None


# ---------------------------------------------------------------------------
# Part 3: period_end is always a date (or None), never a leaked string
# ---------------------------------------------------------------------------

def test_entity_fact_parse_date_never_leaks_string():
    """_parse_date returns date or None for every input — never the raw string."""
    from edgar.entity.parser import EntityFactsParser

    parse = EntityFactsParser._parse_date
    assert parse('2024-12-20') == date(2024, 12, 20)
    assert parse('20241220') == date(2024, 12, 20)
    assert parse('12/20/2024') == date(2024, 12, 20)
    assert parse(None) is None
    assert parse('') is None
    # Unparseable input yields None (a useful absence), not the raw string
    result = parse('not a date')
    assert result is None
    assert not isinstance(result, str)


def test_financial_fact_period_end_is_date():
    """FinancialFact / FinancialStatement period_end fields are typed date|None."""
    from edgar.entity.models import FinancialFact

    # The dataclass field is annotated as a date
    assert FinancialFact.__annotations__['period_end'] is date

    # Construct a fact and confirm the attribute round-trips as a date
    fact = FinancialFact(
        concept='us-gaap:Revenue', taxonomy='us-gaap', label='Revenue',
        value=100, numeric_value=100.0, unit='USD',
        period_end=date(2024, 12, 31),
    )
    assert isinstance(fact.period_end, date)
