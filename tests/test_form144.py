from pathlib import Path
from edgar.form144 import Form144
from edgar import Filing



def test_form_144_from_xml():
    form144_xml = Path('data/144/EDGAR Form 144 XML Samples/Sample 144.xml').read_text()
    form144 = Form144.parse_xml(form144_xml)
    print("------\nForm 144\n------")
    print(form144)


def test_form144_from_filing():
    filing = Filing(form='144/A', filing_date='2022-12-22', company='Assure Holdings Corp.', cik=1798270,
                    accession_no='0001886261-22-000004')
    form144 = Form144.from_filing(filing)
    print(form144)
