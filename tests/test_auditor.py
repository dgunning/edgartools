"""Verification tests for auditor information extraction from XBRL DEI facts."""
from unittest.mock import MagicMock

import pytest

from edgar import Company, Filing
from edgar.company_reports.auditor import AuditorInfo, extract_auditor_info


class TestAuditorInfoUnit:
    """Fast unit tests using mock XBRL data."""

    def _make_mock_xbrl(self, facts_map):
        """Create a mock XBRL object returning given element->value mappings."""
        xbrl = MagicMock()

        def find_facts(element_name, **kwargs):
            value = facts_map.get(element_name)
            if value is None:
                return {}
            fact = MagicMock()
            fact.value = value
            return {'ctx0': {'fact': fact, 'dimension_info': [], 'dimension_key': ''}}

        xbrl._find_facts_for_element = find_facts
        return xbrl

    @pytest.mark.fast
    def test_extract_all_four_fields(self):
        xbrl = self._make_mock_xbrl({
            'dei_AuditorName': 'Ernst & Young LLP',
            'dei_AuditorLocation': 'San Jose, California',
            'dei_AuditorFirmId': '42',
            'dei_IcfrAuditorAttestationFlag': 'true',
        })
        info = extract_auditor_info(xbrl)
        assert info is not None
        assert info.name == 'Ernst & Young LLP'
        assert info.location == 'San Jose, California'
        assert info.firm_id == 42
        assert info.icfr_attestation is True

    @pytest.mark.fast
    def test_returns_none_when_no_auditor_name(self):
        xbrl = self._make_mock_xbrl({})
        assert extract_auditor_info(xbrl) is None

    @pytest.mark.fast
    def test_icfr_false(self):
        xbrl = self._make_mock_xbrl({
            'dei_AuditorName': 'Test LLP',
            'dei_AuditorLocation': 'New York',
            'dei_AuditorFirmId': '99',
            'dei_IcfrAuditorAttestationFlag': 'false',
        })
        info = extract_auditor_info(xbrl)
        assert info.icfr_attestation is False

    @pytest.mark.fast
    def test_firm_id_defaults_to_zero_on_bad_input(self):
        xbrl = self._make_mock_xbrl({
            'dei_AuditorName': 'Test LLP',
            'dei_AuditorFirmId': 'not_a_number',
        })
        info = extract_auditor_info(xbrl)
        assert info.firm_id == 0

    @pytest.mark.fast
    def test_repr_renders_without_error(self):
        info = AuditorInfo(name='EY', location='NYC', firm_id=42, icfr_attestation=True)
        text = repr(info)
        assert 'EY' in text

    @pytest.mark.fast
    def test_rich_renders_without_error(self):
        info = AuditorInfo(name='EY', location='NYC', firm_id=42, icfr_attestation=True)
        panel = info.__rich__()
        assert panel is not None


class TestAuditorInfoNetwork:
    """Network tests with ground-truth values from real SEC filings."""

    @pytest.mark.network
    def test_apple_auditor_ey(self):
        """AAPL 10-K auditor is Ernst & Young LLP, PCAOB ID 42."""
        filing = Filing(company='Apple Inc.', cik=320193, form='10-K',
                        filing_date='2024-11-01', accession_no='0000320193-24-000123')
        tenk = filing.obj()
        auditor = tenk.auditor
        assert auditor is not None
        assert auditor.name == 'Ernst & Young LLP'
        assert auditor.firm_id == 42
        assert 'California' in auditor.location
        assert auditor.icfr_attestation is True

    @pytest.mark.network
    def test_microsoft_auditor_deloitte(self):
        """MSFT 10-K auditor is Deloitte & Touche LLP, PCAOB ID 34."""
        filing = Filing(company='MICROSOFT CORP', cik=789019, form='10-K',
                        filing_date='2024-07-30', accession_no='0000950170-24-087843')
        tenk = filing.obj()
        auditor = tenk.auditor
        assert auditor is not None
        assert auditor.name == 'DELOITTE & TOUCHE LLP'
        assert auditor.firm_id == 34
        assert auditor.icfr_attestation is True

    @pytest.mark.network
    def test_jpmorgan_auditor_pwc(self):
        """JPM 10-K auditor is PricewaterhouseCoopers LLP, PCAOB ID 238."""
        filing = Filing(company='JPMORGAN CHASE & CO', cik=19617, form='10-K',
                        filing_date='2026-02-13', accession_no='0001628280-26-008131')
        tenk = filing.obj()
        auditor = tenk.auditor
        assert auditor is not None
        assert auditor.name == 'PricewaterhouseCoopers LLP'
        assert auditor.firm_id == 238
        assert auditor.icfr_attestation is True

    @pytest.mark.network
    def test_tenq_has_no_auditor(self):
        """10-Q filings do not include auditor DEI facts — returns None."""
        filing = Filing(company='Apple Inc.', cik=320193, form='10-Q',
                        filing_date='2024-08-02', accession_no='0000320193-24-000081')
        tenq = filing.obj()
        assert tenq.auditor is None
