import tempfile
from pathlib import Path
from rich import print
import pytest

from edgar import Filing
from edgar.attachments import Attachment, Attachments
from edgar.httprequests import download_file


def test_attachments_query():
    filing = Filing(form='10-K', filing_date='2024-04-01', company='AQUABOUNTY TECHNOLOGIES INC', cik=1603978,
                    accession_no='0001603978-24-000013')
    attachments = filing.attachments
    assert len(attachments) > 0
    graphics = attachments.query("document_type=='GRAPHIC'")
    assert len(graphics) == 8

    # test for attachments not found
    powerpoints = attachments.query("document_type=='POWERPOINT'")
    assert len(powerpoints) == 0


def test_get_attachment_by_type():
    filing = Filing(form='8-K', filing_date='2024-03-08', company='3M CO', cik=66740,
                    accession_no='0000066740-24-000023')
    attachments = filing.attachments

    # Get a single attachment
    attachment = attachments.query("document_type=='EX-99.1'")
    assert isinstance(attachment, Attachments)

    # Get multiple attachments
    result = attachments.query("re.match('mmm-*', document)")
    assert len(result) == 6

    # No results
    result = attachments.query("re.match('DORM-*', document)")
    assert len(result) == 0


def test_loop_through_attachments():
    filing = Filing(form='8-K', filing_date='2024-03-08', company='3M CO', cik=66740,
                    accession_no='0000066740-24-000023')
    for attachment in filing.attachments:
        assert attachment
        assert isinstance(attachment, Attachment)


def test_attachment_is_empty():
    filing = Filing(form='10-Q', filing_date='2000-05-11', company='APPLE COMPUTER INC', cik=320193,
                    accession_no='0000912057-00-023442')
    attachments = filing.attachments
    print(attachments)
    attachment: Attachment = attachments[0]
    assert attachment.document == ''
    assert attachment.empty


@pytest.fixture
def sample_attachments():
    return [
        Attachment(
            sequence_number="1",
            description="Sample document 1",
            document="doc1.txt",
            ixbrl=False,
            path="doc1.txt",
            document_type="EX-99",
            size=1024
        ),
        Attachment(
            sequence_number="2",
            description="Sample document 2",
            document="doc2.txt",
            ixbrl=False,
            path="doc2.txt",
            document_type="EX-99.1",
            size=2048
        )
    ]


@pytest.fixture
def attachments(sample_attachments):
    return Attachments(document_files=sample_attachments, data_files=None, primary_documents=[])


def test_download_to_directory():
    filing = Filing(form='4', filing_date='2024-05-24', company='t Hart Cees', cik=1983327,
                    accession_no='0000950170-24-064537')
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        attachments = filing.attachments
        attachments.download(temp_path)

        for attachment in attachments.documents:
            file_path = temp_path / attachment.document
            assert file_path.exists()


def test_download_to_archive():
    filing = Filing(form='4', filing_date='2024-05-24', company='t Hart Cees', cik=1983327,
                    accession_no='0000950170-24-064537')
    attachments = filing.attachments
    with tempfile.TemporaryDirectory() as temp_dir:
        archive_path = Path(temp_dir) / "attachments.zip"
        attachments.download(archive_path, archive=True)

        import zipfile
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            archive_names = zipf.namelist()
            for attachment in attachments.documents:
                assert attachment.document in archive_names


def test_attachment_list_url():
    filing = Filing(form='8-K', filing_date='2024-03-08', company='3M CO', cik=66740,
                    accession_no='0000066740-24-000023')
    #assert filing.attachment_list_url == 'https://www.sec.gov/Archives/edgar/data/1983327/000095017024064537/index.json'
    files = download_file(f"{filing.base_dir}/index.json")
    print(files)
    print(filing.attachments)
    header_url = f"{filing.base_dir}/0000066740-24-000023-index-headers.html"
    print(header_url)
    index_headers = download_file(header_url)
    print(index_headers)



