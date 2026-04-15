"""
Regression test for GitHub Issue #778

Problem: xbrl.entity_info crashes with KeyError when XBRL is parsed from local
cached storage, but works fine online.

Root cause: SEC feed files before ~Oct 2020 did not include the extracted iXBRL
instance document (_htm.xml). The local .nc file has the linkbases (schema,
labels, etc.) but not the instance — so parse_instance_content() never runs
and entity_info stays empty.

Fix:
1. Pre-populate entity_info with all expected keys (None/False defaults)
   so callers never get KeyError even when instance parsing fails.
2. When instance document is missing from local storage and network fallback
   is allowed, fetch it from the filing homepage (single HTTP request).
3. Add allow_network_fallback parameter to use_local_storage() so users
   can opt into strict offline mode.
"""
import os
import pytest
from unittest.mock import MagicMock, PropertyMock, patch

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
