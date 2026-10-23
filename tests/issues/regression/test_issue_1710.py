"""
entity_info must not name a co-registrant whose cover facts use srt:ConsolidatedEntitiesAxis.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1710

The #1420 guard set a DEI fact aside as a co-registrant's only when its context had a
dei:LegalEntityAxis member. Lamar Advertising's combined 10-Q (0001090425-26-000024)
puts its co-registrant Lamar Media Corp on srt:ConsolidatedEntitiesAxis, so Lamar
Media's name overwrote the filer's beside the filer's CIK 1090425 and ticker LAMR.

The cover below is cut down from that filing's instance to the facts entity_info reads,
keeping their contexts, members, values and document order.
"""
from edgar.xbrl.parsers import XBRLParser

LAMAR_CIK = "0001090425"
MEMBER = "lamr:LamarMediaCorporationAndSubsidiariesMember"


def _context(context_id, axis=None):
    segment = (f'<segment><xbrldi:explicitMember dimension="{axis}">{MEMBER}</xbrldi:explicitMember></segment>'
               if axis else "")
    return (f'<context id="{context_id}"><entity><identifier scheme="http://www.sec.gov/CIK">{LAMAR_CIK}</identifier>'
            f'{segment}</entity><period><startDate>2026-01-01</startDate><endDate>2026-06-30</endDate></period></context>')


def _cover(axis):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:dei="http://xbrl.sec.gov/dei/2025"
      xmlns:srt="http://fasb.org/srt/2025" xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
      xmlns:lamr="http://www.lamar.com/20260630">
{_context("c-1")}
{_context("c-2", axis)}
<dei:TradingSymbol contextRef="c-1">LAMR</dei:TradingSymbol>
<dei:DocumentType contextRef="c-1">10-Q</dei:DocumentType>
<dei:EntityCentralIndexKey contextRef="c-1">0001090425</dei:EntityCentralIndexKey>
<dei:EntityRegistrantName contextRef="c-1">LAMAR ADVERTISING CO/NEW</dei:EntityRegistrantName>
<dei:EntityRegistrantName contextRef="c-2">LAMAR MEDIA CORP/DE</dei:EntityRegistrantName>
<dei:EntityCentralIndexKey contextRef="c-2">0000899045</dei:EntityCentralIndexKey>
</xbrl>
"""


def _info(axis):
    parser = XBRLParser()
    parser.parse_instance_content(_cover(axis))
    return parser.entity_info


def test_consolidated_entities_axis_co_registrant_does_not_name_the_filer():
    info = _info("srt:ConsolidatedEntitiesAxis")
    assert (info["entity_name"], info["identifier"], info["ticker"], info["document_type"]) == (
        "LAMAR ADVERTISING CO/NEW", "1090425", "LAMR", "10-Q")


def test_legal_entity_axis_guard_unchanged():
    assert _info("dei:LegalEntityAxis")["entity_name"] == "LAMAR ADVERTISING CO/NEW"
