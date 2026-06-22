"""
Regression tests for two Offerings bugs reported on Airbnb (ABNB) filings.

- gh-868: ``RegistrationS1.underwriting.lead_manager`` returned a stray lock-up
  table header ('Earliest Date Available for Sale in the Public Market') instead
  of the real lead underwriter. The junk leaked through the underwriter-table
  extractor's trust_structure branch and the S-1 consumer applied no name
  validation.

- gh-869: A 424B4 IPO final prospectus (mixed primary+secondary) was classified
  as ``OfferingType.PIPE_RESALE`` at high confidence because the PIPE-resale
  signals (no_proceeds_cover + selling_stockholder_cover) co-occur on an IPO
  cover and were checked before the IPO logic in the cascade.

Ground truth: Airbnb's December 2020 IPO, registration file 333-250118, led by
Morgan Stanley with Goldman Sachs, priced at $68.00/share.
"""
import pytest

from edgar import get_by_accession_number
from edgar.offerings import RegistrationS1
from edgar.offerings.prospectus import Prospectus424B, OfferingType


# gh-868 — the lock-up table header that must never appear as an underwriter.
_LOCKUP_JUNK = "Earliest Date Available for Sale in the Public Market"


class TestIssue868S1Underwriters:
    """The S-1 underwriting roster must contain firm names, not table junk."""

    @pytest.mark.vcr
    def test_s1_lead_manager_is_real_underwriter(self):
        # Airbnb S-1 (2020-11-16), registration file 333-250118.
        obj = get_by_accession_number("0001193125-20-294801").obj()
        assert isinstance(obj, RegistrationS1)
        uw = obj.underwriting
        assert uw is not None

        names = [u.name for u in uw.underwriters]
        # The lock-up "Shares Eligible for Future Sale" header must be gone.
        assert _LOCKUP_JUNK not in names
        # lead_manager is the real lead-left bookrunner for Airbnb's IPO.
        assert uw.lead_manager == "Morgan Stanley & Co. LLC"
        # The syndicate is still present and deduplicated.
        assert "Goldman Sachs & Co. LLC" in names
        assert len(names) == len(set(names))

    @pytest.mark.vcr
    def test_s1a_lead_manager_is_real_underwriter(self):
        # Airbnb S-1/A (2020-12-07), same registration file.
        obj = get_by_accession_number("0001193125-20-311265").obj()
        uw = obj.underwriting
        assert uw is not None
        names = [u.name for u in uw.underwriters]
        assert _LOCKUP_JUNK not in names
        assert uw.lead_manager == "Morgan Stanley & Co. LLC"


class TestIssue869IpoClassification:
    """A mixed primary+secondary IPO 424B4 must classify as IPO, not resale."""

    @pytest.mark.vcr
    def test_abnb_424b4_classified_as_ipo(self):
        # Airbnb 424B4 (2020-12-11), IPO final pricing prospectus.
        f = get_by_accession_number("0001193125-20-315318")
        obj = f.obj()
        assert isinstance(obj, Prospectus424B)

        assert obj.offering_type == OfferingType.IPO
        assert obj.offering_type_confidence == "high"

        # The deal economics were always correct — guard against regressing them.
        assert obj.deal.price == 68.0
        assert obj.deal.shares == 51323531
