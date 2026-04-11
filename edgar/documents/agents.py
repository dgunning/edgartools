"""
Filing agent detection from HTML document signatures.

SEC filings are prepared by filing agents (Workiva, Donnelley/DFIN, Toppan Merrill, etc.)
that leave distinctive signatures in the HTML content. Detecting the agent enables
agent-specific parsing strategies, particularly for Table of Contents extraction.

Based on empirical survey of 200 10-K filings (March 2026):
  Workiva ~35%, Donnelley/DFIN ~26%, Toppan Merrill ~11%, Novaworks ~9%,
  CompSci ~3%, Certent ~2%, Broadridge/EDGARsuite/SEC Publisher <1% each.
"""

from typing import Optional

__all__ = ['detect_filing_agent']

# Agent name constants
WORKIVA = 'Workiva'
DONNELLEY = 'Donnelley'
TOPPAN_MERRILL = 'Toppan Merrill'
NOVAWORKS = 'Novaworks'
COMPSCI = 'CompSci'
CERTENT = 'Certent'
BROADRIDGE = 'Broadridge'
EDGARSUITE = 'EDGARsuite'
SEC_PUBLISHER = 'SEC Publisher'


def detect_filing_agent(html_content: str) -> Optional[str]:
    """
    Identify the filing agent from HTML document signatures.

    Scans only the first 3000 characters of the document, where all known
    agent signatures appear (HTML comments, meta tags, copyright notices).
    Checks in frequency order for early exit.

    Args:
        html_content: Raw HTML content of the primary filing document

    Returns:
        Agent name string, or None if unrecognized
    """
    head = html_content[:3000]

    if 'Workiva' in head:
        return WORKIVA
    if 'DFIN' in head or 'Donnelley' in head or 'dfinsolutions' in head:
        return DONNELLEY
    if 'Merrill' in head or 'Toppan' in head:
        return TOPPAN_MERRILL
    if 'ThunderDome' in head:
        return NOVAWORKS
    if 'Field: Set; Name: xdx;' in head:
        return NOVAWORKS
    if 'CompSci' in head or 'compsciresources' in head:
        return COMPSCI
    if 'Certent' in head:
        return CERTENT
    if 'Broadridge' in head:
        return BROADRIDGE
    if 'EDGARsuite' in head or 'Advanced Computer Innovations' in head:
        return EDGARSUITE
    if 'SEC Publisher' in head:
        return SEC_PUBLISHER

    return None
