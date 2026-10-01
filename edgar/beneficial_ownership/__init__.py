"""
Schedule 13D and Schedule 13G beneficial ownership report parsing.

This package provides classes for parsing and working with SEC Schedule 13D
and Schedule 13G filings, which disclose beneficial ownership of 5% or more
of a company's securities.

Schedule 13D: Active ownership with potential control intent (activist filings)
Schedule 13G: Passive institutional investor ownership

These are Section 13(d)/(g) filings. Which package holds the form you have:

    Schedule 13D / 13G           edgar.beneficial_ownership  (this package)
    Forms 3, 4, 5 and 144        edgar.ownership             Section 16: a company's own insiders
    13F-HR                       edgar.thirteenf             Section 13(f): institutional managers

Both classes are also importable from the top level: ``from edgar import Schedule13D``.

Example usage:
    from edgar import Filing
    from edgar.beneficial_ownership import Schedule13D

    filing = Filing(form='SCHEDULE 13D', cik='1373604', accession_no='...')
    schedule = filing.obj()  # Returns Schedule13D instance

    print(schedule.issuer_info.name)
    print(schedule.reporting_persons)
    print(schedule.items.item4_purpose_of_transaction)
"""

from edgar.beneficial_ownership.models import IssuerInfo, ReportingPerson, Schedule13DItems, Schedule13GItems, SecurityInfo, Signature
from edgar.beneficial_ownership.schedule13 import Schedule13D, Schedule13G

__all__ = [
    'Schedule13D',
    'Schedule13G',
    'ReportingPerson',
    'IssuerInfo',
    'SecurityInfo',
    'Schedule13DItems',
    'Schedule13GItems',
    'Signature'
]
