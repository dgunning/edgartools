"""
Constants for entity classification and form types.

This module contains constants used throughout the entity package for
determining entity types and form classifications.
"""

import re
from typing import List, Optional

# Performance optimization: use set for O(1) lookups
COMPANY_FORMS = {
    # Registration statements
    "S-1", "S-3", "S-4", "S-8", "S-11",
    # Foreign issuers registration forms
    "F-1", "F-3", "F-4", "F-6", "F-7", "F-8", "F-9", "F-10", "F-80",
    # Foreign form amendments and effectiveness
    "F-6EF", "F-6 POS", "F-3ASR", "F-4MEF", "F-10EF", "F-3D", "F-3MEF",
    # Exchange Act registration
    "10-12B", "10-12G",
    # Periodic reports
    "10-K", "10-Q", "10-K/A", "10-Q/A",
    "10-KSB", "10-KSB/A",      # Small business annual report (pre-2008)
    "10-QSB", "10-QSB/A",      # Small business quarterly report (pre-2008)
    "20-F", "20-F/A",           # Foreign issuers
    "40-F", "40-F/A",           # Foreign issuers
    "11-K", "11-K/A",           # Employee benefit plans
    # Current reports
    "8-K", "8-K/A",
    "6-K", "6-K/A",             # Foreign issuers
    # Proxy materials
    "DEF 14A", "PRE 14A", "DEFA14A", "DEFM14A",
    "DEF 14C",                  # Information statement (no vote required)
    "DEFR14A",                  # Definitive revised proxy
    "PREM14A",                  # Preliminary merger proxy
    "PREC14A",                  # Preliminary revised consent solicitation
    # Prospectus supplements
    "424B1", "424B2", "424B3", "424B4", "424B5",
    # Annual reports and notices
    "ARS", "NT 10-K", "NT 10-Q",
    # Tender offers
    "SC TO-I", "SC TO-T",
    "SD", "PX14A6G",
    # Investment company forms
    "N-CSR", "N-CSR/A",
    "N-CSRS", "N-CSRS/A",      # Semi-annual certified shareholder report
    "N-Q", "N-Q/A",
    "N-MFP", "N-CEN",
    "N-1A", "N-1A/A",          # Open-end fund registration
    "N-2", "N-2/A",            # Closed-end fund registration
    "N-14", "N-14/A",          # Fund merger/reorganization registration
    "N-PX",                    # Annual proxy voting record
    "N-8A",                    # Notification of registration (Investment Company Act)
    "485APOS", "485BPOS",      # Post-effective amendments
    "497", "497K",             # Fund prospectus supplements
    # Broker-dealer and transfer agent
    "X-17A-5", "17-H",
    "TA-1", "TA-2",
    "ATS-N",
    # Corporate disclosures
    "EFFECT", "FWP", "425", "CB",
    "POS AM", "CORRESP", "UPLOAD",
    "NO ACT",                  # No-action letter
}

# Fund-specific form types
FUND_FORMS = {
    # Investment company registration
    "N-1A", "N-2", "N-3", "N-4", "N-5", "N-6",
    # Investment company periodic reports
    "N-CSR", "N-Q", "N-CEN", "N-MFP",
    # Investment adviser forms
    "ADV", "ADV-E", "ADV-H", "ADV-NR", "ADV-W",
    # Private fund forms
    "PF", "CPO-PQR", "CTA-PR",
    # Municipal advisor forms
    "MA", "MA-I", "MA-NR", "MA-W",
    # Investment company shareholder reports
    "N-30B-2", "N-30D", "485APOS", "485BPOS",
    # Variable insurance products
    "N-3/A", "N-4/A", "N-6/A",
    # Closed-end funds
    "N-2/A", "N-5/A",
    # Business development companies
    "N-6F", "N-54A", "N-54C",
    # Exchange-traded funds
    "N-1A/A",
    # Portfolio holdings
    "NPORT-P", "NPORT-EX", "N-PORT", "N-PORT/A"
}

# Individual/insider forms
INDIVIDUAL_FORMS = {
    # Ownership reports
    "3", "4", "5", "3/A", "4/A", "5/A",
    # Beneficial ownership
    "SC 13D", "SC 13G", "SC 13D/A", "SC 13G/A",
    # Tender offer schedules
    "SC TO-I", "SC TO-C", "SC TO-T",
    # Investment adviser representatives
    "ADV-E", "DRS"
}

