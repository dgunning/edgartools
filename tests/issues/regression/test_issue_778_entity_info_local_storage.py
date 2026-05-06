"""
Regression test for GitHub Issue #778

Problem: xbrl.entity_info crashes with KeyError when XBRL is parsed from local
cached storage, but works fine online.

Root cause: iXBRL filings filed before SEC's Oct-2020 feed format change have
their XBRL data embedded in the .htm document; SEC didn't yet extract a
standalone _htm.xml instance into the feed bundle. The local SGML has all the
linkbases (schema, calculation, definition, label, presentation) but no
instance — so parse_instance_content() never runs and entity_info stays empty.

(Empirically verified: CPB FY2019 10-K filed 2019-09-26 has EX-101.INS in feed;
CPB FY2020 10-K filed 2020-09-24 has only linkbases + .htm, no instance.)

Fix:
1. Pre-populate entity_info with all expected keys (None/False defaults)
   so callers never get KeyError even when instance parsing fails.
2. When instance document is missing from local storage and network fallback
   is allowed, fetch it from the filing homepage (single HTTP request).
3. Add allow_network_fallback parameter to use_local_storage() so users
   can opt into strict offline mode.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from edgar.xbrl.parsers import XBRLParser
from edgar.xbrl.xbrl import XBRL, XBRLAttachments
from edgar.storage._local import is_network_fallback_allowed


EXPECTED_ENTITY_INFO_KEYS = [
    'entity_name', 'ticker', 'identifier', 'document_type',
    'reporting_end_date', 'document_period_end_date',
    'fiscal_year', 'fiscal_period',
    'fiscal_year_end_month', 'fiscal_year_end_day',
    'annual_report', 'quarterly_report', 'amendment',
]


class TestEntityInfoDefaultKeys:
    """entity_info should always have expected keys, even without instance parsing."""

    def test_entity_info_has_all_keys_before_parsing(self):
        """XBRLParser entity_info should have default keys immediately after init."""
        parser = XBRLParser()
        for key in EXPECTED_ENTITY_INFO_KEYS:
            assert key in parser.entity_info, f"Missing key: {key}"

    def test_entity_info_no_keyerror_on_bracket_access(self):
        """Accessing entity_info['identifier'] should not raise KeyError."""
        parser = XBRLParser()
        identifier = parser.entity_info['identifier']
        fiscal_year = parser.entity_info['fiscal_year']
        assert identifier is None
        assert fiscal_year is None

    def test_entity_info_defaults_are_sensible(self):
        """Boolean fields default to False, others to None."""
        parser = XBRLParser()
        info = parser.entity_info
        assert info['annual_report'] is False
        assert info['quarterly_report'] is False
        assert info['amendment'] is False
        assert info['entity_name'] is None
        assert info['identifier'] is None

    def test_xbrl_entity_info_inherits_defaults(self):
        """XBRL object's entity_info property should have defaults."""
        xbrl = XBRL()
        info = xbrl.entity_info
        for key in EXPECTED_ENTITY_INFO_KEYS:
            assert key in info, f"Missing key: {key}"


class TestNetworkFallbackFlag:
    """The allow_network_fallback flag controls whether network requests are allowed."""

    def test_default_allows_network_fallback(self):
        """Network fallback should be allowed by default."""
        # Clear any test-set env var
        old = os.environ.pop('EDGAR_ALLOW_NETWORK_FALLBACK', None)
        try:
            assert is_network_fallback_allowed() is True
        finally:
            if old is not None:
                os.environ['EDGAR_ALLOW_NETWORK_FALLBACK'] = old

    def test_can_disable_network_fallback(self):
        """Setting the env var to 0 should disable fallback."""
        old = os.environ.get('EDGAR_ALLOW_NETWORK_FALLBACK')
        try:
            os.environ['EDGAR_ALLOW_NETWORK_FALLBACK'] = '0'
            assert is_network_fallback_allowed() is False
        finally:
            if old is not None:
                os.environ['EDGAR_ALLOW_NETWORK_FALLBACK'] = old
            else:
                os.environ.pop('EDGAR_ALLOW_NETWORK_FALLBACK', None)

    def test_can_enable_network_fallback(self):
        """Setting the env var to 1 should enable fallback."""
        old = os.environ.get('EDGAR_ALLOW_NETWORK_FALLBACK')
        try:
            os.environ['EDGAR_ALLOW_NETWORK_FALLBACK'] = '1'
            assert is_network_fallback_allowed() is True
        finally:
            if old is not None:
                os.environ['EDGAR_ALLOW_NETWORK_FALLBACK'] = old
            else:
                os.environ.pop('EDGAR_ALLOW_NETWORK_FALLBACK', None)


# Helpers for constructing minimal attachment fixtures that drive XBRLAttachments

def _make_attachment(doc_type, ext, content):
    """Build an attachment-like mock that XBRLAttachments will recognize."""
    a = MagicMock()
    a.document_type = doc_type
    a.extension = ext
    a.content = content
    return a


def _make_attachments(*atts):
    """Build an Attachments-like mock with the given data_files."""
    a = MagicMock()
    a.data_files = list(atts)
    return a


# Empirically-shaped fixtures: pre-Oct-2020 iXBRL feed bundles have linkbases
# but no separate instance file; the homepage carries the instance.
_LOCAL_LINKBASES_NO_INSTANCE = lambda: _make_attachments(  # noqa: E731
    _make_attachment('EX-101.SCH', '.xsd', '<xs:schema/>'),
    _make_attachment('EX-101.LAB', '.xml', '<labels/>'),
    _make_attachment('EX-101.PRE', '.xml', '<pre/>'),
    _make_attachment('EX-101.CAL', '.xml', '<cal/>'),
    _make_attachment('EX-101.DEF', '.xml', '<def/>'),
)

