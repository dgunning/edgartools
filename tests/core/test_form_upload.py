from edgar import Filing

def test_get_text_of_upload_form():
    filing = Filing(form='UPLOAD', filing_date='2024-03-01', company='Antelope Enterprise Holdings Ltd', cik=1470683,
                    accession_no='0000000000-24-002373')
    text_content = filing.text()
    assert 'Antelope Enterprise' in text_content


def test_view_text_of_upload_form(capsys):
    filing = Filing(form='UPLOAD', filing_date='2024-03-01', company='Antelope Enterprise Holdings Ltd', cik=1470683,
                    accession_no='0000000000-24-002373')
    print()
    filing.view()
    captured = capsys.readouterr()
    text = captured.out
    assert 'Antelope Enterprise' in text


def test_form_upload_markdown():
    filing = Filing(form='UPLOAD', filing_date='2024-03-01', company='Antelope Enterprise Holdings Ltd', cik=1470683,
                    accession_no='0000000000-24-002373')
    md = filing.markdown()
    assert 'Antelope Enterprise' in md