# All known form types for validation
ALL_FORM_TYPES = COMPANY_FORMS | FUND_FORMS | INDIVIDUAL_FORMS

# Name-based heuristic constants for company detection
# Loose keywords: substring match (keyword appears anywhere in uppercased name)
# Only include words that are long enough or distinctive enough to avoid
# matching inside common personal names (e.g. "LP" in "ALPINE").
COMPANY_NAME_KEYWORDS = {
    # Corporate structure
    "CORP", "CORPORATION", "LLC", "L.L.C.", "LTD", "LIMITED",
    "L.P.", "COMPANY", "GROUP", "HOLDINGS",
    "PARTNERS", "PARTNERSHIP",
    # Investment entities
    "TRUST", "FUND", "FUNDS", "CAPITAL", "VENTURES",
    "MANAGEMENT", "ADVISORS", "ADVISERS", "SECURITIES",
    "INVESTMENT", "INVESTMENTS", "PORTFOLIO",
    # Industries
    "TECHNOLOGIES", "SERVICES", "INTERNATIONAL", "GLOBAL",
    "FINANCIAL", "BANK", "INDUSTRIES", "SYSTEMS", "ENTERPRISES",
    # Organizations
    "FOUNDATION", "ASSOCIATION", "AUTHORITY",
}

# Strict keywords: whole-word match only (to avoid false positives like
# "INC" in "LINCOLN", "LP" in "ALPINE", "CO" in "SCOTT")
COMPANY_NAME_KEYWORDS_STRICT = {"CO", "NA", "PLC", "SA", "INC", "LP"}

# Pre-compiled regex for SEC filing suffixes like /ADR/, /BD/, /TA/
_SEC_SUFFIX_RE = re.compile(r"/[A-Z0-9-]{2,}(?:/|\s|$)")


def _name_suggests_company(name: str) -> bool:
    """Check if entity name contains company keywords."""
    if not name:
        return False
    upper = name.upper()

    # Loose keyword match (substring)
    if any(kw in upper for kw in COMPANY_NAME_KEYWORDS):
        return True

    # Strict keyword match (whole word only)
    words = set(re.split(r"\W+", upper))
    if words & COMPANY_NAME_KEYWORDS_STRICT:
        return True

    # SEC filing suffixes like /ADR/, /BD/, /TA/ indicate companies
    if _SEC_SUFFIX_RE.search(name):
        return True

    return False


def _classify_is_individual(
    *,
    name: Optional[str] = None,
    tickers: Optional[List[str]] = None,
    exchanges: Optional[List[str]] = None,
    state_of_incorporation: Optional[str] = None,
    entity_type: Optional[str] = None,
    forms: Optional[List[str]] = None,
    ein: Optional[str] = None,
    cik: Optional[int] = None,
    insider_transaction_for_issuer_exists: Optional[bool] = None,
    insider_transaction_for_owner_exists: Optional[bool] = None,
) -> bool:
    """
    Determine if an entity is an individual using a 9-signal priority chain.

    This is the single source of truth for entity classification, called by
    both EntityData.is_individual and is_individual_from_json().

    Returns True if the entity is an individual, False if a company.
    """

    # 1. Strongest: receives insider filings as ISSUER -> definitely a company
    if insider_transaction_for_issuer_exists is True:
        return False

    # 2. Has tickers or exchanges -> traded company
    if tickers and len(tickers) > 0:
        return False
    if exchanges and len(exchanges) > 0:
        return False

    # 3. State of incorporation -> company (with exception)
    if state_of_incorporation and state_of_incorporation.strip():
        if cik == 1033331:  # Reed Hastings
            return True
        return False

    # 4. Entity type indicates company
    if entity_type and entity_type not in ('', 'other'):
        return False

    # 5. Company-specific forms in filing history
    if forms:
        if any(form in COMPANY_FORMS for form in forms):
            if cik == 315090:  # Warren Buffett
                return True
            return False

    # 6. Valid EIN -> company (with exception)
    if ein and ein != "000000000":
        if cik == 315090:  # Warren Buffett
            return True
        return False

    # 7. Name contains company keywords -> company
    if _name_suggests_company(name):
        return False

    # 8. Files as insider owner (without being issuer) -> individual
    if insider_transaction_for_owner_exists is True:
        return True

    # 9. Default: individual
    return True
