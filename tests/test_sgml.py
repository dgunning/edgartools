from edgar.sgml import stream_documents

def test_parse_secdocument():
    source = "https://www.sec.gov/Archives/edgar/data/1894188/000189418823000007/0001894188-23-000007.txt"
    for document in stream_documents(source):
        print(document)
        if document.type == "INFORMATION TABLE":
            assert document.sequence == "2"
            assert document.filename == "index.xml"
            assert document.text_content.startswith('<?xml version="1.0"')