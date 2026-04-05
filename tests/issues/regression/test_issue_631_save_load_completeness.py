"""
Regression test for Issue #631: Filing.save()/load() incomplete serialization

GitHub Issue: https://github.com/dgunning/edgartools/issues/631
Reporter: mpreiss9

Bug (FIXED): When Filing.save() is called without first accessing lazy-loaded
data (e.g., filing.xbrl()), the pickled object has _sgml = None. On Filing.load(),
subsequent operations like filing.xbrl() must re-download SGML from SEC, which can
fail (rate limiting, network issues), producing None content in Attachment objects.
This crashes XBRLAttachments.__init__ with TypeError: argument of type 'NoneType'
is not iterable.

Fix:
1. Filing.save() now calls self.sgml() before pickling to ensure SGML is populated
2. XBRLAttachments.__init__ guards against None content defensively

Test Strategy:
- Save a filing to pickle WITHOUT pre-loading xbrl
- Load it back and verify xbrl() works without network access issues
- Verify the loaded filing has _sgml populated (not None)
"""

import pickle
import tempfile
from pathlib import Path

import pytest

from edgar import Filing


@pytest.mark.network
@pytest.mark.regression
def test_issue_631_save_populates_sgml():
    """
    Verify Filing.save() populates _sgml before pickling.

    Before the fix, saving without accessing lazy data left _sgml as None.
    """
    # Apple 10-K filing
    filing = Filing(form='10-K', company='Apple Inc.', cik=320193,
                    filing_date='2024-11-01',
                    accession_no='0000320193-24-000123')

    # DO NOT call filing.xbrl() or filing.sgml() before saving
    # This is the exact scenario that triggered the bug
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "test_filing.pkl"
        filing.save(filepath)

        # Load and verify _sgml is populated
        loaded = Filing.load(filepath)
        assert loaded._sgml is not None, (
            "Filing._sgml should be populated after save/load, "
            "but was None (the original bug)"
        )


@pytest.mark.network
@pytest.mark.regression
def test_issue_631_loaded_filing_xbrl_works():
    """
    Verify that xbrl() works on a loaded filing without needing network access.

    This is the core user-facing bug: save a filing, load it later, and
    filing.xbrl() crashes because SGML wasn't serialized.
    """
    filing = Filing(form='10-K', company='Apple Inc.', cik=320193,
                    filing_date='2024-11-01',
                    accession_no='0000320193-24-000123')

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "test_filing.pkl"
        filing.save(filepath)

        loaded = Filing.load(filepath)
        # This should work without any network calls since SGML is embedded
        xbrl_data = loaded.xbrl()
        assert xbrl_data is not None, (
            "xbrl() should work on a loaded filing without network access"
        )


@pytest.mark.network
@pytest.mark.regression
def test_issue_631_save_to_directory():
    """
    Verify save() to a directory also populates SGML.
    """
    filing = Filing(form='10-K', company='Apple Inc.', cik=320193,
                    filing_date='2024-11-01',
                    accession_no='0000320193-24-000123')

    with tempfile.TemporaryDirectory() as tmpdir:
        filing.save(tmpdir)

        # The file should be named by accession number
        expected_path = Path(tmpdir) / f"{filing.accession_no}.pkl"
        assert expected_path.exists()

        loaded = Filing.load(expected_path)
        assert loaded._sgml is not None


@pytest.mark.network
@pytest.mark.regression
def test_issue_631_xbrl_attachments_none_content_guard():
    """
    Verify XBRLAttachments handles None content gracefully.

    This is the defensive fix: even if content is None for some reason,
    XBRLAttachments should not crash with TypeError.
    """
    from edgar.xbrl.xbrl import XBRLAttachments
    from unittest.mock import MagicMock

    # Create a mock attachment with None content
    mock_attachment = MagicMock()
    mock_attachment.document_type = "XML"
    mock_attachment.extension = ".xml"
    mock_attachment.content = None  # This is the bug scenario

    mock_attachments = MagicMock()
    mock_attachments.data_files = [mock_attachment]

    # This should NOT raise TypeError
    xbrl_attachments = XBRLAttachments(mock_attachments)
    assert 'instance' not in xbrl_attachments._documents
