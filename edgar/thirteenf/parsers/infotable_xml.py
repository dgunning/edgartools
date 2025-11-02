"""Parser for 13F information table XML format."""

import pandas as pd

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
        info_table = dict()

        info_table['Issuer'] = child_text(info_tag, "nameOfIssuer")
        info_table['Class'] = child_text(info_tag, "titleOfClass")
        info_table['Cusip'] = child_text(info_tag, "cusip")
        info_table['Value'] = int(child_text(info_tag, "value"))

        # Shares or principal
        shares_tag = info_tag.find("shrsOrPrnAmt")
        info_table['SharesPrnAmount'] = child_text(shares_tag, "sshPrnamt")

        # Shares or principal
        ssh_prnamt_type = child_text(shares_tag, "sshPrnamtType")
        info_table['Type'] = shares_or_principal.get(ssh_prnamt_type)

        info_table["PutCall"] = child_text(info_tag, "putCall") or ""
        info_table['InvestmentDiscretion'] = child_text(info_tag, "investmentDiscretion")

        # Voting authority
        voting_auth_tag = info_tag.find("votingAuthority")
        info_table['SoleVoting'] = int(float(child_text(voting_auth_tag, "Sole")))
        info_table['SharedVoting'] = int(float(child_text(voting_auth_tag, "Shared")))
        info_table['NonVoting'] = int(float(child_text(voting_auth_tag, "None")))
        rows.append(info_table)

    table = pd.DataFrame(rows)

    # Add the ticker symbol
    cusip_mapping = cusip_ticker_mapping(allow_duplicate_cusips=False)
    table['Ticker'] = table.Cusip.map(cusip_mapping.Ticker)

    return table
