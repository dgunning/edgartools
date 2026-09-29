from edgar.effect import Effect
from rich import print

effect_xml_1 = """
<edgarSubmission>
    <schemaVersion>X0101</schemaVersion>
    <submissionType>EFFECT</submissionType>
    <act>33</act>
    <testOrLive>LIVE</testOrLive>
    <effectiveData>
        <finalEffectivenessDispDate>2022-11-22</finalEffectivenessDispDate>
        <accessionNumber>0000038723-22-000117</accessionNumber>
        <submissionType>POS AM</submissionType>
        <filer>
            <cik>0000038723</cik>
            <entityName>1st FRANKLIN FINANCIAL CORP</entityName>
            <fileNumber>333-237642</fileNumber>
        </filer>
    </effectiveData>
</edgarSubmission>
"""

effect_xml_2 = """
<?xml version="1.0"?>
<edgarSubmission>
    <schemaVersion>X0101</schemaVersion>
    <submissionType>EFFECT</submissionType>
    <act>33</act>
    <testOrLive>LIVE</testOrLive>
    <effectiveData>
        <finalEffectivenessDispDate>2022-01-11</finalEffectivenessDispDate>
        <finalEffectivenessDispTime>16:00:00</finalEffectivenessDispTime>
        <form>S-1</form>
        <filer>
            <cik>0001848948</cik>
            <entityName>10X Capital Venture Acquisition Corp. III</entityName>
            <fileNumber>333-253868</fileNumber>
        </filer>
    </effectiveData>
</edgarSubmission>
"""


def test_edgar_submission_from_xml():
    edgar_submission: Effect = Effect.from_xml(effect_xml_1)
    print()
    print(edgar_submission)
    assert edgar_submission
    assert edgar_submission.is_live
    assert edgar_submission.submission_type == "EFFECT"
    assert edgar_submission.effective_date == '2022-11-22'
    assert edgar_submission.source_accession_no == '0000038723-22-000117'


def test_edgar_submission_from_xml_format_2():
    edgar_submission: Effect = Effect.from_xml(effect_xml_2)
    assert edgar_submission
    assert edgar_submission.is_live
    assert edgar_submission.submission_type == "EFFECT"
    assert edgar_submission.effective_date == "2022-01-11"
    assert not edgar_submission.source_accession_no
    assert edgar_submission.effectiveness_data.form == "S-1"
    assert edgar_submission.entity == "10X Capital Venture Acquisition Corp. III"
    print(edgar_submission)


def test_effect_filing_source_filing():
    edgar_submission: Effect = Effect.from_xml(effect_xml_1)
    source_filing = edgar_submission.get_source_filing()
    assert source_filing
    assert source_filing.accession_no == edgar_submission.source_accession_no


def test_effect_get_source_filing_by_file_number():
    edgar_submission: Effect = Effect.from_xml(effect_xml_2)
    source_filing = edgar_submission.get_source_filing()
    assert source_filing.form in ["S-1", "S-1/A"]


def test_effect_repr():
    edgar_submission: Effect = Effect.from_xml(effect_xml_2)
    value = edgar_submission.__repr__()
    print(value)