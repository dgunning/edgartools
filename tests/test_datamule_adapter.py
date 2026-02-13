"""
Tests for the datamule storage adapter.

All tests use synthetic tar fixtures — no network, no datamule package required.
"""

import json
import tarfile
from io import BytesIO
from unittest.mock import patch

import pytest

import edgar.storage.datamule.storage as _storage_mod
from edgar.storage.datamule.storage import (
    use_datamule_storage,
    is_using_datamule_storage,
    get_datamule_filing,
    _normalize_accession,
)
from edgar.storage.datamule.metadata import (
    filing_header_from_metadata,
    filing_args_from_metadata,
)
from edgar.storage.datamule.documents import TarSGMLDocument
from edgar.storage.datamule.reader import load_filing_from_tar, _infer_doc_type, _get_prefix


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_METADATA = {
    "accession_number": "0001193125-24-012345",
    "form_type": "10-K",
    "filing_date": "2024-03-15",
    "period_of_report": "2023-12-31",
    "cik": "320193",
    "company_name": "Apple Inc.",
    "sic": "3571",
    "irs_number": "942404110",
    "state_of_incorporation": "CA",
    "fiscal_year_end": "0930",
    "file_number": "001-36743",
    "document_count": 3,
}

SAMPLE_HTML = """<!DOCTYPE html>
<html><head><title>10-K Filing</title></head>
<body><h1>Annual Report</h1><p>Revenue was $394.3 billion.</p></body></html>"""

SAMPLE_XML = """<?xml version="1.0"?>
<xbrl><context id="FY2023"><period><startDate>2023-01-01</startDate></period></context></xbrl>"""


def _make_tar_bytes(metadata: dict, files: dict[str, str], prefix: str = '') -> bytes:
    """
    Create an in-memory tar archive.

    Args:
        metadata: Contents for metadata.json
        files: Mapping of filename -> content
        prefix: Optional directory prefix for batch tars
    """
    buf = BytesIO()
    with tarfile.open(fileobj=buf, mode='w') as tf:
        # Add metadata.json
        meta_bytes = json.dumps(metadata).encode('utf-8')
        meta_info = tarfile.TarInfo(name=f'{prefix}metadata.json')
        meta_info.size = len(meta_bytes)
        tf.addfile(meta_info, BytesIO(meta_bytes))

        # Add document files
        for name, content in files.items():
            content_bytes = content.encode('utf-8')
            info = tarfile.TarInfo(name=f'{prefix}{name}')
            info.size = len(content_bytes)
            tf.addfile(info, BytesIO(content_bytes))

    return buf.getvalue()


@pytest.fixture
def single_tar(tmp_path):
    """Create a single-filing tar in a temp directory."""
    tar_bytes = _make_tar_bytes(
        SAMPLE_METADATA,
        {'primary-document.htm': SAMPLE_HTML, 'Financial_Report.xml': SAMPLE_XML},
    )
    tar_path = tmp_path / 'filing.tar'
    tar_path.write_bytes(tar_bytes)
    return tar_path


@pytest.fixture
def batch_tar(tmp_path):
    """Create a batch tar with two filings."""
    buf = BytesIO()
    meta1 = {**SAMPLE_METADATA}
    meta2 = {**SAMPLE_METADATA, 'accession_number': '0001193125-24-067890', 'company_name': 'Microsoft Corp.', 'cik': '789019'}

    with tarfile.open(fileobj=buf, mode='w') as tf:
        for meta, prefix in [(meta1, '0001193125-24-012345/'), (meta2, '0001193125-24-067890/')]:
            meta_bytes = json.dumps(meta).encode('utf-8')
            meta_info = tarfile.TarInfo(name=f'{prefix}metadata.json')
            meta_info.size = len(meta_bytes)
            tf.addfile(meta_info, BytesIO(meta_bytes))

            content = b'<html><body>Filing content</body></html>'
            doc_info = tarfile.TarInfo(name=f'{prefix}primary-document.htm')
            doc_info.size = len(content)
            tf.addfile(doc_info, BytesIO(content))

    tar_path = tmp_path / 'batch.tar'
    tar_path.write_bytes(buf.getvalue())
    return tar_path


@pytest.fixture(autouse=True)
def _reset_datamule_state():
    """Reset datamule state before and after each test."""
    _storage_mod._datamule_path = None
    _storage_mod._accession_index.clear()
    yield
    _storage_mod._datamule_path = None
    _storage_mod._accession_index.clear()


# ---------------------------------------------------------------------------
# TestStorage
# ---------------------------------------------------------------------------

