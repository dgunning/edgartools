"""ATS-N (Alternative Trading System) filings — data objects and parsers.

ATS-N is the SEC form filed by broker-dealers operating Alternative Trading
Systems (dark pools and non-exchange electronic venues). Filings disclose
order types, fees, access criteria, matching rules, and conflicts of interest.

Form variants:
    ATS-N     — initial filing
    ATS-N/MA  — material amendment
    ATS-N/UA  — updating amendment
    ATS-N/CA  — correcting amendment
    ATS-N-W   — withdrawal
"""
from __future__ import annotations

from edgar.ats.atsn import (
    AlternativeTradingSystem,
    AlternativeTradingSystemWithdrawal,
    from_atsn_filing,
)
from edgar.ats.models import (
    ATSAddress,
    ATSIdentifyingInfo,
    ATSNameRecord,
    ATSOperations,
    ATSOperatorActivities,
    FilerContact,
)

__all__ = [
    "AlternativeTradingSystem",
    "AlternativeTradingSystemWithdrawal",
    "ATSAddress",
    "ATSIdentifyingInfo",
    "ATSNameRecord",
    "ATSOperations",
    "ATSOperatorActivities",
    "FilerContact",
    "ATS_N_FORMS",
    "ATS_N_AMENDMENT_FORMS",
    "ATS_N_WITHDRAWAL_FORMS",
    "ATS_N_ALL_FORMS",
    "from_atsn_filing",
]

ATS_N_FORMS = ["ATS-N"]
ATS_N_AMENDMENT_FORMS = ["ATS-N/MA", "ATS-N/UA", "ATS-N/CA"]
ATS_N_WITHDRAWAL_FORMS = ["ATS-N-W"]
ATS_N_ALL_FORMS = ATS_N_FORMS + ATS_N_AMENDMENT_FORMS + ATS_N_WITHDRAWAL_FORMS
