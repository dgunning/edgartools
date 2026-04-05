"""Parser for 13F information table XML format."""

import pandas as pd
from lxml import etree

from edgar.reference import cusip_ticker_mapping

__all__ = ['parse_infotable_xml']


def parse_infotable_xml(infotable_xml: str) -> pd.DataFrame:
    """
    Parse the infotable xml and return a pandas DataFrame using lxml for maximum performance.

    Args:
        infotable_xml: XML content of the information table

    Returns:
        pd.DataFrame: Holdings data with columns matching the XML structure

    Performance: Optimized to use lxml's etree directly instead of BeautifulSoup.
    - BeautifulSoup version: ~10-26 seconds for 24K holdings
    - lxml direct version: ~1-2 seconds for 24K holdings (10-20x faster)
    """
    # Parse XML with lxml (much faster than BeautifulSoup)
    # Strip leading/trailing whitespace to handle edge cases
    xml_content = infotable_xml.strip()

    try:
        root = etree.fromstring(xml_content.encode('utf-8'))
    except etree.XMLSyntaxError:
        # Fallback: Try to parse with more lenient parser
        parser = etree.XMLParser(recover=True)
        root = etree.fromstring(xml_content.encode('utf-8'), parser=parser)

    rows = []
    shares_or_principal = {"SH": "Shares", "PRN": "Principal"}

    # Extract namespace (if present)
    nsmap = root.nsmap
    # Prioritize the default namespace (None key), otherwise use any namespace
    if nsmap:
        # Use default namespace if it exists, otherwise use first available
        ns_value = nsmap.get(None) or list(nsmap.values())[0]
        # Only use the SEC 13F namespace, ignore other namespaces like xsd/xsi
        if 'thirteenf' in ns_value or 'informationtable' in ns_value.lower():
            ns = {'ns': ns_value}
            prefix = 'ns:'
        else:
            # No relevant namespace found, try without prefix
            ns = {}
            prefix = ''
    else:
        ns = {}
        prefix = ''

    # Use findall with namespace to get all infoTable elements
    info_tables_list = root.findall(f'.//{prefix}infoTable', namespaces=ns)
    # Debug
    if len(info_tables_list) == 0:
        # Try without namespace
        info_tables_list = root.findall('.//infoTable')

    for info_tag in info_tables_list:
        # Helper function to safely get text from child elements
        def get_text(tag_name: str, parent=None, default: str = "") -> str:
            """Get text from a child element, returns default if not found."""
            parent = parent if parent is not None else info_tag
            # Use namespace prefix for element lookup
            element = parent.find(f'{prefix}{tag_name}', namespaces=ns)
            if element is not None and element.text:
                return element.text.strip()
            return default

        # Helper to get int value
        def get_int(tag_name: str, parent=None, default: int = 0) -> int:
            """Get integer value from a child element."""
            text = get_text(tag_name, parent)
            try:
                return int(float(text)) if text else default
            except (ValueError, TypeError):
                return default

        info_table = {}

        # Extract direct children (single pass)
        info_table['Issuer'] = get_text("nameOfIssuer")
        info_table['Class'] = get_text("titleOfClass")
        info_table['Cusip'] = get_text("cusip")
        info_table['Value'] = get_int("value")
        info_table["PutCall"] = get_text("putCall")
        info_table['InvestmentDiscretion'] = get_text("investmentDiscretion")
        info_table['OtherManager'] = get_text("otherManager")  # Issue #512: Manager assignment per holding

        # Shares or principal (nested element)
        shares_tag = info_tag.find(f'{prefix}shrsOrPrnAmt', namespaces=ns)
        if shares_tag is None:
            continue

        info_table['SharesPrnAmount'] = get_int("sshPrnamt", parent=shares_tag)

        ssh_prnamt_type = get_text("sshPrnamtType", parent=shares_tag)
        info_table['Type'] = shares_or_principal.get(ssh_prnamt_type)

        # Voting authority (nested element)
        voting_auth_tag = info_tag.find(f'{prefix}votingAuthority', namespaces=ns)
        if voting_auth_tag is not None:
            info_table['SoleVoting'] = get_int("Sole", parent=voting_auth_tag)
            info_table['SharedVoting'] = get_int("Shared", parent=voting_auth_tag)
            info_table['NonVoting'] = get_int("None", parent=voting_auth_tag)
        else:
            info_table['SoleVoting'] = 0
            info_table['SharedVoting'] = 0
            info_table['NonVoting'] = 0

        rows.append(info_table)

    table = pd.DataFrame(rows)

    # Debug: Check if table has data
    if len(table) == 0:
        return table  # Return empty DataFrame early

    # Add the ticker symbol
    cusip_mapping = cusip_ticker_mapping(allow_duplicate_cusips=False)
    table['Ticker'] = table.Cusip.map(cusip_mapping.Ticker)

    return table