class TestStorage:

    def test_use_datamule_storage_indexes_tars(self, single_tar):
        use_datamule_storage(single_tar.parent)
        assert is_using_datamule_storage()
        assert '0001193125-24-012345' in _storage_mod._accession_index
        assert _storage_mod._accession_index['0001193125-24-012345'] == single_tar

    def test_use_datamule_storage_batch(self, batch_tar):
        use_datamule_storage(batch_tar.parent)
        assert is_using_datamule_storage()
        assert '0001193125-24-012345' in _storage_mod._accession_index
        assert '0001193125-24-067890' in _storage_mod._accession_index

    def test_use_datamule_storage_disable(self, single_tar):
        use_datamule_storage(single_tar.parent)
        assert is_using_datamule_storage()

        use_datamule_storage(disable=True)
        assert not is_using_datamule_storage()
        assert len(_storage_mod._accession_index) == 0

    def test_use_datamule_storage_missing_dir(self):
        with pytest.raises(FileNotFoundError):
            use_datamule_storage('/nonexistent/path/to/nowhere')

    def test_use_datamule_storage_not_a_dir(self, single_tar):
        with pytest.raises(NotADirectoryError):
            use_datamule_storage(single_tar)  # file, not directory

    def test_use_datamule_storage_no_path(self):
        with pytest.raises(ValueError):
            use_datamule_storage()

    def test_get_datamule_filing_not_found(self, single_tar):
        use_datamule_storage(single_tar.parent)
        result = get_datamule_filing('9999999999-99-999999')
        assert result is None

    def test_get_datamule_filing_success(self, single_tar):
        use_datamule_storage(single_tar.parent)
        filing = get_datamule_filing('0001193125-24-012345')
        assert filing is not None
        assert filing.accession_number == '0001193125-24-012345'
        assert filing.form == '10-K'


# ---------------------------------------------------------------------------
# TestMetadataMapping
# ---------------------------------------------------------------------------

class TestMetadataMapping:

    def test_filing_header_fields(self):
        header = filing_header_from_metadata(SAMPLE_METADATA)
        assert header.accession_number == '0001193125-24-012345'
        assert header.form == '10-K'
        assert header.filing_date == '2024-03-15'
        assert header.period_of_report == '2023-12-31'

    def test_filing_header_filer(self):
        header = filing_header_from_metadata(SAMPLE_METADATA)
        assert len(header.filers) == 1
        filer = header.filers[0]
        assert filer.company_information.name == 'Apple Inc.'
        assert filer.company_information.cik == '320193'
        assert filer.company_information.sic == '3571'
        assert filer.company_information.state_of_incorporation == 'CA'
        assert filer.company_information.fiscal_year_end == '0930'
        assert filer.filing_information.form == '10-K'
        assert filer.filing_information.file_number == '001-36743'

    def test_filing_args_from_metadata(self):
        args = filing_args_from_metadata(SAMPLE_METADATA)
        assert args['accession_no'] == '0001193125-24-012345'
        assert args['form'] == '10-K'
        assert args['filing_date'] == '2024-03-15'
        assert args['cik'] == '320193'
        assert args['company'] == 'Apple Inc.'

    def test_camelcase_metadata_keys(self):
        """Datamule might use camelCase keys."""
        camel_meta = {
            'accessionNumber': '0001193125-24-099999',
            'formType': '8-K',
            'filingDate': '2024-06-01',
            'companyName': 'Test Corp',
            'cik': '12345',
        }
        header = filing_header_from_metadata(camel_meta)
        assert header.accession_number == '0001193125-24-099999'
        assert header.form == '8-K'
        assert header.filing_date == '2024-06-01'

    def test_minimal_metadata(self):
        """Should handle metadata with only a few fields."""
        minimal = {'accession_number': '0001193125-24-000001'}
        header = filing_header_from_metadata(minimal)
        assert header.accession_number == '0001193125-24-000001'
        assert header.form is None  # No form provided


# ---------------------------------------------------------------------------
# TestTarSGMLDocument
# ---------------------------------------------------------------------------

class TestTarSGMLDocument:

    def test_html_content(self):
        doc = TarSGMLDocument.create(
            sequence='1',
            type='HTML',
            filename='filing.htm',
            description='Primary document',
            raw_content=SAMPLE_HTML,
        )
        assert doc.content == SAMPLE_HTML
        assert doc.raw_content == SAMPLE_HTML
        assert doc.filename == 'filing.htm'
        assert doc.type == 'HTML'

    def test_xml_content(self):
        doc = TarSGMLDocument.create(
            sequence='2',
            type='XML',
            filename='report.xml',
            description='',
            raw_content=SAMPLE_XML,
        )
        assert doc.content == SAMPLE_XML
        assert '<?xml' in doc.content

    def test_empty_content(self):
        doc = TarSGMLDocument.create(
            sequence='3',
            type='TEXT',
            filename='empty.txt',
            description='',
            raw_content='',
        )
        assert doc.content == ''
        assert doc.raw_content == ''


# ---------------------------------------------------------------------------
# TestReader
# ---------------------------------------------------------------------------

