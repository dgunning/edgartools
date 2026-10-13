"""
Regression test for GitHub issue #1420: entity_info names a co-registrant as the filer

A combined filing covers several registrants in one instance. The filer's cover
facts sit in a context with no dei:LegalEntityAxis member, and each
co-registrant's sit under one. entity_info kept whichever fact of a concept came
last in document order, so a co-registrant's fact could stand in for the
filer's. Duke Energy's FY2025 10-K (0001326160-26-000014) covers eight
registrants, and came back as PIEDMONT NATURAL GAS COMPANY, INC. beside
identifier 1326160, which is Duke Energy Corporation's CIK (Piedmont's own is
78460). The ticker crossed over the same way: Prologis's FY2025 10-K
(0001193125-26-051453) reported 'PLD/40', a note of its co-registrant
Prologis, L.P., instead of 'PLD'.

The filer's facts now win, and a co-registrant's fact fills a field only when
the filer reports none. Which of the filer's own symbols becomes the scalar
ticker, when it lists several, is GH #1252 and is unchanged here.

Each cover below is cut down from the filing's own instance to the facts
entity_info reads, keeping their members, CIKs, names, symbols and document
order.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1420
"""

from edgar.xbrl.parsers import XBRLParser

LEGAL_ENTITY_AXIS = "dei:LegalEntityAxis"
CLASS_OF_STOCK_AXIS = "us-gaap:StatementClassOfStockAxis"

DUKE_ENERGY_CIK = "0001326160"

# The seven co-registrants on Duke Energy's cover, in document order:
# (dei:LegalEntityAxis member, dei:EntityCentralIndexKey, dei:EntityRegistrantName)
DUKE_ENERGY_CO_REGISTRANTS = [
    ("duk:DukeEnergyCarolinasMember", "0000030371", "DUKE ENERGY CAROLINAS, LLC"),
    ("duk:ProgressEnergyMember", "0001094093", "PROGRESS ENERGY, INC."),
    ("duk:DukeEnergyProgressMember", "0000017797", "DUKE ENERGY PROGRESS, LLC"),
    ("duk:DukeEnergyFloridaMember", "0000037637", "DUKE ENERGY FLORIDA, LLC"),
    ("duk:DukeEnergyOhioMember", "0000020290", "DUKE ENERGY OHIO, INC."),
    ("duk:DukeEnergyIndianaMember", "0000081020", "DUKE ENERGY INDIANA, LLC"),
    ("duk:PiedmontNaturalGasMember", "0000078460", "PIEDMONT NATURAL GAS COMPANY, INC."),
]

PROLOGIS_CIK = "0001045609"
PROLOGIS_LP = (LEGAL_ENTITY_AXIS, "pld:PrologisLimitedPartnershipMember")
COMMON_STOCK = (CLASS_OF_STOCK_AXIS, "us-gaap:CommonStockMember")
NOTES_DUE_2029 = (CLASS_OF_STOCK_AXIS, "pld:TwoPointTwoFiveZeroPercentNotesDueTwoThousandTwentyNineMember")
NOTES_DUE_2040 = (CLASS_OF_STOCK_AXIS, "pld:FivePointSixTwoFivePercentNotesDueTwoThousandFortyMember")


def _context(context_id, cik, *dimensions):
    """A full-year cover context; each dimension is an (axis, member) pair."""
    members = "".join(f'<xbrldi:explicitMember dimension="{axis}">{member}</xbrldi:explicitMember>' for axis, member in dimensions)
    segment = f"<segment>{members}</segment>" if members else ""
    return (
        f'<context id="{context_id}">'
        f'<entity><identifier scheme="http://www.sec.gov/CIK">{cik}</identifier>{segment}</entity>'
        "<period><startDate>2025-01-01</startDate><endDate>2025-12-31</endDate></period>"
        "</context>"
    )


def _fact(concept, context_id, value):
    return f'<dei:{concept} contextRef="{context_id}">{value}</dei:{concept}>'


