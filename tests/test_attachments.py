from edgar import Filing


def test_attachments_query():
    filing = Filing(form='10-K', filing_date='2024-04-01', company='AQUABOUNTY TECHNOLOGIES INC', cik=1603978, accession_no='0001603978-24-000013')
    attachments = filing.attachments
    assert len(attachments.files) > 0
    graphics = attachments.files.query("Type=='GRAPHIC'")
    assert len(graphics) == 8

    # test for attachments not found
    powerpoints = attachments.query("Type=='POWERPOINT'")
    assert len(powerpoints) == 0