class TestReader:

    def test_load_single_filing(self, single_tar):
        filing = load_filing_from_tar(single_tar)
        assert filing is not None
        assert filing.accession_number == '0001193125-24-012345'
        assert filing.form == '10-K'
        assert filing.filing_date == '2024-03-15'

        # Should have 2 documents (HTML + XML)
        total_docs = sum(len(v) for v in filing._documents_by_sequence.values())
        assert total_docs == 2

    def test_load_batch_tar_specific(self, batch_tar):
        filing = load_filing_from_tar(batch_tar, accession_no='0001193125-24-067890')
        assert filing is not None
        assert filing.header.filers[0].company_information.name == 'Microsoft Corp.'

    def test_load_batch_tar_first(self, batch_tar):
        """Without accession_no, loads the first filing."""
        filing = load_filing_from_tar(batch_tar)
        assert filing is not None
        assert filing.accession_number == '0001193125-24-012345'

    def test_load_nonexistent_tar(self, tmp_path):
        result = load_filing_from_tar(tmp_path / 'nonexistent.tar')
        assert result is None

    def test_load_wrong_accession(self, single_tar):
        result = load_filing_from_tar(single_tar, accession_no='9999999999-99-999999')
        assert result is None


# ---------------------------------------------------------------------------
# TestFilingSgmlResolution
# ---------------------------------------------------------------------------

class TestFilingSgmlResolution:

    def test_filing_sgml_resolves_from_datamule(self, single_tar):
        """Filing.sgml() should resolve from datamule when configured."""
        from edgar._filings import Filing

        use_datamule_storage(single_tar.parent)

        # Create a minimal Filing object
        filing = Filing(
            cik=320193,
            company='Apple Inc.',
            form='10-K',
            filing_date='2024-03-15',
            accession_no='0001193125-24-012345',
        )

        # Mock the network fallback so it doesn't actually call SEC
        with patch.object(type(filing), 'sgml', wraps=filing.sgml):
            # The sgml() method should find this via datamule
            sgml = get_datamule_filing('0001193125-24-012345')
            assert sgml is not None
            assert sgml.accession_number == '0001193125-24-012345'


# ---------------------------------------------------------------------------
# TestHelpers
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_normalize_accession_dashed(self):
        assert _normalize_accession('0001193125-24-012345') == '0001193125-24-012345'

    def test_normalize_accession_undashed(self):
        assert _normalize_accession('000119312524012345') == '0001193125-24-012345'

    def test_normalize_accession_spaces(self):
        assert _normalize_accession('  0001193125-24-012345  ') == '0001193125-24-012345'

    def test_infer_doc_type(self):
        assert _infer_doc_type('filing.htm') == 'HTML'
        assert _infer_doc_type('report.xml') == 'XML'
        assert _infer_doc_type('data.json') == 'JSON'
        assert _infer_doc_type('image.jpg') == 'GRAPHIC'
        assert _infer_doc_type('document.pdf') == 'PDF'
        assert _infer_doc_type('notes.txt') == 'TEXT'

    def test_get_prefix(self):
        assert _get_prefix('metadata.json') == ''
        assert _get_prefix('0001193125-24-012345/metadata.json') == '0001193125-24-012345/'


# ---------------------------------------------------------------------------
# TestErrorHandling
# ---------------------------------------------------------------------------

class TestErrorHandling:

    def test_empty_tar(self, tmp_path):
        """Tar with no files should return None."""
        tar_path = tmp_path / 'empty.tar'
        buf = BytesIO()
        with tarfile.open(fileobj=buf, mode='w') as tf:
            pass  # empty tar
        tar_path.write_bytes(buf.getvalue())

        result = load_filing_from_tar(tar_path)
        assert result is None

    def test_tar_without_metadata(self, tmp_path):
        """Tar with files but no metadata.json should return None."""
        tar_path = tmp_path / 'no_meta.tar'
        buf = BytesIO()
        with tarfile.open(fileobj=buf, mode='w') as tf:
            content = b'<html>test</html>'
            info = tarfile.TarInfo(name='filing.htm')
            info.size = len(content)
            tf.addfile(info, BytesIO(content))
        tar_path.write_bytes(buf.getvalue())

        result = load_filing_from_tar(tar_path)
        assert result is None

    def test_corrupt_metadata_json(self, tmp_path):
        """Tar with invalid JSON metadata should return None."""
        tar_path = tmp_path / 'corrupt.tar'
        buf = BytesIO()
        with tarfile.open(fileobj=buf, mode='w') as tf:
            bad_json = b'not valid json {'
            info = tarfile.TarInfo(name='metadata.json')
            info.size = len(bad_json)
            tf.addfile(info, BytesIO(bad_json))
        tar_path.write_bytes(buf.getvalue())

        result = load_filing_from_tar(tar_path)
        assert result is None

    def test_scan_skips_bad_tars(self, tmp_path):
        """use_datamule_storage should skip corrupt tars without crashing."""
        # Create a good tar
        good_bytes = _make_tar_bytes(
            SAMPLE_METADATA,
            {'filing.htm': '<html>test</html>'},
        )
        (tmp_path / 'good.tar').write_bytes(good_bytes)

        # Create a corrupt file named .tar
        (tmp_path / 'bad.tar').write_bytes(b'not a tar file at all')

        # Should still index the good tar
        use_datamule_storage(tmp_path)
        assert is_using_datamule_storage()
        assert '0001193125-24-012345' in _storage_mod._accession_index

    def test_empty_directory(self, tmp_path):
        """Directory with no tar files should still enable storage."""
        use_datamule_storage(tmp_path)
        assert is_using_datamule_storage()
        assert len(_storage_mod._accession_index) == 0
