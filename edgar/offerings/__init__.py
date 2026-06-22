"""SEC offerings: prospectuses, registration statements, and exempt/crowdfunding offerings.

Organized into domain subpackages:
- ``crowdfunding`` — Regulation Crowdfunding (Form C) and the campaign lifecycle view
- ``exempt``       — Regulation D exempt offerings (Form D)
- ``prospectus``   — 424B prospectuses, S-1/S-3/DRS registration statements, fee tables

The former flat module paths (``edgar.offerings.formc``, ``edgar.offerings._fee_table``,
``edgar.offerings.registration_s1``, …) remain importable via thin back-compat shims.
"""
from __future__ import annotations

from edgar.offerings.crowdfunding import (
    Campaign,
    Offering,
    FormC,
    FundingPortal,
    IssuerCompany,
    Signer,
    group_offerings_by_file_number,
)
from edgar.offerings.exempt import FormD
from edgar.offerings.prospectus import Prospectus424B, OfferingType
from edgar.offerings.prospectus.registration_s1 import RegistrationS1, S1OfferingType, S1CoverPage
from edgar.offerings.prospectus.drs import DraftRegistrationStatement
from edgar.offerings.prospectus.registration_s3 import RegistrationS3, S3OfferingType, S3CoverPage

__all__ = [
    "Campaign",
    "Offering",
    "FormC",
    "FundingPortal",
    "IssuerCompany",
    "Signer",
    "FormD",
    "Prospectus424B",
    "OfferingType",
    "RegistrationS1",
    "S1OfferingType",
    "S1CoverPage",
    "DraftRegistrationStatement",
    "RegistrationS3",
    "S3OfferingType",
    "S3CoverPage",
    "group_offerings_by_file_number",
]
