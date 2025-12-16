"""Parser for 13F information table XML format."""

import pandas as pd
from bs4 import Tag

from edgar.reference import cusip_ticker_mapping
from edgar.xmltools import child_text, find_element

__all__ = ['parse_infotable_xml']


def parse_infotable_xml(infotable_xml: str) -> pd.DataFrame:
    """
    Parse the infotable xml and return a pandas DataFrame

    Args:
        infotable_xml: XML content of the information table

    Returns:
        pd.DataFrame: Holdings data with columns matching the XML structure
    """
    root = find_element(infotable_xml, "informationTable")
    rows = []
    shares_or_principal = {"SH": "Shares", "PRN": "Principal"}
    for info_tag in root.find_all("infoTable"):
        if not isinstance(info_tag, Tag):
            continue
        info_table = dict()

        info_table['Issuer'] = child_text(info_tag, "nameOfIssuer")
        info_table['Class'] = child_text(info_tag, "titleOfClass")
        info_table['Cusip'] = child_text(info_tag, "cusip")
        info_table['Value'] = int(child_text(info_tag, "value") or "0")

        # Shares or principal
        shares_tag = info_tag.find("shrsOrPrnAmt")
        if not isinstance(shares_tag, Tag):
            continue
        info_table['SharesPrnAmount'] = int(child_text(shares_tag, "sshPrnamt") or "0")

        # Shares or principal
        ssh_prnamt_type = child_text(shares_tag, "sshPrnamtType")
        info_table['Type'] = shares_or_principal.get(ssh_prnamt_type)

        info_table["PutCall"] = child_text(info_tag, "putCall") or ""
        info_table['InvestmentDiscretion'] = child_text(info_tag, "investmentDiscretion")
        info_table['OtherManager'] = child_text(info_tag, "otherManager")  # Issue #512: Manager assignment per holding

        # Voting authority
        voting_auth_tag = info_tag.find("votingAuthority")
        if isinstance(voting_auth_tag, Tag):
            info_table['SoleVoting'] = int(float(child_text(voting_auth_tag, "Sole") or "0"))
            info_table['SharedVoting'] = int(float(child_text(voting_auth_tag, "Shared") or "0"))
            info_table['NonVoting'] = int(float(child_text(voting_auth_tag, "None") or "0"))
        else:
            info_table['SoleVoting'] = 0
            info_table['SharedVoting'] = 0
            info_table['NonVoting'] = 0
        rows.append(info_table)

    table = pd.DataFrame(rows)

    # Add the ticker symbol
    cusip_mapping = cusip_ticker_mapping(allow_duplicate_cusips=False)
    table['Ticker'] = table.Cusip.map(cusip_mapping.Ticker)

    return table
