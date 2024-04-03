from edgar import Filing, Attachments


def test_attachments_query():
    filing = Filing(form='10-K', filing_date='2024-04-01', company='AQUABOUNTY TECHNOLOGIES INC', cik=1603978,
                    accession_no='0001603978-24-000013')
    attachments = filing.attachments
    assert len(attachments.files) > 0
    graphics = attachments.files.query("Type=='GRAPHIC'")
    assert len(graphics) == 8

    # test for attachments not found
    powerpoints = attachments.query("Type=='POWERPOINT'")
    assert len(powerpoints) == 0


def test_get_attachment_by_type():
    filing = Filing(form='8-K', filing_date='2024-03-08', company='3M CO', cik=66740,
                    accession_no='0000066740-24-000023')
    attachments = filing.attachments

    print(attachments)
    # Get a single attachment
    attachment = attachments.query("Type=='EX-99.1'")
    assert isinstance(attachment, Attachments)

    # Get multiple attachments
    attachments = attachments.query("Document.str.match('mmm-*')")
    assert len(attachments) == 6

    # No results
    attachments = attachments.query("Document.str.match('DORM-*')")
    assert len(attachments) == 0