def _instance(parts):
    body = "\n".join(parts)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance"
      xmlns:dei="http://xbrl.sec.gov/dei/2025"
      xmlns:us-gaap="http://fasb.org/us-gaap/2025"
      xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
      xmlns:duk="http://www.duke-energy.com/20251231"
      xmlns:pld="http://www.prologis.com/20251231">
{body}
</xbrl>
"""


def _duke_energy_cover():
    co_registrants = list(enumerate(DUKE_ENERGY_CO_REGISTRANTS, start=2))
    return _instance(
        [_context("c-1", DUKE_ENERGY_CIK)]
        + [_context(f"c-{i}", DUKE_ENERGY_CIK, (LEGAL_ENTITY_AXIS, member)) for i, (member, _, _) in co_registrants]
        + [_fact("EntityCentralIndexKey", "c-1", DUKE_ENERGY_CIK)]
        + [_fact("EntityCentralIndexKey", f"c-{i}", cik) for i, (_, cik, _) in co_registrants]
        + [_fact("DocumentType", "c-1", "10-K"), _fact("DocumentPeriodEndDate", "c-1", "2025-12-31")]
        + [_fact("EntityRegistrantName", "c-1", "DUKE ENERGY CORPORATION")]
        + [_fact("EntityRegistrantName", f"c-{i}", name) for i, (_, _, name) in co_registrants]
    )


def _prologis_cover():
    return _instance(
        [
            _context("filer", PROLOGIS_CIK),
            _context("lp", PROLOGIS_CIK, PROLOGIS_LP),
            _context("common", PROLOGIS_CIK, COMMON_STOCK),
            _context("notes-2029", PROLOGIS_CIK, NOTES_DUE_2029, PROLOGIS_LP),
            _context("notes-2040", PROLOGIS_CIK, NOTES_DUE_2040, PROLOGIS_LP),
            _fact("EntityCentralIndexKey", "filer", PROLOGIS_CIK),
            _fact("EntityCentralIndexKey", "lp", "0001045610"),
            _fact("DocumentType", "lp", "10-K"),
            _fact("DocumentType", "filer", "10-K"),
            _fact("EntityRegistrantName", "filer", "Prologis, Inc."),
            _fact("EntityRegistrantName", "lp", "Prologis, L.P."),
            _fact("TradingSymbol", "common", "PLD"),
            _fact("TradingSymbol", "notes-2029", "PLD/29"),
            _fact("TradingSymbol", "notes-2040", "PLD/40"),
        ]
    )


def _parse(content):
    parser = XBRLParser()
    parser.parse_instance_content(content)
    return parser


def test_entity_info_names_the_filer_not_its_last_co_registrant():
    info = _parse(_duke_energy_cover()).entity_info

    assert info["entity_name"] == "DUKE ENERGY CORPORATION", f"entity_name names a co-registrant: {info['entity_name']!r}"
    assert info["identifier"] == "1326160"
    assert info["document_type"] == "10-K"
    assert info["document_period_end_date"] == "2025-12-31"


def test_ticker_is_the_filers_own_symbol_not_a_co_registrants():
    info = _parse(_prologis_cover()).entity_info

    assert info["ticker"] == "PLD", f"ticker is a co-registrant's security: {info['ticker']!r}"
    assert info["entity_name"] == "Prologis, Inc."
    assert info["identifier"] == "1045609"


def test_every_registrants_name_is_still_parsed():
    parser = _parse(_duke_energy_cover())

    names = {
        parser.contexts[fact.context_ref].dimensions.get(LEGAL_ENTITY_AXIS): fact.value
        for fact in parser.facts.values()
        if fact.element_id == "dei:EntityRegistrantName"
    }

    assert names == {None: "DUKE ENERGY CORPORATION", **{member: name for member, _, name in DUKE_ENERGY_CO_REGISTRANTS}}


def test_a_co_registrants_fact_fills_a_field_the_filer_leaves_empty():
    member, _, name = DUKE_ENERGY_CO_REGISTRANTS[0]
    content = _instance(
        [
            _context("c-1", DUKE_ENERGY_CIK),
            _context("c-2", DUKE_ENERGY_CIK, (LEGAL_ENTITY_AXIS, member)),
            _fact("DocumentType", "c-1", "10-K"),
            _fact("EntityRegistrantName", "c-2", name),
        ]
    )

    info = _parse(content).entity_info

    assert info["entity_name"] == "DUKE ENERGY CAROLINAS, LLC"
    assert info["document_type"] == "10-K"
