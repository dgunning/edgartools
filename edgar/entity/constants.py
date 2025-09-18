"""
Constants for entity classification and form types.

This module contains constants used throughout the entity package for
determining entity types and form classifications.
"""

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
    "20-F", "40-F",  # Foreign issuers
    "11-K",  # Employee benefit plans
    # Current reports
    "8-K", "6-K",
    # Proxy materials
    "DEF 14A", "PRE 14A", "DEFA14A", "DEFM14A",
    # Other corporate filings
    "424B1", "424B2", "424B3", "424B4", "424B5",
    "ARS", "NT 10-K", "NT 10-Q",
    "SC 13D", "SC 13G", "SC TO-I", "SC TO-T",
    "SD", "PX14A6G",
    # Specialized corporate filings
    "N-CSR", "N-Q", "N-MFP", "N-CEN",
    "X-17A-5", "17-H",
    "TA-1", "TA-2",
    "ATS-N",
    # Corporate disclosures
    "EFFECT", "FWP", "425", "CB",
    "POS AM", "CORRESP", "UPLOAD"
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