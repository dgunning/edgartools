"""
Regression test for GitHub issue #1499: the EFFECT notice's effective time was dropped

An EFFECT notice for an initial registration carries <finalEffectivenessDispTime>
beside <finalEffectivenessDispDate>, and Effect.from_xml() read only the date.
The XML below is Lyntris Inc.'s S-1 notice (9999999995-26-002694) and Fitness
Fanatics' POS AM notice (9999999995-25-003344), as SEC serves them. Lyntris's
filing date is 2026-08-18 but SEC accepted the notice at 2026-08-19 00:15:13;
Fitness Fanatics' is 2025-11-21 (a Friday), accepted 2025-11-24 00:15:20.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1499
"""

from edgar.offerings.effect import Effect

LYNTRIS_S1_EFFECT = """<?xml version="1.0"?>
<edgarSubmission>
    <schemaVersion>X0101</schemaVersion>
    <submissionType>EFFECT</submissionType>
    <act>33</act>
    <testOrLive>LIVE</testOrLive>
    <effectiveData>
        <finalEffectivenessDispDate>2026-08-18</finalEffectivenessDispDate>
        <finalEffectivenessDispTime>15:30:00</finalEffectivenessDispTime>
        <form>S-1</form>
        <filer>
            <cik>0002132582</cik>
            <entityName>Lyntris Inc.</entityName>
            <fileNumber>333-297657</fileNumber>
        </filer>
    </effectiveData>
</edgarSubmission>
"""

FITNESS_FANATICS_POS_AM_EFFECT = """<?xml version="1.0"?>
<edgarSubmission>
    <schemaVersion>X0101</schemaVersion>
    <submissionType>EFFECT</submissionType>
    <act>33</act>
    <testOrLive>LIVE</testOrLive>
    <effectiveData>
        <finalEffectivenessDispDate>2025-11-21</finalEffectivenessDispDate>
        <accessionNumber>0001493152-25-019212</accessionNumber>
        <submissionType>POS AM</submissionType>
        <filer>
            <cik>0002065232</cik>
            <entityName>Fitness Fanatics Ltd</entityName>
            <fileNumber>333-289484</fileNumber>
        </filer>
    </effectiveData>
</edgarSubmission>
"""


def test_effective_time_is_read_from_the_notice():
    effect = Effect.from_xml(LYNTRIS_S1_EFFECT)
    assert effect.effective_date == "2026-08-18"
    assert effect.effective_time == "15:30:00"
    assert "Effective Time: 15:30:00 ET" in effect.to_context()


def test_effective_time_is_none_when_the_notice_has_none():
    effect = Effect.from_xml(FITNESS_FANATICS_POS_AM_EFFECT)
    assert effect.effective_date == "2025-11-21"
    assert effect.effective_time is None
    assert "Effective Time" not in effect.to_context()
