"""Form C (Regulation Crowdfunding) parsing.

This package preserves the original ``edgar.offerings.crowdfunding.formc`` import surface —
every name that was importable from the former single module is re-exported here.
"""
from __future__ import annotations

from edgar.offerings.crowdfunding.formc.models import (
    FilerInformation,
    FundingPortal,
    IssuerInformation,
    OfferingInformation,
    AnnualReportDisclosure,
    PersonSignature,
    IssuerSignature,
    Signer,
    SignatureInfo,
)
from edgar.offerings.crowdfunding.formc.helpers import (
    split_list,
    maybe_float,
    maybe_date,
    group_offerings_by_file_number,
)
from edgar.offerings.crowdfunding.formc.core import IssuerCompany, FormC

__all__ = ['FormC', 'Signer', 'FundingPortal', 'IssuerCompany']