_HOMEPAGE_INSTANCE_CONTENT = (
    '<?xml version="1.0"?>'
    '<xbrl xmlns="http://www.xbrl.org/2003/instance">'
    '<identifier>1234567</identifier>'
    '</xbrl>'
)
_HOMEPAGE_WITH_INSTANCE = lambda: _make_attachments(  # noqa: E731
    _make_attachment('EX-101.INS', '.xml', _HOMEPAGE_INSTANCE_CONTENT),
)
_HOMEPAGE_WITHOUT_INSTANCE = lambda: _make_attachments()  # noqa: E731


def _make_filing(local_attachments, homepage_attachments,
                 accession='0000016732-20-000111', form='10-K'):
    """Build a Filing-like mock for from_filing()."""
    filing = MagicMock()
    filing.form = form
    filing.accession_no = accession
    filing.attachments = local_attachments
    filing.homepage.attachments = homepage_attachments
    return filing


class TestNetworkFallbackPath:
    """The inner fallback fires only when:
      (1) local SGML has linkbases but no XBRL instance, AND
      (2) network fallback is allowed.

    These tests verify the routing logic — that parse_instance_content is
    called with the homepage's instance content, not skipped, and not
    called from local content. The actual XBRL parsing is covered by other
    tests; we patch parser methods so the test stays fast.
    """

    def _patch_parsers(self):
        """Stub all linkbase parser methods to no-op."""
        return [
            patch.object(XBRLParser, 'parse_schema_content'),
            patch.object(XBRLParser, 'parse_labels_content'),
            patch.object(XBRLParser, 'parse_calculation_content'),
            patch.object(XBRLParser, 'parse_definition_content'),
            patch.object(XBRLParser, 'parse_presentation_content'),
        ]

    def test_inner_fallback_fetches_instance_when_local_lacks_it(self):
        """Local has linkbases-only + fallback enabled → instance fetched from homepage."""
        from edgar.xbrl.xbrl import XBRL

        filing = _make_filing(_LOCAL_LINKBASES_NO_INSTANCE(),
                              _HOMEPAGE_WITH_INSTANCE())

        patches = self._patch_parsers()
        for p in patches:
            p.start()
        try:
            with patch('edgar.storage.is_using_local_storage', return_value=True), \
                 patch('edgar.storage.is_network_fallback_allowed', return_value=True), \
                 patch.object(XBRLParser, 'parse_instance_content') as parse_instance:
                XBRL.from_filing(filing)
            parse_instance.assert_called_once_with(_HOMEPAGE_INSTANCE_CONTENT)
        finally:
            for p in patches:
                p.stop()

    def test_no_fallback_when_disabled(self):
        """Fallback disabled → parse_instance_content not called even if homepage has it."""
        from edgar.xbrl.xbrl import XBRL

        filing = _make_filing(_LOCAL_LINKBASES_NO_INSTANCE(),
                              _HOMEPAGE_WITH_INSTANCE())

        patches = self._patch_parsers()
        for p in patches:
            p.start()
        try:
            with patch('edgar.storage.is_using_local_storage', return_value=True), \
                 patch('edgar.storage.is_network_fallback_allowed', return_value=False), \
                 patch.object(XBRLParser, 'parse_instance_content') as parse_instance:
                XBRL.from_filing(filing)
            parse_instance.assert_not_called()
        finally:
            for p in patches:
                p.stop()

    def test_no_fallback_when_homepage_also_lacks_instance(self):
        """Local AND homepage both lack instance → parse_instance_content not called."""
        from edgar.xbrl.xbrl import XBRL

        filing = _make_filing(_LOCAL_LINKBASES_NO_INSTANCE(),
                              _HOMEPAGE_WITHOUT_INSTANCE())

        patches = self._patch_parsers()
        for p in patches:
            p.start()
        try:
            with patch('edgar.storage.is_using_local_storage', return_value=True), \
                 patch('edgar.storage.is_network_fallback_allowed', return_value=True), \
                 patch.object(XBRLParser, 'parse_instance_content') as parse_instance:
                XBRL.from_filing(filing)
            parse_instance.assert_not_called()
        finally:
            for p in patches:
                p.stop()

    def test_no_fallback_when_local_has_instance(self):
        """Local SGML already has the instance → no homepage fetch, parsed locally."""
        from edgar.xbrl.xbrl import XBRL

        local_with_instance = _make_attachments(
            _make_attachment('EX-101.SCH', '.xsd', '<xs:schema/>'),
            _make_attachment('EX-101.INS', '.xml', _HOMEPAGE_INSTANCE_CONTENT),
        )
        # Attach a different instance to homepage so we can detect if the wrong path runs
        wrong_homepage = _make_attachments(
            _make_attachment('EX-101.INS', '.xml',
                             '<xbrl><identifier>WRONG</identifier></xbrl>'),
        )
        filing = _make_filing(local_with_instance, wrong_homepage)

        patches = self._patch_parsers()
        for p in patches:
            p.start()
        try:
            with patch('edgar.storage.is_using_local_storage', return_value=True), \
                 patch('edgar.storage.is_network_fallback_allowed', return_value=True), \
                 patch.object(XBRLParser, 'parse_instance_content') as parse_instance:
                XBRL.from_filing(filing)
            # Must use the local instance, not the homepage one
            parse_instance.assert_called_once_with(_HOMEPAGE_INSTANCE_CONTENT)
        finally:
            for p in patches:
                p.stop()
